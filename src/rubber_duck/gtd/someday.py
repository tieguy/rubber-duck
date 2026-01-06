"""Someday-maybe triage for GTD workflows."""

import os
from datetime import UTC, date, datetime

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
    """Categorize someday-maybe items by age.

    Args:
        tasks: List of task dicts with 'id', 'content', 'labels', 'created_at', 'project_id'
        today: Reference date for calculations
        proj_by_id: Dict mapping project_id to project dict

    Returns:
        Dict with consider_deleting, needs_decision, keep lists and summary
    """
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


def _fetch_projects() -> list:
    """Fetch all projects from Todoist.

    Returns:
        List of project dicts with keys: id, name, parent_id
    """
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
        Each item includes: id, content, project (name), days_old.
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

    result["generated_at"] = datetime.now(UTC).isoformat()

    return result
