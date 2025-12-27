# Agent Integration Implementation Plan

**Status:** Complete (with extensions)

**Goal:** Replace placeholder echo responses with real Claude-powered conversations that have persistent memory and task awareness.

**Architecture:** Use Letta Cloud as the conversational brain (has built-in Claude + memory). Letta agent has custom tools that call Todoist API directly.

---

## Completed Tasks

### Task 1: Add Todoist API Client ✅

- Created `src/rubber_duck/integrations/todoist.py`
- Added `todoist-api-python` dependency

### Task 2: Add Letta Memory Client ✅

- Created `src/rubber_duck/integrations/memory.py`
- Agent name: `rubber-duck`
- System prompt updated on each startup (not just creation)

### Task 3: Wire Up Agent Module ✅

- Updated `src/rubber_duck/agent.py`
- Integrates Letta + Todoist for nudges and messages

### Task 4: Test End-to-End ✅

- Bot responds with Letta-powered messages
- Nudges work with Todoist context

### Task 5: Add Task Capture Flow ✅

- Keywords trigger task creation: "i need to", "remind me to", "todo:", etc.

---

## Extensions Implemented

### Letta Custom Tools for Todoist ✅

Created `src/rubber_duck/integrations/letta_tools.py` with 11 tools:

**Task CRUD:**
| Tool | Description |
|------|-------------|
| `query_todoist` | Query tasks by filter (today, overdue, @label, #Project) |
| `create_todoist_task` | Create new tasks |
| `update_todoist_task` | Reschedule/modify existing tasks |
| `complete_todoist_task` | Mark tasks complete |

**Project Operations:**
| Tool | Description |
|------|-------------|
| `list_todoist_projects` | Show project hierarchy with task counts |
| `create_todoist_project` | Create new projects |
| `archive_todoist_project` | Delete projects |

**GTD Workflow Tools:**
| Tool | Description |
|------|-------------|
| `run_morning_planning` | Prioritized daily plan with TOP 3, overdue alerts, time blocks |
| `run_end_of_day_review` | Identifies slipped tasks, suggests rescheduling, tomorrow's priorities |
| `run_weekly_review` | Project health, waiting-for items, overdue/deadline scan |
| `get_completed_tasks` | Recently completed tasks for celebrating wins |

Tools are automatically attached to the agent on startup.

### Personality Update ✅

System prompt changed from "friendly personal assistant" to "helpful executive assistant" with:
- GTD priority algorithm (urgency → feasibility → strategic value)
- Follow-up timing guidance
- Concise, no-fluff communication style

---

## Verification Checklist

- [x] Bot responds with Letta-powered messages (not echo)
- [x] Nudges include relevant Todoist tasks when available
- [x] "I need to X" messages create tasks in Todoist
- [x] Memory persists across conversations
- [x] Bot handles missing API keys gracefully
- [x] Agent can query Todoist when asked about tasks
- [x] Agent can reschedule tasks
- [x] Agent can mark tasks complete
- [x] Agent can list projects

---

## GTD Skills (Implemented 2025-12-27)

All GTD workflow tools implemented and attached to agent:

- **Morning Planning** (`run_morning_planning`): Queries all tasks, categorizes by urgency, generates TOP 3 priorities and schedule
- **End-of-Day Review** (`run_end_of_day_review`): Identifies slipped tasks, suggests rescheduling, prepares tomorrow's priorities
- **Weekly Review** (`run_weekly_review`): Project health analysis, waiting-for follow-ups, deadline scanning
- **Get Completed** (`get_completed_tasks`): Shows recent completions for celebrating wins

Priority algorithm embedded in all tools: urgency → feasibility → strategic value

---

## Future Work

See bd issue `rubber-duck-0i8` for:
- Google Calendar integration for nudges and time-blocking

---

## Files

- `src/rubber_duck/integrations/todoist.py` - Todoist API wrapper
- `src/rubber_duck/integrations/memory.py` - Letta agent management
- `src/rubber_duck/integrations/letta_tools.py` - Custom Todoist tools for Letta
- `src/rubber_duck/agent.py` - Orchestration layer
