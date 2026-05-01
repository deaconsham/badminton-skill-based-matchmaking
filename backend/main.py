import threading
import time
import sys
import traceback
from db_client import fetch_current_state, record_match, set_standby_active, process_finished_matches, db
from matchmaker import find_best_matches

DEBOUNCE_SECONDS = 5.0

class Debouncer:
    def __init__(self, delay, callback):
        self.delay = delay
        self.callback = callback
        self.timer = None
        self._lock = threading.Lock()

    def trigger(self):
        with self._lock:
            if self.timer is not None:
                self.timer.cancel()
            self.timer = threading.Timer(self.delay, self.callback)
            self.timer.start()

def run_matchmaking_cycle():
    """the main loop that grabs the state, crunches the numbers, and pushes new matches to the database"""
    try:
        print("running matchmaking cycle")
        process_finished_matches()
        
        state = fetch_current_state()
        matches_to_create = find_best_matches(state)
        
        for action in matches_to_create:
            if action["type"] == "deploy_standby":
                set_standby_active(action["standby_id"], action["court_number"], action["match_data"])
                print(f"standby match {action['standby_id']} deployed to court {action['court_number']}")
            elif action["type"] == "new_match":
                mid = record_match(action["match_data"], action["court_number"], status="in_progress")
                spread = action["match_data"].get("lobby_spread", 0.0)
                print(f"created new match on court {action['court_number']} (spread: {spread:.1f}). id: {mid}")
            elif action["type"] == "standby_match":
                mid = record_match(action["match_data"], None, status="standby")
                spread = action["match_data"].get("lobby_spread", 0.0)
                print(f"created standby match (spread: {spread:.1f}). id: {mid}")
                
        print("cycle complete")
                
    except Exception as e:
        print(f"error in matchmaking cycle: {e}")
        traceback.print_exc()

def main():
    """sets up the firebase listeners and the debouncer so we don't spam the database"""
    print("initializing event-driven matchmaking engine")
    
    debouncer = Debouncer(DEBOUNCE_SECONDS, run_matchmaking_cycle)
    
    def on_snapshot_callback(col_snapshot, changes, read_time):
        print(f"received snapshot event ({len(changes)} changes). debouncing")
        debouncer.trigger()

    def on_settings_snapshot(doc_snapshot, changes, read_time):
        print("received settings snapshot event. debouncing")
        debouncer.trigger()

    queue_watch = db.collection("queue").on_snapshot(on_snapshot_callback)
    matches_watch = db.collection("matches").on_snapshot(on_snapshot_callback)
    settings_watch = db.collection("settings").document("engine").on_snapshot(on_settings_snapshot)
    
    print("engine is running")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("shutting down listeners...")
        queue_watch.unsubscribe()
        matches_watch.unsubscribe()
        settings_watch.unsubscribe()
        sys.exit(0)

if __name__ == "__main__":
    main()
