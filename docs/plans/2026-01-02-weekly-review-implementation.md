# Weekly Review Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace single-pass weekly review with interactive 6-step session using conductor orchestration.

**Architecture:** Conductor tool manages session state in JSON file. Six sub-review tools fetch Todoist data and return focused output. Agent follows conductor guidance, converses naturally between steps.

**Tech Stack:** Python, Todoist REST API, existing agent loop infrastructure.

---

## Task 1: Extract Shared Utilities from weekly_review.py

**Files:**
- Create: `src/rubber_duck/integrations/tools/weekly_utils.py`
- Modify: `src/rubber_duck/integrations/tools/weekly_review.py`

**Step 1: Create shared utilities module**

```python
# src/rubber_duck/integrations/tools/weekly_utils.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Shared utilities for weekly review tools."""

import os
from datetime import date, datetime, timedelta

import requests

# Label sets for categorization
BACKBURNER_LABELS = {"someday-maybe", "maybe", "someday", "later", "backburner"}
WAITING_LABELS = {"waiting", "waiting-for", "waiting for"}
SOMEDAY_PROJECT_NAMES = {"someday-maybe", "someday maybe", "someday/maybe", "someday"}


def get_todoist_api_key() -> str | None:
    """Get Todoist API key from environment."""
    return os.environ.get("TODOIST_API_KEY")


def fetch_todoist_projects(api_key: str) -> list:
    """Fetch all projects from Todoist."""
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers)
    resp.raise_for_status()
    return resp.json()


def fetch_todoist_tasks(api_key: str) -> list:
    """Fetch all open tasks from Todoist."""
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get("https://api.todoist.com/rest/v2/tasks", headers=headers)
    resp.raise_for_status()
    return resp.json()


def fetch_completed_tasks(api_key: str, days: int = 7) -> list:
    """Fetch completed tasks from last N days."""
    headers = {"Authorization": f"Bearer {api_key}"}
    since = (datetime.now() - timedelta(days=days)).isoformat()
    resp = requests.post(
        "https://api.todoist.com/sync/v9/completed/get_all",
        headers=headers,
        json={"since": since, "limit": 200}
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def group_by_project(items: list, key: str = "project_id") -> dict:
    """Group items by project ID."""
    grouped = {}
    for item in items:
        pid = item.get(key)
        if pid not in grouped:
            grouped[pid] = []
        grouped[pid].append(item)
    return grouped


def is_someday_maybe_project(project_id: str, proj_by_id: dict) -> bool:
    """Check if project or any ancestor is someday-maybe."""
    current_id = project_id
    while current_id:
        proj = proj_by_id.get(current_id)
        if not proj:
            break
        if proj.get("name", "").lower().strip() in SOMEDAY_PROJECT_NAMES:
            return True
        current_id = proj.get("parent_id")
    return False


def compute_project_status(tasks: list, completions: list) -> str:
    """Compute project health status based on GTD principles.

    Returns: ACTIVE, STALLED, WAITING, or INCOMPLETE
    """
    if completions:
        return "ACTIVE"

    next_actions = []
    waiting_actions = []

    for task in tasks:
        labels = {label.lower() for label in task.get("labels", [])}
        if labels & BACKBURNER_LABELS:
            continue
        elif labels & WAITING_LABELS:
            waiting_actions.append(task)
        else:
            next_actions.append(task)

    if not next_actions and not waiting_actions:
        return "INCOMPLETE"
    if not next_actions and waiting_actions:
        return "WAITING"
    return "STALLED"


def calculate_days_until_due(task: dict, today: date) -> int | None:
    """Calculate days until task is due. Negative means overdue."""
    due = task.get("due")
    if not due:
        return None

    due_date_str = due.get("date", "")[:10]
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        return (due_date - today).days
    except ValueError:
        return None


def calculate_task_age_days(task: dict, today: date) -> int | None:
    """Calculate task age in days from created_at."""
    created = task.get("created_at")
    if not created:
        return None
    try:
        created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
        return (today - created_date).days
    except (ValueError, AttributeError):
        return None
```

**Step 2: Verify module imports correctly**

Run: `cd /workspaces/rubber-duck && python -c "from rubber_duck.integrations.tools.weekly_utils import get_todoist_api_key, fetch_todoist_tasks; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/rubber_duck/integrations/tools/weekly_utils.py
git commit -m "refactor: extract shared utilities from weekly_review"
```

---

## Task 2: Create Weekly Conductor

**Files:**
- Create: `src/rubber_duck/integrations/tools/weekly_conductor.py`
- Create: `tests/test_weekly_conductor.py`

**Step 1: Write the failing test**

```python
# tests/test_weekly_conductor.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Tests for weekly review conductor."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from rubber_duck.integrations.tools.weekly_conductor import (
    weekly_review_conductor,
    REVIEW_STEPS,
    _load_session,
    _save_session,
    _clear_session,
)


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary state directory."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    with patch("rubber_duck.integrations.tools.weekly_conductor.STATE_PATH", state_dir / "weekly_review_session.json"):
        yield state_dir


def test_start_creates_session(temp_state_dir):
    """Starting a review creates session state."""
    result = weekly_review_conductor("start")

    assert "Step 1" in result
    assert "calendar" in result.lower()

    session = _load_session()
    assert session is not None
    assert session["current_step"] == "calendar_review"
    assert session["completed_steps"] == []


def test_status_shows_current_step(temp_state_dir):
    """Status returns current step info."""
    weekly_review_conductor("start")
    result = weekly_review_conductor("status")

    assert "Step 1" in result
    assert "calendar" in result.lower()


def test_next_advances_step(temp_state_dir):
    """Next advances to the next step."""
    weekly_review_conductor("start")
    result = weekly_review_conductor("next")

    assert "Step 2" in result
    assert "deadline" in result.lower()

    session = _load_session()
    assert session["current_step"] == "deadline_scan"
    assert "calendar_review" in session["completed_steps"]


def test_next_after_final_step_completes(temp_state_dir):
    """Next after final step completes the review."""
    weekly_review_conductor("start")

    # Advance through all steps
    for _ in range(len(REVIEW_STEPS) - 1):
        weekly_review_conductor("next")

    result = weekly_review_conductor("next")

    assert "complete" in result.lower()
    assert _load_session() is None


def test_complete_ends_session(temp_state_dir):
    """Complete ends the session."""
    weekly_review_conductor("start")
    weekly_review_conductor("next")
    result = weekly_review_conductor("complete")

    assert "complete" in result.lower()
    assert _load_session() is None


def test_abandon_clears_session(temp_state_dir):
    """Abandon clears the session without completing."""
    weekly_review_conductor("start")
    result = weekly_review_conductor("abandon")

    assert "abandon" in result.lower() or "cleared" in result.lower()
    assert _load_session() is None


def test_status_with_no_session(temp_state_dir):
    """Status with no session returns helpful message."""
    result = weekly_review_conductor("status")

    assert "no active session" in result.lower() or "start" in result.lower()


def test_stale_session_auto_clears(temp_state_dir):
    """Session older than 24 hours is auto-cleared on start."""
    from datetime import datetime, timedelta, timezone

    # Create stale session
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    session = {
        "started_at": stale_time,
        "current_step": "deadline_scan",
        "completed_steps": ["calendar_review"],
    }
    _save_session(session)

    result = weekly_review_conductor("start")

    assert "Step 1" in result  # Started fresh
    session = _load_session()
    assert session["current_step"] == "calendar_review"
```

**Step 2: Run test to verify it fails**

Run: `cd /workspaces/rubber-duck && python -m pytest tests/test_weekly_conductor.py -v`
Expected: FAIL with "No module named 'rubber_duck.integrations.tools.weekly_conductor'"

**Step 3: Write the implementation**

```python
# src/rubber_duck/integrations/tools/weekly_conductor.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Weekly review session conductor."""

import json
import logging
from datetime import datetime, timedelta, timezone
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
    except (json.JSONDecodeError, IOError):
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
        age = datetime.now(timezone.utc) - start_time
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
    return f"**Step {step_index + 1} of {len(REVIEW_STEPS)}: {step_name}**\n\nCall `{tool_call}` to run this review."


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
            "started_at": datetime.now(timezone.utc).isoformat(),
            "current_step": REVIEW_STEPS[0][0],
            "completed_steps": [],
        }
        _save_session(session)

        return f"Weekly review started!\n\n{_format_step_guidance(0)}"

    elif action == "status":
        if not session:
            return "No active weekly review session. Call `weekly_review_conductor('start')` to begin."

        step_index = _get_step_index(session["current_step"])
        completed = len(session["completed_steps"])
        return f"Weekly review in progress ({completed} of {len(REVIEW_STEPS)} complete).\n\n{_format_step_guidance(step_index)}"

    elif action == "next":
        if not session:
            return "No active weekly review session. Call `weekly_review_conductor('start')` to begin."

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
```

**Step 4: Run tests to verify they pass**

Run: `cd /workspaces/rubber-duck && python -m pytest tests/test_weekly_conductor.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/rubber_duck/integrations/tools/weekly_conductor.py tests/test_weekly_conductor.py
git commit -m "feat: add weekly review conductor for session orchestration"
```

---

## Task 3: Create Deadline Scan Tool

**Files:**
- Create: `src/rubber_duck/integrations/tools/deadline_scan.py`

**Step 1: Write the implementation**

```python
# src/rubber_duck/integrations/tools/deadline_scan.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Deadline scan sub-review for weekly review."""

from datetime import date, timedelta

from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    calculate_days_until_due,
)


def run_deadline_scan() -> str:
    """Scan tasks for deadline issues.

    Groups tasks by urgency:
    - OVERDUE: Past their deadline
    - DUE THIS WEEK: 0-7 days
    - DUE NEXT WEEK: 8-14 days

    Returns:
        Formatted deadline scan results with action recommendations
    """
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run deadline scan."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        proj_by_id = {p["id"]: p for p in projects}
        today = date.today()

        # Categorize by urgency
        overdue = []
        due_this_week = []
        due_next_week = []

        for task in tasks:
            days = calculate_days_until_due(task, today)
            if days is None:
                continue

            if days < 0:
                overdue.append((task, days))
            elif days <= 7:
                due_this_week.append((task, days))
            elif days <= 14:
                due_next_week.append((task, days))

        # Sort by urgency
        overdue.sort(key=lambda x: x[1])  # Most overdue first
        due_this_week.sort(key=lambda x: x[1])
        due_next_week.sort(key=lambda x: x[1])

        # Build output
        lines = ["## Deadline Scan", ""]

        if overdue:
            lines.append("### OVERDUE - Decision Required")
            lines.append("*For each: reschedule realistically, complete now, or delete if no longer needed*")
            lines.append("")
            for task, days in overdue[:10]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                lines.append(f"- [ ] **{task['content']}** ({abs(days)}d overdue)")
                lines.append(f"      Project: {proj_name}")
            lines.append("")
        else:
            lines.append("### OVERDUE")
            lines.append("*None - great job staying on top of deadlines!*")
            lines.append("")

        if due_this_week:
            lines.append("### DUE THIS WEEK")
            lines.append("*Schedule specific time blocks for these*")
            lines.append("")
            for task, days in due_this_week[:10]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                day_name = (today + timedelta(days=days)).strftime("%A") if days > 0 else "Today"
                lines.append(f"- [ ] **{task['content']}** (due {day_name})")
                lines.append(f"      Project: {proj_name}")
            lines.append("")

        if due_next_week:
            lines.append("### DUE NEXT WEEK")
            lines.append("*Identify any preparation needed*")
            lines.append("")
            for task, days in due_next_week[:10]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                day_name = (today + timedelta(days=days)).strftime("%A, %b %d")
                lines.append(f"- [ ] **{task['content']}** (due {day_name})")
                lines.append(f"      Project: {proj_name}")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append(f"**Summary:** {len(overdue)} overdue, {len(due_this_week)} due this week, {len(due_next_week)} due next week")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running deadline scan: {str(e)}"
```

**Step 2: Verify module imports**

Run: `cd /workspaces/rubber-duck && python -c "from rubber_duck.integrations.tools.deadline_scan import run_deadline_scan; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/rubber_duck/integrations/tools/deadline_scan.py
git commit -m "feat: add deadline_scan sub-review tool"
```

---

## Task 4: Create Waiting-For Review Tool

**Files:**
- Create: `src/rubber_duck/integrations/tools/waiting_for_review.py`

**Step 1: Write the implementation with follow-up strategy matrix**

```python
# src/rubber_duck/integrations/tools/waiting_for_review.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Waiting-for review sub-review for weekly review."""

from datetime import date

from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    calculate_task_age_days,
    WAITING_LABELS,
)


def _get_follow_up_recommendation(age_days: int) -> tuple[str, str]:
    """Get follow-up timing and suggested wording based on age.

    Returns:
        Tuple of (action_level, suggested_wording)
    """
    if age_days is None or age_days < 4:
        return ("wait", "Still within normal timeline - no action needed yet.")
    elif age_days < 8:
        return ("gentle", f"Just checking in on this. No rush, wanted to ensure it's on your radar.")
    elif age_days < 15:
        return ("firm", f"Following up on this from {age_days} days ago. Could you provide a status update?")
    elif age_days < 22:
        return ("urgent", f"This has been pending for {age_days} days. Need a firm timeline or we should explore alternatives.")
    else:
        return ("escalate", f"Waiting {age_days} days. May need to escalate or find workaround.")


def run_waiting_for_review() -> str:
    """Review all waiting-for items for follow-up actions.

    Applies follow-up strategy matrix based on:
    - Age (days since created)
    - Provides specific follow-up wording

    Returns:
        Formatted waiting-for review with action recommendations
    """
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run waiting-for review."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        proj_by_id = {p["id"]: p for p in projects}
        today = date.today()

        # Find waiting-for items
        waiting_items = []
        for task in tasks:
            labels = {label.lower() for label in task.get("labels", [])}
            if labels & WAITING_LABELS:
                age = calculate_task_age_days(task, today)
                action, wording = _get_follow_up_recommendation(age)
                waiting_items.append((task, age, action, wording))

        # Sort by age (oldest first, None last)
        waiting_items.sort(key=lambda x: x[1] if x[1] is not None else -1, reverse=True)

        # Build output
        lines = ["## Waiting-For Review", ""]

        if not waiting_items:
            lines.append("*No waiting-for items found.*")
            return "\n".join(lines)

        # Group by action level
        needs_action = [w for w in waiting_items if w[2] in ("firm", "urgent", "escalate")]
        gentle_check = [w for w in waiting_items if w[2] == "gentle"]
        still_waiting = [w for w in waiting_items if w[2] == "wait"]

        if needs_action:
            lines.append("### NEEDS FOLLOW-UP")
            lines.append("")
            for task, age, action, wording in needs_action:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                age_str = f"{age}d" if age else "?"
                icon = "🔴" if action == "escalate" else "⚠️"
                lines.append(f"- {icon} **{task['content']}** ({age_str})")
                lines.append(f"      Project: {proj_name}")
                lines.append(f"      Suggested: \"{wording}\"")
                lines.append("")

        if gentle_check:
            lines.append("### GENTLE CHECK-IN")
            lines.append("")
            for task, age, action, wording in gentle_check:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                age_str = f"{age}d" if age else "?"
                lines.append(f"- **{task['content']}** ({age_str})")
                lines.append(f"      Project: {proj_name}")
                lines.append(f"      Suggested: \"{wording}\"")
                lines.append("")

        if still_waiting:
            lines.append("### STILL WITHIN TIMELINE")
            lines.append("")
            for task, age, action, wording in still_waiting:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                age_str = f"{age}d" if age else "new"
                lines.append(f"- {task['content']} ({age_str}) - {proj_name}")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append(f"**Summary:** {len(waiting_items)} waiting-for items ({len(needs_action)} need follow-up)")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running waiting-for review: {str(e)}"
```

**Step 2: Verify module imports**

Run: `cd /workspaces/rubber-duck && python -c "from rubber_duck.integrations.tools.waiting_for_review import run_waiting_for_review; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/rubber_duck/integrations/tools/waiting_for_review.py
git commit -m "feat: add waiting_for_review with follow-up strategy matrix"
```

---

## Task 5: Create Project Review Tool

**Files:**
- Create: `src/rubber_duck/integrations/tools/project_review.py`

**Step 1: Write the implementation**

```python
# src/rubber_duck/integrations/tools/project_review.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Project review sub-review for weekly review."""

from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    fetch_completed_tasks,
    group_by_project,
    compute_project_status,
    is_someday_maybe_project,
    BACKBURNER_LABELS,
    WAITING_LABELS,
)


def _get_next_action(tasks: list) -> dict | None:
    """Get highest priority actionable task."""
    actionable = [
        t for t in tasks
        if not ({label.lower() for label in t.get("labels", [])} & (BACKBURNER_LABELS | WAITING_LABELS))
    ]
    if not actionable:
        return None

    prioritized = [t for t in actionable if t.get("priority", 4) < 4]
    if prioritized:
        return min(prioritized, key=lambda t: t.get("priority", 4))
    return actionable[0]


def run_project_review() -> str:
    """Review all projects for health status.

    Computes health status:
    - ACTIVE: Has completions in last 7 days
    - STALLED: Has next actions but no completions
    - WAITING: All tasks are waiting-for
    - INCOMPLETE: No next actions defined

    Returns:
        Formatted project review with health symbols and recommendations
    """
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run project review."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        completed = fetch_completed_tasks(api_key, days=7)

        proj_by_id = {p["id"]: p for p in projects}
        tasks_by_project = group_by_project(tasks)
        completions_by_project = group_by_project(completed)

        # Assess each project
        by_status = {"ACTIVE": [], "STALLED": [], "WAITING": [], "INCOMPLETE": []}
        someday_maybe = []

        for proj in projects:
            pid = proj["id"]
            proj_tasks = tasks_by_project.get(pid, [])
            proj_completions = completions_by_project.get(pid, [])

            # Skip empty projects
            if not proj_tasks and not proj_completions:
                continue

            # Handle someday-maybe separately
            if is_someday_maybe_project(pid, proj_by_id):
                someday_maybe.append((proj, len(proj_tasks)))
                continue

            status = compute_project_status(proj_tasks, proj_completions)
            next_action = _get_next_action(proj_tasks)
            by_status[status].append((proj, proj_tasks, proj_completions, next_action))

        # Build output
        lines = ["## Project Review", ""]

        # ACTIVE projects
        if by_status["ACTIVE"]:
            lines.append("### ✓ ACTIVE (making progress)")
            lines.append("")
            for proj, proj_tasks, proj_completions, _ in by_status["ACTIVE"][:6]:
                lines.append(f"- **{proj['name']}**: {len(proj_completions)} done this week, {len(proj_tasks)} open")
            lines.append("")

        # STALLED projects - need decision
        if by_status["STALLED"]:
            lines.append("### ⚠️ STALLED (has next actions, no progress)")
            lines.append("*Decision needed: better next action? defer? abandon?*")
            lines.append("")
            for proj, proj_tasks, _, next_action in by_status["STALLED"][:5]:
                next_str = f" → {next_action['content'][:50]}" if next_action else ""
                lines.append(f"- **{proj['name']}**: {len(proj_tasks)} tasks{next_str}")
            lines.append("")

        # WAITING projects
        if by_status["WAITING"]:
            lines.append("### ⏳ WAITING (all tasks waiting-for)")
            lines.append("")
            for proj, proj_tasks, _, _ in by_status["WAITING"][:5]:
                lines.append(f"- **{proj['name']}**: {len(proj_tasks)} waiting-for items")
            lines.append("")

        # INCOMPLETE projects - critical
        if by_status["INCOMPLETE"]:
            lines.append("### 🔴 INCOMPLETE (needs next action)")
            lines.append("*GTD requires every project have a next action*")
            lines.append("")
            for proj, proj_tasks, _, _ in by_status["INCOMPLETE"][:5]:
                lines.append(f"- **{proj['name']}**: needs next action defined")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append(f"**Summary:** {len(by_status['ACTIVE'])} active, {len(by_status['STALLED'])} stalled, {len(by_status['WAITING'])} waiting, {len(by_status['INCOMPLETE'])} incomplete")
        if someday_maybe:
            lines.append(f"*(Plus {len(someday_maybe)} someday-maybe projects - reviewed separately)*")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running project review: {str(e)}"
```

**Step 2: Verify module imports**

Run: `cd /workspaces/rubber-duck && python -c "from rubber_duck.integrations.tools.project_review import run_project_review; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/rubber_duck/integrations/tools/project_review.py
git commit -m "feat: add project_review with health status assessment"
```

---

## Task 6: Create Category Health Tool

**Files:**
- Create: `src/rubber_duck/integrations/tools/category_health.py`

**Step 1: Write the implementation**

```python
# src/rubber_duck/integrations/tools/category_health.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Category health sub-review for weekly review."""

from datetime import date

from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    group_by_project,
    calculate_task_age_days,
)


def run_category_health() -> str:
    """Analyze task distribution across projects/categories.

    Identifies:
    - Overloaded categories (many tasks, many aging)
    - Neglected categories (no recent activity)
    - Balanced categories

    Returns:
        Formatted category health analysis
    """
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run category health."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        proj_by_id = {p["id"]: p for p in projects}
        today = date.today()

        tasks_by_project = group_by_project(tasks)

        # Analyze each project
        project_stats = []
        total_tasks = len(tasks)

        for proj in projects:
            pid = proj["id"]
            proj_tasks = tasks_by_project.get(pid, [])

            if not proj_tasks:
                continue

            # Calculate metrics
            count = len(proj_tasks)
            aging = sum(1 for t in proj_tasks if (age := calculate_task_age_days(t, today)) and age > 14)

            project_stats.append({
                "name": proj["name"],
                "count": count,
                "aging": aging,
                "percent": round(count / total_tasks * 100) if total_tasks else 0,
            })

        # Sort by count descending
        project_stats.sort(key=lambda x: x["count"], reverse=True)

        # Identify patterns
        overloaded = [p for p in project_stats if p["count"] > 15 or p["aging"] > 5]
        neglected = [p for p in project_stats if p["aging"] == p["count"] and p["count"] > 0]

        # Build output
        lines = ["## Category Health", ""]

        lines.append("### Task Distribution")
        lines.append("")
        for stat in project_stats[:10]:
            bar_len = min(stat["percent"] // 5, 20)
            bar = "█" * bar_len
            aging_note = f" ({stat['aging']} aging)" if stat["aging"] > 0 else ""
            lines.append(f"- **{stat['name']}**: {stat['count']} tasks ({stat['percent']}%) {bar}{aging_note}")

        if len(project_stats) > 10:
            remaining = sum(p["count"] for p in project_stats[10:])
            lines.append(f"- *...and {len(project_stats) - 10} more projects with {remaining} tasks*")
        lines.append("")

        if overloaded:
            lines.append("### ⚠️ Potentially Overloaded")
            lines.append("*Consider: defer some tasks, break into smaller chunks*")
            lines.append("")
            for stat in overloaded[:5]:
                lines.append(f"- **{stat['name']}**: {stat['count']} tasks, {stat['aging']} aging")
            lines.append("")

        if neglected:
            lines.append("### 🔴 All Tasks Aging")
            lines.append("*No recent activity - either activate or move to backburner*")
            lines.append("")
            for stat in neglected[:5]:
                lines.append(f"- **{stat['name']}**: {stat['count']} tasks, all 2+ weeks old")
            lines.append("")

        # Summary
        lines.append("---")
        total_aging = sum(p["aging"] for p in project_stats)
        lines.append(f"**Summary:** {total_tasks} tasks across {len(project_stats)} projects ({total_aging} aging)")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running category health: {str(e)}"
```

**Step 2: Verify module imports**

Run: `cd /workspaces/rubber-duck && python -c "from rubber_duck.integrations.tools.category_health import run_category_health; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/rubber_duck/integrations/tools/category_health.py
git commit -m "feat: add category_health for workload distribution analysis"
```

---

## Task 7: Create Someday-Maybe Review Tool

**Files:**
- Create: `src/rubber_duck/integrations/tools/someday_maybe_review.py`

**Step 1: Write the implementation**

```python
# src/rubber_duck/integrations/tools/someday_maybe_review.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Someday-maybe review sub-review for weekly review."""

from datetime import date

from rubber_duck.integrations.tools.weekly_utils import (
    get_todoist_api_key,
    fetch_todoist_tasks,
    fetch_todoist_projects,
    calculate_task_age_days,
    is_someday_maybe_project,
    BACKBURNER_LABELS,
)


def _get_triage_recommendation(age_days: int | None) -> str:
    """Get triage recommendation based on age."""
    if age_days is None:
        return "keep"
    elif age_days > 365:
        return "delete"  # Over a year in backburner
    elif age_days > 180:
        return "review"  # 6+ months, needs decision
    else:
        return "keep"


def run_someday_maybe_review() -> str:
    """Review backburner/someday-maybe items for triage.

    Groups items by recommendation:
    - CONSIDER ACTIVATING: Ready to become active
    - KEEP: Still interesting, not ready
    - CONSIDER DELETING: Old, no longer relevant

    Returns:
        Formatted someday-maybe review
    """
    api_key = get_todoist_api_key()
    if not api_key:
        return "Todoist is not configured. Cannot run someday-maybe review."

    try:
        tasks = fetch_todoist_tasks(api_key)
        projects = fetch_todoist_projects(api_key)
        proj_by_id = {p["id"]: p for p in projects}
        today = date.today()

        # Find backburner items (by label or project)
        backburner_items = []
        for task in tasks:
            labels = {label.lower() for label in task.get("labels", [])}
            is_backburner_label = bool(labels & BACKBURNER_LABELS)
            is_backburner_project = is_someday_maybe_project(task.get("project_id"), proj_by_id)

            if is_backburner_label or is_backburner_project:
                age = calculate_task_age_days(task, today)
                rec = _get_triage_recommendation(age)
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                backburner_items.append((task, age, rec, proj_name))

        # Sort by age (oldest first)
        backburner_items.sort(key=lambda x: x[1] if x[1] is not None else 0, reverse=True)

        # Build output
        lines = ["## Someday-Maybe Review", ""]

        if not backburner_items:
            lines.append("*No someday-maybe items found.*")
            return "\n".join(lines)

        # Group by recommendation
        consider_delete = [i for i in backburner_items if i[2] == "delete"]
        needs_review = [i for i in backburner_items if i[2] == "review"]
        keep = [i for i in backburner_items if i[2] == "keep"]

        if consider_delete:
            lines.append("### 🗑️ CONSIDER DELETING")
            lines.append("*Over 1 year in backburner - still relevant?*")
            lines.append("")
            for task, age, _, proj_name in consider_delete[:5]:
                age_str = f"{age}d" if age else "?"
                lines.append(f"- [ ] **{task['content']}** ({age_str})")
                lines.append(f"      Project: {proj_name}")
            lines.append("")

        if needs_review:
            lines.append("### 🤔 NEEDS DECISION")
            lines.append("*6+ months old - activate or delete?*")
            lines.append("")
            for task, age, _, proj_name in needs_review[:5]:
                age_str = f"{age}d" if age else "?"
                lines.append(f"- [ ] **{task['content']}** ({age_str})")
                lines.append(f"      Project: {proj_name}")
            lines.append("")

        if keep:
            lines.append("### ✓ KEEP ON BACKBURNER")
            lines.append("*Still interesting, check next review*")
            lines.append("")
            for task, age, _, proj_name in keep[:10]:
                age_str = f"{age}d" if age else "new"
                lines.append(f"- {task['content']} ({age_str}) - {proj_name}")
            if len(keep) > 10:
                lines.append(f"- *...and {len(keep) - 10} more*")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append(f"**Summary:** {len(backburner_items)} someday-maybe items ({len(consider_delete)} to delete, {len(needs_review)} to review)")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running someday-maybe review: {str(e)}"
```

**Step 2: Verify module imports**

Run: `cd /workspaces/rubber-duck && python -c "from rubber_duck.integrations.tools.someday_maybe_review import run_someday_maybe_review; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/rubber_duck/integrations/tools/someday_maybe_review.py
git commit -m "feat: add someday_maybe_review for backburner triage"
```

---

## Task 8: Create Calendar Review Scaffold

**Files:**
- Create: `src/rubber_duck/integrations/tools/calendar_review.py`

**Step 1: Write the placeholder implementation**

```python
# src/rubber_duck/integrations/tools/calendar_review.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Calendar review sub-review for weekly review.

NOTE: This is a scaffold. Calendar integration is not yet implemented.
See rubber-duck-gaz for GCal integration work.
"""


def run_calendar_review() -> str:
    """Review calendar for task creation opportunities.

    NOTE: Calendar integration not yet configured.

    When implemented, will:
    - Check past week for tasks to create from events
    - Check upcoming week for preparation needs
    - Identify scheduling conflicts

    Returns:
        Placeholder message until calendar is integrated
    """
    return """## Calendar Review

*Calendar integration not yet configured.*

When ready, this will:
- Check past week's events for follow-up tasks
- Check upcoming week for preparation needs
- Identify potential scheduling conflicts

**For now:** Manually review your calendar and note any tasks to add.

See rubber-duck-gaz for calendar integration status.

---
**Status:** Scaffolded (pending GCal integration)"""
```

**Step 2: Verify module imports**

Run: `cd /workspaces/rubber-duck && python -c "from rubber_duck.integrations.tools.calendar_review import run_calendar_review; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/rubber_duck/integrations/tools/calendar_review.py
git commit -m "feat: add calendar_review scaffold (pending GCal integration)"
```

---

## Task 9: Register Tools with Agent

**Files:**
- Modify: `src/rubber_duck/agent/tools.py`

**Step 1: Add imports and schemas**

Add to imports section:
```python
from rubber_duck.integrations.tools.weekly_conductor import weekly_review_conductor
from rubber_duck.integrations.tools.calendar_review import run_calendar_review
from rubber_duck.integrations.tools.deadline_scan import run_deadline_scan
from rubber_duck.integrations.tools.waiting_for_review import run_waiting_for_review
from rubber_duck.integrations.tools.project_review import run_project_review
from rubber_duck.integrations.tools.category_health import run_category_health
from rubber_duck.integrations.tools.someday_maybe_review import run_someday_maybe_review
```

Add to TOOL_SCHEMAS list:
```python
{
    "name": "weekly_review_conductor",
    "description": "Manage weekly review session. Actions: 'start' (begin review), 'status' (current step), 'next' (advance), 'complete' (end), 'abandon' (cancel).",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform: start, status, next, complete, abandon"
            }
        },
        "required": ["action"]
    }
},
{
    "name": "run_calendar_review",
    "description": "Weekly review step 1: Check calendar for tasks to create from events. (Currently scaffolded - calendar integration pending)",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
},
{
    "name": "run_deadline_scan",
    "description": "Weekly review step 2: Scan tasks with due dates, group by urgency (overdue, this week, next week).",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
},
{
    "name": "run_waiting_for_review",
    "description": "Weekly review step 3: Review waiting-for items with follow-up timing recommendations.",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
},
{
    "name": "run_project_review",
    "description": "Weekly review step 4: Assess project health (ACTIVE/STALLED/WAITING/INCOMPLETE).",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
},
{
    "name": "run_category_health",
    "description": "Weekly review step 5: Analyze task distribution across projects, identify overloaded/neglected areas.",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
},
{
    "name": "run_someday_maybe_review",
    "description": "Weekly review step 6: Triage backburner items (delete, review, or keep).",
    "input_schema": {
        "type": "object",
        "properties": {}
    }
},
```

Add to TOOL_FUNCTIONS dict:
```python
"weekly_review_conductor": lambda action: weekly_review_conductor(action),
"run_calendar_review": lambda: run_calendar_review(),
"run_deadline_scan": lambda: run_deadline_scan(),
"run_waiting_for_review": lambda: run_waiting_for_review(),
"run_project_review": lambda: run_project_review(),
"run_category_health": lambda: run_category_health(),
"run_someday_maybe_review": lambda: run_someday_maybe_review(),
```

**Step 2: Verify tools load correctly**

Run: `cd /workspaces/rubber-duck && python -c "from rubber_duck.agent.tools import TOOL_SCHEMAS, TOOL_FUNCTIONS; print(f'{len(TOOL_SCHEMAS)} schemas, {len(TOOL_FUNCTIONS)} functions'); assert 'weekly_review_conductor' in TOOL_FUNCTIONS; print('OK')"`
Expected: Shows counts and `OK`

**Step 3: Commit**

```bash
git add src/rubber_duck/agent/tools.py
git commit -m "feat: register weekly review tools with agent"
```

---

## Task 10: Update System Prompt

**Files:**
- Modify: `src/rubber_duck/agent/loop.py`

**Step 1: Add weekly review guidance to system prompt**

In `_build_system_prompt()`, add after the existing tool guidance section:

```python
## Weekly Review Sessions

When the user wants to do a weekly review, use the weekly_review_conductor to manage the session:

1. Call `weekly_review_conductor("start")` to begin
2. Follow the conductor's guidance - it tells you which tool to call next
3. After each sub-review, discuss the results with the user
4. When user is ready (says "next", "continue", etc.), call `weekly_review_conductor("next")`
5. Handle user requests between steps (add tasks, answer questions) naturally
6. The conductor tracks progress - just follow its instructions
```

**Step 2: Verify prompt builds correctly**

Run: `cd /workspaces/rubber-duck && python -c "from rubber_duck.agent.loop import _build_system_prompt; p = _build_system_prompt({}); assert 'weekly_review_conductor' in p; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/rubber_duck/agent/loop.py
git commit -m "feat: add weekly review guidance to system prompt"
```

---

## Task 11: Integration Test

**Files:**
- None (manual verification)

**Step 1: Test conductor flow**

Run:
```bash
cd /workspaces/rubber-duck && python -c "
from rubber_duck.integrations.tools.weekly_conductor import weekly_review_conductor, _clear_session

# Clean start
_clear_session()

# Test flow
print('=== START ===')
print(weekly_review_conductor('start'))
print()
print('=== NEXT ===')
print(weekly_review_conductor('next'))
print()
print('=== STATUS ===')
print(weekly_review_conductor('status'))
print()
print('=== ABANDON ===')
print(weekly_review_conductor('abandon'))
"
```

Expected: Shows step progression through the review

**Step 2: Test a sub-review (requires Todoist API key)**

Run:
```bash
cd /workspaces/rubber-duck && python -c "
from rubber_duck.integrations.tools.deadline_scan import run_deadline_scan
print(run_deadline_scan())
"
```

Expected: Either deadline scan output OR "Todoist is not configured" message

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete weekly review redesign implementation

- Added weekly_review_conductor for session management
- Added 6 sub-review tools (calendar, deadline, waiting-for, project, category, someday-maybe)
- Extracted shared utilities to weekly_utils.py
- Registered all tools with agent
- Added system prompt guidance

See docs/plans/2026-01-02-weekly-review-redesign.md for design.
Closes rubber-duck-qx1."
```
