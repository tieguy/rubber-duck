"""Custom Letta tools for Rubber Duck.

These tools are registered with Letta and can be called by the agent
during conversations. Tool source code is loaded from the tools/ directory.
"""

import logging
import os
from pathlib import Path

from letta_client import Letta

logger = logging.getLogger(__name__)

# Directory containing tool source files
TOOLS_DIR = Path(__file__).parent / "tools"


def load_tool_source(name: str) -> str:
    """Load tool source code from file.

    Args:
        name: Tool filename without .py extension

    Returns:
        Source code as string
    """
    tool_path = TOOLS_DIR / f"{name}.py"
    return tool_path.read_text()


# Tool definitions: (filename, description)
TOOL_DEFINITIONS = [
    # Task CRUD
    ("query_todoist", "Query tasks from Todoist"),
    ("create_todoist_task", "Create a task in Todoist"),
    ("update_todoist_task", "Update/reschedule a task in Todoist"),
    ("complete_todoist_task", "Mark a task as complete in Todoist"),
    # Project operations
    ("list_todoist_projects", "List all Todoist projects with task counts"),
    ("create_todoist_project", "Create a new project in Todoist"),
    ("archive_todoist_project", "Delete/archive a project in Todoist"),
    # GTD workflows
    ("morning_planning", "Run morning planning workflow - prioritizes today's tasks using GTD principles"),
    ("end_of_day_review", "Run end-of-day review - identifies slipped tasks and prepares tomorrow's priorities"),
    ("weekly_review", "Run weekly review - checks project health, waiting-for items, and overdue tasks"),
    ("get_completed_tasks", "Get recently completed tasks from Todoist"),
]


def setup_tools(client: Letta) -> list[str]:
    """Create/update Letta tools and return their IDs.

    Args:
        client: Letta API client

    Returns:
        List of tool IDs that were created/updated
    """
    tool_ids = []

    for filename, description in TOOL_DEFINITIONS:
        try:
            source_code = load_tool_source(filename)
            tool = client.tools.upsert(
                source_code=source_code,
                description=description,
                pip_requirements=[{"name": "requests"}],
            )
            tool_ids.append(tool.id)
            logger.info(f"Created/updated tool: {filename} ({tool.id})")
        except Exception as e:
            logger.exception(f"Failed to create {filename} tool: {e}")

    return tool_ids


def attach_tools_to_agent(client: Letta, agent_id: str, tool_ids: list[str]) -> None:
    """Attach tools to an agent.

    Args:
        client: Letta API client
        agent_id: The agent to attach tools to
        tool_ids: List of tool IDs to attach
    """
    for tool_id in tool_ids:
        try:
            client.agents.tools.attach(agent_id=agent_id, tool_id=tool_id)
            logger.info(f"Attached tool {tool_id} to agent {agent_id}")
        except Exception as e:
            # May already be attached
            if "already" in str(e).lower():
                logger.debug(f"Tool {tool_id} already attached to agent")
            else:
                logger.exception(f"Failed to attach tool {tool_id}: {e}")


def setup_agent_tools(client: Letta, agent_id: str) -> None:
    """Set up all custom tools for an agent.

    Args:
        client: Letta API client
        agent_id: The agent to set up tools for
    """
    # First, set the environment variable for the agent's sandbox
    try:
        todoist_key = os.environ.get("TODOIST_API_KEY", "")
        if todoist_key:
            # Set agent-scoped env var for tool execution
            client.agents.update(
                agent_id=agent_id,
                tool_exec_environment_variables={"TODOIST_API_KEY": todoist_key}
            )
            logger.info("Set TODOIST_API_KEY in agent's tool environment")
    except Exception as e:
        logger.warning(f"Could not set agent environment variables: {e}")

    # Create/update tools
    tool_ids = setup_tools(client)

    # Attach to agent
    if tool_ids:
        attach_tools_to_agent(client, agent_id, tool_ids)
