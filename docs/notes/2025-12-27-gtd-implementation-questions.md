# GTD Implementation - Questions for Morning Review

**Date:** 2025-12-27
**Context:** Implemented GTD workflow tools overnight

---

## Questions for Your Review

### 1. Calendar Integration

The morning planning workflow from marvin-to-model emphasizes checking calendar FIRST before scheduling. Currently, we don't have calendar integration.

**Question:** Should I prioritize adding Google Calendar integration (`rubber-duck-0i8`) so morning planning can see your actual availability?

Options:
- A) Yes, calendar is essential for realistic time-blocking
- B) No, task-based planning is sufficient for now
- C) Defer - let's test current GTD tools first

### 2. Scheduled Nudges for Reviews

marvin-to-model runs daily reviews at specific times (morning planning ~9am, end-of-day ~3pm). Should Rubber Duck:

**Question:** Should I add scheduled nudges that prompt for GTD reviews?

Options:
- A) Yes, add "morning planning" nudge at startup / ~9am
- B) Yes, add "end of day" nudge at ~3pm
- C) Both A and B
- D) No, reviews should be on-demand only

### 3. Slipped Task Detection

The morning planning tool looks for "slipped" tasks (scheduled for yesterday but not done). However, Todoist's REST API doesn't track original scheduled dates after rescheduling.

**Question:** Is the current approximation (overdue tasks) sufficient, or do you want more sophisticated slip tracking?

### 4. Waiting-For Labels

The weekly review looks for tasks with "waiting" or "waiting-for" labels.

**Question:** Are you using these labels in Todoist? If not, should I adjust the detection or add instructions for labeling waiting-for items?

### 5. Someday-Maybe

marvin-to-model has extensive someday-maybe review logic. Currently, our weekly review doesn't explicitly surface backburner items.

**Question:** Do you use a "someday-maybe" or "backburner" label/project in Todoist? If so, I can add detection for these.

---

## Implementation Notes

All 4 GTD workflow tools are implemented and attached to the Letta agent:

1. `run_morning_planning` - TOP 3 priorities, overdue alerts, schedule for today
2. `run_end_of_day_review` - slipped tasks, tomorrow's priorities, waiting-for items
3. `run_weekly_review` - project health, overdue scan, follow-up timing
4. `get_completed_tasks` - recent completions for celebrating wins

The bot will use these when you ask things like:
- "What should I work on today?" → morning planning
- "Wrap up my day" → end-of-day review
- "Weekly review" → weekly review
- "What did I get done?" → completed tasks

---

## Files Changed

- `src/rubber_duck/integrations/letta_tools.py` - Added 4 GTD workflow tools
- `src/rubber_duck/integrations/memory.py` - Updated system prompt with tool usage guidance
- `docs/plans/2025-12-27-agent-integration.md` - Updated with GTD section

bd issues closed:
- rubber-duck-jdh (epic)
- rubber-duck-jdh.1 (morning planning)
- rubber-duck-jdh.2 (end-of-day)
- rubber-duck-jdh.3 (weekly review)
- rubber-duck-jdh.4 (priority rules)
