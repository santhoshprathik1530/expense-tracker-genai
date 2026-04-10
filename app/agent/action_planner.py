import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

SYSTEM_PROMPT = """
You are an AI agent for a personal expense tracker.

Convert user request into structured JSON actions.

Return ONLY JSON in this format:

{
  "actions": [
    {
      "tool": "create_expense" | "update_expense" | "delete_expense" | "query_expense",
      "arguments": { ... }
    }
  ]
}

Rules:
- If multiple operations are requested, return multiple actions.
- For update/delete, include filters (merchant, date, category, etc.)
- Do not explain.
- Only JSON.
"""

def plan_actions(user_text: str):
    response = client.chat.completions.create(
        model=os.getenv("OPENROUTER_MODEL"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        temperature=0,
    )

    content = response.choices[0].message.content.strip()
    return json.loads(content)
