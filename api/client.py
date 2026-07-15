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

        # HTTP cache for ETag and Last-Modified support
        self._cache: Dict[str, Dict] = {}

    def _get_with_cache(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """
        Perform GET request with HTTP caching support.

        Uses ETag/If-None-Match and Last-Modified/If-Modified-Since headers
        to avoid redundant data transfers when content hasn't changed.

        Args:
            url: The URL to fetch
            params: Optional query parameters

        Returns:
            Response object, or None if request fails
        """
        cache_key = url + str(params) if params else url
        headers = self.headers.copy()

        # Add conditional headers if we have cached data
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if 'etag' in cached:
                headers['If-None-Match'] = cached['etag']
            if 'last_modified' in cached:
                headers['If-Modified-Since'] = cached['last_modified']

        try:
            response = requests.get(url, headers=headers, params=params)

            # Handle 304 Not Modified - return cached response
            if response.status_code == 304:
                if cache_key in self._cache:
                    return self._cache[cache_key]['response']
                # Fallback if cache missing (shouldn't happen)
                response.raise_for_status()

            response.raise_for_status()

            # Store response and caching headers
            cache_entry = {'response': response}
            if 'ETag' in response.headers:
                cache_entry['etag'] = response.headers['ETag']
            if 'Last-Modified' in response.headers:
                cache_entry['last_modified'] = response.headers['Last-Modified']

            self._cache[cache_key] = cache_entry
            return response

        except requests.RequestException:
            return None

    def fetch_item_mapping(self) -> Optional[List[Dict]]:
        """
        Fetch item mapping data including high alchemy values.

        Returns:
            List of item dictionaries, or None if request fails
        """
        response = self._get_with_cache(self.mapping_url)
        if response:
            return response.json()
        return None

    def fetch_volume_data(self) -> Optional[Dict]:
        """
        Fetch volume data from 1-hour endpoint.

        Returns:
            Dictionary of volume data by item ID, or None if request fails
        """
        response = self._get_with_cache(self.hourly_prices_url)
        if response:
            return response.json().get('data', {})
        return None

    def fetch_current_prices(self) -> Optional[Dict]:
        """
        Fetch current Grand Exchange prices.

        Returns:
            Dictionary of price data by item ID, or None if request fails
        """
        response = self._get_with_cache(self.latest_prices_url)
        if response:
            return response.json().get('data', {})
        return None

    def fetch_five_minute_data(self) -> Optional[Dict]:
        """
        Fetch 5-minute price data for trend analysis.

        Returns:
            Dictionary of 5-minute price data by item ID, or None if request fails
        """
        response = self._get_with_cache(self.five_min_prices_url)
        if response:
            return response.json().get('data', {})
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
        params = {"id": item_id, "timestep": timestep}
        response = self._get_with_cache(self.timeseries_url, params=params)
        if response:
            return response.json().get("data", [])
        return []
