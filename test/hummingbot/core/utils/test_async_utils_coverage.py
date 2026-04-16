"""Coverage tests for hummingbot/core/utils/async_utils.py - line 40 (run_command)."""

import pytest

from hummingbot.core.utils.async_utils import run_command


@pytest.mark.asyncio
async def test_run_command_returns_stdout():
    """Line 40: run_command creates subprocess, communicates, and returns decoded stdout."""
    result = await run_command("echo", "hello")
    assert result == "hello"


@pytest.mark.asyncio
async def test_run_command_strips_output():
    """Line 40-42: run_command strips trailing whitespace/newlines from stdout."""
    result = await run_command("printf", "  trimmed  ")
    assert result == "trimmed"
