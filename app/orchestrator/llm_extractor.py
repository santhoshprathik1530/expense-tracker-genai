import os
import json
from datetime import datetime
from typing import Any, Dict, Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def _client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    # Optional headers OpenRouter recommends (helps with routing/analytics)
    headers = {}
    site_url = os.getenv("OPENROUTER_SITE_URL")
    app_name = os.getenv("OPENROUTER_APP_NAME")
    if site_url:
        headers["HTTP-Referer"] = site_url
    if app_name:
        headers["X-Title"] = app_name

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers=headers if headers else None,
    )

SYSTEM_PROMPT = """
You are an expense extraction engine.

Return ONLY valid JSON (no markdown, no commentary) with exactly these keys:
{
  "amount": number,
  "currency": string,
  "category": string,
  "merchant": string or null,
  "expense_date": "YYYY-MM-DD"
}

Rules:
- If message describes a split expense, assume the amount mentioned is the user's share unless explicitly stated otherwise.
- If date missing, use today's date.
- If currency missing, assume USD.
- If not an expense, return null for amount.
"""

def llm_extract_expense(text: str) -> Optional[Dict[str, Any]]:
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")
    today = datetime.now().strftime("%Y-%m-%d")

    client = _client()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + f"\nToday's date is {today}."},
            {"role": "user", "content": text},
        ],
        temperature=0,
        # We do NOT need reasoning for extraction; keep it simple + reliable.
        # extra_body={"reasoning": {"enabled": True}},
    )

    content = (resp.choices[0].message.content or "").strip()

    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError:
        # If model returns non-JSON, treat as failure (we'll fall back to rule parser)
        return None
   