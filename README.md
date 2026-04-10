# Expense Tracker GenAI

Telegram expense tracker built with FastAPI, OpenRouter, LangGraph, and SQLite.

## What It Does

- Logs expenses from natural language
- Summarizes total spend over dates
- Breaks spend down by category, sub-category, or date
- Updates and deletes existing expenses through search-first workflows
- Handles Telegram webhook requests end to end

## Stack

- FastAPI
- LangGraph
- OpenRouter with `openai/gpt-4o-mini`
- SQLite
- Telegram Bot API

## Local Setup

1. Create a `.env` file with:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENROUTER_API_KEY`
   - `OPENROUTER_MODEL`
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
uvicorn app.main:app --reload
```

## Notes

- SQLite storage is created automatically at `app/db/expense_tracker.db`
- Logs are written to `logs/app.log` and `logs/llm.log`
- Telegram should point to `/telegram/webhook`
