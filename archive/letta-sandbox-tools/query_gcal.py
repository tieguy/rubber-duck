def query_gcal(time_range: str = "today", calendar_id: str = "primary") -> str:
    """Query Google Calendar for events.

    This tool fetches events from Google Calendar using service account auth.
    The user must have shared their calendar with the service account email.

    Args:
        time_range: One of "today", "evening" (5pm-midnight), "tomorrow", "week"
        calendar_id: Calendar ID to query (default "primary" = shared calendar)

    Call this when:
    - User asks about their schedule or calendar
    - Running morning/evening planning
    - Checking for conflicts before scheduling
    - "What's on my calendar?"
    - "Do I have anything tonight?"

    Returns:
        Formatted list of calendar events
    """
    import base64
    import json
    import os
    from datetime import datetime, timedelta

    # Check for credentials
    json_b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not json_b64:
        return "Google Calendar is not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON."

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        # Parse credentials
        json_str = base64.b64decode(json_b64).decode("utf-8")
        info = json.loads(json_str)
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )

        # Build service
        service = build("calendar", "v3", credentials=credentials)

        # Calculate time range
        now = datetime.now()

        if time_range == "today":
            time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = now.replace(hour=23, minute=59, second=59)
        elif time_range == "evening":
            time_min = now.replace(hour=17, minute=0, second=0, microsecond=0)
            time_max = now.replace(hour=23, minute=59, second=59)
        elif time_range == "tomorrow":
            tomorrow = now + timedelta(days=1)
            time_min = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = tomorrow.replace(hour=23, minute=59, second=59)
        elif time_range == "week":
            time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = time_min + timedelta(days=7)
        else:
            return f"Invalid time_range: {time_range}. Use: today, evening, tomorrow, week"

        # Format for API (RFC3339)
        time_min_str = time_min.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        time_max_str = time_max.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        # Fetch events
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min_str,
            timeMax=time_max_str,
            maxResults=25,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])

        if not events:
            return f"No events found for {time_range}."

        # Format output
        lines = [f"## Calendar: {time_range.title()}"]
        lines.append("")

        current_date = None
        for event in events:
            # Parse start time
            start = event.get("start", {})
            start_str = start.get("dateTime") or start.get("date")
            all_day = "date" in start and "dateTime" not in start

            try:
                if all_day:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                    time_display = "All day"
                else:
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    time_display = start_dt.strftime("%I:%M %p").lstrip("0")

                event_date = start_dt.date()
            except ValueError:
                time_display = start_str
                event_date = None

            # Add date header for week view
            if time_range == "week" and event_date and event_date != current_date:
                current_date = event_date
                lines.append(f"### {event_date.strftime('%A, %b %d')}")

            # Event details
            summary = event.get("summary", "(No title)")
            location = event.get("location", "")

            if location:
                lines.append(f"- **{time_display}**: {summary} @ {location}")
            else:
                lines.append(f"- **{time_display}**: {summary}")

        return "\n".join(lines)

    except ImportError as e:
        return f"Missing required library: {e}. Need google-auth and google-api-python-client."
    except Exception as e:
        return f"Error querying calendar: {str(e)}"
