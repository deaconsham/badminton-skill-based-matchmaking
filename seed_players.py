import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("badminton-matchmaking-9b69f-firebase-adminsdk-fbsvc-cceede915a.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

PLAYERS = [
    {"name": "Chen Long",          "colour_tier": "Red",    "mu": 51.4, "sigma": 0.9, "games_played": 0},
    {"name": "Anthony Ginting",    "colour_tier": "Green",  "mu": 45.2, "sigma": 1.5, "games_played": 0},
    {"name": "Tai Tzu-ying",       "colour_tier": "Orange", "mu": 42.8, "sigma": 1.1, "games_played": 0},
    {"name": "Jonatan Christie",   "colour_tier": "Yellow", "mu": 38.7, "sigma": 2.3, "games_played": 0},
    {"name": "Chen Jin",           "colour_tier": "Orange", "mu": 41.5, "sigma": 5.0, "games_played": 0},
    {"name": "Carolina Marin",     "colour_tier": "Yellow", "mu": 37.9, "sigma": 4.8, "games_played": 0},
    {"name": "Akane Yamaguchi",    "colour_tier": "Yellow", "mu": 34.2, "sigma": 5.5, "games_played": 0},
    {"name": "Lin Shidong",        "colour_tier": "Green",  "mu": 43.1, "sigma": 5.0, "games_played": 0},
    {"name": "Bao Chunlai",        "colour_tier": "Red",    "mu": 49.3, "sigma": 2.2, "games_played": 0},
    {"name": "Zheng Siwei",        "colour_tier": "Yellow", "mu": 41.2, "sigma": 3.1, "games_played": 0},
    {"name": "Huang Yaqiong",      "colour_tier": "Green",  "mu": 40.5, "sigma": 3.0, "games_played": 0},
    {"name": "Yuta Watanabe",      "colour_tier": "Orange", "mu": 44.1, "sigma": 4.1, "games_played": 0},
    {"name": "Arisa Higashino",    "colour_tier": "Orange", "mu": 43.8, "sigma": 4.2, "games_played": 0},
    {"name": "Dechapol P.",        "colour_tier": "Red",    "mu": 48.0, "sigma": 1.8, "games_played": 0},
    {"name": "Sapsiree T.",        "colour_tier": "Red",    "mu": 47.9, "sigma": 1.9, "games_played": 0},
    {"name": "Seo Seung-jae",      "colour_tier": "Yellow", "mu": 39.5, "sigma": 3.5, "games_played": 0},
    {"name": "Chae Yoo-jung",      "colour_tier": "Yellow", "mu": 39.1, "sigma": 3.6, "games_played": 0},
    {"name": "Kim So-yeong",       "colour_tier": "Green",  "mu": 42.0, "sigma": 2.8, "games_played": 0},
    {"name": "Kong Hee-yong",      "colour_tier": "Green",  "mu": 41.8, "sigma": 2.9, "games_played": 0},
    {"name": "Pusarla V. Sindhu",  "colour_tier": "Orange", "mu": 40.2, "sigma": 3.2, "games_played": 0},
    {"name": "He Bingjiao",        "colour_tier": "Yellow", "mu": 38.4, "sigma": 4.0, "games_played": 0},
]

# Delete existing players first (including the test player)
print("Clearing existing players...")
existing = db.collection("players").stream()
batch = db.batch()
count = 0
for doc in existing:
    batch.delete(doc.reference)
    count += 1
if count > 0:
    batch.commit()
    print(f"  Deleted {count} existing players")

# Add all players
print(f"Adding {len(PLAYERS)} players...")
batch = db.batch()
for p in PLAYERS:
    ref = db.collection("players").document()
    batch.set(ref, p)

batch.commit()

# Verify
verify = list(db.collection("players").stream())
print(f"Done! {len(verify)} players in database:")
for doc in verify:
    d = doc.to_dict()
    rating = max(0, min(9999, round(d["mu"] * 50)))
    print(f"  {d['name']:20s}  {d['colour_tier']:6s}  mu={d['mu']:.1f}  σ={d['sigma']:.1f}  rating={rating}")
