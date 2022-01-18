import asyncio
import json
from typing import Awaitable

from unittest import TestCase

from aioresponses import aioresponses

from hummingbot.connector.exchange.beaxy.beaxy_api_order_book_data_source import BeaxyAPIOrderBookDataSource
from hummingbot.connector.exchange.beaxy.beaxy_constants import BeaxyConstants


class BeaxyAPIOrderBookDataSourceTests(TestCase):

    def tearDown(self) -> None:
        BeaxyAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_trading_pairs_initialization(self, mock_api):
        url = BeaxyConstants.PublicApi.SYMBOLS_URL
        resp = [
            {
                "symbol": "BTCUSDT",
                "name": "BTCUSDT",
                "minimumQuantity": 0.01,
                "maximumQuantity": 2509.41,
                "quantityIncrement": 1.0E-7,
                "quantityPrecision": 7,
                "tickSize": 1.0E-7,
                "baseCurrency": "BTC",
                "termCurrency": "USDT",
                "pricePrecision": 7,
                "buyerTakerCommissionProgressive": 0.25,
                "buyerMakerCommissionProgressive": 0.15,
                "sellerTakerCommissionProgressive": 0.25,
                "sellerMakerCommissionProgressive": 0.15,
                "type": "crypto",
                "suspendedForTrading": False},
            {
                "symbol": "ETHBTC",
                "name": "ETHBTC",
                "minimumQuantity": 50.0,
                "maximumQuantity": 2000000.0,
                "quantityIncrement": 0.001,
                "quantityPrecision": 0,
                "tickSize": 1.0E-8,
                "baseCurrency": "ETH",
                "termCurrency": "BTC",
                "pricePrecision": 8,
                "buyerTakerCommissionProgressive": 0.25,
                "buyerMakerCommissionProgressive": 0.15,
                "sellerTakerCommissionProgressive": 0.25,
                "sellerMakerCommissionProgressive": 0.15,
                "type": "crypto", "suspendedForTrading": False}
        ]

        mock_api.get(url, body=json.dumps(resp))

        map = self.async_run_with_timeout(BeaxyAPIOrderBookDataSource.trading_pair_symbol_map())

        self.assertIn("BTCUSDT", map)
        self.assertEqual("BTC-USDT", map["BTCUSDT"])
        self.assertIn("ETHBTC", map)
        self.assertEqual("ETH-BTC", map["ETHBTC"])

    def test_fetch_trading_pairs(self):
        BeaxyAPIOrderBookDataSource._trading_pair_symbol_map = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
        trading_pairs = self.async_run_with_timeout(BeaxyAPIOrderBookDataSource.fetch_trading_pairs())
        self.assertEqual(["BTC-USDT", "ETH-USDT"], trading_pairs)

    def test_exchange_symbol_associated_to_pair(self):
        BeaxyAPIOrderBookDataSource._trading_pair_symbol_map = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
        symbol = self.async_run_with_timeout(
            BeaxyAPIOrderBookDataSource.exchange_symbol_associated_to_pair("BTC-USDT"))
        self.assertEqual("BTCUSDT", symbol)

    def test_exchange_symbol_associated_to_pair_raises_error_when_pair_not_found(self):
        BeaxyAPIOrderBookDataSource._trading_pair_symbol_map = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
        with self.assertRaises(ValueError) as exception:
            self.async_run_with_timeout(
                BeaxyAPIOrderBookDataSource.exchange_symbol_associated_to_pair("NOT-VALID"))
            self.assertEqual("There is no symbol mapping for trading pair NOT-VALID", str(exception))

    def test_trading_pair_associated_to_exchange_symbol(self):
        BeaxyAPIOrderBookDataSource._trading_pair_symbol_map = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
        symbol = self.async_run_with_timeout(
            BeaxyAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol("BTCUSDT"))
        self.assertEqual("BTC-USDT", symbol)
