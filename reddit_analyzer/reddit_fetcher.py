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
from flask import Flask, jsonify
load_dotenv()  # Ensure .env is loaded before reading env vars

# --- OpenAI API-based antisemitism scoring ---
from openai_explanation import get_openai_antisemitism_explanation
from openai_score import get_openai_antisemitism_score

from reddit_instance import get_reddit_instance
from firebase_setup import init_firebase

app = Flask(__name__)

def fetch_posts(subreddit_name, query, limit=15):
    reddit = get_reddit_instance()
    subreddit = reddit.subreddit(subreddit_name)
    posts = []
    # Fetch newest posts and filter by buzzword
    for submission in subreddit.new(limit=limit):
        content = (submission.title or "") + " " + (submission.selftext or "")
        if query.lower() in content.lower():
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
    from datetime import datetime
    doc_id = user_info['author']
    # Add upload date to user_info
    user_info['upload_date'] = datetime.utcnow().isoformat()
    # Add upload date to each post in history
    for post in user_info.get('history', []):
        post['upload_date'] = datetime.utcnow().isoformat()
    doc_ref = db.collection('flagged_users').document(doc_id)
    doc_ref.set(user_info)
def post_exists_in_firestore(db, post_id):
    # Search all flagged_users for this post_id in their flagged_post_id field
    users_ref = db.collection('flagged_users')
    query = users_ref.where('flagged_post_id', '==', post_id).limit(1)
    results = query.stream()
    return any(True for _ in results)



# Flask endpoint to trigger the main logic
@app.route('/run', methods=['POST'])
def run_detector():
    try:
        print("[LOG] /run endpoint triggered.")
        reddit = get_reddit_instance()
        print("[LOG] Reddit instance initialized.")
        db = init_firebase()
        print("[LOG] Firebase initialized.")
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        two_months_ago = now - timedelta(days=60)
        grade_history_posts = False  # Set to True to enable history grading
        top_posts = []
        flagged_users = []
        for subreddit in SUBREDDITS:
            print(f"[LOG] Processing subreddit: {subreddit}")
            for buzzword in BUZZWORDS:
                print(f"[LOG] Buzzword: {buzzword}")
                posts = fetch_posts(subreddit, buzzword, limit=5)
                print(f"[LOG] Found {len(posts)} posts for buzzword '{buzzword}' in subreddit '{subreddit}'")
                for post in posts:
                    print(f"[LOG] Processing post ID: {post['post_id']}")
                    content = (post['title'] or "") + " " + (post['text'] or "")
                    if buzzword.lower() not in content.lower():
                        print(f"[LOG] Buzzword '{buzzword}' not in post content. Skipping.")
                        continue
                    if post_exists_in_firestore(db, post['post_id']):
                        print(f"[LOG] Post {post['post_id']} already exists in Firestore. Skipping.")
                        continue
                    text_for_model = (post['title'] or "") + "\n" + ((post['text'] or "")[:500])
                    hate_score = get_openai_antisemitism_score(text_for_model)
                    print(f"[LOG] Hate score for post {post['post_id']}: {hate_score}")
                    post_with_score = post.copy()
                    post_with_score['hate_score'] = hate_score
                    top_posts.append(post_with_score)
                    if hate_score >= 0.7:
                        author_name = post['author']
                        print(f"[LOG] Flagging user: {author_name}")
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
                            print(f"[LOG] Error fetching user history for {author_name}: {e}")
                            user_info['notes'] = [f"Could not fetch user history (private/new/no posts): {e}"]
                        flagged_users.append(user_info)
                        upload_flagged_user_to_firestore(db, user_info)
                        print(f"[LOG] Uploaded flagged user {author_name} to Firestore.")
        print("[LOG] Scan completed.")
        return jsonify({
            "top_posts": top_posts,
            "flagged_users": flagged_users,
            "status": "completed"
        })
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
