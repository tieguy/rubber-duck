"""Deadline scanning for GTD workflows."""

import os
from datetime import UTC, date, datetime

import requests


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


def _fetch_tasks() -> list:
    """Fetch all tasks from Todoist.

    Returns:
        List of task dicts with keys: id, content, due, project_id
    """
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
    """Fetch projects and return id->name mapping.

    Returns:
        Dict mapping project_id to project_name
    """
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

    result["generated_at"] = datetime.now(UTC).isoformat()

    return result
