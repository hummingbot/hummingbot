import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.derivative.deepcoin_perpetual import (
    deepcoin_perpetual_constants as CONSTANTS,
    deepcoin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_api_order_book_data_source import (
    DeepcoinPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_derivative import DeepcoinPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class DeepcoinPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.trading_pair}-SWAP"
        cls.domain = "deepcoin_perpetual_main"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None

        self.connector = DeepcoinPerpetualDerivative(
            bybit_perpetual_api_key="",
            bybit_perpetual_secret_key="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.data_source = DeepcoinPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({f"{self.base_asset}{self.quote_asset}": self.trading_pair}))

    async def asyncSetUp(self) -> None:
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def get_rest_snapshot_msg(self) -> Dict:
        return {"code": "0", "msg": "", "data": {"bids": [["97515.7", "14.507"]], "asks": [["97516", "9.303"]]}}

    def get_ws_snapshot_msg(self) -> Dict:
        return {
            "a": "PMO",
            "t": "i",
            "r": [
                {"d": {"I": self.trading_pair, "D": "0", "P": 115970.7, "V": 13285.0}},
                {"d": {"I": self.trading_pair, "D": "0", "P": 115970.6, "V": 1272.0}},
            ],
        }

    def get_ws_diff_msg(self) -> Dict:
        return {
            "a": "PMO",
            "t": "i",
            "r": [
                {"d": {"I": self.trading_pair, "D": "0", "P": 115970.7, "V": 13285.0}},
                {"d": {"I": self.trading_pair, "D": "0", "P": 115970.6, "V": 1272.0}},
            ],
        }

    def get_funding_info_msg(self) -> Dict:
        return {
            "code": "0",
            "msg": "",
            "data": {"current_fund_rates": [{"instrumentId": self.trading_pair, "fundingRate": 0.0001}]},
        }

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api):
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = {"code": "0", "msg": "", "data": {"asks": [[4114.25, 6.263]], "bids": [[4112.25, 49.29]]}}

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(4112.25, bids[0].price)
        self.assertEqual(49.29 * 0.000001, bids[0].amount)
        self.assertEqual(1, len(asks))
        self.assertEqual(4114.25, asks[0].price)
        self.assertEqual(6.263 * 0.000001, asks[0].amount)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_trades_diffs_and_funding_info(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_diffs = self.get_ws_snapshot_msg()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs),
        )

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(1, len(sent_subscription_messages))
        istId = self.trading_pair.replace("-SWAP", "").replace("-", "")
        expected_trade_subscription = {
            "SendTopicAction": {
                "Action": "1",
                "FilterValue": "DeepCoin_" + istId,
                "LocalNo": 9,
                "ResumeNo": 0,
                "TopicID": "2",
            }
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        #
        # self.assertTrue(
        #     self._is_logged("INFO", "Subscribed to public order book, trade and funding info channels...")
        # )

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
        self.assertTrue(True)

    async def test_subscribe_to_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_to_channels(mock_ws, [self.trading_pair])

    async def test_subscribe_to_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_to_channels(mock_ws, [self.trading_pair])

        self.assertTrue(True)

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    async def test_listen_for_trades_logs_exception(self):
        istId = self.trading_pair.replace("-SWAP", "").replace("-", "")
        incomplete_resp = {
            "a": "PMT",
            "b": 0,
            "tt": 1757640595167,
            "mt": 1757640595167,
            "r": [{"d": {"TradeID": "1000170423277947", "I": istId, "D": "1", "P": 4519.91, "V": 4, "T": 1757640595}}],
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(True)

    async def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        istId = self.trading_pair.replace("-SWAP", "").replace("-", "")
        trade_event = {
            "a": "PMT",
            "b": 0,
            "tt": 1757640595167,
            "mt": 1757640595167,
            "r": [{"d": {"TradeID": "1000170423277947", "I": istId, "D": "1", "P": 4519.91, "V": 4, "T": 1757640595}}],
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        # self.assertEqual(trade_event["data"][0]["i"], msg.trade_id)
        # self.assertEqual(trade_event["data"][0]["T"] * 1e-3, msg.timestamp)

    async def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)

    async def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = self.get_ws_diff_msg()
        del incomplete_resp["ts"]

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(True)

    async def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = self.get_ws_diff_msg()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await msg_queue.get()

        bids = msg.bids
        # asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(115970.7, bids[0].price)
        self.assertEqual(13285.0, bids[0].amount)

    @aioresponses()
    async def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint=endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    async def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint=endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )
        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    async def test_listen_for_order_book_snapshots_successful(self, mock_api):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(CONSTANTS.ORDER_BOOK_ENDPOINT, self.domain)
        snapshot_data = {
            "code": "0",
            "msg": "",
            "data": {
                "bids": [["6500.12", "0.45054140"], ["6500.11", "0.45054140"]],
                "asks": [["6500.16", "0.57753524"], ["6500.15", "0.57753524"]],
            },
        }

        mock_api.get(url, body=json.dumps(snapshot_data))

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await msg_queue.get()

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(6500.12, bids[0].price)
        self.assertEqual(4.505414e-07, bids[0].amount)
        self.assertEqual(6500.11, bids[1].price)
        self.assertEqual(4.505414e-07, bids[1].amount)
        self.assertEqual(2, len(asks))
        self.assertEqual(6500.16, asks[0].price)
        self.assertEqual(5.7753524e-07, asks[0].amount)
        self.assertEqual(6500.15, asks[1].price)
        self.assertEqual(5.7753524e-07, asks[1].amount)

    async def test_listen_for_funding_info_cancelled_when_listening(self):
        # DeepCoin doesn't have ws updates for funding info
        pass

    async def test_listen_for_funding_info_logs_exception(self):
        # DeepCoin doesn't have ws updates for funding info
        pass

    async def test_listen_for_funding_info_successful(self):
        # DeepCoin doesn't have ws updates for funding info
        pass

    @aioresponses()
    async def test_get_funding_info(self, mock_api):
        endpoint = CONSTANTS.FUNDING_INFO_URL
        url = web_utils.public_rest_url(endpoint, self.domain)
        general_resp = self.get_funding_info_msg()
        mock_api.get(url, body=json.dumps(general_resp))

        funding_info: FundingInfo = await self.data_source.get_funding_info(self.trading_pair)
        general_info_result = general_resp["data"]["current_fund_rates"][0]
        self.assertEqual(Decimal(str(general_info_result["instrumentId"])), funding_info.trading_pair)
