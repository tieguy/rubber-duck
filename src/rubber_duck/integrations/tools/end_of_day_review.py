def run_end_of_day_review() -> str:
    """Run the end-of-day review workflow.

    This tool reviews today's work and prepares for tomorrow:
    1. Identify tasks that were due today (did they get done?)
    2. Suggest rescheduling for slipped tasks
    3. Generate priority-ordered list for tomorrow

    Call this when the user asks for:
    - "End of day review"
    - "Wrap up my day"
    - "What do I need to do tomorrow?"
    - "Review my tasks"

    Returns:
        End-of-day summary with suggestions for tomorrow
    """
    import os
    import requests
    from datetime import datetime, date, timedelta

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot run end-of-day review."

    try:
        # Get all open tasks
        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        all_tasks = response.json()

        today = date.today()
        tomorrow = today + timedelta(days=1)
        today_str = today.isoformat()
        tomorrow_str = tomorrow.isoformat()

        # Categorize
        overdue = []
        due_today_incomplete = []
        due_tomorrow = []
        due_this_week = []
        waiting_for = []

        for task in all_tasks:
            # Check for waiting-for label
            labels = task.get("labels", [])
            if "waiting" in labels or "waiting-for" in labels:
                waiting_for.append(task)
                continue

            due = task.get("due")
            if not due:
                continue

            due_date_str = due.get("date", "")[:10]
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                days_until = (due_date - today).days

                if days_until < 0:
                    overdue.append((task, days_until))
                elif days_until == 0:
                    due_today_incomplete.append(task)
                elif days_until == 1:
                    due_tomorrow.append(task)
                elif days_until <= 7:
                    due_this_week.append((task, days_until))
            except ValueError:
                pass

        # Sort
        overdue.sort(key=lambda x: x[1])

        # Build review
        now = datetime.now()
        lines = []
        lines.append(f"## End-of-Day Review - {today.strftime('%A, %B %d')}")
        lines.append(f"*Generated at {now.strftime('%I:%M %p')}*")
        lines.append("")

        # Today's incomplete work
        if due_today_incomplete or overdue:
            lines.append("### Needs Rescheduling")
            lines.append("*These were due today/earlier but still open:*")
            for task in due_today_incomplete[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']} -> suggest: tomorrow")
            for task, days in overdue[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']} ({abs(days)}d overdue) -> suggest: tomorrow AM")
            lines.append("")
            lines.append("*Use update_todoist_task to reschedule these.*")
            lines.append("")

        # Tomorrow's priorities
        lines.append("### TOMORROW'S PRIORITIES")

        # Build tomorrow's list: rescheduled today + already due tomorrow
        tomorrow_candidates = []
        for task in due_today_incomplete:
            tomorrow_candidates.append((task, "rescheduled from today"))
        for task, _ in overdue:
            tomorrow_candidates.append((task, "overdue"))
        for task in due_tomorrow:
            tomorrow_candidates.append((task, "due tomorrow"))

        if tomorrow_candidates:
            for i, (task, reason) in enumerate(tomorrow_candidates[:7], 1):
                lines.append(f"{i}. [ID:{task['id']}] {task['content']} ({reason})")
        else:
            lines.append("*No urgent tasks for tomorrow - check projects for strategic work*")
        lines.append("")

        # Waiting-for check
        if waiting_for:
            lines.append("### Waiting-For Items")
            lines.append("*Consider following up on these:*")
            for task in waiting_for[:5]:
                created = task.get("created_at", "")
                if created:
                    try:
                        created_date = datetime.fromisoformat(created.replace('Z', '+00:00')).date()
                        age = (today - created_date).days
                        age_str = f" ({age}d ago)"
                    except:
                        age_str = ""
                else:
                    age_str = ""
                lines.append(f"- [ID:{task['id']}] {task['content']}{age_str}")
            lines.append("")

        # Coming this week
        if due_this_week:
            lines.append("### Coming This Week")
            for task, days in due_this_week[:5]:
                day_name = (today + timedelta(days=days)).strftime('%A')
                lines.append(f"- {day_name}: [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append("**Quick Actions:**")
        lines.append("1. Reschedule slipped tasks to tomorrow")
        lines.append("2. Mark any secretly-completed tasks as done")
        lines.append("3. Add any new tasks that came up today")

        return "\n".join(lines)

    except Exception as e:
        return f"Error running end-of-day review: {str(e)}"
