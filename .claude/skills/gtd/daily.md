---
name: planning-daily
description: Run GTD morning planning to identify today's priorities. Use when user asks about daily planning, morning routine, what to work on today, or when triggered by scheduled nudge.
---

# Daily Planning

Run through today's commitments and identify the user's TOP priorities.

**IMPORTANT: Use the current date/time from the system prompt ("Current time: ...") at the very top of your context. This is the authoritative timestamp. The scan-deadlines command also outputs a "today" field with the local date (e.g., "Wednesday, January 07, 2026") - use this to confirm the day. Ignore any dates in memory blocks or previous context that may be stale.**

## Checklist

Copy this checklist into your response and check off each step AS YOU COMPLETE IT:

```
Daily Planning Progress:
- [ ] Step 1: Check calendar for fixed commitments
- [ ] Step 2: Scan deadlines (overdue + due today + this week)
- [ ] Step 3: Identify TOP priorities (2-4 items)
- [ ] Step 4: Present summary
```

DO NOT skip steps. DO NOT combine steps. Complete each one, report findings, then proceed.

## Step 1: Check Calendar

Run:
```bash
uv run python -m rubber_duck.cli.gtd calendar-today
```

Report all meetings and time-blocked commitments. These are non-negotiable fixed points in the day.

If no calendar events: Say "No calendar events scheduled for today."

## Step 2: Scan Deadlines

Run:
```bash
uv run python -m rubber_duck.cli.gtd scan-deadlines
```

YOU MUST report ALL of these categories, even if empty:

1. **OVERDUE** - Past due date. For each: note how many days overdue.
2. **DUE TODAY** - Must be completed today.
3. **DUE THIS WEEK** - Coming up soon, for awareness.

Format each task as: `[🔗](https://todoist.com/app/task/{id}) Task content`

If a category is empty, explicitly state: "No overdue items" / "Nothing due today" / etc.

## Step 3: Identify TOP Priorities

Based on the deadline scan, identify **2-4 TOP priorities** for today.

Priority algorithm (see [reference/prioritizing-tasks.md](reference/prioritizing-tasks.md)):
1. Overdue items first (most days overdue = highest priority)
2. Due today items
3. High-priority items due this week

YOU MUST:
- Select exactly 2-4 priorities (not 1, not 5+)
- Briefly explain WHY each was selected
- Include clickable task link for each

## Step 4: Present Summary

Format the final output as:

```
## Daily Plan - [Current Date from System Prompt]

### Calendar
[List events or "No events scheduled"]

### TOP Priorities
1. [🔗](url) Task - [reason]
2. [🔗](url) Task - [reason]
...

### Also Due Today
[List or "Nothing else due"]

### Coming This Week
[Brief list for awareness]

---
*[count] overdue | [count] due today | [count] due this week*
```

## Common Mistakes to Avoid

- **Skipping empty categories**: Always report "No overdue items" rather than omitting
- **Too many priorities**: 2-4 is the limit. More dilutes focus.
- **Missing task links**: Every task mentioned needs a [🔗](url) link
- **Vague priority reasons**: "It's important" is not a reason. "3 days overdue" is.
