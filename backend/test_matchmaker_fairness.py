import unittest
from backend.matchmaker import _best_split, _score_lobby

class TestMatchmakerFairness(unittest.TestCase):
    def test_minimize_disparity(self):
        # Case: Two high skill players, two low skill players.
        # Player 1: 30 mu
        # Player 2: 30 mu
        # Player 3: 10 mu
        # Player 4: 10 mu
        
        lobby = [
            {"player_doc_id": "p1", "mu": 30.0, "sigma": 2.0},
            {"player_doc_id": "p2", "mu": 30.0, "sigma": 2.0},
            {"player_doc_id": "p3", "mu": 10.0, "sigma": 2.0},
            {"player_doc_id": "p4", "mu": 10.0, "sigma": 2.0},
        ]
        
        # Best split should be (p1, p3) vs (p2, p4) or (p1, p4) vs (p2, p3)
        # to ensure both teams have equal total skill.
        # Disparity in (p1, p2) vs (p3, p4) would be:
        # Team A (30, 30) -> spread 0
        # Team B (10, 10) -> spread 0
        # Total disparity 0. BUT Quality would be very low because 60 vs 20.
        
        # Team A (30, 10) -> spread 20
        # Team B (30, 10) -> spread 20
        # Total disparity 40. Quality would be 100% (1.0).
        
        # Current formula: Score = (quality * 100) - (disparity * 2)
        # Option 1 (Unbalanced): (approx 0 * 100) - (0 * 2) = 0
        # Option 2 (Balanced but high disparity): (1.0 * 100) - (40 * 2) = 100 - 80 = 20
        # So it would pick Option 2.
        
        best_a, best_b, quality, delta, disparity = _best_split(lobby)
        
        # We want to make sure it picks the balanced teams
        self.assertAlmostEqual(delta, 0.0)
        
    def test_find_best_match_in_pool(self):
        from backend.matchmaker import _find_match_queue_traversal
        import time
        now = time.time()
        
        # p1 is at the front but has no "perfect" match.
        # p2, p3, p4, p5 have a perfect 0-disparity 100% quality match.
        pool = [
            {"player_doc_id": "p1", "mu": 50.0, "sigma": 2.0, "check_in_time": now},
            {"player_doc_id": "p2", "mu": 20.0, "sigma": 2.0, "check_in_time": now},
            {"player_doc_id": "p3", "mu": 20.0, "sigma": 2.0, "check_in_time": now},
            {"player_doc_id": "p4", "mu": 20.0, "sigma": 2.0, "check_in_time": now},
            {"player_doc_id": "p5", "mu": 20.0, "sigma": 2.0, "check_in_time": now},
        ]
        
        # Current logic: 
        # anchor = p1
        # combos with p1: (p1, p2, p3, p4) -> spread 30. (p1, p2, p3, p5) -> spread 30. etc.
        # spread 30 might be within "relaxed_threshold" if wait time is long.
        # If p1's match is "fair", it returns p1's match.
        
        # We want to see if it would rather pick (p2, p3, p4, p5) which is much better.
        
        match = _find_match_queue_traversal(pool, [])
        if match:
            player_ids = {p["player_doc_id"] for p in match["team_a"] + match["team_b"]}
            print(f"Match found with players: {player_ids}, score: {match['heuristic_score']}")
            self.assertNotIn("p1", player_ids, "Should have skipped p1 to find a much better match for others")
        else:
            self.fail("No match found")

if __name__ == "__main__":
    unittest.main()
