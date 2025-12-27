# Agent Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace placeholder echo responses with real Claude-powered conversations that have persistent memory and task awareness.

**Architecture:** Use Letta Cloud as the conversational brain (has built-in Claude + memory). Query Todoist directly for task context. Pass task context to Letta when generating nudges or processing messages.

**Tech Stack:** letta-client, todoist-api-python, existing discord.py bot

---

## Task 1: Add Todoist API Client

**Files:**
- Create: `src/rubber_duck/integrations/__init__.py`
- Create: `src/rubber_duck/integrations/todoist.py`
- Modify: `pyproject.toml` (add todoist-api-python)

**Step 1: Add todoist-api-python dependency**

```bash
uv add todoist-api-python
```

**Step 2: Create integrations package**

Create `src/rubber_duck/integrations/__init__.py`:
```python
"""External service integrations for Rubber Duck."""
```

**Step 3: Create Todoist client wrapper**

Create `src/rubber_duck/integrations/todoist.py`:
```python
"""Todoist API integration for Rubber Duck."""

import logging
import os

from todoist_api_python.api import TodoistAPI

logger = logging.getLogger(__name__)


def get_client() -> TodoistAPI | None:
    """Get a Todoist API client.

    Returns None if TODOIST_API_KEY is not set.
    """
    api_key = os.environ.get("TODOIST_API_KEY")
    if not api_key:
        logger.warning("TODOIST_API_KEY not set, Todoist integration disabled")
        return None
    return TodoistAPI(api_key)


async def get_tasks_by_filter(filter_query: str) -> list[dict]:
    """Get tasks matching a Todoist filter query.

    Args:
        filter_query: Todoist filter string (e.g., "@asa", "#Health", "today")

    Returns:
        List of task dicts with keys: id, content, description, due, labels, project_id
    """
    client = get_client()
    if not client:
        return []

    try:
        tasks = client.get_tasks(filter=filter_query)
        return [
            {
                "id": t.id,
                "content": t.content,
                "description": t.description or "",
                "due": t.due.string if t.due else None,
                "labels": t.labels,
                "project_id": t.project_id,
            }
            for t in tasks
        ]
    except Exception as e:
        logger.exception(f"Error fetching Todoist tasks: {e}")
        return []


async def create_task(
    content: str,
    description: str = "",
    labels: list[str] | None = None,
    due_string: str | None = None,
) -> dict | None:
    """Create a new task in Todoist.

    Args:
        content: Task title
        description: Optional task description
        labels: Optional list of label names
        due_string: Optional due date string (e.g., "tomorrow", "next monday")

    Returns:
        Created task dict or None on failure
    """
    client = get_client()
    if not client:
        return None

    try:
        task = client.add_task(
            content=content,
            description=description,
            labels=labels or [],
            due_string=due_string,
        )
        return {
            "id": task.id,
            "content": task.content,
            "url": task.url,
        }
    except Exception as e:
        logger.exception(f"Error creating Todoist task: {e}")
        return None
```

**Step 4: Verify import works**

```bash
uv run python -c "from rubber_duck.integrations.todoist import get_tasks_by_filter; print('OK')"
```

Expected: `OK`

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Todoist API integration"
```

---

## Task 2: Add Letta Memory Client

**Files:**
- Create: `src/rubber_duck/integrations/memory.py`

**Step 1: Create Letta memory wrapper**

Create `src/rubber_duck/integrations/memory.py`:
```python
"""Letta Cloud memory integration for Rubber Duck."""

import logging
import os

from letta_client import Letta

logger = logging.getLogger(__name__)

# Cache the agent ID after first creation/lookup
_agent_id: str | None = None
_client: Letta | None = None

AGENT_NAME = "rubber-duck"
SYSTEM_PROMPT = """You are Rubber Duck, a friendly personal assistant bot.

You help your owner stay on track with tasks, relationships, and self-care through
gentle nudges and conversation. You remember past conversations and notice patterns.

Be warm but concise. When given task context, weave it naturally into your response.
Don't be preachy or lecture - just be a helpful presence."""


def get_client() -> Letta | None:
    """Get a Letta API client.

    Returns None if LETTA_API_KEY is not set.
    """
    global _client
    if _client:
        return _client

    api_key = os.environ.get("LETTA_API_KEY")
    if not api_key:
        logger.warning("LETTA_API_KEY not set, Letta integration disabled")
        return None

    _client = Letta(api_key=api_key)
    return _client


async def get_or_create_agent() -> str | None:
    """Get the Rubber Duck agent ID, creating it if needed.

    Returns:
        Agent ID string or None if Letta is not configured
    """
    global _agent_id
    if _agent_id:
        return _agent_id

    client = get_client()
    if not client:
        return None

    try:
        # Look for existing agent
        agents = client.agents.list()
        for agent in agents:
            if agent.name == AGENT_NAME:
                _agent_id = agent.id
                logger.info(f"Found existing Letta agent: {_agent_id}")
                return _agent_id

        # Create new agent
        agent = client.agents.create(
            name=AGENT_NAME,
            system=SYSTEM_PROMPT,
            memory_blocks=[
                {"label": "persona", "value": "I am Rubber Duck, a friendly assistant."},
                {"label": "human", "value": "My owner. I'm learning about them."},
            ],
        )
        _agent_id = agent.id
        logger.info(f"Created new Letta agent: {_agent_id}")
        return _agent_id

    except Exception as e:
        logger.exception(f"Error getting/creating Letta agent: {e}")
        return None


async def send_message(user_message: str, context: str = "") -> str:
    """Send a message to the Letta agent and get a response.

    Args:
        user_message: The user's message
        context: Optional context to prepend (e.g., task info)

    Returns:
        Agent's response text
    """
    client = get_client()
    agent_id = await get_or_create_agent()

    if not client or not agent_id:
        return "I'm having trouble connecting to my memory. Please try again later."

    try:
        # Prepend context if provided
        full_message = user_message
        if context:
            full_message = f"[Context: {context}]\n\nUser: {user_message}"

        response = client.agents.messages.create(
            agent_id=agent_id,
            messages=[{"role": "user", "content": full_message}],
        )

        # Extract text from response
        if response.messages:
            for msg in response.messages:
                if hasattr(msg, 'content') and msg.content:
                    return msg.content

        return "I'm not sure what to say."

    except Exception as e:
        logger.exception(f"Error sending message to Letta: {e}")
        return "Sorry, I encountered an error. Please try again."


async def generate_nudge(nudge_name: str, prompt_hint: str, tasks_context: str) -> str:
    """Generate a nudge message using the Letta agent.

    Args:
        nudge_name: Name of the nudge (e.g., "exercise", "asa")
        prompt_hint: Hint about the nudge's focus
        tasks_context: Formatted string of relevant tasks

    Returns:
        Generated nudge message
    """
    client = get_client()
    agent_id = await get_or_create_agent()

    if not client or not agent_id:
        return f"**{nudge_name.title()} Reminder**\n\n_Memory unavailable. Here are your tasks:_\n{tasks_context}"

    try:
        prompt = f"""Generate a {nudge_name} nudge for the user.

Focus: {prompt_hint}

Relevant tasks from Todoist:
{tasks_context if tasks_context else "No matching tasks found."}

Write a brief, friendly nudge (2-3 sentences) based on the above. Be specific if there are tasks. Don't be preachy."""

        response = client.agents.messages.create(
            agent_id=agent_id,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        if response.messages:
            for msg in response.messages:
                if hasattr(msg, 'content') and msg.content:
                    return msg.content

        return f"**{nudge_name.title()}** - Time for a check-in!"

    except Exception as e:
        logger.exception(f"Error generating nudge: {e}")
        return f"**{nudge_name.title()}** - Time for a check-in!"
```

**Step 2: Verify import works**

```bash
uv run python -c "from rubber_duck.integrations.memory import get_client; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: add Letta Cloud memory integration"
```

---

## Task 3: Wire Up Agent Module

**Files:**
- Modify: `src/rubber_duck/agent.py`

**Step 1: Update agent.py to use real integrations**

Replace contents of `src/rubber_duck/agent.py`:
```python
"""Agent module for Rubber Duck - orchestrates memory and tasks."""

import logging

from rubber_duck.integrations import todoist, memory

logger = logging.getLogger(__name__)


async def generate_nudge_content(nudge_config: dict) -> str:
    """Generate nudge content using Letta + Todoist.

    Args:
        nudge_config: Configuration containing:
            - name: Nudge identifier
            - context_query: Query for Todoist tasks (e.g., "@asa")
            - prompt_hint: Hint for the LLM about this nudge's focus

    Returns:
        Generated nudge message string
    """
    name = nudge_config.get("name", "unknown")
    context_query = nudge_config.get("context_query", "")
    prompt_hint = nudge_config.get("prompt_hint", "")

    logger.info(f"Generating nudge content for '{name}'")

    # Fetch relevant tasks from Todoist
    tasks = []
    if context_query:
        tasks = await todoist.get_tasks_by_filter(context_query)

    # Format tasks as context
    if tasks:
        tasks_context = "\n".join(
            f"- {t['content']}" + (f" (due: {t['due']})" if t['due'] else "")
            for t in tasks
        )
    else:
        tasks_context = ""

    # Generate nudge via Letta
    return await memory.generate_nudge(name, prompt_hint, tasks_context)


async def process_user_message(message: str, context: dict | None = None) -> str:
    """Process a user message and generate a response.

    Args:
        message: The user's message text
        context: Optional context from memory/previous conversation

    Returns:
        Response message string
    """
    logger.info(f"Processing user message: {message[:50]}...")

    # Check if this looks like a task capture
    task_keywords = ["i need to", "remind me to", "add task", "todo:"]
    is_task_capture = any(kw in message.lower() for kw in task_keywords)

    if is_task_capture:
        # For now, just acknowledge - full task creation comes later
        return await memory.send_message(
            message,
            context="User may be trying to capture a task."
        )

    # Regular conversation
    return await memory.send_message(message)
```

**Step 2: Verify module loads**

```bash
uv run python -c "from rubber_duck.agent import generate_nudge_content, process_user_message; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: wire up agent with Letta and Todoist"
```

---

## Task 4: Test End-to-End

**Files:** None (manual testing)

**Step 1: Restart the bot with new code**

Kill any running bot, then:
```bash
source .envrc && uv run python -m rubber_duck
```

**Step 2: Test DM conversation**

Send a DM to the bot: "Hello! What can you help me with?"

Expected: A real response from Letta (not the echo placeholder)

**Step 3: Test nudge generation (optional)**

Temporarily modify a nudge time in `config/nudges.yaml` to trigger soon, or manually call:
```bash
uv run python -c "
import asyncio
from rubber_duck.agent import generate_nudge_content
config = {'name': 'exercise', 'context_query': '@exercise OR #health', 'prompt_hint': 'Focus on movement'}
print(asyncio.run(generate_nudge_content(config)))
"
```

Expected: A generated nudge message (may say "no tasks" if none match)

**Step 4: Commit any fixes**

If any issues found and fixed:
```bash
git add -A && git commit -m "fix: agent integration fixes from testing"
```

---

## Task 5: Add Task Capture Flow

**Files:**
- Modify: `src/rubber_duck/agent.py`
- Modify: `src/rubber_duck/integrations/todoist.py`

**Step 1: Enhance task capture detection and creation**

Update the `process_user_message` function in `src/rubber_duck/agent.py`:
```python
async def process_user_message(message: str, context: dict | None = None) -> str:
    """Process a user message and generate a response.

    Args:
        message: The user's message text
        context: Optional context from memory/previous conversation

    Returns:
        Response message string
    """
    logger.info(f"Processing user message: {message[:50]}...")

    # Check if this looks like a task capture
    task_keywords = ["i need to", "remind me to", "add task", "todo:", "don't forget"]
    message_lower = message.lower()
    is_task_capture = any(kw in message_lower for kw in task_keywords)

    if is_task_capture:
        # Extract task content (simple approach - everything after the keyword)
        task_content = message
        for kw in task_keywords:
            if kw in message_lower:
                idx = message_lower.find(kw) + len(kw)
                task_content = message[idx:].strip()
                break

        # Create the task
        result = await todoist.create_task(content=task_content)

        if result:
            return f"Got it! I've added to your tasks:\n> {result['content']}\n\n[View in Todoist]({result['url']})"
        else:
            # Fall back to memory response if task creation fails
            return await memory.send_message(
                message,
                context="User tried to add a task but Todoist may not be configured."
            )

    # Regular conversation
    return await memory.send_message(message)
```

**Step 2: Test task capture**

Send a DM: "I need to schedule a dentist appointment"

Expected: Task created in Todoist with confirmation message

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: add basic task capture from DMs"
```

---

## Verification Checklist

After all tasks complete:

- [ ] Bot responds with Letta-powered messages (not echo)
- [ ] Nudges include relevant Todoist tasks when available
- [ ] "I need to X" messages create tasks in Todoist
- [ ] Memory persists across conversations (test by referencing earlier messages)
- [ ] Bot handles missing API keys gracefully (warnings, not crashes)

---

## Notes

- **Letta model**: Uses Letta's default model. Can be changed in agent creation.
- **Todoist filters**: Uses Todoist's filter syntax (@label, #project, etc.)
- **Error handling**: Graceful fallbacks when services are unavailable.
- **Future improvements**:
  - Smarter task parsing (labels, due dates from natural language)
  - MCP integration for Claude Agent SDK
  - Pattern learning from conversation history
