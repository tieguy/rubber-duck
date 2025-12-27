def run_weekly_review() -> str:
    """Run the weekly review workflow.

    This comprehensive GTD review covers:
    1. Project health - which projects are active, stalled, or incomplete?
    2. Waiting-for items - what needs follow-up?
    3. Overdue/upcoming deadlines
    4. Task volume by project

    Call this when the user asks for:
    - "Weekly review"
    - "How are my projects doing?"
    - "What's stalled?"
    - "Review everything"

    Returns:
        Comprehensive weekly review with project status and recommendations
    """
    import os
    import requests
    from datetime import datetime, date, timedelta

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot run weekly review."

    try:
        # Get projects
        proj_resp = requests.get(
            "https://api.todoist.com/rest/v2/projects",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        proj_resp.raise_for_status()
        projects = proj_resp.json()

        # Get all tasks
        task_resp = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        task_resp.raise_for_status()
        all_tasks = task_resp.json()

        today = date.today()

        # Organize tasks by project
        tasks_by_project = {}
        waiting_for = []
        overdue = []
        due_this_week = []

        for task in all_tasks:
            pid = task.get("project_id")
            if pid not in tasks_by_project:
                tasks_by_project[pid] = []
            tasks_by_project[pid].append(task)

            # Check for waiting-for
            labels = task.get("labels", [])
            if "waiting" in labels or "waiting-for" in labels:
                waiting_for.append(task)

            # Check due dates
            due = task.get("due")
            if due:
                due_date_str = due.get("date", "")[:10]
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                    days_until = (due_date - today).days
                    if days_until < 0:
                        overdue.append((task, days_until))
                    elif days_until <= 7:
                        due_this_week.append((task, days_until))
                except ValueError:
                    pass

        # Build project health report
        proj_by_id = {p["id"]: p for p in projects}

        lines = []
        lines.append(f"## Weekly Review - Week of {today.strftime('%B %d, %Y')}")
        lines.append("")

        # Urgent items first
        if overdue:
            lines.append("### OVERDUE ITEMS")
            for task, days in sorted(overdue, key=lambda x: x[1])[:10]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                lines.append(f"- [{proj_name}] [ID:{task['id']}] {task['content']} ({abs(days)}d overdue)")
            lines.append("")

        # This week's deadlines
        if due_this_week:
            lines.append("### DUE THIS WEEK")
            for task, days in sorted(due_this_week, key=lambda x: x[1])[:10]:
                day_name = (today + timedelta(days=days)).strftime('%A')
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                lines.append(f"- {day_name}: [{proj_name}] {task['content']}")
            lines.append("")

        # Project health
        lines.append("### PROJECT HEALTH")
        lines.append("")

        def get_next_action(tasks):
            """Get next action: highest priority task, or first task if no priorities."""
            # Filter out waiting-for tasks
            actionable = [t for t in tasks if not any(
                l in t.get("labels", []) for l in ["waiting", "waiting-for"]
            )]
            if not actionable:
                return None
            # Priority 1-3 are explicit, 4 means no priority
            # Sort by priority (1=highest), then by order in list
            prioritized = [t for t in actionable if t.get("priority", 4) < 4]
            if prioritized:
                return min(prioritized, key=lambda t: t.get("priority", 4))
            # No explicit priority - first task is next action
            return actionable[0]

        active = []
        stalled = []

        for proj in projects:
            pid = proj["id"]
            tasks = tasks_by_project.get(pid, [])

            if not tasks:
                continue  # Skip empty projects

            next_action = get_next_action(tasks)
            if next_action:
                active.append((proj, len(tasks), next_action))
            else:
                # All tasks are waiting-for, project is stalled
                stalled.append((proj, len(tasks)))

        if active:
            lines.append("**Active Projects** (with next actions):")
            for proj, count, next_task in sorted(active, key=lambda x: -x[1])[:8]:
                priority = next_task.get("priority", 4)
                priority_str = f"P{priority}" if priority < 4 else ""
                lines.append(f"- {proj['name']}: {count} tasks")
                lines.append(f"  → Next: {next_task['content']} {priority_str}".rstrip())
            lines.append("")

        if stalled:
            lines.append("**Stalled Projects** (all tasks waiting-for):")
            for proj, count in stalled[:5]:
                lines.append(f"- {proj['name']}: {count} waiting-for tasks - needs follow-up")
            lines.append("")

        # Waiting-for items
        if waiting_for:
            lines.append("### WAITING-FOR ITEMS")
            lines.append("*Review for follow-up:*")
            for task in waiting_for[:8]:
                proj_name = proj_by_id.get(task.get("project_id"), {}).get("name", "Inbox")
                created = task.get("created_at", "")
                age_str = ""
                if created:
                    try:
                        created_date = datetime.fromisoformat(created.replace('Z', '+00:00')).date()
                        age = (today - created_date).days
                        if age > 14:
                            age_str = f" !! {age}d - follow up!"
                        elif age > 7:
                            age_str = f" ({age}d - gentle check-in)"
                        else:
                            age_str = f" ({age}d)"
                    except:
                        pass
                lines.append(f"- [{proj_name}] {task['content']}{age_str}")
            lines.append("")

        # Summary stats
        lines.append("---")
        lines.append("**Summary:**")
        lines.append(f"- Total open tasks: {len(all_tasks)}")
        lines.append(f"- Overdue: {len(overdue)}")
        lines.append(f"- Due this week: {len(due_this_week)}")
        lines.append(f"- Waiting-for: {len(waiting_for)}")
        lines.append(f"- Active projects: {len(active)}")
        lines.append(f"- Stalled projects: {len(stalled)}")
        lines.append("")
        lines.append("**Recommended Actions:**")
        if overdue:
            lines.append("1. Address overdue items first")
        if stalled:
            lines.append("2. Follow up on stalled projects (all waiting-for)")
        if waiting_for:
            old_waiting = [t for t in waiting_for if t.get("created_at")]
            if old_waiting:
                lines.append("3. Check waiting-for items older than 2 weeks")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running weekly review: {str(e)}"
