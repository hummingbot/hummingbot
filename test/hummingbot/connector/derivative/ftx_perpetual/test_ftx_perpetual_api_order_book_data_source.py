import asyncio
import json
import time
import unittest
from decimal import Decimal
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant
from typing import Any, Awaitable, Dict, List

import aiohttp
from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_api_order_book_data_source import (
    FtxPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book import OrderBook

FTX_REST_URL = "https://ftx.com/api"
FTX_EXCHANGE_INFO_PATH = "/markets"
FTX_WS_FEED = "wss://ftx.com/ws/"


class FtxPerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = "ftx_perpetual_testnet"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.data_source = FtxPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair]
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        FtxPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.ex_trading_pair: self.trading_pair})
        }

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        FtxPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def resume_test_callback(self, *_, **__):
        self.resume_test_event.set()
        return None

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _raise_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "last": "10.0",
                    "name": "COINALPHA-PERP"
                }
            ]
        }
        mock_api.get(url, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )
        self.assertTrue(self.trading_pair in result)
        self.assertEqual(10.0, result[self.trading_pair])

    @aioresponses()
    def test_get_snapshot_exception_raised(self, mock_api):
        url = f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}/COINALPHA-PERP/orderbook?depth=100"
        mock_api.get(url, status=400, body=json.dumps(["ERROR"]))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(
                self.data_source.get_snapshot(client=aiohttp.ClientSession(), trading_pair=self.trading_pair)
            )

        self.assertEqual(str(context.exception), f"Error fetching FTX market snapshot for {self.trading_pair}. HTTP status is 400.")

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}/COINALPHA-PERP/orderbook?depth=100"
        mock_response = {
            "result":
            {
                "bids": [["10", "1"]],
                "asks": [["11", "1"]],
            }
        }
        mock_api.get(url, status=200, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_snapshot(client=aiohttp.ClientSession(), trading_pair=self.trading_pair)
        )
        self.assertEqual(mock_response, result)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}/COINALPHA-PERP/orderbook?depth=100"
        mock_response = {
            "result":
            {
                "bids": [["10", "1"]],
                "asks": [["11", "1"]],
            }
        }
        mock_api.get(url, status=200, body=json.dumps(mock_response))
        result = self.async_run_with_timeout(self.data_source.get_new_order_book(trading_pair=self.trading_pair))

        self.assertIsInstance(result, OrderBook)
        self.assertTrue((time.time() - result.snapshot_uid) < 1)

    def test_listen_for_trades(self, ):
        trades_queue = asyncio.Queue()
        self.data_source = FtxPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-PERP"]
        )
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_trades(ev_loop=asyncio.get_event_loop(), output=trades_queue))

        # Add trade event message be processed

        # Lock the test to let the async task run
        first_trade = asyncio.get_event_loop().run_until_complete(trades_queue.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(first_trade.content['price'] > Decimal('0'))

    def test_listen_for_order_book_snapshot_event(self, ):
        order_book_messages = asyncio.Queue()
        self.data_source = FtxPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-PERP"]
        )
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_snapshots(ev_loop=asyncio.get_event_loop(), output=order_book_messages))

        # Lock the test to let the async task run
        order_book_message = asyncio.get_event_loop().run_until_complete(order_book_messages.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(order_book_message.asks[0].price > Decimal('0'))

    def test_listen_for_order_book_diff_event(self, ):
        order_book_messages = asyncio.Queue()
        self.data_source = FtxPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-PERP"]
        )
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=order_book_messages))

        # Lock the test to let the async task run
        order_book_message = asyncio.get_event_loop().run_until_complete(order_book_messages.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass
        if len(order_book_message.bids) > 0:
            price = order_book_message.bids[0].price
        else:
            price = order_book_message.asks[0].price

        self.assertTrue(price > Decimal('0'))

    def test_fetch_trading_pairs(self):
        task = asyncio.get_event_loop().create_task(
            self.data_source.fetch_trading_pairs())
        trading_pairs = asyncio.get_event_loop().run_until_complete(task)
        self.assertTrue(len(trading_pairs) > 0)

    def test_get_mid_prices(self):
        mid_price = self.data_source.get_mid_price("BTC-PERP")
        self.assertTrue(mid_price > Decimal('0'))
