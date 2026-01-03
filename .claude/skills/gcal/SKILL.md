---
name: google-calendar
description: Query Google Calendar events. Use when user asks about schedule, meetings, appointments, or calendar.
allowed-tools: Bash(python:*), Bash(uv:*)
---

# Google Calendar

Query the user's Google Calendar events.

## Query Events

Today's events:
```bash
uv run python -m rubber_duck.cli.tools gcal query --range today
```

Options:
- `--range today` - today's events
- `--range tomorrow` - tomorrow's events
- `--range week` - this week's events

## Output Format

```json
{
  "success": true,
  "data": [
    {"summary": "Meeting", "start": "2026-01-03T10:00:00", "end": "2026-01-03T11:00:00"}
  ]
}
```
