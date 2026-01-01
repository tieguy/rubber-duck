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
) -> dict | None:
    """Create a new task in Todoist.

    Args:
        content: Task title
        description: Optional task description
        labels: Optional list of label names
        due_string: Optional due date string (e.g., "tomorrow", "next monday")

    Returns:
        Created task dict or None on failure
    """
    client = get_client()
    if not client:
        return None

    try:
        # Wrap sync call to avoid blocking event loop
        task = await asyncio.to_thread(
            client.add_task,
            content=content,
            description=description,
            labels=labels or [],
            due_string=due_string,
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
        # close_task expects task_id as positional argument
        await asyncio.to_thread(client.close_task, task_id)
        return True
    except Exception as e:
        logger.exception(f"Error completing Todoist task: {e}")
        return False
