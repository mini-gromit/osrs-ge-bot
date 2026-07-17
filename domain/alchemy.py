from typing import Dict, List, Optional


def is_alchemizable(item_data: Dict, non_alchemizable_keywords: List[str]) -> bool:
    """
    Check if an item can be alchemized based on various criteria.

    Args:
        item_data: Dictionary containing item information from mapping
        non_alchemizable_keywords: List of keywords that indicate non-alchemizable items

    Returns:
        True if item can be alchemized, False otherwise
    """
    if item_data.get('highalch', 0) <= 0:
        return False

    if item_data.get('limit', 0) <= 0:
        return False

    item_name = item_data.get('name', '').lower()
    for keyword in non_alchemizable_keywords:
        if keyword in item_name:
            return False

    examine = item_data.get('examine', '').lower()
    if any(phrase in examine for phrase in ['untradeable', 'cannot be traded', 'quest item']):
        return False

    item_value = item_data.get('value', 0)
    alch_value = item_data.get('highalch', 0)

    if item_value > 0 and alch_value > (item_value * 10):
        return False

    return True


def calculate_alchemy_profit(item_id: int, item_mapping: Dict, current_prices: Dict,
                            five_min_data: Dict, nature_rune_cost: int,
                            non_alchemizable_keywords: List[str]) -> Optional[Dict]:
    """
    Calculate high alchemy profit for a specific item.

    Args:
        item_id: Item ID to calculate profit for
        item_mapping: Mapping of item IDs to item data
        current_prices: Current price data by item ID
        five_min_data: 5-minute price data for volume
        nature_rune_cost: Cost of nature rune
        non_alchemizable_keywords: List of keywords that indicate non-alchemizable items

    Returns:
        Dictionary with profit calculation or None if data unavailable or not alchemizable
    """
    if item_id not in item_mapping:
        return None

    if str(item_id) not in current_prices:
        return None

    item_info = item_mapping[item_id]

    if not is_alchemizable(item_info, non_alchemizable_keywords):
        return None

    price_info = current_prices[str(item_id)]

    if price_info['low'] is None:
        return None

    buy_price = price_info['low']
    high_alch_value = item_info['highalch']

    profit = high_alch_value - buy_price - nature_rune_cost

    total_cost = buy_price + nature_rune_cost
    roi_percent = (profit / total_cost) * 100 if total_cost > 0 else 0

    volume = 0
    five_min_avg_low = None
    five_min_lowest_buy = None
    is_at_five_min_low = False

    if item_id in five_min_data:
        volume = five_min_data[item_id].get('low_volume', 0)
        five_min_avg_low = five_min_data[item_id].get('avg_low')
        five_min_lowest_buy = five_min_data[item_id].get('lowest_low')

        # Business flag: current buy price is at or below the lowest observed 5m price
        if five_min_lowest_buy is not None:
            is_at_five_min_low = buy_price <= five_min_lowest_buy

    return {
        'item_id': item_id,
        'name': item_info['name'],
        'buy_price': buy_price,
        'high_alch_value': high_alch_value,
        'nature_rune_cost': nature_rune_cost,
        'profit': profit,
        'roi_percent': roi_percent,
        'limit': item_info['limit'],
        'members': item_info['members'],
        'max_profit_per_limit': profit * item_info['limit'] if profit > 0 else 0,
        'recent_volume': volume,
        'five_min_avg_low': five_min_avg_low,
        'five_min_lowest_buy': five_min_lowest_buy,
        'is_at_five_min_low': is_at_five_min_low,
        'alchemizable': True
    }


def get_profitable_items(item_mapping: Dict, current_prices: Dict, five_min_data: Dict,
                        nature_rune_cost: int, non_alchemizable_keywords: List[str],
                        min_profit: int = 0, max_items: int = 100,
                        members_only: bool = None, max_buy_price: int = None,
                        min_limit: int = None, min_volume: int = None,
                        max_roi: float = None) -> List[Dict]:
    """
    Get list of profitable high alchemy items.

    Args:
        item_mapping: Mapping of item IDs to item data
        current_prices: Current price data by item ID
        five_min_data: 5-minute price data for volume
        nature_rune_cost: Cost of nature rune
        non_alchemizable_keywords: List of keywords that indicate non-alchemizable items
        min_profit: Minimum profit per cast
        max_items: Maximum number of items to return
        members_only: Filter by members items (True/False/None for all)
        max_buy_price: Maximum buy price for items (None for no limit)
        min_limit: Minimum buying limit (None for no limit)
        min_volume: Minimum hourly trading volume (None for no limit)
        max_roi: Maximum ROI percentage (None for no limit)

    Returns:
        List of profitable items sorted by profit descending
    """
    profitable_items = []

    for item_id in item_mapping:
        if not is_alchemizable(item_mapping[item_id], non_alchemizable_keywords):
            continue

        profit_data = calculate_alchemy_profit(
            item_id, item_mapping, current_prices, five_min_data,
            nature_rune_cost, non_alchemizable_keywords
        )

        if profit_data is None:
            continue

        if profit_data['profit'] < min_profit:
            continue

        if members_only is not None:
            if profit_data['members'] != members_only:
                continue

        if max_buy_price is not None:
            if profit_data['buy_price'] > max_buy_price:
                continue

        if min_limit is not None:
            if profit_data['limit'] < min_limit:
                continue

        if min_volume is not None:
            if profit_data['recent_volume'] < min_volume:
                continue

        if max_roi is not None:
            if profit_data['roi_percent'] > max_roi:
                continue

        profitable_items.append(profit_data)

    profitable_items.sort(key=lambda x: x['profit'], reverse=True)

    return profitable_items[:max_items]


def get_non_alchemizable_sample(item_mapping: Dict, non_alchemizable_keywords: List[str],
                                sample_size: int = 10) -> List[Dict]:
    """
    Get a sample of items that are not alchemizable for debugging purposes.

    Args:
        item_mapping: Mapping of item IDs to item data
        non_alchemizable_keywords: List of keywords that indicate non-alchemizable items
        sample_size: Number of samples to return

    Returns:
        List of non-alchemizable item samples
    """
    non_alchemizable = []

    for item_id, item_info in list(item_mapping.items())[:1000]:
        if not is_alchemizable(item_info, non_alchemizable_keywords):
            non_alchemizable.append({
                'item_id': item_id,
                'name': item_info['name'],
                'highalch': item_info['highalch'],
                'limit': item_info['limit'],
                'value': item_info['value'],
                'examine': item_info['examine'][:50] + '...' if len(item_info['examine']) > 50 else item_info['examine']
            })

            if len(non_alchemizable) >= sample_size:
                break

    return non_alchemizable
