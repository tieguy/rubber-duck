# Natural Language Task Capture

**Date:** 2025-12-29

## Problem

When users ask the bot to add tasks conversationally (e.g., "add a todo to todoist: tomorrow, in my house, I need to find the moisture tester"), the agent wasn't extracting structured data like due dates and project assignments from the natural language.

## Solution

Two changes:

### 1. Tool Enhancement

Added `project_id` parameter to `create_todoist_task` so the agent can assign tasks to specific projects.

**File:** `src/rubber_duck/integrations/tools/create_todoist_task.py`

### 2. System Prompt Guidance

Added "Task Capture from Natural Language" section to the system prompt instructing the agent to:

- Extract temporal references ("tomorrow", "next week") → `due_string`
- Look for context clues ("house", "work", etc.)
- Call `list_todoist_projects` to match project names
- Apply matching labels (e.g., "errand" → @errands)
- Use best-guess with confirmation: "Added to House project. Let me know if that's wrong."

**File:** `src/rubber_duck/integrations/memory.py`

## Design Decision

**Project/label matching strategy:** Best-guess with confirmation

The agent picks the most likely match and tells the user what it chose. This balances convenience (no upfront questions) with correctness (user can correct mistakes). The agent learns preferences over time via its persistent memory.

## Testing

Restart the bot to reload the system prompt and tool definitions. Test with:
- "add a task: tomorrow I need to call the dentist" (should set due date)
- "add a task for my house project: fix the leaky faucet" (should match project)
- "remind me to pick up groceries when I'm out running errands" (should match @errands label)
