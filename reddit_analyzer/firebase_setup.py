import firebase_admin
from firebase_admin import credentials, firestore
import os

# Use FIREBASE_CREDENTIALS env variable for service account path
import os
SERVICE_ACCOUNT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "firebase_service_account.json")

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
    return firestore.client()
