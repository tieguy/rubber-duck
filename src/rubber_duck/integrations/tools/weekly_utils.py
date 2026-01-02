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
