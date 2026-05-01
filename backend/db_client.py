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

def fetch_current_state():
    """pulls queue and active matches from firestore and builds the pool of available players"""
    active_docs = list(db.collection("matches").where("status", "in", ["in_progress", "standby"]).stream())
    active_matches = [d.to_dict() for d in active_docs]
    for i, d in enumerate(active_docs):
        active_matches[i]["match_doc_id"] = d.id

    queue_docs = list(db.collection("queue").order_by("check_in_time").stream())
    raw_queue = []
    for d in queue_docs:
        q = d.to_dict()
        q["queue_doc_id"] = d.id
        raw_queue.append(q)

    pids = set()
    for m in active_matches:
        pids.update(m.get("team_a", []))
        pids.update(m.get("team_b", []))
    for q in raw_queue:
        pids.add(q["player_id"])

    player_map = {}
    if pids:
        refs = [db.collection("players").document(pid) for pid in pids]
        snaps = db.get_all(refs)
        player_map = {s.id: s.to_dict() for s in snaps if s.exists}

    in_progress_players = []
    for m in active_matches:
        if m.get("status") == "in_progress":
            for pid in m.get("team_a", []) + m.get("team_b", []):
                if pid in player_map:
                    p = dict(player_map[pid])
                    if "mu" in p and "sigma" in p:
                        p["player_doc_id"] = pid
                        in_progress_players.append(p)

    queue = []
    seen_pids = set()
    for q in raw_queue:
        pid = q["player_id"]
        if pid in seen_pids:
            db.collection("queue").document(q["queue_doc_id"]).delete()
            continue
            
        player = player_map.get(pid)
        if not player or player.get("is_in_game") or player.get("is_in_standby"):
            db.collection("queue").document(q["queue_doc_id"]).delete()
            continue
            
        seen_pids.add(pid)
        entry = {**player, **q}
        entry["player_doc_id"] = pid
        entry["colour_tier"] = entry.get("colour_tier") or entry.get("tier")
        queue.append(entry)

    return {
        "active_matches": active_matches,
        "in_progress_players": in_progress_players,
        "queue": queue,
        "num_courts": 4
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
    for pid in standby_match_data.get("team_a", []) + standby_match_data.get("team_b", []):
        batch.update(db.collection("players").document(pid), {"is_in_game": True, "is_in_standby": False})
    batch.commit()

def _update_ratings(team_a_ids, team_b_ids, team_a_won, is_unranked=False):
    all_ids = team_a_ids + team_b_ids
    snaps = db.get_all([db.collection("players").document(pid) for pid in all_ids])
    player_docs = {s.id: s.to_dict() for s in snaps if s.exists}

    team_a_ratings = {pid: env.create_rating(player_docs[pid]["mu"], player_docs[pid]["sigma"]) for pid in team_a_ids if pid in player_docs}
    team_b_ratings = {pid: env.create_rating(player_docs[pid]["mu"], player_docs[pid]["sigma"]) for pid in team_b_ids if pid in player_docs}

    if not is_unranked and team_a_ratings and team_b_ratings:
        ranks = [0, 1] if team_a_won else [1, 0]
        new_a, new_b = env.rate([team_a_ratings, team_b_ratings], ranks=ranks)
    else:
        new_a, new_b = team_a_ratings, team_b_ratings

    batch = db.batch()
    for pid, rating in {**new_a, **new_b}.items():
        ref = db.collection("players").document(pid)
        update = {"games_played": firestore.Increment(1)}
        if not is_unranked:
            update["mu"] = rating.mu
            update["sigma"] = rating.sigma
        batch.update(ref, update)
    batch.commit()

def _check_tier_promotion(player_ids):
    snaps = db.get_all([db.collection("players").document(pid) for pid in player_ids])
    batch = db.batch()
    changes = False

    for snap in snaps:
        if not snap.exists:
            continue
        p = snap.to_dict()

        current = p.get("colour_tier") or p.get("tier")
        mu = p.get("mu", 25.0)
        new = current
        for name in TIERS:
            low, high = TIER_BOUNDARIES[name]
            if low <= mu < high:
                new = name
                break

        if new != current:
            batch.update(snap.reference, {"colour_tier": new})
            changes = True

    if changes:
        batch.commit()

def _requeue_players(winners_ids, losers_ids, winners_names, losers_names):
    now = time.time()
    batch = db.batch()
    
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
            
    batch.commit()

def process_finished_matches():
    """finds recently completed matches to update ratings, check tiers, and throw players back in the queue"""
    finished = list(
        db.collection("matches")
        .where("status", "in", ["completed", "voided"])
        .stream()
    )
    for doc in finished:
        m = doc.to_dict()
        mid = doc.id
        status = m.get("status")

        team_a = m.get("team_a", [])
        team_b = m.get("team_b", [])
        team_a_names = m.get("team_a_names", [])
        team_b_names = m.get("team_b_names", [])

        if status == "completed":
            team_a_won = (m.get("winner") in ("a", "Team A"))
            _update_ratings(
                team_a, team_b,
                team_a_won=team_a_won,
                is_unranked=m.get("unranked", False),
            )
            _check_tier_promotion(team_a + team_b)
            
            if team_a_won:
                _requeue_players(team_a, team_b, team_a_names, team_b_names)
            else:
                _requeue_players(team_b, team_a, team_b_names, team_a_names)
            print(f"match #{m.get('match_number')} done, players requeued")
        else:
            print(f"match #{m.get('match_number')} voided, players checked out")
            void_batch = db.batch()
            for pid in team_a + team_b:
                void_batch.update(db.collection("players").document(pid), {"is_in_game": False, "is_in_standby": False, "is_in_queue": False})
            void_batch.commit()

        db.collection("matches").document(mid).delete()
