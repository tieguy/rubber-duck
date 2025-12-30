def run_end_of_day_review() -> str:
    """Run the end-of-day review workflow.

    This tool reviews today's work, checks evening calendar, and prepares for tomorrow:
    1. Show remaining evening calendar events
    2. Identify tasks that were due today (did they get done?)
    3. Suggest rescheduling for slipped tasks
    4. Preview tomorrow's calendar commitments
    5. Generate priority-ordered list for tomorrow

    Call this when the user asks for:
    - "End of day review"
    - "Wrap up my day"
    - "What do I need to do tomorrow?"
    - "Review my tasks"
    - 5pm nudge / evening check-in

    Returns:
        End-of-day summary with calendar events and suggestions for tomorrow
    """
    import base64
    import json
    import os
    from datetime import date, datetime, timedelta

    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot run end-of-day review."

    # Helper to fetch calendar events
    def get_calendar_events(time_min, time_max):
        """Fetch calendar events in a time range if Google Calendar is configured."""
        gcal_creds = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not gcal_creds:
            return None

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            json_str = base64.b64decode(gcal_creds).decode("utf-8")
            info = json.loads(json_str)
            credentials = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            )
            service = build("calendar", "v3", credentials=credentials)

            time_min_str = time_min.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
            time_max_str = time_max.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

            events_result = service.events().list(
                calendarId="primary",
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=20,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            return events_result.get("items", [])
        except Exception:
            return None

    def format_calendar_event(event):
        """Format a calendar event for display."""
        start = event.get("start", {})
        start_str = start.get("dateTime") or start.get("date")
        all_day = "date" in start and "dateTime" not in start

        if all_day:
            time_display = "All day"
        else:
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                time_display = start_dt.strftime("%I:%M %p").lstrip("0")
            except ValueError:
                time_display = start_str

        summary = event.get("summary", "(No title)")
        location = event.get("location", "")
        if location:
            return f"- **{time_display}**: {summary} @ {location}"
        else:
            return f"- **{time_display}**: {summary}"

    try:
        # Get all open tasks
        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        all_tasks = response.json()

        today = date.today()

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

        # Evening calendar (5pm to midnight)
        evening_start = now.replace(hour=17, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59)
        evening_events = get_calendar_events(evening_start, end_of_day)

        if evening_events:
            lines.append("### Tonight's Calendar")
            for event in evening_events:
                lines.append(format_calendar_event(event))
            lines.append("")
        elif evening_events is not None:
            lines.append("### Tonight's Calendar")
            lines.append("*No evening events - free to work on tasks or relax*")
            lines.append("")

        # Today's incomplete work
        if due_today_incomplete or overdue:
            lines.append("### Needs Rescheduling")
            lines.append("*These were due today/earlier but still open:*")
            for task in due_today_incomplete[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']} -> suggest: tomorrow")
            for task, days in overdue[:5]:
                task_line = f"- [ID:{task['id']}] {task['content']}"
                lines.append(f"{task_line} ({abs(days)}d overdue) -> tomorrow AM")
            lines.append("")
            lines.append("*Use update_todoist_task to reschedule these.*")
            lines.append("")

        # Tomorrow's calendar preview
        next_day = now + timedelta(days=1)
        tomorrow_start = next_day.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_end = next_day.replace(hour=23, minute=59, second=59)
        tomorrow_events = get_calendar_events(tomorrow_start, tomorrow_end)

        if tomorrow_events:
            lines.append("### Tomorrow's Calendar")
            for event in tomorrow_events:
                lines.append(format_calendar_event(event))
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
                        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        age = (today - created_dt.date()).days
                        age_str = f" ({age}d ago)"
                    except ValueError:
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
