# Preemption Handling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add preemption handling so user messages interrupt autonomous work gracefully.

**Architecture:** State module tracks idle/working/wrapping_up status. Message handler checks state, sends ack, polls for idle. Autonomous work checks should_yield() before each task unit.

**Tech Stack:** Python, asyncio, pytest

---

### Task 1: Create preemption module with state management

**Files:**
- Create: `src/rubber_duck/preemption.py`
- Create: `tests/test_preemption.py`

**Step 1: Write the failing tests**

```python
# tests/test_preemption.py
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_preemption.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/rubber_duck/preemption.py
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Preemption state management for autonomous work."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    _state.started_at = datetime.now(timezone.utc)


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
    elapsed = (datetime.now(timezone.utc) - _state.started_at).total_seconds()
    if elapsed > 600:  # 10 minutes
        finish_work()
        return True
    return False
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_preemption.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add src/rubber_duck/preemption.py tests/test_preemption.py
git commit -m "feat: add preemption state management module"
```

---

### Task 2: Add stuck detection test

**Files:**
- Modify: `tests/test_preemption.py`

**Step 1: Add test for stuck detection**

```python
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
```

**Step 2: Run tests**

Run: `uv run pytest tests/test_preemption.py -v`
Expected: 10 passed

**Step 3: Commit**

```bash
git add tests/test_preemption.py
git commit -m "test: add stuck detection tests"
```

---

### Task 3: Modify bot.py to handle preemption

**Files:**
- Modify: `src/rubber_duck/bot.py`

**Step 1: Read current bot.py**

Read the file to understand current structure.

**Step 2: Add preemption handling to on_message**

Add imports at top:
```python
import asyncio
from rubber_duck.preemption import (
    get_state,
    BotStatus,
    request_preempt,
    clear_preempt,
    check_stuck,
)
```

Modify `on_message` method in `RubberDuck` class:

```python
async def on_message(self, message: discord.Message) -> None:
    """Handle incoming messages."""
    # Ignore messages from the bot itself
    if message.author == self.user:
        return

    # Only respond to DMs from the owner
    if isinstance(message.channel, discord.DMChannel):
        if message.author.id == self.owner_id:
            state = get_state()

            # Check for stuck state first
            check_stuck()

            if state.status == BotStatus.WORKING:
                # Acknowledge immediately
                await message.channel.send(
                    "One moment, I'm finishing something up..."
                )
                request_preempt(f"User message: {message.content[:50]}")

                # Poll for idle (up to 60 seconds)
                for _ in range(30):
                    await asyncio.sleep(2)
                    if get_state().status == BotStatus.IDLE:
                        break

                clear_preempt()

            await handle_message(self, message)
        else:
            logger.warning(f"Ignoring DM from non-owner: {message.author.id}")

    # Process commands if any
    await self.process_commands(message)
```

**Step 3: Verify bot still imports**

Run: `uv run python -c "from rubber_duck.bot import RubberDuck; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add src/rubber_duck/bot.py
git commit -m "feat: add preemption handling to message handler"
```

---

### Task 4: Update perch.py to use preemption

**Files:**
- Modify: `src/rubber_duck/perch.py`

**Step 1: Read current perch.py structure**

Read the file to understand current `perch_tick` function.

**Step 2: Add preemption imports and wrap work**

Add imports:
```python
from rubber_duck.preemption import start_work, finish_work, should_yield
```

Modify `perch_tick` to use preemption:

```python
async def perch_tick(bot) -> None:
    """Run a perch tick - check for maintenance work."""
    from rubber_duck.preemption import start_work, finish_work, should_yield

    now = datetime.now(timezone.utc)
    state = _load_perch_state()

    # Check last activity
    last_activity = _get_last_activity_ts()

    if not last_activity:
        await _send_debug_dm(bot, "🪺 Perch tick\n• No journal activity found")
        state["last_tick_ts"] = now.isoformat()
        _save_perch_state(state)
        return

    # Calculate gap
    gap = now - last_activity
    gap_minutes = gap.total_seconds() / 60

    if gap_minutes < GAP_MINUTES:
        await _send_debug_dm(
            bot,
            f"🪺 Perch tick\n"
            f"• Last activity: {int(gap_minutes)} min ago\n"
            f"• Action: Skipped - conversation may be active"
        )
        state["last_tick_ts"] = now.isoformat()
        _save_perch_state(state)
        return

    # Get entries since last archive
    last_archive_ts = state.get("last_archive_ts")
    entries = _get_journal_entries_since(last_archive_ts)

    if not entries:
        await _send_debug_dm(
            bot,
            f"🪺 Perch tick\n"
            f"• Last activity: {int(gap_minutes)} min ago\n"
            f"• Action: Skipped - no new entries since last archive"
        )
        state["last_tick_ts"] = now.isoformat()
        _save_perch_state(state)
        return

    # Start autonomous work
    start_work("archiving conversation")
    try:
        # Check for preemption before doing work
        if should_yield():
            await _send_debug_dm(bot, "🪺 Perch tick\n• Preempted before archiving")
            return

        # Summarize and evaluate
        summary = await _summarize_and_evaluate(entries)

        # Check again after async work
        if should_yield():
            await _send_debug_dm(bot, "🪺 Perch tick\n• Preempted after summarization")
            return

        if summary is None:
            await _send_debug_dm(
                bot,
                f"🪺 Perch tick\n"
                f"• Last activity: {int(gap_minutes)} min ago\n"
                f"• Entries since last archive: {len(entries)}\n"
                f"• Action: Skipped - trivial conversation"
            )
        else:
            # Archive the summary
            result = archive_to_memory(summary)
            logger.info(f"Archived conversation summary: {result}")

            await _send_debug_dm(
                bot,
                f"🪺 Perch tick\n"
                f"• Last activity: {int(gap_minutes)} min ago\n"
                f"• Entries since last archive: {len(entries)}\n"
                f"• Action: Archived conversation summary"
            )

        # Update state
        state["last_archive_ts"] = now.isoformat()
        state["last_tick_ts"] = now.isoformat()
        _save_perch_state(state)

    finally:
        finish_work()
```

**Step 3: Verify perch still imports**

Run: `uv run python -c "from rubber_duck.perch import perch_tick; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add src/rubber_duck/perch.py
git commit -m "feat: add preemption checks to perch tick"
```

---

### Task 5: Update bead status and close related bead

**Files:**
- None (bead management only)

**Step 1: Update rubber-duck-6qh bead**

```bash
bd update rubber-duck-6qh --status in_progress
```

**Step 2: Close rubber-duck-9rz as duplicate**

```bash
bd close rubber-duck-9rz --reason "Implemented by rubber-duck-6qh preemption handling"
```

**Step 3: Run all tests**

Run: `uv run pytest tests/test_preemption.py tests/test_weekly_conductor.py -v`
Expected: All pass

**Step 4: Close rubber-duck-6qh**

```bash
bd close rubber-duck-6qh
```

**Step 5: Push**

```bash
git push
```
