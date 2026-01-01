# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Morning planning workflow for GTD-based daily planning."""

import base64
import json
import os
from datetime import date, datetime, timedelta

import requests


def _get_calendar_events() -> list | None:
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

        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min.strftime("%Y-%m-%dT%H:%M:%SZ"),
            timeMax=time_max.strftime("%Y-%m-%dT%H:%M:%SZ"),
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        return events_result.get("items", [])
    except Exception:
        return None


def _parse_time_display(start_str: str) -> str:
    """Parse datetime string into display format."""
    try:
        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        return start_dt.strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return start_str


def _format_calendar_section(events: list | None) -> list[str]:
    """Format calendar events into output lines."""
    if events is None:
        return []  # Calendar not configured

    if not events:
        return ["### Calendar", "*No events scheduled for today*", ""]

    lines = ["### Calendar (Fixed Commitments)"]
    for event in events:
        start = event.get("start", {})
        start_str = start.get("dateTime") or start.get("date")
        is_all_day = "date" in start and "dateTime" not in start

        time_display = "All day" if is_all_day else _parse_time_display(start_str)
        summary = event.get("summary", "(No title)")
        location = event.get("location", "")

        if location:
            lines.append(f"- **{time_display}**: {summary} @ {location}")
        else:
            lines.append(f"- **{time_display}**: {summary}")

    lines.append("")
    return lines


def _categorize_tasks(all_tasks: list, today: date) -> dict:
    """Categorize tasks by urgency level."""
    categories = {
        "overdue": [],
        "due_today": [],
        "due_this_week": [],
        "scheduled_today": [],
        "no_date": [],
    }

    for task in all_tasks:
        due = task.get("due")
        if not due:
            categories["no_date"].append(task)
            continue

        due_date_str = due.get("date", "")[:10]
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            days_until = (due_date - today).days

            if days_until < 0:
                categories["overdue"].append((task, days_until))
            elif days_until == 0:
                categories["due_today"].append(task)
            elif days_until <= 7:
                categories["due_this_week"].append((task, days_until))

            if due.get("datetime") and due_date == today:
                categories["scheduled_today"].append(task)
        except ValueError:
            categories["no_date"].append(task)

    # Sort by urgency
    categories["overdue"].sort(key=lambda x: x[1])
    categories["due_this_week"].sort(key=lambda x: x[1])

    return categories


def _select_top_priorities(categories: dict, limit: int = 3) -> list:
    """Select top priority tasks using GTD algorithm."""
    top = []
    sources = [
        [t for t, _ in categories["overdue"]],
        categories["due_today"],
        [t for t, _ in categories["due_this_week"]],
    ]

    for source in sources:
        for task in source:
            if len(top) >= limit:
                return top
            if task not in top:
                top.append(task)

    return top


def _format_task_time(task: dict) -> str:
    """Format scheduled task time for display."""
    time_str = task.get("due", {}).get("datetime", "")
    if not time_str:
        return ""
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt.strftime("%I:%M %p")
    except ValueError:
        return time_str


def run_morning_planning() -> str:
    """Run the morning planning workflow.

    This tool queries Todoist AND Google Calendar to generate a prioritized,
    time-blocked plan for TODAY based on GTD principles:
    1. Check calendar for fixed commitments (meetings, events)
    2. Identify overdue and due-today tasks (highest priority)
    3. Check for tasks that slipped from yesterday
    4. Apply 3-step priority algorithm (urgency -> feasibility -> strategic value)
    5. Generate realistic schedule around calendar blocks

    Returns:
        Formatted morning plan with calendar events, TOP 3 priorities, and time blocks
    """
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        return "Todoist is not configured. Cannot run morning planning."

    try:
        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        all_tasks = response.json()

        today = date.today()
        now = datetime.now()
        categories = _categorize_tasks(all_tasks, today)

        # Build output
        lines = [
            f"## Morning Planning - {today.strftime('%A, %B %d')}",
            f"*Generated at {now.strftime('%I:%M %p')}*",
            "",
        ]

        # Calendar section
        lines.extend(_format_calendar_section(_get_calendar_events()))

        # Overdue alerts
        if categories["overdue"]:
            lines.append("### OVERDUE (Address First)")
            for task, days in categories["overdue"][:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']} ({abs(days)} days overdue)")
            lines.append("")

        # TOP 3 priorities
        lines.append("### TODAY'S TOP 3 PRIORITIES")
        top_3 = _select_top_priorities(categories)

        if top_3:
            for i, task in enumerate(top_3, 1):
                due = task.get("due", {})
                due_info = f" (due: {due.get('string', due.get('date', ''))})" if due else ""
                lines.append(f"{i}. [ID:{task['id']}] {task['content']}{due_info}")
        else:
            lines.append("*No urgent tasks - consider strategic work or clearing backlog*")
        lines.append("")

        # Scheduled tasks
        scheduled = categories["scheduled_today"]
        if scheduled:
            lines.append("### Scheduled for Today")
            for task in scheduled:
                time_str = _format_task_time(task)
                lines.append(f"- {time_str}: [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Remaining due today
        remaining = [t for t in categories["due_today"] if t not in scheduled and t not in top_3]
        if remaining:
            lines.append("### Also Due Today")
            for task in remaining[:5]:
                lines.append(f"- [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Coming this week
        upcoming = [(t, d) for t, d in categories["due_this_week"] if t not in top_3]
        if upcoming:
            lines.append("### Coming This Week")
            for task, days in upcoming[:5]:
                day_name = (today + timedelta(days=days)).strftime("%A")
                lines.append(f"- {day_name}: [ID:{task['id']}] {task['content']}")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append(
            f"*{len(categories['overdue'])} overdue | {len(categories['due_today'])} due today | "
            f"{len(categories['due_this_week'])} due this week | {len(categories['no_date'])} unscheduled*"
        )

        return "\n".join(lines)

    except Exception as e:
        return f"Error running morning planning: {str(e)}"
