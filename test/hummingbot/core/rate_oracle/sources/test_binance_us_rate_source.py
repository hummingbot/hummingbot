import asyncio
import json
import unittest
from decimal import Decimal
from typing import Awaitable

from aioresponses import aioresponses

from hummingbot.connector.exchange.binance import binance_constants as CONSTANTS, binance_web_utils as web_utils
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.binance_us_rate_source import BinanceUSRateSource


class BinanceUSRateSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.target_token = "COINALPHA"
        cls.binance_us_pair = f"{cls.target_token}USD"
        cls.us_trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote="USD")
        cls.binance_ignored_pair = "SOMEPAIR"
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def setup_binance_us_responses(self, mock_api, expected_rate: Decimal):
        pairs_us_url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain="us")
        symbols_response = {  # truncated
            "symbols": [
                {
                    "symbol": self.binance_us_pair,
                    "status": "TRADING",
                    "baseAsset": self.target_token,
                    "quoteAsset": "USD",
                    "permissionSets": [[
                        "SPOT",
                    ]],
                },
                {
                    "symbol": self.binance_ignored_pair,
                    "status": "PAUSED",
                    "baseAsset": "SOME",
                    "quoteAsset": "PAIR",
                    "permissionSets": [[
                        "SPOT",
                    ]],
                },
            ]
        }
        binance_prices_us_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_BOOK_PATH_URL, domain="us")
        binance_prices_us_response = [
            {
                "symbol": self.binance_us_pair,
                "bidPrice": str(expected_rate - Decimal("0.1")),
                "bidQty": "0.50000000",
                "askPrice": str(expected_rate + Decimal("0.1")),
                "askQty": "0.14500000",
            },
            {
                "symbol": self.binance_ignored_pair,
                "bidPrice": "0",
                "bidQty": "0",
                "askPrice": "0",
                "askQty": "0",
            }
        ]
        mock_api.get(pairs_us_url, body=json.dumps(symbols_response))
        mock_api.get(binance_prices_us_url, body=json.dumps(binance_prices_us_response))

    @aioresponses()
    def test_get_binance_prices(self, mock_api):
        expected_rate = Decimal("10")
        self.setup_binance_us_responses(mock_api=mock_api, expected_rate=expected_rate)

        rate_source = BinanceUSRateSource()
        prices = self.async_run_with_timeout(rate_source.get_prices())

        self.assertIn(self.us_trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.us_trading_pair])
        self.assertNotIn(self.ignored_trading_pair, prices)
