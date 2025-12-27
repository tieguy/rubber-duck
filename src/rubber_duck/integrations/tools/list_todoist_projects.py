def list_todoist_projects() -> str:
    """List all projects in Todoist with their task counts.

    Use this tool to see the project hierarchy and understand how tasks are organized.
    Useful for weekly reviews or when helping the user decide what to work on.

    Returns:
        Formatted list of projects with task counts
    """
    import os
    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured."

    try:
        # Get projects
        proj_resp = requests.get(
            "https://api.todoist.com/rest/v2/projects",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        proj_resp.raise_for_status()
        projects = proj_resp.json()

        # Get all tasks to count per project
        task_resp = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        task_resp.raise_for_status()
        tasks = task_resp.json()

        # Count tasks per project
        task_counts = {}
        for task in tasks:
            pid = task.get("project_id")
            task_counts[pid] = task_counts.get(pid, 0) + 1

        # Build project tree
        proj_by_id = {p["id"]: p for p in projects}
        roots = [p for p in projects if not p.get("parent_id")]

        def format_project(proj, indent=0, parent_name=None):
            pid = proj["id"]
            count = task_counts.get(pid, 0)
            prefix = "  " * indent
            # Show hierarchy path for sub-projects
            if parent_name:
                path_info = f" (sub-project of {parent_name})"
            else:
                path_info = ""
            line = f"{prefix}- [ID:{pid}] {proj['name']}{path_info} ({count} tasks)"
            children = [p for p in projects if p.get("parent_id") == pid]
            child_lines = [format_project(c, indent + 1, proj['name']) for c in children]
            return "\n".join([line] + child_lines)

        lines = [format_project(r) for r in roots]
        result = "Projects (indented = sub-project):\n" + "\n".join(lines)
        return result

    except Exception as e:
        return f"Error listing projects: {str(e)}"
