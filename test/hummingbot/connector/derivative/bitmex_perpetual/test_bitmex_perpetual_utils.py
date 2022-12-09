import asyncio
import json
import re
import unittest
from typing import Any, Dict, List

from aioresponses.core import aioresponses

import hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_utils as utils
import hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.bitmex_perpetual.constants as CONSTANTS


class BitmexPerpetualUtilsUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls._ev_loop = asyncio.get_event_loop()

    @aioresponses()
    def test_get_trading_pair_index_and_tick_size(self, mock_api):
        url = f"{CONSTANTS.PERPETUAL_BASE_URL}{CONSTANTS.EXCHANGE_INFO_URL}?count=500&start=0"
        mock_response: List[Dict[str, Any]] = [
            {
                "symbol": "COINALPHAHBOT",
                "tickSize": 5
            },
        ]
        mock_api.get(url, status=200, body=json.dumps(mock_response))
        id_tick = self._ev_loop.run_until_complete(utils.get_trading_pair_index_and_tick_size("COINALPHAHBOT"))
        self.assertEqual(id_tick.index, 0)
        self.assertEqual(id_tick.tick_size, 5)

    @aioresponses()
    def test_get_trading_pair_size_currency(self, mock_api):
        url = web_utils.rest_url(
            CONSTANTS.EXCHANGE_INFO_URL, domain="bitmex_perpetual"
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Dict[str, Any] = [
            {
                "symbol": "COINALPHAHBOT",
                "rootSymbol": "COINALPHA",
                "quoteCurrency": "HBOT",
                "settlCurrency": "HBOT",
                "lotSize": 1.0,
                "tickSize": 0.0001,
                "minProvideSize": 0.001,
                "maxOrderQty": 1000000,
                "underlyingToPositionMultiplier": 100,
                "positionCurrency": "COINALPHA"
            },
        ]
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        size_currency = self._ev_loop.run_until_complete(utils.get_trading_pair_size_currency("COINALPHAHBOT"))
        self.assertTrue(size_currency.is_base)
