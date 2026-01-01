# Interactive Agent Progress

Date: 2026-01-01

## Problem

The agent loop is a black box. Users see "🤔 Thinking..." and nothing else until completion. This causes:
1. Uncertainty about whether it's working or stuck
2. No way to stop a runaway loop
3. Hitting the 20-tool limit feels like a crash, not a checkpoint

## Solution

Transform the agent loop into a visible, controllable process:
- Live tool log updated after each tool call
- Keyword cancellation ("stop", "cancel") via new messages
- Tool limit becomes an interactive checkpoint, not a hard stop

## Design

### Callback Interface

```python
@dataclass
class AgentCallbacks:
    on_tool_start: Callable[[str], Awaitable[None]]  # tool name
    on_tool_end: Callable[[str, bool], Awaitable[None]]  # tool name, success
    check_cancelled: Callable[[], Awaitable[bool]]  # returns True if cancelled
    on_checkpoint: Callable[[int], Awaitable[bool]]  # tools used → continue?
```

The agent loop stays transport-agnostic (no Discord imports). Handlers provide platform-specific callbacks.

### Message Format

During execution:
```
🔧 query_todoist ✓
🔧 create_todoist_task ✓
🔧 set_memory_block ...
```

Symbols: `...` = in progress, `✓` = success, `✗` = error

On completion, the tool log is replaced with Claude's final response.

### Cancellation Flow

1. Handler spawns background task watching for new messages
2. Before each tool call, `check_cancelled()` checks a flag
3. If "stop" or "cancel" detected → loop exits immediately
4. Response: "Cancelled. Was working on: query_todoist ✓ → create_todoist_task ✓ → set_memory_block ✗"

### Checkpoint Flow

1. After 20 tool calls, `on_checkpoint(20)` is called
2. Handler updates message: "Used 20 tools. Reply 'yes' to continue or 'stop' to cancel."
3. Handler waits up to 15 minutes for response
4. "yes"/"continue" → returns True, loop continues with fresh 20-call budget
5. "stop"/"cancel"/timeout → returns False, loop exits with summary
6. Can trigger multiple times (20, 40, 60...) if user keeps approving

## Files to Change

### `agent/loop.py`
- Add `AgentCallbacks` dataclass
- New `run_agent_loop_interactive()` that accepts callbacks
- Keep existing `run_agent_loop()` as wrapper for nudges/backwards compat

### `handlers/conversation.py`
- Implement Discord-specific callbacks
- Background task to watch for cancel messages
- Message editing logic for tool progress
- Checkpoint waiting logic with 15-minute timeout

## Backwards Compatibility

- `run_agent_loop()` continues to work unchanged (used by nudges)
- Only interactive user messages use the new flow
- Existing behavior preserved when callbacks not provided
