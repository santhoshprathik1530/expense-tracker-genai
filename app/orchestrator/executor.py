# app/orchestrator/executor.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date

from app.orchestrator.state import STATE, PendingState
from app.core.logging_config import logger


# DB tools (you might need to adjust function names to match your repository)
from app.db.expense_repository import (
    search_expenses_db,        # NEW: implement if not present
    add_expense_db,            # already have
    update_expense_db,         # already have (by id)
    delete_expense_db,         # already have (by id)
    aggregate_expenses_db,     # NEW: implement later (can stub)
)

ALLOWED_TOOLS = {
    "search_expenses",
    "create_expense",
    "update_expense",
    "delete_expense",
    "aggregate_expenses",
}

CANCEL_WORDS = {"cancel", "nevermind", "never mind", "stop", "ignore", "forget it"}
MAX_DISAMBIGUATION_LIST = 10


def _is_cancel(text: str) -> bool:
    t = text.strip().lower()
    return t in CANCEL_WORDS or any(w in t for w in CANCEL_WORDS)


def _parse_selection(text: str) -> Optional[int]:
    """
    Returns 1-based selection index if user sent a clean number like "1" or "2".
    """
    t = text.strip()
    if t.isdigit():
        n = int(t)
        if 1 <= n <= 99:
            return n
    return None


def _format_candidate_list(cands: List[Dict[str, Any]]) -> str:
    lines = ["I found multiple matching expenses:"]
    for i, e in enumerate(cands[:MAX_DISAMBIGUATION_LIST], start=1):
        # expected keys: id, date, description, category, sub_category, amount, currency
        desc = e.get("description", "—")[:50]  # truncate long descriptions
        sub_cat = e.get("sub_category", "—")
        lines.append(
            f"{i}) {e.get('currency','USD')} {float(e.get('amount',0)):.2f} - {e.get('category','misc')}/{sub_cat} "
            f"- {desc} ({e.get('date')})"
        )
    lines.append("\nReply with the number (1, 2, 3...) or say 'cancel'.")
    return "\n".join(lines)


def handle_pending_if_any(chat_id: int, text: str) -> Optional[str]:
    """
    If user is in disambiguation mode:
      - numeric selection -> execute pending action on chosen candidate
      - cancel -> clear state
      - anything else -> clear state and treat as new request (return None)
    Returns reply_text if handled, else None.
    """
    if chat_id not in STATE:
        return None

    # If user cancels
    if _is_cancel(text):
        del STATE[chat_id]
        return "✅ Cancelled. What would you like to do next?"

    # If user selects a number
    sel = _parse_selection(text)
    pending = STATE[chat_id]

    if sel is not None:
        idx = sel - 1
        if idx < 0 or idx >= len(pending.candidates):
            return "That selection number is out of range. Reply with a valid number or say 'cancel'."

        chosen = pending.candidates[idx]
        action = pending.pending_action
        # Execute the waiting action using chosen expense_id
        reply = _execute_single_action(chat_id, action, chosen_expense=chosen)

        # Clear state after executing
        del STATE[chat_id]
        return reply

    # User said something else (topic switch) -> clear state, let normal planner run
    del STATE[chat_id]
    return None


def execute_plan(chat_id: int, plan: Dict[str, Any]) -> str:
    """
    Execute a planner-first plan. Returns a user-friendly reply string.
    """
    logger.info(f"EXECUTING PLAN: {plan}")

    if not isinstance(plan, dict) or "actions" not in plan:
        return "I couldn't understand that request. Try again with a simpler message."

    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        return "Plan contained no actions. Try rephrasing."

    # Execution context
    last_search: List[Dict[str, Any]] = []

    # Collect outputs (for final response)
    executed_messages: List[str] = []

    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            return "Invalid action format from planner."

        tool = action.get("tool")
        args = action.get("arguments", {})

        if tool not in ALLOWED_TOOLS:
            return f"Planner requested an unknown tool: {tool}"

        # Defensive rule: update/delete must be preceded by search in THIS plan or earlier context
        if tool in {"update_expense", "delete_expense"}:
            if not last_search and not args.get("use_last_search_result", False):
                return "Safety check: cannot update/delete without searching first."

        # Execute each tool
        if tool == "search_expenses":
            filters = (args.get("filters") or {})
            limit = int(args.get("limit") or 10)
            results = search_expenses_db(chat_id, filters=filters, limit=limit)  # returns list[dict]
            last_search = results

            if len(results) == 0:
                return "No matching expenses found."

            if len(results) > 1:
                # Planner likely expects to use last search result. We stop and ask user to pick.
                # Determine what the next action is, if any, to store as pending.
                next_action = None
                if i + 1 < len(actions):
                    next_action = actions[i + 1]
                else:
                    # If no next action, user probably just wanted to view matches
                    # So we can show matches and stop.
                    return _format_candidate_list(results)

                # Store pending state to execute next action after selection
                STATE[chat_id] = PendingState(
                    candidates=results[:MAX_DISAMBIGUATION_LIST],
                    pending_action=next_action,
                )
                return _format_candidate_list(results)

            # exactly 1 match
            e = results[0]
            executed_messages.append(
                f"Found: {e.get('currency','USD')} {float(e.get('amount',0)):.2f} - {e.get('category','misc')}/{e.get('sub_category','—')} - {e.get('description','')} ({e.get('date')})"
            )

        elif tool == "create_expense":
            # args expected to contain required fields
            created = add_expense_db(chat_id, args)  # if your add_expense_db expects ExtractedExpense, adapt later
            executed_messages.append("✅ Logged the expense.")

        elif tool == "update_expense":
            msg = _execute_single_action(chat_id, action, last_search=last_search)
            executed_messages.append(msg)

        elif tool == "delete_expense":
            msg = _execute_single_action(chat_id, action, last_search=last_search)
            executed_messages.append(msg)

        elif tool == "aggregate_expenses":
            # You can stub this for now if not implemented yet
            result = aggregate_expenses_db(chat_id, args)  # return dict like {"total":..., "count":...}
            total = float(result.get("total", 0))
            count = int(result.get("count", 0))
            executed_messages.append(f"Total: {total:.2f} across {count} expense(s).")

    # Final response
    return "\n".join(executed_messages) if executed_messages else "Done."


def _execute_single_action(
    chat_id: int,
    action: Dict[str, Any],
    last_search: Optional[List[Dict[str, Any]]] = None,
    chosen_expense: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Executes update/delete using either:
      - chosen_expense (from pending selection), OR
      - last_search (must contain exactly one match)
    """
    tool = action.get("tool")
    args = action.get("arguments", {}) or {}

    expense = chosen_expense
    if expense is None:
        if not last_search or len(last_search) != 1:
            return "Safety check: I need exactly one matched expense to modify. Please refine your request."
        expense = last_search[0]

    expense_id = expense.get("id")
    if expense_id is None:
        return "Internal error: matched expense missing id."

    if tool == "delete_expense":
        ok = delete_expense_db(expense_id)
        if ok:
            return f"🗑️ Deleted: {expense.get('currency','USD')} {float(expense.get('amount',0)):.2f} - {expense.get('category','misc')}/{expense.get('sub_category','—')} - {expense.get('description','')} ({expense.get('date')})"
        return "Couldn’t delete that expense."

    if tool == "update_expense":
        # Support absolute or delta
        amount = args.get("amount", None)
        amount_delta = args.get("amount_delta", None)

        updates: Dict[str, Any] = {}

        if amount is not None:
            updates["amount"] = float(amount)
        elif amount_delta is not None:
            updates["amount"] = float(expense.get("amount", 0)) + float(amount_delta)

        for k in ["currency", "category", "sub_category", "description"]:
            if args.get(k) is not None:
                updates[k] = args[k]

        if args.get("date"):
            updates["date"] = args["date"]

        if not updates:
            return "Nothing to update."

        ok = update_expense_db(expense_id, **updates)
        if ok:
            parts = [f"✏️ Updated expense {expense_id}:"]
            for k, v in updates.items():
                parts.append(f"- {k} → {v}")
            return "\n".join(parts)
        return "Couldn’t update that expense."

    return f"Unsupported pending action: {tool}"
