#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Debug script to inspect the Letta agent's system prompt and tools."""

import os
import sys

from letta_client import Letta


def main():
    api_key = os.environ.get("LETTA_API_KEY")
    if not api_key:
        print("ERROR: LETTA_API_KEY not set")
        sys.exit(1)

    client = Letta(api_key=api_key)

    # Find the agent
    agents = client.agents.list()
    agent = next((a for a in agents if a.name == "rubber-duck"), None)

    if not agent:
        print("ERROR: No agent named 'rubber-duck' found")
        print(f"Available agents: {[a.name for a in agents]}")
        sys.exit(1)

    print(f"Agent ID: {agent.id}")
    print(f"Agent name: {agent.name}")
    print()

    # Check system prompt
    print("=" * 60)
    print("SYSTEM PROMPT")
    print("=" * 60)
    print(agent.system)
    print()

    # Check for the key phrase we added
    if "Task Capture from Natural Language" in agent.system:
        print("✓ System prompt contains 'Task Capture from Natural Language'")
    else:
        print("✗ System prompt MISSING 'Task Capture from Natural Language'")
    print()

    # Check attached tools
    print("=" * 60)
    print("ATTACHED TOOLS")
    print("=" * 60)
    tools = client.agents.tools.list(agent_id=agent.id)

    create_task_tool = None
    for t in tools:
        # Skip built-in tools
        if t.source_code is None:
            print(f"  {t.name} (built-in)")
            continue
        print(f"  {t.name}")
        if t.name == "create_todoist_task":
            create_task_tool = t

    print()

    # Check create_todoist_task specifically
    print("=" * 60)
    print("CREATE_TODOIST_TASK TOOL")
    print("=" * 60)
    if create_task_tool:
        print(f"Tool ID: {create_task_tool.id}")
        print()
        print("Source code:")
        print(create_task_tool.source_code)
        print()
        if "project_id" in create_task_tool.source_code:
            print("✓ Tool has 'project_id' parameter")
        else:
            print("✗ Tool MISSING 'project_id' parameter")
    else:
        print("✗ create_todoist_task tool not found!")

    print()

    # List all tools in the organization (not just attached)
    print("=" * 60)
    print("ALL ORGANIZATION TOOLS (checking for duplicates)")
    print("=" * 60)
    all_tools = client.tools.list()
    todoist_tools = [t for t in all_tools if "todoist" in t.name.lower()]
    for t in todoist_tools:
        print(f"  {t.name} (ID: {t.id})")


if __name__ == "__main__":
    main()
