import re
import discord
from datetime import datetime
from typing import List, Dict, Optional
from events import CrashRiskEvent, FlippingTrendEvent


class DiscordRenderer:
    """
    Discord-specific presentation logic.

    Handles embed creation, formatting, colors, and Discord-specific rules.
    Consumes business/domain data and produces Discord embeds.
    """

    @staticmethod
    def get_item_ge_tracker_url(item_id: Optional[int] = None, item_name: Optional[str] = None) -> Optional[str]:
        """
        Generate GE-Tracker URL for an item.

        Args:
            item_id: Item ID (preferred)
            item_name: Item name (fallback)

        Returns:
            GE-Tracker URL or None
        """
        if item_id:
            return f"https://www.ge-tracker.com/item/{item_id}"

        if item_name:
            slug = (
                item_name.lower()
                .replace("'", "-")
                .replace(" ", "-")
                .replace("&", "and")
            )
            slug = re.sub(r'[^a-z0-9\-]', '', slug)
            return f"https://www.ge-tracker.com/item/{slug}"

        return None

    @staticmethod
    def create_alchemy_embed(items: List[Dict], title: str, color: discord.Color) -> discord.Embed:
        """
        Create a Discord embed for alchemy items.

        Args:
            items: List of alchemy item dicts
            title: Embed title
            color: Discord color

        Returns:
            Discord embed
        """
        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now()
        )

        if not items:
            embed.description = "No items found."
            return embed

        for i, item in enumerate(items[:10], 1):
            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=item.get('item_id'),
                item_name=item.get('name')
            )

            member_tag = "[M]" if item.get('members') else "[F2P]"

            embed.add_field(
                name=f"{i}. {member_tag} {item['name']}",
                value=(
                    f"[GE-Tracker]({ge_url})\n"
                    f"Profit: {item['profit']:,} gp\n"
                    f"Buy: {item['buy_price']:,} gp\n"
                    f"Alch: {item['high_alch_value']:,} gp\n"
                    f"ROI: {item['roi_percent']:.1f}%\n"
                    f"Current Profit: {item['profit']:,} gp\n"
                    f"5m Max Seen: "
                    f"{item.get('rolling_max_profit', item['profit']):,} gp"
                ),
                inline=True
            )

        return embed

    @staticmethod
    def create_notification_embed(items: List[Dict], title: str) -> discord.Embed:
        """
        Create a simpler Discord embed for personal notifications.

        Args:
            items: List of alchemy item dicts
            title: Notification title

        Returns:
            Discord embed
        """
        embed = discord.Embed(
            title=title,
            color=discord.Color.red(),
            timestamp=datetime.now()
        )

        for item in items[:5]:
            embed.add_field(
                name=item['name'],
                value=(
                    f"Profit: {item['profit']:,} gp\n"
                    f"ROI: {item['roi_percent']:.1f}%"
                ),
                inline=False
            )

        return embed

    @staticmethod
    def create_crash_risk_alert_embed(alerts: List[CrashRiskEvent], title: str = "🚨 Crash Risk Alerts") -> discord.Embed:
        """
        Create a Discord embed for crash risk alerts.

        Args:
            alerts: List of CrashRiskEvent objects
            title: Embed title

        Returns:
            Discord embed
        """
        # Determine embed color based on severity
        if any(alert.status == 'crashing' for alert in alerts):
            color = discord.Color.red()
        else:
            color = discord.Color.orange()

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now()
        )

        if not alerts:
            embed.description = "✅ No crash risks detected"
            return embed

        for alert in alerts[:10]:
            # Status emoji
            status_emoji = '🔴' if alert.status == 'crashing' else '🟡'

            # Recommendation emoji
            rec_emoji = '🔥' if alert.recommendation == 'buy low' else '⚠️'

            # Get GE-Tracker URL
            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=alert.item_id,
                item_name=alert.name
            )

            # Volume spike indicator
            vol_spike_emoji = '📈' if alert.volume_spike else ''

            embed.add_field(
                name=f"{status_emoji} {alert.name}",
                value=(
                    f"[GE-Tracker]({ge_url})\n"
                    f"**Status:** {alert.status}\n"
                    f"**Profit:** {alert.profit:,} gp\n"
                    f"**Buy:** {alert.buy_price:,} gp\n"
                    f"**Alch:** {alert.alch_value:,} gp\n"
                    f"**Volume Ratio:** {alert.volume_ratio:.1f}x\n"
                    f"**Hourly Volume:** {alert.hourly_volume:,} {vol_spike_emoji}\n"
                    f"**Severity:** {alert.severity_score}/100\n"
                    f"**Alert %:** {alert.alert_percent:.1f}%\n"
                    f"{rec_emoji} **Rec:** {alert.recommendation.upper()}"
                ),
                inline=True
            )

        embed.set_footer(text=f"Total alerts: {len(alerts)}")
        return embed

    @staticmethod
    def create_flipping_trend_alert_embed(alerts: List[FlippingTrendEvent], title: str = "📊 Market Trend Alerts") -> discord.Embed:
        """
        Create a Discord embed for flipping trend alerts.

        Args:
            alerts: List of FlippingTrendEvent objects
            title: Embed title

        Returns:
            Discord embed
        """
        # Determine color based on alert types
        statuses = [alert.status for alert in alerts]
        if 'surging' in statuses:
            color = discord.Color.green()
        elif 'crashing' in statuses:
            color = discord.Color.red()
        else:
            color = discord.Color.orange()

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now()
        )

        if not alerts:
            embed.description = "✅ No significant market movements detected"
            return embed

        for alert in alerts[:10]:
            # Status emoji
            status_emoji = {
                'crashing': '🔴',
                'crash_risk': '🟡',
                'surging': '🟢',
                'surge_risk': '🟠'
            }.get(alert.status, '⚪')

            # Recommendation emoji
            recommendation_emoji = {
                'avoid': '❌',
                'caution': '⚠️',
                'opportunity': '💰',
                'safe': '✅'
            }.get(alert.recommendation, '❓')

            # Get GE-Tracker URL
            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=alert.item_id,
                item_name=alert.name
            )

            # Volume spike indicator
            vol_spike_emoji = '📈' if alert.volume_spike else ''

            embed.add_field(
                name=f"{status_emoji} {alert.name}",
                value=(
                    f"[GE-Tracker]({ge_url})\n"
                    f"**Status:** {alert.status}\n"
                    f"**Margin:** {alert.margin:,} gp\n"
                    f"**Buy:** {alert.buy_price:,} gp\n"
                    f"**Sell:** {alert.sell_price:,} gp\n"
                    f"**Price Δ:** {alert.price_change_percent:+.1f}%\n"
                    f"**Volume:** {alert.high_volume}/{alert.low_volume}\n"
                    f"**Hourly Volume:** {alert.hourly_volume:,} {vol_spike_emoji}\n"
                    f"**Severity:** {alert.severity_score}/100\n"
                    f"{recommendation_emoji} **Rec:** {alert.recommendation.upper()}"
                ),
                inline=True
            )

        embed.set_footer(text=f"Total alerts: {len(alerts)}")
        return embed
