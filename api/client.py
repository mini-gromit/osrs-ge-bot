import requests
from typing import Dict, List, Optional


class OSRSAPIClient:
    """HTTP client for OSRS Wiki API - handles only API requests and data fetching."""

    def __init__(self, user_agent: str = None):
        self.base_url = "https://prices.runescape.wiki/api/v1/osrs"
        self.mapping_url = f"{self.base_url}/mapping"
        self.latest_prices_url = f"{self.base_url}/latest"
        self.hourly_prices_url = f"{self.base_url}/1h"
        self.five_min_prices_url = f"{self.base_url}/5m"
        self.timeseries_url = f"{self.base_url}/timeseries"

        if user_agent is None:
            user_agent = 'OSRS_Alchemy_Calculator - Educational/Personal Use - Python Script - @lovvu0173 on Discord.'

        self.headers = {'User-Agent': user_agent}

    def fetch_item_mapping(self) -> Optional[List[Dict]]:
        """
        Fetch item mapping data including high alchemy values.

        Returns:
            List of item dictionaries, or None if request fails
        """
        try:
            response = requests.get(self.mapping_url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None

    def fetch_volume_data(self) -> Optional[Dict]:
        """
        Fetch volume data from 1-hour endpoint.

        Returns:
            Dictionary of volume data by item ID, or None if request fails
        """
        try:
            response = requests.get(self.hourly_prices_url, headers=self.headers)
            response.raise_for_status()
            return response.json().get('data', {})
        except requests.RequestException:
            return None

    def fetch_current_prices(self) -> Optional[Dict]:
        """
        Fetch current Grand Exchange prices.

        Returns:
            Dictionary of price data by item ID, or None if request fails
        """
        try:
            response = requests.get(self.latest_prices_url, headers=self.headers)
            response.raise_for_status()
            return response.json().get('data', {})
        except requests.RequestException:
            return None

    def fetch_five_minute_data(self) -> Optional[Dict]:
        """
        Fetch 5-minute price data for trend analysis.

        Returns:
            Dictionary of 5-minute price data by item ID, or None if request fails
        """
        try:
            response = requests.get(self.five_min_prices_url, headers=self.headers)
            response.raise_for_status()
            return response.json().get('data', {})
        except requests.RequestException:
            return None

    def fetch_timeseries(self, item_id: int, timestep: str = "24h") -> List[Dict]:
        """
        Fetch historical price data for an item.

        Args:
            item_id: Item ID to fetch data for
            timestep: Time resolution (24h, 6h, 1h, 5m)

        Returns:
            List of price data points, empty list if request fails
        """
        try:
            params = {"id": item_id, "timestep": timestep}
            response = requests.get(self.timeseries_url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.RequestException:
            return []
