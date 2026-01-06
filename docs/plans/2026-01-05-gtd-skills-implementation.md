# GTD Skills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert Python GTD workflows to Claude Code skills backed by JSON-returning CLI tools.

**Architecture:** Skills (markdown) guide procedure and judgment; CLI tools (Python) handle computation and return JSON. Bot invokes skills via Claude Code rather than calling Python directly.

**Tech Stack:** Python CLI with Click, existing Todoist/GCal integrations, Claude Code skills (markdown with YAML frontmatter)

---

## Phase 1: CLI Tools Module

### Task 1: Create GTD Module Structure

**Files:**
- Create: `src/rubber_duck/gtd/__init__.py`
- Create: `src/rubber_duck/gtd/deadlines.py`
- Create: `src/rubber_duck/gtd/projects.py`
- Create: `src/rubber_duck/gtd/waiting.py`
- Create: `src/rubber_duck/gtd/someday.py`
- Create: `src/rubber_duck/gtd/calendar.py`
- Create: `src/rubber_duck/cli/gtd.py`
- Create: `tests/test_gtd_deadlines.py`

**Step 1: Create module directory and __init__.py**

```bash
mkdir -p src/rubber_duck/gtd
```

```python
# src/rubber_duck/gtd/__init__.py
"""GTD workflow computation modules.

These modules return structured dicts for CLI consumption.
Skills handle presentation and judgment.
"""
```

**Step 2: Create empty module files**

```python
# src/rubber_duck/gtd/deadlines.py
"""Deadline scanning for GTD workflows."""


def scan_deadlines() -> dict:
    """Scan tasks for deadline urgency.

    Returns dict with keys: overdue, due_today, due_this_week, summary
    """
    raise NotImplementedError
```

```python
# src/rubber_duck/gtd/projects.py
"""Project health checking for GTD workflows."""


def check_projects() -> dict:
    """Check project health status.

    Returns dict with keys: active, stalled, waiting, incomplete, summary
    """
    raise NotImplementedError
```

```python
# src/rubber_duck/gtd/waiting.py
"""Waiting-for tracking for GTD workflows."""


def check_waiting() -> dict:
    """Check waiting-for items and staleness.

    Returns dict with keys: needs_followup, gentle_check, still_fresh, summary
    """
    raise NotImplementedError
```

```python
# src/rubber_duck/gtd/someday.py
"""Someday-maybe triage for GTD workflows."""


def check_someday() -> dict:
    """Triage someday-maybe items by age.

    Returns dict with keys: consider_deleting, needs_decision, keep, summary
    """
    raise NotImplementedError
```

```python
# src/rubber_duck/gtd/calendar.py
"""Calendar integration for GTD workflows."""


def calendar_today() -> dict:
    """Get today's calendar events.

    Returns dict with keys: events, all_day, summary
    """
    raise NotImplementedError


def calendar_range(days_back: int = 0, days_forward: int = 7) -> dict:
    """Get calendar events in a date range.

    Returns dict with keys: events, all_day, summary
    """
    raise NotImplementedError
```

**Step 3: Commit structure**

```bash
git add src/rubber_duck/gtd/
git commit -m "feat(gtd): create module structure for GTD CLI tools"
```

---

### Task 2: Implement scan_deadlines

**Files:**
- Modify: `src/rubber_duck/gtd/deadlines.py`
- Create: `tests/test_gtd_deadlines.py`

**Step 1: Write the failing test**

```python
# tests/test_gtd_deadlines.py
"""Tests for GTD deadline scanning."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from rubber_duck.gtd.deadlines import scan_deadlines, _categorize_by_urgency


class TestCategorizeByUrgency:
    """Test task categorization by deadline urgency."""

    def test_overdue_task(self):
        """Task with past due date is categorized as overdue."""
        today = date(2026, 1, 5)
        task = {
            "id": "123",
            "content": "Overdue task",
            "due": {"date": "2026-01-03"},
            "project_id": "proj1",
        }

        result = _categorize_by_urgency([task], today)

        assert len(result["overdue"]) == 1
        assert result["overdue"][0]["id"] == "123"
        assert result["overdue"][0]["days_overdue"] == 2

    def test_due_today_task(self):
        """Task due today is categorized correctly."""
        today = date(2026, 1, 5)
        task = {
            "id": "456",
            "content": "Due today",
            "due": {"date": "2026-01-05"},
            "project_id": "proj1",
        }

        result = _categorize_by_urgency([task], today)

        assert len(result["due_today"]) == 1
        assert result["due_today"][0]["id"] == "456"

    def test_due_this_week_task(self):
        """Task due within 7 days is categorized as due_this_week."""
        today = date(2026, 1, 5)
        task = {
            "id": "789",
            "content": "Due this week",
            "due": {"date": "2026-01-08"},
            "project_id": "proj1",
        }

        result = _categorize_by_urgency([task], today)

        assert len(result["due_this_week"]) == 1
        assert result["due_this_week"][0]["days_until"] == 3

    def test_task_with_no_due_date_excluded(self):
        """Task without due date is not included in any category."""
        today = date(2026, 1, 5)
        task = {
            "id": "999",
            "content": "No due date",
            "due": None,
            "project_id": "proj1",
        }

        result = _categorize_by_urgency([task], today)

        assert len(result["overdue"]) == 0
        assert len(result["due_today"]) == 0
        assert len(result["due_this_week"]) == 0

    def test_summary_counts(self):
        """Summary contains correct counts."""
        today = date(2026, 1, 5)
        tasks = [
            {"id": "1", "content": "Overdue", "due": {"date": "2026-01-01"}, "project_id": "p"},
            {"id": "2", "content": "Today", "due": {"date": "2026-01-05"}, "project_id": "p"},
            {"id": "3", "content": "This week", "due": {"date": "2026-01-10"}, "project_id": "p"},
        ]

        result = _categorize_by_urgency(tasks, today)

        assert result["summary"]["overdue"] == 1
        assert result["summary"]["due_today"] == 1
        assert result["summary"]["due_this_week"] == 1
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_gtd_deadlines.py -v
```

Expected: FAIL with `ImportError` (function not defined)

**Step 3: Write minimal implementation**

```python
# src/rubber_duck/gtd/deadlines.py
"""Deadline scanning for GTD workflows."""

from datetime import date, datetime


def _categorize_by_urgency(tasks: list, today: date) -> dict:
    """Categorize tasks by deadline urgency.

    Args:
        tasks: List of task dicts with 'id', 'content', 'due', 'project_id'
        today: Reference date for calculations

    Returns:
        Dict with overdue, due_today, due_this_week lists and summary
    """
    overdue = []
    due_today = []
    due_this_week = []

    for task in tasks:
        due = task.get("due")
        if not due or not due.get("date"):
            continue

        due_date_str = due["date"][:10]
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        days_diff = (due_date - today).days

        base_info = {
            "id": task["id"],
            "content": task["content"],
            "project": task.get("project_id", ""),
        }

        if days_diff < 0:
            overdue.append({
                **base_info,
                "days_overdue": abs(days_diff),
            })
        elif days_diff == 0:
            has_time = "datetime" in due
            due_today.append({
                **base_info,
                "has_time": has_time,
                "time": due.get("datetime", "")[-5:] if has_time else None,
            })
        elif days_diff <= 7:
            due_this_week.append({
                **base_info,
                "due_date": due_date_str,
                "days_until": days_diff,
            })

    # Sort by urgency
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)
    due_this_week.sort(key=lambda x: x["days_until"])

    return {
        "overdue": overdue,
        "due_today": due_today,
        "due_this_week": due_this_week,
        "summary": {
            "overdue": len(overdue),
            "due_today": len(due_today),
            "due_this_week": len(due_this_week),
        },
    }
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_gtd_deadlines.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/rubber_duck/gtd/deadlines.py tests/test_gtd_deadlines.py
git commit -m "feat(gtd): implement deadline categorization by urgency"
```

---

### Task 3: Implement scan_deadlines with Todoist integration

**Files:**
- Modify: `src/rubber_duck/gtd/deadlines.py`
- Modify: `tests/test_gtd_deadlines.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_gtd_deadlines.py

class TestScanDeadlines:
    """Test the main scan_deadlines function."""

    @patch("rubber_duck.gtd.deadlines._fetch_tasks")
    @patch("rubber_duck.gtd.deadlines._fetch_projects")
    def test_scan_deadlines_returns_structured_output(self, mock_projects, mock_tasks):
        """scan_deadlines returns properly structured dict."""
        mock_tasks.return_value = [
            {"id": "1", "content": "Task", "due": {"date": "2026-01-03"}, "project_id": "p1"},
        ]
        mock_projects.return_value = {"p1": "Work"}

        result = scan_deadlines()

        assert "generated_at" in result
        assert "overdue" in result
        assert "due_today" in result
        assert "due_this_week" in result
        assert "summary" in result
        # Project name should be resolved
        assert result["overdue"][0]["project"] == "Work"

    @patch("rubber_duck.gtd.deadlines._fetch_tasks")
    @patch("rubber_duck.gtd.deadlines._fetch_projects")
    def test_scan_deadlines_empty_when_no_tasks(self, mock_projects, mock_tasks):
        """scan_deadlines handles empty task list."""
        mock_tasks.return_value = []
        mock_projects.return_value = {}

        result = scan_deadlines()

        assert result["overdue"] == []
        assert result["summary"]["overdue"] == 0
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_gtd_deadlines.py::TestScanDeadlines -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
# Add to src/rubber_duck/gtd/deadlines.py
import os
from datetime import date, datetime, timezone

import requests


def _fetch_tasks() -> list:
    """Fetch all tasks from Todoist."""
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return []

    response = requests.get(
        "https://api.todoist.com/rest/v2/tasks",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_projects() -> dict:
    """Fetch projects and return id->name mapping."""
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return {}

    response = requests.get(
        "https://api.todoist.com/rest/v2/projects",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return {p["id"]: p["name"] for p in response.json()}


def scan_deadlines() -> dict:
    """Scan tasks for deadline urgency.

    Returns:
        Dict with overdue, due_today, due_this_week lists and summary.
        Each task includes: id, content, project (name), and urgency-specific fields.
    """
    tasks = _fetch_tasks()
    projects = _fetch_projects()
    today = date.today()

    result = _categorize_by_urgency(tasks, today)

    # Resolve project IDs to names
    for category in ["overdue", "due_today", "due_this_week"]:
        for item in result[category]:
            item["project"] = projects.get(item["project"], item["project"])

    result["generated_at"] = datetime.now(timezone.utc).isoformat()

    return result
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_gtd_deadlines.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/rubber_duck/gtd/deadlines.py tests/test_gtd_deadlines.py
git commit -m "feat(gtd): implement scan_deadlines with Todoist integration"
```

---

### Task 4: Implement check_waiting

**Files:**
- Modify: `src/rubber_duck/gtd/waiting.py`
- Create: `tests/test_gtd_waiting.py`

**Step 1: Write the failing test**

```python
# tests/test_gtd_waiting.py
"""Tests for GTD waiting-for tracking."""

from datetime import date
from unittest.mock import patch

import pytest

from rubber_duck.gtd.waiting import check_waiting, _categorize_waiting, WAITING_LABELS


class TestCategorizeWaiting:
    """Test waiting-for categorization."""

    def test_fresh_waiting_item(self):
        """Item waiting < 4 days is still_fresh."""
        today = date(2026, 1, 5)
        task = {
            "id": "1",
            "content": "Waiting on Bob",
            "labels": ["waiting"],
            "created_at": "2026-01-03T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_waiting([task], today)

        assert len(result["still_fresh"]) == 1
        assert result["still_fresh"][0]["days_waiting"] == 2

    def test_gentle_check_item(self):
        """Item waiting 4-7 days needs gentle check."""
        today = date(2026, 1, 10)
        task = {
            "id": "2",
            "content": "Waiting on vendor",
            "labels": ["waiting-for"],
            "created_at": "2026-01-04T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_waiting([task], today)

        assert len(result["gentle_check"]) == 1
        assert result["gentle_check"][0]["urgency"] == "gentle"

    def test_needs_followup_item(self):
        """Item waiting > 7 days needs followup."""
        today = date(2026, 1, 20)
        task = {
            "id": "3",
            "content": "Waiting on specs",
            "labels": ["waiting"],
            "created_at": "2026-01-05T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_waiting([task], today)

        assert len(result["needs_followup"]) == 1
        assert "suggested_action" in result["needs_followup"][0]

    def test_non_waiting_task_excluded(self):
        """Task without waiting label is excluded."""
        today = date(2026, 1, 5)
        task = {
            "id": "4",
            "content": "Regular task",
            "labels": ["work"],
            "created_at": "2026-01-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_waiting([task], today)

        assert result["summary"]["total"] == 0
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_gtd_waiting.py -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
# src/rubber_duck/gtd/waiting.py
"""Waiting-for tracking for GTD workflows."""

import os
from datetime import date, datetime, timezone

import requests

WAITING_LABELS = {"waiting", "waiting-for", "waiting for"}


def _get_staleness_category(days: int) -> tuple[str, str, str]:
    """Get category, urgency, and suggested action based on days waiting.

    Returns: (category, urgency, suggested_action)
    """
    if days < 4:
        return ("still_fresh", "fresh", "Still within normal response time.")
    elif days < 8:
        return ("gentle_check", "gentle",
                "Just checking in on this. No rush, wanted to ensure it's on your radar.")
    elif days < 15:
        return ("needs_followup", "firm",
                f"Following up on this from {days} days ago. Could you provide a status update?")
    elif days < 22:
        return ("needs_followup", "urgent",
                f"This has been pending for {days} days. Need a firm timeline or explore alternatives.")
    else:
        return ("needs_followup", "escalate",
                f"Waiting {days} days. May need to escalate or find workaround.")


def _categorize_waiting(tasks: list, today: date) -> dict:
    """Categorize waiting-for items by staleness."""
    needs_followup = []
    gentle_check = []
    still_fresh = []

    for task in tasks:
        labels = {label.lower() for label in task.get("labels", [])}
        if not labels & WAITING_LABELS:
            continue

        created = task.get("created_at")
        if not created:
            days = 0
        else:
            try:
                created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
                days = (today - created_date).days
            except (ValueError, AttributeError):
                days = 0

        category, urgency, suggested = _get_staleness_category(days)

        item = {
            "id": task["id"],
            "content": task["content"],
            "days_waiting": days,
            "urgency": urgency,
            "suggested_action": suggested,
            "project": task.get("project_id", ""),
        }

        if category == "needs_followup":
            needs_followup.append(item)
        elif category == "gentle_check":
            gentle_check.append(item)
        else:
            still_fresh.append(item)

    # Sort by days waiting (oldest first)
    needs_followup.sort(key=lambda x: x["days_waiting"], reverse=True)
    gentle_check.sort(key=lambda x: x["days_waiting"], reverse=True)

    total = len(needs_followup) + len(gentle_check) + len(still_fresh)

    return {
        "needs_followup": needs_followup,
        "gentle_check": gentle_check,
        "still_fresh": still_fresh,
        "summary": {
            "total": total,
            "needs_followup": len(needs_followup),
        },
    }


def _fetch_tasks() -> list:
    """Fetch all tasks from Todoist."""
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return []

    response = requests.get(
        "https://api.todoist.com/rest/v2/tasks",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_projects() -> dict:
    """Fetch projects and return id->name mapping."""
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return {}

    response = requests.get(
        "https://api.todoist.com/rest/v2/projects",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return {p["id"]: p["name"] for p in response.json()}


def check_waiting() -> dict:
    """Check waiting-for items and staleness.

    Returns:
        Dict with needs_followup, gentle_check, still_fresh lists and summary.
    """
    tasks = _fetch_tasks()
    projects = _fetch_projects()
    today = date.today()

    result = _categorize_waiting(tasks, today)

    # Resolve project IDs to names
    for category in ["needs_followup", "gentle_check", "still_fresh"]:
        for item in result[category]:
            item["project"] = projects.get(item["project"], item["project"])

    result["generated_at"] = datetime.now(timezone.utc).isoformat()

    return result
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_gtd_waiting.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/rubber_duck/gtd/waiting.py tests/test_gtd_waiting.py
git commit -m "feat(gtd): implement check_waiting with staleness tracking"
```

---

### Task 5: Implement check_someday

**Files:**
- Modify: `src/rubber_duck/gtd/someday.py`
- Create: `tests/test_gtd_someday.py`

**Step 1: Write the failing test**

```python
# tests/test_gtd_someday.py
"""Tests for GTD someday-maybe triage."""

from datetime import date
from unittest.mock import patch

import pytest

from rubber_duck.gtd.someday import check_someday, _categorize_someday, BACKBURNER_LABELS


class TestCategorizeSomeday:
    """Test someday-maybe categorization by age."""

    def test_old_item_consider_deleting(self):
        """Item > 365 days old should be considered for deletion."""
        today = date(2026, 1, 5)
        task = {
            "id": "1",
            "content": "Learn Esperanto",
            "labels": ["someday-maybe"],
            "created_at": "2024-06-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_someday([task], today, {})

        assert len(result["consider_deleting"]) == 1
        assert result["consider_deleting"][0]["days_old"] > 365

    def test_medium_age_needs_decision(self):
        """Item 180-365 days old needs decision."""
        today = date(2026, 1, 5)
        task = {
            "id": "2",
            "content": "Build a shed",
            "labels": ["maybe"],
            "created_at": "2025-07-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_someday([task], today, {})

        assert len(result["needs_decision"]) == 1

    def test_recent_item_keep(self):
        """Item < 180 days old should be kept."""
        today = date(2026, 1, 5)
        task = {
            "id": "3",
            "content": "Try pottery",
            "labels": ["someday"],
            "created_at": "2025-10-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_someday([task], today, {})

        assert len(result["keep"]) == 1

    def test_non_backburner_excluded(self):
        """Task without backburner label is excluded."""
        today = date(2026, 1, 5)
        task = {
            "id": "4",
            "content": "Active task",
            "labels": ["work"],
            "created_at": "2024-01-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_someday([task], today, {})

        assert result["summary"]["total"] == 0
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_gtd_someday.py -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
# src/rubber_duck/gtd/someday.py
"""Someday-maybe triage for GTD workflows."""

import os
from datetime import date, datetime, timezone

import requests

BACKBURNER_LABELS = {"someday-maybe", "maybe", "someday", "later", "backburner"}
SOMEDAY_PROJECT_NAMES = {"someday-maybe", "someday maybe", "someday/maybe", "someday"}


def _get_age_category(days: int) -> str:
    """Get triage category based on age in days."""
    if days > 365:
        return "consider_deleting"
    elif days > 180:
        return "needs_decision"
    else:
        return "keep"


def _is_backburner(task: dict, proj_by_id: dict) -> bool:
    """Check if task is in backburner (by label or project)."""
    labels = {label.lower() for label in task.get("labels", [])}
    if labels & BACKBURNER_LABELS:
        return True

    # Check project hierarchy
    project_id = task.get("project_id")
    while project_id:
        proj = proj_by_id.get(project_id, {})
        if proj.get("name", "").lower().strip() in SOMEDAY_PROJECT_NAMES:
            return True
        project_id = proj.get("parent_id")

    return False


def _categorize_someday(tasks: list, today: date, proj_by_id: dict) -> dict:
    """Categorize someday-maybe items by age."""
    consider_deleting = []
    needs_decision = []
    keep = []

    for task in tasks:
        if not _is_backburner(task, proj_by_id):
            continue

        created = task.get("created_at")
        if not created:
            days = 0
        else:
            try:
                created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
                days = (today - created_date).days
            except (ValueError, AttributeError):
                days = 0

        category = _get_age_category(days)

        item = {
            "id": task["id"],
            "content": task["content"],
            "days_old": days,
            "project": task.get("project_id", ""),
        }

        if category == "consider_deleting":
            consider_deleting.append(item)
        elif category == "needs_decision":
            needs_decision.append(item)
        else:
            keep.append(item)

    # Sort by age (oldest first)
    consider_deleting.sort(key=lambda x: x["days_old"], reverse=True)
    needs_decision.sort(key=lambda x: x["days_old"], reverse=True)
    keep.sort(key=lambda x: x["days_old"], reverse=True)

    total = len(consider_deleting) + len(needs_decision) + len(keep)

    return {
        "consider_deleting": consider_deleting,
        "needs_decision": needs_decision,
        "keep": keep,
        "summary": {
            "total": total,
            "consider_deleting": len(consider_deleting),
            "needs_decision": len(needs_decision),
        },
    }


def _fetch_tasks() -> list:
    """Fetch all tasks from Todoist."""
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return []

    response = requests.get(
        "https://api.todoist.com/rest/v2/tasks",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_projects() -> list:
    """Fetch all projects from Todoist."""
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return []

    response = requests.get(
        "https://api.todoist.com/rest/v2/projects",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def check_someday() -> dict:
    """Triage someday-maybe items by age.

    Returns:
        Dict with consider_deleting, needs_decision, keep lists and summary.
    """
    tasks = _fetch_tasks()
    projects = _fetch_projects()
    proj_by_id = {p["id"]: p for p in projects}
    proj_names = {p["id"]: p["name"] for p in projects}
    today = date.today()

    result = _categorize_someday(tasks, today, proj_by_id)

    # Resolve project IDs to names
    for category in ["consider_deleting", "needs_decision", "keep"]:
        for item in result[category]:
            item["project"] = proj_names.get(item["project"], item["project"])

    result["generated_at"] = datetime.now(timezone.utc).isoformat()

    return result
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_gtd_someday.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/rubber_duck/gtd/someday.py tests/test_gtd_someday.py
git commit -m "feat(gtd): implement check_someday with age-based triage"
```

---

### Task 6: Implement check_projects

**Files:**
- Modify: `src/rubber_duck/gtd/projects.py`
- Create: `tests/test_gtd_projects.py`

**Step 1: Write the failing test**

```python
# tests/test_gtd_projects.py
"""Tests for GTD project health checking."""

from datetime import date
from unittest.mock import patch

import pytest

from rubber_duck.gtd.projects import check_projects, _compute_project_health


class TestComputeProjectHealth:
    """Test project health computation."""

    def test_active_project(self):
        """Project with recent completions is active."""
        proj_tasks = [{"id": "1", "content": "Task", "labels": []}]
        completions = [{"task_id": "2"}]  # completed task

        status = _compute_project_health(proj_tasks, completions)

        assert status == "active"

    def test_stalled_project(self):
        """Project with tasks but no completions is stalled."""
        proj_tasks = [{"id": "1", "content": "Task", "labels": []}]
        completions = []

        status = _compute_project_health(proj_tasks, completions)

        assert status == "stalled"

    def test_waiting_project(self):
        """Project with only waiting tasks is waiting."""
        proj_tasks = [{"id": "1", "content": "Task", "labels": ["waiting"]}]
        completions = []

        status = _compute_project_health(proj_tasks, completions)

        assert status == "waiting"

    def test_incomplete_project(self):
        """Project with no actionable tasks is incomplete."""
        proj_tasks = []  # No tasks
        completions = []

        status = _compute_project_health(proj_tasks, completions)

        assert status == "incomplete"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_gtd_projects.py -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
# src/rubber_duck/gtd/projects.py
"""Project health checking for GTD workflows."""

import os
from datetime import date, datetime, timedelta, timezone

import requests

BACKBURNER_LABELS = {"someday-maybe", "maybe", "someday", "later", "backburner"}
WAITING_LABELS = {"waiting", "waiting-for", "waiting for"}


def _compute_project_health(tasks: list, completions: list) -> str:
    """Compute project health status.

    Returns: "active", "stalled", "waiting", or "incomplete"
    """
    if completions:
        return "active"

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
        return "incomplete"
    if not next_actions and waiting_actions:
        return "waiting"
    return "stalled"


def _get_next_action(tasks: list) -> dict | None:
    """Get highest priority actionable task from project."""
    actionable = [
        t for t in tasks
        if not ({label.lower() for label in t.get("labels", [])}
                & (BACKBURNER_LABELS | WAITING_LABELS))
    ]
    if not actionable:
        return None

    # Prefer prioritized tasks
    prioritized = [t for t in actionable if t.get("priority", 4) < 4]
    if prioritized:
        return min(prioritized, key=lambda t: t.get("priority", 4))
    return actionable[0]


def _fetch_tasks() -> list:
    """Fetch all tasks from Todoist."""
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return []

    response = requests.get(
        "https://api.todoist.com/rest/v2/tasks",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_projects() -> list:
    """Fetch all projects from Todoist."""
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return []

    response = requests.get(
        "https://api.todoist.com/rest/v2/projects",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_completed_tasks(days: int = 7) -> list:
    """Fetch completed tasks from last N days."""
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return []

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    response = requests.post(
        "https://api.todoist.com/sync/v9/completed/get_all",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"since": since, "limit": 200},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("items", [])


def _group_by_project(items: list, key: str = "project_id") -> dict:
    """Group items by project ID."""
    grouped = {}
    for item in items:
        pid = item.get(key)
        if pid not in grouped:
            grouped[pid] = []
        grouped[pid].append(item)
    return grouped


def check_projects() -> dict:
    """Check project health status.

    Returns:
        Dict with active, stalled, waiting, incomplete lists and summary.
    """
    tasks = _fetch_tasks()
    projects = _fetch_projects()
    completed = _fetch_completed_tasks(days=7)

    proj_by_id = {p["id"]: p for p in projects}
    tasks_by_project = _group_by_project(tasks)
    completions_by_project = _group_by_project(completed)

    active = []
    stalled = []
    waiting = []
    incomplete = []

    for proj in projects:
        pid = proj["id"]
        proj_tasks = tasks_by_project.get(pid, [])
        proj_completions = completions_by_project.get(pid, [])

        # Skip empty projects
        if not proj_tasks and not proj_completions:
            continue

        status = _compute_project_health(proj_tasks, proj_completions)

        info = {
            "name": proj["name"],
            "open_tasks": len(proj_tasks),
        }

        if status == "active":
            info["completed_this_week"] = len(proj_completions)
            active.append(info)
        elif status == "stalled":
            next_action = _get_next_action(proj_tasks)
            if next_action:
                info["next_action"] = {
                    "id": next_action["id"],
                    "content": next_action["content"],
                }
            info["days_since_activity"] = 7  # At least 7 since no completions
            stalled.append(info)
        elif status == "waiting":
            info["waiting_tasks"] = len(proj_tasks)
            waiting.append(info)
        else:
            info["reason"] = "no next action defined"
            incomplete.append(info)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active": active,
        "stalled": stalled,
        "waiting": waiting,
        "incomplete": incomplete,
        "summary": {
            "active": len(active),
            "stalled": len(stalled),
            "waiting": len(waiting),
            "incomplete": len(incomplete),
        },
    }
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_gtd_projects.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/rubber_duck/gtd/projects.py tests/test_gtd_projects.py
git commit -m "feat(gtd): implement check_projects with health status"
```

---

### Task 7: Implement calendar functions

**Files:**
- Modify: `src/rubber_duck/gtd/calendar.py`
- Create: `tests/test_gtd_calendar.py`

**Step 1: Write the failing test**

```python
# tests/test_gtd_calendar.py
"""Tests for GTD calendar integration."""

from datetime import date, datetime
from unittest.mock import patch, MagicMock

import pytest

from rubber_duck.gtd.calendar import calendar_today, calendar_range, _format_events


class TestFormatEvents:
    """Test event formatting."""

    def test_timed_event(self):
        """Timed event is formatted correctly."""
        events = [{
            "summary": "Meeting",
            "start": {"dateTime": "2026-01-05T14:00:00Z"},
            "end": {"dateTime": "2026-01-05T15:00:00Z"},
            "location": "Room 101",
        }]

        result = _format_events(events)

        assert len(result["events"]) == 1
        assert result["events"][0]["summary"] == "Meeting"
        assert result["events"][0]["start"] == "14:00"
        assert result["events"][0]["location"] == "Room 101"

    def test_all_day_event(self):
        """All-day event is categorized separately."""
        events = [{
            "summary": "Holiday",
            "start": {"date": "2026-01-05"},
            "end": {"date": "2026-01-06"},
        }]

        result = _format_events(events)

        assert len(result["all_day"]) == 1
        assert result["all_day"][0]["summary"] == "Holiday"

    def test_summary_counts(self):
        """Summary has correct counts."""
        events = [
            {"summary": "Meeting", "start": {"dateTime": "2026-01-05T14:00:00Z"}, "end": {"dateTime": "2026-01-05T15:00:00Z"}},
            {"summary": "Holiday", "start": {"date": "2026-01-05"}, "end": {"date": "2026-01-06"}},
        ]

        result = _format_events(events)

        assert result["summary"]["timed_events"] == 1
        assert result["summary"]["all_day"] == 1
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_gtd_calendar.py -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
# src/rubber_duck/gtd/calendar.py
"""Calendar integration for GTD workflows."""

import base64
import json
import os
from datetime import datetime, timedelta, timezone


def _get_calendar_service():
    """Get Google Calendar service if configured."""
    gcal_creds = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not gcal_creds:
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        json_str = base64.b64decode(gcal_creds).decode("utf-8")
        info = json.loads(json_str)
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        return build("calendar", "v3", credentials=credentials)
    except Exception:
        return None


def _format_events(events: list) -> dict:
    """Format calendar events into structured output."""
    timed = []
    all_day = []

    for event in events:
        start = event.get("start", {})
        end = event.get("end", {})

        is_all_day = "date" in start and "dateTime" not in start

        if is_all_day:
            all_day.append({
                "summary": event.get("summary", "(No title)"),
            })
        else:
            start_dt = start.get("dateTime", "")
            end_dt = end.get("dateTime", "")

            # Extract time portion
            start_time = ""
            end_time = ""
            if start_dt:
                try:
                    dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
                    start_time = dt.strftime("%H:%M")
                except ValueError:
                    start_time = start_dt
            if end_dt:
                try:
                    dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
                    end_time = dt.strftime("%H:%M")
                except ValueError:
                    end_time = end_dt

            timed.append({
                "summary": event.get("summary", "(No title)"),
                "start": start_time,
                "end": end_time,
                "location": event.get("location"),
            })

    return {
        "events": timed,
        "all_day": all_day,
        "summary": {
            "timed_events": len(timed),
            "all_day": len(all_day),
        },
    }


def _fetch_events(time_min: datetime, time_max: datetime) -> list:
    """Fetch events in date range from Google Calendar."""
    service = _get_calendar_service()
    if not service:
        return []

    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min.strftime("%Y-%m-%dT%H:%M:%SZ"),
            timeMax=time_max.strftime("%Y-%m-%dT%H:%M:%SZ"),
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        return events_result.get("items", [])
    except Exception:
        return []


def calendar_today() -> dict:
    """Get today's calendar events.

    Returns:
        Dict with events, all_day lists and summary.
    """
    now = datetime.now(timezone.utc)
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = now.replace(hour=23, minute=59, second=59, microsecond=0)

    events = _fetch_events(time_min, time_max)
    result = _format_events(events)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()

    return result


def calendar_range(days_back: int = 0, days_forward: int = 7) -> dict:
    """Get calendar events in a date range.

    Args:
        days_back: Number of days in the past to include
        days_forward: Number of days in the future to include

    Returns:
        Dict with events, all_day lists and summary.
    """
    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = (now + timedelta(days=days_forward)).replace(hour=23, minute=59, second=59, microsecond=0)

    events = _fetch_events(time_min, time_max)
    result = _format_events(events)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["range"] = {
        "from": time_min.strftime("%Y-%m-%d"),
        "to": time_max.strftime("%Y-%m-%d"),
    }

    return result
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_gtd_calendar.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/rubber_duck/gtd/calendar.py tests/test_gtd_calendar.py
git commit -m "feat(gtd): implement calendar functions"
```

---

### Task 8: Create CLI entry point

**Files:**
- Create: `src/rubber_duck/cli/gtd.py`
- Modify: `src/rubber_duck/cli/__init__.py` (if exists)

**Step 1: Write the CLI module**

```python
# src/rubber_duck/cli/gtd.py
"""GTD CLI commands for skill consumption.

All commands output JSON for Claude Code skills to interpret.
"""

import json
import sys

import click


@click.group()
def gtd():
    """GTD workflow commands."""
    pass


@gtd.command("scan-deadlines")
def scan_deadlines_cmd():
    """Scan tasks for deadline urgency."""
    from rubber_duck.gtd.deadlines import scan_deadlines

    try:
        result = scan_deadlines()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("check-projects")
def check_projects_cmd():
    """Check project health status."""
    from rubber_duck.gtd.projects import check_projects

    try:
        result = check_projects()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("check-waiting")
def check_waiting_cmd():
    """Check waiting-for items and staleness."""
    from rubber_duck.gtd.waiting import check_waiting

    try:
        result = check_waiting()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("check-someday")
def check_someday_cmd():
    """Triage someday-maybe items by age."""
    from rubber_duck.gtd.someday import check_someday

    try:
        result = check_someday()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("calendar-today")
def calendar_today_cmd():
    """Get today's calendar events."""
    from rubber_duck.gtd.calendar import calendar_today

    try:
        result = calendar_today()
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


@gtd.command("calendar-range")
@click.option("--days-back", default=0, help="Days in the past to include")
@click.option("--days-forward", default=7, help="Days in the future to include")
def calendar_range_cmd(days_back: int, days_forward: int):
    """Get calendar events in a date range."""
    from rubber_duck.gtd.calendar import calendar_range

    try:
        result = calendar_range(days_back=days_back, days_forward=days_forward)
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(json.dumps({"error": str(e)}), err=True)
        sys.exit(1)


if __name__ == "__main__":
    gtd()
```

**Step 2: Register CLI in pyproject.toml**

Add to `pyproject.toml` under `[project.scripts]`:

```toml
[project.scripts]
rubber-duck-gtd = "rubber_duck.cli.gtd:gtd"
```

**Step 3: Test CLI works**

```bash
uv run python -m rubber_duck.cli.gtd --help
```

Expected: Shows help with all commands listed

**Step 4: Commit**

```bash
git add src/rubber_duck/cli/gtd.py pyproject.toml
git commit -m "feat(gtd): add CLI entry point for GTD commands"
```

---

## Phase 2: Skills

### Task 9: Create skill directory structure

**Files:**
- Create: `.claude/skills/gtd/SKILL.md`
- Create: `.claude/skills/gtd/daily.md`
- Create: `.claude/skills/gtd/weekly.md`
- Create: `.claude/skills/gtd/reference/prioritizing-tasks.md`

**Step 1: Create directories**

```bash
mkdir -p .claude/skills/gtd/reference
```

**Step 2: Create router skill**

```markdown
# .claude/skills/gtd/SKILL.md
---
name: managing-gtd
description: GTD (Getting Things Done) workflow system. Routes to daily planning or weekly review based on user request. Use when user mentions GTD, daily planning, weekly review, or productivity workflows.
---

# GTD Workflow System

This skill system implements GTD (Getting Things Done) workflows.

## Available Workflows

**Daily Planning** - Morning routine to identify today's priorities
- Trigger: "morning planning", "daily planning", "what should I work on today"
- See: [daily.md](daily.md)

**Weekly Review** - Comprehensive review of all open loops
- Trigger: "weekly review", "review projects", "GTD review"
- See: [weekly.md](weekly.md)

## CLI Tools

All workflows use these JSON-returning CLI commands:

```bash
uv run python -m rubber_duck.cli.gtd scan-deadlines
uv run python -m rubber_duck.cli.gtd check-projects
uv run python -m rubber_duck.cli.gtd check-waiting
uv run python -m rubber_duck.cli.gtd check-someday
uv run python -m rubber_duck.cli.gtd calendar-today
uv run python -m rubber_duck.cli.gtd calendar-range --days-back 7 --days-forward 14
```

## Task Link Format

Format all task links as: `[🔗](https://todoist.com/app/task/{id})`
```

**Step 3: Commit structure**

```bash
git add .claude/skills/gtd/
git commit -m "feat(gtd): create skill directory structure"
```

---

### Task 10: Create planning-daily skill

**Files:**
- Create: `.claude/skills/gtd/daily.md`

**Step 1: Write the skill**

```markdown
# .claude/skills/gtd/daily.md
---
name: planning-daily
description: Run GTD morning planning to identify today's priorities. Use when user asks about daily planning, morning routine, what to work on today, or when triggered by scheduled nudge.
---

# Daily Planning

Run through today's commitments and identify the user's TOP priorities.

## Checklist

Copy this checklist into your response and check off each step AS YOU COMPLETE IT:

```
Daily Planning Progress:
- [ ] Step 1: Check calendar for fixed commitments
- [ ] Step 2: Scan deadlines (overdue + due today + this week)
- [ ] Step 3: Identify TOP priorities (2-4 items)
- [ ] Step 4: Present summary
```

DO NOT skip steps. DO NOT combine steps. Complete each one, report findings, then proceed.

## Step 1: Check Calendar

Run:
```bash
uv run python -m rubber_duck.cli.gtd calendar-today
```

Report all meetings and time-blocked commitments. These are non-negotiable fixed points in the day.

If no calendar events: Say "No calendar events scheduled for today."

## Step 2: Scan Deadlines

Run:
```bash
uv run python -m rubber_duck.cli.gtd scan-deadlines
```

YOU MUST report ALL of these categories, even if empty:

1. **OVERDUE** - Past due date. For each: note how many days overdue.
2. **DUE TODAY** - Must be completed today.
3. **DUE THIS WEEK** - Coming up soon, for awareness.

Format each task as: `[🔗](https://todoist.com/app/task/{id}) Task content`

If a category is empty, explicitly state: "No overdue items" / "Nothing due today" / etc.

## Step 3: Identify TOP Priorities

Based on the deadline scan, identify **2-4 TOP priorities** for today.

Priority algorithm (see [reference/prioritizing-tasks.md](reference/prioritizing-tasks.md)):
1. Overdue items first (most days overdue = highest priority)
2. Due today items
3. High-priority items due this week

YOU MUST:
- Select exactly 2-4 priorities (not 1, not 5+)
- Briefly explain WHY each was selected
- Include clickable task link for each

## Step 4: Present Summary

Format the final output as:

```
## Daily Plan - [Date]

### Calendar
[List events or "No events scheduled"]

### TOP Priorities
1. [🔗](url) Task - [reason]
2. [🔗](url) Task - [reason]
...

### Also Due Today
[List or "Nothing else due"]

### Coming This Week
[Brief list for awareness]

---
*[count] overdue | [count] due today | [count] due this week*
```

## Common Mistakes to Avoid

- **Skipping empty categories**: Always report "No overdue items" rather than omitting
- **Too many priorities**: 2-4 is the limit. More dilutes focus.
- **Missing task links**: Every task mentioned needs a [🔗](url) link
- **Vague priority reasons**: "It's important" is not a reason. "3 days overdue" is.
```

**Step 2: Commit**

```bash
git add .claude/skills/gtd/daily.md
git commit -m "feat(gtd): create planning-daily skill"
```

---

### Task 11: Create reviewing-weekly skill

**Files:**
- Create: `.claude/skills/gtd/weekly.md`

**Step 1: Write the skill**

```markdown
# .claude/skills/gtd/weekly.md
---
name: reviewing-weekly
description: Run GTD weekly review to assess project health, follow up on waiting items, and triage someday-maybe. Use when user asks for weekly review, wants to review projects, or on scheduled weekly nudge.
---

# Weekly Review

A comprehensive review of all open loops. Takes 15-30 minutes.

## Checklist

Copy this checklist into your response and check off each step AS YOU COMPLETE IT:

```
Weekly Review Progress:
- [ ] Step 1: Calendar review (past week + next 2 weeks)
- [ ] Step 2: Deadline scan
- [ ] Step 3: Waiting-for review
- [ ] Step 4: Project health check
- [ ] Step 5: Someday-maybe triage
- [ ] Step 6: Summary
```

**CRITICAL**: DO NOT skip steps. DO NOT summarize multiple steps together. Complete each step fully, report findings, then proceed to next.

---

## Step 1: Calendar Review

Run:
```bash
uv run python -m rubber_duck.cli.gtd calendar-range --days-back 7 --days-forward 14
```

Review and report:
- **Past week**: Any events that need follow-up? Actions not captured?
- **Next two weeks**: What's coming that needs preparation?

If calendar not configured or empty, state that and move on.

---

## Step 2: Deadline Scan

Run:
```bash
uv run python -m rubber_duck.cli.gtd scan-deadlines
```

YOU MUST report ALL categories even if empty:

### OVERDUE
For each overdue item, ask the user:
- Reschedule to realistic date?
- Do it now?
- Delete if no longer relevant?

### DUE THIS WEEK
List items. Ask if any need time blocked.

### DUE NEXT WEEK
Brief mention for awareness.

Format: `[🔗](https://todoist.com/app/task/{id}) Task content`

---

## Step 3: Waiting-For Review

Run:
```bash
uv run python -m rubber_duck.cli.gtd check-waiting
```

### NEEDS FOLLOW-UP (> 7 days)
For each item:
- Show the suggested follow-up message from the JSON
- Ask: Send follow-up? Reschedule? Give more time?

### GENTLE CHECK (4-7 days)
Brief mention. Ask if any need follow-up.

### STILL FRESH (< 4 days)
Acknowledge count only: "X items still within normal response time"

---

## Step 4: Project Health Check

Run:
```bash
uv run python -m rubber_duck.cli.gtd check-projects
```

YOU MUST report on each status category:

### STALLED (has tasks but no recent progress)
For each stalled project:
- Show the next action if available
- Ask: Is this the right next action? Should project be deferred? Abandoned?

### INCOMPLETE (no next action defined)
GTD requires every active project have a next action.
For each: Ask user to define a next action OR move to someday-maybe.

### WAITING (all tasks are waiting-for)
Brief acknowledgment. These are blocked, not stalled.

### ACTIVE (has recent completions)
Brief positive acknowledgment: "X projects making progress"

---

## Step 5: Someday-Maybe Triage

Run:
```bash
uv run python -m rubber_duck.cli.gtd check-someday
```

### CONSIDER DELETING (> 1 year old)
For each: "This has been on backburner for [X] days. Still relevant?"
- Delete?
- Activate (move to active project)?
- Keep on backburner?

### NEEDS DECISION (6-12 months)
Brief review. Any ready to activate?

### KEEP (< 6 months)
Acknowledge count: "X items appropriately on backburner"

---

## Step 6: Summary

Provide:

```
## Weekly Review Complete

### Decisions Made
- [List any decisions from the review]

### Action Items Generated
- [List any new tasks created or follow-ups needed]

### System Health
- Active projects: X
- Stalled projects: X (addressed above)
- Waiting items: X
- Someday-maybe: X

### Next Review
Schedule for: [suggest date ~7 days out]
```

---

## Common Mistakes to Avoid

- **Rushing through steps**: Each step deserves full attention
- **Not asking for decisions**: Stalled projects and old backburner items need user input
- **Skipping empty categories**: Always report "No stalled projects" rather than omitting
- **Missing task links**: Every task needs `[🔗](url)`
- **Combining steps**: Report each step separately, even if findings are brief
```

**Step 2: Commit**

```bash
git add .claude/skills/gtd/weekly.md
git commit -m "feat(gtd): create reviewing-weekly skill"
```

---

### Task 12: Create priority reference file

**Files:**
- Create: `.claude/skills/gtd/reference/prioritizing-tasks.md`

**Step 1: Write the reference**

```markdown
# .claude/skills/gtd/reference/prioritizing-tasks.md

# Prioritizing Tasks

Algorithm for selecting TOP priorities in daily planning.

## Priority Order

1. **Overdue items** (highest priority)
   - Sort by days overdue (most overdue first)
   - These represent broken commitments

2. **Due today**
   - Hard deadlines that cannot slip
   - Time-specific items take precedence

3. **High-priority items due this week**
   - Todoist priority 1-3 (priority 4 is default/none)
   - Closer due date wins ties

4. **Strategic value** (tiebreaker)
   - Unblocks other work
   - High visibility/impact
   - User's stated current focus

## Constraints

- Select **2-4 items** only
- More than 4 dilutes focus and sets up for failure
- Fewer than 2 suggests either nothing is urgent (great!) or poor capture

## What NOT to Prioritize

- Tasks with no due date (unless strategically important)
- Someday-maybe items (by definition not for today)
- Waiting-for items (blocked on others)
- Tasks in "backburner" labeled projects
```

**Step 2: Commit**

```bash
git add .claude/skills/gtd/reference/prioritizing-tasks.md
git commit -m "feat(gtd): add priority algorithm reference"
```

---

## Phase 3: Cleanup

### Task 13: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update the GTD Workflows section**

Find the "GTD Workflows" section and update it to reference the new skills:

```markdown
### GTD Workflows

The bot implements GTD (Getting Things Done) via Claude Code skills:

**Skills** (`.claude/skills/gtd/`):
- `planning-daily` - Morning planning: TOP priorities, calendar, deadlines
- `reviewing-weekly` - Weekly review: projects, waiting-for, someday-maybe

**CLI Tools** (return JSON for skill consumption):
```bash
uv run python -m rubber_duck.cli.gtd scan-deadlines
uv run python -m rubber_duck.cli.gtd check-projects
uv run python -m rubber_duck.cli.gtd check-waiting
uv run python -m rubber_duck.cli.gtd check-someday
uv run python -m rubber_duck.cli.gtd calendar-today
```

Skills guide the procedure; CLI tools handle computation.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with GTD skills documentation"
```

---

### Task 14: Run full test suite

**Step 1: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All tests pass (existing + new GTD tests)

**Step 2: Run linter**

```bash
uv run ruff check src/rubber_duck/gtd/ tests/test_gtd_*.py
```

Fix any issues.

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: address linter issues in GTD module"
```

---

### Task 15: Manual skill test

**Step 1: Test CLI tools work**

```bash
# These may fail without API keys, but should at least not crash
uv run python -m rubber_duck.cli.gtd scan-deadlines
uv run python -m rubber_duck.cli.gtd check-projects
```

**Step 2: Verify skill files are valid**

Check that skill files have valid YAML frontmatter:

```bash
head -10 .claude/skills/gtd/SKILL.md
head -10 .claude/skills/gtd/daily.md
head -10 .claude/skills/gtd/weekly.md
```

**Step 3: Create summary commit**

```bash
git add -A
git commit -m "feat(gtd): complete GTD skills implementation

- CLI tools: scan-deadlines, check-projects, check-waiting, check-someday, calendar-today/range
- Skills: managing-gtd (router), planning-daily, reviewing-weekly
- Reference: prioritizing-tasks algorithm

Implements rubber-duck-jay"
```

---

## Execution Complete

After all tasks:

1. Run full test suite one more time
2. Push branch for review: `git push -u origin feature/gtd-skills`
3. Create PR for user review

---

Plan complete and saved to `docs/plans/2026-01-05-gtd-skills-implementation.md`.

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session in worktree with executing-plans, batch execution with checkpoints

Which approach?
