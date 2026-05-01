import time
import itertools
import trueskill

env = trueskill.TrueSkill(draw_probability=0.0)
trueskill.setup(env=env)

SPREAD_THRESHOLD = 10.0
STARVATION_RELAX_PER_MIN = 0.25

def _all_team_splits(lobby):
    indices = [0, 1, 2, 3]
    seen = set()
    for pair in itertools.combinations(indices, 2):
        complement = tuple(i for i in indices if i not in pair)
        key = frozenset([pair, complement])
        if key not in seen:
            seen.add(key)
            yield [lobby[pair[0]], lobby[pair[1]]], [lobby[complement[0]], lobby[complement[1]]]

def _requests_satisfied(team_a, team_b):
    team_a_ids = {p["player_doc_id"] for p in team_a}
    team_b_ids = {p["player_doc_id"] for p in team_b}
    for team, opp_ids in [(team_a, team_b_ids), (team_b, team_a_ids)]:
        team_ids = {p["player_doc_id"] for p in team}
        for p in team:
            req_tm = p.get("requested_teammate")
            if req_tm and req_tm not in team_ids:
                return False
    return True

def _check_requests(lobby):
    lobby_ids = {p["player_doc_id"] for p in lobby}
    for p in lobby:
        req_tm = p.get("requested_teammate")
        if req_tm and req_tm not in lobby_ids:
            return False
    return True

def _lobby_spread(lobby):
    mus = [p["mu"] for p in lobby]
    return max(mus) - min(mus)

def _best_split(lobby):
    best_score = -float("inf")
    best_a = best_b = None
    best_quality = 0.0
    best_delta = 0.0
    best_disparity = 0.0

    for team_a, team_b in _all_team_splits(lobby):
        if not _requests_satisfied(team_a, team_b):
            continue
        
        team_a_ratings = [env.create_rating(p["mu"], p["sigma"]) for p in team_a]
        team_b_ratings = [env.create_rating(p["mu"], p["sigma"]) for p in team_b]
        
        quality = env.quality([team_a_ratings, team_b_ratings])
        
        spread_a = abs(team_a[0]["mu"] - team_a[1]["mu"])
        if team_a[0].get("requested_teammate") == team_a[1]["player_doc_id"] and team_a[1].get("requested_teammate") == team_a[0]["player_doc_id"]:
            spread_a = 0.0

        spread_b = abs(team_b[0]["mu"] - team_b[1]["mu"])
        if team_b[0].get("requested_teammate") == team_b[1]["player_doc_id"] and team_b[1].get("requested_teammate") == team_b[0]["player_doc_id"]:
            spread_b = 0.0

        disparity_penalty = spread_a + spread_b
        
        split_score = (quality * 100.0) - (disparity_penalty * 2.0) - (_lobby_spread(lobby) * 1.0)
        
        if split_score > best_score:
            best_score = split_score
            best_a, best_b = team_a, team_b
            best_quality = quality
            best_delta = abs(sum(p["mu"] for p in team_a) - sum(p["mu"] for p in team_b))
            best_disparity = disparity_penalty
            
    return best_a, best_b, max(0.0, best_quality), best_delta, best_disparity

def _score_lobby(lobby):
    """calculates a heuristic score for a lobby using trueskill and a penalty for unequal partner skill disparity"""
    if not _check_requests(lobby):
        return None
        
    team_a, team_b, quality, skill_delta, disparity_penalty = _best_split(lobby)
    if team_a is None:
        return None
        
    real_spread = _lobby_spread(lobby)
    heuristic_score = (quality * 100.0) - (disparity_penalty * 2.0) - (real_spread * 1.0)
    
    unranked = False
    if skill_delta > 15.0 or real_spread > 20.0:
        unranked = True
        
    return {
        "team_a": team_a,
        "team_b": team_b,
        "match_quality": quality,
        "lobby_spread": real_spread,
        "unranked": unranked,
        "skill_delta": skill_delta,
        "heuristic_score": heuristic_score,
    }

def _find_fairest_fallback(pool):
    best_fallback = None
    best_fallback_score = -float('inf')
    
    if len(pool) < 4:
        return None
        
    for combo in itertools.combinations(pool, 4):
        lobby = list(combo)
        match_data = _score_lobby(lobby)
        if match_data and match_data["heuristic_score"] > best_fallback_score:
            best_fallback_score = match_data["heuristic_score"]
            best_fallback = match_data
            
    return best_fallback

def _find_match_queue_traversal(pool, in_progress_players):
    """iterates through the queue to find the best match for each player, skipping anyone who is stalling for a better game"""
    now = time.time()
    stalling_players = set()
    
    global_best_match = None
    global_best_score = -float('inf')
    
    for anchor in pool:
        if anchor["player_doc_id"] in stalling_players:
            continue
            
        other_q = [p for p in pool if p["player_doc_id"] != anchor["player_doc_id"] and p["player_doc_id"] not in stalling_players]
        
        if len(other_q) < 3:
            continue
            
        check_in = anchor.get("check_in_time", now)
        max_wait_mins = (now - check_in) / 60.0
        dynamic_threshold = 0.20 + (max_wait_mins * 0.015)
        
        best_curr_score = -float('inf')
        best_curr_match = None
        has_fair_current = False
        
        for combo in itertools.combinations(other_q, 3):
            lobby = [anchor] + list(combo)
            spread = _lobby_spread(lobby)
            
            lobby_check_ins = [p.get("check_in_time", now) for p in lobby if "check_in_time" in p]
            lobby_max_wait = (now - min(lobby_check_ins)) / 60.0 if lobby_check_ins else 0.0
            
            relaxed_threshold = SPREAD_THRESHOLD + (lobby_max_wait * STARVATION_RELAX_PER_MIN)
            
            if spread <= relaxed_threshold:
                has_fair_current = True
                
            if spread <= 30.0:
                match_data = _score_lobby(lobby)
                if match_data:
                    wait_bonus = lobby_max_wait * 2.0 
                    adjusted_score = match_data["heuristic_score"] + wait_bonus
                    
                    if adjusted_score > best_curr_score:
                        best_curr_score = adjusted_score
                        best_curr_match = match_data
                    
        best_future_score = -float('inf')
        future_pool = other_q + in_progress_players
        if len(future_pool) >= 3:
            for combo in itertools.combinations(future_pool, 3):
                lobby = [anchor] + list(combo)
                spread = _lobby_spread(lobby)
                if spread <= SPREAD_THRESHOLD:
                    match_data = _score_lobby(lobby)
                    if match_data and match_data["heuristic_score"] > best_future_score:
                        best_future_score = match_data["heuristic_score"]
                        
        score_diff = (best_future_score - best_curr_score) / 100.0
        
        if score_diff > dynamic_threshold:
            stalling_players.add(anchor["player_doc_id"])
            continue
            
        if has_fair_current and best_curr_match:
            if best_curr_score > global_best_score:
                global_best_score = best_curr_score
                global_best_match = best_curr_match
            
    return global_best_match

def find_best_matches(state):
    """core logic to figure out who plays next based on trueskill spread, wait time, and available courts"""
    queue = state["queue"]
    in_progress_players = state["in_progress_players"]
    active_matches = state["active_matches"]
    num_courts = state.get("num_courts", 4)
    
    occupied_courts = {m["court_number"] for m in active_matches if m.get("court_number")}
    free_courts = [c for c in range(1, num_courts + 1) if c not in occupied_courts]
    
    standby_matches = [m for m in active_matches if m.get("status") == "standby"]
    
    matches_to_create = []
    available_pool = list(queue)
    total_players_in_building = len(in_progress_players) + len(queue)
    
    while free_courts and len(available_pool) >= 4:
        if standby_matches:
            standby = standby_matches.pop(0)
            matches_to_create.append({
                "type": "deploy_standby",
                "standby_id": standby["match_doc_id"],
                "court_number": free_courts.pop(0),
                "match_data": standby
            })
            continue

        match = _find_match_queue_traversal(available_pool, in_progress_players)
        
        if match:
            court_num = free_courts.pop(0)
            matches_to_create.append({
                "type": "new_match",
                "court_number": court_num,
                "match_data": match
            })
            matched_ids = {p["player_doc_id"] for p in match["team_a"] + match["team_b"]}
            available_pool = [p for p in available_pool if p["player_doc_id"] not in matched_ids]
            in_progress_players.extend(match["team_a"] + match["team_b"])
        else:
            match = _find_fairest_fallback(available_pool)
            if match:
                court_num = free_courts.pop(0)
                matches_to_create.append({
                    "type": "new_match",
                    "court_number": court_num,
                    "match_data": match
                })
                matched_ids = {p["player_doc_id"] for p in match["team_a"] + match["team_b"]}
                available_pool = [p for p in available_pool if p["player_doc_id"] not in matched_ids]
                in_progress_players.extend(match["team_a"] + match["team_b"])
            else:
                break
                
    if not free_courts and not standby_matches and len(available_pool) >= 4:
        match = _find_match_queue_traversal(available_pool, in_progress_players)
        if match:
            matches_to_create.append({
                "type": "standby_match",
                "match_data": match
            })

    return matches_to_create
