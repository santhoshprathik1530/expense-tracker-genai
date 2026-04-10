# Local Run Guide

Use this file as the single place for the commands needed to run the app locally and make the Telegram webhook live.

## 1. Activate venv

```bash
source .venv/bin/activate
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Start FastAPI locally

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/
```

## 4. Start ngrok for Telegram webhook

```bash
ngrok http 8000
```

Copy the HTTPS URL from ngrok, for example:

```text
https://your-ngrok-subdomain.ngrok-free.dev
```

## 5. Set Telegram webhook

Replace:
- `YOUR_BOT_TOKEN`
- `YOUR_NGROK_URL`

```bash
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"YOUR_NGROK_URL/telegram/webhook"}'
```

Example:

```bash
curl -X POST "https://api.telegram.org/bot123456:ABCDEF/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://your-ngrok-subdomain.ngrok-free.dev/telegram/webhook"}'
```

## 6. Verify webhook

```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getWebhookInfo"
```

## 7. Watch logs

General app flow:

```bash
tail -f logs/app.log
```

Planner / LLM logs:

```bash
tail -f logs/llm.log
```

## 8. Test messages in Telegram

Try:

```text
hi
i spent 10 dollars on lunch today
how much did i spend today
which category did i spend today
change my lunch expense to 12
```

## 9. Stop webhook later

```bash
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/deleteWebhook"
```
