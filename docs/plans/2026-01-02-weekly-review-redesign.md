# Weekly Review Redesign

Date: 2026-01-02

## Overview

Replace the single-pass `run_weekly_review()` with an interactive, multi-step weekly review session. The bot walks the user through six sub-reviews with natural conversation between each step.

## Goals

- Port the proven marvin-to-model two-phase workflow to Discord
- Allow conversation and task updates between each sub-review
- Make the weekly review feel like a guided GTD session, not a static report

## Architecture

### Session Lifecycle

**Starting:**
- User says "let's do weekly review" (or similar)
- Agent calls `conductor("start")` → creates session state
- Session stored in `state/weekly_review_session.json`

**During:**
- Agent runs sub-reviews in sequence using conductor guidance
- Between each: natural conversation (add tasks, answer questions, etc.)
- Agent calls `conductor("next")` when user indicates readiness
- Session persists if user pauses - can resume later

**Completing/Abandoning:**
- After final sub-review: `conductor("complete")`
- User says "stop" or "cancel": session cleared
- Sessions >24 hours old: auto-cleared on next start

**Session State:**
```json
{
  "started_at": "2026-01-02T10:00:00Z",
  "current_step": "deadline_scan",
  "completed_steps": ["calendar_review"],
  "todoist_snapshot_at": "2026-01-02T10:00:00Z"
}
```

### The Six Sub-Reviews

Run in this order:

1. **calendar_review** - Check GCal for tasks to create from calendar items. (Scaffolded only until GCal integration complete - see rubber-duck-gaz)

2. **deadline_scan** - Fetch tasks with due dates, group by urgency (overdue, due this week, due next week). Apply priority rules. Output: reschedule/complete/delete decisions.

3. **waiting_for_review** - Fetch waiting-for labeled tasks, calculate age, apply follow-up strategy matrix. Output: specific follow-up wording by age and context.

4. **project_review** - Fetch projects with tasks and 7-day completions, compute health (ACTIVE/STALLED/WAITING/INCOMPLETE). Output: projects needing decisions.

5. **category_health** - Analyze task distribution across projects/areas. Output: overloaded vs neglected areas, balance assessment.

6. **someday_maybe_review** - Fetch backburner items, group by activate/keep/delete. Output: triage decisions.

### The Conductor Tool

Single tool managing session state:

```python
def weekly_review_conductor(action: str) -> str:
    """
    Actions:
    - "start": Create session, return first step guidance
    - "status": Return current step and progress
    - "next": Mark current complete, advance, return guidance
    - "complete": End session, return summary
    - "abandon": Clear session without completing
    """
```

**Example conductor responses:**
- `conductor("start")` → "Weekly review started. Step 1: Calendar Review. Call run_calendar_review()."
- `conductor("next")` → "Step 2: Deadline Scan. Call run_deadline_scan()."
- `conductor("next")` after step 6 → "Weekly review complete! Covered all 6 areas."

### Conversation Flow

Agent decides when to advance based on user signals:
- "next" / "move on" / "continue" → call `conductor("next")`
- "add a task for X" → use Todoist tools, stay on current step
- "what about project ABC?" → answer, stay on current step
- "pause" / "stop here" → acknowledge, session persists

System prompt includes minimal guidance:
> "When conducting a weekly review session, follow the conductor's guidance for sequencing. Between sub-reviews, handle user requests naturally. Advance to the next step when the user indicates they're ready."

## File Structure

```
src/rubber_duck/integrations/tools/
├── weekly_review.py          # existing - keep as legacy or deprecate
├── weekly_conductor.py       # NEW - session state + conductor logic
├── calendar_review.py        # NEW - scaffolded placeholder
├── deadline_scan.py          # NEW
├── waiting_for_review.py     # NEW
├── project_review.py         # NEW
├── category_health.py        # NEW
└── someday_maybe_review.py   # NEW

state/
└── weekly_review_session.json  # session persistence
```

## What to Port from marvin-to-model

**Port as code logic:**
- Follow-up strategy matrix (age × context → timing + wording) → `waiting_for_review.py`
- Priority rules (urgency → feasibility → strategic value) → `deadline_scan.py`
- Project health computation → extract from existing `weekly_review.py` as shared util

**Port as output formatting:**
- Checklist style for first 3 sub-reviews (tasks to mark done, add, update)
- Report style with health symbols (✓ ⚠️ 🔴) for last 3 sub-reviews
- Specific follow-up wording templates

**Source prompts:**
- `/projects/self-serious/marvin-to-model/code/prompts/sub-reviews/` - sub-review logic
- `/projects/self-serious/marvin-to-model/code/prompts/skills/follow-up-strategy/` - follow-up matrix
- `/projects/self-serious/marvin-to-model/code/prompts/skills/priority-rules/` - priority algorithm

## Error Handling

**Todoist API failures:**
- Return "Could not fetch Todoist data: {error}. Try again or skip this step."
- Session continues

**Session state corruption:**
- `conductor("status")` returns "No active session. Call conductor('start') to begin."

**Stale session (>24 hours):**
- `conductor("start")` auto-clears and starts fresh
- Warns user about incomplete previous session

**Bot restart mid-session:**
- Session state persists in file
- Agent can resume: "Looks like we were on step 3. Continue from there?"

## Integration

**Changes to existing files:**
- `agent/tools.py` - Add 7 new tools to `TOOL_SCHEMAS` and `TOOL_FUNCTIONS`
- `agent/loop.py` - Add one paragraph to system prompt about conductor guidance

**Reuse existing code:**
- `weekly_review.py`: `_fetch_todoist_data()`, `_categorize_tasks()`, `_compute_project_status()`
- `morning_planning.py`: `_get_calendar_events()` (when calendar ready)

## Triggering

**Nudge:** Weekly nudge reminds user ("Time for weekly review?") but does NOT auto-start. User must explicitly begin.

**Manual:** User can start anytime with "let's do weekly review" or similar.

## Out of Scope

- Calendar integration (scaffolded only) - see rubber-duck-gaz
- Todoist URL formatting - see rubber-duck-k8i
- Moving guidance to a skill - see rubber-duck-2sm

## Dependencies

- rubber-duck-gaz (GCal integration) blocks calendar_review functionality
- No blockers for the other 5 sub-reviews and conductor
