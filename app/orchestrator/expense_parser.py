import re
from datetime import datetime, date
import dateparser
from app.orchestrator.expense_schema import ExtractedExpense

AMOUNT_RE = re.compile(r"(?P<currency>[$₹€£])?\s*(?P<amount>\d+(?:\.\d{1,2})?)")

CURRENCY_MAP = {
    "$": "USD",
    "₹": "INR",
    "€": "EUR",
    "£": "GBP",
}

CATEGORY_KEYWORDS = {
    "coffee": ["starbucks", "coffee", "cafe", "latte", "cappuccino"],
    "food": ["lunch", "dinner", "breakfast", "pizza", "biryani", "restaurant", "swiggy", "zomato"],
    "transport": ["uber", "ola", "taxi", "auto", "bus", "train", "metro", "flight"],
    "groceries": ["grocery", "groceries", "supermarket", "walmart", "costco"],
    "shopping": ["amazon", "flipkart", "mall", "shopping"],
}

def infer_category(text: str) -> str:
    t = text.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(k in t for k in kws):
            return cat
    return "misc"


def extract_merchant(text: str) -> str | None:
    # very simple heuristic for now:
    # "at Starbucks" -> Starbucks
    m = re.search(r"\bat\s+([A-Za-z][A-Za-z0-9&\-\s]{1,30})", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def extract_date(text: str, base_dt: datetime) -> date:
    # dateparser handles "yesterday", "last friday", etc.
    dt = dateparser.parse(
        text,
        settings={
            "RELATIVE_BASE": base_dt,
            "PREFER_DATES_FROM": "past",
        }
    )
    return (dt.date() if dt else base_dt.date())


def extract_amount_currency(text: str) -> tuple[float | None, str | None]:
    m = AMOUNT_RE.search(text)
    if not m:
        return None, None

    amount = float(m.group("amount"))
    symbol = m.group("currency")
    currency = CURRENCY_MAP.get(symbol, None)
    return amount, currency


def parse_expense_message(text: str, base_dt: datetime | None = None) -> ExtractedExpense | None:
    base_dt = base_dt or datetime.now()

    amount, currency = extract_amount_currency(text)
    if amount is None:
        return None

    exp_date = extract_date(text, base_dt)
    merchant = extract_merchant(text)
    category = infer_category(text)

    # very rough confidence score for now
    confidence = 0.6
    if currency: confidence += 0.1
    if merchant: confidence += 0.1
    if category != "misc": confidence += 0.1

    return ExtractedExpense(
        amount=amount,
        currency=currency or "USD",
        merchant=merchant,
        category=category,
        expense_date=exp_date,
        confidence=min(confidence, 0.95),
    )
