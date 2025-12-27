def query_todoist(filter_query: str) -> str:
    """Query tasks from Todoist.

    Use this tool when the user asks about their tasks, todos, or what they
    should work on. Common filters:
    - "today" - tasks due today
    - "overdue" - overdue tasks
    - "@label" - tasks with a specific label (e.g., "@asa", "@krissa")
    - "#Project" - tasks in a specific project
    - "all" - all incomplete tasks

    Args:
        filter_query: Todoist filter string

    Returns:
        Formatted list of matching tasks, or a message if none found
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot query tasks."

    try:
        # Get projects first for names and hierarchy
        proj_resp = requests.get(
            "https://api.todoist.com/rest/v2/projects",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        proj_resp.raise_for_status()
        projects = proj_resp.json()
        proj_by_id = {p["id"]: p for p in projects}

        def get_project_path(pid):
            """Get full project path like 'Parent > Child'."""
            if not pid or pid not in proj_by_id:
                return "Inbox"
            proj = proj_by_id[pid]
            parent_id = proj.get("parent_id")
            if parent_id and parent_id in proj_by_id:
                return f"{proj_by_id[parent_id]['name']} > {proj['name']}"
            return proj["name"]

        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"filter": filter_query} if filter_query and filter_query != "all" else {}
        )
        response.raise_for_status()
        tasks = response.json()

        if not tasks:
            return f"No tasks found matching '{filter_query}'."

        # Format tasks with IDs for update/complete operations
        lines = [f"Found {len(tasks)} task(s):"]
        for task in tasks[:20]:  # Limit to 20
            project_path = get_project_path(task.get("project_id"))
            due = ""
            if task.get("due"):
                due = f" (due: {task['due'].get('string', task['due'].get('date', ''))})"
            labels = ""
            if task.get("labels"):
                labels = f" [{', '.join(task['labels'])}]"
            # Include task ID and project so it can be used for updates
            lines.append(f"- [{project_path}] [ID:{task['id']}] {task['content']}{due}{labels}")

        if len(tasks) > 20:
            lines.append(f"... and {len(tasks) - 20} more")

        return "\n".join(lines)

    except Exception as e:
        return f"Error querying Todoist: {str(e)}"
