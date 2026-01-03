# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Tests for preemption state management."""

from datetime import datetime, timedelta, timezone

import pytest

from rubber_duck.preemption import (
    BotStatus,
    get_state,
    start_work,
    finish_work,
    request_preempt,
    clear_preempt,
    should_yield,
    check_stuck,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    finish_work()
    clear_preempt()
    yield


def test_initial_state_is_idle():
    """Fresh state is idle with no task."""
    state = get_state()
    assert state.status == BotStatus.IDLE
    assert state.current_task is None


def test_start_work_sets_working():
    """Starting work transitions to WORKING."""
    start_work("test task")
    state = get_state()
    assert state.status == BotStatus.WORKING
    assert state.current_task == "test task"
    assert state.started_at is not None


def test_finish_work_returns_to_idle():
    """Finishing work returns to IDLE."""
    start_work("test task")
    finish_work()
    state = get_state()
    assert state.status == BotStatus.IDLE
    assert state.current_task is None


def test_should_yield_false_when_no_preemption():
    """should_yield returns False when not preempted."""
    start_work("test task")
    assert should_yield() is False


def test_should_yield_true_when_preempted():
    """should_yield returns True when preemption requested."""
    start_work("test task")
    request_preempt("user message")
    assert should_yield() is True


def test_clear_preempt_resets_flag():
    """Clearing preempt resets the flag."""
    request_preempt("user message")
    clear_preempt()
    assert should_yield() is False
    assert get_state().preempt_reason is None


def test_check_stuck_resets_after_10_minutes():
    """Stuck detection resets state after 10 minutes."""
    from rubber_duck.preemption import _state

    start_work("long task")
    # Simulate 11 minutes ago
    _state.started_at = datetime.now(timezone.utc) - timedelta(minutes=11)

    assert check_stuck() is True
    assert get_state().status == BotStatus.IDLE


def test_check_stuck_false_when_recent():
    """Stuck detection returns False for recent work."""
    start_work("recent task")
    assert check_stuck() is False
    assert get_state().status == BotStatus.WORKING


def test_check_stuck_false_when_idle():
    """Stuck detection returns False when idle."""
    assert check_stuck() is False
