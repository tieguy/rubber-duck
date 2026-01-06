"""Calendar integration for GTD workflows."""

import base64
import json
import os
from datetime import UTC, datetime, timedelta


def _get_calendar_service():
    """Get Google Calendar service if configured."""
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
        return build("calendar", "v3", credentials=credentials)
    except Exception:
        return None


def _format_events(events: list) -> dict:
    """Format calendar events into structured output."""
    timed = []
    all_day = []

    for event in events:
        start = event.get("start", {})
        end = event.get("end", {})

        is_all_day = "date" in start and "dateTime" not in start

        if is_all_day:
            all_day.append({
                "summary": event.get("summary", "(No title)"),
            })
        else:
            start_dt = start.get("dateTime", "")
            end_dt = end.get("dateTime", "")

            # Extract time portion
            start_time = ""
            end_time = ""
            if start_dt:
                try:
                    dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
                    start_time = dt.strftime("%H:%M")
                except ValueError:
                    start_time = start_dt
            if end_dt:
                try:
                    dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
                    end_time = dt.strftime("%H:%M")
                except ValueError:
                    end_time = end_dt

            timed.append({
                "summary": event.get("summary", "(No title)"),
                "start": start_time,
                "end": end_time,
                "location": event.get("location"),
            })

    return {
        "events": timed,
        "all_day": all_day,
        "summary": {
            "timed_events": len(timed),
            "all_day": len(all_day),
        },
    }


def _fetch_events(time_min: datetime, time_max: datetime) -> list:
    """Fetch events in date range from Google Calendar."""
    service = _get_calendar_service()
    if not service:
        return []

    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min.strftime("%Y-%m-%dT%H:%M:%SZ"),
            timeMax=time_max.strftime("%Y-%m-%dT%H:%M:%SZ"),
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        return events_result.get("items", [])
    except Exception:
        return []


def calendar_today() -> dict:
    """Get today's calendar events.

    Returns:
        Dict with events, all_day lists and summary.
    """
    now = datetime.now(UTC)
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = now.replace(hour=23, minute=59, second=59, microsecond=0)

    events = _fetch_events(time_min, time_max)
    result = _format_events(events)
    result["generated_at"] = datetime.now(UTC).isoformat()

    return result


def calendar_range(days_back: int = 0, days_forward: int = 7) -> dict:
    """Get calendar events in a date range.

    Args:
        days_back: Number of days in the past to include
        days_forward: Number of days in the future to include

    Returns:
        Dict with events, all_day lists and summary.
    """
    now = datetime.now(UTC)
    time_min = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = now + timedelta(days=days_forward)
    time_max = end_day.replace(hour=23, minute=59, second=59, microsecond=0)

    events = _fetch_events(time_min, time_max)
    result = _format_events(events)
    result["generated_at"] = datetime.now(UTC).isoformat()
    result["range"] = {
        "from": time_min.strftime("%Y-%m-%d"),
        "to": time_max.strftime("%Y-%m-%d"),
    }

    return result
