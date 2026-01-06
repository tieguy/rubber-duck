"""Project health checking for GTD workflows."""

import os
from datetime import UTC, datetime, timedelta

import requests

BACKBURNER_LABELS = {"someday-maybe", "maybe", "someday", "later", "backburner"}
WAITING_LABELS = {"waiting", "waiting-for", "waiting for"}


def _compute_project_health(tasks: list, completions: list) -> str:
    """Compute project health status.

    Args:
        tasks: List of open tasks in the project
        completions: List of completed tasks in the project (last 7 days)

    Returns:
        Status string: "active", "stalled", "waiting", or "incomplete"
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
    """Get highest priority actionable task from project.

    Args:
        tasks: List of task dicts

    Returns:
        The highest priority actionable task, or None if no actionable tasks
    """
    actionable = [
        t
        for t in tasks
        if not (
            {label.lower() for label in t.get("labels", [])}
            & (BACKBURNER_LABELS | WAITING_LABELS)
        )
    ]
    if not actionable:
        return None

    # Prefer prioritized tasks (priority 1-3, where 4 is default/none)
    prioritized = [t for t in actionable if t.get("priority", 4) < 4]
    if prioritized:
        return min(prioritized, key=lambda t: t.get("priority", 4))
    return actionable[0]


def _fetch_tasks() -> list:
    """Fetch all tasks from Todoist.

    Returns:
        List of task dicts with keys: id, content, labels, project_id, priority
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
        List of project dicts with keys: id, name
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


def _fetch_completed_tasks(days: int = 7) -> list:
    """Fetch completed tasks from last N days.

    Args:
        days: Number of days to look back (default 7)

    Returns:
        List of completed task items with task_id, project_id
    """
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return []

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    response = requests.post(
        "https://api.todoist.com/sync/v9/completed/get_all",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"since": since, "limit": 200},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("items", [])


def _group_by_project(items: list, key: str = "project_id") -> dict:
    """Group items by project ID.

    Args:
        items: List of dicts with project_id key
        key: Key name to group by (default "project_id")

    Returns:
        Dict mapping project_id to list of items
    """
    grouped: dict[str, list] = {}
    for item in items:
        pid = item.get(key)
        if pid not in grouped:
            grouped[pid] = []
        grouped[pid].append(item)
    return grouped


def check_projects() -> dict:
    """Check project health status.

    Returns:
        Dict with keys:
        - active: List of projects with recent completions
        - stalled: List of projects with tasks but no activity
        - waiting: List of projects with only waiting tasks
        - incomplete: List of projects with no next action defined
        - summary: Counts for each category
        - generated_at: ISO timestamp
    """
    tasks = _fetch_tasks()
    projects = _fetch_projects()
    completed = _fetch_completed_tasks(days=7)

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

        # Skip empty projects (no open tasks and no recent completions)
        if not proj_tasks and not proj_completions:
            continue

        status = _compute_project_health(proj_tasks, proj_completions)

        info: dict = {
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
        "generated_at": datetime.now(UTC).isoformat(),
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
