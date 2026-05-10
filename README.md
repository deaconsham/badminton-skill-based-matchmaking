# Badminton TrueSkill Matchmaking

A skill-based matchmaking system for doubles badminton clubs. It uses Microsoft's TrueSkill algorithm to keep games balanced and competitive.

## How it works
- **Balanced Teams:** The engine scans the queue and finds the best 2v2 combinations based on player skill (TrueSkill mu/sigma).
- **Teammate Requests:** Players can request specific partners, and the matchmaker will try to honor them if possible.
- **Auto-Queue:** After a match finishes and a winner is declared, players are automatically thrown back into the queue.
- **Standby System:** If all courts are full, it prepares standby matches so players can head to the court as soon as one opens up.

## Stack
- **Frontend:** React + Tailwind CSS + Framer Motion
- **Backend:** Python (Firebase Admin SDK + TrueSkill)
- **Database:** Google Firestore (for real-time updates)

## Setup

### 1. Firebase
You'll need a Firebase project with Firestore enabled. 
- Create a `players`, `queue`, `matches`, and `settings` collection.
- In `settings`, create a document named `engine` with a boolean field `enabled`.

### 2. Backend
The backend is a Python script that listens to Firestore events.
- Install dependencies: `pip install -r backend/requirements.txt`
- You need a service account key JSON from Firebase. Place it in the project root and name it `badminton-matchmaking-9b69f-firebase-adminsdk-fbsvc-cceede915a.json` (or update the path in `backend/db_client.py`).
- Run it: `python backend/main.py`

### 3. Frontend
- Go to the `frontend` folder.
- Create a `.env` file with your Firebase config:
  ```env
  VITE_FIREBASE_API_KEY=...
  VITE_FIREBASE_AUTH_DOMAIN=...
  VITE_FIREBASE_PROJECT_ID=...
  VITE_FIREBASE_STORAGE_BUCKET=...
  VITE_FIREBASE_MESSAGING_SENDER_ID=...
  VITE_FIREBASE_APP_ID=...
  ```
- Install and run:
  ```bash
  npm install
  npm run dev
  ```

## Development
The matchmaking logic lives in `backend/matchmaker.py`. It uses a heuristic score to balance match quality, skill gaps within teams, and player wait times.

## References
- **TrueSkill Website:** [TrueSkill™ Ranking System](https://www.microsoft.com/en-us/research/project/trueskill-ranking-system/) (Microsoft Research)
- **TrueSkill Paper:** [TrueSkill™: A Bayesian Skill Rating System](https://www.microsoft.com/en-us/research/wp-content/uploads/2006/01/TR-2006-80.pdf) (R. Herbrich, T. Graepel)