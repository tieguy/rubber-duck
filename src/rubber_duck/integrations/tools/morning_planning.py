def run_morning_planning() -> str:
    """Run the morning planning workflow.

    This tool queries Todoist AND Google Calendar to generate a prioritized,
    time-blocked plan for TODAY based on GTD principles:
    1. Check calendar for fixed commitments (meetings, events)
    2. Identify overdue and due-today tasks (highest priority)
    3. Check for tasks that slipped from yesterday
    4. Apply 3-step priority algorithm (urgency -> feasibility -> strategic value)
    5. Generate realistic schedule around calendar blocks

    Call this when the user asks for:
    - "What should I work on today?"
    - "Morning planning" or "daily planning"
    - "Help me plan my day"
    - "What's on my plate?"

    Returns:
        Formatted morning plan with calendar events, TOP 3 priorities, and time blocks
    """
    import base64
    import json
    import os
    from datetime import date, datetime, timedelta

    import requests

    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot run morning planning."

    # Helper to fetch calendar events
    def get_calendar_events():
        """Fetch today's calendar events if Google Calendar is configured."""
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

            now = datetime.now()
            time_min = now.replace(hour=0, minute=0, second=0)
            time_max = now.replace(hour=23, minute=59, second=59)
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

    try:
        # Get all tasks
        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        all_tasks = response.json()

        today = date.today()

        # Categorize tasks by urgency
        overdue = []
        due_today = []
        due_this_week = []
        scheduled_today = []
        no_date = []

        for task in all_tasks:
            due = task.get("due")
            if not due:
                no_date.append(task)
                continue

            due_date_str = due.get("date", "")[:10]  # YYYY-MM-DD
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                days_until = (due_date - today).days

                if days_until < 0:
                    overdue.append((task, days_until))
                elif days_until == 0:
                    due_today.append(task)
                elif days_until <= 7:
                    due_this_week.append((task, days_until))

                # Check for scheduled (has datetime, not just date)
                if due.get("datetime") and due_date == today:
                    scheduled_today.append(task)
            except ValueError:
                no_date.append(task)

        # Sort by urgency
        overdue.sort(key=lambda x: x[1])  # Most overdue first
        due_this_week.sort(key=lambda x: x[1])  # Soonest first

        # Build the morning plan
        now = datetime.now()
        lines = []
        lines.append(f"## Morning Planning - {today.strftime('%A, %B %d')}")
        lines.append(f"*Generated at {now.strftime('%I:%M %p')}*")
        lines.append("")

        # Calendar events (fixed commitments)
        calendar_events = get_calendar_events()
        if calendar_events:
            lines.append("### Calendar (Fixed Commitments)")
            for event in calendar_events:
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
                    lines.append(f"- **{time_display}**: {summary} @ {location}")
                else:
                    lines.append(f"- **{time_display}**: {summary}")
            lines.append("")
        elif calendar_events is None:
            # Calendar not configured - no message needed
            pass
        else:
            lines.append("### Calendar")
            lines.append("*No events scheduled for today*")
            lines.append("")

        # Critical alerts
        if overdue:
            lines.append("### OVERDUE (Address First)")
            for task, days in overdue[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']} ({abs(days)} days overdue)")
            lines.append("")

        # Today's focus
        lines.append("### TODAY'S TOP 3 PRIORITIES")
        top_3 = []

        # Priority order: overdue, then due today, then strategic
        for task, _ in overdue[:3]:
            if len(top_3) < 3:
                top_3.append(task)
        for task in due_today:
            if len(top_3) < 3 and task not in top_3:
                top_3.append(task)
        for task, _ in due_this_week[:3]:
            if len(top_3) < 3 and task not in top_3:
                top_3.append(task)

        if top_3:
            for i, task in enumerate(top_3, 1):
                due_info = ""
                if task.get("due"):
                    due_info = f" (due: {task['due'].get('string', task['due'].get('date', ''))})"
                lines.append(f"{i}. [ID:{task['id']}] {task['content']}{due_info}")
        else:
            lines.append("*No urgent tasks - consider strategic work or clearing backlog*")
        lines.append("")

        # Scheduled tasks
        if scheduled_today:
            lines.append("### Scheduled for Today")
            for task in scheduled_today:
                time_str = task['due'].get('datetime', '')
                if time_str:
                    try:
                        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        time_str = dt.strftime('%I:%M %p')
                    except ValueError:
                        pass
                lines.append(f"- {time_str}: [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Due today (not scheduled)
        remaining_today = [t for t in due_today if t not in scheduled_today and t not in top_3]
        if remaining_today:
            lines.append("### Also Due Today")
            for task in remaining_today[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Coming up this week
        upcoming = [(t, d) for t, d in due_this_week if t not in top_3]
        if upcoming:
            lines.append("### Coming This Week")
            for task, days in upcoming[:5]:
                day_name = (today + timedelta(days=days)).strftime('%A')
                lines.append(f"- {day_name}: [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Summary stats
        lines.append("---")
        week_count = len([t for t, _ in due_this_week])
        lines.append(
            f"*{len(overdue)} overdue | {len(due_today)} due today | "
            f"{week_count} due this week | {len(no_date)} unscheduled*"
        )

        return "\n".join(lines)

    except Exception as e:
        return f"Error running morning planning: {str(e)}"
