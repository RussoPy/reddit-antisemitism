BUZZWORDS = [
    "jews", "zionist", "holocaust", "antisemitic", "israel",
    "rothschild", "globalist", "new world order", "protocols of zion",
    "Jewish conspiracy", "Jewish control", "Jewish media", "Jewish power",
    "zionist crimes", "zionazi", "anti-semitism", "anti semitism", "kike",
    "zionist shill", "ashkenazi", "control the media", "zionist media", "zionist apartheid",
    "zionist lies", "zionist war", "zionist takeover", "zionist terrorism", "zionist propaganda", "zionist control of banks"
]

SUBREDDITS = [
    "worldnews", "politics", "conspiracy", "unpopularopinion", "worldpolitics", "DebateReligion"
]
import praw
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import numpy as np
import os
import requests
import time
from dotenv import load_dotenv
load_dotenv()  # Ensure .env is loaded before reading env vars

# --- OpenAI API-based antisemitism scoring ---
from openai_explanation import get_openai_antisemitism_explanation
from openai_score import get_openai_antisemitism_score


from reddit_instance import get_reddit_instance
from firebase_setup import init_firebase



def fetch_posts(subreddit_name, query, limit=10):
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
    doc_id = user_info['author']
    doc_ref = db.collection('flagged_users').document(doc_id)
    doc_ref.set(user_info)


if __name__ == "__main__":
    # Load environment variables from .env file if present
    load_dotenv()
    try:
        reddit = get_reddit_instance()
        print("Authenticated as:", reddit.user.me())
        print()
        top_posts = []  # List of dicts: each with post info and hate_score
        flagged_users = []  # List to store flagged user histories
        db = init_firebase()
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        two_months_ago = now - timedelta(days=60)
        for subreddit in SUBREDDITS:
            for buzzword in BUZZWORDS:
                print(f"Subreddit: {subreddit} | Buzzword: '{buzzword}'")
                posts = fetch_posts(subreddit, buzzword, limit=5)
                for post in posts:
                    # Only process posts that actually contain the buzzword in title or text
                    content = (post['title'] or "") + " " + (post['text'] or "")
                    if buzzword.lower() not in content.lower():
                        continue
                    text_for_model = (post['title'] or "") + "\n" + ((post['text'] or "")[:500])
                    hate_score = get_openai_antisemitism_score(text_for_model)
                    post_with_score = post.copy()
                    post_with_score['hate_score'] = hate_score
                    top_posts.append(post_with_score)
                    print(f"- Title: {post['title']}")
                    print(f"  Author: {post['author']}")
                    if post['text']:
                        print(f"  Text: {post['text'][:100]}{'...' if len(post['text']) > 100 else ''}")
                    else:
                        print(f"  Link: {post['url']}")
                    print(f"  Hate Score: {hate_score:.2f}")
                    print(f"  Post ID: {post['post_id']}")
                    print(f"  Created UTC: {post['created_utc']}")
                    print(f"  Reddit Link: {post['permalink']}")
                    # If hate_score > 0.8, fetch user post history and explanation
                    if hate_score > 0.8:
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
                            'explanation': explanation
                        }
                        try:
                            redditor = reddit.redditor(author_name)
                            # Fetch up to 100 recent submissions
                            submissions = []
                            for submission in redditor.submissions.new(limit=100):
                                # Only include posts from last 2 months
                                post_time = datetime.fromtimestamp(submission.created_utc, timezone.utc)
                                if post_time >= two_months_ago:
                                    submissions.append({
                                        'id': submission.id,
                                        'title': submission.title,
                                        'text': submission.selftext,
                                        'created_utc': submission.created_utc,
                                        'url': submission.url,
                                        'permalink': f"https://reddit.com{submission.permalink}",
                                        'subreddit': str(submission.subreddit)
                                    })
                            user_info['history'] = submissions
                            if len(submissions) < 3:
                                user_info['note'] = f"User has less than 3 posts in last 2 months."
                            else:
                                user_info['note'] = f"User has {len(submissions)} posts in last 2 months."
                        except Exception as e:
                            user_info['note'] = f"Could not fetch user history (private/new/no posts): {e}"
                        flagged_users.append(user_info)
                        upload_flagged_user_to_firestore(db, user_info)
                        print(f"  [FLAGGED] User post history extracted. Posts in last 2 months: {len(user_info['history'])}")
                        print(f"  Explanation: {explanation}")
                        if user_info['note']:
                            print(f"  Note: {user_info['note']}")
                    print()
                if not posts:
                    print("  No posts found.\n")
        # Sort all posts by hate_score descending and print top 5
        if top_posts:
            top_posts_sorted = sorted(top_posts, key=lambda x: x['hate_score'], reverse=True)[:5]
            print("\n=== Top 5 Most Hateful Posts Detected ===")
            for i, post in enumerate(top_posts_sorted, 1):
                print(f"#{i} | Score: {post['hate_score']:.2f}")
                print(f"Title: {post['title']}")
                print(f"Reddit Link: {post['permalink']}")
                print()
        else:
            print("\nNo posts found with a hate score.")
        # Print flagged user histories summary
        if flagged_users:
            print("\n=== Flagged User Histories ===")
            for user in flagged_users:
                print(f"User: {user['author']}")
                print(f"Flagged Post: {user['flagged_post_title']}")
                print(f"Hate Score: {user['hate_score']:.2f}")
                print(f"Explanation: {user['explanation']}")
                print(f"Note: {user['note']}")
                print(f"Posts in last 2 months: {len(user['history'])}")
                for hist in user['history']:
                    print(f"  - [{hist['created_utc']}] {hist['title']} | {hist['permalink']}")
                print()
    except Exception as e:
        print("Authentication or fetch failed:", e)
