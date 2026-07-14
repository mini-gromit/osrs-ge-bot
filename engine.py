import json
import time
import statistics
import logging
from typing import Dict, List, Optional
import pandas as pd
import math

from api.client import OSRSAPIClient
from domain import alchemy, flipping, risk
from alerts import alchemy as alchemy_alerts, flipping as flipping_alerts
import config

logger = logging.getLogger(__name__)

class OSRSAlchemyFlippingCalculator:
    def __init__(self):
        self.client = OSRSAPIClient()

        self.nature_rune_cost = config.NATURE_RUNE_COST

        self.item_mapping = {}
        self.current_prices = {}
        self.volume_data = {}
        self.five_min_data = {}
        self.flipping_average_prices = {}
        self.use_flipping_averages = config.USE_FLIPPING_AVERAGES
        self.flipping_history_periods = config.FLIPPING_HISTORY_PERIODS

        self.non_alchemizable_keywords = config.NON_ALCHEMIZABLE_KEYWORDS
        
    def is_alchemizable(self, item_data: Dict) -> bool:
        """
        Check if an item can be alchemized based on various criteria

        Args:
            item_data: Dictionary containing item information from mapping

        Returns:
            True if item can be alchemized, False otherwise
        """
        return alchemy.is_alchemizable(item_data, self.non_alchemizable_keywords)
        
    def fetch_item_mapping(self) -> bool:
        """
        Fetch item mapping data including high alchemy values
        Returns True if successful, False otherwise
        """
        logger.info("Fetching item mapping data...")
        mapping_data = self.client.fetch_item_mapping()

        if mapping_data is None:
            logger.error("Error fetching item mapping")
            return False

        for item in mapping_data:
            self.item_mapping[item['id']] = {
                'name': item.get('name', 'Unknown'),
                'examine': item.get('examine', ''),
                'members': item.get('members', False),
                'lowalch': item.get('lowalch', 0),
                'highalch': item.get('highalch', 0),
                'limit': item.get('limit', 0),
                'value': item.get('value', 0),
                'icon': item.get('icon', '')
            }

        logger.info(f"Successfully fetched mapping for {len(self.item_mapping)} items")
        return True
    
    def fetch_volume_data(self) -> bool:
        """
        Fetch volume data from 1-hour endpoint
        Returns True if successful, False otherwise
        """
        logger.info("Fetching volume data...")
        hourly_data = self.client.fetch_volume_data()

        if hourly_data is None:
            logger.error("Error fetching volume data")
            return False

        for item_id_str, data in hourly_data.items():
            if 'avgHighPrice' in data and 'avgLowPrice' in data and 'highPriceVolume' in data and 'lowPriceVolume' in data:
                item_id = int(item_id_str)
                total_volume = (data.get('highPriceVolume', 0) or 0) + (data.get('lowPriceVolume', 0) or 0)
                self.volume_data[item_id] = total_volume

        logger.info(f"Successfully fetched volume data for {len(self.volume_data)} items")
        return True
    
    def fetch_current_prices(self) -> bool:
        """
        Fetch current Grand Exchange prices
        Returns True if successful, False otherwise
        """
        logger.info("Fetching current GE prices...")
        price_data = self.client.fetch_current_prices()

        if price_data is None:
            logger.error("Error fetching current prices")
            return False

        self.current_prices = price_data
        logger.info(f"Successfully fetched prices for {len(self.current_prices)} items")
        return True

    def fetch_five_minute_data(self) -> bool:
        """
        NEW: Fetch 5-minute price data for trend analysis
        Returns True if successful, False otherwise
        """
        logger.info("Fetching 5-minute price data for trend analysis...")
        five_min_data = self.client.fetch_five_minute_data()

        if five_min_data is None:
            logger.error("Error fetching 5-minute data")
            return False

        # Convert to dict and extract price information
        for item_id_str, data in five_min_data.items():
            if 'avgHighPrice' in data and 'avgLowPrice' in data:
                item_id = int(item_id_str)
                self.five_min_data[item_id] = {
                    'high': data.get('avgHighPrice'),
                    'low': data.get('avgLowPrice'),
                    'high_volume': data.get('highPriceVolume', 0) or 0,
                    'low_volume': data.get('lowPriceVolume', 0) or 0,
                    'timestamp': data.get('timestamp')
                }

        logger.info(f"Successfully fetched 5-minute data for {len(self.five_min_data)} items")
        return True

    def fetch_timeseries(self, item_id: int, timestep: str = "24h") -> List[Dict]:
        """
        Fetch historical price data for an item

        Args:
            item_id: Item ID to fetch data for
            timestep: Time resolution (24h, 6h, 1h, 5m)

        Returns:
            List of price data points
        """
        data = self.client.fetch_timeseries(item_id, timestep)
        if not data:
            logger.warning(f"Error fetching timeseries for item {item_id}")
        return data
    
    def detect_pump_and_dump(self, history_prices: List[Dict], current_high: int, current_low: int) -> tuple:
        """
        Enhanced pump and dump detection with multiple criteria

        Args:
            history_prices: List of historical price data
            current_high: Current high price
            current_low: Current low price

        Returns:
            Tuple of (is_suspicious, risk_level, reason)
        """
        return risk.detect_pump_and_dump(history_prices, current_high, current_low)
    
    def calculate_alchemy_profit(self, item_id: int) -> Optional[Dict]:
        """
        Calculate high alchemy profit for a specific item

        Returns:
            Dict with profit calculation or None if data unavailable or not alchemizable
        """
        return alchemy.calculate_alchemy_profit(
            item_id, self.item_mapping, self.current_prices,
            self.five_min_data, self.nature_rune_cost, self.non_alchemizable_keywords
        )

    def calculate_flip_score(self, current_high_price: int, current_low_price: int,
                            volume: int, margin: int, limit: int, history_prices: List[Dict], base_score=0) -> tuple:
        """
        Balanced granular flip score calculation.

        Returns:
            Tuple of (score, summary, risk_info)
        """
        return flipping.calculate_flip_score(
            current_high_price, current_low_price, volume, margin, limit,
            history_prices, self.detect_pump_and_dump, base_score
        )

    def get_profitable_items(self, min_profit: int = 0, max_items: int = 100,
                           members_only: bool = None, max_buy_price: int = None,
                           min_limit: int = None, min_volume: int = None,
                           max_roi: float = None) -> List[Dict]:
        """
        Get list of profitable high alchemy items

        Args:
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
        total_items_checked = len(self.item_mapping)
        alchemizable_items = sum(
            1 for item_id in self.item_mapping
            if self.is_alchemizable(self.item_mapping[item_id])
        )

        profitable_items = alchemy.get_profitable_items(
            self.item_mapping, self.current_prices, self.five_min_data,
            self.nature_rune_cost, self.non_alchemizable_keywords,
            min_profit, max_items, members_only, max_buy_price,
            min_limit, min_volume, max_roi
        )

        logger.info(f"Filtering results: {total_items_checked} total items, {alchemizable_items} alchemizable, {len(profitable_items)} profitable")

        return profitable_items
    
    def get_top_flips(self, limit: int = 10, min_margin: int = 200, min_volume: int = 20, 
                    max_buy_price: int = None, fetch_history: bool = True, 
                    max_margin_percent: float = 20.0, exclude_high_risk: bool = True,
                    min_score: int = 30) -> List[Dict]:
        """
        Enhanced get_top_flips with pump/dump filtering and better scoring
        FIXED: Now properly calculates scores and accounts for GE tax
        """
        if not self.current_prices or not self.volume_data:
            logger.error("Missing price or volume data. Make sure to fetch current prices and volume data first.")
            return []
            
        flips = []
        
        # First pass: collect all potential flips with proper GE tax calculation
        for item_id_str, current_price_data in self.current_prices.items():
            try:
                item_id = int(item_id_str)
                item = self.item_mapping.get(item_id)
                if not item:
                    continue
                
                # Use averaged prices for flipping if available
                price_info = self.get_flipping_prices(item_id)
                if not price_info:
                    continue
                    
                high = price_info.get("high")
                low = price_info.get("low")
                
                if not high or not low or high <= low:
                    continue
                
                # Get volume from hourly data
                vol = self.volume_data.get(item_id, 0)
                
                # FIXED: Calculate margin AFTER GE tax (1% on buy, 1% on sell = ~2% total)
                buy_price_with_tax = int(low * 1.01)  # 1% tax when buying
                sell_price_after_tax = int(high * 0.99)  # 1% tax when selling
                actual_margin = sell_price_after_tax - buy_price_with_tax
                
                # Calculate margin percentage based on actual costs
                margin_percent = (actual_margin / buy_price_with_tax * 100) if buy_price_with_tax > 0 else 0
                
                # UPDATED: Apply filters using the actual margin after tax
                if actual_margin < min_margin or vol < min_volume:
                    continue
                    
                # Filter for maximum buy price (use the taxed buy price)
                if max_buy_price is not None and buy_price_with_tax > max_buy_price:
                    continue
                
                # Filter out items with margin percentage greater than max_margin_percent
                if margin_percent > max_margin_percent:
                    continue
                
                # FIXED: Calculate a basic score even without history
                # This prevents all items from having score=50
                basic_score = 0
                
                # Basic margin score (0-20)
                if actual_margin >= 100000:
                    basic_score += 20
                elif actual_margin >= 50000:
                    basic_score += 15
                elif actual_margin >= 10000:
                    basic_score += 12
                elif actual_margin >= 5000:
                    basic_score += 8
                elif actual_margin >= 2000:
                    basic_score += 5
                else:
                    basic_score += 2
                
                # Basic volume score (0-15)
                if vol >= 1000:
                    basic_score += 15
                elif vol >= 500:
                    basic_score += 12
                elif vol >= 200:
                    basic_score += 8
                elif vol >= 100:
                    basic_score += 5
                else:
                    basic_score += 2
                
                # Basic ROI score (0-10) - capped to avoid pump/dump rewards
                roi_capped = min(margin_percent, 15)  # Cap at 15%
                if roi_capped >= 10:
                    basic_score += 10
                elif roi_capped >= 5:
                    basic_score += 7
                elif roi_capped >= 3:
                    basic_score += 4
                else:
                    basic_score += 1
                
                flips.append({
                    "name": item["name"],
                    "id": item_id,
                    "buy_price": low,  # Display original price
                    "sell_price": high,  # Display original price
                    "buy_price_with_tax": buy_price_with_tax,  # Store taxed price
                    "sell_price_after_tax": sell_price_after_tax,  # Store after-tax price
                    "margin": actual_margin,  # FIXED: Use actual margin after tax
                    "margin_percent": round(margin_percent, 2),
                    "volume": vol,
                    "score": basic_score,  # FIXED: Use calculated basic score instead of 50
                    "history": "Basic scoring",
                    "members": item.get("members", False),
                    "limit": item.get("limit", 0),
                    "risk_level": 0,
                    "risk_info": "Not analyzed"
                })
                
            except Exception as e:
                continue
        
        # Sort by score first, then margin
        flips.sort(key=lambda x: (x['score'], x['margin']), reverse=True)
        
        # FIXED: Limit the number of items we analyze with history
        analysis_limit = min(limit * 2, 15)  # Never more than 15 items for history analysis
        top_candidates = flips[:analysis_limit]

        logger.info(f"Pre-filtered to {len(flips)} candidates, analyzing top {len(top_candidates)} with history")

        # Second pass: fetch history and calculate enhanced scores
        if fetch_history and top_candidates:
            logger.info(f"Analyzing price history for top {len(top_candidates)} candidates...")
            analyzed_flips = []
            
            for i, flip in enumerate(top_candidates):
                try:
                    logger.info(f"Fetching history for {flip['name']} ({i+1}/{len(top_candidates)})")
                    ts_data = self.fetch_timeseries(flip['id'], "24h")
                    
                    # FIXED: Use the original prices for score calculation (the method handles GE tax internally)
                    score, history_summary, risk_info = self.calculate_flip_score(
                        flip['sell_price'],  # Original high price
                        flip['buy_price'],   # Original low price
                        flip['volume'], 
                        flip['margin'],      # Already tax-adjusted margin
                        flip['limit'],
                        ts_data,
                        flip['score']  # Pass the basic score to build upon
                    )
                    
                    # FIXED: Update the score properly
                    flip['score'] = score
                    flip['history'] = history_summary
                    flip['risk_level'] = risk_info[1]
                    flip['risk_info'] = risk_info[2]
                    
                    # Apply filters
                    if exclude_high_risk and risk_info[0] and risk_info[1] >= 3:
                        continue  # Skip high-risk items
                    
                    if score >= min_score:
                        analyzed_flips.append(flip)
                    
                    time.sleep(0.1)  # Be kind to the API
                except Exception as e:
                    logger.warning(f"Error analyzing {flip['name']}: {e}")
                    # FIXED: Still include items that couldn't be analyzed but passed basic filters
                    if flip['score'] >= min_score:
                        analyzed_flips.append(flip)
                    continue
            
            # Sort by score after analysis
            analyzed_flips.sort(key=lambda x: (x['score'], x['margin']), reverse=True)
            logger.info(f"History analysis complete: {len(analyzed_flips)} items passed all filters")
            return analyzed_flips[:limit]
        else:
            for flip in flips:
                flip['score'] = (flip['score'] / 45) * 100
            # Return without detailed analysis, but still properly scored
            logger.info(f"Returning {len(top_candidates[:limit])} items with basic scoring")
            return top_candidates[:limit]

    def get_non_alchemizable_sample(self, sample_size: int = 10) -> List[Dict]:
        """
        Get a sample of items that are not alchemizable for debugging purposes

        Args:
            sample_size: Number of samples to return

        Returns:
            List of non-alchemizable item samples
        """
        return alchemy.get_non_alchemizable_sample(
            self.item_mapping, self.non_alchemizable_keywords, sample_size
        )


    def fetch_flipping_average_prices(self, item_ids: List[int] = None, timestep: str = "24h") -> bool:
        """
        FIXED: Fetch average prices specifically for flipping analysis using timeseries data
        Now properly limits the number of items to prevent excessive API calls
        """
        if not self.current_prices:
            logger.error("No current prices available. Fetch current prices first.")
            return False
            
        # FIXED: If no specific items provided, intelligently select the best candidates
        if item_ids is None:
            candidate_items = []
            
            # Pre-filter items to only the most promising candidates
            for item_id_str, price_data in self.current_prices.items():
                item_id = int(item_id_str)
                
                # Only consider items with decent prices and volume
                high = price_data.get('high')
                low = price_data.get('low')
                volume = self.volume_data.get(item_id, 0)
                
                if (high and low and high > low and 
                    volume >= 10 and  # Minimum volume threshold
                    low >= 1000 and  # Don't bother with very cheap items
                    high <= 50000000):  # Skip extremely expensive items
                    
                    margin = high - low
                    margin_percent = (margin / low) * 100
                    
                    # Only include items with reasonable margins
                    if 1000 <= margin <= 5000000 and margin_percent < 25:  # Reasonable bounds
                        candidate_items.append({
                            'id': item_id,
                            'margin': margin,
                            'volume': volume,
                            'margin_percent': margin_percent
                        })
            
            # Sort by a combination of margin and volume, take top candidates
            candidate_items.sort(key=lambda x: x['margin'] * (x['volume'] ** 0.5), reverse=True)

            # FIXED: Limit to top 30 candidates maximum to prevent excessive API calls
            max_items = min(30, len(candidate_items))
            item_ids = [item['id'] for item in candidate_items[:max_items]]

            logger.info(f"Auto-selected {len(item_ids)} promising items from {len(candidate_items)} candidates")

        # Additional safety check
        if len(item_ids) > 100:
            logger.warning(f"Too many items ({len(item_ids)}), limiting to top 100")
            item_ids = item_ids[:100]

        logger.info(f"Fetching flipping average prices for {len(item_ids)} items using {timestep} timestep...")
        
        successful_fetches = 0
        failed_fetches = 0
        
        for i, item_id in enumerate(item_ids):
            try:
                # Progress indicator every 10 items instead of 25
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(item_ids)} items...")

                # Fetch timeseries data
                ts_data = self.fetch_timeseries(item_id, timestep)
                
                if not ts_data or len(ts_data) < 5:  # Need at least 5 data points
                    failed_fetches += 1
                    continue
                
                # Use recent data for averaging (last N periods)
                recent_data = ts_data[-min(len(ts_data), self.flipping_history_periods):]
                
                highs = [entry.get('avgHighPrice') for entry in recent_data if entry.get('avgHighPrice')]
                lows = [entry.get('avgLowPrice') for entry in recent_data if entry.get('avgLowPrice')]
                volumes = [entry.get('highPriceVolume', 0) + entry.get('lowPriceVolume', 0) 
                        for entry in recent_data 
                        if entry.get('highPriceVolume') is not None and entry.get('lowPriceVolume') is not None]
                
                if len(highs) >= 3 and len(lows) >= 3:  # Need at least 3 valid data points
                    # For flipping, we want more conservative averages to avoid pump/dump traps
                    # Use median-weighted average (60% median + 40% mean) for stability
                    mean_high = statistics.mean(highs)
                    mean_low = statistics.mean(lows)
                    median_high = statistics.median(highs)
                    median_low = statistics.median(lows)
                    
                    # Conservative weighted average favoring median for stability
                    avg_high = int(median_high * 0.6 + mean_high * 0.4)
                    avg_low = int(median_low * 0.6 + mean_low * 0.4)
                    
                    # Calculate stability metrics
                    high_std = statistics.stdev(highs) if len(highs) > 1 else 0
                    low_std = statistics.stdev(lows) if len(lows) > 1 else 0
                    high_cv = (high_std / mean_high * 100) if mean_high > 0 else 100
                    low_cv = (low_std / mean_low * 100) if mean_low > 0 else 100
                    
                    self.flipping_average_prices[item_id] = {
                        'high': avg_high,
                        'low': avg_low,
                        'data_points': len(recent_data),
                        'high_std': high_std,
                        'low_std': low_std,
                        'high_cv': high_cv,  # Coefficient of variation
                        'low_cv': low_cv,
                        'realtime_high': self.current_prices[str(item_id)].get('high'),
                        'realtime_low': self.current_prices[str(item_id)].get('low'),
                        'avg_volume': statistics.mean(volumes) if volumes else 0
                    }
                    successful_fetches += 1
                else:
                    failed_fetches += 1
                
                # Be respectful to the API - slightly longer delay
                time.sleep(0.1)  # 100ms delay between requests

            except Exception as e:
                logger.warning(f"Error fetching data for item {item_id}: {e}")
                failed_fetches += 1
                continue

        logger.info(f"Flipping average price fetching complete: {successful_fetches} successful, {failed_fetches} failed")
        return successful_fetches > 0

    def get_flipping_prices(self, item_id: int) -> Dict:
        """
        Get prices for flipping - either averaged or realtime based on settings
        
        Args:
            item_id: Item ID to get prices for
            
        Returns:
            Dictionary with 'high', 'low', and price source info
        """
        if self.use_flipping_averages and item_id in self.flipping_average_prices:
            avg_data = self.flipping_average_prices[item_id]
            return {
                'high': avg_data['high'],
                'low': avg_data['low'],
                'source': 'averaged',
                'stability': {
                    'high_cv': avg_data['high_cv'],
                    'low_cv': avg_data['low_cv'],
                    'data_points': avg_data['data_points']
                }
            }
        elif str(item_id) in self.current_prices:
            price_data = self.current_prices[str(item_id)]
            return {
                'high': price_data.get('high'),
                'low': price_data.get('low'),
                'source': 'realtime',
                'stability': None
            }
        else:
            return None

    def analyze_alchemy_crash_risk(self, item_id: int) -> Dict:
        """
        Simplified alchemy crash detection - when low price volume >> high price volume

        Args:
            item_id: Item ID to analyze

        Returns:
            Dictionary with simple crash analysis for alchemy items
        """
        return risk.analyze_alchemy_crash_risk(item_id, self.five_min_data, self.volume_data)

    def analyze_flipping_trend(self, item_id: int) -> Dict:
        """
        Simplified flipping trend analysis for Discord alerts

        Args:
            item_id: Item ID to analyze

        Returns:
            Dictionary with simple trend analysis
        """
        return risk.analyze_flipping_trend(
            item_id, self.current_prices, self.five_min_data, self.volume_data
        )

    def get_alchemy_alerts(self, min_profit: int = 100, min_volume_imbalance: float = 2.0,
                        min_limit: int = None, min_volume: int = None):
        """
        Get alchemy items with crash risk alerts.

        Args:
            min_profit: Minimum profit to consider alerting about
            min_volume_imbalance: Minimum ratio of low_volume/high_volume to alert
            min_limit: Minimum trade limit filter
            min_volume: Minimum volume filter

        Returns:
            List of CrashRiskEvent objects
        """
        return alchemy_alerts.get_alchemy_crash_alerts(
            self, min_profit, min_volume_imbalance, min_limit, min_volume
        )

    def get_flipping_alerts(self, min_margin: int = 1000, min_volume: int = 20):
        """
        Get flipping items with trend alerts.

        Args:
            min_margin: Minimum margin to consider
            min_volume: Minimum volume to consider

        Returns:
            List of FlippingTrendEvent objects
        """
        return flipping_alerts.get_flipping_trend_alerts(self, min_margin, min_volume)

if __name__ == "__main__":
    import logging
    from cli import main as cli

    # Configure logging
    logging.basicConfig(
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
        level=getattr(logging, config.LOG_LEVEL)
    )

    calculator = OSRSAlchemyFlippingCalculator()

    print("=" * 70)
    print("ENHANCED FLIPPING ANALYSIS WITH TREND ALERTS")
    print("=" * 70)

    cli.run_flipping_analysis(
        calculator,
        limit=15,
        min_margin=1000,
        min_volume=50,
        members_only=None,
        max_buy_price=20000000,
        max_margin_percent=15.0,
        exclude_high_risk=True,
        min_score=40,
        save_csv_file=True,
        fetch_history=True,
        use_averaged_prices=True,
        show_alerts=True,
        alert_min_margin=1000,
        alert_min_volume=20
    )

    time.sleep(2)

    print("\n" + "=" * 70)
    print("ENHANCED ALCHEMY ANALYSIS WITH CRASH DETECTION")
    print("=" * 70)

    cli.run_alchemy_analysis(
        calculator,
        min_profit=200,
        max_items=100,
        members_only=None,
        save_csv_file=True,
        max_buy_price=10000000,
        min_limit=None,
        min_volume=20,
        max_roi=None,
        show_non_alchemizable_sample=False,
        show_crash_alerts=True,
        alert_min_profit=100,
        alert_min_imbalance=2.0
    )