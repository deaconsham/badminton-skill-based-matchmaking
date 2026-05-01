import os
import time
import firebase_admin
from firebase_admin import credentials, firestore
import trueskill

env = trueskill.TrueSkill(draw_probability=0.0)
trueskill.setup(env=env)

TIERS = ["Beginner", "Intermediate", "Advanced", "Elite"]
TIER_BOUNDARIES = {
    "Beginner": (0,20),
    "Intermediate": (20,30),
    "Advanced": (30,40),
    "Elite": (40,float("inf")),
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED_PATH = os.path.join(BASE_DIR, "badminton-matchmaking-9b69f-firebase-adminsdk-fbsvc-cceede915a.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(CRED_PATH)
    firebase_admin.initialize_app(cred)
db = firestore.client()

def _get_all_players_from_match(match):
    """returns a combined list of player ids from both teams in a match"""
    return match.get("team_a", []) + match.get("team_b", [])

def clean_invalid_queue_entries():
    """cleans queue of duplicate entries and ensures batch limits"""
    queue_docs = list(db.collection("queue").stream())
    batch = db.batch()
    ops_count = 0
    seen_pids = set()
    
    for doc in queue_docs:
        q = doc.to_dict()
        pid = q["player_id"]
        
        if pid in seen_pids:
            batch.delete(doc.reference)
            ops_count += 1
            continue
            
        seen_pids.add(pid)
        
        if ops_count >= 490: 
            batch.commit()
            batch = db.batch()
            ops_count = 0

    if ops_count > 0:
        batch.commit()

def fetch_current_state():
    """pulls queue and active matches from firestore and builds the pool of available players"""
    clean_invalid_queue_entries()
    
    active_docs = list(db.collection("matches").where("status", "in", ["in_progress", "standby"]).stream())
    active_matches = [{"match_doc_id": d.id, **d.to_dict()} for d in active_docs]

    queue_docs = list(db.collection("queue").order_by("check_in_time").stream())
    raw_queue = [{"queue_doc_id": d.id, **d.to_dict()} for d in queue_docs]

    pids = set(q["player_id"] for q in raw_queue)
    for m in active_matches:
        pids.update(_get_all_players_from_match(m))

    player_map = {}
    if pids:
        refs = [db.collection("players").document(pid) for pid in pids]
        for i in range(0, len(refs), 100):
            snaps = db.get_all(refs[i:i+100])
            player_map.update({s.id: s.to_dict() for s in snaps if s.exists})

    in_progress_players = []
    for m in active_matches:
        if m.get("status") == "in_progress":
            for pid in _get_all_players_from_match(m):
                p = player_map.get(pid)
                if p and "mu" in p and "sigma" in p:
                    in_progress_players.append({"player_doc_id": pid, **p})

    queue = []
    for q in raw_queue:
        pid = q["player_id"]
        player = player_map.get(pid)
        
        if not player or player.get("is_in_game") or player.get("is_in_standby"):
            continue
            
        queue.append({
            **player, 
            **q, 
            "player_doc_id": pid,
            "colour_tier": player.get("colour_tier") or player.get("tier")
        })

    return {
        "active_matches": active_matches,
        "in_progress_players": in_progress_players,
        "queue": queue
    }

def record_match(match_data, court_number, status="in_progress"):
    """writes a new match to the database and pulls players out of the queue"""
    existing = (
        db.collection("matches")
        .order_by("match_number", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    last_num = 0
    for doc in existing:
        last_num = doc.to_dict().get("match_number", 0)

    team_a_ids = [p["player_doc_id"] for p in match_data["team_a"]]
    team_b_ids = [p["player_doc_id"] for p in match_data["team_b"]]
    team_a_names = [p["name"] for p in match_data["team_a"]]
    team_b_names = [p["name"] for p in match_data["team_b"]]

    _, ref = db.collection("matches").add({
        "match_number": last_num + 1,
        "court_number": court_number,
        "team_a": team_a_ids,
        "team_b": team_b_ids,
        "team_a_names": team_a_names,
        "team_b_names": team_b_names,
        "winner": None,
        "unranked": match_data.get("unranked", False),
        "skill_delta": match_data.get("skill_delta", 0),
        "status": status,
        "created_at": time.time(),
        "started_at": time.time() if status == "in_progress" else None,
    })

    batch = db.batch()
    for pid in team_a_ids + team_b_ids:
        player_ref = db.collection("players").document(pid)
        if status == "in_progress":
            batch.update(player_ref, {"is_in_game": True, "is_in_queue": False, "is_in_standby": False})
        elif status == "standby":
            batch.update(player_ref, {"is_in_standby": True, "is_in_queue": False, "is_in_game": False})
            
    for p in match_data["team_a"] + match_data["team_b"]:
        qid = p.get("queue_doc_id")
        if qid:
            batch.delete(db.collection("queue").document(qid))
            
    batch.commit()
    return ref.id

def set_standby_active(standby_id, court_number, standby_match_data):
    """moves a standby match to an active court"""
    db.collection("matches").document(standby_id).update({
        "status": "in_progress",
        "court_number": court_number,
        "started_at": time.time(),
    })
    
    batch = db.batch()
    for pid in _get_all_players_from_match(standby_match_data):
        batch.update(db.collection("players").document(pid), {"is_in_game": True, "is_in_standby": False})
    batch.commit()

def _update_ratings(team_a_ids, team_b_ids, team_a_won, is_unranked, player_docs, batch):
    """updates trueskill ratings for all players in a match"""
    team_a_ratings = {pid: env.create_rating(player_docs[pid]["mu"], player_docs[pid]["sigma"]) for pid in team_a_ids if pid in player_docs}
    team_b_ratings = {pid: env.create_rating(player_docs[pid]["mu"], player_docs[pid]["sigma"]) for pid in team_b_ids if pid in player_docs}

    if not is_unranked and team_a_ratings and team_b_ratings:
        ranks = [0, 1] if team_a_won else [1, 0]
        new_a, new_b = env.rate([team_a_ratings, team_b_ratings], ranks=ranks)
    else:
        new_a, new_b = team_a_ratings, team_b_ratings

    for pid, rating in {**new_a, **new_b}.items():
        ref = db.collection("players").document(pid)
        update = {"games_played": firestore.Increment(1)}
        if not is_unranked:
            update["mu"] = rating.mu
            update["sigma"] = rating.sigma
        batch.update(ref, update)

def _check_tier_promotion(player_docs, batch):
    """checks and updates player tiers based on their new trueskill mu values"""
    for pid, p in player_docs.items():
        current = p.get("colour_tier") or p.get("tier")
        mu = p.get("mu", 25.0)
        new = current
        for name in TIERS:
            low, high = TIER_BOUNDARIES[name]
            if low <= mu < high:
                new = name
                break

        if new != current:
            ref = db.collection("players").document(pid)
            batch.update(ref, {"colour_tier": new})

def _requeue_players(winners_ids, losers_ids, winners_names, losers_names, batch):
    """places players back into the queue after a match finishes"""
    now = time.time()
    
    for ids, names, offset in [(winners_ids, winners_names, 0.0), (losers_ids, losers_names, 1.0)]:
        check_in = now + offset
        for pid, name in zip(ids, names):
            ref = db.collection("queue").document()
            batch.set(ref, {
                "player_id": pid,
                "name": name,
                "check_in_time": check_in,
                "requested_teammate": None,
            })
            player_ref = db.collection("players").document(pid)
            batch.update(player_ref, {"is_in_queue": True, "is_in_game": False, "is_in_standby": False})

def process_finished_matches():
    """finds recently completed matches to update ratings, check tiers, and throw players back in the queue"""
    finished = list(
        db.collection("matches")
        .where("status", "in", ["completed", "voided"])
        .stream()
    )
    if not finished:
        return

    batch = db.batch()
    
    for doc in finished:
        m = doc.to_dict()
        mid = doc.id
        status = m.get("status")
        
        all_players = _get_all_players_from_match(m)

        if status == "completed":
            snaps = []
            if all_players:
                snaps = db.get_all([db.collection("players").document(pid) for pid in all_players])
            player_docs = {s.id: s.to_dict() for s in snaps if s.exists}

            team_a_won = (m.get("winner") in ("a", "Team A"))
            
            _update_ratings(m.get("team_a", []), m.get("team_b", []), team_a_won, m.get("unranked", False), player_docs, batch)
            _check_tier_promotion(player_docs, batch)
            
            if team_a_won:
                _requeue_players(m.get("team_a", []), m.get("team_b", []), m.get("team_a_names", []), m.get("team_b_names", []), batch)
            else:
                _requeue_players(m.get("team_b", []), m.get("team_a", []), m.get("team_b_names", []), m.get("team_a_names", []), batch)
                
            print(f"match #{m.get('match_number')} done, players requeued")
        else:
            print(f"match #{m.get('match_number')} voided, players checked out")
            for pid in all_players:
                batch.update(db.collection("players").document(pid), {"is_in_game": False, "is_in_standby": False, "is_in_queue": False})

        batch.delete(doc.reference)
        
    batch.commit()
