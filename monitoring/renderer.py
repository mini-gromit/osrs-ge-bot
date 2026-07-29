"""
Discord renderer for bot health monitoring.

Responsible only for rendering BotStatus into Discord embeds.
Contains no monitoring logic or business logic.
"""
import discord
from datetime import datetime
from .models import BotStatus, ServiceHealth, HealthState


class MonitoringRenderer:
    """Renders monitoring data into Discord embeds"""

    @staticmethod
    def _get_state_emoji(state: HealthState) -> str:
        """
        Get emoji for a health state.

        Args:
            state: Health state

        Returns:
            Emoji string
        """
        emoji_map = {
            HealthState.HEALTHY: "🟢",
            HealthState.WARNING: "🟡",
            HealthState.UNHEALTHY: "🔴",
            HealthState.UNKNOWN: "⚪",
        }
        return emoji_map.get(state, "⚪")

    @staticmethod
    def _format_started_time(started_at: datetime) -> str:
        """
        Format started timestamp in a human-friendly way.

        Args:
            started_at: When the bot started

        Returns:
            Formatted string like "Today, 8:31 PM" or "Jul 28, 8:31 PM"
        """
        from datetime import timedelta

        now = datetime.now()

        # Check if started today
        if started_at.date() == now.date():
            time_str = started_at.strftime("%I:%M %p").lstrip("0")
            return f"Today, {time_str}"

        # Check if started yesterday
        yesterday = (now - timedelta(days=1)).date()
        if started_at.date() == yesterday:
            time_str = started_at.strftime("%I:%M %p").lstrip("0")
            return f"Yesterday, {time_str}"

        # Different day - show month abbreviation
        date_str = started_at.strftime("%b %d").replace(" 0", " ")
        time_str = started_at.strftime("%I:%M %p").lstrip("0")
        return f"{date_str}, {time_str}"

    @staticmethod
    def _format_time_ago(service: ServiceHealth) -> str:
        """
        Format time since last success for a service.

        Args:
            service: Service health object

        Returns:
            Formatted string like "24 sec ago" or "Never"
        """
        if service.last_success is None:
            return "Never"

        seconds = service.seconds_since_success()

        if seconds < 60:
            return f"{int(seconds)} sec ago"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m ago"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}d {hours}h ago"

    @staticmethod
    def create_status_dashboard_embed(status: BotStatus) -> discord.Embed:
        """
        Create status dashboard embed.

        Args:
            status: Bot status snapshot

        Returns:
            Discord embed for status dashboard
        """
        # Determine embed color based on overall state
        color_map = {
            HealthState.HEALTHY: discord.Color.green(),
            HealthState.WARNING: discord.Color.yellow(),
            HealthState.UNHEALTHY: discord.Color.red(),
            HealthState.UNKNOWN: discord.Color.light_gray(),
        }
        embed_color = color_map.get(status.state, discord.Color.light_gray())

        # Create embed
        state_emoji = MonitoringRenderer._get_state_emoji(status.state)
        embed = discord.Embed(
            title=f"{state_emoji} OSRS GE Bot",
            color=embed_color,
            timestamp=datetime.now()
        )

        # Status and version
        embed.add_field(
            name="Status",
            value=status.state.value.capitalize(),
            inline=True
        )
        embed.add_field(
            name="Version",
            value=status.version,
            inline=True
        )
        embed.add_field(
            name="Uptime",
            value=status.uptime_formatted(),
            inline=True
        )

        # Service health - Current Prices
        current_prices_emoji = MonitoringRenderer._get_state_emoji(status.current_prices.state)
        current_prices_time = MonitoringRenderer._format_time_ago(status.current_prices)
        embed.add_field(
            name="Current Prices",
            value=f"{current_prices_emoji} {current_prices_time}",
            inline=True
        )

        # Service health - 5 Minute Data
        five_min_emoji = MonitoringRenderer._get_state_emoji(status.five_minute_data.state)
        five_min_time = MonitoringRenderer._format_time_ago(status.five_minute_data)
        embed.add_field(
            name="5 Minute Data",
            value=f"{five_min_emoji} {five_min_time}",
            inline=True
        )

        # Service health - History Store
        history_emoji = MonitoringRenderer._get_state_emoji(status.history_store.state)
        history_status = "Healthy" if status.history_store.state == HealthState.HEALTHY else history_emoji
        embed.add_field(
            name="History Store",
            value=f"{history_emoji} {history_status}",
            inline=True
        )

        # Service health - Discord
        discord_emoji = MonitoringRenderer._get_state_emoji(status.discord.state)
        discord_status = "Connected" if status.discord.state == HealthState.HEALTHY else "Disconnected"
        embed.add_field(
            name="Discord",
            value=f"{discord_emoji} {discord_status}",
            inline=True
        )

        # Service health - Alerts
        alerts_emoji = MonitoringRenderer._get_state_emoji(status.alerts.state)
        alerts_status = "Healthy" if status.alerts.state == HealthState.HEALTHY else alerts_emoji
        embed.add_field(
            name="Alerts",
            value=f"{alerts_emoji} {alerts_status}",
            inline=True
        )

        # Blank field for alignment
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Metrics
        embed.add_field(
            name="Items Tracked",
            value=f"{status.items_tracked:,}",
            inline=True
        )
        embed.add_field(
            name="History Items",
            value=f"{status.history_items:,}",
            inline=True
        )
        embed.add_field(
            name="Memory",
            value=f"{int(status.memory_mb)} MB",
            inline=True
        )

        # Started timestamp
        started_formatted = MonitoringRenderer._format_started_time(status.started_at)
        embed.add_field(
            name="Started",
            value=started_formatted,
            inline=False
        )

        return embed

    @staticmethod
    def create_startup_event_embed(status: BotStatus, recovered: bool = False) -> discord.Embed:
        """
        Create startup/recovery event embed.

        Args:
            status: Bot status snapshot
            recovered: True if recovering from previous crash

        Returns:
            Discord embed for startup event
        """
        if recovered:
            embed = discord.Embed(
                title="🟡 Bot Restarted",
                description="Recovered after previous failure.",
                color=discord.Color.yellow(),
                timestamp=datetime.now()
            )
        else:
            embed = discord.Embed(
                title="🟢 Bot Started",
                description=f"Version: {status.version}\nUptime begins now.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )

        return embed

    @staticmethod
    def create_crash_event_embed(exception_type: str, exception_message: str) -> discord.Embed:
        """
        Create crash notification embed.

        Args:
            exception_type: Type of exception that caused crash
            exception_message: Exception message

        Returns:
            Discord embed for crash event
        """
        embed = discord.Embed(
            title="🔴 Bot Crashed",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="Exception Type",
            value=exception_type,
            inline=False
        )

        # Truncate message if too long
        if len(exception_message) > 1000:
            exception_message = exception_message[:997] + "..."

        embed.add_field(
            name="Exception Message",
            value=exception_message or "No message",
            inline=False
        )

        return embed

    @staticmethod
    def create_health_change_embed(
        service_name: str,
        old_state: HealthState,
        new_state: HealthState,
        time_ago: str = None,
        error_message: str = None
    ) -> discord.Embed:
        """
        Create health state change notification embed.

        Args:
            service_name: Name of the service
            old_state: Previous health state
            new_state: New health state
            time_ago: Optional time since last success
            error_message: Optional error message

        Returns:
            Discord embed for health change event
        """
        # Determine emoji and color
        emoji = MonitoringRenderer._get_state_emoji(new_state)
        color_map = {
            HealthState.HEALTHY: discord.Color.green(),
            HealthState.WARNING: discord.Color.yellow(),
            HealthState.UNHEALTHY: discord.Color.red(),
            HealthState.UNKNOWN: discord.Color.light_gray(),
        }
        color = color_map.get(new_state, discord.Color.light_gray())

        # Determine title
        if new_state == HealthState.HEALTHY:
            title = f"{emoji} {service_name} recovered"
        elif new_state == HealthState.WARNING:
            title = f"{emoji} {service_name} warning"
        else:
            title = f"{emoji} {service_name} unhealthy"

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now()
        )

        # Add time ago if provided
        if time_ago:
            embed.add_field(
                name="Last successful refresh",
                value=time_ago,
                inline=False
            )

        # Add error message if provided
        if error_message:
            if len(error_message) > 500:
                error_message = error_message[:497] + "..."
            embed.add_field(
                name="Error",
                value=error_message,
                inline=False
            )

        return embed

    @staticmethod
    def create_reconnect_embed() -> discord.Embed:
        """
        Create Discord reconnection event embed.

        Returns:
            Discord embed for reconnect event
        """
        embed = discord.Embed(
            title="🟡 Discord reconnected",
            color=discord.Color.yellow(),
            timestamp=datetime.now()
        )
        return embed

    @staticmethod
    def create_shutdown_event_embed(uptime: str = None) -> discord.Embed:
        """
        Create graceful shutdown event embed.

        Args:
            uptime: Formatted uptime string (e.g., "1h 17m")

        Returns:
            Discord embed for shutdown event
        """
        description = "Graceful shutdown completed."
        if uptime:
            description += f"\nUptime: {uptime}"

        embed = discord.Embed(
            title="🟡 Bot Stopped",
            description=description,
            color=discord.Color.yellow(),
            timestamp=datetime.now()
        )
        return embed

    @staticmethod
    def create_unexpected_shutdown_embed() -> discord.Embed:
        """
        Create unexpected shutdown event embed.

        Returns:
            Discord embed for unexpected shutdown event
        """
        embed = discord.Embed(
            title="🟡 Bot Restarted",
            description="Restarted after unexpected shutdown.",
            color=discord.Color.yellow(),
            timestamp=datetime.now()
        )
        return embed
