import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

SYSTEM_PROMPT = """
You are an intent classifier for a personal expense tracking bot.

Classify the message into ONE of:
- log
- query
- unknown

Return only one word.
"""

def classify_intent(text: str) -> str:
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0,
        )

        intent = response.choices[0].message.content.strip().lower()

        if intent in ["log", "query"]:
            return intent

        return "unknown"

    except Exception as e:
        print("Intent classifier failed:", e)
        return "unknown"
