# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

"""Conversation handler for Rubber Duck."""

import asyncio
import logging

import discord

from rubber_duck.agent.loop import AgentCallbacks, run_agent_loop_interactive

logger = logging.getLogger(__name__)

# Cancellation keywords
CANCEL_KEYWORDS = {"stop", "cancel"}

# Checkpoint timeout (15 minutes)
CHECKPOINT_TIMEOUT = 15 * 60

# Continue keywords for checkpoint
CONTINUE_KEYWORDS = {"yes", "continue", "go", "ok", "keep going"}


class InteractiveSession:
    """Manages state for an interactive agent session."""

    def __init__(self, bot, channel: discord.DMChannel, status_msg: discord.Message):
        self.bot = bot
        self.channel = channel
        self.status_msg = status_msg
        self.cancelled = False
        self.tool_log: list[str] = []
        self._message_queue: asyncio.Queue[str] = asyncio.Queue()
        self._listener_task: asyncio.Task | None = None

    def start_listening(self) -> None:
        """Start listening for new messages."""
        self._listener_task = asyncio.create_task(self._listen_for_messages())

    def stop_listening(self) -> None:
        """Stop the message listener."""
        if self._listener_task:
            self._listener_task.cancel()

    async def _listen_for_messages(self) -> None:
        """Background task to watch for cancellation/control messages."""

        def check(m: discord.Message) -> bool:
            return (
                m.channel == self.channel
                and m.author != self.bot.user
                and m.author.id == self.bot.owner_id
            )

        while True:
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=None)
                content = msg.content.strip().lower()

                if content in CANCEL_KEYWORDS:
                    self.cancelled = True
                    logger.info("Cancellation requested by user")

                # Queue any message for checkpoint handling
                await self._message_queue.put(content)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in message listener: {e}")

    async def on_tool_start(self, tool_name: str) -> None:
        """Called when a tool starts executing."""
        self.tool_log.append(f"🔧 {tool_name} ...")
        await self._update_status()

    async def on_tool_end(self, tool_name: str, success: bool) -> None:
        """Called when a tool finishes executing."""
        symbol = "✓" if success else "✗"
        # Update the last entry for this tool
        for i in range(len(self.tool_log) - 1, -1, -1):
            if tool_name in self.tool_log[i]:
                self.tool_log[i] = f"🔧 {tool_name} {symbol}"
                break
        await self._update_status()

    async def check_cancelled(self) -> bool:
        """Check if the user has requested cancellation."""
        return self.cancelled

    async def on_checkpoint(self, tools_used: int) -> bool:
        """Called when hitting the tool limit. Returns True to continue."""
        checkpoint_msg = (
            f"Used {tools_used} tools. Reply 'yes' to continue or 'stop' to cancel.\n\n"
            + "\n".join(self.tool_log)
        )
        await self.status_msg.edit(content=checkpoint_msg)

        # Wait for response with timeout
        try:
            # Drain any queued messages first
            while not self._message_queue.empty():
                try:
                    self._message_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            # Wait for new message
            response = await asyncio.wait_for(
                self._message_queue.get(),
                timeout=CHECKPOINT_TIMEOUT,
            )

            if response in CANCEL_KEYWORDS:
                return False
            elif response in CONTINUE_KEYWORDS:
                # Clear the checkpoint message and continue
                await self.status_msg.edit(content="\n".join(self.tool_log))
                return True
            else:
                # Unclear response, treat as continue
                await self.status_msg.edit(content="\n".join(self.tool_log))
                return True

        except asyncio.TimeoutError:
            logger.info("Checkpoint timed out")
            return False

    async def _update_status(self) -> None:
        """Update the status message with current tool log."""
        if self.tool_log:
            try:
                await self.status_msg.edit(content="\n".join(self.tool_log))
            except discord.HTTPException as e:
                logger.warning(f"Failed to update status message: {e}")

    def get_callbacks(self) -> AgentCallbacks:
        """Get the callbacks for the agent loop."""
        return AgentCallbacks(
            on_tool_start=self.on_tool_start,
            on_tool_end=self.on_tool_end,
            check_cancelled=self.check_cancelled,
            on_checkpoint=self.on_checkpoint,
        )


async def handle_message(bot, message: discord.Message) -> None:
    """Handle an incoming message from the owner.

    Args:
        bot: The Discord bot instance
        message: The Discord message to handle
    """
    content = message.content.strip()

    if not content:
        return

    logger.info(f"Handling message from owner: {content[:50]}...")

    try:
        # Send initial status message
        status_msg = await message.reply("🤔 Starting...")

        # Create interactive session
        session = InteractiveSession(bot, message.channel, status_msg)
        session.start_listening()

        try:
            response = await run_agent_loop_interactive(
                content,
                callbacks=session.get_callbacks(),
            )
            await status_msg.edit(content=response)
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            await status_msg.edit(
                content="Sorry, something went wrong processing your message."
            )
        finally:
            session.stop_listening()

    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        await message.reply("Sorry, something went wrong processing your message.")
