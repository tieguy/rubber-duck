# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Shared utilities for the agent module."""

import asyncio
import concurrent.futures


def run_async(coro):
    """Run an async coroutine from sync context safely.

    Handles the case where we're called from within an existing async loop
    by running the coroutine in a thread pool.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
