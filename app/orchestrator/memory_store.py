from collections import defaultdict
from typing import List
from app.orchestrator.expense_schema import ExtractedExpense

# user_id → list of expenses
EXPENSE_STORE = defaultdict(list)


def add_expense(user_id: int, expense: ExtractedExpense):
    EXPENSE_STORE[user_id].append(expense)


def get_expenses(user_id: int) -> List[ExtractedExpense]:
    return EXPENSE_STORE[user_id]
