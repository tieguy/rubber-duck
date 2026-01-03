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


def test_cli_gcal_query_returns_json():
    """CLI gcal query returns valid JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "rubber_duck.cli.tools", "gcal", "query", "--range", "today"],
        capture_output=True,
        text=True,
    )
    output = json.loads(result.stdout)
    assert "success" in output


def test_cli_invalid_service_exits_with_error():
    """CLI with invalid service exits with non-zero code."""
    result = subprocess.run(
        [sys.executable, "-m", "rubber_duck.cli.tools", "invalid_service"],
        capture_output=True,
        text=True,
    )
    # argparse prints to stderr for invalid arguments
    assert result.returncode != 0
    assert "invalid_service" in result.stderr or "invalid choice" in result.stderr


def test_cli_missing_required_arg_exits_with_error():
    """CLI with missing required argument exits with non-zero code."""
    result = subprocess.run(
        [sys.executable, "-m", "rubber_duck.cli.tools", "todoist", "query"],
        capture_output=True,
        text=True,
    )
    # argparse exits with code 2 for missing required args
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "arguments" in result.stderr.lower()


def test_cli_error_case_returns_exit_code_1():
    """CLI commands that fail should return exit code 1."""
    # Memory get-blocks will fail without LETTA_API_KEY configured
    result = subprocess.run(
        [sys.executable, "-m", "rubber_duck.cli.tools", "memory", "get-blocks"],
        capture_output=True,
        text=True,
        env={"PATH": "", "LETTA_API_KEY": ""},  # Ensure no API key
    )
    output = json.loads(result.stdout)
    # If success is False, exit code should be 1
    if output.get("success") is False:
        assert result.returncode == 1
