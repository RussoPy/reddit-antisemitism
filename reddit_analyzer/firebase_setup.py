import firebase_admin
from firebase_admin import credentials, firestore
import os

# Use FIREBASE_CREDENTIALS env variable for service account path
SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_CREDENTIALS")

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
    return firestore.client()
