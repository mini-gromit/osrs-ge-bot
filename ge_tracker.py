import json
import time
import statistics
from typing import Dict, List, Optional
import pandas as pd
import math

from api.client import OSRSAPIClient

class OSRSAlchemyFlippingCalculator:
    def __init__(self):
        # API client for HTTP requests
        self.client = OSRSAPIClient()

        # Cost of nature rune (you can update this manually or fetch it dynamically)
        self.nature_rune_cost = 125  # Current cost from my head
        
        # Data storage - using existing endpoints for flipping
        self.item_mapping = {}
        self.current_prices = {}
        self.volume_data = {}
        self.five_min_data = {}
        self.flipping_average_prices = {}  # Store averaged prices for flipping only
        self.use_flipping_averages = True  # Flag to use averages for flipping
        self.flipping_history_periods = 300  # How many periods back to average (120 * 6h = 30 days)

        # Items that are known to not be alchemizable (can be expanded)
        self.non_alchemizable_keywords = [
            'noted', '(noted)', 'bank note', 'certificate',
            'clue', 'casket', 'scroll', 'pet', 'spirit',
            'teleport', 'tab', 'tablet', 'crystal seed',
            'broken', 'damaged', 'degraded', 'uncharged',
            'contract', 'bloodied', 'severance', 'sensory'
        ]
        
    def is_alchemizable(self, item_data: Dict) -> bool:
        """
        Check if an item can be alchemized based on various criteria
        
        Args:
            item_data: Dictionary containing item information from mapping
            
        Returns:
            True if item can be alchemized, False otherwise
        """
        # Must have a high alchemy value greater than 0
        if item_data.get('highalch', 0) <= 0:
            return False
            
        # Must have a trade limit (items with limit 0 are often untradeable)
        if item_data.get('limit', 0) <= 0:
            return False
            
        # Check item name for non-alchemizable keywords
        item_name = item_data.get('name', '').lower()
        for keyword in self.non_alchemizable_keywords:
            if keyword in item_name:
                return False
        
        # Additional checks based on examine text (if available)
        examine = item_data.get('examine', '').lower()
        if any(phrase in examine for phrase in ['untradeable', 'cannot be traded', 'quest item']):
            return False
            
        # Items with extremely high alch values relative to their value might be suspicious
        # (could indicate items that aren't actually alchemizable but have incorrect data)
        item_value = item_data.get('value', 0)
        alch_value = item_data.get('highalch', 0)
        
        # If alch value is more than 10x the base value, it might be suspicious
        # This helps filter out some incorrect data
        if item_value > 0 and alch_value > (item_value * 10):
            return False
            
        return True
        
    def fetch_item_mapping(self) -> bool:
        """
        Fetch item mapping data including high alchemy values
        Returns True if successful, False otherwise
        """
        print("Fetching item mapping data...")
        mapping_data = self.client.fetch_item_mapping()

        if mapping_data is None:
            print("Error fetching item mapping")
            return False

        # Convert list to dict for easier lookup by item ID
        for item in mapping_data:
            self.item_mapping[item['id']] = {
                'name': item.get('name', 'Unknown'),
                'examine': item.get('examine', ''),
                'members': item.get('members', False),
                'lowalch': item.get('lowalch', 0),
                'highalch': item.get('highalch', 0),
                'limit': item.get('limit', 0),  # Default to 0 if no limit (untradeable items)
                'value': item.get('value', 0),
                'icon': item.get('icon', '')
            }

        print(f"Successfully fetched mapping for {len(self.item_mapping)} items")
        return True
    
    def fetch_volume_data(self) -> bool:
        """
        Fetch volume data from 1-hour endpoint
        Returns True if successful, False otherwise
        """
        print("Fetching volume data...")
        hourly_data = self.client.fetch_volume_data()

        if hourly_data is None:
            print("Error fetching volume data")
            return False

        # Convert to dict and extract volume information
        for item_id_str, data in hourly_data.items():
            if 'avgHighPrice' in data and 'avgLowPrice' in data and 'highPriceVolume' in data and 'lowPriceVolume' in data:
                item_id = int(item_id_str)
                # Use total volume (high + low price volumes)
                total_volume = (data.get('highPriceVolume', 0) or 0) + (data.get('lowPriceVolume', 0) or 0)
                self.volume_data[item_id] = total_volume

        print(f"Successfully fetched volume data for {len(self.volume_data)} items")
        return True
    
    def fetch_current_prices(self) -> bool:
        """
        Fetch current Grand Exchange prices
        Returns True if successful, False otherwise
        """
        print("Fetching current GE prices...")
        price_data = self.client.fetch_current_prices()

        if price_data is None:
            print("Error fetching current prices")
            return False

        self.current_prices = price_data
        print(f"Successfully fetched prices for {len(self.current_prices)} items")
        return True

    def fetch_five_minute_data(self) -> bool:
        """
        NEW: Fetch 5-minute price data for trend analysis
        Returns True if successful, False otherwise
        """
        print("Fetching 5-minute price data for trend analysis...")
        five_min_data = self.client.fetch_five_minute_data()

        if five_min_data is None:
            print("Error fetching 5-minute data")
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

        print(f"Successfully fetched 5-minute data for {len(self.five_min_data)} items")
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
            print(f"Error fetching timeseries for item {item_id}")
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
        if not history_prices or len(history_prices) < 10:
            return False, 0, "Insufficient data"
        
        try:
            # Get recent data points (last 20 entries)
            recent_data = history_prices[-20:]
            
            # Extract high and low prices
            highs = [entry.get('avgHighPrice', 0) for entry in recent_data if entry.get('avgHighPrice')]
            lows = [entry.get('avgLowPrice', 0) for entry in recent_data if entry.get('avgLowPrice')]
            volumes = [entry.get('highPriceVolume', 0) + entry.get('lowPriceVolume', 0) 
                      for entry in recent_data 
                      if entry.get('highPriceVolume') is not None and entry.get('lowPriceVolume') is not None]
            
            if len(highs) < 10 or len(lows) < 10:
                return False, 0, "Insufficient price data"
            
            # Calculate statistics
            avg_high = statistics.mean(highs)
            avg_low = statistics.mean(lows)
            median_high = statistics.median(highs)
            median_low = statistics.median(lows)
            
            # Standard deviations
            high_std = statistics.stdev(highs) if len(highs) > 1 else 0
            low_std = statistics.stdev(lows) if len(lows) > 1 else 0
            
            risk_factors = []
            risk_score = 0
            
            # 1. Extreme price spikes (current price vs historical average)
            high_spike_ratio = current_high / avg_high if avg_high > 0 else 1
            low_spike_ratio = current_low / avg_low if avg_low > 0 else 1
            
            if high_spike_ratio > 1.5:  # Current high is 2x+ historical average
                risk_score += 30
                risk_factors.append(f"High spike: {high_spike_ratio:.1f}x avg")
            elif high_spike_ratio > 1.3:
                risk_score += 15
                risk_factors.append(f"Moderate high spike: {high_spike_ratio:.1f}x avg")
            
            if low_spike_ratio > 1.2:  # Current low is 1.8x+ historical average
                risk_score += 25
                risk_factors.append(f"Low spike: {low_spike_ratio:.1f}x avg")
            
            # 2. Excessive volatility
            if avg_high > 0:
                high_volatility = (high_std / avg_high) * 100
                if high_volatility > 20:  # More than 30% volatility
                    risk_score += 20
                    risk_factors.append(f"High volatility: {high_volatility:.1f}%")
                elif high_volatility > 15:
                    risk_score += 10
                    risk_factors.append(f"Moderate volatility: {high_volatility:.1f}%")
            
            # 3. Large deviation from median (indicates outliers)
            high_median_deviation = abs(current_high - median_high) / median_high if median_high > 0 else 0
            if high_median_deviation > 0.5:  # Current price deviates >50% from median
                risk_score += 15
                risk_factors.append(f"Median deviation: {high_median_deviation:.1%}")
            
            # 4. Sudden volume changes (if volume data available)
            if volumes and len(volumes) >= 5:
                recent_volume = statistics.mean(volumes[-3:])  # Last 3 periods
                older_volume = statistics.mean(volumes[:-3])   # Older periods
                
                if older_volume > 0:
                    volume_change = recent_volume / older_volume
                    if volume_change > 3.0:  # 3x+ volume increase
                        risk_score += 20
                        risk_factors.append(f"Volume spike: {volume_change:.1f}x")
                    elif volume_change < 0.3:  # Volume dropped to <30%
                        risk_score += 15
                        risk_factors.append(f"Volume drop: {volume_change:.1%}")
            
            # 5. Recent rapid price changes
            if len(highs) >= 5:
                recent_highs = highs[-3:]
                if len(set(recent_highs)) > 1:  # Prices are changing
                    max_recent = max(recent_highs)
                    min_recent = min(recent_highs)
                    if min_recent > 0:
                        recent_volatility = (max_recent - min_recent) / min_recent
                        if recent_volatility > 0.3:  # 30%+ swing in recent periods
                            risk_score += 15
                            risk_factors.append(f"Recent swing: {recent_volatility:.1%}")
            
            # 6. Unrealistic margins
            current_margin_percent = ((current_high - current_low) / current_low * 100) if current_low > 0 else 0
            if current_margin_percent > 25:  # >25% margin is suspicious for most items
                risk_score += 25
                risk_factors.append(f"High margin: {current_margin_percent:.1f}%")
            elif current_margin_percent > 15:
                risk_score += 10
                risk_factors.append(f"Elevated margin: {current_margin_percent:.1f}%")
            
            # Determine risk level and suspicion
            if risk_score >= 30:
                return True, 3, "HIGH: " + "; ".join(risk_factors[:3])
            elif risk_score >= 20:
                return True, 2, "MEDIUM: " + "; ".join(risk_factors[:2])
            elif risk_score >= 10:
                return True, 1, "LOW: " + "; ".join(risk_factors[:2])
            else:
                return False, 0, "Clean"
                
        except Exception as e:
            return False, 0, f"Analysis error: {str(e)}"
    
    def calculate_alchemy_profit(self, item_id: int) -> Optional[Dict]:
        """
        Calculate high alchemy profit for a specific item
        MODIFIED: Now uses 5-minute low_volume instead of hourly volume
        Returns dict with profit calculation or None if data unavailable or not alchemizable
        """
        if item_id not in self.item_mapping:
            return None
            
        if str(item_id) not in self.current_prices:
            return None
            
        item_info = self.item_mapping[item_id]
        
        # Check if item is alchemizable
        if not self.is_alchemizable(item_info):
            return None
            
        price_info = self.current_prices[str(item_id)]
        
        # Use the low price (instant-sell price) for buying
        if price_info['low'] is None:
            return None
            
        buy_price = price_info['low']
        high_alch_value = item_info['highalch']
        
        # Calculate profit: High alch value - buy price - nature rune cost
        profit = high_alch_value - buy_price - self.nature_rune_cost
        
        # Calculate ROI percentage
        total_cost = buy_price + self.nature_rune_cost
        roi_percent = (profit / total_cost) * 100 if total_cost > 0 else 0
        
        # Get 5-minute volume data (low volume) instead of hourly volume
        volume = 0
        if item_id in self.five_min_data:
            volume = self.five_min_data[item_id].get('low_volume', 0)
        
        return {
            'item_id': item_id,
            'name': item_info['name'],
            'buy_price': buy_price,
            'high_alch_value': high_alch_value,
            'nature_rune_cost': self.nature_rune_cost,
            'profit': profit,
            'roi_percent': roi_percent,
            'limit': item_info['limit'],
            'members': item_info['members'],
            'max_profit_per_limit': profit * item_info['limit'] if profit > 0 else 0,
            'recent_volume': volume,  # uses 5-minute data
            'alchemizable': True  # Only returned if alchemizable
        }

    def calculate_flip_score(self, current_high_price: int, current_low_price: int, 
                            volume: int, margin: int, limit: int, history_prices: List[Dict], base_score=0) -> tuple:
        """
        Balanced granular flip score calculation - maintains score ranges while adding precision
        FIXED: Better balanced scoring that doesn't penalize good items too heavily
        """
        score = base_score  # Start with basic score instead of 0
        factors = [f"Base: {base_score}"]
        
        # FIXED: Recalculate actual margin with GE tax for scoring consistency
        buy_price_with_tax = int(current_low_price * 1.01)
        sell_price_after_tax = int(current_high_price * 0.99)
        actual_margin = sell_price_after_tax - buy_price_with_tax
        actual_margin_percent = (actual_margin / buy_price_with_tax * 100) if buy_price_with_tax > 0 else 0
        
        # Use the actual margin for scoring instead of the passed margin
        scoring_margin = actual_margin
        scoring_margin_percent = actual_margin_percent
        
        # First, check for pump and dump using original prices
        is_suspicious, risk_level, risk_reason = self.detect_pump_and_dump(
            history_prices, current_high_price, current_low_price
        )
        
        # Heavily penalize suspicious items
        if is_suspicious:
            if risk_level >= 3:  # HIGH risk
                score -= 50
                factors.append(f"🚨 HIGH RISK: {risk_reason}")
            elif risk_level >= 2:  # MEDIUM risk
                score -= 25
                factors.append(f"⚠️ MEDIUM RISK: {risk_reason}")
            else:  # LOW risk
                score -= 10
                factors.append(f"⚡ LOW RISK: {risk_reason}")
        
        # 1. BALANCED Margin Score (0-20 points) - More generous scoring
        if scoring_margin >= 50000:  # 50K+
            margin_score = min(20, 18 + (scoring_margin - 50000) / 50000)  # 18-20 range
        elif scoring_margin >= 25000:   # 25K-50K
            margin_score = 16 + (scoring_margin - 25000) / 12500           # 16-18 range
        elif scoring_margin >= 15000:   # 15K-25K
            margin_score = 14 + (scoring_margin - 15000) / 5000            # 14-16 range
        elif scoring_margin >= 10000:   # 10K-15K
            margin_score = 12 + (scoring_margin - 10000) / 2500            # 12-14 range
        elif scoring_margin >= 5000:    # 5K-10K
            margin_score = 9 + (scoring_margin - 5000) / 1667              # 9-12 range
        elif scoring_margin >= 2500:    # 2.5K-5K
            margin_score = 6 + (scoring_margin - 2500) / 833               # 6-9 range
        elif scoring_margin >= 1000:    # 1K-2.5K
            margin_score = 3 + (scoring_margin - 1000) / 500               # 3-6 range
        elif scoring_margin >= 500:     # 500-1K
            margin_score = 1 + (scoring_margin - 500) / 250                # 1-3 range
        else:
            margin_score = max(0, scoring_margin / 500)                    # 0-1 range
        
        margin_score = round(margin_score, 1)
        score += margin_score
        factors.append(f"Margin: {margin_score}/20")
        
        # 2. BALANCED Volume Score (0-20 points) - More generous for your data
        if volume >= 500:
            volume_score = min(20, 18 + (volume - 500) / 250)             # 18-20 range
        elif volume >= 400:
            volume_score = 16 + (volume - 300) / 150                      # 16-18 range
        elif volume >= 300:
            volume_score = 14 + (volume - 60) / 30                       # 14-16 range
        elif volume >= 200:
            volume_score = 12 + (volume - 150) / 75                       # 12-14 range
        elif volume >= 100:
            volume_score = 9 + (volume - 100) / 50                        # 9-12 range
        elif volume >= 50:
            volume_score = 7 + (volume - 50) / 25                       # 7-9 range
        elif volume >= 30:
            volume_score = 5 + (volume - 30) / 15                       # 5-7 range
        elif volume >= 15:
            volume_score = 3 + (volume - 15) / 7.5                       # 3-5 range
        elif volume >= 10:
            volume_score = 1 + (volume - 10) / 7.5                        # 1-3 range
        else:
            volume_score = volume / 10                                     # 0-1 range
        
        volume_score = round(volume_score, 1)
        score += volume_score
        factors.append(f"Volume: {volume_score}/20")
        
        # 3. BALANCED ROI Score (0-15 points) - More generous percentage bands
        # Cap ROI at reasonable levels to avoid pump/dump items
        capped_margin_percent = min(25, scoring_margin_percent)
        
        if capped_margin_percent >= 8:
            roi_score = 13 + (capped_margin_percent - 8) / 8.5            # 13-15 range
        elif capped_margin_percent >= 5:
            roi_score = 11 + (capped_margin_percent - 5) / 1.5            # 11-13 range
        elif capped_margin_percent >= 3:
            roi_score = 8 + (capped_margin_percent - 3) / 0.67            # 8-11 range
        elif capped_margin_percent >= 2:
            roi_score = 6 + (capped_margin_percent - 2) / 0.5             # 6-8 range
        elif capped_margin_percent >= 1:
            roi_score = 4 + (capped_margin_percent - 1) / 0.5             # 4-6 range
        elif capped_margin_percent >= 0.5:
            roi_score = 2 + (capped_margin_percent - 0.5) / 0.25          # 2-4 range
        else:
            roi_score = capped_margin_percent * 4                         # 0-2 range
        
        roi_score = round(roi_score, 1)
        score += roi_score
        factors.append(f"ROI: {roi_score}/15 ({scoring_margin_percent:.1f}%)")
        
        # 4. Enhanced Stability Score (0-25 points) - More generous base scoring
        stability_score = 8  # Higher default for items without history
        trend_info = "No trend data"
        
        if history_prices and len(history_prices) >= 8:
            try:
                # Get more data points for better analysis
                recent_data = history_prices[-15:]
                highs = [entry.get('avgHighPrice', 0) for entry in recent_data if entry.get('avgHighPrice')]
                lows = [entry.get('avgLowPrice', 0) for entry in recent_data if entry.get('avgLowPrice')]
                
                if len(highs) >= 8 and len(lows) >= 8:
                    # Calculate multiple stability metrics
                    avg_high = statistics.mean(highs)
                    avg_low = statistics.mean(lows)
                    
                    # Coefficient of variation (more robust than simple variance)
                    if avg_high > 0 and avg_low > 0:
                        high_cv = (statistics.stdev(highs) / avg_high) * 100
                        low_cv = (statistics.stdev(lows) / avg_low) * 100
                        avg_cv = (high_cv + low_cv) / 2
                        
                        # BALANCED stability scoring - more generous
                        if avg_cv < 2:
                            stability_score = 25
                            trend_info = "🟢 Extremely Stable"
                        elif avg_cv < 4:
                            stability_score = 22 + (4 - avg_cv) * 1.5              # 22-25 range
                            trend_info = "🟢 Very Stable"
                        elif avg_cv < 7:
                            stability_score = 18 + (7 - avg_cv) * 1.33             # 18-22 range
                            trend_info = "🟢 Stable"
                        elif avg_cv < 12:
                            stability_score = 14 + (12 - avg_cv) * 0.8             # 14-18 range
                            trend_info = "🟡 Mostly Stable"
                        elif avg_cv < 20:
                            stability_score = 10 + (20 - avg_cv) * 0.5             # 10-14 range
                            trend_info = "🟡 Moderate"
                        elif avg_cv < 30:
                            stability_score = 6 + (30 - avg_cv) * 0.4              # 6-10 range
                            trend_info = "🟠 Volatile"
                        else:
                            stability_score = max(3, 6 - (avg_cv - 30) * 0.1)      # 3-6 range
                            trend_info = "🔴 Very Volatile"
                    
                    # More generous bonus/penalty for current prices vs historical averages
                    if avg_high > 0 and avg_low > 0:
                        high_deviation = abs(current_high_price - avg_high) / avg_high
                        low_deviation = abs(current_low_price - avg_low) / avg_low
                        avg_deviation = (high_deviation + low_deviation) / 2
                        
                        if avg_deviation < 0.05:
                            score += 4
                            trend_info += " | Perfect avg"
                        elif avg_deviation < 0.1:
                            score += 3
                            trend_info += " | Near avg"
                        elif avg_deviation < 0.15:
                            score += 2
                            trend_info += " | Close to avg"
                        elif avg_deviation < 0.25:
                            score += 1
                            trend_info += " | Reasonable avg"
                        elif avg_deviation > 0.5:
                            score -= 2
                            trend_info += " | Far from avg"
                        elif avg_deviation > 0.35:
                            score -= 1
                            trend_info += " | Off avg"
                            
            except Exception:
                pass
        
        stability_score = round(stability_score, 1)
        score += stability_score
        factors.append(f"Stability: {stability_score}/25")
        
        # 5. BALANCED Limit Score (0-15 points) - More generous scoring
        if limit <= 0:
            limit_score = 2  # Better base score for items without limits
        else:
            # Calculate potential daily profit using tax-adjusted margin
            daily_profit_potential = scoring_margin * limit
            
            if daily_profit_potential >= 2000000:  # 2M+ daily potential
                limit_score = 13 + min(2, (daily_profit_potential - 2000000) / 2000000)  # 13-15 range
            elif daily_profit_potential >= 1000000:  # 1M-2M daily potential
                limit_score = 11 + (daily_profit_potential - 1000000) / 500000           # 11-13 range
            elif daily_profit_potential >= 500000:   # 500K-1M daily potential
                limit_score = 9 + (daily_profit_potential - 500000) / 250000             # 9-11 range
            elif daily_profit_potential >= 250000:   # 250K-500K daily potential
                limit_score = 7 + (daily_profit_potential - 250000) / 125000             # 7-9 range
            elif daily_profit_potential >= 100000:   # 100K-250K daily potential
                limit_score = 5 + (daily_profit_potential - 100000) / 75000              # 5-7 range
            elif daily_profit_potential >= 50000:    # 50K-100K daily potential
                limit_score = 3 + (daily_profit_potential - 50000) / 25000               # 3-5 range
            else:
                limit_score = 2 + daily_profit_potential / 25000                         # 2-3 range
        
        limit_score = round(limit_score, 1)
        score += limit_score
        factors.append(f"Limit: {limit_score}/15")
        
        # 6. BALANCED Liquidity Score (0-5 points) - More achievable scoring
        if volume > 0 and scoring_margin > 0:
            turnover_ratio = volume / max(1, current_low_price / 1000)
            
            if turnover_ratio > 30:
                liquidity_score = 5
            elif turnover_ratio > 20:
                liquidity_score = 4.5 + (turnover_ratio - 20) / 20            # 4.5-5 range
            elif turnover_ratio > 15:
                liquidity_score = 4 + (turnover_ratio - 15) / 10              # 4-4.5 range
            elif turnover_ratio > 10:
                liquidity_score = 3.5 + (turnover_ratio - 10) / 10            # 3.5-4 range
            elif turnover_ratio > 5:
                liquidity_score = 2.5 + (turnover_ratio - 5) / 5              # 2.5-3.5 range
            elif turnover_ratio > 2:
                liquidity_score = 1.5 + (turnover_ratio - 2) / 3              # 1.5-2.5 range
            elif turnover_ratio > 1:
                liquidity_score = 1 + (turnover_ratio - 1) / 1                # 1-1.5 range
            else:
                liquidity_score = 0.5 + turnover_ratio / 2                    # 0.5-1 range
        else:
            liquidity_score = 0.5
        
        liquidity_score = round(liquidity_score, 1)
        score += liquidity_score
        factors.append(f"Liquidity: {liquidity_score}/5")
        
        # Final score bounds with decimal precision
        score = max(0, min(100, round(score, 1)))
        
        # Create comprehensive summary
        risk_indicator = ""
        if is_suspicious:
            if risk_level >= 3:
                risk_indicator = "🚨 HIGH RISK"
            elif risk_level >= 2:
                risk_indicator = "⚠️ MEDIUM RISK"
            else:
                risk_indicator = "⚡ LOW RISK"
        else:
            risk_indicator = "✅ Clean"
        
        summary = f"{trend_info} | {risk_indicator} | Score: {score}/100"
        
        return score, summary, (is_suspicious, risk_level, risk_reason)

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
        profitable_items = []
        total_items_checked = 0
        alchemizable_items = 0
        
        for item_id in self.item_mapping:
            total_items_checked += 1
            
            # First check if item is alchemizable
            if not self.is_alchemizable(self.item_mapping[item_id]):
                continue
                
            alchemizable_items += 1
            profit_data = self.calculate_alchemy_profit(item_id)
            
            if profit_data is None:
                continue
                
            # Apply filters
            if profit_data['profit'] < min_profit:
                continue
                
            if members_only is not None:
                if profit_data['members'] != members_only:
                    continue
                    
            # Filter for buy price
            if max_buy_price is not None:
                if profit_data['buy_price'] > max_buy_price:
                    continue
                    
            # Filter for limit
            if min_limit is not None:
                if profit_data['limit'] < min_limit:
                    continue
                    
            # Filter for minimum volume
            if min_volume is not None:
                if profit_data['recent_volume'] < min_volume:
                    continue
                    
            # Filter for maximum ROI
            if max_roi is not None:
                if profit_data['roi_percent'] > max_roi:
                    continue
            
            profitable_items.append(profit_data)
        
        # Sort by profit descending and return top items
        profitable_items.sort(key=lambda x: x['profit'], reverse=True)
        
        print(f"Filtering results: {total_items_checked} total items, {alchemizable_items} alchemizable, {len(profitable_items)} profitable")
        
        return profitable_items[:max_items]
    
    def get_top_flips(self, limit: int = 10, min_margin: int = 200, min_volume: int = 20, 
                    max_buy_price: int = None, fetch_history: bool = True, 
                    max_margin_percent: float = 20.0, exclude_high_risk: bool = True,
                    min_score: int = 30) -> List[Dict]:
        """
        Enhanced get_top_flips with pump/dump filtering and better scoring
        FIXED: Now properly calculates scores and accounts for GE tax
        """
        if not self.current_prices or not self.volume_data:
            print("Missing price or volume data. Make sure to fetch current prices and volume data first.")
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
        
        print(f"Pre-filtered to {len(flips)} candidates, analyzing top {len(top_candidates)} with history")
        
        # Second pass: fetch history and calculate enhanced scores
        if fetch_history and top_candidates:
            print(f"Analyzing price history for top {len(top_candidates)} candidates...")
            analyzed_flips = []
            
            for i, flip in enumerate(top_candidates):
                try:
                    print(f"Fetching history for {flip['name']} ({i+1}/{len(top_candidates)})")
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
                    print(f"Error analyzing {flip['name']}: {e}")
                    # FIXED: Still include items that couldn't be analyzed but passed basic filters
                    if flip['score'] >= min_score:
                        analyzed_flips.append(flip)
                    continue
            
            # Sort by score after analysis
            analyzed_flips.sort(key=lambda x: (x['score'], x['margin']), reverse=True)
            print(f"History analysis complete: {len(analyzed_flips)} items passed all filters")
            return analyzed_flips[:limit]
        else:
            for flip in flips:
                flip['score'] = (flip['score'] / 45) * 100            
            # Return without detailed analysis, but still properly scored
            print(f"Returning {len(top_candidates[:limit])} items with basic scoring")
            return top_candidates[:limit]

    def display_alchemy_results(self, items: List[Dict], show_count: int = 20):
        """Display alchemy results in a formatted table"""
        if not items:
            print("No profitable alchemizable items found with the given criteria.")
            return
            
        print(f"\nTop {min(show_count, len(items))} High Alchemy Opportunities (Alchemizable Items Only):")
        print("-" * 140)
        print(f"{'Rank':<4} {'Item Name':<18} {'Buy Price':<10} {'Alch Value':<10} {'Profit':<8} {'ROI%':<5} {'Limit':<6} {'Max Profit':<10} {'Volume/hr':<10} {'Members'}")
        print("-" * 140)
        
        for i, item in enumerate(items[:show_count], 1):
            members_str = "Yes" if item['members'] else "No"
            volume_str = f"{item['recent_volume']:,}" if item['recent_volume'] > 0 else "N/A"
            print(f"{i:<4} {item['name'][:16]:<18} {item['buy_price']:<10,} "
                  f"{item['high_alch_value']:<10,} {item['profit']:<8,} {item['roi_percent']:<5.1f} "
                  f"{item['limit']:<6} {item['max_profit_per_limit']:<10,} {volume_str:<10} {members_str}")
    
    def display_flip_results(self, flips: List[Dict], show_count: int = 20):
        """Enhanced display with risk indicators"""
        if not flips:
            print("No profitable flipping opportunities found with the given criteria.")
            return
            
        print(f"\nTop {min(show_count, len(flips))} Flipping Opportunities:")
        print("-" * 150)
        print(f"{'Rank':<4} {'Item Name':<25} {'Buy Price':<12} {'Sell Price':<12} {'Margin':<9} {'Margin%':<7} {'Volume':<8} {'Score':<5} {'Risk':<12} {'Members'}")
        print("-" * 150)
        
        for i, flip in enumerate(flips[:show_count], 1):
            members_str = "Yes" if flip['members'] else "No"
            
            # Risk indicator
            risk_level = flip.get('risk_level', 0)
            if risk_level >= 3:
                risk_indicator = "🚨 HIGH"
            elif risk_level >= 2:
                risk_indicator = "⚠️ MEDIUM"
            elif risk_level >= 1:
                risk_indicator = "⚡ LOW"
            else:
                risk_indicator = "✅ Clean"
            
            print(f"{i:<4} {flip['name'][:23]:<25} {flip['buy_price']:<12,} "
                  f"{flip['sell_price']:<12,} {flip['margin']:<9,} {flip['margin_percent']:<7.1f} "
                  f"{flip['volume']:<8,} {flip['score']:<5.0f} {risk_indicator:<12} {members_str}")
        
        # Show detailed risk information for top items
        print(f"\nDetailed Risk Analysis for Top {min(5, len(flips))} Items:")
        print("-" * 80)
        for i, flip in enumerate(flips[:min(5, len(flips))], 1):
            risk_info = flip.get('risk_info', 'No analysis')
            print(f"{i}. {flip['name']}: {risk_info}")
    
    def save_to_csv(self, items: List[Dict], filename: str = "osrs_analysis.csv"):
        """Save results to CSV file"""
        if not items:
            print("No data to save.")
            return
            
        try:
            df = pd.DataFrame(items)
            df.to_csv(filename, index=False)
            print(f"Results saved to {filename}")
        except Exception as e:
            print(f"Error saving to CSV: {e}")
            print("Data structure might be incompatible with CSV format.")
    
    def get_non_alchemizable_sample(self, sample_size: int = 10) -> List[Dict]:
        """
        Get a sample of items that are not alchemizable for debugging purposes
        """
        non_alchemizable = []
        
        for item_id, item_info in list(self.item_mapping.items())[:1000]:  # Check first 1000 items
            if not self.is_alchemizable(item_info):
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
    
    def run_alchemy_analysis(self, min_profit: int = 0, max_items: int = 100, 
                        members_only: bool = None, save_csv: bool = False,
                        max_buy_price: int = None, min_limit: int = None, 
                        min_volume: int = None, max_roi: float = None,
                        show_non_alchemizable_sample: bool = False,
                        show_crash_alerts: bool = False, 
                        alert_min_profit: int = 100, 
                        alert_min_imbalance: float = 2.0):
        """
        Run complete alchemy profit analysis with optional crash detection
        
        Args:
            min_profit: Minimum profit per cast
            max_items: Maximum number of items to analyze
            members_only: Filter by members items (True/False/None for all)
            save_csv: Whether to save results to CSV
            max_buy_price: Maximum buy price for items (None for no limit)
            min_limit: Minimum buying limit (None for no limit)
            min_volume: Minimum hourly trading volume (None for no limit)
            max_roi: Maximum ROI percentage (None for no limit)
            show_non_alchemizable_sample: Show sample of filtered non-alchemizable items
            show_crash_alerts: Whether to show crash risk alerts (NEW)
            alert_min_profit: Minimum profit for crash alerts (NEW)
            alert_min_imbalance: Minimum volume imbalance ratio for alerts (NEW)
        """
        analysis_title = "OSRS High Alchemy Profit Analysis with Alchemizable Filter"
        if show_crash_alerts:
            analysis_title += " + Crash Detection"
        
        print(f"Starting {analysis_title}...")
        print("=" * 70)
        
        # Fetch data
        if not self.fetch_item_mapping():
            print("Failed to fetch item mapping. Exiting.")
            return
            
        if not self.fetch_current_prices():
            print("Failed to fetch current prices. Exiting.")
            return
            
        if not self.fetch_volume_data():
            print("Failed to fetch volume data. Continuing without volume filtering.")
        
        # Fetch 5-minute data for crash alerts if requested
        if show_crash_alerts:
            print("Fetching 5-minute data for crash risk analysis...")
            if not self.fetch_five_minute_data():
                print("Warning: Failed to fetch 5-minute data, crash alerts will be limited")
        
        # Show sample of non-alchemizable items if requested
        if show_non_alchemizable_sample:
            print("\nSample of items filtered out as non-alchemizable:")
            print("-" * 80)
            non_alch_sample = self.get_non_alchemizable_sample()
            for item in non_alch_sample:
                reason = "No alch value" if item['highalch'] <= 0 else "No trade limit" if item['limit'] <= 0 else "Name/examine filter"
                print(f"{item['name'][:25]:<25} | Alch: {item['highalch']:<6} | Limit: {item['limit']:<4} | Reason: {reason}")
            print("-" * 80)
        
        # Display filter information
        print(f"\nFilters applied:")
        print(f"Minimum profit: {min_profit:,} gp")
        if max_buy_price is not None:
            print(f"Maximum buy price: {max_buy_price:,} gp")
        if min_limit is not None:
            print(f"Minimum buying limit: {min_limit}")
        if min_volume is not None:
            print(f"Minimum hourly volume: {min_volume:,}")
        if max_roi is not None:
            print(f"Maximum ROI: {max_roi}%")
        if members_only is not None:
            print(f"Membership: {'Members only' if members_only else 'F2P only'}")
        if show_crash_alerts:
            print(f"Crash alerts: Enabled (min profit: {alert_min_profit:,}gp, min imbalance: {alert_min_imbalance}x)")
        
        profitable_items = self.get_profitable_items(
            min_profit=min_profit,
            max_items=max_items,
            members_only=members_only,
            max_buy_price=max_buy_price,
            min_limit=min_limit,
            min_volume=min_volume,
            max_roi=max_roi
        )
        
        # Display results
        self.display_alchemy_results(profitable_items)
        
        # Show crash alerts if enabled
        if show_crash_alerts and profitable_items:
            print("\n" + "=" * 70)
            print("ALCHEMY CRASH RISK ALERTS")
            print("=" * 70)
            
            # Get crash alerts
            crash_alerts = self.get_alchemy_alerts(
                min_profit=alert_min_profit,
                min_volume_imbalance=alert_min_imbalance
            )
            
            # Get item IDs from our profitable items for comparison
            profitable_item_ids = {item['item_id'] for item in profitable_items}
            
            # Separate alerts into those affecting our results vs others
            relevant_alerts = [alert for alert in crash_alerts 
                            if alert['item_id'] in profitable_item_ids]
            other_alerts = [alert for alert in crash_alerts 
                        if alert['item_id'] not in profitable_item_ids]
            
            if relevant_alerts:
                print(f"\n🚨 CRASH RISK FOR YOUR ITEMS ({len(relevant_alerts)} items):")
                print("-" * 70)
                print(f"{'Item':<25} | {'Profit':<8} | {'Status':<12} | {'Vol Ratio':<10} | {'Alert %':<8} | {'Rec'}")
                print("-" * 70)
                
                for alert in relevant_alerts:
                    status_emoji = '🔴' if alert['status'] == 'crashing' else '🟡'
                    rec_emoji = '🔥' if alert['recommendation'] == 'buy low' else '⚠️'
                    
                    print(f"{status_emoji} {alert['name'][:23]:<23} | "
                        f"{alert['profit']:>7,.0f} | "
                        f"{alert['status']:<12} | "
                        f"{alert['volume_ratio']:>8.1f}x | "
                        f"{alert['alert_percent']:>6.1f}% | "
                        f"{rec_emoji} {alert['recommendation'].upper()}")
            else:
                print("\n✅ No crash risks detected for your profitable alchemy items")
                print("All your items show healthy volume balance")
            
            # Show other market crash risks
            if other_alerts:
                print(f"\n📊 OTHER ALCHEMY CRASH RISKS ({len(other_alerts[:5])} of {len(other_alerts)}):")
                print("-" * 70)
                
                for alert in other_alerts[:5]:  # Show top 5 other risks
                    status_emoji = '🔴' if alert['status'] == 'crashing' else '🟡'
                    print(f"{status_emoji} {alert['name'][:30]:<30} | "
                        f"Profit: {alert['profit']:>6,.0f} | "
                        f"Vol Ratio: {alert['volume_ratio']:>5.1f}x | "
                        f"Status: {alert['status']}")
        
        # Save to CSV if requested
        if save_csv:
            self.save_to_csv(profitable_items, "alchemy_profits.csv")
        
        # Enhanced summary statistics
        if profitable_items:
            total_profitable = len(profitable_items)
            avg_profit = sum(item['profit'] for item in profitable_items) / total_profitable
            max_profit = profitable_items[0]['profit'] if profitable_items else 0
            avg_volume = sum(item['recent_volume'] for item in profitable_items) / total_profitable
            avg_roi = sum(item['roi_percent'] for item in profitable_items) / total_profitable
            
            print(f"\n" + "=" * 70)
            print("SUMMARY")
            print("=" * 70)
            print(f"Total profitable alchemizable items found: {total_profitable}")
            print(f"Average profit per cast: {avg_profit:,.1f} gp")
            print(f"Maximum profit per cast: {max_profit:,} gp")
            print(f"Average ROI: {avg_roi:.1f}%")
            print(f"Average hourly volume: {avg_volume:,.0f}")
            print(f"Nature rune cost used: {self.nature_rune_cost} gp")
            
            # Crash alert summary if enabled
            if show_crash_alerts:
                crash_alerts = self.get_alchemy_alerts(alert_min_profit, alert_min_imbalance)
                profitable_item_ids = {item['item_id'] for item in profitable_items}
                relevant_alerts = [alert for alert in crash_alerts 
                                if alert['item_id'] in profitable_item_ids]
                
                alert_counts = {}
                for alert in relevant_alerts:
                    status = alert['status']
                    alert_counts[status] = alert_counts.get(status, 0) + 1
                
                print(f"\nCrash Alert Summary for Your Items:")
                if alert_counts:
                    for status, count in alert_counts.items():
                        emoji = '🔴' if status == 'crashing' else '🟡'
                        print(f"  {emoji} {status.replace('_', ' ').title()}: {count}")
                else:
                    print(f"  ✅ All items stable (no crash risks detected)")

    def run_flipping_analysis(self, limit: int = 10, min_margin: int = 200, 
                        min_volume: int = 20, max_buy_price: int = None,
                        members_only: bool = None, save_csv: bool = False, 
                        fetch_history: bool = True, max_margin_percent: float = 20.0,
                        exclude_high_risk: bool = True, min_score: int = 30,
                        use_averaged_prices: bool = True, show_alerts: bool = True,
                        alert_min_margin: int = 1000, alert_min_volume: int = 20):
        """
        Enhanced flipping analysis with optional price averaging and integrated alerts
        
        Args:
            show_alerts: Whether to show crash/trend alerts for flipping items
            alert_min_margin: Minimum margin for flipping alerts
            alert_min_volume: Minimum volume for flipping alerts
        """
        print("Starting Enhanced OSRS Flipping Analysis with Price Averaging and Alerts...")
        print("=" * 70)
        
        # Fetch basic data
        if not self.item_mapping:
            if not self.fetch_item_mapping():
                print("Failed to fetch item mapping. Exiting.")
                return
        
        if not self.current_prices:
            if not self.fetch_current_prices():
                print("Failed to fetch current prices. Exiting.")
                return
                
        if not self.volume_data:
            if not self.fetch_volume_data():
                print("Failed to fetch volume data. Exiting.")
                return
        
        # Fetch averaged prices for flipping if requested
        if use_averaged_prices:
            self.use_flipping_averages = True
            print("Fetching averaged prices for more stable flipping analysis...")
            if not self.fetch_flipping_average_prices():
                print("Warning: Failed to fetch averaged prices, falling back to realtime prices")
                self.use_flipping_averages = False
        else:
            self.use_flipping_averages = False
        
        # Fetch 5-minute data for alerts if requested
        if show_alerts:
            print("Fetching 5-minute data for trend and crash analysis...")
            if not self.fetch_five_minute_data():
                print("Warning: Failed to fetch 5-minute data, alerts will be limited")
        
        print(f"\nPrice source: {'Averaged (more stable)' if self.use_flipping_averages else 'Realtime'}")
        print(f"Alert system: {'Enabled' if show_alerts else 'Disabled'}")
        print(f"\nEnhanced Filters applied:")
        print(f"Minimum margin: {min_margin:,} gp")
        print(f"Minimum volume: {min_volume:,}")
        print(f"Maximum margin percentage: {max_margin_percent}%")
        print(f"Minimum score: {min_score}/100")
        print(f"Exclude high risk: {'Yes' if exclude_high_risk else 'No'}")
        if max_buy_price is not None:
            print(f"Maximum buy price: {max_buy_price:,} gp")
        if members_only is not None:
            print(f"Membership: {'Members only' if members_only else 'F2P only'}")
        
        # Get flips with enhanced filtering
        flips = self.get_top_flips(
            limit=limit * 2,  # Get more items to account for filtering
            min_margin=min_margin,
            min_volume=min_volume,
            max_buy_price=max_buy_price,
            fetch_history=fetch_history,
            max_margin_percent=max_margin_percent,
            exclude_high_risk=exclude_high_risk,
            min_score=min_score
        )
        
        # Apply members filter if specified
        if members_only is not None:
            flips = [flip for flip in flips if flip['members'] == members_only]
        
        # Trim to requested limit after filtering
        flips = flips[:limit]
        
        # Display results
        self.display_flip_results(flips)
        
        # Show alerts if enabled
        if show_alerts and flips:
            print("\n" + "=" * 70)
            print("MARKET TREND & CRASH ALERTS")
            print("=" * 70)
            
            # Get flipping alerts for the items we're showing
            flipping_alerts = self.get_flipping_alerts(
                min_margin=alert_min_margin,
                min_volume=alert_min_volume
            )
            
            # Filter alerts to only include items from our flip results
            flip_item_ids = {flip['id'] for flip in flips}
            relevant_alerts = [alert for alert in flipping_alerts 
                            if alert['item_id'] in flip_item_ids]
            
            if relevant_alerts:
                print(f"\n🚨 ACTIVE ALERTS ({len(relevant_alerts)} items):")
                print("-" * 70)
                
                for alert in relevant_alerts:
                    status_emoji = {
                        'crashing': '🔴',
                        'crash_risk': '🟡',
                        'surging': '🟢',
                        'surge_risk': '🟠'
                    }.get(alert['status'], '⚪')
                    
                    recommendation_emoji = {
                        'avoid': '❌',
                        'caution': '⚠️',
                        'opportunity': '💰',
                        'safe': '✅'
                    }.get(alert['recommendation'], '❓')
                    
                    print(f"{status_emoji} {alert['name'][:30]:<30} | "
                        f"Status: {alert['status']:<12} | "
                        f"Price Δ: {alert['price_change_percent']:>6.1f}% | "
                        f"Vol: {alert['high_volume']:>4}/{alert['low_volume']:<4} | "
                        f"{recommendation_emoji} {alert['recommendation'].upper()}")
            else:
                print("\n✅ No significant alerts for your current flipping opportunities")
                print("All items appear stable based on recent 5-minute data")
            
            # Show broader market alerts (items not in current flip list)
            other_alerts = [alert for alert in flipping_alerts 
                        if alert['item_id'] not in flip_item_ids]
            
            if other_alerts:
                print(f"\n📊 OTHER MARKET MOVEMENTS ({len(other_alerts[:10])} of {len(other_alerts)}):")
                print("-" * 70)
                
                for alert in other_alerts[:10]:  # Show top 10 other alerts
                    status_emoji = {
                        'crashing': '🔴',
                        'crash_risk': '🟡',
                        'surging': '🟢',
                        'surge_risk': '🟠'
                    }.get(alert['status'], '⚪')
                    
                    print(f"{status_emoji} {alert['name'][:30]:<30} | "
                        f"Status: {alert['status']:<12} | "
                        f"Price Δ: {alert['price_change_percent']:>6.1f}% | "
                        f"Margin: {alert['margin']:>8,.0f}gp")
        
        # Save to CSV if requested
        if save_csv:
            self.save_to_csv(flips, "enhanced_flipping_opportunities.csv")
        
        # Enhanced summary statistics
        if flips:
            total_flips = len(flips)
            avg_margin = sum(flip['margin'] for flip in flips) / total_flips
            avg_margin_percent = sum(flip['margin_percent'] for flip in flips) / total_flips
            avg_volume = sum(flip['volume'] for flip in flips) / total_flips
            avg_score = sum(flip['score'] for flip in flips) / total_flips
            
            # Risk distribution
            high_risk = len([f for f in flips if f.get('risk_level', 0) >= 3])
            medium_risk = len([f for f in flips if f.get('risk_level', 0) == 2])
            low_risk = len([f for f in flips if f.get('risk_level', 0) == 1])
            clean = len([f for f in flips if f.get('risk_level', 0) == 0])
            
            print(f"\n" + "=" * 70)
            print("ENHANCED SUMMARY")
            print("=" * 70)
            print(f"Total flipping opportunities found: {total_flips}")
            print(f"Average margin: {avg_margin:,.0f} gp ({avg_margin_percent:.1f}%)")
            print(f"Average volume: {avg_volume:,.0f}")
            print(f"Average flip score: {avg_score:.1f}/100")
            print(f"\nRisk Distribution:")
            print(f"  🚨 High Risk: {high_risk}")
            print(f"  ⚠️ Medium Risk: {medium_risk}")
            print(f"  ⚡ Low Risk: {low_risk}")
            print(f"  ✅ Clean: {clean}")
            
            # Alert summary if enabled
            if show_alerts:
                flipping_alerts = self.get_flipping_alerts(alert_min_margin, alert_min_volume)
                flip_item_ids = {flip['id'] for flip in flips}
                relevant_alerts = [alert for alert in flipping_alerts 
                                if alert['item_id'] in flip_item_ids]
                
                alert_counts = {}
                for alert in relevant_alerts:
                    status = alert['status']
                    alert_counts[status] = alert_counts.get(status, 0) + 1
                
                print(f"\nAlert Summary for Your Items:")
                if alert_counts:
                    for status, count in alert_counts.items():
                        emoji = {'crashing': '🔴', 'crash_risk': '🟡', 
                                'surging': '🟢', 'surge_risk': '🟠'}.get(status, '⚪')
                        print(f"  {emoji} {status.replace('_', ' ').title()}: {count}")
                else:
                    print(f"  ✅ All items stable (no alerts)")

    def run_combined_analysis(self, alchemy_filters: Dict = None, flipping_filters: Dict = None,
                            save_csv: bool = False):
        """
        Run both alchemy and flipping analysis with shared data fetching
        
        Args:
            alchemy_filters: Dictionary of filters for alchemy analysis
            flipping_filters: Dictionary of filters for flipping analysis
            save_csv: Whether to save results to CSV files
        """
        print("Starting Combined OSRS Analysis (Alchemy + Enhanced Flipping)...")
        print("=" * 70)
        
        # Set default filters if not provided
        if alchemy_filters is None:
            alchemy_filters = {
                'min_profit': 0,
                'max_items': 50,
                'members_only': None,
                'max_buy_price': None,
                'min_limit': None,
                'min_volume': None,
                'max_roi': None
            }
        
        if flipping_filters is None:
            flipping_filters = {
                'limit': 10,
                'min_margin': 200,
                'min_volume': 20,
                'members_only': None,
                'fetch_history': True,
                'max_margin_percent': 20.0,
                'exclude_high_risk': True,
                'min_score': 30
            }
        
        # Fetch shared data once
        if not self.fetch_item_mapping():
            print("Failed to fetch item mapping. Exiting.")
            return
        
        # Run alchemy analysis
        print("\n" + "="*50)
        print("HIGH ALCHEMY ANALYSIS")
        print("="*50)
        
        if not self.fetch_current_prices():
            print("Failed to fetch current prices for alchemy analysis.")
        else:
            if not self.fetch_volume_data():
                print("Warning: Failed to fetch volume data for alchemy analysis.")
            
            profitable_items = self.get_profitable_items(**alchemy_filters)
            self.display_alchemy_results(profitable_items)
            
            if save_csv:
                self.save_to_csv(profitable_items, "alchemy_profits.csv")
        
        # Run enhanced flipping analysis
        print("\n" + "="*50)
        print("ENHANCED FLIPPING ANALYSIS")
        print("="*50)
        
        # Reuse current prices and volume data if already fetched for alchemy
        if not self.current_prices:
            if not self.fetch_current_prices():
                print("Failed to fetch current prices for flipping analysis.")
                return
        
        if not self.volume_data:
            if not self.fetch_volume_data():
                print("Failed to fetch volume data for flipping analysis.")
                return
        
        # Extract members_only from flipping_filters before passing to get_top_flips
        members_filter = flipping_filters.pop('members_only', None)
        flips = self.get_top_flips(**flipping_filters)
        
        # Apply members filter if specified
        if members_filter is not None:
            flips = [flip for flip in flips if flip['members'] == members_filter]
        
        self.display_flip_results(flips)
        
        if save_csv:
            self.save_to_csv(flips, "enhanced_flipping_opportunities.csv")
        
        print("\n" + "="*70)
        print("ENHANCED ANALYSIS COMPLETE")
        print("="*70)

    def fetch_flipping_average_prices(self, item_ids: List[int] = None, timestep: str = "24h") -> bool:
        """
        FIXED: Fetch average prices specifically for flipping analysis using timeseries data
        Now properly limits the number of items to prevent excessive API calls
        """
        if not self.current_prices:
            print("No current prices available. Fetch current prices first.")
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
            
            print(f"Auto-selected {len(item_ids)} promising items from {len(candidate_items)} candidates")
        
        # Additional safety check
        if len(item_ids) > 100:
            print(f"WARNING: Too many items ({len(item_ids)}), limiting to top 100")
            item_ids = item_ids[:100]
        
        print(f"Fetching flipping average prices for {len(item_ids)} items using {timestep} timestep...")
        
        successful_fetches = 0
        failed_fetches = 0
        
        for i, item_id in enumerate(item_ids):
            try:
                # Progress indicator every 10 items instead of 25
                if (i + 1) % 10 == 0:
                    print(f"Processed {i + 1}/{len(item_ids)} items...")
                
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
                print(f"Error fetching data for item {item_id}: {e}")
                failed_fetches += 1
                continue
        
        print(f"Flipping average price fetching complete: {successful_fetches} successful, {failed_fetches} failed")
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
        This indicates people are dumping items, which could crash the buy price
        
        Args:
            item_id: Item ID to analyze
            
        Returns:
            Dictionary with simple crash analysis for alchemy items
        """
        result = {
            'status': 'stable',  # stable, crash_risk, crashing
            'high_volume': 0,
            'low_volume': 0,
            'hourly_volume': 0,
            'volume_ratio': 0,  # low_volume / high_volume
            'volume_spike': False,  # if 5m volume >> hourly average
            'alert_percent': 0,  # how much more low volume vs high volume
            'recommendation': 'safe'  # safe, caution, avoid
        }
        
        try:
            # Get 5-minute data for most recent volume info
            five_min_info = self.five_min_data.get(item_id)
            if not five_min_info:
                return result
                
            high_vol = five_min_info.get('high_volume', 0)
            low_vol = five_min_info.get('low_volume', 0)
            
            # Get hourly volume for comparison
            hourly_vol = self.volume_data.get(item_id, 0)
            
            result['high_volume'] = high_vol
            result['low_volume'] = low_vol
            result['hourly_volume'] = hourly_vol
            
            # Check for volume spike (5m volume vs hourly average)
            if hourly_vol > 0:
                # Convert hourly to 5-minute average for comparison
                hourly_avg_5min = hourly_vol / 12  # 12 five-minute periods in an hour
                current_5min_total = high_vol + low_vol
                
                if current_5min_total > (hourly_avg_5min * 3):  # 3x normal volume
                    result['volume_spike'] = True
            
            # Calculate volume imbalance analysis
            if high_vol > 0:
                volume_ratio = low_vol / high_vol
                result['volume_ratio'] = round(volume_ratio, 1)
                result['alert_percent'] = round((volume_ratio - 1) * 100, 1)
            else:
                # If no high volume but there's low volume, that's concerning
                if low_vol > 0:
                    result['volume_ratio'] = 999  # Effectively infinite
                    result['alert_percent'] = 999
                else:
                    return result
            
            # Determine status based on volume imbalance AND volume spikes
            crash_score = 0
            
            # Volume imbalance scoring
            if result['volume_ratio'] >= 5.0:  # 5x more selling than buying
                crash_score += 30
            elif result['volume_ratio'] >= 3.0:  # 3x more selling
                crash_score += 20
            elif result['volume_ratio'] >= 2.0:  # 2x more selling
                crash_score += 10
            
            # Volume spike bonus (dump signal)
            if result['volume_spike']:
                crash_score += 15
            
            # Final status determination
            if crash_score >= 35:
                result['status'] = 'crashing'
                result['recommendation'] = 'buy low'
            elif crash_score >= 20:
                result['status'] = 'crash_risk'
                result['recommendation'] = 'consider buying'
            else:
                result['status'] = 'stable'
                result['recommendation'] = 'stable'
                
        except Exception as e:
            result['status'] = 'error'
            
        return result

    def analyze_flipping_trend(self, item_id: int) -> Dict:
        """
        Simplified flipping trend analysis for Discord alerts
        
        Args:
            item_id: Item ID to analyze
            
        Returns:
            Dictionary with simple trend analysis
        """
        result = {
            'status': 'stable',  # stable, crash_risk, crashing, surge_risk, surging
            'high_volume': 0,
            'low_volume': 0,
            'hourly_volume': 0,
            'volume_spike': False,
            'price_change_percent': 0,  # positive = rising, negative = falling
            'recommendation': 'safe'  # safe, caution, avoid, opportunity
        }
        
        try:
            # Get current and 5-minute data
            current_price = self.current_prices.get(str(item_id))
            five_min_info = self.five_min_data.get(item_id)
            hourly_vol = self.volume_data.get(item_id, 0)
            
            if not current_price or not five_min_info:
                return result
                
            # Volume data
            result['high_volume'] = five_min_info.get('high_volume', 0)
            result['low_volume'] = five_min_info.get('low_volume', 0)
            result['hourly_volume'] = hourly_vol
            
            # Check for volume spike
            if hourly_vol > 0:
                hourly_avg_5min = hourly_vol / 12
                current_5min_total = result['high_volume'] + result['low_volume']
                if current_5min_total > (hourly_avg_5min * 3):
                    result['volume_spike'] = True
            
            # Price change analysis (focus on high price for flipping)
            current_high = current_price.get('high')
            five_min_high = five_min_info.get('high')
            
            if current_high and five_min_high and five_min_high > 0:
                price_change = ((current_high - five_min_high) / five_min_high) * 100
                result['price_change_percent'] = round(price_change, 1)
                
                # Volume analysis for confirmation
                high_vol = result['high_volume']
                low_vol = result['low_volume']
                volume_imbalance = False
                
                if high_vol > 0:
                    volume_ratio = low_vol / high_vol
                    volume_imbalance = volume_ratio > 2.0  # More selling than buying
                elif low_vol > 10:  # Selling with no buying
                    volume_imbalance = True
                
                # Determine status with volume spike consideration
                crash_score = 0
                surge_score = 0
                
                # Price movement scoring
                if price_change <= -5.0:
                    crash_score += 30
                elif price_change <= -2.0:
                    crash_score += 15
                elif price_change >= 5.0:
                    surge_score += 30
                elif price_change >= 2.0:
                    surge_score += 15
                
                # Volume factors
                if volume_imbalance:
                    crash_score += 15
                if result['volume_spike'] and price_change < -1:
                    crash_score += 20  # Volume spike + price drop = dump
                if result['volume_spike'] and price_change > 1:
                    surge_score += 10  # Volume spike + price rise = pump (could be good or bad)
                
                # Final determination
                if crash_score >= 35:
                    result['status'] = 'crashing'
                    result['recommendation'] = 'avoid'
                elif crash_score >= 20:
                    result['status'] = 'crash_risk'
                    result['recommendation'] = 'caution'
                elif surge_score >= 35:
                    result['status'] = 'surging'
                    result['recommendation'] = 'opportunity'
                elif surge_score >= 15:
                    result['status'] = 'surge_risk'
                    result['recommendation'] = 'caution'
                else:
                    result['status'] = 'stable'
                    result['recommendation'] = 'safe'
                        
        except Exception as e:
            result['status'] = 'error'
            
        return result

    def get_alchemy_alerts(self, min_profit: int = 100, min_volume_imbalance: float = 2.0,
                        min_limit: int = None, min_volume: int = None) -> List[Dict]:
        """
        Get alchemy items with crash risk alerts for Discord bot
    
        Args:
            min_profit: Minimum profit to consider alerting about
            min_volume_imbalance: Minimum ratio of low_volume/high_volume to alert
        
        Returns:
            List of alchemy items with crash risk
        """
        alerts = []
    
        # FIXED: Check if five_min_data exists AND has items
        if not hasattr(self, 'five_min_data') or not self.five_min_data or len(self.five_min_data) == 0:
            print("⚠️ No 5-minute data available, fetching...")
            try:
                self.fetch_five_minute_data()
                if not self.five_min_data or len(self.five_min_data) == 0:
                    print("❌ Still no 5-minute data after fetch - cannot generate alchemy alerts")
                    return []
                print(f"✅ Fetched 5-minute data for {len(self.five_min_data)} items")
            except Exception as e:
                print(f"❌ Failed to fetch 5-minute data: {e}")
                return []
    
        # Get profitable alchemy items
        print(f"🔍 Looking for profitable items with profit ≥ {min_profit}gp...")
        profitable_items = self.get_profitable_items(min_profit=min_profit, max_items=200, min_limit=min_limit,
                                                    min_volume=min_volume)
        
        print(f"📊 Found {len(profitable_items)} profitable alchemy items to analyze")
    
        for item in profitable_items:
            item_id = item['item_id']
        
            # Analyze crash risk
            try:
                crash_analysis = self.analyze_alchemy_crash_risk(item_id)
                
                # Debug logging for first few items
                if len(alerts) < 3:
                    print(f"🔍 {item['name']}: status={crash_analysis.get('status', 'unknown')}, "
                        f"volume_ratio={crash_analysis.get('volume_ratio', 0):.2f}")
            except Exception as e:
                print(f"⚠️ Error analyzing {item['name']}: {e}")
                continue
        
            # Only alert if there's risk and volume imbalance meets threshold
            if (crash_analysis.get('status') in ['crash_risk', 'crashing'] and
                crash_analysis.get('volume_ratio', 0) >= min_volume_imbalance):
            
                alerts.append({
                    'name': item['name'],
                    'item_id': item_id,
                    'profit': item['profit'],
                    'buy_price': item['buy_price'],
                    'alch_value': item['high_alch_value'],
                    'status': crash_analysis['status'],
                    'high_volume': crash_analysis['high_volume'],
                    'low_volume': crash_analysis['low_volume'],
                    'volume_ratio': crash_analysis['volume_ratio'],
                    'alert_percent': crash_analysis.get('alert_percent', 0),
                    'recommendation': crash_analysis.get('recommendation', 'unknown')
                })
                
                print(f"✅ Added alert for {item['name']}: {crash_analysis['status']}")
    
        print(f"🚨 Generated {len(alerts)} alchemy crash alerts")
        
        # Sort by volume ratio (most concerning first)  
        alerts.sort(key=lambda x: x['volume_ratio'], reverse=True)
    
        return alerts

    def get_flipping_alerts(self, min_margin: int = 1000, min_volume: int = 20) -> List[Dict]:
        """
        Get flipping items with trend alerts for Discord bot
        
        Args:
            min_margin: Minimum margin to consider
            min_volume: Minimum volume to consider
            
        Returns:
            List of flipping items with trend alerts
        """
        alerts = []
        
        # Ensure we have required data
        if not self.five_min_data:
            self.fetch_five_minute_data()
        
        # Get current flipping opportunities
        flips = self.get_top_flips(
            limit=100,
            min_margin=min_margin,
            min_volume=min_volume,
            fetch_history=False  # Skip history for speed
        )
        
        for flip in flips:
            item_id = flip['id']
            
            # Analyze trend
            trend_analysis = self.analyze_flipping_trend(item_id)
            
            # Only alert if there's significant movement or risk
            if trend_analysis['status'] != 'stable':
                alerts.append({
                    'name': flip['name'],
                    'item_id': item_id,
                    'buy_price': flip['buy_price'],
                    'sell_price': flip['sell_price'],
                    'margin': flip['margin'],
                    'status': trend_analysis['status'],
                    'price_change_percent': trend_analysis['price_change_percent'],
                    'high_volume': trend_analysis['high_volume'],
                    'low_volume': trend_analysis['low_volume'],
                    'recommendation': trend_analysis['recommendation']
                })
        
        # Sort by price change magnitude (biggest moves first)
        alerts.sort(key=lambda x: abs(x['price_change_percent']), reverse=True)
        
        return alerts

# Example usage with enhanced filtering
if __name__ == "__main__":
    calculator = OSRSAlchemyFlippingCalculator()
   
    # Example 1: Enhanced flipping analysis with trend alerts
    print("=" * 70)
    print("ENHANCED FLIPPING ANALYSIS WITH TREND ALERTS")
    print("=" * 70)
   
    calculator.run_flipping_analysis(
        limit=15,
        min_margin=1000,
        min_volume=50,
        members_only=None,
        max_buy_price=20000000,
        max_margin_percent=15.0,
        exclude_high_risk=True,
        min_score=40,
        save_csv=True,
        fetch_history=True,
        use_averaged_prices=True,
        show_alerts=True,           # NEW: Enable trend alerts
        alert_min_margin=1000,      # NEW: Alert threshold
        alert_min_volume=20         # NEW: Alert volume threshold
    )
   
    time.sleep(2)
   
    # Example 2: Enhanced alchemy analysis with crash detection
    print("\n" + "=" * 70)
    print("ENHANCED ALCHEMY ANALYSIS WITH CRASH DETECTION")
    print("=" * 70)
   
    calculator.run_alchemy_analysis(
        min_profit=200,             # Your existing parameters
        max_items=100,
        members_only=None,
        save_csv=True,
        max_buy_price=10000000,
        min_limit=None,
        min_volume=20,
        max_roi=None,
        show_non_alchemizable_sample=False,
        show_crash_alerts=True,     # NEW: Enable crash alerts
        alert_min_profit=100,       # NEW: Alert threshold
        alert_min_imbalance=2.0     # NEW: Volume imbalance threshold
    )