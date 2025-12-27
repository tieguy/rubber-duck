def update_todoist_task(task_id: str, due_string: str = None, content: str = None) -> str:
    """Update an existing task in Todoist.

    Use this tool when the user wants to reschedule a task, change its due date,
    or modify the task content. You need the task_id from a previous query.

    Args:
        task_id: The Todoist task ID (from query results)
        due_string: New due date in natural language (e.g., "tomorrow", "Dec 29")
        content: New task content/title (optional)

    Returns:
        Confirmation message or error
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot update task."

    try:
        payload = {}
        if due_string:
            payload["due_string"] = due_string
        if content:
            payload["content"] = content

        if not payload:
            return "Nothing to update. Provide due_string or content."

        response = requests.post(
            f"https://api.todoist.com/rest/v2/tasks/{task_id}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        response.raise_for_status()
        task = response.json()

        return f"Updated task: {task['content']}\nNew due: {task.get('due', {}).get('string', 'none')}"

    except Exception as e:
        return f"Error updating task: {str(e)}"
