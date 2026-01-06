---
name: reviewing-weekly
description: Run GTD weekly review to assess project health, follow up on waiting items, and triage someday-maybe. Use when user asks for weekly review, wants to review projects, or on scheduled weekly nudge.
---

# Weekly Review

A comprehensive review of all open loops. Takes 15-30 minutes.

## Checklist

Copy this checklist into your response and check off each step AS YOU COMPLETE IT:

```
Weekly Review Progress:
- [ ] Step 1: Calendar review (past week + next 2 weeks)
- [ ] Step 2: Deadline scan
- [ ] Step 3: Waiting-for review
- [ ] Step 4: Project health check
- [ ] Step 5: Someday-maybe triage
- [ ] Step 6: Summary
```

**CRITICAL**: DO NOT skip steps. DO NOT summarize multiple steps together. Complete each step fully, report findings, then proceed to next.

---

## Step 1: Calendar Review

Run:
```bash
uv run python -m rubber_duck.cli.gtd calendar-range --days-back 7 --days-forward 14
```

Review and report:
- **Past week**: Any events that need follow-up? Actions not captured?
- **Next two weeks**: What's coming that needs preparation?

If calendar not configured or empty, state that and move on.

---

## Step 2: Deadline Scan

Run:
```bash
uv run python -m rubber_duck.cli.gtd scan-deadlines
```

YOU MUST report ALL categories even if empty:

### OVERDUE
For each overdue item, ask the user:
- Reschedule to realistic date?
- Do it now?
- Delete if no longer relevant?

### DUE THIS WEEK
List items. Ask if any need time blocked.

### DUE NEXT WEEK
Brief mention for awareness.

Format: `[🔗](https://todoist.com/app/task/{id}) Task content`

---

## Step 3: Waiting-For Review

Run:
```bash
uv run python -m rubber_duck.cli.gtd check-waiting
```

### NEEDS FOLLOW-UP (> 7 days)
For each item:
- Show the suggested follow-up message from the JSON
- Ask: Send follow-up? Reschedule? Give more time?

### GENTLE CHECK (4-7 days)
Brief mention. Ask if any need follow-up.

### STILL FRESH (< 4 days)
Acknowledge count only: "X items still within normal response time"

---

## Step 4: Project Health Check

Run:
```bash
uv run python -m rubber_duck.cli.gtd check-projects
```

YOU MUST report on each status category:

### STALLED (has tasks but no recent progress)
For each stalled project:
- Show the next action if available
- Ask: Is this the right next action? Should project be deferred? Abandoned?

### INCOMPLETE (no next action defined)
GTD requires every active project have a next action.
For each: Ask user to define a next action OR move to someday-maybe.

### WAITING (all tasks are waiting-for)
Brief acknowledgment. These are blocked, not stalled.

### ACTIVE (has recent completions)
Brief positive acknowledgment: "X projects making progress"

---

## Step 5: Someday-Maybe Triage

Run:
```bash
uv run python -m rubber_duck.cli.gtd check-someday
```

### CONSIDER DELETING (> 1 year old)
For each: "This has been on backburner for [X] days. Still relevant?"
- Delete?
- Activate (move to active project)?
- Keep on backburner?

### NEEDS DECISION (6-12 months)
Brief review. Any ready to activate?

### KEEP (< 6 months)
Acknowledge count: "X items appropriately on backburner"

---

## Step 6: Summary

Provide:

```
## Weekly Review Complete

### Decisions Made
- [List any decisions from the review]

### Action Items Generated
- [List any new tasks created or follow-ups needed]

### System Health
- Active projects: X
- Stalled projects: X (addressed above)
- Waiting items: X
- Someday-maybe: X

### Next Review
Schedule for: [suggest date ~7 days out]
```

---

## Common Mistakes to Avoid

- **Rushing through steps**: Each step deserves full attention
- **Not asking for decisions**: Stalled projects and old backburner items need user input
- **Skipping empty categories**: Always report "No stalled projects" rather than omitting
- **Missing task links**: Every task needs `[🔗](url)`
- **Combining steps**: Report each step separately, even if findings are brief
