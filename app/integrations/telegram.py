from fastapi import APIRouter, Request
import os
import requests

from app.core.logging_config import logger
from app.orchestrator.workflow import run_expense_workflow

router = APIRouter()

TELEGRAM_API = "https://api.telegram.org"


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    print("Telegram update:", update)
    logger.info("WEBHOOK_UPDATE raw=%s", update)

    if "message" not in update:
        return {"ok": True}

    chat_id = update["message"]["chat"]["id"]
    text = update["message"].get("text", "")
    logger.info("WEBHOOK_MESSAGE chat_id=%s text=%r", chat_id, text)
    reply_text = run_expense_workflow(chat_id, text)
    logger.info("WEBHOOK_REPLY chat_id=%s reply=%r", chat_id, reply_text)

    # ============================================
    # 4️⃣ Send reply back to Telegram
    # ============================================
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
    logger.info(
        "TELEGRAM_SEND_MESSAGE chat_id=%s status=%s response=%s",
        chat_id,
        response.status_code,
        response.text,
    )

    return {"ok": True}
