
# Reddit Antisemitism Detector

Detects antisemitic Reddit posts using OpenAI and saves flagged users/posts to Firebase.

## How to Start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Add your API keys and credentials to a `.env` file (see `requirements.txt` for needed services).
3. Run:
   ```bash
   python reddit_fetcher.py
   ```

## What It Does
- Scans Reddit for antisemitic content
- Scores posts with OpenAI
- Saves flagged users and their post history to Firestore

Deployable to Render or similar cloud platforms.
