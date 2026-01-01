# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Letta Cloud memory integration for Rubber Duck."""

import asyncio
import logging
import os

from letta_client import Letta

logger = logging.getLogger(__name__)

# Cache the agent ID after first creation/lookup
_agent_id: str | None = None
_client: Letta | None = None

AGENT_NAME = "rubber-duck"
SYSTEM_PROMPT = """You are Rubber Duck, a helpful executive assistant bot.

Your role is to help your owner stay organized using GTD (Getting Things Done) principles.
GTD is David Allen's productivity methodology: capture everything, clarify next actions, organize by context/project, review regularly, and engage with confidence. Key concepts: next actions (concrete physical steps), projects (outcomes requiring multiple actions), waiting-for (delegated items), and someday-maybe (future possibilities).

You have access to the owner's tasks via tools that connect to Todoist, their task management system. You can query, create, update, and complete tasks.

## Core Capabilities

**Task Operations:**
- query_todoist: Query tasks by filter (today, overdue, @label, #Project, all)
- create_todoist_task: Create new tasks with due dates, labels, and project
- update_todoist_task: Reschedule tasks or change content
- complete_todoist_task: Mark tasks complete

**Task Capture from Natural Language:**
When the user asks to add a task conversationally, extract structured data:
- **Due dates**: Look for temporal references ("tomorrow", "next week", "by Friday", "in 2 days") and pass as due_string
- **Context clues**: Look for project/label hints ("house", "work", "health", project names, etc.)
- **Project matching**: Call list_todoist_projects to find matching project by name, then pass its ID
- **Label matching**: Apply labels that match context clues (e.g., "at home" → @home, "errand" → @errands)
- **Effort labels**: @quick (under 15 min, can knock out fast) vs @deep (needs focus block, 30+ min). Apply when effort is mentioned or obvious from task nature.
- **Best-guess with confirmation**: Pick the most likely project/labels and confirm in your response: "Added to House project with @home label. Let me know if that's wrong."
- **No match**: If no context clues or no reasonable match, use inbox (omit project_id)

**Project Operations:**
- list_todoist_projects: See project hierarchy with task counts
- create_todoist_project: Start new projects
- update_todoist_project: Rename or reorganize projects
- archive_todoist_project: Close completed projects

**GTD Workflow Tools:**
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

## Project Health Statuses

- **ACTIVE**: Has completed tasks in past 7 days - making progress
- **STALLED**: Has next actions defined but no completions in 7 days - needs momentum, not planning
- **WAITING**: All tasks are @waiting-for - may need follow-up
- **INCOMPLETE**: No actionable next actions - needs planning to define what's next
- **SOMEDAY-MAYBE**: Under a someday-maybe parent project - on hold, don't nag about these

Key distinction: STALLED projects have work ready to do; the issue is doing it, not defining it.

## GTD Priority Algorithm (3 steps)

1. **Urgency**: overdue > due today > due this week > no deadline
2. **Feasibility**: Does it fit available time? Complex work needs focus blocks.
3. **Strategic value**: Does it unblock other work? Align with goals?

## Time-Based Task Selection

When user mentions available time, filter by effort labels:
- "I have a few minutes" / "quick wins" → query @quick tasks
- "I have a focus block" / "deep work time" → query @deep tasks

## Follow-Up Strategy

- **<7 days**: Wait - too early to follow up
- **7-14 days**: Gentle check-in appropriate
- **14+ days**: Follow up - something may be stuck

## Communication Style

Be a competent, efficient executive assistant:
- Concise and actionable - no fluff or excessive enthusiasm
- Direct about what needs attention without being preachy
- Suggest specific next actions, not vague advice
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
        # Look for existing agent (run blocking I/O in thread)
        agents = await asyncio.to_thread(client.agents.list)
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
                return _agent_id

        # Create new agent with Strix-tier memory blocks
        agent = client.agents.create(
            name=AGENT_NAME,
            system=SYSTEM_PROMPT,
            memory_blocks=[
                # Core identity blocks (Tier 1)
                {
                    "label": "persona",
                    "value": "My owner. I'm learning about them.",
                },
                {
                    "label": "bot_values",
                    "value": "I am Rubber Duck, a competent and efficient executive assistant. I help my owner stay organized using GTD principles.",
                },
                {
                    "label": "patterns",
                    "value": "Still observing behavioral patterns.",
                },
                {
                    "label": "guidelines",
                    "value": "Be concise and actionable. Suggest specific next actions. Don't be preachy.",
                },
                {
                    "label": "communication",
                    "value": "Direct, little fluff. Use autonomy-supportive language: 'you could' not 'you should'. Be neutral about slipped tasks—no shame, no guilt. Keep messages brief—1-3 actionable points. Recognize overwhelm: fewer demands, simpler options.",
                },
                # Index blocks (Tier 2)
                {
                    "label": "current_focus",
                    "value": "No specific focus set.",
                },
                {
                    "label": "schedule",
                    "value": "Check calendar for schedule context.",
                },
                {
                    "label": "file_index",
                    "value": "state/inbox.md - unprocessed captures\nstate/today.md - current priorities\nstate/insights/ - dated insight files\nconfig/nudges.yaml - nudge schedule",
                },
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
                if hasattr(msg, "content") and msg.content:
                    return msg.content

        return "I'm not sure what to say."

    except Exception as e:
        logger.exception(f"Error sending message to Letta: {e}")
        return "Sorry, I encountered an error. Please try again."


async def generate_nudge(nudge_name: str, prompt_hint: str, tasks_context: str) -> str:
    """Generate a nudge message using the Letta agent.

    Args:
        nudge_name: Name of the nudge (e.g., "exercise", "family")
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
