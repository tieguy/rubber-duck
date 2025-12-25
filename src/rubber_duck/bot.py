"""Discord bot client for Rubber Duck."""

import logging
import os

import discord
from discord.ext import commands

from rubber_duck.handlers.conversation import handle_message
from rubber_duck.scheduler import setup_scheduler

logger = logging.getLogger(__name__)


class RubberDuck(commands.Bot):
    """The main Rubber Duck Discord bot."""

    def __init__(self, owner_id: int):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True

        super().__init__(command_prefix="!", intents=intents)
        self.owner_id = owner_id
        self.scheduler = None

    async def setup_hook(self) -> None:
        """Called when the bot is starting up."""
        self.scheduler = await setup_scheduler(self)
        logger.info("Scheduler initialized")

    async def on_ready(self) -> None:
        """Called when the bot has connected to Discord."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Owner ID: {self.owner_id}")

    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages."""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Only respond to DMs from the owner
        if isinstance(message.channel, discord.DMChannel):
            if message.author.id == self.owner_id:
                await handle_message(self, message)
            else:
                logger.warning(f"Ignoring DM from non-owner: {message.author.id}")

        # Process commands if any
        await self.process_commands(message)


def create_bot() -> RubberDuck:
    """Create and configure the bot instance."""
    owner_id = os.environ.get("DISCORD_OWNER_ID")
    if not owner_id:
        raise ValueError("DISCORD_OWNER_ID environment variable is required")

    return RubberDuck(owner_id=int(owner_id))


async def run_bot() -> None:
    """Run the bot."""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

    bot = create_bot()
    await bot.start(token)
