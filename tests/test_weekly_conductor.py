# tests/test_weekly_conductor.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Tests for weekly review conductor."""

from unittest.mock import patch

import pytest

from rubber_duck.integrations.tools.weekly_conductor import (
    REVIEW_STEPS,
    _load_session,
    _save_session,
    weekly_review_conductor,
)


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary state directory."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    session_file = state_dir / "weekly_review_session.json"
    with patch(
        "rubber_duck.integrations.tools.weekly_conductor.STATE_PATH",
        session_file,
    ):
        yield state_dir


def test_start_creates_session(temp_state_dir):
    """Starting a review creates session state."""
    result = weekly_review_conductor("start")

    assert "Step 1" in result
    assert "calendar" in result.lower()

    session = _load_session()
    assert session is not None
    assert session["current_step"] == "calendar_review"
    assert session["completed_steps"] == []


def test_status_shows_current_step(temp_state_dir):
    """Status returns current step info."""
    weekly_review_conductor("start")
    result = weekly_review_conductor("status")

    assert "Step 1" in result
    assert "calendar" in result.lower()


def test_next_advances_step(temp_state_dir):
    """Next advances to the next step."""
    weekly_review_conductor("start")
    result = weekly_review_conductor("next")

    assert "Step 2" in result
    assert "deadline" in result.lower()

    session = _load_session()
    assert session["current_step"] == "deadline_scan"
    assert "calendar_review" in session["completed_steps"]


def test_next_after_final_step_completes(temp_state_dir):
    """Next after final step completes the review."""
    weekly_review_conductor("start")

    # Advance through all steps
    for _ in range(len(REVIEW_STEPS) - 1):
        weekly_review_conductor("next")

    result = weekly_review_conductor("next")

    assert "complete" in result.lower()
    assert _load_session() is None


def test_complete_ends_session(temp_state_dir):
    """Complete ends the session."""
    weekly_review_conductor("start")
    weekly_review_conductor("next")
    result = weekly_review_conductor("complete")

    assert "complete" in result.lower()
    assert _load_session() is None


def test_abandon_clears_session(temp_state_dir):
    """Abandon clears the session without completing."""
    weekly_review_conductor("start")
    result = weekly_review_conductor("abandon")

    assert "abandon" in result.lower() or "cleared" in result.lower()
    assert _load_session() is None


def test_status_with_no_session(temp_state_dir):
    """Status with no session returns helpful message."""
    result = weekly_review_conductor("status")

    assert "no active session" in result.lower() or "start" in result.lower()


def test_stale_session_auto_clears(temp_state_dir):
    """Session older than 24 hours is auto-cleared on start."""
    from datetime import UTC, datetime, timedelta

    # Create stale session
    stale_time = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    session = {
        "started_at": stale_time,
        "current_step": "deadline_scan",
        "completed_steps": ["calendar_review"],
    }
    _save_session(session)

    result = weekly_review_conductor("start")

    assert "Step 1" in result  # Started fresh
    session = _load_session()
    assert session["current_step"] == "calendar_review"
