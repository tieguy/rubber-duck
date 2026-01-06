"""Waiting-for tracking for GTD workflows."""

import os
from datetime import UTC, date, datetime

import requests

WAITING_LABELS = {"waiting", "waiting-for", "waiting for"}


def _get_staleness_category(days: int) -> tuple[str, str, str]:
    """Get category, urgency, and suggested action based on days waiting.

    Returns: (category, urgency, suggested_action)
    """
    if days < 4:
        return ("still_fresh", "fresh", "Still within normal response time.")
    elif days < 8:
        return (
            "gentle_check",
            "gentle",
            "Just checking in on this. No rush, wanted to ensure it's on your radar.",
        )
    elif days < 15:
        return (
            "needs_followup",
            "firm",
            f"Following up on this from {days} days ago. Could you provide a status update?",
        )
    elif days < 22:
        return (
            "needs_followup",
            "urgent",
            f"This has been pending for {days} days. Need a firm timeline or explore alternatives.",
        )
    else:
        return (
            "needs_followup",
            "escalate",
            f"Waiting {days} days. May need to escalate or find workaround.",
        )


def _categorize_waiting(tasks: list, today: date) -> dict:
    """Categorize waiting-for items by staleness.

    Args:
        tasks: List of task dicts with 'id', 'content', 'labels', 'created_at', 'project_id'
        today: Reference date for calculations

    Returns:
        Dict with needs_followup, gentle_check, still_fresh lists and summary
    """
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
    """Fetch all tasks from Todoist.

    Returns:
        List of task dicts with keys: id, content, labels, created_at, project_id
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


def check_waiting() -> dict:
    """Check waiting-for items and staleness.

    Returns:
        Dict with needs_followup, gentle_check, still_fresh lists and summary.
        Each item includes: id, content, project (name), days_waiting, urgency, suggested_action.
    """
    tasks = _fetch_tasks()
    projects = _fetch_projects()
    today = date.today()

    result = _categorize_waiting(tasks, today)

    # Resolve project IDs to names
    for category in ["needs_followup", "gentle_check", "still_fresh"]:
        for item in result[category]:
            item["project"] = projects.get(item["project"], item["project"])

    result["generated_at"] = datetime.now(UTC).isoformat()

    return result
