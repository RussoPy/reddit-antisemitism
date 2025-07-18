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
def get_openai_antisemitism_explanation(text, api_key=None, model="gpt-3.5-turbo"):
    """
    Uses OpenAI API to explain why the post is flagged as antisemitic.
    Returns a short explanation string.
    """
    if not text or not text.strip():
        return "No explanation available."
    if api_key is None:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not set. Set OPENAI_API_KEY environment variable.")
    prompt = (
        "Explain in 1 very short sentence why the following Reddit post is antisemitic and flagged. "
        "Focus on antisemitic language, stereotypes, or hate speech.\nPost: " + text.strip()[:500]
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an expert in antisemitism detection."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 100,
        "temperature": 0.0
    }
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        answer = result["choices"][0]["message"]["content"].strip()
        return answer
    except Exception as e:
        print(f"[DEBUG] OpenAI explanation request exception: {e}")
        return "Explanation not available due to error."
def get_openai_antisemitism_score(text, api_key=None, model="gpt-3.5-turbo"):
    """
    Uses OpenAI API to rate antisemitism in the text from 0 (not antisemitic) to 1 (extremely antisemitic).
    Only considers antisemitism, not general hate.
    """
    if not text or not text.strip():
        return 0.0
    if api_key is None:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not set. Set OPENAI_API_KEY environment variable.")
    prompt = (
        "Rate the following Reddit post for antisemitism on a scale from 0 (not antisemitic) to 1 (extremely antisemitic and super high). "
        "Only consider antisemitism, not general hate. "
        "Respond with only a number between 0 and 1.\n\nPost: " + text.strip()[:500]
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an expert in antisemitism detection."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 10,
        "temperature": 0.0
    }
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        answer = result["choices"][0]["message"]["content"].strip()
        import re
        match = re.search(r"(?<!\d)(0(\.\d+)?|1(\.0+)?)(?!\d)", answer)
        if match:
            score = float(match.group(0))
            if score < 0: score = 0.0
            if score > 1: score = 1.0
            return score
        else:
            print(f"[DEBUG] Could not parse OpenAI response: '{answer}'")
            return 0.0
    except Exception as e:
        print(f"[DEBUG] OpenAI API request exception: {e}")
        return 0.0


# Fill in your credentials here
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")


def get_reddit_instance():
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD
    )
    return reddit


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


if __name__ == "__main__":
    # Load environment variables from .env file if present
    load_dotenv()
    try:
        reddit = get_reddit_instance()
        print("Authenticated as:", reddit.user.me())
        print()
        top_posts = []  # List of dicts: each with post info and hate_score
        flagged_users = []  # List to store flagged user histories
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
