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
    def format_volume_compact(volume: int) -> str:
        """
        Format volume with k/m suffix for compact display.

        Args:
            volume: Volume count (hourly)

        Returns:
            Formatted string like "850", "2.4k", "18k"
        """
        if volume >= 10000:
            return f"{volume/1000:.0f}k"
        elif volume >= 1000:
            return f"{volume/1000:.1f}k"
        else:
            return str(volume)

    @staticmethod
    def format_5m_price_range(avg_low: Optional[int], lowest_buy: Optional[int]) -> str:
        """
        Format 5-minute price range with arrow notation.

        Shows average and lowest as range, or just what's available.
        Uses ─ for missing data instead of "N/A".

        Args:
            avg_low: 5-minute average low price
            lowest_buy: Lowest observed buy price in recent 5m windows

        Returns:
            Formatted string like "2,450→2,350", "2,450", or "─"
        """
        if avg_low is None and lowest_buy is None:
            return "─"

        if avg_low is None:
            return f"→{lowest_buy:,}" if lowest_buy else "─"

        if lowest_buy is None:
            return f"{avg_low:,}"

        # Both available - show range if different
        if avg_low == lowest_buy:
            return f"{avg_low:,}"

        return f"{avg_low:,}→{lowest_buy:,}"

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
    def create_alchemy_embed(
        items: List[Dict],
        title: str,
        color: discord.Color
    ) -> discord.Embed:
        """
        Compact trading-terminal style embed.

        One item = two lines.

        ⭐ = Current buy is at the best 5m buy opportunity.
        🏆 = Members
        💎 = F2P
        """

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now()
        )

        if not items:
            embed.description = "No items found."
            return embed

        lines = []

        for i, item in enumerate(items[:3], 1):

            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=item.get("item_id"),
                item_name=item.get("name"),
            )

            member = "🏆" if item.get("members") else "💎"

            star = " ⭐" if item.get("is_at_five_min_low") else ""

            price_range = DiscordRenderer.format_5m_price_range(
                item.get("five_min_avg_low"),
                item.get("five_min_lowest_buy"),
            )

            volume = DiscordRenderer.format_volume_compact(
                item.get("recent_volume", 0)
            )

            lines.append(
                f"**{i}. {member} [{item['name']}]({ge_url}){star}**"
                f"`{item['profit']:,} gp` • "
                f"Buy `{item['buy_price']:,}` • "
                f"5m `{price_range}` • "
                f"Vol `{volume}/hr`"
            )

        embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="⭐ Current buy matches lowest 5m buy opportunity"
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

        for item in items[:3]:
            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=item.get("item_id"),
                item_name=item.get("name"),
            )

            member = "🏆" if item.get("members") else "💎"

            embed.add_field(
                name="​",  # No field name for personal notifications
                value=(
                    f"{member} [{item['name']}]({ge_url})\n"
                    f"`+{item['profit']:,} gp` • "
                    f"Buy `{item['buy_price']:,}`"
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

            # Members tag
            member_tag = "[M]" if alert.members else "[F2P]"

            # Get GE-Tracker URL
            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=alert.item_id,
                item_name=alert.name
            )

            # Volume spike indicator
            vol_spike_emoji = '📈' if alert.volume_spike else ''

            # Build value sections
            value_parts = [
                f"[GE-Tracker]({ge_url})\n",
                f"📊 **What's Happening**",
                f"{alert.explanation}\n",
                f"💰 **Profit Opportunity**",
                f"{alert.impact_summary}\n",
                f"⚠️ **Market Conditions**",
                f"• Status: {alert.status.replace('_', ' ').title()}",
                f"• Volume: {alert.hourly_volume:,}/hr {vol_spike_emoji}",
                f"• Sell/Buy Ratio: {alert.volume_ratio:.1f}x",
                f"• Severity: {alert.severity_score}/100\n",
                f"👉 **Recommendation**",
                f"{rec_emoji} {alert.recommendation.upper()}"
            ]

            embed.add_field(
                name=f"{status_emoji} {alert.name} {member_tag}",
                value="\n".join(value_parts),
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

            # Members tag
            member_tag = "[M]" if alert.members else "[F2P]"

            # Get GE-Tracker URL
            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=alert.item_id,
                item_name=alert.name
            )

            # Volume spike indicator
            vol_spike_emoji = '📈' if alert.volume_spike else ''

            # Build value sections
            value_parts = [
                f"[GE-Tracker]({ge_url})\n",
                f"📊 **What's Happening**",
                f"{alert.explanation}\n",
                f"💰 **Flip Opportunity**",
                f"{alert.impact_summary}\n",
                f"⚠️ **Market Conditions**",
                f"• Status: {alert.status.replace('_', ' ').title()}",
                f"• Price Change: {alert.price_change_percent:+.1f}%",
                f"• Volume: {alert.hourly_volume:,}/hr {vol_spike_emoji}",
                f"• Buy/Sell: {alert.high_volume}/{alert.low_volume}",
                f"• Severity: {alert.severity_score}/100\n",
                f"👉 **Recommendation**",
                f"{recommendation_emoji} {alert.recommendation.upper()}"
            ]

            embed.add_field(
                name=f"{status_emoji} {alert.name} {member_tag}",
                value="\n".join(value_parts),
                inline=True
            )

        embed.set_footer(text=f"Total alerts: {len(alerts)}")
        return embed

    @staticmethod
    def create_profitable_alchemy_alert_embed(
        alerts: List['ProfitableAlchemyEvent'],
        title: str = "💰 Profitable Alchemy Alert"
    ) -> discord.Embed:
        """
        Create Discord embed for profitable alchemy alerts.

        Reuses layout from create_alchemy_embed but accepts MarketEvent objects.

        Args:
            alerts: List of ProfitableAlchemyEvent objects
            title: Embed title

        Returns:
            Discord Embed object
        """
        from events import ProfitableAlchemyEvent

        embed = discord.Embed(
            title=title,
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        if not alerts:
            embed.description = "No profitable items at this time."
            return embed

        # Limit to 10 items to fit embed limits
        alerts = alerts[:10]

        # Build compact item list
        lines = []

        for alert in alerts:
            ge_url = DiscordRenderer.get_item_ge_tracker_url(
                item_id=alert.item_id,
                item_name=alert.name,
            )

            star = " ⭐" if getattr(alert, "is_at_five_min_low", False) else ""

            price_range = DiscordRenderer.format_5m_price_range(
                getattr(alert, "five_min_avg_low", None),
                getattr(alert, "lowest_low", None),
            )

            lines.append(
                f"**[{alert.name}]({ge_url}){star}**\n"
                f"`+{alert.profit:,} gp` • "
                f"Buy `{alert.buy_price:,}` • "
                f"5m `{price_range}`"
            )

        embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="⭐ Current buy matches lowest 5m buy opportunity"
        )

        return embed
