import unittest
import asyncio
import ujson

import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS

from unittest.mock import patch, AsyncMock
from typing import (
    Any,
    Dict,
    List,
)

from hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source import NdaxAPIOrderBookDataSource

from hummingbot.connector.exchange.ndax.ndax_order_book_message import NdaxOrderBookEntry, NdaxOrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class NdaxAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.instrument_id = 1

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.listening_task = None

        self.data_source = NdaxAPIOrderBookDataSource([self.trading_pair])
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def simulate_trading_pair_ids_initialized(self):
        self.data_source._trading_pair_id_map.update({self.trading_pair: self.instrument_id})

    def set_mock_response(self, mock_api, status: int, json_data: Any):
        mock_api.return_value.__aenter__.return_value.status = status
        mock_api.return_value.__aenter__.return_value.json = AsyncMock(return_value=json_data)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    async def _get_next_received_message(self):
        return await self.ws_incoming_messages.get()

    def _create_ws_mock(self):
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: self.ws_sent_messages.append(sent_message)
        ws.recv.side_effect = self._get_next_received_message
        return ws

    def _add_subscribe_level_2_response(self):
        resp = {
            "m": 1,
            "i": 2,
            "n": "SubscribeLevel2",
            "o": "[[93617617, 1, 1626788175000, 0, 37800.0, 1, 37750.0, 1, 0.015, 0],[93617617, 1, 1626788175000, 0, 37800.0, 1, 37751.0, 1, 0.015, 1]]"
        }
        self.ws_incoming_messages.put_nowait(ujson.dumps(resp))
        return resp

    def _add_orderbook_update_event(self):
        resp = {
            "m": 3,
            "i": 3,
            "n": "Level2UpdateEvent",
            "o": "[[93617618, 1, 1626788175001, 0, 37800.0, 1, 37740.0, 1, 0.015, 0]]"
        }
        self.ws_incoming_messages.put_nowait(ujson.dumps(resp))
        return resp

    @patch("aiohttp.ClientSession.get")
    def test_init_trading_pair_ids(self, mock_api):

        mock_response: List[Any] = [{
            "Product1Symbol": self.base_asset,
            "Product2Symbol": self.quote_asset,
            "InstrumentId": self.instrument_id,
        }]

        self.set_mock_response(mock_api, 200, mock_response)

        self.ev_loop.run_until_complete(self.data_source.init_trading_pair_ids())
        self.assertEqual(1, self.data_source._trading_pair_id_map[self.trading_pair])

    @patch("aiohttp.ClientSession.get")
    def test_get_last_traded_prices(self, mock_api):

        self.simulate_trading_pair_ids_initialized()
        mock_response: Dict[Any] = {
            "LastTradedPx": 1.0
        }

        self.set_mock_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.get_last_traded_prices([self.trading_pair])))
        results: Dict[str, Any] = results[0]

        self.assertEqual(results[self.trading_pair], mock_response["LastTradedPx"])

    @patch("aiohttp.ClientSession.get")
    def test_fetch_trading_pairs(self, mock_api):

        self.simulate_trading_pair_ids_initialized()

        mock_response: List[Any] = [{
            "Product1Symbol": self.base_asset,
            "Product2Symbol": self.quote_asset,
        }]
        self.set_mock_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.fetch_trading_pairs()))
        result = results[0]
        self.assertTrue(self.trading_pair in result)

    @patch("aiohttp.ClientSession.get")
    def test_get_order_book_data(self, mock_api):
        self.simulate_trading_pair_ids_initialized()
        mock_response: List[List[Any]] = [
            # mdUpdateId, accountId, actionDateTime, actionType, lastTradePrice, orderId, price, productPairCode, quantity, side
            [93617617, 1, 1626788175416, 0, 37813.22, 1, 37750.6, 1, 0.014698, 0]
        ]
        self.set_mock_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.get_order_book_data(self.trading_pair)))
        result = results[0]

        self.assertTrue("data" in result)
        self.assertGreaterEqual(len(result["data"]), 0)
        self.assertEqual(NdaxOrderBookEntry(*mock_response[0]), result["data"][0])

    @patch("aiohttp.ClientSession.get")
    def test_get_new_order_book(self, mock_api):

        self.simulate_trading_pair_ids_initialized()

        mock_response: List[List[Any]] = [
            # mdUpdateId, accountId, actionDateTime, actionType, lastTradePrice, orderId, price, productPairCode, quantity, side
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37750.0, 1, 0.015, 0],
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37751.0, 1, 0.015, 1]
        ]
        self.set_mock_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.get_new_order_book(self.trading_pair)))
        result: OrderBook = results[0]

        self.assertTrue(type(result) == OrderBook)
        self.assertEqual(result.snapshot_uid, NdaxOrderBookEntry(*mock_response[0]).actionDateTime)

    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        mock_api.side_effect = asyncio.CancelledError
        self.simulate_trading_pair_ids_initialized()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 0)

    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_logs_exception_when_fetching_snapshot(self, mock_api):
        self.simulate_trading_pair_ids_initialized()

        mock_api.side_effect = Exception

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(asyncio.TimeoutError):
            self.listening_task = self.ev_loop.create_task(asyncio.wait_for(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue),
                2.0
            ))
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 0)
        self.assertTrue(self._is_logged("ERROR", "Unexpected error occured listening for orderbook snapshots. Retrying in 5 secs..."))

    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_successful(self, mock_api):
        mock_response: List[List[Any]] = [
            # mdUpdateId, accountId, actionDateTime, actionType, lastTradePrice, orderId, price, productPairCode, quantity, side
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37750.0, 1, 0.015, 0],
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37751.0, 1, 0.015, 1],
        ]
        self.set_mock_response(mock_api, 200, mock_response)
        self.simulate_trading_pair_ids_initialized()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(asyncio.TimeoutError):
            self.listening_task = self.ev_loop.create_task(asyncio.wait_for(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue),
                2.0
            ))
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 1)

        snapshot_msg: OrderBookMessage = msg_queue.get_nowait()
        self.assertEqual(snapshot_msg.update_id, NdaxOrderBookEntry(*mock_response[0]).actionDateTime)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_cancelled_when_subscribing(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self._create_ws_mock()
        mock_ws.return_value.send.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if CONSTANTS.WS_ORDER_BOOK_CHANNEL in sent_message
            else self.ws_sent_messages.append(sent_message)
        )

        self._add_subscribe_level_2_response()
        self._add_orderbook_update_event()

        self.simulate_trading_pair_ids_initialized()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_cancelled_when_listening(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self._create_ws_mock()
        mock_ws.return_value.recv.side_effect = lambda: (
            self._raise_exception(asyncio.CancelledError)
        )

        self.simulate_trading_pair_ids_initialized()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 0)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_successful(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self._create_ws_mock()

        self._add_subscribe_level_2_response()
        self._add_orderbook_update_event()

        self.simulate_trading_pair_ids_initialized()

        with self.assertRaises(asyncio.TimeoutError):
            self.listening_task = self.ev_loop.create_task(asyncio.wait_for(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue),
                2.0
            ))
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertGreater(msg_queue.qsize(), 0)
        first_msg: NdaxOrderBookMessage = msg_queue.get_nowait()
        self.assertTrue(first_msg.type == OrderBookMessageType.SNAPSHOT)
        second_msg: NdaxOrderBookMessage = msg_queue.get_nowait()
        self.assertTrue(second_msg.type == OrderBookMessageType.DIFF)
