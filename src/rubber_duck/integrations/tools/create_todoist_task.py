def create_todoist_task(content: str, due_string: str = None, labels: list = None, project_id: str = None) -> str:
    """Create a new task in Todoist.

    Use this tool when the user wants to add a task, reminder, or todo item.

    Args:
        content: The task title/description
        due_string: Optional due date in natural language (e.g., "tomorrow", "next monday")
        labels: Optional list of label names to apply
        project_id: Optional project ID to put the task in (get from list_todoist_projects)

    Returns:
        Confirmation message with task details
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot create task."

    try:
        payload = {"content": content}
        if due_string:
            payload["due_string"] = due_string
        if labels:
            payload["labels"] = labels
        if project_id:
            payload["project_id"] = project_id

        response = requests.post(
            "https://api.todoist.com/rest/v2/tasks",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        response.raise_for_status()
        task = response.json()

        return f"Created task: {task['content']}\nURL: {task['url']}"

    except Exception as e:
        return f"Error creating task: {str(e)}"
