import time
import itertools
import firebase_admin
from firebase_admin import credentials, firestore
import trueskill

cred = credentials.Certificate("badminton-matchmaking-9b69f-firebase-adminsdk-fbsvc-cceede915a.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

env = trueskill.TrueSkill(draw_probability=0.0)
trueskill.setup(env=env)

TIER_BOUNDARIES = {"Green": (0, 20), "Yellow": (20, 30), "Orange": (30, 40), "Red": (40, float("inf"))}
TIER_NAMES = ["Green", "Yellow", "Orange", "Red"]
STARTING_MU = {"Green": 15.0, "Yellow": 25.0, "Orange": 35.0, "Red": 45.0}
SIGMA_CONFIDENCE_THRESHOLD = 6.0

RATING_RANGES = {
    "Green": (0, 999),
    "Yellow": (1000, 1499),
    "Orange": (1500, 1999),
    "Red": (2000, 9999),
}


def compute_rating(mu: float) -> int:
    """Converts mu to a display-friendly integer rating (mu * 50), clamped to [0, 9999]."""
    return max(0, min(9999, int(round(mu * 50))))


def fetch_queue() -> list[dict]:
    """
    Pulls all entries from Firestore 'queue' collection, oldest first.
    Fetches the linked player doc for each and merges them into one dict.
    
    Returns:
        list[dict]: merged queue + player data, sorted by check_in_time ASC
    """
    queue_docs = (
        db.collection("queue")
        .order_by("check_in_time")
        .stream()
    )

    queue: list[dict] = []
    for q_doc in queue_docs:
        q = q_doc.to_dict()
        q["queue_doc_id"] = q_doc.id

        player_ref = db.collection("players").document(q["player_id"])
        player_snap = player_ref.get()
        if not player_snap.exists:
            continue

        player = player_snap.to_dict()
        player["player_doc_id"] = q["player_id"]

        entry = {**player, **q}
        queue.append(entry)

    return queue


def _all_team_splits(lobby: list[dict]):
    """
    Yields all 3 unique ways to split 4 players into 2v2 teams.
    
    Yields:
        tuple(team_a, team_b): two lists of 2 player dicts each
    """
    indices = [0, 1, 2, 3]
    seen: set[frozenset] = set()
    for pair in itertools.combinations(indices, 2):
        complement = tuple(i for i in indices if i not in pair)
        key = frozenset([pair, complement])
        if key not in seen:
            seen.add(key)
            team_a = [lobby[pair[0]], lobby[pair[1]]]
            team_b = [lobby[complement[0]], lobby[complement[1]]]
            yield team_a, team_b


def _check_requests(lobby: list[dict]) -> bool:
    """
    Checks if teammate/opponent requests can be satisfied within this lobby.
    If any request references a player NOT in the lobby, returns False.
    """
    lobby_ids = {p["player_doc_id"] for p in lobby}

    for p in lobby:
        # Check teammate request
        req_tm = p.get("requested_teammate")
        if req_tm and req_tm not in lobby_ids:
            return False
            
        # Check multiple opponent requests
        opp_reqs = [p.get("requested_opponent"), p.get("requested_opponent1"), p.get("requested_opponent2")]
        for req_op in opp_reqs:
            if req_op and req_op not in lobby_ids:
                return False
    return True


def _requests_satisfied(team_a: list[dict], team_b: list[dict]) -> bool:
    """
    Validates a specific 2v2 split against player requests.
    Teammate requests must be on the same team, opponent requests on opposite.
    """
    team_a_ids = {p["player_doc_id"] for p in team_a}
    team_b_ids = {p["player_doc_id"] for p in team_b}

    for team, other_team_ids in [(team_a, team_b_ids), (team_b, team_a_ids)]:
        team_ids = {p["player_doc_id"] for p in team}
        for p in team:
            # Teammate check
            req_tm = p.get("requested_teammate")
            if req_tm and req_tm not in team_ids:
                return False
                
            # Opponent check (multiple allowed)
            opp_reqs = [p.get("requested_opponent"), p.get("requested_opponent1"), p.get("requested_opponent2")]
            for req_op in opp_reqs:
                if req_op and req_op not in other_team_ids:
                    return False
    return True


def _lobby_is_unranked(lobby: list[dict]) -> bool:
    """
    Checks if a lobby should be flagged unranked due to tier distance.
    If any two players are 2+ tiers apart, the match is unranked.
    
    Tier Order:
        Green(0) > Yellow(1) > Orange(2) > Red(3)
    """
    tier_values = [{"Green": 0, "Yellow": 1, "Orange": 2, "Red": 3}[p["colour_tier"]] for p in lobby]
    max_distance = max(tier_values) - min(tier_values)
    return max_distance > 1


def find_best_match(queue: list[dict]) -> dict | None:
    """
    Finds the best 4-player lobby and 2v2 team split from the queue.
    
    Anchor Logic:
        queue[0] is the longest waiting player, they must play
        searches all C(n-1, 3) combinations for the other 3 players
        evaluates all 3 possible team splits per combination
    
    Cost Function:
        cost = skill_delta - (0.4 * total_wait_seconds)
        lower cost = better match (balanced skill + rewarded wait time)
    
    Returns:
        dict with team_a, team_b, cost, skill_delta, total_wait_min, unranked
        None if fewer than 4 players in queue
    """
    if len(queue) < 4:
        return None

    anchor = queue[0]
    candidates = queue[1:]
    now = time.time()

    best_cost = float("inf")
    best_match: dict | None = None

    for trio in itertools.combinations(candidates, 3):
        lobby = [anchor, *trio]

        if not _check_requests(lobby):
            continue

        unranked = _lobby_is_unranked(lobby)

        if any(p.get("unranked_flag") for p in lobby):
            unranked = True

        for team_a, team_b in _all_team_splits(lobby):
            if not _requests_satisfied(team_a, team_b):
                continue

            skill_delta = abs(
                sum(p["mu"] for p in team_a) - sum(p["mu"] for p in team_b)
            )

            total_wait = sum(now - p["check_in_time"] for p in lobby)
            wait_bonus = 0.4 * total_wait

            cost = skill_delta - wait_bonus

            if cost < best_cost:
                best_cost = cost
                best_match = {
                    "team_a": team_a,
                    "team_b": team_b,
                    "cost": cost,
                    "skill_delta": skill_delta,
                    "total_wait_min": total_wait / 60,
                    "unranked": unranked,
                }

    return best_match


def update_ratings(
    team_a_ids: list[str],
    team_b_ids: list[str],
    team_a_won: bool,
    is_unranked: bool = False,
) -> None:
    """
    Runs TrueSkill rating update and writes new values to Firestore.
    
    Args:
        team_a_ids: list of 2 Firestore player doc IDs
        team_b_ids: list of 2 Firestore player doc IDs
        team_a_won: True if Team A won
        is_unranked: if True, only increments games_played (mu/sigma unchanged)
    
    Note: Uses Firestore batch write so all 4 player updates are atomic.
    """
    all_ids = team_a_ids + team_b_ids
    player_docs: dict[str, dict] = {}
    for pid in all_ids:
        snap = db.collection("players").document(pid).get()
        if snap.exists:
            player_docs[pid] = snap.to_dict()

    team_a_ratings = {pid: env.create_rating(player_docs[pid]["mu"], player_docs[pid]["sigma"]) for pid in team_a_ids}
    team_b_ratings = {pid: env.create_rating(player_docs[pid]["mu"], player_docs[pid]["sigma"]) for pid in team_b_ids}

    if not is_unranked:
        if team_a_won:
            (new_a, new_b) = env.rate([team_a_ratings, team_b_ratings], ranks=[0, 1])
        else:
            (new_a, new_b) = env.rate([team_a_ratings, team_b_ratings], ranks=[1, 0])
    else:
        new_a = team_a_ratings
        new_b = team_b_ratings

    batch = db.batch()
    for pid, rating in {**new_a, **new_b}.items():
        ref = db.collection("players").document(pid)
        update_data = {"games_played": firestore.Increment(1)}
        if not is_unranked:
            update_data["mu"] = rating.mu
            update_data["sigma"] = rating.sigma
        batch.update(ref, update_data)

    batch.commit()


def check_tier_promotion(player_ids: list[str]) -> list[dict]:
    """
    Checks if any players should be promoted or demoted based on their mu.
    Only triggers when sigma is below the confidence threshold (enough games played).

    Args:
        player_ids: list of Firestore player doc IDs to check

    Returns:
        list of dicts with player_id, name, old_tier, new_tier for each change
    """
    changes = []
    batch = db.batch()

    for pid in player_ids:
        snap = db.collection("players").document(pid).get()
        if not snap.exists:
            continue

        p = snap.to_dict()

        if p["sigma"] > SIGMA_CONFIDENCE_THRESHOLD:
            continue

        current_tier = p["colour_tier"]
        mu = p["mu"]

        new_tier = current_tier
        for tier_name in TIER_NAMES:
            low, high = TIER_BOUNDARIES[tier_name]
            if low <= mu < high:
                new_tier = tier_name
                break

        if new_tier != current_tier:
            batch.update(db.collection("players").document(pid), {"colour_tier": new_tier})
            changes.append({
                "player_id": pid,
                "name": p["name"],
                "old_tier": current_tier,
                "new_tier": new_tier,
            })

    if changes:
        batch.commit()

    return changes


def record_match(match: dict, court_number: int, status: str = "in_progress") -> str:
    """
    Creates a new document in the 'matches' collection.
    Auto-increments match_number based on the last recorded match.
    
    Args:
        match: dict from find_best_match() with team_a, team_b, unranked
        court_number: which court (1-4)
        status: "standby" for on-deck matches, "in_progress" for active matches
    
    Returns:
        str: auto-generated Firestore document ID for the match
    """
    existing = db.collection("matches").order_by("match_number", direction=firestore.Query.DESCENDING).limit(1).stream()
    last_num = 0
    for doc in existing:
        last_num = doc.to_dict().get("match_number", 0)

    team_a_ids = [p["player_doc_id"] for p in match["team_a"]]
    team_b_ids = [p["player_doc_id"] for p in match["team_b"]]
    team_a_names = [p["name"] for p in match["team_a"]]
    team_b_names = [p["name"] for p in match["team_b"]]

    match_doc = {
        "match_number": last_num + 1,
        "court_number": court_number,
        "team_a": team_a_ids,
        "team_b": team_b_ids,
        "team_a_names": team_a_names,
        "team_b_names": team_b_names,
        "winner": None,
        "unranked": match["unranked"],
        "skill_delta": match.get("skill_delta", 0),
        "status": status,
        "created_at": time.time(),
    }
    _, ref = db.collection("matches").add(match_doc)
    return ref.id


def requeue_players(team_a_ids: list[str], team_b_ids: list[str], team_a_names: list[str], team_b_names: list[str]) -> None:
    """
    Sends all players back to the end of the queue.
    """
    all_player_ids = team_a_ids + team_b_ids
    all_names = team_a_names + team_b_names
    now = time.time()
    batch = db.batch()

    for i, pid in enumerate(all_player_ids):
        # We don't bother deleting old queue entries here because 
        # players in matches have already been removed from the queue
        # by create_standby_match.
        new_ref = db.collection("queue").document()
        batch.set(new_ref, {
            "player_id": pid,
            "name": all_names[i],
            "check_in_time": now,
            "requested_teammate": None,
            "requested_opponent": None,
            "requested_opponent1": None,
            "requested_opponent2": None,
            "unranked_flag": False,
        })
    batch.commit()


def create_standby_match(court_number: int) -> dict | None:
    """
    Creates the next match on standby so players can get ready.
    Pulls from the queue, records the match as "standby", and removes
    those players from the queue so they aren't double-matched.
    
    Args:
        court_number: which court this standby match is for
    
    Returns:
        dict with match info and match_doc_id, or None if not enough players
    """
    queue = fetch_queue()
    match = find_best_match(queue)

    if match is None:
        return None

    match_doc_id = record_match(match, court_number, status="standby")

    all_players = match["team_a"] + match["team_b"]
    batch = db.batch()
    for p in all_players:
        if "queue_doc_id" in p:
            batch.delete(db.collection("queue").document(p["queue_doc_id"]))
    batch.commit()

    match["match_doc_id"] = match_doc_id
    return match


def activate_standby_match(match_doc_id: str) -> None:
    """
    Moves a standby match to in_progress when the court is ready.
    
    Args:
        match_doc_id: Firestore document ID of the standby match
    """
    db.collection("matches").document(match_doc_id).update({
        "status": "in_progress",
        "started_at": time.time(),
    })


def auto_matchmaking():
    """
    Finds available courts and assigns new matches.
    After all courts are filled, creates a standby match if possible.
    """
    active_matches_docs = list(db.collection("matches").where("status", "in", ["in_progress", "standby"]).stream())
    occupied_courts = set()
    has_standby = False
    
    for d in active_matches_docs:
        m = d.to_dict()
        occupied_courts.add(m.get("court_number"))
        if m.get("status") == "standby":
            has_standby = True
    
    for court_num in range(1, 5):
        if court_num in occupied_courts:
            continue
            
        queue = fetch_queue()
        if len(queue) < 4:
            return
            
        print(f"Court {court_num} is free. Attempting to match...")
        match = create_standby_match(court_num)
        if match:
            activate_standby_match(match["match_doc_id"])
            print(f"  MATCH LIVE: Court {court_num} is now active.")
            occupied_courts.add(court_num)
        else:
            print(f"  No valid match found for Court {court_num} (constraints not met)")

    if not has_standby:
        queue = fetch_queue()
        if len(queue) >= 4:
            next_court = min(range(1, 5), key=lambda c: c)
            print(f"Creating standby match for next available court...")
            match = find_best_match(queue)
            if match:
                match_doc_id = record_match(match, next_court, status="standby")
                all_players = match["team_a"] + match["team_b"]
                batch = db.batch()
                for p in all_players:
                    if "queue_doc_id" in p:
                        batch.delete(db.collection("queue").document(p["queue_doc_id"]))
                batch.commit()
                print(f"  STANDBY: Match ready on deck.")


def process_finished_matches():
    """
    Checks for completed/voided matches to update ratings and re-queue players.
    """
    finished = db.collection("matches").where("status", "in", ["completed", "voided"]).stream()
    
    for doc in finished:
        m = doc.to_dict()
        mid = doc.id
        status = m.get("status")
        
        print(f"Processing {status} Match #{m.get('match_number')}...")
        
        if status == "completed":
            update_ratings(
                m["team_a"], m["team_b"], 
                team_a_won=(m["winner"] == "a" or m["winner"] == "Team A"),
                is_unranked=m.get("unranked", False)
            )
            check_tier_promotion(m["team_a"] + m["team_b"])
            
        requeue_players(m["team_a"], m["team_b"], m["team_a_names"], m["team_b_names"])
        
        # Archive the match
        db.collection("matches").document(mid).update({"status": "archived", "archived_at": time.time()})
        print(f"  Match #{m.get('match_number')} archived and players re-queued.")


def is_engine_enabled() -> bool:
    snap = db.collection("settings").document("engine").get()
    if snap.exists:
        return snap.to_dict().get("enabled", False)
    return False


def main_loop():
    print("Matchmaking started")
    
    while True:
        try:
            if is_engine_enabled():
                process_finished_matches()
                auto_matchmaking()
            
        except Exception as e:
            print(f"ERROR: {e}")
            
        time.sleep(1)


if __name__ == "__main__":
    main_loop()
