import os
import requests
from dotenv import load_dotenv
import re

def get_openai_antisemitism_score(text, api_key=None, model="gpt-4"):
    """
    Uses OpenAI API to rate antisemitism in the text from 0 (not antisemitic) to 1 (extremely antisemitic).
    Only considers antisemitism, not general hate.
    """
    if not text or not text.strip():
        return 0.0
    if api_key is None:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not set. Set OPENAI_API_KEY environment variable.")
    prompt = (
    "You are an expert in hate speech detection. "
    "Your task is to analyze the following Reddit post for antisemitic content. "
    "If the post contains antisemitic language, conspiracy theories, or harmful stereotypes about Jewish people, score it accordingly. "
    "If the post is simply quoting a headline, news, or another person (using quotation marks), and does not endorse or support the content, do not flag it as antisemitic. "
    "Treat both double quotes (\"\") and single quotes (') as indicators of quoted material. If the post contains text within either type of quotes, assume it may be a quotation and do not flag unless there is clear endorsement or agreement. "
    "Return a score from 0.0 (not antisemitic) to 1.0 (extremely antisemitic), return only a number. "
    f"\n\nReddit post:\n{text}\n"
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
