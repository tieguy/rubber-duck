# GTD Skills Design

Convert Python GTD workflows to Claude Code skills for flexibility, transparency, and consistency.

## Goals

1. **Flexibility**: LLM applies GTD judgment dynamically based on context
2. **Transparency**: Logic visible/editable in markdown rather than buried in Python
3. **Consistency**: Same procedures across all contexts (Discord bot, CLI, etc.)

## Architecture

### Hybrid Approach

- **Skills** guide procedure and judgment (markdown)
- **CLI tools** handle computation (Python, returns JSON)
- Bot invokes skills via Claude Code; no direct Python function calls

### Skill Structure

```
.claude/skills/gtd/
├── SKILL.md                      # name: managing-gtd (router)
├── daily.md                      # name: planning-daily
├── weekly.md                     # name: reviewing-weekly
├── monthly.md                    # name: reviewing-monthly (future)
├── quarterly.md                  # name: reviewing-quarterly (future)
└── reference/
    ├── prioritizing-tasks.md     # Priority algorithm
    └── assessing-staleness.md    # Staleness rules
```

### CLI Tools

```
uv run python -m rubber_duck.cli.gtd scan-deadlines
uv run python -m rubber_duck.cli.gtd check-projects
uv run python -m rubber_duck.cli.gtd check-waiting
uv run python -m rubber_duck.cli.gtd check-someday
uv run python -m rubber_duck.cli.gtd calendar-today
uv run python -m rubber_duck.cli.gtd calendar-range --days-back 7 --days-forward 14
```

## CLI Output Format

All commands return JSON. Claude interprets and presents with judgment.

### scan-deadlines

```json
{
  "generated_at": "2026-01-05T14:30:00Z",
  "overdue": [
    {"id": "123", "content": "Review PR", "days_overdue": 2, "project": "Work"}
  ],
  "due_today": [
    {"id": "456", "content": "Call dentist", "has_time": true, "time": "14:00", "project": "Personal"}
  ],
  "due_this_week": [
    {"id": "789", "content": "Submit report", "due_date": "2026-01-08", "days_until": 3, "project": "Work"}
  ],
  "summary": {"overdue": 1, "due_today": 1, "due_this_week": 1}
}
```

### check-projects

```json
{
  "generated_at": "2026-01-05T14:30:00Z",
  "active": [
    {"name": "Website Redesign", "open_tasks": 5, "completed_this_week": 3}
  ],
  "stalled": [
    {"name": "Learn Piano", "open_tasks": 2, "days_since_activity": 14,
     "next_action": {"id": "111", "content": "Practice scales"}}
  ],
  "waiting": [
    {"name": "Home Renovation", "waiting_tasks": 2}
  ],
  "incomplete": [
    {"name": "Tax Prep", "reason": "no next action defined"}
  ],
  "summary": {"active": 1, "stalled": 1, "waiting": 1, "incomplete": 1}
}
```

### check-waiting

```json
{
  "generated_at": "2026-01-05T14:30:00Z",
  "needs_followup": [
    {"id": "222", "content": "Waiting on Bob for specs", "days_waiting": 12,
     "urgency": "firm", "suggested_action": "Follow up - it's been 12 days", "project": "Work"}
  ],
  "gentle_check": [
    {"id": "333", "content": "Waiting on vendor quote", "days_waiting": 5,
     "urgency": "gentle", "project": "Home"}
  ],
  "still_fresh": [
    {"id": "444", "content": "Waiting on reply from Jane", "days_waiting": 2, "project": "Work"}
  ],
  "summary": {"total": 3, "needs_followup": 1}
}
```

### check-someday

```json
{
  "generated_at": "2026-01-05T14:30:00Z",
  "consider_deleting": [
    {"id": "555", "content": "Learn Mandarin", "days_old": 400, "project": "Someday"}
  ],
  "needs_decision": [
    {"id": "666", "content": "Build a shed", "days_old": 200, "project": "Someday"}
  ],
  "keep": [
    {"id": "777", "content": "Try pottery class", "days_old": 30, "project": "Someday"}
  ],
  "summary": {"total": 3, "consider_deleting": 1, "needs_decision": 1}
}
```

### calendar-today / calendar-range

```json
{
  "generated_at": "2026-01-05T14:30:00Z",
  "events": [
    {"summary": "Team standup", "start": "09:00", "end": "09:15", "location": null},
    {"summary": "Dentist", "start": "14:00", "end": "15:00", "location": "123 Main St"}
  ],
  "all_day": [
    {"summary": "Mom's birthday"}
  ],
  "summary": {"timed_events": 2, "all_day": 1}
}
```

**Design notes:**
- IDs only, no URLs (URL is `https://todoist.com/app/task/{id}`)
- Pre-computed hints (urgency, days_old, suggested_action) - tool does math, skill uses it
- Summary counts for quick reporting

## Skill Content Format

Skills use:
- **Checklists** Claude copies into responses and checks off
- **"YOU MUST" language** for non-skippable steps
- **"Report even if empty"** to prevent skipping sections with no findings

### Example: planning-daily

```markdown
---
name: planning-daily
description: Run GTD morning planning to identify today's priorities. Use when user asks about daily planning, morning routine, what to work on today, or when triggered by scheduled nudge.
---

# Daily Planning

Run through today's commitments and select the user's TOP priorities.

## Checklist

Copy this checklist and check off each step as you complete it:

` ` `
Daily Planning Progress:
- [ ] Step 1: Check calendar for fixed commitments
- [ ] Step 2: Scan deadlines (overdue + due today)
- [ ] Step 3: Identify TOP priorities (2-4)
- [ ] Step 4: Review scheduled tasks
- [ ] Step 5: Present summary
` ` `

## Step 1: Check Calendar
...

## Step 2: Scan Deadlines

Run:
` ` `bash
uv run python -m rubber_duck.cli.gtd scan-deadlines
` ` `

YOU MUST report:
- All overdue items (even if zero - say "No overdue items")
- All items due today

Format task links as [🔗](https://todoist.com/app/task/{id})
...
```

### Example: reviewing-weekly

Similar structure but with more steps:
1. Calendar review (past week + next 2 weeks)
2. Deadline scan
3. Waiting-for review
4. Project health check
5. Someday-maybe triage
6. Summary and next actions

Key enforcement: "DO NOT skip steps. DO NOT summarize multiple steps together."

## Migration Plan

### Refactored into CLI

- Date math / staleness calculations
- Todoist API calls and batching
- Project health computation
- Calendar fetching

### New module structure

```
src/rubber_duck/cli/gtd.py      # CLI entry point
src/rubber_duck/gtd/
├── __init__.py
├── deadlines.py                # scan_deadlines() -> dict
├── projects.py                 # check_projects() -> dict
├── waiting.py                  # check_waiting() -> dict
├── someday.py                  # check_someday() -> dict
└── calendar.py                 # calendar_today(), calendar_range() -> dict
```

### Removed

- `run_morning_planning()` - replaced by `planning-daily` skill
- `weekly_review_conductor()` - replaced by `reviewing-weekly` skill
- All markdown formatting in Python (skills handle presentation)

### Bot integration

- Nudge system invokes skill via Claude Code (same as user would)
- No direct Python function calls from bot to GTD workflows

## Future Work

- `reviewing-monthly` skill
- `reviewing-quarterly` skill
- Reference files for priority algorithm and staleness rules
- Iteration based on observed skill behavior (RED-GREEN-REFACTOR)

## References

- [Anthropic Skill Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Superpowers writing-skills](https://github.com/obra/superpowers/tree/main/skills/writing-skills)
