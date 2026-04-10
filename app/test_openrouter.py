import os
from dotenv import load_dotenv
from openai import OpenAI

# Load .env file
load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise ValueError("OPENROUTER_API_KEY not found in .env")

print("✅ API Key Loaded")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

print("🚀 Sending test request to OpenRouter...")

try:
    response = client.chat.completions.create(
        model="google/gemma-3-27b-it:free",  # You can change model later
        messages=[
            {"role": "user", "content": "Respond with only the word OK"}
        ],
        temperature=0,
    )

    print("✅ API Call Successful")
    print("Response:", response.choices[0].message.content)

except Exception as e:
    print("❌ API Call Failed")
    print("Error:", e)
