import os
import requests
from dotenv import load_dotenv

def get_openai_antisemitism_explanation(text, api_key=None, model="gpt-3.5-turbo"):
    """
    Uses OpenAI API to explain why the post is flagged as antisemitic.
    Returns a short explanation string.
    """
    if not text or not text.strip():
        return "No explanation available."
    if api_key is None:
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
