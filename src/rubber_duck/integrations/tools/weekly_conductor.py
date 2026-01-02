# src/rubber_duck/integrations/tools/weekly_conductor.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Weekly review session conductor."""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# State file path
REPO_ROOT = Path(__file__).parent.parent.parent.parent
STATE_PATH = REPO_ROOT / "state" / "weekly_review_session.json"

# Review steps in order
REVIEW_STEPS = [
    ("calendar_review", "Calendar Review", "run_calendar_review()"),
    ("deadline_scan", "Deadline Scan", "run_deadline_scan()"),
    ("waiting_for_review", "Waiting-For Review", "run_waiting_for_review()"),
    ("project_review", "Project Review", "run_project_review()"),
    ("category_health", "Category Health", "run_category_health()"),
    ("someday_maybe_review", "Someday-Maybe Review", "run_someday_maybe_review()"),
]

# Session timeout (24 hours)
SESSION_TIMEOUT_HOURS = 24


def _load_session() -> dict | None:
    """Load session state from file."""
    if not STATE_PATH.exists():
        return None
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_session(session: dict) -> None:
    """Save session state to file."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(session, f, indent=2)


def _clear_session() -> None:
    """Clear session state."""
    if STATE_PATH.exists():
        STATE_PATH.unlink()


def _is_session_stale(session: dict) -> bool:
    """Check if session is older than timeout."""
    started_at = session.get("started_at")
    if not started_at:
        return True

    try:
        start_time = datetime.fromisoformat(started_at)
        age = datetime.now(UTC) - start_time
        return age > timedelta(hours=SESSION_TIMEOUT_HOURS)
    except (ValueError, TypeError):
        return True


def _get_step_index(step_id: str) -> int:
    """Get index of step in REVIEW_STEPS."""
    for i, (sid, _, _) in enumerate(REVIEW_STEPS):
        if sid == step_id:
            return i
    return -1


def _format_step_guidance(step_index: int) -> str:
    """Format guidance for a step."""
    step_id, step_name, tool_call = REVIEW_STEPS[step_index]
    step_num = step_index + 1
    total = len(REVIEW_STEPS)
    return f"**Step {step_num} of {total}: {step_name}**\n\nCall `{tool_call}` to run this review."


def weekly_review_conductor(action: str) -> str:
    """Conduct the weekly review session.

    Actions:
    - start: Begin a new weekly review session
    - status: Get current session status
    - next: Advance to the next step
    - complete: End the session successfully
    - abandon: Clear the session without completing

    Returns:
        Guidance message for the agent
    """
    action = action.lower().strip()
    session = _load_session()

    if action == "start":
        # Check for stale session
        if session and _is_session_stale(session):
            logger.info("Clearing stale weekly review session")
            _clear_session()
            session = None

        if session:
            step_index = _get_step_index(session["current_step"])
            return f"Weekly review already in progress.\n\n{_format_step_guidance(step_index)}"

        # Create new session
        session = {
            "started_at": datetime.now(UTC).isoformat(),
            "current_step": REVIEW_STEPS[0][0],
            "completed_steps": [],
        }
        _save_session(session)

        return f"Weekly review started!\n\n{_format_step_guidance(0)}"

    elif action == "status":
        if not session:
            return (
                "No active weekly review session. "
                "Call `weekly_review_conductor('start')` to begin."
            )

        step_index = _get_step_index(session["current_step"])
        completed = len(session["completed_steps"])
        progress = f"Weekly review in progress ({completed} of {len(REVIEW_STEPS)} complete)."
        return f"{progress}\n\n{_format_step_guidance(step_index)}"

    elif action == "next":
        if not session:
            return (
                "No active weekly review session. "
                "Call `weekly_review_conductor('start')` to begin."
            )

        current_index = _get_step_index(session["current_step"])

        # Mark current as complete
        session["completed_steps"].append(session["current_step"])

        # Check if we're done
        if current_index >= len(REVIEW_STEPS) - 1:
            _clear_session()
            step_names = [name for _, name, _ in REVIEW_STEPS]
            return f"Weekly review complete! Covered: {', '.join(step_names)}."

        # Advance to next step
        next_index = current_index + 1
        session["current_step"] = REVIEW_STEPS[next_index][0]
        _save_session(session)

        return f"Step {current_index + 1} complete.\n\n{_format_step_guidance(next_index)}"

    elif action == "complete":
        if not session:
            return "No active weekly review session to complete."

        completed = session["completed_steps"]
        _clear_session()

        if completed:
            step_names = [name for sid, name, _ in REVIEW_STEPS if sid in completed]
            return f"Weekly review completed early. Covered: {', '.join(step_names)}."
        else:
            return "Weekly review ended (no steps completed)."

    elif action == "abandon":
        _clear_session()
        return "Weekly review session cleared."

    else:
        return f"Unknown action: {action}. Valid actions: start, status, next, complete, abandon."
