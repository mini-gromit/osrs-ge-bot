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

            # Format 5-minute buy price data safely
            five_min_avg_low = item.get('five_min_avg_low')
            five_min_lowest_buy = item.get('five_min_lowest_buy')
            is_at_five_min_low = item.get('is_at_five_min_low', False)

            avg_low_str = f"{five_min_avg_low:,} gp" if five_min_avg_low is not None else "N/A"
            lowest_buy_str = f"{five_min_lowest_buy:,} gp" if five_min_lowest_buy is not None else "N/A"

            # Add indicator emoji if current price is at lowest observed level
            name_indicator = " ⭐" if is_at_five_min_low else ""

            embed.add_field(
                name=f"{i}. {member_tag} {item['name']}{name_indicator}",
                value=(
                    f"[URL]({ge_url})\n"
                    f"Profit: {item['profit']:,} gp\n"
                    f"Current Buy: {item['buy_price']:,} gp\n"
                    f"5m Avg Low: {avg_low_str}\n"
                    f"5m Lowest: {lowest_buy_str}"
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
