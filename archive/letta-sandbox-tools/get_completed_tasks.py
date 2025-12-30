def get_completed_tasks(since_days: int = 1) -> str:
    """Get recently completed tasks from Todoist.

    Use this to see what was accomplished recently. Useful for:
    - End-of-day reviews (what got done today)
    - Weekly reviews (what got done this week)
    - Celebrating wins and progress

    Args:
        since_days: How many days back to look (default: 1 for today)

    Returns:
        Formatted list of completed tasks
    """
    import os
    import requests
    from datetime import datetime, timedelta

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured."

    try:
        # Todoist Sync API for completed tasks
        # Note: REST API doesn't support completed tasks, need Sync API
        since = (datetime.now() - timedelta(days=since_days)).isoformat()

        response = requests.post(
            "https://api.todoist.com/sync/v9/completed/get_all",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"since": since, "limit": 50}
        )
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            return f"No tasks completed in the last {since_days} day(s)."

        lines = [f"Completed in last {since_days} day(s): {len(items)} task(s)"]
        lines.append("")

        # Group by project
        by_project = {}
        for item in items:
            proj_id = item.get("project_id", "unknown")
            if proj_id not in by_project:
                by_project[proj_id] = []
            by_project[proj_id].append(item)

        projects = data.get("projects", {})
        for proj_id, tasks in by_project.items():
            proj_name = projects.get(str(proj_id), {}).get("name", "Unknown Project")
            lines.append(f"**{proj_name}:**")
            for task in tasks:
                completed_at = task.get("completed_at", "")
                if completed_at:
                    try:
                        dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        time_str = dt.strftime('%b %d %I:%M %p')
                    except:
                        time_str = completed_at
                else:
                    time_str = ""
                lines.append(f"  [done] {task['content']} ({time_str})")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting completed tasks: {str(e)}"
