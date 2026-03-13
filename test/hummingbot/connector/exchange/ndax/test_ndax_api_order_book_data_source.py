import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS, ndax_web_utils as web_utils
from hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source import NdaxAPIOrderBookDataSource
from hummingbot.connector.exchange.ndax.ndax_exchange import NdaxExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class NdaxAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.instrument_id = 1
        cls.domain = "ndax_main"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.connector = NdaxExchange(
            ndax_uid="",
            ndax_api_key="",
            ndax_secret_key="",
            ndax_account_name="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.data_source = NdaxAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.instrument_id: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.run_async_with_timeout(coroutine, timeout)
        return ret

    def _raise_exception(self, exception_class):
        raise exception_class

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _subscribe_level_2_response(self):
        resp = {
            "m": 1,
            "i": 2,
            "n": "SubscribeLevel2",
            "o": "[[93617617, 1, 1626788175000, 0, 37800.0, 1, 37750.0, 1, 0.015, 0],[93617617, 1, 1626788175000, 0, 37800.0, 1, 37751.0, 1, 0.015, 1]]"
        }
        return resp

    def _orderbook_update_event(self):
        resp = {
            "m": 3,
            "i": 3,
            "n": "Level2UpdateEvent",
            "o": "[[93617618, 1, 1626788175001, 0, 37800.0, 1, 37740.0, 1, 0.015, 0]]"
        }
        return resp

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _snapshot_response(self):
        resp = [
            # mdUpdateId, accountId, actionDateTime, actionType, lastTradePrice, orderId, price, productPairCode, quantity, side
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37750.0, 1, 0.015, 0],
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37751.0, 1, 0.015, 1]
        ]
        return resp

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self._snapshot_response()

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(37750.0, bids[0].price)
        self.assertEqual(0.015, bids[0].amount)
        self.assertEqual(1, len(asks))
        self.assertEqual(37751.0, asks[0].price)
        self.assertEqual(0.015, asks[0].amount)

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        result_subscribe_diffs = self._subscribe_level_2_response()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_diff_subscription = {'m': 0, 'i': 1, 'n': 'SubscribeLevel2', 'o': '{"OMSId":1,"InstrumentId":1,"Depth":200}'}
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[0])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = AsyncMock()
        mock_ws.send_request.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send_request.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.ORDER_TRADE_EVENT_ENDPOINT_NAME] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    async def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)

    async def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    async def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = self._orderbook_update_event()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.WS_ORDER_BOOK_L2_UPDATE_EVENT] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(self.trading_pair, msg.trading_pair)

    @aioresponses()
    async def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError, repeat=True)

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())

    @aioresponses()
    @patch("hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source"
           ".NdaxAPIOrderBookDataSource._sleep")
    async def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception, repeat=True)

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )
        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    async def test_listen_for_order_book_snapshots_successful(self, mock_api, ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(0, msg.update_id)
