---
name: letta-memory
description: Access persistent memory - get/set memory blocks, search past conversations, archive insights. Use for remembering user preferences, patterns, past discussions.
allowed-tools: Bash(python:*), Bash(uv:*)
---

# Memory Operations

Access the user's persistent memory stored in Letta.

## Memory Blocks (Core Identity)

Get all blocks:
```bash
uv run python -m rubber_duck.cli.tools memory get-blocks
```

Update a block:
```bash
uv run python -m rubber_duck.cli.tools memory set-block "patterns" "New observed patterns..."
```

Available blocks:
- `persona` - facts about the owner
- `bot_values` - bot identity
- `patterns` - observed behavioral patterns
- `guidelines` - operating principles
- `communication` - tone and style
- `current_focus` - what owner is working on
- `schedule` - schedule awareness

## Search Past Conversations

```bash
uv run python -m rubber_duck.cli.tools memory search "query about past topic" --limit 10
```

## Archive Information

Save important information for future reference:
```bash
uv run python -m rubber_duck.cli.tools memory archive "User prefers morning meetings"
```

## Output Format

All commands return JSON:
```json
{"success": true, "data": {"blocks": {...}}}
{"success": true, "data": {"results": [...]}}
```
