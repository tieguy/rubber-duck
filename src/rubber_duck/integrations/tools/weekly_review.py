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

    # Label sets for categorization
    BACKBURNER_LABELS = {"someday-maybe", "maybe", "someday", "later", "backburner"}
    WAITING_LABELS = {"waiting", "waiting-for", "waiting for"}
    SOMEDAY_PROJECT_NAMES = {"someday-maybe", "someday maybe", "someday/maybe", "someday"}

    try:
        # Get projects
        proj_resp = requests.get(
            "https://api.todoist.com/rest/v2/projects",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        proj_resp.raise_for_status()
        projects = proj_resp.json()

        # Get all open tasks
        task_resp = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        task_resp.raise_for_status()
        all_tasks = task_resp.json()

        # Get completed tasks from last 7 days
        since = (datetime.now() - timedelta(days=7)).isoformat()
        completed_resp = requests.post(
            "https://api.todoist.com/sync/v9/completed/get_all",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"since": since, "limit": 200}
        )
        completed_resp.raise_for_status()
        completed_data = completed_resp.json()
        completed_tasks = completed_data.get("items", [])

        # Group completions by project
        completions_by_project = {}
        for task in completed_tasks:
            pid = task.get("project_id")
            if pid not in completions_by_project:
                completions_by_project[pid] = []
            completions_by_project[pid].append(task)

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

        # Project health using marvin-to-model logic
        lines.append("### PROJECT HEALTH")
        lines.append("")

        def compute_project_status(tasks, completions):
            """
            Compute project health status.
            - ACTIVE: Has completions in last 7 days
            - WAITING: Has tasks, but all non-backburner are waiting
            - INCOMPLETE: No next actions (only backburner/waiting)
            - STALLED: Has next actions but no recent completions
            """
            if len(completions) > 0:
                return "ACTIVE"

            next_actions = []
            waiting_actions = []

            for task in tasks:
                labels = {label.lower() for label in task.get("labels", [])}
                is_backburner = bool(labels & BACKBURNER_LABELS)
                is_waiting = bool(labels & WAITING_LABELS)

                if is_backburner:
                    continue
                elif is_waiting:
                    waiting_actions.append(task)
                else:
                    next_actions.append(task)

            if len(next_actions) == 0 and len(waiting_actions) == 0:
                return "INCOMPLETE"
            if len(next_actions) == 0 and len(waiting_actions) > 0:
                return "WAITING"
            return "STALLED"

        def get_next_action(tasks):
            """Get next action: highest priority non-backburner/waiting task."""
            actionable = []
            for t in tasks:
                labels = {label.lower() for label in t.get("labels", [])}
                if not (labels & BACKBURNER_LABELS) and not (labels & WAITING_LABELS):
                    actionable.append(t)
            if not actionable:
                return None
            prioritized = [t for t in actionable if t.get("priority", 4) < 4]
            if prioritized:
                return min(prioritized, key=lambda t: t.get("priority", 4))
            return actionable[0]

        projects_by_status = {"ACTIVE": [], "STALLED": [], "WAITING": [], "INCOMPLETE": []}

        someday_maybe_projects = []
        for proj in projects:
            pid = proj["id"]
            tasks = tasks_by_project.get(pid, [])
            completions = completions_by_project.get(pid, [])

            if not tasks and not completions:
                continue  # Skip empty projects

            # Skip someday-maybe projects from health assessment
            if is_someday_maybe(pid):
                someday_maybe_projects.append((proj, len(tasks)))
                continue

            status = compute_project_status(tasks, completions)
            next_action = get_next_action(tasks)
            projects_by_status[status].append((proj, len(tasks), len(completions), next_action))

        # Show ACTIVE projects (making progress)
        if projects_by_status["ACTIVE"]:
            lines.append("**ACTIVE** (completed tasks this week):")
            for proj, task_count, comp_count, next_task in projects_by_status["ACTIVE"][:6]:
                lines.append(f"- ✓ {proj['name']}: {comp_count} done, {task_count} open")
            lines.append("")

        # Show STALLED projects (have work but no progress)
        if projects_by_status["STALLED"]:
            lines.append("**STALLED** (next actions exist but no recent progress):")
            for proj, task_count, _, next_task in projects_by_status["STALLED"][:5]:
                next_str = f" → {next_task['content'][:40]}" if next_task else ""
                lines.append(f"- ⚠️ {proj['name']}: {task_count} tasks{next_str}")
            lines.append("")

        # Show WAITING projects
        if projects_by_status["WAITING"]:
            lines.append("**WAITING** (all tasks waiting-for):")
            for proj, task_count, _, _ in projects_by_status["WAITING"][:5]:
                lines.append(f"- ⏳ {proj['name']}: {task_count} waiting-for items")
            lines.append("")

        # Show INCOMPLETE projects (need next actions defined)
        if projects_by_status["INCOMPLETE"]:
            lines.append("**INCOMPLETE** (no actionable next actions):")
            for proj, task_count, _, _ in projects_by_status["INCOMPLETE"][:5]:
                lines.append(f"- 🔴 {proj['name']}: needs next action defined")
            lines.append("")

        # Show SOMEDAY-MAYBE projects (excluded from health assessment)
        if someday_maybe_projects:
            lines.append("**SOMEDAY-MAYBE** (on hold, not assessed):")
            for proj, task_count in someday_maybe_projects[:5]:
                lines.append(f"- 💤 {proj['name']}: {task_count} tasks")
            if len(someday_maybe_projects) > 5:
                lines.append(f"  ... and {len(someday_maybe_projects) - 5} more")
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
                    except (ValueError, AttributeError):
                        pass
                lines.append(f"- [{proj_name}] {task['content']}{age_str}")
            lines.append("")

        # Summary stats
        lines.append("---")
        lines.append("**Summary:**")
        lines.append(f"- Total open tasks: {len(all_tasks)}")
        lines.append(f"- Completed this week: {len(completed_tasks)}")
        lines.append(f"- Overdue: {len(overdue)}")
        lines.append(f"- Due this week: {len(due_this_week)}")
        lines.append(f"- Waiting-for: {len(waiting_for)}")
        lines.append(f"- Projects: {len(projects_by_status['ACTIVE'])} active, {len(projects_by_status['STALLED'])} stalled, {len(projects_by_status['WAITING'])} waiting, {len(projects_by_status['INCOMPLETE'])} incomplete, {len(someday_maybe_projects)} someday-maybe")
        lines.append("")
        lines.append("**Recommended Actions:**")
        if overdue:
            lines.append("1. Address overdue items first")
        if projects_by_status["STALLED"]:
            lines.append("2. Make progress on stalled projects (they have next actions)")
        if projects_by_status["INCOMPLETE"]:
            lines.append("3. Define next actions for incomplete projects")
        if waiting_for:
            old_waiting = [t for t in waiting_for if t.get("created_at")]
            if old_waiting:
                lines.append("4. Check waiting-for items older than 2 weeks")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running weekly review: {str(e)}"
