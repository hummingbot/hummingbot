import asyncio
import json
import unittest
from decimal import Decimal
from typing import Awaitable

from aioresponses import aioresponses

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.gate_io_rate_source import GateIoRateSource


class GateIoRateSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.target_token = "COINALPHA"
        cls.global_token = "HBOT"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def setup_gate_io_responses(self, mock_api, expected_rate: Decimal):
        symbols_url = f"{CONSTANTS.REST_URL}/{CONSTANTS.SYMBOL_PATH_URL}"
        symbols_response = [
            {
                "id": self.trading_pair,
                "base": "COINALPHA",
                "quote": "HBOT",
                "fee": "0.2",
                "trade_status": "tradable",
            },
            {
                "id": self.ignored_trading_pair,
                "base": "SOME",
                "quote": "PAIR",
                "fee": "0.2",
                "trade_status": "non-tradable",
            },
            {
                "id": "FAKE_BTC",
                "base": "FAKE",
                "quote": "BTC",
                "fee": "0.2",
                "trade_status": "tradable",
            }
        ]
        mock_api.get(url=symbols_url, body=json.dumps(symbols_response))
        prices_url = f"{CONSTANTS.REST_URL}/{CONSTANTS.TICKER_PATH_URL}"
        prices_response = [
            {
                "currency_pair": self.trading_pair,
                "last": "0.49876",
                "high_24h": "0.52271",
                "low_24h": "0.48598",
                "base_volume": "122140",
                "quote_volume": "122140",
                "lowest_ask": str(expected_rate - Decimal("0.1")),
                "highest_bid": str(expected_rate + Decimal("0.1")),
                "change_percentage": "-2.05",
                "etf_net_value": "2.46316141",
                "etf_pre_net_value": "2.43201848",
                "etf_pre_timestamp": 1611244800,
                "etf_leverage": "2.2803019447281203"
            },
            {
                "currency_pair": "KCS_BTC",
                "last": "0.0001816",
                "high_24h": "0.00018315",
                "low_24h": "0.0001658",
                "base_volume": "14595.7",
                "quote_volume": "14595.7",
                "lowest_ask": "",
                "highest_bid": "",
                "etf_net_value": "2.46316141",
                "etf_pre_net_value": "2.43201848",
                "etf_pre_timestamp": 1611244800,
                "etf_leverage": "2.2803019447281203"
            },
            {
                "currency_pair": self.ignored_trading_pair,
                "last": "0.0001816",
                "high_24h": "0.00018315",
                "low_24h": "0.0001658",
                "base_volume": "14595.7",
                "quote_volume": "14595.7",
                "lowest_ask": str(expected_rate - Decimal("0.1")),
                "highest_bid": str(expected_rate + Decimal("0.1")),
                "etf_net_value": "2.46316141",
                "etf_pre_net_value": "2.43201848",
                "etf_pre_timestamp": 1611244800,
                "etf_leverage": "2.2803019447281203"
            },
        ]
        mock_api.get(url=prices_url, body=json.dumps(prices_response))

    @aioresponses()
    def test_get_prices(self, mock_api):
        expected_rate = Decimal("10")
        self.setup_gate_io_responses(mock_api=mock_api, expected_rate=expected_rate)

        rate_source = GateIoRateSource()
        prices = self.async_run_with_timeout(rate_source.get_prices())

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        self.assertNotIn(self.ignored_trading_pair, prices)
