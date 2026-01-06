"""Calendar integration for GTD workflows."""


def calendar_today() -> dict:
    """Get today's calendar events.

    Returns dict with keys: events, all_day, summary
    """
    raise NotImplementedError


def calendar_range(days_back: int = 0, days_forward: int = 7) -> dict:
    """Get calendar events in a date range.

    Returns dict with keys: events, all_day, summary
    """
    raise NotImplementedError
