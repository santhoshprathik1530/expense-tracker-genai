from typing import Union

from app.core.logging_config import logger
from app.db.client import get_connection
from app.orchestrator.expense_schema import ExtractedExpense


def _row_to_expense(row):
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "date": row["date"],
        "description": row["description"],
        "category": row["category"],
        "sub_category": row["sub_category"],
        "amount": float(row["amount"]),
        "currency": row["currency"],
    }


def add_expense_db(user_id: int, expense: Union[ExtractedExpense, dict]):
    conn = get_connection()
    cur = conn.cursor()

    data = expense.model_dump() if isinstance(expense, ExtractedExpense) else expense
    logger.info("DB_ADD_EXPENSE_INPUT user_id=%s data=%s", user_id, data)

    cur.execute(
        """
        INSERT INTO expenses
        (user_id, date, description, category, sub_category, amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            data.get("date") or data.get("expense_date"),
            data.get("description", ""),
            data.get("category"),
            data.get("sub_category"),
            data.get("amount"),
            data.get("currency", "USD"),
        ),
    )
    expense_id = cur.lastrowid
    conn.commit()

    cur.execute(
        """
        SELECT id, user_id, date, description, category, sub_category, amount, currency
        FROM expenses
        WHERE id = ?
        """,
        (expense_id,),
    )
    result = cur.fetchone()
    cur.close()
    conn.close()

    created = _row_to_expense(result)
    logger.info("DB_ADD_EXPENSE_RESULT user_id=%s created=%s", user_id, created)
    return created


def get_expenses_db(user_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, date, description, category, sub_category, amount, currency
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC, created_at DESC
        """,
        (user_id,),
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    expenses = [_row_to_expense(row) for row in rows]
    logger.info("DB_GET_EXPENSES_RESULT user_id=%s count=%s", user_id, len(expenses))
    return expenses


def search_expenses_db(user_id: int, filters: dict, limit: int = 10):
    conn = get_connection()
    cur = conn.cursor()

    logger.info("search_expenses_db filters: %s", filters)

    query = """
        SELECT id, user_id, date, description, category, sub_category, amount, currency
        FROM expenses
        WHERE user_id = ?
    """
    params = [user_id]

    if filters.get("description"):
        query += " AND lower(description) LIKE ?"
        params.append(f"%{filters['description'].lower()}%")

    if filters.get("category"):
        query += " AND lower(category) LIKE ?"
        params.append(f"%{filters['category'].lower()}%")

    if filters.get("sub_category"):
        query += " AND lower(sub_category) LIKE ?"
        params.append(f"%{filters['sub_category'].lower()}%")

    if filters.get("date"):
        query += " AND date = ?"
        params.append(filters["date"])

    if filters.get("start_date"):
        query += " AND date >= ?"
        params.append(filters["start_date"])

    if filters.get("end_date"):
        query += " AND date <= ?"
        params.append(filters["end_date"])

    if filters.get("amount_min") is not None:
        query += " AND amount >= ?"
        params.append(filters["amount_min"])

    if filters.get("amount_max") is not None:
        query += " AND amount <= ?"
        params.append(filters["amount_max"])

    query += " ORDER BY date DESC, created_at DESC LIMIT ?"
    params.append(limit)

    logger.info("search_expenses_db query: %s", query.strip())
    logger.info("search_expenses_db params: %s", params)

    cur.execute(query, tuple(params))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    results = [_row_to_expense(row) for row in rows]
    logger.info("DB_SEARCH_EXPENSES_RESULT user_id=%s count=%s results=%s", user_id, len(results), results)
    return results


def update_expense_db(expense_id: int, **updates):
    if not updates:
        return False

    logger.info("DB_UPDATE_EXPENSE_INPUT expense_id=%s updates=%s", expense_id, updates)

    conn = get_connection()
    cur = conn.cursor()

    fields = []
    values = []

    for key, value in updates.items():
        fields.append(f"{key} = ?")
        values.append(value)

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(expense_id)

    query = f"""
        UPDATE expenses
        SET {', '.join(fields)}
        WHERE id = ?
    """

    cur.execute(query, tuple(values))
    updated_rows = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()

    logger.info("DB_UPDATE_EXPENSE_RESULT expense_id=%s updated=%s", expense_id, updated_rows > 0)
    return updated_rows > 0


def delete_expense_db(expense_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    deleted_rows = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()

    logger.info("DB_DELETE_EXPENSE_RESULT expense_id=%s deleted=%s", expense_id, deleted_rows > 0)
    return deleted_rows > 0


def aggregate_expenses_db(user_id: int, filters: dict):
    group_by = None
    if isinstance(filters, dict):
        group_by = filters.get("group_by")
        if isinstance(filters.get("filters"), dict):
            filters = filters.get("filters")
    logger.info("DB_AGGREGATE_INPUT user_id=%s group_by=%s filters=%s", user_id, group_by, filters)

    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT SUM(amount), COUNT(*)
        FROM expenses
        WHERE user_id = ?
    """
    params = [user_id]

    if filters.get("category"):
        query += " AND lower(category) LIKE ?"
        params.append(f"%{filters['category'].lower()}%")

    if filters.get("sub_category"):
        query += " AND lower(sub_category) LIKE ?"
        params.append(f"%{filters['sub_category'].lower()}%")

    if filters.get("start_date"):
        query += " AND date >= ?"
        params.append(filters["start_date"])

    if filters.get("end_date"):
        query += " AND date <= ?"
        params.append(filters["end_date"])

    cur.execute(query, tuple(params))
    result = cur.fetchone()

    breakdown = []
    if group_by in {"category", "sub_category", "date"}:
        group_column = group_by
        group_query = f"""
            SELECT COALESCE({group_column}, 'Uncategorized') as label, SUM(amount) as total, COUNT(*)
            FROM expenses
            WHERE user_id = ?
        """
        group_params = [user_id]

        if filters.get("category"):
            group_query += " AND lower(category) LIKE ?"
            group_params.append(f"%{filters['category'].lower()}%")

        if filters.get("sub_category"):
            group_query += " AND lower(sub_category) LIKE ?"
            group_params.append(f"%{filters['sub_category'].lower()}%")

        if filters.get("start_date"):
            group_query += " AND date >= ?"
            group_params.append(filters["start_date"])

        if filters.get("end_date"):
            group_query += " AND date <= ?"
            group_params.append(filters["end_date"])

        group_query += f" GROUP BY {group_column} ORDER BY total DESC"
        cur.execute(group_query, tuple(group_params))
        breakdown = [
            {
                "label": row[0],
                "total": float(row[1]),
                "count": int(row[2]),
            }
            for row in cur.fetchall()
        ]

    cur.close()
    conn.close()

    total = float(result[0]) if result[0] else 0.0
    count = result[1] if result[1] else 0

    aggregate = {"total": total, "count": count, "group_by": group_by, "breakdown": breakdown}
    logger.info("DB_AGGREGATE_RESULT user_id=%s result=%s", user_id, aggregate)
    return aggregate
