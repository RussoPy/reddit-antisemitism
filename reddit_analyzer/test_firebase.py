from firebase_setup import init_firebase

def main():
    db = init_firebase()
    # Test: Write a simple document
    doc_ref = db.collection("test_collection").document("test_doc")
    doc_ref.set({"message": "Hello from Reddit Extract!"})
    print("Test document written to Firestore.")

if __name__ == "__main__":
    main()
