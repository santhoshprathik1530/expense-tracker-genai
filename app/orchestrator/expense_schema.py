from pydantic import BaseModel
from datetime import date
from typing import Optional, Literal

class ExtractedExpense(BaseModel):
    amount: float
    currency: str = "USD"            # default for now
    merchant: Optional[str] = None
    category: str = "misc"
    expense_date: date
    confidence: float = 0.7
