"""
Notifications Cog - User notification preference management.

Provides /notifications slash command for viewing and editing personal notification settings.
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import config

logger = logging.getLogger(__name__)


class NotificationsCog(commands.Cog, name="Notifications"):
    """Commands for managing personal notification preferences"""

    # Valid notification types for personal notifications
    NOTIFICATION_TYPES = ['all_alchs', 'f2p_alchs', 'crash_risk', 'flipping_trend']

    def __init__(self, bot):
        self.bot = bot

    async def type_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for notification type parameter."""
        return [
            app_commands.Choice(name=ntype, value=ntype)
            for ntype in self.NOTIFICATION_TYPES
            if current.lower() in ntype.lower()
        ]

    @app_commands.command(name="notifications", description="View or edit your notification preferences")
    @app_commands.describe(
        type="Notification type to configure",
        enabled="Enable (True) or disable (False) notifications",
        min_profit="Minimum profit threshold in gp (for alchemy notifications)"
    )
    @app_commands.autocomplete(type=type_autocomplete)
    async def notifications(
        self,
        interaction: discord.Interaction,
        type: str = None,
        enabled: bool = None,
        min_profit: int = None
    ):
        """
        View or edit notification preferences.

        Usage:
        - /notifications - Display current preferences
        - /notifications type:all_alchs enabled:True - Enable alchemy notifications
        - /notifications type:all_alchs enabled:False - Disable alchemy notifications
        - /notifications type:all_alchs min_profit:3500 - Update profit threshold
        - /notifications type:all_alchs enabled:True min_profit:3500 - Enable and set threshold
        """
        user_id = interaction.user.id

        # If no arguments, display current preferences
        if type is None and enabled is None and min_profit is None:
            await self._display_preferences(interaction, user_id)
            return

        # If type specified, update preferences and/or subscription
        if type is not None:
            await self._update_preferences(interaction, user_id, type, enabled, min_profit)
            return

        # Edge case: parameters specified without type
        await interaction.response.send_message(
            "❌ Please specify a notification type.",
            ephemeral=True
        )

    async def _display_preferences(self, interaction: discord.Interaction, user_id: int):
        """Display user's current notification preferences."""
        preference_store = self.bot.preference_store
        notification_manager = self.bot.notification_manager

        # Get user subscriptions
        user_subs = notification_manager.user_subscriptions.get(user_id, set())

        # Build embed
        embed = discord.Embed(
            title="🔔 Personal Notifications",
            description="Your current notification preferences",
            color=discord.Color.blue()
        )

        # Alchemy notifications
        all_alchs_enabled = 'all_alchs' in user_subs
        all_alchs_profit = preference_store.get_user_min_profit(user_id, 'all_alchs')

        embed.add_field(
            name="🧪 Alchemy",
            value=(
                f"{'✓' if all_alchs_enabled else '✗'} "
                f"{'Enabled' if all_alchs_enabled else 'Disabled'}\n"
                f"Minimum Profit: {all_alchs_profit:,} gp"
            ),
            inline=False
        )

        # F2P Alchemy notifications
        f2p_alchs_enabled = 'f2p_alchs' in user_subs
        f2p_alchs_profit = preference_store.get_user_min_profit(user_id, 'f2p_alchs')

        embed.add_field(
            name="🆓 F2P Alchemy",
            value=(
                f"{'✓' if f2p_alchs_enabled else '✗'} "
                f"{'Enabled' if f2p_alchs_enabled else 'Disabled'}\n"
                f"Minimum Profit: {f2p_alchs_profit:,} gp"
            ),
            inline=False
        )

        # Crash Risk notifications
        crash_risk_enabled = 'crash_risk' in user_subs
        crash_risk_severity = preference_store.get_min_severity(user_id, 'crash_risk')

        embed.add_field(
            name="💥 Crash Risk",
            value=(
                f"{'✓' if crash_risk_enabled else '✗'} "
                f"{'Enabled' if crash_risk_enabled else 'Disabled'}\n"
                f"Minimum Severity: {crash_risk_severity}"
            ),
            inline=False
        )

        # Flipping Trends notifications
        flipping_trend_enabled = 'flipping_trend' in user_subs
        flipping_trend_severity = preference_store.get_min_severity(user_id, 'flipping_trend')

        embed.add_field(
            name="📈 Flipping Trends",
            value=(
                f"{'✓' if flipping_trend_enabled else '✗'} "
                f"{'Enabled' if flipping_trend_enabled else 'Disabled'}\n"
                f"Minimum Severity: {flipping_trend_severity}"
            ),
            inline=False
        )

        # Add footer with instructions
        embed.set_footer(
            text="Use /notifications type:<type> enabled:True/False to enable or disable. "
                 "Use min_profit:<value> to change profit thresholds."
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _update_preferences(
        self,
        interaction: discord.Interaction,
        user_id: int,
        notif_type: str,
        enabled: bool,
        min_profit: int
    ):
        """Update user's notification preferences and subscription with validation."""
        preference_store = self.bot.preference_store
        notification_manager = self.bot.notification_manager

        # Validate notification type
        if notif_type not in self.NOTIFICATION_TYPES:
            await interaction.response.send_message(
                f"❌ Invalid notification type: `{notif_type}`\n"
                f"Valid types: {', '.join(self.NOTIFICATION_TYPES)}",
                ephemeral=True
            )
            return

        # Type labels for user-friendly messages
        type_labels = {
            'all_alchs': '🧪 Alchemy',
            'f2p_alchs': '🆓 F2P Alchemy',
            'crash_risk': '💥 Crash Risk',
            'flipping_trend': '📈 Flipping Trends'
        }
        label = type_labels.get(notif_type, notif_type)

        # Handle subscription enable/disable
        if enabled is not None:
            if enabled:
                # Subscribe user
                was_new = notification_manager.subscribe_user(user_id, notif_type)
                if was_new:
                    logger.info(f"User {user_id} subscribed to {notif_type} via /notifications")
            else:
                # Unsubscribe user
                was_removed = notification_manager.unsubscribe_user(user_id, notif_type)
                if was_removed:
                    logger.info(f"User {user_id} unsubscribed from {notif_type} via /notifications")

        # Handle preference updates for alchemy notifications
        if notif_type in ['all_alchs', 'f2p_alchs']:
            if min_profit is not None:
                # Validate min_profit
                if min_profit < config.MIN_PROFIT_THRESHOLD:
                    await interaction.response.send_message(
                        f"❌ Minimum profit must be at least {config.MIN_PROFIT_THRESHOLD} gp.",
                        ephemeral=True
                    )
                    return

                if min_profit > config.MAX_PROFIT_THRESHOLD:
                    await interaction.response.send_message(
                        f"❌ Minimum profit cannot exceed {config.MAX_PROFIT_THRESHOLD:,} gp.",
                        ephemeral=True
                    )
                    return

                # Update preference
                preference_store.set_user_min_profit(user_id, notif_type, min_profit)
        else:
            # crash_risk and flipping_trend don't support min_profit
            if min_profit is not None:
                await interaction.response.send_message(
                    f"❌ The `{notif_type}` notification type does not support min_profit configuration.\n"
                    f"Only `all_alchs` and `f2p_alchs` can be configured with min_profit.",
                    ephemeral=True
                )
                return

        # Build response message
        user_subs = notification_manager.user_subscriptions.get(user_id, set())
        is_subscribed = notif_type in user_subs

        # Determine what changed
        changes = []
        if enabled is not None:
            if enabled:
                changes.append("enabled")
            else:
                changes.append("disabled")

        if min_profit is not None:
            changes.append(f"minimum profit set to {min_profit:,} gp")

        if not changes:
            # No changes specified, show current status
            if notif_type in ['all_alchs', 'f2p_alchs']:
                current_profit = preference_store.get_user_min_profit(user_id, notif_type)
                await interaction.response.send_message(
                    f"**{label}**\n"
                    f"Status: {'✓ Enabled' if is_subscribed else '✗ Disabled'}\n"
                    f"Minimum Profit: {current_profit:,} gp\n\n"
                    f"Use `/notifications type:{notif_type} enabled:True` to enable.\n"
                    f"Use `/notifications type:{notif_type} min_profit:<value>` to change threshold.",
                    ephemeral=True
                )
            else:
                current_severity = preference_store.get_min_severity(user_id, notif_type)
                await interaction.response.send_message(
                    f"**{label}**\n"
                    f"Status: {'✓ Enabled' if is_subscribed else '✗ Disabled'}\n"
                    f"Minimum Severity: {current_severity}\n\n"
                    f"Use `/notifications type:{notif_type} enabled:True` to enable.",
                    ephemeral=True
                )
            return

        # Build success message
        message_parts = [f"✅ {label} notifications {changes[0]}"]
        if len(changes) > 1:
            message_parts.append(f" and {changes[1]}")
        message_parts.append(".")

        if is_subscribed and min_profit is not None:
            message_parts.append(
                f"\nYou will receive notifications for items with profit >= {min_profit:,} gp."
            )

        await interaction.response.send_message(
            "".join(message_parts),
            ephemeral=True
        )


async def setup(bot):
    """Load the notifications cog."""
    await bot.add_cog(NotificationsCog(bot))
