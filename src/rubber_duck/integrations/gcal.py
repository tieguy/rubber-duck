# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Google Calendar integration for Rubber Duck using service account auth."""

import asyncio
import base64
import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Credentials can be provided as:
# 1. GOOGLE_SERVICE_ACCOUNT_JSON - Base64-encoded JSON key
# 2. GOOGLE_SERVICE_ACCOUNT_FILE - Path to JSON key file


def get_credentials():
    """Get Google service account credentials.

    Returns None if credentials are not configured.
    """
    try:
        from google.oauth2 import service_account

        # Try base64-encoded JSON first (preferred for secrets)
        json_b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if json_b64:
            try:
                json_str = base64.b64decode(json_b64).decode("utf-8")
                info = json.loads(json_str)
                return service_account.Credentials.from_service_account_info(
                    info,
                    scopes=["https://www.googleapis.com/auth/calendar.readonly"],
                )
            except Exception as e:
                logger.error(f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
                return None

        # Try file path
        json_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
        if json_file:
            return service_account.Credentials.from_service_account_file(
                json_file,
                scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            )

        logger.warning("No Google service account credentials configured")
        return None

    except ImportError:
        logger.warning("google-auth not installed, Google Calendar disabled")
        return None


def get_calendar_service():
    """Get a Google Calendar API service client.

    Returns None if credentials are not configured.
    """
    credentials = get_credentials()
    if not credentials:
        return None

    try:
        from googleapiclient.discovery import build

        return build("calendar", "v3", credentials=credentials)
    except ImportError:
        logger.warning("google-api-python-client not installed")
        return None
    except Exception as e:
        logger.exception(f"Failed to build Calendar service: {e}")
        return None


async def get_events(
    calendar_id: str = "primary",
    time_min: datetime | None = None,
    time_max: datetime | None = None,
    max_results: int = 20,
) -> list[dict]:
    """Get calendar events in a time range.

    Args:
        calendar_id: Calendar ID (default "primary" for the shared calendar)
        time_min: Start of time range (default: now)
        time_max: End of time range (default: end of today)
        max_results: Maximum number of events to return

    Returns:
        List of event dicts with keys: id, summary, start, end, location, description
    """
    service = get_calendar_service()
    if not service:
        return []

    if time_min is None:
        time_min = datetime.now()
    if time_max is None:
        time_max = datetime.now().replace(hour=23, minute=59, second=59)

    try:
        # Convert to RFC3339 format
        if time_min.tzinfo is None:
            time_min_str = time_min.isoformat() + "Z"
        else:
            time_min_str = time_min.isoformat()
        if time_max.tzinfo is None:
            time_max_str = time_max.isoformat() + "Z"
        else:
            time_max_str = time_max.isoformat()

        # Wrap sync call to avoid blocking event loop
        events_result = await asyncio.to_thread(
            lambda: service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        return [
            {
                "id": e.get("id"),
                "summary": e.get("summary", "(No title)"),
                "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                "location": e.get("location"),
                "description": e.get("description"),
                "all_day": "date" in e.get("start", {}),
            }
            for e in events
        ]
    except Exception as e:
        logger.exception(f"Error fetching calendar events: {e}")
        return []


async def get_today_events(calendar_id: str = "primary") -> list[dict]:
    """Get all events for today."""
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return await get_events(calendar_id, start_of_day, end_of_day)


async def get_evening_events(calendar_id: str = "primary") -> list[dict]:
    """Get events from 5pm to midnight today."""
    now = datetime.now()
    evening_start = now.replace(hour=17, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return await get_events(calendar_id, evening_start, end_of_day)


async def get_week_events(calendar_id: str = "primary") -> list[dict]:
    """Get events for the next 7 days."""
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_day + timedelta(days=7)
    return await get_events(calendar_id, start_of_day, end_of_week, max_results=50)
