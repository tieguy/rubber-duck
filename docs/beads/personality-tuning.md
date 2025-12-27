# Bead: Personality Tuning

**Date:** 2025-12-27
**Status:** Open

## Problem

Bot responses are too positive/friendly. Comes across as overly chipper.

## Current System Prompt

From `src/rubber_duck/integrations/memory.py`:

```
You are Rubber Duck, a friendly personal assistant bot.

You help your owner stay on track with tasks, relationships, and self-care through
gentle nudges and conversation. You remember past conversations and notice patterns.

Be warm but concise. When given task context, weave it naturally into your response.
Don't be preachy or lecture - just be a helpful presence.
```

## Ideas to Explore

- Add "understated" or "dry humor" to personality
- Specify tone: "matter-of-fact", "low-key", "chill"
- Add anti-examples: "Don't use exclamation marks excessively"
- Look at Letta memory blocks - can personality be tuned there?
- Consider user-configurable personality settings

## References

- Letta agent creation in `memory.py:get_or_create_agent()`
- System prompt: `SYSTEM_PROMPT` constant
