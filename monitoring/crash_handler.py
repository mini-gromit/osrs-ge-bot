"""
Crash detection and reporting for bot health monitoring.

Provides crash state tracking and notification sending.
"""
import os
import json
import logging
import asyncio
import discord
from typing import Optional
from .renderer import MonitoringRenderer

logger = logging.getLogger(__name__)

CRASH_STATE_FILE = "crash_state.json"


class CrashHandler:
    """
    Handles crash detection, state persistence, and notifications.

    Tracks bot lifecycle states:
    - crashed: Unhandled exception occurred
    - running: Bot is currently running
    - graceful_shutdown: Bot shut down gracefully
    """

    @staticmethod
    def mark_running():
        """Mark that the bot is running"""
        try:
            with open(CRASH_STATE_FILE, 'w') as f:
                json.dump({'running': True, 'graceful_shutdown': False, 'crashed': False}, f)
        except Exception as e:
            logger.error(f"Failed to write running state: {e}")

    @staticmethod
    def mark_crash():
        """Mark that the bot crashed"""
        try:
            with open(CRASH_STATE_FILE, 'w') as f:
                json.dump({'crashed': True, 'running': False, 'graceful_shutdown': False}, f)
        except Exception as e:
            logger.error(f"Failed to write crash state file: {e}")

    @staticmethod
    def mark_graceful_shutdown():
        """Mark that the bot shut down gracefully"""
        try:
            with open(CRASH_STATE_FILE, 'w') as f:
                json.dump({'graceful_shutdown': True, 'running': False, 'crashed': False}, f)
        except Exception as e:
            logger.error(f"Failed to write graceful shutdown state: {e}")

    @staticmethod
    def clear_state():
        """Clear all state (clean startup)"""
        try:
            if os.path.exists(CRASH_STATE_FILE):
                os.remove(CRASH_STATE_FILE)
        except Exception as e:
            logger.error(f"Failed to clear crash state file: {e}")

    @staticmethod
    def had_previous_crash() -> bool:
        """
        Check if bot crashed previously.

        Returns:
            True if bot crashed previously
        """
        try:
            if os.path.exists(CRASH_STATE_FILE):
                with open(CRASH_STATE_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get('crashed', False)
        except Exception:
            pass
        return False

    @staticmethod
    def had_unexpected_shutdown() -> bool:
        """
        Check if bot had an unexpected shutdown (not crash, not graceful).

        Returns:
            True if bot was running but didn't shut down gracefully or crash
        """
        try:
            if os.path.exists(CRASH_STATE_FILE):
                with open(CRASH_STATE_FILE, 'r') as f:
                    data = json.load(f)
                    # Unexpected shutdown = was running, didn't crash, didn't shutdown gracefully
                    was_running = data.get('running', False)
                    crashed = data.get('crashed', False)
                    graceful = data.get('graceful_shutdown', False)
                    return was_running and not crashed and not graceful
        except Exception:
            pass
        return False

    # Flag to prevent duplicate shutdown notifications
    _shutdown_notification_sent = False

    @staticmethod
    async def send_crash_notification(
        bot,
        exception_type: str,
        exception_message: str
    ):
        """
        Send crash notification to events channel.

        Args:
            bot: Discord bot instance
            exception_type: Type of exception that caused crash
            exception_message: Exception message
        """
        try:
            # Prevent duplicate notifications
            if CrashHandler._shutdown_notification_sent:
                return
            CrashHandler._shutdown_notification_sent = True

            # Load channel config
            if not bot.channel_config or not bot.channel_config.events_channel:
                logger.warning("No events channel configured for crash notification")
                return

            # Create crash embed
            embed = MonitoringRenderer.create_crash_event_embed(
                exception_type,
                exception_message
            )

            # Send to events channel
            channel = bot.get_channel(bot.channel_config.events_channel)
            if channel:
                await channel.send(embed=embed)
                logger.info("[MONITORING] Sent crash notification to events channel")
            else:
                logger.warning(f"Events channel {bot.channel_config.events_channel} not found")

        except Exception as e:
            logger.error(f"Failed to send crash notification: {e}")

    @staticmethod
    async def send_shutdown_notification(bot):
        """
        Send graceful shutdown notification to events channel.

        Args:
            bot: Discord bot instance
        """
        try:
            # Prevent duplicate notifications
            if CrashHandler._shutdown_notification_sent:
                return
            CrashHandler._shutdown_notification_sent = True

            if not bot.channel_config or not bot.channel_config.events_channel:
                logger.warning("No events channel configured for shutdown notification")
                return

            # Get uptime from monitoring manager
            status = bot.monitoring.get_status()
            uptime = status.uptime_formatted()

            # Create shutdown embed with uptime
            embed = MonitoringRenderer.create_shutdown_event_embed(uptime=uptime)

            # Send to events channel
            channel = bot.get_channel(bot.channel_config.events_channel)
            if channel:
                await channel.send(embed=embed)
                logger.info("[MONITORING] Sent shutdown notification to events channel")
            else:
                logger.warning(f"Events channel {bot.channel_config.events_channel} not found")

        except Exception as e:
            logger.error(f"Failed to send shutdown notification: {e}")

    @staticmethod
    async def send_unexpected_shutdown_notification(bot):
        """
        Send unexpected shutdown notification to events channel.

        Args:
            bot: Discord bot instance
        """
        try:
            if not bot.channel_config or not bot.channel_config.events_channel:
                logger.warning("No events channel configured for unexpected shutdown notification")
                return

            # Create unexpected shutdown embed
            embed = MonitoringRenderer.create_unexpected_shutdown_embed()

            # Send to events channel
            channel = bot.get_channel(bot.channel_config.events_channel)
            if channel:
                await channel.send(embed=embed)
                logger.info("[MONITORING] Sent unexpected shutdown notification to events channel")
            else:
                logger.warning(f"Events channel {bot.channel_config.events_channel} not found")

        except Exception as e:
            logger.error(f"Failed to send unexpected shutdown notification: {e}")

    @staticmethod
    async def update_status_dashboard_for_crash(bot):
        """
        Update status dashboard to show crashed state.

        Args:
            bot: Discord bot instance
        """
        try:
            if not bot.channel_config or not bot.channel_config.status_channel:
                return

            # Get current status
            status = bot.monitoring.get_status()

            # Override state to unhealthy
            from .models import HealthState
            status.state = HealthState.UNHEALTHY

            # Create status embed
            embed = MonitoringRenderer.create_status_dashboard_embed(status)

            # Update status message
            if bot.channel_config.status_message_id:
                channel = bot.get_channel(bot.channel_config.status_channel)
                if channel:
                    try:
                        msg = await channel.fetch_message(bot.channel_config.status_message_id)
                        await msg.edit(embed=embed)
                        logger.info("[MONITORING] Updated status dashboard for crash")
                    except discord.NotFound:
                        # Message was deleted, create new one
                        msg = await channel.send(embed=embed)
                        bot.channel_config.status_message_id = msg.id
                        await bot.save_channel_config()

        except Exception as e:
            logger.error(f"Failed to update status dashboard for crash: {e}")

    @staticmethod
    async def update_status_dashboard_for_shutdown(bot):
        """
        Update status dashboard to show stopped state.

        Args:
            bot: Discord bot instance
        """
        try:
            if not bot.channel_config or not bot.channel_config.status_channel:
                return

            # Get current status
            status = bot.monitoring.get_status()

            # Override state to warning (stopping)
            from .models import HealthState
            status.state = HealthState.WARNING

            # Create status embed with "Stopping" state
            embed = MonitoringRenderer.create_status_dashboard_embed(status)
            # Update title to indicate stopping
            embed.title = "🟡 OSRS GE Bot - Stopping"

            # Update status message
            if bot.channel_config.status_message_id:
                channel = bot.get_channel(bot.channel_config.status_channel)
                if channel:
                    try:
                        msg = await channel.fetch_message(bot.channel_config.status_message_id)
                        await msg.edit(embed=embed)
                        logger.info("[MONITORING] Updated status dashboard for shutdown")
                    except discord.NotFound:
                        # Message was deleted, can't update
                        pass

        except Exception as e:
            logger.error(f"Failed to update status dashboard for shutdown: {e}")


async def handle_graceful_shutdown(bot):
    """
    Handle graceful shutdown.

    Updates status dashboard, sends notification, marks state.

    Args:
        bot: Discord bot instance
    """
    try:
        logger.info("[MONITORING] Graceful shutdown initiated")

        # Mark graceful shutdown state
        CrashHandler.mark_graceful_shutdown()

        # Update status dashboard
        await CrashHandler.update_status_dashboard_for_shutdown(bot)

        # Send shutdown notification
        await CrashHandler.send_shutdown_notification(bot)

        # Give Discord time to send messages
        await asyncio.sleep(2)

        # Close bot connection
        await bot.close()

    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}")


async def run_with_crash_detection(bot_factory, token: str):
    """
    Run bot with crash detection, shutdown handling, and lifecycle tracking.

    Handles:
    - Crash detection and recovery
    - Graceful shutdown (KeyboardInterrupt, SIGINT, SIGTERM)
    - Unexpected shutdown detection

    Args:
        bot_factory: Async function that creates and returns a bot instance
        token: Discord bot token

    Raises:
        Exception: Re-raises the exception after handling
    """
    import signal

    bot = None

    # Reset shutdown notification flag on startup
    CrashHandler._shutdown_notification_sent = False

    try:
        # Check previous state
        had_crash = CrashHandler.had_previous_crash()
        had_unexpected_shutdown = CrashHandler.had_unexpected_shutdown()

        # Create bot
        bot = await bot_factory()

        # Mark previous lifecycle state in monitoring
        if had_crash:
            bot.monitoring.previous_crash = True
            logger.info("[MONITORING] Detected previous crash - will send recovery notification")
        elif had_unexpected_shutdown:
            logger.info("[MONITORING] Detected unexpected shutdown - will send notification")
            # Send unexpected shutdown notification
            if bot.channel_config and bot.channel_config.events_channel:
                await CrashHandler.send_unexpected_shutdown_notification(bot)

        # Clear previous state and mark as running
        CrashHandler.mark_running()

        # Register signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            """Handle SIGINT and SIGTERM"""
            logger.info(f"[MONITORING] Received signal {signum}")
            # Create task to handle graceful shutdown
            if bot:
                asyncio.create_task(handle_graceful_shutdown(bot))

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start bot
        await bot.start(token)

    except KeyboardInterrupt:
        logger.info("[MONITORING] KeyboardInterrupt received - shutting down gracefully")
        if bot:
            await handle_graceful_shutdown(bot)

    except Exception as e:
        import traceback
        logger.error(f"Bot crashed: {e}")
        logger.error(traceback.format_exc())

        # Mark crash state
        CrashHandler.mark_crash()

        # Try to send crash notification
        if bot:
            try:
                # Send crash notification
                exception_type = type(e).__name__
                exception_message = str(e)

                await CrashHandler.send_crash_notification(
                    bot,
                    exception_type,
                    exception_message
                )

                # Update status dashboard
                await CrashHandler.update_status_dashboard_for_crash(bot)

                # Give Discord time to send messages
                await asyncio.sleep(2)

            except Exception as notify_error:
                logger.error(f"Failed to send crash notification: {notify_error}")

        # Re-raise to allow normal exit
        raise
