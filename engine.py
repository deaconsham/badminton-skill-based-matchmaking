import time
import itertools
import traceback
import firebase_admin
from firebase_admin import credentials, firestore
import trueskill

cred = credentials.Certificate("badminton-matchmaking-9b69f-firebase-adminsdk-fbsvc-cceede915a.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

env = trueskill.TrueSkill(draw_probability=0.0)
trueskill.setup(env=env)

TIERS = ["Beginner", "Intermediate", "Advanced", "Elite"]
TIER_ORDER = {t: i for i, t in enumerate(TIERS)}

TIER_BOUNDARIES = {
    "Beginner": (0,20),
    "Intermediate": (20,30),
    "Advanced": (30,40),
    "Elite": (40,float("inf")),
}

STARTING_MU = {
    "Beginner": 15.0,
    "Intermediate": 25.0,
    "Advanced": 35.0,
    "Elite": 45.0,
}

NUM_COURTS = 4
POLL_INTERVAL = 2
SPREAD_THRESHOLD = 8.0
STARVATION_RELAX_PER_MIN = 0.5
LOOK_AHEAD_FACTOR = 0.6
SIGMA_THRESHOLD = 6.0


def compute_rating(mu):
    return max(0, min(9999, int(round(mu * 50))))


def normalise_tier(raw):
    if raw in TIER_ORDER:
        return raw
    return TIER_FALLBACK.get(raw, "Intermediate")


def fetch_queue():
    queue_docs = list(db.collection("queue").order_by("check_in_time").stream())
    if not queue_docs:
        return []

    refs = [db.collection("players").document(q.to_dict()["player_id"]) for q in queue_docs]
    player_map = {s.id: s.to_dict() for s in db.get_all(refs) if s.exists}

    queue = []
    seen_pids = set()
    for q_doc in queue_docs:
        q = q_doc.to_dict()
        pid = q["player_id"]
        
        if pid in seen_pids:
            db.collection("queue").document(q_doc.id).delete()
            continue
            
        player = player_map.get(pid)
        if not player or player.get("is_in_game") or player.get("is_in_standby"):
            db.collection("queue").document(q_doc.id).delete()
            continue
            
        seen_pids.add(pid)
        entry = {**player, **q}
        entry["queue_doc_id"]  = q_doc.id
        entry["player_doc_id"] = pid
        entry["colour_tier"]   = normalise_tier(entry.get("colour_tier") or entry.get("tier"))
        queue.append(entry)
    return queue


def _all_team_splits(lobby):
    indices = [0, 1, 2, 3]
    seen = set()
    for pair in itertools.combinations(indices, 2):
        complement = tuple(i for i in indices if i not in pair)
        key = frozenset([pair, complement])
        if key not in seen:
            seen.add(key)
            yield [lobby[pair[0]], lobby[pair[1]]], [lobby[complement[0]], lobby[complement[1]]]


def _opponent_reqs(p):
    return [r for r in [p.get("requested_opponent1"), p.get("requested_opponent2")] if r]


def _check_requests(lobby):
    lobby_ids = {p["player_doc_id"] for p in lobby}
    for p in lobby:
        req_tm = p.get("requested_teammate")
        if req_tm and req_tm not in lobby_ids:
            return False
        for req_op in _opponent_reqs(p):
            if req_op not in lobby_ids:
                return False
    return True


def _requests_satisfied(team_a, team_b):
    team_a_ids = {p["player_doc_id"] for p in team_a}
    team_b_ids = {p["player_doc_id"] for p in team_b}
    for team, opp_ids in [(team_a, team_b_ids), (team_b, team_a_ids)]:
        team_ids = {p["player_doc_id"] for p in team}
        for p in team:
            req_tm = p.get("requested_teammate")
            if req_tm and req_tm not in team_ids:
                return False
            for req_op in _opponent_reqs(p):
                if req_op not in opp_ids:
                    return False
    return True


def _lobby_is_unranked(lobby):
    vals = [TIER_ORDER.get(p["colour_tier"], 1) for p in lobby]
    return (max(vals) - min(vals)) > 1


def _lobby_spread(lobby):
    """Range of mu values across all 4 players (primary quality metric)."""
    mus = [p["mu"] for p in lobby]
    return max(mus) - min(mus)


def _best_split(lobby):
    """Return (team_a, team_b, match_quality) for the most balanced team split
    using TrueSkill's quality calculation, respecting player pairing requests.
    Returns (None, None, 0.0) if no valid split."""
    best_quality = -1.0
    best_a = best_b = None
    for team_a, team_b in _all_team_splits(lobby):
        if not _requests_satisfied(team_a, team_b):
            continue
        
        team_a_ratings = [env.create_rating(p["mu"], p["sigma"]) for p in team_a]
        team_b_ratings = [env.create_rating(p["mu"], p["sigma"]) for p in team_b]
        
        quality = env.quality([team_a_ratings, team_b_ratings])
        
        if quality > best_quality:
            best_quality = quality
            best_a, best_b = team_a, team_b
            
    return best_a, best_b, max(0.0, best_quality)


def _best_future_spread(player_mu, in_progress_mus):
    if len(in_progress_mus) < 3:
        return float("inf")
    best = float("inf")
    for combo in itertools.combinations(in_progress_mus, 3):
        all_mus = [player_mu] + list(combo)
        spread = max(all_mus) - min(all_mus)
        if spread < best:
            best = spread
    return best


def find_best_match(queue, in_progress_mus=None, must_fill=False):
    if in_progress_mus is None:
        in_progress_mus = []
    if len(queue) < 4:
        return None

    now = time.time()

    def _score_lobby(lobby):
        if not _check_requests(lobby):
            return None
        spread = _lobby_spread(lobby)
        team_a, team_b, quality = _best_split(lobby)
        if team_a is None:
            return None
        unranked = _lobby_is_unranked(lobby) or any(p.get("unranked_flag") for p in lobby)
        return {
            "team_a": team_a,
            "team_b": team_b,
            "match_quality": quality,
            "lobby_spread": spread,
            "unranked": unranked,
            "skill_delta": abs(sum(p["mu"] for p in team_a) - sum(p["mu"] for p in team_b)),
        }

    for i, anchor in enumerate(queue):
        anchor_tier = TIER_ORDER.get(anchor["colour_tier"], 1)
        best_fair_match = None
        best_fair_key = None
        
        other_players = queue[:i] + queue[i+1:]
        for combo in itertools.combinations(other_players, 3):
            lobby = [anchor] + list(combo)
            is_same_rank = all(TIER_ORDER.get(p["colour_tier"], 1) == anchor_tier for p in lobby)
            spread = _lobby_spread(lobby)
            
            if is_same_rank or spread <= SPREAD_THRESHOLD:
                match_data = _score_lobby(lobby)
                if match_data:
                    key = (spread, -match_data["match_quality"])
                    if best_fair_key is None or key < best_fair_key:
                        best_fair_key = key
                        best_fair_match = match_data
                        
        if best_fair_match:
            return best_fair_match

    def _find_fallback(pool):
        if len(pool) < 4:
            return None
            
        for i, anchor in enumerate(pool):
            other_players = pool[:i] + pool[i+1:]
            best_fallback_match = None
            best_fallback_key = None
            
            for combo in itertools.combinations(other_players, 3):
                lobby = [anchor] + list(combo)
                match_data = _score_lobby(lobby)
                if match_data:
                    key = (match_data["lobby_spread"], -match_data["match_quality"])
                    if best_fallback_key is None or key < best_fallback_key:
                        best_fallback_key = key
                        best_fallback_match = match_data
                        
            if best_fallback_match:
                return best_fallback_match
        return None

    if not must_fill:
        waiting_players = set()
        for anchor in queue:
            future_spread = _best_future_spread(anchor["mu"], in_progress_mus)
            if future_spread <= SPREAD_THRESHOLD:
                waiting_players.add(anchor["player_doc_id"])

        available_queue = [p for p in queue if p["player_doc_id"] not in waiting_players]
        match = _find_fallback(available_queue)
        if match:
            return match
            
    return _find_fallback(queue)


def update_ratings(team_a_ids, team_b_ids, team_a_won, is_unranked=False):
    all_ids = team_a_ids + team_b_ids
    player_docs = {
        s.id: s.to_dict()
        for s in db.get_all([db.collection("players").document(pid) for pid in all_ids])
        if s.exists
    }

    team_a_ratings = {pid: env.create_rating(player_docs[pid]["mu"], player_docs[pid]["sigma"]) for pid in team_a_ids}
    team_b_ratings = {pid: env.create_rating(player_docs[pid]["mu"], player_docs[pid]["sigma"]) for pid in team_b_ids}

    if not is_unranked:
        ranks = [0, 1] if team_a_won else [1, 0]
        new_a, new_b = env.rate([team_a_ratings, team_b_ratings], ranks=ranks)
    else:
        new_a, new_b = team_a_ratings, team_b_ratings

    batch = db.batch()
    for pid, rating in {**new_a, **new_b}.items():
        ref = db.collection("players").document(pid)
        update = {"games_played": firestore.Increment(1)}
        if not is_unranked:
            update["mu"]    = rating.mu
            update["sigma"] = rating.sigma
        batch.update(ref, update)
    batch.commit()


def check_tier_promotion(player_ids):
    snaps   = db.get_all([db.collection("players").document(pid) for pid in player_ids])
    batch   = db.batch()
    changes = []

    for snap in snaps:
        if not snap.exists:
            continue
        p = snap.to_dict()
        if p.get("sigma", 999) > SIGMA_THRESHOLD:
            continue

        current = normalise_tier(p.get("colour_tier") or p.get("tier"))
        mu      = p["mu"]
        new     = current
        for name in TIERS:
            low, high = TIER_BOUNDARIES[name]
            if low <= mu < high:
                new = name
                break

        if new != current:
            batch.update(snap.reference, {"colour_tier": new})
            changes.append({"player_id": snap.id, "name": p["name"], "old": current, "new": new})

    if changes:
        batch.commit()
        for c in changes:
            print(f"tier: {c['name']} {c['old']} → {c['new']}")

    return changes


def record_match(match, court_number, status="in_progress"):
    existing = (
        db.collection("matches")
        .order_by("match_number", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    last_num = 0
    for doc in existing:
        last_num = doc.to_dict().get("match_number", 0)

    team_a_ids   = [p["player_doc_id"] for p in match["team_a"]]
    team_b_ids   = [p["player_doc_id"] for p in match["team_b"]]
    team_a_names = [p["name"] for p in match["team_a"]]
    team_b_names = [p["name"] for p in match["team_b"]]

    _, ref = db.collection("matches").add({
        "match_number":  last_num + 1,
        "court_number":  court_number,
        "team_a":        team_a_ids,
        "team_b":        team_b_ids,
        "team_a_names":  team_a_names,
        "team_b_names":  team_b_names,
        "winner":        None,
        "unranked":      match["unranked"],
        "skill_delta":   match.get("skill_delta", 0),
        "status":        status,
        "created_at":    time.time(),
    })

    batch = db.batch()
    for pid in team_a_ids + team_b_ids:
        player_ref = db.collection("players").document(pid)
        if status == "in_progress":
            batch.update(player_ref, {"is_in_game": True, "is_in_queue": False, "is_in_standby": False})
        elif status == "standby":
            batch.update(player_ref, {"is_in_standby": True, "is_in_queue": False, "is_in_game": False})
    batch.commit()

    return ref.id


def _remove_from_queue(players):
    batch = db.batch()
    for p in players:
        qid = p.get("queue_doc_id")
        if qid:
            batch.delete(db.collection("queue").document(qid))
    batch.commit()


def requeue_players(team_a_ids, team_b_ids, team_a_names, team_b_names):
    now   = time.time()
    batch = db.batch()
    for pid, name in zip(team_a_ids + team_b_ids, team_a_names + team_b_names):
        ref = db.collection("queue").document()
        batch.set(ref, {
            "player_id":           pid,
            "name":                name,
            "check_in_time":       now,
            "requested_teammate":  None,
            "requested_opponent1": None,
            "requested_opponent2": None,
            "unranked_flag":       False,
        })
        player_ref = db.collection("players").document(pid)
        batch.update(player_ref, {"is_in_queue": True, "is_in_game": False, "is_in_standby": False})
    batch.commit()


def process_finished_matches():
    finished = list(
        db.collection("matches")
        .where("status", "in", ["completed", "voided"])
        .stream()
    )
    for doc in finished:
        m      = doc.to_dict()
        mid    = doc.id
        status = m.get("status")

        if status == "completed":
            update_ratings(
                m["team_a"], m["team_b"],
                team_a_won=(m.get("winner") in ("a", "Team A")),
                is_unranked=m.get("unranked", False),
            )
            check_tier_promotion(m["team_a"] + m["team_b"])
            requeue_players(m["team_a"], m["team_b"], m["team_a_names"], m["team_b_names"])
            print(f"match #{m.get('match_number')} done, players requeued")
        else:
            print(f"match #{m.get('match_number')} voided, players checked out")
            void_batch = db.batch()
            for pid in m.get("team_a", []) + m.get("team_b", []):
                void_batch.update(db.collection("players").document(pid), {"is_in_game": False, "is_in_standby": False, "is_in_queue": False})
            void_batch.commit()

        db.collection("matches").document(mid).update({
            "status":      "archived",
            "archived_at": time.time(),
        })


def _fetch_in_progress_mus(active_docs):
    """Batch-fetch mu values for all players currently on active courts.
    Used by the look-ahead phase in find_best_match."""
    in_progress_pids = [
        pid
        for d in active_docs
        for pid in (d.to_dict().get("team_a", []) + d.to_dict().get("team_b", []))
        if d.to_dict().get("status") == "in_progress"
    ]
    if not in_progress_pids:
        return []
    refs  = [db.collection("players").document(pid) for pid in in_progress_pids]
    snaps = db.get_all(refs)
    return [s.to_dict()["mu"] for s in snaps if s.exists and "mu" in s.to_dict()]


def auto_matchmaking():
    active = list(
        db.collection("matches")
        .where("status", "in", ["in_progress", "standby"])
        .stream()
    )

    occupied:      set[int]  = set()
    standby_id:    str | None = None
    standby_court: int | None = None

    for d in active:
        m = d.to_dict()
        court = m.get("court_number")
        if court:
            occupied.add(court)
        if m.get("status") == "standby":
            standby_id    = d.id
            standby_court = court

    free = [c for c in range(1, NUM_COURTS + 1) if c not in occupied]

    if not free and standby_id is None:
        return

    in_progress_mus = _fetch_in_progress_mus(active)

    if standby_id and free:
        target = standby_court if standby_court in free else free[0]
        db.collection("matches").document(standby_id).update({
            "status":       "in_progress",
            "court_number": target,
            "started_at":   time.time(),
        })
        
        standby_match = db.collection("matches").document(standby_id).get().to_dict()
        batch = db.batch()
        for pid in standby_match.get("team_a", []) + standby_match.get("team_b", []):
            batch.update(db.collection("players").document(pid), {"is_in_game": True, "is_in_standby": False})
        batch.commit()
        
        print(f"court {target} active")
        occupied.add(target)
        free.remove(target)
        standby_id = None

    already_matched: set[str] = set()

    for court_num in free:
        queue = [p for p in fetch_queue() if p["player_doc_id"] not in already_matched]
        if len(queue) < 4:
            break
        match = find_best_match(queue, in_progress_mus, must_fill=True)
        if not match:
            continue
        record_match(match, court_num, status="in_progress")
        _remove_from_queue(match["team_a"] + match["team_b"])
        already_matched |= {p["player_doc_id"] for p in match["team_a"] + match["team_b"]}
        occupied.add(court_num)
        print(f"court {court_num} filled (spread {match.get('lobby_spread', 0):.1f} mu)")
        in_progress_mus.extend(p["mu"] for p in match["team_a"] + match["team_b"])

    if standby_id is None:
        queue = [p for p in fetch_queue() if p["player_doc_id"] not in already_matched]
        if len(queue) >= 4:
            match = find_best_match(queue, in_progress_mus)
            if match:
                record_match(match, None, status="standby")
                _remove_from_queue(match["team_a"] + match["team_b"])
                print(f"standby ready (spread {match.get('lobby_spread', 0):.1f} mu)")


def is_engine_enabled():
    snap = db.collection("settings").document("engine").get()
    return snap.exists and snap.to_dict().get("enabled", False)


def main_loop():
    print("engine started")
    while True:
        try:
            if is_engine_enabled():
                process_finished_matches()
                auto_matchmaking()
        except Exception as e:
            print(f"error: {e}")
            traceback.print_exc()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
