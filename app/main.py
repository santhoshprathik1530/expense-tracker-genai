from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
import os
from app.integrations.telegram import router as telegram_router

load_dotenv()


app = FastAPI()
app.include_router(telegram_router)

@app.get("/")
def health():
    return {"status": "ok", "message": "Expense bot backend running"}
