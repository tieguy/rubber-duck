def complete_todoist_task(task_id: str) -> str:
    """Mark a task as complete in Todoist.

    Use this tool when the user says they finished a task or wants to check it off.

    Args:
        task_id: The Todoist task ID (from query results)

    Returns:
        Confirmation message or error
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot complete task."

    try:
        response = requests.post(
            f"https://api.todoist.com/rest/v2/tasks/{task_id}/close",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        return "Task marked as complete!"

    except Exception as e:
        return f"Error completing task: {str(e)}"
