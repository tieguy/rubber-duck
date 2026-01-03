# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Integration tests for Claude Code executor.

These tests require Claude Code CLI to be installed and authenticated.
Skip if not available.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Skip all tests if Claude Code CLI not available
pytestmark = pytest.mark.skipif(
    shutil.which("claude") is None,
    reason="Claude Code CLI not installed"
)


@pytest.fixture
def temp_session_file():
    """Create a temporary session file for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "claude_sessions.json"
        with patch("rubber_duck.agent.claude_code.SESSION_FILE", session_file):
            yield session_file


@pytest.mark.anyio
async def test_run_claude_code_simple_prompt():
    """Test simple prompt execution with Claude Code."""
    from rubber_duck.agent.claude_code import run_claude_code

    response, session_id = await run_claude_code(
        prompt="What is 2+2? Reply with just the number, nothing else.",
    )

    # Response should contain "4"
    assert "4" in response
    # Session ID should be returned
    assert session_id is not None


@pytest.mark.anyio
async def test_run_claude_code_with_system_prompt():
    """Test with additional system prompt."""
    from rubber_duck.agent.claude_code import run_claude_code

    response, _ = await run_claude_code(
        prompt="What is my name?",
        system_prompt="The user's name is TestUser.",
    )

    assert "TestUser" in response


def test_build_system_prompt_with_real_blocks():
    """Test system prompt building with mock memory blocks."""
    from rubber_duck.agent.claude_code import build_system_prompt

    blocks = {
        "persona": "A software developer who likes Python",
        "patterns": "Works best in the morning",
        "current_focus": "Building a Discord bot",
        "communication": "Prefers concise responses",
        "guidelines": "Follow GTD methodology",
    }

    prompt = build_system_prompt(blocks)

    # Verify all blocks are included
    assert "software developer" in prompt
    assert "morning" in prompt
    assert "Discord bot" in prompt
    assert "concise" in prompt
    assert "GTD" in prompt
    assert "Current time:" in prompt


def test_session_persistence(temp_session_file):
    """Test session save and load."""
    from rubber_duck.agent.claude_code import load_session, save_session

    # Use a test channel ID
    test_channel_id = 999999999

    # Save a session
    save_session(test_channel_id, "test-session-id-12345")

    # Verify the file was created
    assert temp_session_file.exists()

    # Load it back
    loaded = load_session(test_channel_id)
    assert loaded == "test-session-id-12345"

    # Verify file content
    data = json.loads(temp_session_file.read_text())
    assert data[str(test_channel_id)] == "test-session-id-12345"


def test_session_load_nonexistent():
    """Test loading a session that doesn't exist."""
    from rubber_duck.agent.claude_code import load_session

    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "nonexistent.json"
        with patch("rubber_duck.agent.claude_code.SESSION_FILE", session_file):
            loaded = load_session(123456789)
            assert loaded is None


def test_session_load_missing_channel(temp_session_file):
    """Test loading a channel that doesn't exist in session file."""
    from rubber_duck.agent.claude_code import load_session, save_session

    # Save a session for one channel
    save_session(111111111, "session-a")

    # Try to load a different channel
    loaded = load_session(222222222)
    assert loaded is None
