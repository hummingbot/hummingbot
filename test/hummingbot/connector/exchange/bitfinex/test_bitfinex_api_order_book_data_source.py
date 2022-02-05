import asyncio
import json
from unittest import TestCase

from aioresponses import aioresponses

import hummingbot.connector.exchange.bitfinex.bitfinex_utils as utils
from hummingbot.connector.exchange.bitfinex import BITFINEX_REST_URL
from hummingbot.connector.exchange.bitfinex.bitfinex_api_order_book_data_source import BitfinexAPIOrderBookDataSource


class BitfinexAPIOrderBookDataSourceTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        BitfinexAPIOrderBookDataSource.logger().setLevel(1)
        BitfinexAPIOrderBookDataSource.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    @aioresponses()
    def test_get_last_traded_price(self, api_mock):
        response = [
            10645,
            73.93854271,
            10647,
            75.22266119,
            731.60645389,
            0.0738,
            10644.00645389,
            14480.89849423,
            10766,
            9889.1449809]
        api_mock.get(f"{BITFINEX_REST_URL}/ticker/{utils.convert_to_exchange_trading_pair('BTC-USDT')}",
                     body=json.dumps(response))
        last_price = asyncio.get_event_loop().run_until_complete(
            BitfinexAPIOrderBookDataSource.get_last_traded_price("BTC-USDT"))

        self.assertEqual(response[6], last_price)

    @aioresponses()
    def test_get_last_traded_price_returns_zero_when_an_error_happens(self, api_mock):
        response = {"error": "ERR_RATE_LIMIT"}
        api_mock.get(f"{BITFINEX_REST_URL}/ticker/{utils.convert_to_exchange_trading_pair('BTC-USDT')}",
                     body=json.dumps(response))
        last_price = asyncio.get_event_loop().run_until_complete(
            BitfinexAPIOrderBookDataSource.get_last_traded_price("BTC-USDT"))

        self.assertEqual(0, last_price)
        self.assertTrue(self._is_logged(
            "ERROR",
            f"Error encountered requesting ticker information. The response was: {response} "
            f"(There was an error requesting ticker information BTC-USDT ({response}))"
        ))
