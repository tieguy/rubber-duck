# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Todoist API integration for Rubber Duck."""

import asyncio
import logging
import os

from todoist_api_python.api import TodoistAPI

logger = logging.getLogger(__name__)


def get_client() -> TodoistAPI | None:
    """Get a Todoist API client.

    Returns None if TODOIST_API_KEY is not set.
    """
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        logger.warning("TODOIST_API_KEY not set, Todoist integration disabled")
        return None
    return TodoistAPI(api_key)


async def get_tasks_by_filter(filter_query: str) -> list[dict]:
    """Get tasks matching a Todoist filter query.

    Args:
        filter_query: Todoist filter string (e.g., "@home", "#Health", "today")

    Returns:
        List of task dicts with keys: id, content, description, due, labels, project_id
    """
    client = get_client()
    if not client:
        return []

    try:
        # Wrap sync call to avoid blocking event loop
        # filter_tasks returns Iterator[list[Task]], flatten it
        task_batches = await asyncio.to_thread(
            lambda: list(client.filter_tasks(query=filter_query))
        )
        tasks = [task for batch in task_batches for task in batch]
        return [
            {
                "id": t.id,
                "content": t.content,
                "description": t.description or "",
                "due": t.due.string if t.due else None,
                "labels": t.labels,
                "project_id": t.project_id,
            }
            for t in tasks
        ]
    except Exception as e:
        logger.exception(f"Error fetching Todoist tasks: {e}")
        return []


async def create_task(
    content: str,
    description: str = "",
    labels: list[str] | None = None,
    due_string: str | None = None,
    project_id: str | None = None,
) -> dict | None:
    """Create a new task in Todoist.

    Args:
        content: Task title
        description: Optional task description
        labels: Optional list of label names
        due_string: Optional due date string (e.g., "tomorrow", "next monday")
        project_id: Optional project ID to add task to

    Returns:
        Created task dict or None on failure
    """
    client = get_client()
    if not client:
        return None

    try:
        # Build kwargs, only including non-None values
        kwargs: dict = {
            "content": content,
            "description": description,
            "labels": labels or [],
        }
        if due_string:
            kwargs["due_string"] = due_string
        if project_id:
            kwargs["project_id"] = project_id

        # Wrap sync call to avoid blocking event loop
        task = await asyncio.to_thread(
            lambda: client.add_task(**kwargs)
        )
        return {
            "id": task.id,
            "content": task.content,
            "url": task.url,
        }
    except Exception as e:
        logger.exception(f"Error creating Todoist task: {e}")
        return None


async def complete_task(task_id: str) -> bool:
    """Mark a task as complete in Todoist.

    For recurring tasks, this completes the current occurrence and
    schedules the next one automatically.

    Args:
        task_id: The ID of the task to complete

    Returns:
        True if successful, False otherwise
    """
    client = get_client()
    if not client:
        return False

    try:
        # complete_task marks task as done (recurring tasks get rescheduled)
        await asyncio.to_thread(client.complete_task, task_id)
        return True
    except Exception as e:
        logger.exception(f"Error completing Todoist task: {e}")
        return False


async def get_projects() -> dict[str, str]:
    """Get all Todoist projects as an ID -> name map.

    Returns:
        Dict mapping project_id to project_name, empty dict on failure
    """
    client = get_client()
    if not client:
        return {}

    try:
        project_result = await asyncio.to_thread(
            lambda: list(client.get_projects())
        )
        project_map = {}
        for item in project_result:
            if isinstance(item, list):
                for p in item:
                    project_map[p.id] = p.name
            else:
                project_map[item.id] = item.name
        return project_map
    except Exception as e:
        logger.exception(f"Error fetching Todoist projects: {e}")
        return {}


async def list_projects() -> list[dict]:
    """Get all Todoist projects with full details.

    Returns:
        List of project dicts with id, name, parent_id
    """
    client = get_client()
    if not client:
        return []

    try:
        result = await asyncio.to_thread(
            lambda: list(client.get_projects())
        )

        # Flatten if nested (API returns Iterator[list[Project]])
        projects = []
        for item in result:
            if isinstance(item, list):
                projects.extend(item)
            else:
                projects.append(item)

        return [
            {
                "id": p.id,
                "name": p.name,
                "parent_id": getattr(p, "parent_id", None),
            }
            for p in projects
        ]
    except Exception as e:
        logger.exception(f"Error listing Todoist projects: {e}")
        return []


async def update_task(
    task_id: str,
    content: str | None = None,
    due_string: str | None = None,
    labels: list[str] | None = None,
) -> bool:
    """Update an existing Todoist task.

    Args:
        task_id: Task ID to update
        content: New task content (optional)
        due_string: New due date (optional)
        labels: New labels (optional)

    Returns:
        True if successful, False otherwise
    """
    client = get_client()
    if not client:
        return False

    kwargs: dict = {}
    if content:
        kwargs["content"] = content
    if due_string:
        kwargs["due_string"] = due_string
    if labels is not None:
        kwargs["labels"] = labels

    if not kwargs:
        return False  # Nothing to update

    try:
        await asyncio.to_thread(
            lambda: client.update_task(task_id=task_id, **kwargs)
        )
        return True
    except Exception as e:
        logger.exception(f"Error updating Todoist task: {e}")
        return False


async def move_task(task_id: str, project_id: str) -> bool:
    """Move a task to a different project using Todoist Sync API.

    The REST API doesn't support moving tasks, so we use the Sync API.

    Args:
        task_id: Task ID to move
        project_id: Destination project ID

    Returns:
        True if successful, False otherwise
    """
    import uuid

    import requests

    api_token = os.environ.get("TODOIST_API_KEY")
    if not api_token:
        return False

    try:
        response = await asyncio.to_thread(
            lambda: requests.post(
                "https://api.todoist.com/sync/v9/sync",
                headers={"Authorization": f"Bearer {api_token}"},
                json={
                    "commands": [
                        {
                            "type": "item_move",
                            "uuid": str(uuid.uuid4()),
                            "args": {
                                "id": task_id,
                                "project_id": project_id,
                            },
                        }
                    ]
                },
                timeout=30,
            )
        )
        response.raise_for_status()
        result = response.json()

        # Check for errors in sync response
        if "sync_status" in result:
            for cmd_uuid, status in result["sync_status"].items():
                if status != "ok" and isinstance(status, dict) and "error" in status:
                    logger.error(f"Sync API error: {status['error']}")
                    return False

        return True
    except Exception as e:
        logger.exception(f"Error moving Todoist task: {e}")
        return False
