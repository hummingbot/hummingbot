import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.vertex import vertex_constants as CONSTANTS
from hummingbot.connector.exchange.vertex.vertex_api_order_book_data_source import VertexAPIOrderBookDataSource
from hummingbot.connector.exchange.vertex.vertex_exchange import VertexExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage

# QUEUE KEYS FOR WEBSOCKET DATA PROCESSING
TRADE_KEY = "trade"
ORDER_BOOK_DIFF_KEY = "order_book_diff"
ORDER_BOOK_SNAPSHOT_KEY = "order_book_snapshot"


class TestVertexAPIOrderBookDataSource(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "wBTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.TESTNET_DOMAIN

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()

        self.log_records = []
        self.async_task = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        # NOTE: RANDOM KEYS GENERATED JUST FOR UNIT TESTS
        self.connector = VertexExchange(
            vertex_arbitrum_address="0x2162Db26939B9EAF0C5404217774d166056d31B5",
            vertex_arbitrum_private_key="5500eb16bf3692840e04fb6a63547b9a80b75d9cbb36b43ca5662127d4c19c83",  # noqa: mock
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.time_synchronnizer = TimeSynchronizer()
        self.time_synchronnizer.add_time_offset_ms_sample(1000)
        self.ob_data_source = VertexAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
            throttler=self.throttler,
        )

        self.connector._exchange_market_info = {self.domain: self.get_exchange_market_info_mock()}

        self._original_full_order_book_reset_time = self.ob_data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.ob_data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.ob_data_source.logger().setLevel(1)
        self.ob_data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        self.ob_data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def get_exchange_market_info_mock(self) -> Dict:
        exchange_rules = {
            1: {
                "product_id": 1,
                "oracle_price_x18": "26377830075239748635916",
                "risk": {
                    "long_weight_initial_x18": "900000000000000000",
                    "short_weight_initial_x18": "1100000000000000000",
                    "long_weight_maintenance_x18": "950000000000000000",
                    "short_weight_maintenance_x18": "1050000000000000000",
                    "large_position_penalty_x18": "0",
                },
                "config": {
                    "token": "0x5cc7c91690b2cbaee19a513473d73403e13fb431",  # noqa: mock
                    "interest_inflection_util_x18": "800000000000000000",
                    "interest_floor_x18": "10000000000000000",
                    "interest_small_cap_x18": "40000000000000000",
                    "interest_large_cap_x18": "1000000000000000000",
                },
                "state": {
                    "cumulative_deposits_multiplier_x18": "1001494499342736176",
                    "cumulative_borrows_multiplier_x18": "1005427534505418441",
                    "total_deposits_normalized": "336222763183987406404281",
                    "total_borrows_normalized": "106663044719707335242158",
                },
                "lp_state": {
                    "supply": "62619418496845923388438072",
                    "quote": {
                        "amount": "91404440604308224485238211",
                        "last_cumulative_multiplier_x18": "1000000008185212765",
                    },
                    "base": {
                        "amount": "3531841597039580133389",
                        "last_cumulative_multiplier_x18": "1001494499342736176",
                    },
                },
                "book_info": {
                    "size_increment": "1000000000000000",
                    "price_increment_x18": "1000000000000000000",
                    "min_size": "10000000000000000",
                    "collected_fees": "56936143536016463686263",
                    "lp_spread_x18": "3000000000000000",
                },
                "symbol": "wBTC",
                "market": "wBTC/USDC",
                "contract": "0x939b0915f9c3b657b9e9a095269a0078dd587491",  # noqa: mock
            },
        }
        return exchange_rules

    def get_exchange_rules_mock(self) -> Dict:
        exchange_rules = {
            "status": "success",
            "data": {
                "spot_products": [
                    {
                        "product_id": 1,
                        "oracle_price_x18": "26377830075239748635916",
                        "risk": {
                            "long_weight_initial_x18": "900000000000000000",
                            "short_weight_initial_x18": "1100000000000000000",
                            "long_weight_maintenance_x18": "950000000000000000",
                            "short_weight_maintenance_x18": "1050000000000000000",
                            "large_position_penalty_x18": "0",
                        },
                        "config": {
                            "token": "0x5cc7c91690b2cbaee19a513473d73403e13fb431",  # noqa: mock
                            "interest_inflection_util_x18": "800000000000000000",
                            "interest_floor_x18": "10000000000000000",
                            "interest_small_cap_x18": "40000000000000000",
                            "interest_large_cap_x18": "1000000000000000000",
                        },
                        "state": {
                            "cumulative_deposits_multiplier_x18": "1001494499342736176",
                            "cumulative_borrows_multiplier_x18": "1005427534505418441",
                            "total_deposits_normalized": "336222763183987406404281",
                            "total_borrows_normalized": "106663044719707335242158",
                        },
                        "lp_state": {
                            "supply": "62619418496845923388438072",
                            "quote": {
                                "amount": "91404440604308224485238211",
                                "last_cumulative_multiplier_x18": "1000000008185212765",
                            },
                            "base": {
                                "amount": "3531841597039580133389",
                                "last_cumulative_multiplier_x18": "1001494499342736176",
                            },
                        },
                        "book_info": {
                            "size_increment": "1000000000000000",
                            "price_increment_x18": "1000000000000000000",
                            "min_size": "10000000000000000",
                            "collected_fees": "56936143536016463686263",
                            "lp_spread_x18": "3000000000000000",
                        },
                        "symbol": "wBTC",
                        "market": "wBTC/USDC",
                        "contract": "0x939b0915f9c3b657b9e9a095269a0078dd587491",  # noqa: mock
                    },
                ],
            },
        }
        return exchange_rules

    # ORDER BOOK SNAPSHOT
    @staticmethod
    def _snapshot_response() -> Dict:
        snapshot = {
            "status": "success",
            "data": {
                "bids": [
                    ["25100000000000000000000", "1000000000000000000"],
                    ["25000000000000000000000", "2000000000000000000"],
                ],
                "asks": [
                    ["26000000000000000000000", "3000000000000000000"],
                    ["26100000000000000000000", "4000000000000000000"],
                ],
                "timestamp": "1686272064612415825",
            },
        }
        return snapshot

    @aioresponses()
    async def test_request_order_book_snapshot(self, mock_api):
        url = f"{CONSTANTS.BASE_URLS[self.domain]}/query?depth={CONSTANTS.ORDER_BOOK_DEPTH}&product_id=1&type={CONSTANTS.MARKET_LIQUIDITY_REQUEST_TYPE}"
        snapshot_data = self._snapshot_response()
        tradingrule_url = f"{CONSTANTS.BASE_URLS[self.domain]}/query?type={CONSTANTS.ALL_PRODUCTS_REQUEST_TYPE}"
        tradingrule_resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(tradingrule_resp))
        mock_api.get(url, body=json.dumps(snapshot_data))

        ret = await self.ob_data_source._request_order_book_snapshot(self.trading_pair)

        self.assertEqual(snapshot_data, ret)

    @aioresponses()
    async def test_get_snapshot_raises(self, mock_api):
        url = f"{CONSTANTS.BASE_URLS[self.domain]}/query?depth={CONSTANTS.ORDER_BOOK_DEPTH}&product_id=1&type={CONSTANTS.MARKET_LIQUIDITY_REQUEST_TYPE}"
        tradingrule_url = f"{CONSTANTS.BASE_URLS[self.domain]}/query?type={CONSTANTS.ALL_PRODUCTS_REQUEST_TYPE}"
        tradingrule_resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(tradingrule_resp))
        mock_api.get(url, status=500)

        with self.assertRaises(IOError):
            await self.ob_data_source._order_book_snapshot(self.trading_pair)

    @aioresponses()
    async def test_get_new_order_book(self, mock_api):
        url = f"{CONSTANTS.BASE_URLS[self.domain]}/query?depth={CONSTANTS.ORDER_BOOK_DEPTH}&product_id=1&type={CONSTANTS.MARKET_LIQUIDITY_REQUEST_TYPE}"
        resp = self._snapshot_response()
        tradingrule_url = f"{CONSTANTS.BASE_URLS[self.domain]}/query?type={CONSTANTS.ALL_PRODUCTS_REQUEST_TYPE}"
        tradingrule_resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(tradingrule_resp))
        mock_api.get(url, body=json.dumps(resp))

        ret = await self.ob_data_source.get_new_order_book(self.trading_pair)
        bid_entries = list(ret.bid_entries())
        ask_entries = list(ret.ask_entries())
        self.assertEqual(2, len(bid_entries))
        self.assertEqual(25100, bid_entries[0].price)
        self.assertEqual(1, bid_entries[0].amount)
        self.assertEqual(25000, bid_entries[1].price)
        self.assertEqual(2, bid_entries[1].amount)

        self.assertEqual(int(resp["data"]["timestamp"]), bid_entries[0].update_id)
        self.assertEqual(2, len(ask_entries))
        self.assertEqual(26000, ask_entries[0].price)
        self.assertEqual(3, ask_entries[0].amount)
        self.assertEqual(26100, ask_entries[1].price)
        self.assertEqual(4, ask_entries[1].amount)
        self.assertEqual(int(resp["data"]["timestamp"]), ask_entries[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_trades_and_depth(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {"method": "subscribe", "stream": {"type": "trade", "product_id": 1}, "id": 1}

        result_subscribe_depth = {"method": "subscribe", "stream": {"type": "book_depth", "product_id": 1}, "id": 1}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_subscribe_trades)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_subscribe_depth)
        )

        self.listening_task = self.local_event_loop.create_task(self.ob_data_source.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {"method": "subscribe", "stream": {"type": "trade", "product_id": 1}, "id": 1}
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {"method": "subscribe", "stream": {"type": "book_depth", "product_id": 1}, "id": 1}
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(
            self._is_logged(
                "INFO", f"Subscribed to public trade and order book diff channels of {self.trading_pair}..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    async def test_listen_for_subscriptions_raises_cancel_exception(self, _, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.ob_data_source.listen_for_subscriptions()

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    async def test_listen_for_subscriptions_logs_exception_details(self, sleep_mock, ws_connect_mock):
        sleep_mock.side_effect = asyncio.CancelledError
        ws_connect_mock.side_effect = Exception("TEST ERROR.")

        with self.assertRaises(asyncio.CancelledError):
            await self.ob_data_source.listen_for_subscriptions()

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.ob_data_source.listen_for_trades(self.local_event_loop, msg_queue)

    async def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "type": "trade",
            "timestamp": 1676151190656903000,
            "product_id": 1,
            "taker_qty": "1000000000000000000",
            "maker_qty": "1000000000000000000",
            "is_taker_buyer": True,
            "is_maker_amm": True,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.ob_data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.ob_data_source.listen_for_trades(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    async def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        trade_event = {
            "type": "trade",
            "timestamp": 1676151190656903000,
            "product_id": 1,
            "price": "26000000000000000000000",
            "taker_qty": "1000000000000000000",
            "maker_qty": "1000000000000000000",
            "is_taker_buyer": True,
            "is_maker_amm": True,
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.ob_data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.local_event_loop.create_task(
                self.ob_data_source.listen_for_trades(self.local_event_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = await msg_queue.get()

        self.assertTrue(trade_event["timestamp"], msg.trade_id)

    async def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue[ORDER_BOOK_DIFF_KEY] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.ob_data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)

    async def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "type": "book_depth",
            "min_timestamp": "1683805381879572835",
            "max_timestamp": "1683805381879572835",
            "last_max_timestamp": "1683805381771464799",
            "product_id": 1,
            "bids": [["26000000000000000000000", "1000000000000000000"]],
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.ob_data_source._message_queue[ORDER_BOOK_DIFF_KEY] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.ob_data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange")
        )

    async def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = {
            "type": "book_depth",
            "min_timestamp": "1683805381879572835",
            "max_timestamp": "1683805381879572835",
            "last_max_timestamp": "1683805381771464799",
            "product_id": 1,
            "bids": [["26000000000000000000000", "1000000000000000000"]],
            "asks": [],
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.ob_data_source._message_queue[ORDER_BOOK_DIFF_KEY] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.local_event_loop.create_task(
                self.ob_data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = await msg_queue.get()

        self.assertTrue(diff_event["last_max_timestamp"], msg.update_id)

    @aioresponses()
    async def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = f"{CONSTANTS.BASE_URLS[self.domain]}/query?depth={CONSTANTS.ORDER_BOOK_DEPTH}&product_id=1&type={CONSTANTS.MARKET_LIQUIDITY_REQUEST_TYPE}"
        mock_api.get(url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            await self.ob_data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    async def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = asyncio.CancelledError

        url = f"{CONSTANTS.BASE_URLS[self.domain]}/query?depth={CONSTANTS.ORDER_BOOK_DEPTH}&product_id=1&type={CONSTANTS.MARKET_LIQUIDITY_REQUEST_TYPE}"
        mock_api.get(url, exception=Exception)

        try:
            await self.ob_data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    async def test_listen_for_order_book_snapshots_successful(self, mock_api):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.TimeoutError
        self.ob_data_source._message_queue[ORDER_BOOK_SNAPSHOT_KEY] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()
        url = f"{CONSTANTS.BASE_URLS[self.domain]}/query?depth={CONSTANTS.ORDER_BOOK_DEPTH}&product_id=1&type={CONSTANTS.MARKET_LIQUIDITY_REQUEST_TYPE}"
        snapshot_data = self._snapshot_response()
        mock_api.get(url, body=json.dumps(snapshot_data))
        self.ob_data_source._sleep = AsyncMock()

        self.listening_task = self.local_event_loop.create_task(
            self.ob_data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(int(snapshot_data["data"]["timestamp"]), msg.update_id)

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.ob_data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.ob_data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to trading and order book stream...")
        )
