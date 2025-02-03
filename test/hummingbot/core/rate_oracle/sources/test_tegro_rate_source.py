import asyncio
import json
import unittest
from decimal import Decimal
from typing import Awaitable

from aioresponses import aioresponses

from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_web_utils as web_utils
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.tegro_rate_source import TegroRateSource


class TegroRateSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.target_token = "COINALPHA"
        cls.global_token = "USDC"
        cls.chain_id = "base"
        cls.domain = "tegro"  # noqa: mock
        cls.chain = 8453
        cls.tegro_api_key = "" # noqa: mock
        cls.tegro_pair = f"{cls.target_token}_{cls.global_token}"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.tegro_ignored_pair = "SOMEPAIR"
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def setup_tegro_responses(self, mock_api, expected_rate: Decimal):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain), domain=self.domain)
        pairs_url = f"{url}?page=1&sort_order=desc&sort_by=volume&page_size=20&verified=true"
        symbols_response = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.tegro_pair,
                "state": "verified",
                "base_symbol": "COINALPHA",
                "quote_symbol": "USDC",
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 10,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.ignored_trading_pair,
                "state": "verified",
                "base_symbol": "WETH",
                "quote_symbol": "USDC",
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 10,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
        ]

        urls = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain), domain=self.domain)
        tegro_prices_global_url = f"{urls}?page=1&sort_order=desc&sort_by=volume&page_size=20&verified=true"
        tegro_prices_global_response = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.tegro_pair,
                "state": "verified",
                "base_symbol": "COINALPHA",
                "quote_symbol": "USDC",
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 10,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.ignored_trading_pair,
                "state": "verified",
                "base_symbol": "WETH",
                "quote_symbol": "USDC",
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 10,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
        ]
        # mock_api.get(pairs_us_url, body=json.dumps(symbols_response))
        mock_api.get(pairs_url, body=json.dumps(symbols_response))
        # mock_api.post(tegro_prices_us_url, body=json.dumps(tegro_prices_us_response))
        mock_api.get(tegro_prices_global_url, body=json.dumps(tegro_prices_global_response))

    @aioresponses()
    def test_get_tegro_prices(self, mock_api):
        expected_rate = Decimal("10")
        self.setup_tegro_responses(mock_api=mock_api, expected_rate=expected_rate)

        rate_source = TegroRateSource()
        prices = self.async_run_with_timeout(rate_source.get_prices())

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        # self.assertIn(self.us_trading_pair, prices)
        self.assertNotIn(self.ignored_trading_pair, prices)
