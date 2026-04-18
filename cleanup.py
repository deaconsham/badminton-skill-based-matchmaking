"""Clears all stale queue entries and matches from Firestore."""
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("badminton-matchmaking-9b69f-firebase-adminsdk-fbsvc-cceede915a.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

queue_docs = db.collection("queue").stream()
count_q = 0
for doc in queue_docs:
    doc.reference.delete()
    count_q += 1

match_docs = db.collection("matches").stream()
count_m = 0
for doc in match_docs:
    doc.reference.delete()
    count_m += 1

print("cleaned")
