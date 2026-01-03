# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Preemption state management for autonomous work."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum


class BotStatus(Enum):
    """Bot operational states."""

    IDLE = "idle"
    WORKING = "working"
    WRAPPING_UP = "wrapping_up"


@dataclass
class BotState:
    """Current bot state."""

    status: BotStatus = BotStatus.IDLE
    current_task: str | None = None
    started_at: datetime | None = None
    preempt_requested: bool = False
    preempt_reason: str | None = None


_state = BotState()


def get_state() -> BotState:
    """Get current bot state."""
    return _state


def start_work(description: str) -> None:
    """Mark bot as working on a task."""
    _state.status = BotStatus.WORKING
    _state.current_task = description
    _state.started_at = datetime.now(UTC)


def finish_work() -> None:
    """Mark bot as idle."""
    _state.status = BotStatus.IDLE
    _state.current_task = None
    _state.started_at = None


def request_preempt(reason: str) -> None:
    """Request preemption of current work."""
    _state.preempt_requested = True
    _state.preempt_reason = reason


def clear_preempt() -> None:
    """Clear preemption request."""
    _state.preempt_requested = False
    _state.preempt_reason = None


def should_yield() -> bool:
    """Check if autonomous work should stop. Call before each task unit."""
    return _state.preempt_requested


def check_stuck() -> bool:
    """Check if stuck (working >10 min). Resets to idle if so.

    Returns:
        True if was stuck and reset, False otherwise.
    """
    if _state.status != BotStatus.WORKING or not _state.started_at:
        return False
    elapsed = (datetime.now(UTC) - _state.started_at).total_seconds()
    if elapsed > 600:  # 10 minutes
        finish_work()
        return True
    return False
