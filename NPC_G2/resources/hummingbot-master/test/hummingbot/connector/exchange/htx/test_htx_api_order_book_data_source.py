import asyncio
import gzip
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import aiohttp
import ujson
from aioresponses.core import aioresponses

import hummingbot.connector.exchange.htx.htx_constants as CONSTANTS
from hummingbot.connector.exchange.htx.htx_api_order_book_data_source import HtxAPIOrderBookDataSource
from hummingbot.connector.exchange.htx.htx_web_utils import build_api_factory
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook


class HtxAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}".lower()

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []
        self.connector = AsyncMock()
        self.connector.exchange_symbol_associated_to_pair.return_value = self.ex_trading_pair
        self.connector.trading_pair_associated_to_exchange_symbol.return_value = self.trading_pair
        self.data_source = HtxAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=build_api_factory()
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)
        self.resume_test_event = asyncio.Event()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _compress(self, message: Dict[str, Any]) -> bytes:
        return gzip.compress(json.dumps(message).encode())

    def _successfully_subscribed_event(self):
        snapshot_resp = {
            "id": self.ex_trading_pair,
            "status": "ok",
            "subbed": f"market.{self.ex_trading_pair}.depth.step0",
            "ts": 1637333566824,
        }

        trade_resp = {
            "id": self.ex_trading_pair,
            "status": "ok",
            "subbed": f"market.{self.ex_trading_pair}.trade.detail",
            "ts": 1637333566737,
        }

        return trade_resp, snapshot_resp

    def _trade_update_event(self):
        resp = {
            "ch": f"market.{self.ex_trading_pair}.trade.detail",
            "ts": 1630994963175,
            "tick": {
                "id": 137005445109,
                "ts": 1630994963173,
                "data": [
                    {
                        "id": 137005445109359286410323766,
                        "ts": 1630994963173,
                        "tradeId": 102523573486,
                        "amount": 0.006754,
                        "price": 52648.62,
                        "direction": "buy",
                    }
                ],
            },
        }
        return resp

    def _snapshot_response(self):
        resp = {
            "ch": f"market.{self.ex_trading_pair}.depth.step0",
            "ts": 1637255180894,
            "tick": {
                "bids": [
                    [57069.57, 0.05],
                ],
                "asks": [
                    [57057.73, 0.007019],
                ],
                "version": 141982962388,
                "ts": 1637255180700,
            },
        }
        return resp

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api):
        url = CONSTANTS.REST_URL + CONSTANTS.DEPTH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = self._snapshot_response()

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = await self.data_source.get_new_order_book(self.trading_pair)

        self.assertIsInstance(result, OrderBook)
        self.assertEqual(1637255180700, result.snapshot_uid)
        self.assertEqual(1, len(list(result.bid_entries())))
        self.assertEqual(1, len(list(result.ask_entries())))
        self.assertEqual(57069.57, list(result.bid_entries())[0].price)
        self.assertEqual(0.05, list(result.bid_entries())[0].amount)
        self.assertEqual(57057.73, list(result.ask_entries())[0].price)
        self.assertEqual(0.007019, list(result.ask_entries())[0].amount)

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api):
        url = CONSTANTS.REST_URL + CONSTANTS.DEPTH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_when_subscribing_raised_cancelled(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.htx.htx_api_order_book_data_source.HtxAPIOrderBookDataSource._sleep")
    async def test_listen_for_subscriptions_raises_logs_exception(self, sleep_mock, ws_connect_mock):
        sleep_mock.side_effect = lambda *_: (
            # Allows listen_for_subscriptions to yield control over thread
            self.local_event_loop.run_until_complete(asyncio.sleep(0.0))
        )
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = lambda *_: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR")
        )
        self.async_tasks.append(self.local_event_loop.create_task(self.data_source.listen_for_subscriptions()))

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_successful_subbed(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        subbed_message_snapshot = self._successfully_subscribed_event()[1]
        subbed_message_trade = self._successfully_subscribed_event()[0]

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            message=self._compress(subbed_message_snapshot),
            message_type=aiohttp.WSMsgType.BINARY,
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            message=self._compress(subbed_message_trade),
            message_type=aiohttp.WSMsgType.BINARY,
        )

        self.async_tasks.append(self.local_event_loop.create_task(self.data_source.listen_for_subscriptions()))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, self.data_source._message_queue[CONSTANTS.TRADE_CHANNEL_SUFFIX].qsize())
        self.assertEqual(0, self.data_source._message_queue[CONSTANTS.ORDERBOOK_CHANNEL_SUFFIX].qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_successfully_append_trade_and_orderbook_messages(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        trade_message = self._trade_update_event()
        orderbook_message = self._snapshot_response()

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=self._compress(trade_message), message_type=aiohttp.WSMsgType.BINARY
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            message=self._compress(orderbook_message),
            message_type=aiohttp.WSMsgType.BINARY,
        )

        self.async_tasks.append(self.local_event_loop.create_task(self.data_source.listen_for_subscriptions()))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, self.data_source._message_queue[CONSTANTS.TRADE_CHANNEL_SUFFIX].qsize())
        self.assertEqual(1, self.data_source._message_queue[CONSTANTS.ORDERBOOK_CHANNEL_SUFFIX].qsize())

    async def test_listen_for_trades_logs_exception(self):

        trade_message = {"ch": f"market.{self.ex_trading_pair}.trade.detail", "err": "INCOMPLETE MESSAGE"}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [trade_message, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_CHANNEL_SUFFIX] = mock_queue
        msg_queue = asyncio.Queue()
        try:
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass
        self.assertTrue(self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    async def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_CHANNEL_SUFFIX] = mock_queue
        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_trades(self.local_event_loop, msg_queue))

        msg = await msg_queue.get()

        self.assertEqual(137005445109359286410323766, msg.trade_id)

    async def test_listen_for_order_book_diffs_logs_exception(self):

        orderbook_message = {"ch": f"market.{self.ex_trading_pair}.depth.step0", "err": "INCOMPLETE MESSAGE"}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [orderbook_message, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.ORDERBOOK_CHANNEL_SUFFIX] = mock_queue
        msg_queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error when processing public order book updates from exchange"))

    async def test_listen_for_order_book_diffs_successful(self):
        orderbook_message = self._snapshot_response()
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [orderbook_message, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.ORDERBOOK_CHANNEL_SUFFIX] = mock_queue
        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        )

        msg = await msg_queue.get()

        self.assertEqual(1637255180700, msg.update_id)
