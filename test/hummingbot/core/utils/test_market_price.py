import asyncio
import re
import unittest

from decimal import Decimal
from typing import Any, Awaitable, Dict, List

import ujson
from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
import hummingbot.connector.exchange.binance.binance_utils as utils
import hummingbot.core.utils.market_price as market_price

from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource


class MarketPriceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.binance_ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def tearDown(self) -> None:
        BinanceAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_get_binance_mid_price(self, mock_api):
        BinanceAPIOrderBookDataSource._trading_pair_symbol_map = {
            "com": bidict(
                {f"{self.base_asset}{self.quote_asset}": self.trading_pair})
        }

        url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: List[Dict[str, Any]] = [
            {
                # Truncated Response
                "symbol": self.binance_ex_trading_pair,
                "bidPrice": "1.0",
                "askPrice": "2.0",
            },
        ]
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(market_price.get_binance_mid_price(trading_pair=self.trading_pair))

        self.assertEqual(result, Decimal("1.5"))

    @aioresponses()
    def test_get_last_price(self, mock_api):
        BinanceAPIOrderBookDataSource._trading_pair_symbol_map = {
            "com": bidict(
                {f"{self.binance_ex_trading_pair}": self.trading_pair})
        }

        url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Dict[str, Any] = {
            # truncated response
            "symbol": self.binance_ex_trading_pair,
            "lastPrice": "1",
        }
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(market_price.get_last_price(exchange="binance",
                                                                         trading_pair=self.trading_pair))

        self.assertEqual(result, Decimal("1.0"))
