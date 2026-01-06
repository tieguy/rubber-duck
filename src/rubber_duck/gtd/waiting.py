"""Waiting-for tracking for GTD workflows."""


def check_waiting() -> dict:
    """Check waiting-for items and staleness.

    Returns dict with keys: needs_followup, gentle_check, still_fresh, summary
    """
    raise NotImplementedError
