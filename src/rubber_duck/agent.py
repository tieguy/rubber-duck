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
