from fastapi import APIRouter, Request
import os
import requests
from datetime import datetime, date

from app.orchestrator.llm_extractor import llm_extract_expense
from app.orchestrator.expense_parser import parse_expense_message
from app.orchestrator.expense_schema import ExtractedExpense
from app.db.expense_repository import add_expense_db, get_expenses_db
from app.orchestrator.intent_classifier import classify_intent


router = APIRouter()

TELEGRAM_API = "https://api.telegram.org"


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    print("Telegram update:", update)

    if "message" not in update:
        return {"ok": True}

    chat_id = update["message"]["chat"]["id"]
    text = update["message"].get("text", "")

    intent = classify_intent(text)
    print("Detected intent:", intent)

    # ============================
    # QUERY HANDLING
    # ============================
    if intent == "query":
        rows = get_expenses_db(chat_id)
        lower_text = text.lower()

        # Filter: today
        if "today" in lower_text:
            rows = [
                r for r in rows
                if r[4] == date.today()
            ]

        # Filter: this month
        elif "month" in lower_text:
            today = date.today()
            rows = [
                r for r in rows
                if r[4].month == today.month
                and r[4].year == today.year
            ]

        if not rows:
            reply_text = "No expenses found for that period."
        else:
            total = sum(float(r[0]) for r in rows)

            breakdown = "\n".join(
                f"{r[1]} {float(r[0]):.2f} - {r[2]} ({r[4]})"
                for r in rows
            )

            reply_text = (
                f"📊 Your Expenses:\n\n"
                f"{breakdown}\n\n"
                f"Total: {total:.2f}"
            )

    # ============================
    # LOGGING HANDLING (OpenRouter + Fallback)
    # ============================
    elif intent == "log":

        # 🔥 1️⃣ Try LLM extraction first
        data = llm_extract_expense(text)

        if data and data.get("amount") is not None:
            try:
                parsed = ExtractedExpense(
                    amount=float(data["amount"]),
                    currency=data.get("currency") or "USD",
                    category=data.get("category") or "misc",
                    merchant=data.get("merchant"),
                    expense_date=datetime.strptime(
                        data["expense_date"], "%Y-%m-%d"
                    ).date(),
                    confidence=0.95
                )

                add_expense_db(chat_id, parsed)

                reply_text = (
                    f"✅ Logged {parsed.currency} {parsed.amount:.2f}\n"
                    f"Category: {parsed.category}\n"
                    f"Merchant: {parsed.merchant or '—'}\n"
                    f"Date: {parsed.expense_date.isoformat()}"
                )

            except Exception as e:
                print("LLM parsing error:", e)
                reply_text = "Something went wrong while processing the expense."

        # 🔁 2️⃣ Fallback to rule-based parser
        else:
            print("LLM failed, using fallback parser")

            parsed = parse_expense_message(text, base_dt=datetime.now())

            if parsed:
                add_expense_db(chat_id, parsed)

                reply_text = (
                    f"✅ Logged {parsed.currency} {parsed.amount:.2f}\n"
                    f"Category: {parsed.category}\n"
                    f"Merchant: {parsed.merchant or '—'}\n"
                    f"Date: {parsed.expense_date.isoformat()}\n"
                    f"(Fallback parser)"
                )
            else:
                reply_text = (
                    "I couldn't extract the expense.\n"
                    "Try: 'I spent $6 at Starbucks yesterday'"
                )

    # ============================
    # UNKNOWN HANDLING
    # ============================
    else:
        reply_text = (
            "I can help you track expenses.\n\n"
            "Try:\n"
            "• I spent $6 at Starbucks\n"
            "• Track today\n"
            "• Track this month"
        )

    # ============================
    # SEND RESPONSE TO TELEGRAM
    # ============================
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    response = requests.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": reply_text
        }
    )

    print("Telegram sendMessage status:", response.status_code)
    print("Telegram sendMessage response:", response.text)

    return {"ok": True}
