import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, Dict
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.hyperliquid_perpetual import hyperliquid_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_api_order_book_data_source import (
    HyperliquidPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_derivative import (
    HyperliquidPerpetualDerivative,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class HyperliquidPerpetualAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = HyperliquidPerpetualDerivative(
            client_config_map,
            hyperliquid_perpetual_api_key="testkey",
            hyperliquid_perpetual_api_secret="13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930",# noqa: mock
            use_vault=False,
            trading_pairs=[self.trading_pair],
        )
        self.data_source = HyperliquidPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}-{self.quote_asset}-PERPETUAL": self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def resume_test_callback(self, *_, **__):
        self.resume_test_event.set()
        return None

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_rest_snapshot_msg(self) -> Dict:
        return {
            "coin": "DYDX", "levels": [
                [{'px': '2080.3', 'sz': '74.6923', 'n': 2}, {'px': '2080.0', 'sz': '162.2829', 'n': 2},
                 {'px': '1825.5', 'sz': '0.0259', 'n': 1}, {'px': '1823.6', 'sz': '0.0259', 'n': 1}],
                [{'px': '2080.5', 'sz': '73.018', 'n': 2}, {'px': '2080.6', 'sz': '74.6799', 'n': 2},
                 {'px': '2118.9', 'sz': '377.495', 'n': 1}, {'px': '2122.1', 'sz': '348.8644', 'n': 1}]],
            "time": 1700687397643
        }

    def get_ws_snapshot_msg(self) -> Dict:
        return {'channel': 'l2Book', 'data': {'coin': 'BTC', 'time': 1700687397641, 'levels': [
            [{'px': '2080.3', 'sz': '74.6923', 'n': 2}, {'px': '2080.0', 'sz': '162.2829', 'n': 2},
             {'px': '1825.5', 'sz': '0.0259', 'n': 1}, {'px': '1823.6', 'sz': '0.0259', 'n': 1}],
            [{'px': '2080.5', 'sz': '73.018', 'n': 2}, {'px': '2080.6', 'sz': '74.6799', 'n': 2},
             {'px': '2118.9', 'sz': '377.495', 'n': 1}, {'px': '2122.1', 'sz': '348.8644', 'n': 1}]]}}

    def get_ws_diff_msg(self) -> Dict:
        return {'channel': 'l2Book', 'data': {'coin': 'BTC', 'time': 1700687397642, 'levels': [
            [{'px': '2080.3', 'sz': '74.6923', 'n': 2}, {'px': '2080.0', 'sz': '162.2829', 'n': 2},
             {'px': '1825.5', 'sz': '0.0259', 'n': 1}, {'px': '1823.6', 'sz': '0.0259', 'n': 1}],
            [{'px': '2080.5', 'sz': '73.018', 'n': 2}, {'px': '2080.6', 'sz': '74.6799', 'n': 2},
             {'px': '2118.9', 'sz': '377.495', 'n': 1}, {'px': '2122.1', 'sz': '348.8644', 'n': 1}]]}}

    def get_ws_diff_msg_2(self) -> Dict:
        return {'channel': 'l2Book', 'data': {'coin': 'BTC', 'time': 1700687397642, 'levels': [
            [{'px': '2080.4', 'sz': '74.6923', 'n': 2}, {'px': '2080.0', 'sz': '162.2829', 'n': 2},
             {'px': '1825.5', 'sz': '0.0259', 'n': 1}, {'px': '1823.6', 'sz': '0.0259', 'n': 1}],
            [{'px': '2080.5', 'sz': '73.018', 'n': 2}, {'px': '2080.6', 'sz': '74.6799', 'n': 2},
             {'px': '2118.9', 'sz': '377.495', 'n': 1}, {'px': '2122.1', 'sz': '348.8644', 'n': 1}]]}}

    def get_funding_info_rest_msg(self):
        return [
            {'universe': [{'maxLeverage': 50, 'name': self.base_asset, 'onlyIsolated': False},
                          {'maxLeverage': 50, 'name': 'ETH', 'onlyIsolated': False}]}, [
                {'dayNtlVlm': '27009889.88843001', 'funding': '0.00001793',
                 'impactPxs': ['36724.0', '36736.9'],
                 'markPx': '36733.0', 'midPx': '36730.0', 'openInterest': '34.37756',
                 'oraclePx': '36717.0',
                 'premium': '0.00036632', 'prevDayPx': '35242.0'},
                {'dayNtlVlm': '8781185.14306', 'funding': '0.00005324', 'impactPxs': ['1922.9', '1923.1'],
                 'markPx': '1923.1',
                 'midPx': '1923.05', 'openInterest': '638.8957', 'oraclePx': '1921.7',
                 'premium': '0.00067648',
                 'prevDayPx': '1877.1'}]
        ]

    def get_trading_rule_rest_msg(self):
        return [
            {'universe': [{'maxLeverage': 50, 'name': self.base_asset, 'onlyIsolated': False},
                          {'maxLeverage': 50, 'name': 'ETH', 'onlyIsolated': False}]}, [
                {'dayNtlVlm': '27009889.88843001', 'funding': '0.00001793',
                 'impactPxs': ['36724.0', '36736.9'],
                 'markPx': '36733.0', 'midPx': '36730.0', 'openInterest': '34.37756',
                 'oraclePx': '36717.0',
                 'premium': '0.00036632', 'prevDayPx': '35242.0'},
                {'dayNtlVlm': '8781185.14306', 'funding': '0.00005324', 'impactPxs': ['1922.9', '1923.1'],
                 'markPx': '1923.1',
                 'midPx': '1923.05', 'openInterest': '638.8957', 'oraclePx': '1921.7',
                 'premium': '0.00067648',
                 'prevDayPx': '1877.1'}]
        ]

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_rest_snapshot_msg()
        mock_api.post(regex_url, body=json.dumps(resp))

        order_book = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        self.assertEqual(1700687397643, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(4, len(bids))
        self.assertEqual(2080.3, bids[0].price)
        self.assertEqual(74.6923, bids[0].amount)
        self.assertEqual(4, len(asks))
        self.assertEqual(2080.5, asks[0].price)
        self.assertEqual(73.018, asks[0].amount)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_diffs_and_orderbooks(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_diffs = self.get_ws_snapshot_msg()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs),
        )
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription_channel = CONSTANTS.TRADES_ENDPOINT_NAME
        expected_trade_subscription_payload = self.ex_trading_pair.split("-")[0]
        self.assertEqual(expected_trade_subscription_channel, sent_subscription_messages[0]["subscription"]["type"])
        self.assertEqual(expected_trade_subscription_payload, sent_subscription_messages[0]["subscription"]["coin"])
        expected_depth_subscription_channel = CONSTANTS.DEPTH_ENDPOINT_NAME
        expected_depth_subscription_payload = self.ex_trading_pair.split("-")[0]
        self.assertEqual(expected_depth_subscription_channel, sent_subscription_messages[1]["subscription"]["type"])
        self.assertEqual(expected_depth_subscription_payload, sent_subscription_messages[1]["subscription"]["coin"])

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to public order book, trade channels...")
        )

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    def test_subscribe_to_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_to_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws)
            )
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book data streams.")
        )

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "code": 0,
            "message": "",
            "data": [
                {
                    "created_at": 1642994704633,
                    "trade_id": 1005483402,
                    "instrument_id": "BTC-USD-PERPETUAL",
                    "qty": "1.00000000",
                    "side": "sell",
                    "sigma": "0.00000000",
                    "index_price": "2447.79750000",
                    "underlying_price": "0.00000000",
                    "is_block_trade": False
                },
                {
                    "created_at": 1642994704241,
                    "trade_id": 1005483400,
                    "instrument_id": "BTC-USD-PERPETUAL",
                    "qty": "1.00000000",
                    "side": "sell",
                    "sigma": "0.00000000",
                    "index_price": "2447.79750000",
                    "underlying_price": "0.00000000",
                    "is_block_trade": False
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        self._simulate_trading_rules_initialized()
        mock_queue = AsyncMock()
        trade_event = {'channel': 'trades', 'data': [
            {'coin': 'BTC', 'side': 'A', 'px': '2009.0', 'sz': '0.0079', 'time': 1701156061468,
             'hash': '0x3e2bc327cc925903cebe0408315a98010b002fda921d23fd1468bbb5d573f902'},  # noqa: mock
            {'coin': 'BTC', 'side': 'B', 'px': '2009.0', 'sz': '0.0079', 'time': 1701156052596,
             'hash': '0x0b2e11dc4ac8efee94660408315a690109003301ae47ae3512cded47641a42b1'}]}  # noqa: mock

        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(trade_event["data"][0]["hash"], msg.trade_id)
        self.assertEqual(trade_event["data"][0]["time"] * 1e-3, msg.timestamp)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = self.get_ws_diff_msg()
        del incomplete_resp["data"]["time"]

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    def test_listen_for_order_book_diffs_successful(self):
        self._simulate_trading_rules_initialized()
        mock_queue = AsyncMock()
        diff_event = self.get_ws_diff_msg_2()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        expected_update_id = diff_event["data"]["time"]
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(4, len(bids))
        self.assertEqual(2080.4, bids[0].price)
        self.assertEqual(74.6923, bids[0].amount)
        self.assertEqual(4, len(asks))
        self.assertEqual(2080.5, asks[0].price)
        self.assertEqual(73.018, asks[0].amount)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, exception=Exception)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api):
        msg_queue: asyncio.Queue = asyncio.Queue()
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        resp = self.get_rest_snapshot_msg()

        mock_api.post(regex_url, body=json.dumps(resp))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        expected_update_id = resp["time"]
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks

        self.assertEqual(4, len(bids))
        self.assertEqual(2080.3, bids[0].price)
        self.assertEqual(74.6923, bids[0].amount)
        self.assertEqual(4, len(asks))
        self.assertEqual(2080.5, asks[0].price)
        self.assertEqual(73.018, asks[0].amount)

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        endpoint = CONSTANTS.EXCHANGE_INFO_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_funding_info_rest_msg()
        mock_api.post(regex_url, body=json.dumps(resp))

        funding_info: FundingInfo = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )
        msg_result = resp

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(str(msg_result[1][0]["funding"])), funding_info.rate)

    def _simulate_trading_rules_initialized(self):
        mocked_response = self.get_trading_rule_rest_msg()
        self.connector._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        self.connector.coin_to_asset = {asset_info["name"]: asset for (asset, asset_info) in
                                        enumerate(mocked_response[0]["universe"])}
        self.connector._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    @aioresponses()
    def test_listen_for_funding_info_cancelled_error_raised(self, mock_api):
        endpoint = CONSTANTS.EXCHANGE_INFO_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_funding_info_rest_msg()
        mock_api.post(regex_url, body=json.dumps(resp), exception=asyncio.CancelledError)

        mock_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_funding_info(mock_queue),
                                        timeout=CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND + 10)

        self.assertEqual(0, mock_queue.qsize())

    @aioresponses()
    def test_listen_for_funding_info_logs_exception(self, mock_api):
        endpoint = CONSTANTS.EXCHANGE_INFO_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_funding_info_rest_msg()
        resp[0]["universe"] = ""
        mock_api.post(regex_url, body=json.dumps(resp), callback=self.resume_test_callback)

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        self.async_run_with_timeout(self.resume_test_event.wait(),
                                    timeout=CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND + 10)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public funding info updates from exchange"))

    @patch(
        "hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_api_order_book_data_source."
        "HyperliquidPerpetualAPIOrderBookDataSource._next_funding_time")
    @aioresponses()
    def test_listen_for_funding_info_successful(self, next_funding_time_mock, mock_api):
        next_funding_time_mock.return_value = 1713272400
        endpoint = CONSTANTS.EXCHANGE_INFO_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_funding_info_rest_msg()
        mock_api.post(regex_url, body=json.dumps(resp))

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        msg: FundingInfoUpdate = self.async_run_with_timeout(msg_queue.get(),
                                                             timeout=CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND + 10)

        self.assertEqual(self.trading_pair, msg.trading_pair)
        expected_index_price = Decimal('36717.0')
        self.assertEqual(expected_index_price, msg.index_price)
        expected_mark_price = Decimal('36733.0')
        self.assertEqual(expected_mark_price, msg.mark_price)
        expected_funding_time = next_funding_time_mock.return_value
        self.assertEqual(expected_funding_time, msg.next_funding_utc_timestamp)
        expected_rate = Decimal('0.00001793')
        self.assertEqual(expected_rate, msg.rate)
