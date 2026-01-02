# Perch Ticks Design

Date: 2026-01-02

## Overview

A periodic background task that wakes up hourly to do maintenance work. First implementation focuses on archiving significant conversations to long-term memory.

## Key Decisions

- Runs every hour via APScheduler interval trigger
- Notifies on each tick for now (debugging), configurable to silent later
- Checks for 30+ min conversation gap
- Summarizes and asks Claude to judge significance
- Archives if significant, skips if trivial

## Architecture

**New file:** `src/rubber_duck/perch.py`

```
perch_tick(bot)
├── Check last journal timestamp
├── If gap < 30 min → skip (conversation still active)
├── If gap ≥ 30 min → summarize_and_archive()
│   ├── Read journal entries since last archive
│   ├── Call Claude: "Summarize. If trivial, respond SKIP"
│   ├── If SKIP → log, don't archive
│   └── If significant → call archive_to_memory()
└── Send debug DM with status
```

**Scheduler changes:** Add interval job alongside existing cron nudges

```python
scheduler.add_job(
    perch_tick,
    trigger=IntervalTrigger(hours=1),
    args=[bot],
    id="perch_tick",
)
```

## Summarization Flow

**Input:** Journal entries since last archive (user_message + assistant_message only)

**Prompt to Claude (Haiku for cost):**
```
Summarize this conversation. Focus on:
- Decisions made
- Preferences expressed
- Work completed
- Context that would be useful later

If the conversation was trivial (greetings, confirmations,
no meaningful content), respond with just: SKIP

Conversation:
{entries}
```

**Output handling:**
- Response starts with "SKIP" → log "No significant content", don't archive
- Otherwise → call `archive_to_memory(summary)`

**Debug DM format:**
```
🪺 Perch tick
• Last activity: 47 min ago
• Entries since last archive: 4
• Action: Archived conversation summary
```

## State Tracking

**state/perch_state.json:**
```json
{
  "last_archive_ts": "2026-01-02T15:30:00Z",
  "last_tick_ts": "2026-01-02T16:00:00Z"
}
```

## Future Configuration (not implementing now)

```yaml
perch:
  interval_hours: 1
  notify: true  # false for silent mode
  gap_minutes: 30
```

For now, hardcoded constants in `perch.py`.

## Files

1. **New:** `src/rubber_duck/perch.py` - perch_tick(), summarize_and_archive()
2. **Modify:** `src/rubber_duck/scheduler.py` - add interval job
3. **New:** `state/perch_state.json` - created on first run
