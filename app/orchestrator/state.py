# app/orchestrator/state.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# In-memory state (resets on server restart). Good for learning/dev.
STATE: Dict[int, "PendingState"] = {}


@dataclass
class PendingState:
    """
    Stores disambiguation state for a user (chat_id).
    """
    candidates: List[Dict[str, Any]]          # list of expense dicts (must include id)
    pending_action: Dict[str, Any]            # tool call waiting to be executed (e.g., delete/update)
    reason: str = "multiple_matches"          # optional
