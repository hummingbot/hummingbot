import asyncio
import json
from typing import Awaitable

from unittest import TestCase

from aioresponses import aioresponses

from hummingbot.connector.exchange.hitbtc.hitbtc_api_order_book_data_source import HitbtcAPIOrderBookDataSource
from hummingbot.connector.exchange.hitbtc.hitbtc_constants import Constants as CONSTANTS


class HitbtcAPIOrderBookDataSourceTests(TestCase):

    def tearDown(self) -> None:
        HitbtcAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_trading_pairs_initialization(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ENDPOINT['SYMBOL']}"
        resp = [
            {
                "id": "BTCUSD",
                "baseCurrency": "BTC",
                "quoteCurrency": "USD",
                "quantityIncrement": "0.001",
                "tickSize": "0.000001",
                "takeLiquidityRate": "0.001",
                "provideLiquidityRate": "-0.0001",
                "feeCurrency": "USDT"
            },
            {
                "id": "ETHBTC",
                "baseCurrency": "ETH",
                "quoteCurrency": "BTC",
                "quantityIncrement": "0.001",
                "tickSize": "0.000001",
                "takeLiquidityRate": "0.001",
                "provideLiquidityRate": "-0.0001",
                "feeCurrency": "BTC",
                "marginTrading": True,
                "maxInitialLeverage": "10.00"
            }
        ]
        mock_api.get(url, body=json.dumps(resp))

        map = self.async_run_with_timeout(HitbtcAPIOrderBookDataSource.trading_pair_symbol_map())

        self.assertIn("BTCUSD", map)
        self.assertEqual("BTC-USDT", map["BTCUSD"])
        self.assertIn("ETHBTC", map)
        self.assertEqual("ETH-BTC", map["ETHBTC"])

    def test_fetch_trading_pairs(self):
        HitbtcAPIOrderBookDataSource._trading_pair_symbol_map = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
        trading_pairs = self.async_run_with_timeout(HitbtcAPIOrderBookDataSource.fetch_trading_pairs())
        self.assertEqual(["BTC-USDT", "ETH-USDT"], trading_pairs)

    def test_exchange_symbol_associated_to_pair(self):
        HitbtcAPIOrderBookDataSource._trading_pair_symbol_map = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
        symbol = self.async_run_with_timeout(
            HitbtcAPIOrderBookDataSource.exchange_symbol_associated_to_pair("BTC-USDT"))
        self.assertEqual("BTCUSDT", symbol)

    def test_exchange_symbol_associated_to_pair_raises_error_when_pair_not_found(self):
        HitbtcAPIOrderBookDataSource._trading_pair_symbol_map = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
        with self.assertRaises(ValueError) as exception:
            self.async_run_with_timeout(
                HitbtcAPIOrderBookDataSource.exchange_symbol_associated_to_pair("NOT-VALID"))
            self.assertEqual("There is no symbol mapping for trading pair NOT-VALID", str(exception))

    def test_trading_pair_associated_to_exchange_symbol(self):
        HitbtcAPIOrderBookDataSource._trading_pair_symbol_map = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
        symbol = self.async_run_with_timeout(
            HitbtcAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol("BTCUSDT"))
        self.assertEqual("BTC-USDT", symbol)
