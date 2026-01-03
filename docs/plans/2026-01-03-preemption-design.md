# Preemption Handling Design

Date: 2026-01-03

## Overview

Handle user messages arriving while autonomous work is in progress. The bot pauses gracefully, responds to the user, then the next scheduled tick re-identifies work if needed.

Inspired by [Bud](https://github.com/vthunder/bud).

## Goals

- User messages always take priority over autonomous work
- Instant acknowledgment ("One moment...") so user knows bot isn't broken
- Graceful stop at task boundaries, not mid-operation
- Simple: no resume prompts, no timers, no persistence

## States

Three states: `idle`, `working`, `wrapping_up`

| State | Meaning |
|-------|---------|
| `idle` | Default. Waiting for user or scheduled tick. |
| `working` | Autonomous work in progress. |
| `wrapping_up` | Preemption requested, finishing current task unit. |

## Preemption Flow

```
User sends message
  → on_message checks state
  → If WORKING:
      → Send "One moment, I'm finishing something up..."
      → Set preempt_requested = True
      → Poll every 2s for up to 60s waiting for IDLE
      → Clear preempt flag
  → Handle message normally
```

Autonomous work:
```
start_work("description")
try:
    for item in items:
        if should_yield():
            return  # Stop gracefully
        await process(item)
finally:
    finish_work()
```

## Safety: Stuck Detection

If `status == WORKING` for more than 10 minutes, auto-reset to `IDLE`. Prevents stuck state from blocking user messages forever.

Checked at start of `on_message` before other logic.

## Implementation

### File: `src/rubber_duck/preemption.py`

```python
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class BotStatus(Enum):
    IDLE = "idle"
    WORKING = "working"
    WRAPPING_UP = "wrapping_up"


@dataclass
class BotState:
    status: BotStatus = BotStatus.IDLE
    current_task: str | None = None
    started_at: datetime | None = None
    preempt_requested: bool = False
    preempt_reason: str | None = None


_state = BotState()


def get_state() -> BotState:
    return _state


def start_work(description: str):
    _state.status = BotStatus.WORKING
    _state.current_task = description
    _state.started_at = datetime.now(timezone.utc)


def finish_work():
    _state.status = BotStatus.IDLE
    _state.current_task = None
    _state.started_at = None


def request_preempt(reason: str):
    _state.preempt_requested = True
    _state.preempt_reason = reason


def clear_preempt():
    _state.preempt_requested = False
    _state.preempt_reason = None


def should_yield() -> bool:
    """Check before each tool call. Returns True if should stop."""
    return _state.preempt_requested


def check_stuck() -> bool:
    """Returns True if stuck (working >10 min). Resets to idle if so."""
    if _state.status != BotStatus.WORKING or not _state.started_at:
        return False
    elapsed = (datetime.now(timezone.utc) - _state.started_at).total_seconds()
    if elapsed > 600:  # 10 minutes
        finish_work()
        return True
    return False
```

### Modified: `src/rubber_duck/bot.py`

```python
import asyncio
from rubber_duck.preemption import (
    get_state, BotStatus, request_preempt, clear_preempt, check_stuck
)

async def on_message(self, message: discord.Message):
    if message.author == self.user:
        return

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

            # Handle message normally
            await handle_message(self, message)
```

### Pattern for Autonomous Work

```python
from rubber_duck.preemption import start_work, finish_work, should_yield

async def do_autonomous_work(bot):
    items = identify_work()
    if not items:
        return

    start_work(f"processing {len(items)} items")

    try:
        for item in items:
            if should_yield():
                return  # Stop gracefully, next tick re-finds work

            await process_item(bot, item)

    finally:
        finish_work()
```

## What This Doesn't Do

- **No resume prompts** - Work stops, next tick re-identifies it
- **No state persistence** - Restart loses state (YAGNI)
- **No budget tracking** - Separate concern (see rubber-duck-2dc)

## Files Changed

- **New:** `src/rubber_duck/preemption.py`
- **Modify:** `src/rubber_duck/bot.py` (on_message handler)
- **Modify:** `src/rubber_duck/perch.py` (use should_yield pattern)
- **Test:** `tests/test_preemption.py`

## Related

- rubber-duck-2dc: API budget tracking (feeds into should_yield later)
- rubber-duck-9rz: Explicit working/idle state machine (this implements it)
