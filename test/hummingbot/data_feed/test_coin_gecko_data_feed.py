import asyncio
import json
import re
import unittest
from typing import Awaitable, Optional
from unittest.mock import MagicMock, patch

from aioresponses import aioresponses

from hummingbot.data_feed.coin_gecko_data_feed import CoinGeckoDataFeed, coin_gecko_constants as CONSTANTS
from hummingbot.data_feed.coin_gecko_data_feed.coin_gecko_constants import DEMO, PRO, PUBLIC


class CoinGeckoDataFeedTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = CoinGeckoDataFeed()
        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message for
            record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_coin_markets_data_mock(self, btc_price: float, eth_price: float):
        data = [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png?1547033579",
                "current_price": btc_price,
                "market_cap": 451469235435,
                "market_cap_rank": 1,
                "fully_diluted_valuation": 496425271642,
                "total_volume": 50599610665,
                "high_24h": 23655,
                "low_24h": 21746,
                "price_change_24h": 1640.38,
                "price_change_percentage_24h": 7.45665,
                "market_cap_change_24h": 31187048611,
                "market_cap_change_percentage_24h": 7.4205,
                "circulating_supply": 19098250,
                "total_supply": 21000000,
                "max_supply": 21000000,
                "ath": 69045,
                "ath_change_percentage": -65.90618,
                "ath_date": "2021-11-10T14:24:11.849Z",
                "atl": 67.81,
                "atl_change_percentage": 34615.15839,
                "atl_date": "2013-07-06T00:00:00.000Z",
                "roi": None,
                "last_updated": "2022-07-20T06:30:40.123Z"
            },
            {
                "id": "ethereum",
                "symbol": "eth",
                "name": "Ethereum",
                "image": "https://assets.coingecko.com/coins/images/279/large/ethereum.png?1595348880",
                "current_price": eth_price,
                "market_cap": 188408028152,
                "market_cap_rank": 2,
                "fully_diluted_valuation": None,
                "total_volume": 22416922274,
                "high_24h": 1585.84,
                "low_24h": 1510.73,
                "price_change_24h": 43.63,
                "price_change_percentage_24h": 2.85217,
                "market_cap_change_24h": 5243861455,
                "market_cap_change_percentage_24h": 2.86293,
                "circulating_supply": 119749448.206629,
                "total_supply": 119748879.331629,
                "max_supply": None,
                "ath": 4878.26,
                "ath_change_percentage": -67.76359,
                "ath_date": "2021-11-10T14:24:19.604Z",
                "atl": 0.432979,
                "atl_change_percentage": 363099.28971,
                "atl_date": "2015-10-20T00:00:00.000Z",
                "roi": {
                    "times": 88.0543596997439,
                    "currency": "btc",
                    "percentage": 8805.435969974389
                },
                "last_updated": "2022-07-20T06:30:15.395Z"
            },
        ]
        return data

    def _verify_api_auth_headers(self, mock_api: aioresponses, url: str, expected_header: Optional[str] = None,
                                 expected_key: Optional[str] = None):
        """Helper to verify auth headers in requests"""
        found_request = False
        for req_key, req_data in mock_api.requests.items():
            req_method, req_url = req_key
            if str(req_url) == url and req_method == 'GET':
                found_request = True
                request_headers = req_data[0].kwargs.get('headers', {})
                if expected_header:
                    self.assertIn(expected_header, request_headers)
                    self.assertEqual(expected_key, request_headers[expected_header])
                else:
                    # Verify no auth headers are present
                    self.assertNotIn(DEMO.header, request_headers)
                    self.assertNotIn(PRO.header, request_headers)
                break
        self.assertTrue(found_request, f"No request found for URL: {url}")

    @aioresponses()
    def test_get_supported_vs_tokens(self, mock_api: aioresponses):
        url = f"{PUBLIC.base_url}{CONSTANTS.SUPPORTED_VS_TOKENS_REST_ENDPOINT}"
        data = ["btc", "eth"]
        mock_api.get(url=url, body=json.dumps(data))

        resp = self.async_run_with_timeout(self.data_feed.get_supported_vs_tokens())

        self.assertEqual(data, resp)

    @aioresponses()
    def test_get_prices_by_page(self, mock_api: aioresponses):
        vs_currency = "USD"
        page_no = 0
        category = "coin"
        url = (
            f"{PUBLIC.base_url}{CONSTANTS.PRICES_REST_ENDPOINT}"
            f"?category={category}&order=market_cap_desc&page={page_no}"
            f"&per_page=250&sparkline=false&vs_currency={vs_currency}"
        )
        data = self.get_coin_markets_data_mock(btc_price=1, eth_price=2)
        mock_api.get(url=url, body=json.dumps(data))

        resp = self.async_run_with_timeout(
            self.data_feed.get_prices_by_page(vs_currency=vs_currency, page_no=page_no, category=category)
        )

        self.assertEqual(data, resp)

    @aioresponses()
    def test_get_prices_by_token_id(self, mock_api: aioresponses):
        vs_currency = "USD"
        token_ids = ["ETH", "BTC"]
        token_ids_str = ",".join(map(str.lower, token_ids))
        url = (
            f"{PUBLIC.base_url}{CONSTANTS.PRICES_REST_ENDPOINT}"
            f"?ids={token_ids_str}&vs_currency={vs_currency}"
        )
        data = self.get_coin_markets_data_mock(btc_price=1, eth_price=2)
        mock_api.get(url=url, body=json.dumps(data))

        resp = self.async_run_with_timeout(
            self.data_feed.get_prices_by_token_id(vs_currency=vs_currency, token_ids=token_ids)
        )

        self.assertEqual(data, resp)

    @aioresponses()
    def test_execute_request_with_demo_api_key(self, mock_api: aioresponses):
        """Test that _execute_request adds DEMO authentication headers when API key is provided"""
        demo_key = "demo_api_key"
        demo_data_feed = CoinGeckoDataFeed(api_key=demo_key, api_tier=CONSTANTS.CoinGeckoAPITier.DEMO)
        url = f"{DEMO.base_url}{CONSTANTS.SUPPORTED_VS_TOKENS_REST_ENDPOINT}"
        data = ["btc", "eth"]

        mock_api.get(url, body=json.dumps(data))

        self.async_run_with_timeout(demo_data_feed.get_supported_vs_tokens())

        self._verify_api_auth_headers(mock_api, url, DEMO.header, demo_key)

    @aioresponses()
    def test_execute_request_with_pro_api_key(self, mock_api: aioresponses):
        """Test that _execute_request adds PRO authentication headers when API key is provided"""
        pro_key = "pro_api_key"
        pro_data_feed = CoinGeckoDataFeed(api_key=pro_key, api_tier=CONSTANTS.CoinGeckoAPITier.PRO)
        url = f"{PRO.base_url}{CONSTANTS.SUPPORTED_VS_TOKENS_REST_ENDPOINT}"
        data = ["btc", "eth"]

        mock_api.get(url, body=json.dumps(data))

        self.async_run_with_timeout(pro_data_feed.get_supported_vs_tokens())

        self._verify_api_auth_headers(mock_api, url, PRO.header, pro_key)

    @aioresponses()
    def test_execute_request_with_no_api_key(self, mock_api: aioresponses):
        """Test that _execute_request does not add authentication headers when no API key is provided"""
        public_data_feed = CoinGeckoDataFeed()
        url = f"{PUBLIC.base_url}{CONSTANTS.SUPPORTED_VS_TOKENS_REST_ENDPOINT}"
        data = ["btc", "eth"]

        mock_api.get(url, body=json.dumps(data))

        self.async_run_with_timeout(public_data_feed.get_supported_vs_tokens())

        found_request = False
        for req_key, req_data in mock_api.requests.items():
            req_method, req_url = req_key
            if str(req_url) == url and req_method == 'GET':
                found_request = True
                request_headers = req_data[0].kwargs.get('headers', {})
                self.assertNotIn(DEMO.header, request_headers)
                self.assertNotIn(PRO.header, request_headers)
                break
        self.assertTrue(found_request, f"No request found for URL: {url}")

    @aioresponses()
    @patch(
        "hummingbot.data_feed.coin_gecko_data_feed.coin_gecko_data_feed.CoinGeckoDataFeed._async_sleep",
        new_callable=MagicMock,
    )
    def test_fetch_data_loop(self, mock_api: aioresponses, sleep_mock: MagicMock):
        sleep_continue_event = asyncio.Event()

        async def wait_on_sleep_event():
            sleep_continue_event.clear()
            await sleep_continue_event.wait()

        sleep_mock.return_value = wait_on_sleep_event()

        prices_requested_event = asyncio.Event()
        url = f"{PUBLIC.base_url}{CONSTANTS.PRICES_REST_ENDPOINT}"
        regex_url = re.compile(f"^{url}")
        data = self.get_coin_markets_data_mock(btc_price=1, eth_price=2)
        first_page = data[:1]
        second_page = data[1:]

        self.assertEqual({}, self.data_feed.price_dict)
        self.data_feed._price_dict["SOMECOIN"] = 10

        mock_api.get(
            url=regex_url, body=json.dumps(first_page), callback=lambda *_, **__: prices_requested_event.set()
        )
        self.async_run_with_timeout(self.data_feed.start_network())
        self.async_run_with_timeout(prices_requested_event.wait())
        prices_dict = self.data_feed.price_dict

        self.assertIn("BTC", prices_dict)
        self.assertEqual(1, prices_dict["BTC"])
        self.assertIn("SOMECOIN", prices_dict)
        self.assertNotIn("ETH", prices_dict)
        self.assertFalse(self.data_feed.ready)

        prices_requested_event.clear()
        mock_api.get(url=regex_url, body=json.dumps(second_page), callback=lambda *_, **__: prices_requested_event.set())
        sleep_continue_event.set()
        sleep_mock.return_value = wait_on_sleep_event()
        self.async_run_with_timeout(prices_requested_event.wait())
        prices_dict = self.data_feed.price_dict

        self.assertIn("BTC", prices_dict)
        self.assertEqual(1, prices_dict["BTC"])
        self.assertIn("SOMECOIN", prices_dict)
        self.assertIn("ETH", prices_dict)
        self.assertEqual(2, prices_dict["ETH"])
        self.assertFalse(self.data_feed.ready)

        mock_api.get(
            url=regex_url, body=json.dumps([]), callback=lambda *_, **__: prices_requested_event.set(), repeat=True
        )
        for i in range(2):
            prices_requested_event.clear()
            sleep_continue_event.set()
            sleep_mock.return_value = wait_on_sleep_event()
            self.async_run_with_timeout(prices_requested_event.wait())
        prices_dict = self.data_feed.price_dict

        self.assertIn("BTC", prices_dict)
        self.assertEqual(1, prices_dict["BTC"])
        self.assertNotIn("SOMECOIN", prices_dict)  # the dict has been fully updated
        self.assertIn("ETH", prices_dict)
        self.assertEqual(2, prices_dict["ETH"])
        self.assertTrue(self.data_feed.ready)

    @aioresponses()
    @patch(
        "hummingbot.data_feed.coin_gecko_data_feed.coin_gecko_data_feed.CoinGeckoDataFeed._async_sleep",
        new_callable=MagicMock,
    )
    def test_update_asset_prices_error_handling(self, mock_api: aioresponses, sleep_mock: MagicMock):
        """Test error handling in _update_asset_prices method"""
        # Configure sleep_mock to return a proper awaitable
        async def mock_sleep(*args, **kwargs):
            return None
        sleep_mock.side_effect = mock_sleep

        # Set up URLs for testing
        base_url = f"{PUBLIC.base_url}{CONSTANTS.PRICES_REST_ENDPOINT}"

        # First test case: API error response
        error_url = f"{base_url}?vs_currency=usd&order=market_cap_desc&per_page=250&page=1&sparkline=false"
        mock_api.get(error_url, body=json.dumps({"error": "API rate limit exceeded"}))

        # Should raise the error with the API message
        with self.assertRaises(Exception) as context:
            self.async_run_with_timeout(self.data_feed._update_asset_prices())
        self.assertEqual(str(context.exception), "API rate limit exceeded")
        self.assertTrue(self.is_logged(log_level="WARNING",
                                       message="Coin Gecko API request failed. Exception: API rate limit exceeded"))

        # Reset for second test case
        self.log_records.clear()
        mock_api.clear()

        # Second test case: null current_price handling
        # Mock all 4 pages needed by the method
        for page in range(1, 5):
            url = f"{base_url}?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}&sparkline=false"
            data = [{"symbol": "btc", "current_price": None}] if page == 1 else []
            mock_api.get(url, body=json.dumps(data))

        # Process null price value (should set to 0.0)
        self.async_run_with_timeout(self.data_feed._update_asset_prices())
        self.assertIn("BTC", self.data_feed.price_dict)
        self.assertEqual(0.0, self.data_feed.price_dict["BTC"])
