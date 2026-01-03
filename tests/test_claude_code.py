# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Tests for Claude Code executor."""

import pytest
from rubber_duck.agent.claude_code import parse_ndjson_line, ClaudeCodeEvent


def test_parse_ndjson_text_event():
    """Parse a text content event."""
    line = '{"type":"assistant","message":{"content":[{"type":"text","text":"Hello"}]}}'
    event = parse_ndjson_line(line)
    assert event is not None
    assert event.type == "assistant"
    assert event.text == "Hello"


def test_parse_ndjson_tool_use_event():
    """Parse a tool use event."""
    line = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"123"}]}}'
    event = parse_ndjson_line(line)
    assert event is not None
    assert event.type == "tool_use"
    assert event.tool_name == "Read"


def test_parse_ndjson_result_event():
    """Parse a final result event."""
    line = '{"type":"result","result":"Final response","session_id":"abc123"}'
    event = parse_ndjson_line(line)
    assert event is not None
    assert event.type == "result"
    assert event.text == "Final response"
    assert event.session_id == "abc123"


def test_parse_invalid_json():
    """Invalid JSON returns None."""
    event = parse_ndjson_line("not json")
    assert event is None
