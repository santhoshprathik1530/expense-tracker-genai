from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.core.logging_config import logger
from app.db.expense_repository import (
    add_expense_db,
    aggregate_expenses_db,
    delete_expense_db,
    search_expenses_db,
    update_expense_db,
)
from app.orchestrator.planner import generate_plan


CANCEL_WORDS = {"cancel", "nevermind", "never mind", "stop", "ignore", "forget it"}
MAX_DISAMBIGUATION_LIST = 10


class WorkflowState(TypedDict, total=False):
    chat_id: int
    user_message: str
    actions: List[Dict[str, Any]]
    action_index: int
    last_search: List[Dict[str, Any]]
    search_results: List[Dict[str, Any]]
    executed_messages: List[str]
    pending_action: Optional[Dict[str, Any]]
    awaiting_selection: bool
    selected_expense: Optional[Dict[str, Any]]
    reply_text: Optional[str]


def _is_cancel(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in CANCEL_WORDS or any(word in lowered for word in CANCEL_WORDS)


def _parse_selection(text: str) -> Optional[int]:
    stripped = text.strip()
    if stripped.isdigit():
        selection = int(stripped)
        if 1 <= selection <= 99:
            return selection
    return None


def _format_candidate_list(candidates: List[Dict[str, Any]]) -> str:
    lines = ["I found multiple matching expenses:"]
    for index, expense in enumerate(candidates[:MAX_DISAMBIGUATION_LIST], start=1):
        description = expense.get("description", "—")[:50]
        lines.append(
            f"{index}) {expense.get('currency', 'USD')} {float(expense.get('amount', 0)):.2f} "
            f"- {expense.get('category', 'misc')}/{expense.get('sub_category', '—')} "
            f"- {description} ({expense.get('date')})"
        )
    lines.append("\nReply with the number (1, 2, 3...) or say 'cancel'.")
    return "\n".join(lines)


def _format_search_results(candidates: List[Dict[str, Any]]) -> str:
    lines = ["I found these matching expenses:"]
    total = 0.0
    for expense in candidates[:MAX_DISAMBIGUATION_LIST]:
        total += float(expense.get("amount", 0))
        description = expense.get("description", "—")[:50]
        lines.append(
            f"- {expense.get('currency', 'USD')} {float(expense.get('amount', 0)):.2f} "
            f"- {expense.get('category', 'misc')}/{expense.get('sub_category', '—')} "
            f"- {description} ({expense.get('date')})"
        )
    lines.append(f"\nShown total: {total:.2f}")
    return "\n".join(lines)


def _is_total_query(text: str) -> bool:
    lowered = text.lower()
    triggers = [
        "how much",
        "total",
        "sum",
        "spent",
        "spend",
    ]
    return any(trigger in lowered for trigger in triggers)


def _infer_followup_action(user_message: str) -> Optional[Dict[str, Any]]:
    lowered = user_message.lower()

    if any(word in lowered for word in ["delete", "remove"]):
        return {
            "tool": "delete_expense",
            "arguments": {"use_last_search_result": True},
        }

    if any(word in lowered for word in ["update", "change", "edit", "set"]):
        amount_match = re.search(r"\bto\s+(\d+(?:\.\d{1,2})?)\b", lowered)
        if amount_match:
            return {
                "tool": "update_expense",
                "arguments": {
                    "use_last_search_result": True,
                    "amount": float(amount_match.group(1)),
                },
            }

        delta_match = re.search(r"\b(?:add|increase)\s+(\d+(?:\.\d{1,2})?)\b", lowered)
        if delta_match:
            return {
                "tool": "update_expense",
                "arguments": {
                    "use_last_search_result": True,
                    "amount_delta": float(delta_match.group(1)),
                },
            }

    return None


def _format_aggregate_result(result: Dict[str, Any]) -> str:
    breakdown = result.get("breakdown") or []
    group_by = result.get("group_by")
    total = float(result.get("total", 0))
    count = int(result.get("count", 0))

    if group_by and breakdown:
        lines = [f"Total: {total:.2f} across {count} expense(s).", f"By {group_by}:"]
        for item in breakdown:
            lines.append(f"- {item['label']}: {item['total']:.2f} across {item['count']} expense(s)")
        return "\n".join(lines)

    return f"Total: {total:.2f} across {count} expense(s)."


def _execute_modify_action(
    action: Dict[str, Any],
    expense: Dict[str, Any],
) -> str:
    tool = action.get("tool")
    args = action.get("arguments", {}) or {}

    expense_id = expense.get("id")
    if expense_id is None:
        return "Internal error: matched expense missing id."

    if tool == "delete_expense":
        deleted = delete_expense_db(expense_id)
        if deleted:
            return (
                f"Deleted: {expense.get('currency', 'USD')} {float(expense.get('amount', 0)):.2f} "
                f"- {expense.get('category', 'misc')}/{expense.get('sub_category', '—')} "
                f"- {expense.get('description', '')} ({expense.get('date')})"
            )
        return "Couldn’t delete that expense."

    if tool == "update_expense":
        updates: Dict[str, Any] = {}

        if args.get("amount") is not None:
            updates["amount"] = float(args["amount"])
        elif args.get("amount_delta") is not None:
            updates["amount"] = float(expense.get("amount", 0)) + float(args["amount_delta"])

        for field in ["currency", "category", "sub_category", "description", "date"]:
            if args.get(field) is not None:
                updates[field] = args[field]

        if not updates:
            return "Nothing to update."

        updated = update_expense_db(expense_id, **updates)
        if not updated:
            return "Couldn’t update that expense."

        lines = [f"Updated expense {expense_id}:"]
        for key, value in updates.items():
            lines.append(f"- {key} -> {value}")
        return "\n".join(lines)

    return f"Unsupported action: {tool}"


def _check_pending_selection(state: WorkflowState) -> WorkflowState:
    if not state.get("awaiting_selection"):
        return {
            "selected_expense": None,
            "reply_text": None,
        }

    text = state.get("user_message", "")
    if _is_cancel(text):
        return {
            "awaiting_selection": False,
            "pending_action": None,
            "search_results": [],
            "selected_expense": None,
            "reply_text": "Cancelled. What would you like to do next?",
        }

    selection = _parse_selection(text)
    candidates = state.get("search_results", [])

    if selection is not None:
        index = selection - 1
        if index < 0 or index >= len(candidates):
            return {
                "reply_text": "That selection number is out of range. Reply with a valid number or say 'cancel'.",
            }
        return {
            "selected_expense": candidates[index],
            "reply_text": None,
        }

    return {
        "awaiting_selection": False,
        "pending_action": None,
        "search_results": [],
        "selected_expense": None,
        "reply_text": None,
    }


def _route_after_pending_check(state: WorkflowState) -> str:
    if state.get("awaiting_selection"):
        if state.get("reply_text"):
            return "finish"
        if state.get("selected_expense") and state.get("pending_action"):
            return "resume_pending_action"
    return "plan_request"


def _resume_pending_action(state: WorkflowState) -> WorkflowState:
    pending_action = state.get("pending_action")
    selected_expense = state.get("selected_expense")
    if not pending_action or not selected_expense:
        return {"reply_text": "I lost the pending action. Please try again."}

    logger.info(
        "WORKFLOW_RESUME_PENDING chat_id=%s action=%s selected_expense=%s",
        state.get("chat_id"),
        pending_action,
        selected_expense,
    )
    reply_text = _execute_modify_action(pending_action, selected_expense)
    return {
        "awaiting_selection": False,
        "pending_action": None,
        "search_results": [],
        "selected_expense": None,
        "reply_text": reply_text,
        "actions": [],
        "action_index": 0,
        "last_search": [],
        "executed_messages": [],
    }


def _plan_request(state: WorkflowState) -> WorkflowState:
    logger.info(
        "WORKFLOW_INPUT chat_id=%s user_message=%r",
        state.get("chat_id"),
        state.get("user_message", ""),
    )
    plan = generate_plan(state.get("user_message", ""))
    logger.info("WORKFLOW PLAN: %s", plan)

    if not isinstance(plan, dict) or "actions" not in plan:
        return {
            "actions": [],
            "action_index": 0,
            "last_search": [],
            "executed_messages": [],
            "reply_text": "I couldn't understand that request. Try again with a simpler message.",
        }

    actions = plan.get("actions") or []
    if len(actions) == 1 and actions[0].get("tool") == "search_expenses":
        followup_action = _infer_followup_action(state.get("user_message", ""))
        if followup_action is not None:
            actions = actions + [followup_action]
            logger.info(
                "WORKFLOW_INFERRED_FOLLOWUP chat_id=%s followup_action=%s",
                state.get("chat_id"),
                followup_action,
            )

    if not actions:
        return {
            "actions": [],
            "action_index": 0,
            "last_search": [],
            "executed_messages": [],
            "reply_text": "I can help track, update, delete, and summarize expenses.",
        }

    return {
        "actions": actions,
        "action_index": 0,
        "last_search": [],
        "executed_messages": [],
        "reply_text": None,
        "selected_expense": None,
    }


def _route_after_plan(state: WorkflowState) -> str:
    return "finish" if state.get("reply_text") else "execute_next_action"


def _execute_next_action(state: WorkflowState) -> WorkflowState:
    actions = state.get("actions", [])
    action_index = state.get("action_index", 0)

    if action_index >= len(actions):
        return {}

    action = actions[action_index]
    tool = action.get("tool")
    args = action.get("arguments", {}) or {}
    logger.info(
        "WORKFLOW_ACTION chat_id=%s index=%s tool=%s arguments=%s",
        state.get("chat_id"),
        action_index,
        tool,
        args,
    )

    if tool == "search_expenses":
        filters = args.get("filters") or {}
        limit = int(args.get("limit") or 10)
        results = search_expenses_db(state["chat_id"], filters=filters, limit=limit)

        if len(results) == 0:
            logger.info("WORKFLOW_SEARCH_RESULT chat_id=%s count=0", state.get("chat_id"))
            return {"reply_text": "No matching expenses found."}

        if len(results) > 1:
            next_action = actions[action_index + 1] if action_index + 1 < len(actions) else None
            logger.info(
                "WORKFLOW_SEARCH_RESULT chat_id=%s count=%s next_action=%s results=%s",
                state.get("chat_id"),
                len(results),
                next_action,
                results,
            )
            if next_action is None:
                if _is_total_query(state.get("user_message", "")):
                    total = sum(float(expense.get("amount", 0)) for expense in results)
                    logger.info(
                        "WORKFLOW_SEARCH_TOTAL_FALLBACK chat_id=%s total=%s count=%s",
                        state.get("chat_id"),
                        total,
                        len(results),
                    )
                    return {"reply_text": f"Total: {total:.2f} across {len(results)} expense(s)."}
                return {"reply_text": _format_search_results(results)}
            return {
                "search_results": results[:MAX_DISAMBIGUATION_LIST],
                "pending_action": next_action,
                "awaiting_selection": True,
                "reply_text": _format_candidate_list(results),
            }

        expense = results[0]
        logger.info(
            "WORKFLOW_SEARCH_RESULT chat_id=%s count=1 result=%s",
            state.get("chat_id"),
            expense,
        )
        message = (
            f"Found: {expense.get('currency', 'USD')} {float(expense.get('amount', 0)):.2f} "
            f"- {expense.get('category', 'misc')}/{expense.get('sub_category', '—')} "
            f"- {expense.get('description', '')} ({expense.get('date')})"
        )
        return {
            "last_search": results,
            "executed_messages": state.get("executed_messages", []) + [message],
            "action_index": action_index + 1,
        }

    if tool == "create_expense":
        created = add_expense_db(state["chat_id"], args)
        logger.info("WORKFLOW_CREATE_RESULT chat_id=%s created=%s", state.get("chat_id"), created)
        return {
            "executed_messages": state.get("executed_messages", []) + ["Logged the expense."],
            "action_index": action_index + 1,
        }

    if tool in {"update_expense", "delete_expense"}:
        last_search = state.get("last_search", [])
        if len(last_search) != 1:
            return {"reply_text": "Safety check: I need exactly one matched expense to modify. Please refine your request."}

        result_message = _execute_modify_action(action, last_search[0])
        logger.info(
            "WORKFLOW_MODIFY_RESULT chat_id=%s tool=%s target=%s result=%r",
            state.get("chat_id"),
            tool,
            last_search[0],
            result_message,
        )
        return {
            "executed_messages": state.get("executed_messages", []) + [result_message],
            "action_index": action_index + 1,
            "selected_expense": None,
        }

    if tool == "aggregate_expenses":
        result = aggregate_expenses_db(state["chat_id"], args)
        logger.info("WORKFLOW_AGGREGATE_RESULT chat_id=%s result=%s", state.get("chat_id"), result)
        return {
            "executed_messages": state.get("executed_messages", []) + [_format_aggregate_result(result)],
            "action_index": action_index + 1,
        }

    return {"reply_text": f"Planner requested an unknown tool: {tool}"}


def _route_after_action(state: WorkflowState) -> str:
    if state.get("reply_text"):
        return "finish"
    if state.get("action_index", 0) < len(state.get("actions", [])):
        return "execute_next_action"
    return "finish"


def _finish(state: WorkflowState) -> WorkflowState:
    if state.get("reply_text"):
        logger.info("WORKFLOW_OUTPUT chat_id=%s reply=%r", state.get("chat_id"), state["reply_text"])
        return {"reply_text": state["reply_text"]}

    executed_messages = state.get("executed_messages", [])
    if executed_messages:
        reply_text = "\n".join(executed_messages)
        logger.info("WORKFLOW_OUTPUT chat_id=%s reply=%r", state.get("chat_id"), reply_text)
        return {"reply_text": reply_text}

    logger.info("WORKFLOW_OUTPUT chat_id=%s reply=%r", state.get("chat_id"), "Done.")
    return {"reply_text": "Done."}


def _build_graph():
    graph = StateGraph(WorkflowState)

    graph.add_node("check_pending_selection", _check_pending_selection)
    graph.add_node("resume_pending_action", _resume_pending_action)
    graph.add_node("plan_request", _plan_request)
    graph.add_node("execute_next_action", _execute_next_action)
    graph.add_node("finish", _finish)

    graph.add_edge(START, "check_pending_selection")
    graph.add_conditional_edges(
        "check_pending_selection",
        _route_after_pending_check,
        {
            "resume_pending_action": "resume_pending_action",
            "plan_request": "plan_request",
            "finish": "finish",
        },
    )
    graph.add_edge("resume_pending_action", "finish")
    graph.add_conditional_edges(
        "plan_request",
        _route_after_plan,
        {
            "execute_next_action": "execute_next_action",
            "finish": "finish",
        },
    )
    graph.add_conditional_edges(
        "execute_next_action",
        _route_after_action,
        {
            "execute_next_action": "execute_next_action",
            "finish": "finish",
        },
    )
    graph.add_edge("finish", END)

    return graph.compile(checkpointer=MemorySaver())


expense_workflow = _build_graph()


def run_expense_workflow(chat_id: int, user_message: str) -> str:
    result = expense_workflow.invoke(
        {
            "chat_id": chat_id,
            "user_message": user_message,
        },
        config={"configurable": {"thread_id": f"telegram:{chat_id}"}},
    )
    return result.get("reply_text") or "Done."
