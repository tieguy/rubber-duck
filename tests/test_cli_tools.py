# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Tests for CLI tool wrappers."""

import json
import subprocess
import sys


def test_cli_todoist_query_returns_json():
    """CLI todoist query returns valid JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "rubber_duck.cli.tools", "todoist", "query", "today"],
        capture_output=True,
        text=True,
    )
    # Should return valid JSON (even if empty or error)
    output = json.loads(result.stdout)
    assert "success" in output or "error" in output


def test_cli_memory_get_blocks_returns_json():
    """CLI memory get-blocks returns valid JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "rubber_duck.cli.tools", "memory", "get-blocks"],
        capture_output=True,
        text=True,
    )
    output = json.loads(result.stdout)
    assert "success" in output or "error" in output
