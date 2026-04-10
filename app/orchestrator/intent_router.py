def detect_intent(text: str) -> str:
    t = text.lower()

    if any(word in t for word in ["track", "show", "summary", "how much"]):
        return "query"

    if any(word in t for word in ["spent", "paid", "bought", "cost"]):
        return "log"

    return "unknown"
