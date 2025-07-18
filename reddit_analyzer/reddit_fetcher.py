"""
reddit_fetcher.py
-----------------
Main script for detecting antisemitic Reddit posts, scoring them with OpenAI, and uploading flagged users and their post histories to Firebase Firestore.

Functions:
- fetch_posts: Fetch posts from a subreddit matching a buzzword.
- upload_flagged_user_to_firestore: Upload flagged user and post history to Firestore.
- post_exists_in_firestore: Check if a post already exists in Firestore.

Entry point:
Iterates through subreddits and buzzwords, scores posts, and uploads flagged users.
"""
BUZZWORDS = [
    "jews", "zionist", "holocaust", "antisemitic", "israel",
    "rothschild", "protocols of zion",
    "Jewish conspiracy", "Jewish control", "Jewish media", "Jewish power",
    "zionist crimes", "zionazi", "anti-semitism", "anti semitism", "kike", "hitler",
    "jewish supremacy",
    "zionist shill", "ashkenazi", "control the media", "zionist media", "zionist apartheid",
    "zionist lies", "zionist war", "zionist takeover", "zionist terrorism", "zionist propaganda", "zionist control of banks"
]

SUBREDDITS = [
    "worldnews", "politics", "conspiracy", "unpopularopinion", "worldpolitics", "DebateReligion"
]
import praw

import os
from dotenv import load_dotenv
load_dotenv()  # Ensure .env is loaded before reading env vars

# --- OpenAI API-based antisemitism scoring ---
from openai_explanation import get_openai_antisemitism_explanation
from openai_score import get_openai_antisemitism_score

from reddit_instance import get_reddit_instance
from firebase_setup import init_firebase


def fetch_posts(subreddit_name, query, limit=15):
    """
    Fetch posts from a subreddit matching a buzzword.
    Args:
        subreddit_name (str): Name of the subreddit.
        query (str): Buzzword to search for.
        limit (int): Number of posts to fetch.
    Returns:
        list: List of post dictionaries.
    """
    reddit = get_reddit_instance()
    subreddit = reddit.subreddit(subreddit_name)
    posts = []
    for submission in subreddit.search(query, limit=limit):
        posts.append({
            "post_id": submission.id,
            "author": str(submission.author),
            "title": submission.title,
            "text": submission.selftext,
            "url": submission.url,
            "permalink": f"https://reddit.com{submission.permalink}",
            "subreddit": subreddit_name,
            "created_utc": submission.created_utc
        })
    return posts

def upload_flagged_user_to_firestore(db, user_info):
    """
    Upload a flagged user and their post history to Firestore.
    Adds upload date to user and each post in history.
    Args:
        db: Firestore database client.
        user_info (dict): User info and post history.
    """
    from datetime import datetime
    doc_id = user_info['author']
    user_info['upload_date'] = datetime.utcnow().isoformat()
    for post in user_info.get('history', []):
        post['upload_date'] = datetime.utcnow().isoformat()
    doc_ref = db.collection('flagged_users').document(doc_id)
    doc_ref.set(user_info)
def post_exists_in_firestore(db, post_id):
    """
    Check if a post already exists in Firestore.
    Args:
        db: Firestore database client.
        post_id (str): Reddit post ID.
    Returns:
        bool: True if post exists, False otherwise.
    """
    users_ref = db.collection('flagged_users')
    query = users_ref.where('flagged_post_id', '==', post_id).limit(1)
    results = query.stream()
    return any(True for _ in results)




# Main script logic for local execution

# Main script logic for local execution
if __name__ == "__main__":
    print("Starting Reddit antisemitism scan...")
    reddit = get_reddit_instance()
    print("Reddit instance initialized.")
    db = init_firebase()
    print("Firebase initialized.")
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    two_months_ago = now - timedelta(days=60)
    grade_history_posts = False  # Set to True to enable history grading
    top_posts = []
    flagged_users = []
    for subreddit in SUBREDDITS:
        print()
        print(f"=== Subreddit: {subreddit} ===")
        for buzzword in BUZZWORDS:
            print()
            print(f"  Buzzword: '{buzzword}'")
            posts = fetch_posts(subreddit, buzzword, limit=5)
            print(f"    Found {len(posts)} posts for buzzword '{buzzword}'")
            for post in posts:
                print()
                print(f"    Title: {post['title']}")
                print(f"    Post ID: {post['post_id']}")
                content = (post['title'] or "") + " " + (post['text'] or "")
                if buzzword.lower() not in content.lower():
                    print(f"      [SKIP] Buzzword not in post content.")
                    continue
                if post_exists_in_firestore(db, post['post_id']):
                    print(f"      [SKIP] Post already exists in Firestore.")
                    continue
                text_for_model = (post['title'] or "") + "\n" + ((post['text'] or "")[:500])
                hate_score = get_openai_antisemitism_score(text_for_model)
                print(f"      Hate Score: {hate_score}")
                post_with_score = post.copy()
                post_with_score['hate_score'] = hate_score
                top_posts.append(post_with_score)
                if hate_score >= 0.7:
                    author_name = post['author']
                    explanation = get_openai_antisemitism_explanation(text_for_model)
                    user_info = {
                        'author': author_name,
                        'flagged_post_id': post['post_id'],
                        'flagged_post_permalink': post['permalink'],
                        'flagged_post_title': post['title'],
                        'flagged_post_text': post['text'],
                        'hate_score': hate_score,
                        'history': [],
                        'note': '',
                        'explanation': explanation,
                        'upload_date': datetime.now(timezone.utc).isoformat()  # Added upload time
                    }
                    try:
                        redditor = reddit.redditor(author_name)
                        submissions = []
                        flagged_history_count = 0
                        for submission in redditor.submissions.new(limit=20):
                            post_time = datetime.fromtimestamp(submission.created_utc, timezone.utc)
                            if post_time >= two_months_ago:
                                hist_post = {
                                    'id': submission.id,
                                    'title': submission.title,
                                    'text': submission.selftext,
                                    'created_utc': submission.created_utc,
                                    'url': submission.url,
                                    'permalink': f"https://reddit.com{submission.permalink}",
                                    'subreddit': str(submission.subreddit)
                                }
                                if grade_history_posts and not post_exists_in_firestore(db, submission.id):
                                    hist_text = (submission.title or "") + "\n" + ((submission.selftext or "")[:500])
                                    hist_score = get_openai_antisemitism_score(hist_text)
                                    hist_post['hate_score'] = hist_score
                                    if hist_score >= 0.7:
                                        flagged_history_count += 1
                                submissions.append(hist_post)
                        user_info['history'] = submissions
                        notes = []
                        if len(submissions) < 3:
                            notes.append("User has less than 3 posts in last 2 months.")
                        else:
                            notes.append(f"User has {len(submissions)} posts in last 2 months.")
                        if grade_history_posts and flagged_history_count > 0:
                            original_score = user_info['hate_score']
                            user_info['hate_score'] = min(user_info['hate_score'] + 0.1, 1.0)
                            notes.append(f"Original score was {original_score:.2f}, increased to {user_info['hate_score']:.2f} due to {flagged_history_count} flagged history posts.")
                        user_info['notes'] = notes
                    except Exception as e:
                        print(f"      Error fetching user history: {e}")
                        user_info['notes'] = [f"Could not fetch user history (private/new/no posts): {e}"]
                    flagged_users.append(user_info)
                    upload_flagged_user_to_firestore(db, user_info)
                    print(f"- Title: {user_info['flagged_post_title']}")
                    print(f"  Author: {user_info['author']}")
                    if user_info['flagged_post_text']:
                        print(f"  Text: {user_info['flagged_post_text'][:100]}{'...' if len(user_info['flagged_post_text']) > 100 else ''}")
                    else:
                        print(f"  Link: {user_info['flagged_post_permalink']}")
                    print(f"  Hate Score: {user_info['hate_score']:.2f}")
                    print(f"  Post ID: {user_info['flagged_post_id']}")
                    print(f"  Time: {user_info['upload_date']}")
                    print(f"  Reddit Link: {user_info['flagged_post_permalink']}")
                    print(f"  Reason: {user_info['explanation']}")
                    if isinstance(user_info['notes'], list):
                        for note in user_info['notes']:
                            print(f"  Note: {note}")
                    elif user_info.get('note'):
                        print(f"  Note: {user_info['note']}")
                    print()
    print("\nScan completed.")

