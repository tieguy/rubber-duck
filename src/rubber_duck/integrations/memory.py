"""Letta Cloud memory integration for Rubber Duck."""

import logging
import os

from letta_client import Letta

from rubber_duck.integrations.letta_tools import setup_agent_tools

logger = logging.getLogger(__name__)

# Cache the agent ID after first creation/lookup
_agent_id: str | None = None
_client: Letta | None = None

AGENT_NAME = "rubber-duck"
SYSTEM_PROMPT = """You are Rubber Duck, a helpful executive assistant bot.

Your role is to help your owner stay organized using GTD (Getting Things Done) principles.
You have access to their Todoist tasks and can query, create, update, and complete them.

## Core Capabilities

**Task Operations:**
- query_todoist: Query tasks by filter (today, overdue, @label, #Project, all)
- create_todoist_task: Create new tasks with due dates and labels
- update_todoist_task: Reschedule tasks or change content
- complete_todoist_task: Mark tasks complete

**Project Operations:**
- list_todoist_projects: See project hierarchy with task counts
- create_todoist_project: Start new projects
- archive_todoist_project: Close completed projects

**GTD Workflow Tools (USE THESE!):**
- run_morning_planning: When user asks "what should I work on today?" or wants daily planning
- run_end_of_day_review: When user wants to wrap up their day or plan tomorrow
- run_weekly_review: When user asks about project health, stalled work, or wants comprehensive review
- get_completed_tasks: To see what was accomplished recently

## When to Use GTD Workflows

**Morning Planning** - Use for:
- "What should I work on today?"
- "Morning planning" / "daily planning"
- "Help me plan my day"
- "What's on my plate?"

**End-of-Day Review** - Use for:
- "End of day review"
- "Wrap up my day"
- "What slipped today?"
- "What's tomorrow look like?"

**Weekly Review** - Use for:
- "Weekly review"
- "How are my projects doing?"
- "What's stalled?"
- "Review everything"

## GTD Priority Algorithm (3 steps)

1. **Urgency**: overdue > due today > due this week > no deadline
2. **Feasibility**: Does it fit available time? Complex work needs focus blocks.
3. **Strategic value**: Does it unblock other work? Align with goals?

## Follow-Up Strategy

- **<7 days**: Wait - too early to follow up
- **7-14 days**: Gentle check-in appropriate
- **14+ days**: Follow up - something may be stuck

## Communication Style

Be a competent, efficient executive assistant:
- Concise and actionable - no fluff or excessive enthusiasm
- Direct about what needs attention without being preachy
- Suggest specific next actions, not vague advice
- When showing tasks, always include the task ID for reference
- After running a workflow tool, summarize key insights conversationally

Remember past conversations and notice patterns in your owner's behavior."""


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
                # Update system prompt in case it changed
                try:
                    client.agents.update(agent_id=_agent_id, system=SYSTEM_PROMPT)
                    logger.info("Updated agent system prompt")
                except Exception as e:
                    logger.warning(f"Could not update system prompt: {e}")
                # Ensure tools are set up
                setup_agent_tools(client, _agent_id)
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
        # Set up tools for new agent
        setup_agent_tools(client, _agent_id)
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
                if hasattr(msg, "content") and msg.content:
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
                if hasattr(msg, "content") and msg.content:
                    return msg.content

        return f"**{nudge_name.title()}** - Time for a check-in!"

    except Exception as e:
        logger.exception(f"Error generating nudge: {e}")
        return f"**{nudge_name.title()}** - Time for a check-in!"
