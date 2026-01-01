def query_todoist(filter_query: str) -> str:
    """Query tasks from Todoist.

    Use this tool when the user asks about their tasks, todos, or what they
    should work on. Common filters:
    - "today" - tasks due today
    - "overdue" - overdue tasks
    - "@label" - tasks with a specific label (e.g., "@home", "@work")
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

        # Someday-maybe detection via ancestry
        SOMEDAY_PROJECT_NAMES = {"someday-maybe", "someday maybe", "someday/maybe", "someday"}

        def is_someday_maybe(project_id):
            """Check if project or any ancestor is named 'someday-maybe'."""
            current_id = project_id
            while current_id:
                proj = proj_by_id.get(current_id)
                if not proj:
                    break
                if proj.get("name", "").lower().strip() in SOMEDAY_PROJECT_NAMES:
                    return True
                current_id = proj.get("parent_id")
            return False

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

        # Build task hierarchy map
        tasks_by_id = {t["id"]: t for t in tasks}

        # Identify parent tasks and subtasks
        parent_tasks = []
        subtasks_by_parent = {}
        orphan_subtasks = []  # Subtasks whose parent isn't in results

        for task in tasks:
            parent_id = task.get("parent_id")
            if parent_id:
                if parent_id in tasks_by_id:
                    if parent_id not in subtasks_by_parent:
                        subtasks_by_parent[parent_id] = []
                    subtasks_by_parent[parent_id].append(task)
                else:
                    orphan_subtasks.append(task)
            else:
                parent_tasks.append(task)

        def format_task(task, indent=0):
            project_path = get_project_path(task.get("project_id"))
            someday_marker = " 💤" if is_someday_maybe(task.get("project_id")) else ""
            due = ""
            if task.get("due"):
                due = f" (due: {task['due'].get('string', task['due'].get('date', ''))})"
            labels = ""
            if task.get("labels"):
                labels = f" [{', '.join(task['labels'])}]"
            prefix = "  " * indent
            subtask_marker = "↳ " if indent > 0 else ""
            return f"{prefix}- {subtask_marker}[{project_path}] [ID:{task['id']}] {task['content']}{due}{labels}{someday_marker}"

        # Format tasks with hierarchy
        lines = [f"Found {len(tasks)} task(s):"]
        shown = 0

        for task in parent_tasks:
            if shown >= 20:
                break
            lines.append(format_task(task))
            shown += 1
            # Show subtasks indented
            for subtask in subtasks_by_parent.get(task["id"], []):
                if shown >= 20:
                    break
                lines.append(format_task(subtask, indent=1))
                shown += 1

        # Show orphan subtasks (parent not in results)
        for task in orphan_subtasks:
            if shown >= 20:
                break
            parent_id = task.get("parent_id")
            lines.append(f"- ↳ (subtask) [{get_project_path(task.get('project_id'))}] [ID:{task['id']}] {task['content']}")
            shown += 1

        if len(tasks) > 20:
            lines.append(f"... and {len(tasks) - 20} more")

        return "\n".join(lines)

    except Exception as e:
        return f"Error querying Todoist: {str(e)}"
