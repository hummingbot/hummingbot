import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Dict, List, Union
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_api_order_book_data_source import (
    ArchitectPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
    ArchitectPerpetualDerivative,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class ArchitectPerpetualAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "EUR"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}-PERP"
        cls.domain = CONSTANTS.SANDBOX_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        self.connector = ArchitectPerpetualDerivative(
            api_key="test-key",
            api_secret="test-secret",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=CONSTANTS.SANDBOX_DOMAIN,
        )
        self.data_source = ArchitectPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=CONSTANTS.SANDBOX_DOMAIN,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        exchange_to_system_pairs = bidict({self.ex_trading_pair: self.trading_pair})
        ArchitectPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: exchange_to_system_pairs
        }

        self.connector._set_trading_pair_symbol_map(exchange_to_system_pairs)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

    async def asyncSetUp(self) -> None:
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        ArchitectPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def resume_test_callback(self, *_, **__):
        self.resume_test_event.set()
        return None

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def raise_exception(self, exception_class):
        raise exception_class

    def raise_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    @staticmethod
    def setup_auth_token(mock_api: aioresponses) -> str:
        expected_token = "test-token"
        url = web_utils.public_rest_url(CONSTANTS.AUTH_TOKEN_ENDPOINT, domain=CONSTANTS.SANDBOX_DOMAIN)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=json.dumps({"token": expected_token}))
        return expected_token

    def simulate_trading_rules_initialized(self):
        mocked_response = self.get_trading_rule_rest_msg()
        instrument_rules = mocked_response["instruments"][0]
        self.connector._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(instrument_rules["minimum_order_size"]),
                min_price_increment=Decimal(instrument_rules["tick_size"]),
                min_base_amount_increment=Decimal(instrument_rules["minimum_order_size"]),
            )
        }

    def get_trading_rule_rest_msg(self):
        response = {
            "instruments": [
                {
                    "symbol": self.ex_trading_pair,
                    "multiplier": "1",
                    "price_scale": 10000,
                    "minimum_order_size": "100",
                    "tick_size": "0.0001",
                    "quote_currency": "USD",
                    "price_band_lower_deviation_pct": "10",
                    "price_band_upper_deviation_pct": "10",
                    "funding_settlement_currency": "USD",
                    "funding_rate_cap_upper_pct": "1.0",
                    "funding_rate_cap_lower_pct": "-1.0",
                    "maintenance_margin_pct": "4.0",
                    "initial_margin_pct": "8.0",
                    "description": "Euro / US Dollar FX Perpetual Future",
                    "underlying_benchmark_price": "WMR London 4pm Closing Spot Rate",
                    "contract_mark_price": "Average price on Architect Bermuda Ltd. at London 4pm",
                    "contract_size": "1 Euro per contract",
                    "price_quotation": "U.S. dollars per Euro",
                    "price_bands": "+/- 10% from prior Contract Mark Price",
                    "funding_frequency": "Daily around 4:00 P.M. London time",
                    "funding_calendar_schedule": (
                        "All days where a valid Underlying Benchmark Price AND Contract Mark Price are published"
                    ),
                    "trading_schedule": {
                        ...
                    },
                },
            ]
        }
        return response

    def get_rest_snapshot_msg(self):
        response = {
            "book": {
                "a": [
                    {"o": [73], "p": "2090", "q": 73},
                    {"o": [100], "p": "2091", "q": 100},
                ],
                "b": [
                    {"o": [74], "p": "2080.3", "q": 74},
                ],
                "s": self.ex_trading_pair,
                "tn": 90277912,
                "ts": 1767995105,
            },
        }
        return response

    def funding_info_rest_data(self) -> Dict[str, List[Dict[str, Union[str, int]]]]:
        resp = {
            "funding_rates": [
                {
                    "benchmark_price": "0.000164",
                    "funding_amount": "0.0375",
                    "funding_rate": "0.000165",
                    "settlement_price": "46353.99600757",
                    "symbol": self.ex_trading_pair,
                    "timestamp_ns": 1767948610909067008,
                },
            ],
        }
        return resp

    def get_subscribed_message(self):
        return {"result": {"subscribed": self.ex_trading_pair}, "rid": 0}

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api: aioresponses):
        self.setup_auth_token(mock_api=mock_api)
        endpoint = CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT
        url = web_utils.public_rest_url(endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_rest_snapshot_msg()
        mock_api.get(regex_url, body=json.dumps(resp))

        order_book = await self.data_source.get_new_order_book(self.trading_pair)

        self.assertEqual(176799510590277912, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(2080.3, bids[0].price)
        self.assertEqual(74, bids[0].amount)
        self.assertEqual(2, len(asks))
        self.assertEqual(2090, asks[0].price)
        self.assertEqual(73, asks[0].amount)

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api: aioresponses):
        self.setup_auth_token(mock_api=mock_api)
        endpoint = CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT
        url = web_utils.public_rest_url(endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_opens_authenticated_connection_and_subscribes_to_trading_pair_updates(
        self,
        mock_api: aioresponses,
        mock_ws: AsyncMock
    ):
        expected_token = self.setup_auth_token(mock_api=mock_api)
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        result_subscribe_trading_pair = self.get_subscribed_message()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_trading_pair),
        )

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_subscriptions()
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value, timeout=1)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )

        mock_calls = mock_ws.mock_calls
        self.assertTrue(
            any(
                [
                    mock_call.kwargs.get("headers", {}).get("Authorization", None) == f"Bearer {expected_token}"
                    for mock_call in mock_calls
                ]
            )
        )
        self.assertEqual(1, len(sent_subscription_messages))
        self.assertEqual(
            {"request_id": 0, "type": "subscribe", "symbol": self.ex_trading_pair, "level": "LEVEL_2"},
            sent_subscription_messages[0],
        )
        self.assertTrue(
            self.is_logged("INFO", f"Subscribed to public channels for {self.trading_pair}...")
        )

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(
        self, mock_api: aioresponses, mock_ws, _: AsyncMock
    ):
        self.setup_auth_token(mock_api=mock_api)
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(self.data_source.listen_for_subscriptions(), timeout=1)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self.create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.resume_test_event.wait()

        self.assertTrue(
            self.is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    async def test_subscribe_to_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_to_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self.is_logged(
                "ERROR",
                f"Unexpected error occurred subscribing to order book data streams for {self.trading_pair}.",
            )
        )

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    async def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "t": "s",
            "ts": 1609459200,
            "tn": 123456789,
            "s": self.ex_trading_pair,
            # "p": "50000.00",
            "q": 100,
            "d": "B"
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self.is_logged("ERROR", "Unexpected error when processing public trade updates from exchange")
        )

    async def test_listen_for_trades_successful(self):
        self.simulate_trading_rules_initialized()
        mock_queue = AsyncMock()
        trade_event = {
            "t": "s",
            "ts": 1609459200,
            "tn": 123456789,
            "s": self.ex_trading_pair,
            "p": "50000.00",
            "q": 100,
            "d": "B"
        }

        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await asyncio.wait_for(msg_queue.get(), timeout=1)

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(int(f"{trade_event['ts']}{trade_event['tn']}"), msg.trade_id)
        self.assertEqual(trade_event["ts"], msg.timestamp)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(
        self,
        mock_api: aioresponses,
        mock_ws: AsyncMock
    ):
        self.setup_auth_token(mock_api=mock_api)
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        endpoint = CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT
        url = web_utils.public_rest_url(endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(
                self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue()), timeout=1
            )

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    async def test_listen_for_order_book_snapshots_log_exception(self, mock_api: aioresponses, sleep_mock: AsyncMock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self.create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        endpoint = CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT
        url = web_utils.public_rest_url(endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, exception=Exception)

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )
        await self.resume_test_event.wait()

        self.assertTrue(
            self.is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_snapshots_successful(self, mock_api: aioresponses, mock_ws: AsyncMock):
        self.setup_auth_token(mock_api=mock_api)
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        msg_queue: asyncio.Queue = asyncio.Queue()
        endpoint = CONSTANTS.PUBLIC_ORDERBOOK_ENDPOINT
        url = web_utils.public_rest_url(endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        resp = self.get_rest_snapshot_msg()

        mock_api.get(regex_url, body=json.dumps(resp))

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue)
        )

        msg: OrderBookMessage = await asyncio.wait_for(msg_queue.get(), timeout=1)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        expected_update_id = int(f"{resp['book']['ts']}{resp['book']['tn']}")
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks

        self.assertEqual(1, len(bids))
        self.assertEqual(2080.3, bids[0].price)
        self.assertEqual(74, bids[0].amount)
        self.assertEqual(2, len(asks))
        self.assertEqual(2090, asks[0].price)
        self.assertEqual(73, asks[0].amount)

    @aioresponses()
    async def test_get_funding_info(self, mock_api):
        self.setup_auth_token(mock_api=mock_api)
        endpoint = CONSTANTS.FUNDING_INFO_ENDPOINT
        url = web_utils.private_rest_url(endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        funding_info_resp = self.funding_info_rest_data()
        mock_api.get(regex_url, body=json.dumps(funding_info_resp))

        funding_info: FundingInfo = await self.data_source.get_funding_info(self.trading_pair)

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(funding_info_resp["funding_rates"][0]["benchmark_price"]), funding_info.index_price)
        self.assertEqual(Decimal(funding_info_resp["funding_rates"][0]["settlement_price"]), funding_info.mark_price)
        self.assertEqual(Decimal(funding_info_resp["funding_rates"][0]["funding_rate"]), funding_info.rate)
        self.assertEqual(
            int(funding_info_resp["funding_rates"][0]["timestamp_ns"] * 1e-9),
            funding_info.next_funding_utc_timestamp,
        )

    @aioresponses()
    async def test_listen_for_funding_info_logs_exception(self, mock_api: aioresponses):
        self.setup_auth_token(mock_api=mock_api)
        endpoint = CONSTANTS.FUNDING_INFO_ENDPOINT
        url = web_utils.private_rest_url(endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.funding_info_rest_data()
        resp["funding_rates"][0]["funding_rate"] = ""
        mock_api.get(regex_url, body=json.dumps(resp), callback=self.resume_test_callback)

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        await asyncio.wait_for(self.resume_test_event.wait(), timeout=1)

        self.assertTrue(
            self.is_logged("ERROR", "Unexpected error when processing public funding info updates from exchange")
        )

    @aioresponses()
    @patch.object(ArchitectPerpetualAPIOrderBookDataSource, "_sleep")
    async def test_listen_for_funding_info_cancelled_error_raised(self, mock_api: aioresponses, sleep_mock: AsyncMock):
        self.setup_auth_token(mock_api=mock_api)
        sleep_mock.side_effect = [asyncio.CancelledError()]
        endpoint = CONSTANTS.FUNDING_INFO_ENDPOINT
        url = web_utils.private_rest_url(endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.funding_info_rest_data()
        mock_api.get(regex_url, body=json.dumps(resp))

        mock_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_funding_info(mock_queue)

        self.assertEqual(1, mock_queue.qsize())

    @aioresponses()
    async def test_get_funding_info_from_exchange_successful(self, mock_api: aioresponses):
        self.setup_auth_token(mock_api=mock_api)
        url = web_utils.private_rest_url(CONSTANTS.FUNDING_INFO_ENDPOINT, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        funding_info_resp = self.funding_info_rest_data()
        mock_api.get(regex_url, body=json.dumps(funding_info_resp))

        funding_info: FundingInfo = await self.data_source.get_funding_info(self.trading_pair)

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(funding_info_resp["funding_rates"][0]["benchmark_price"]), funding_info.index_price)
        self.assertEqual(Decimal(funding_info_resp["funding_rates"][0]["settlement_price"]), funding_info.mark_price)
        self.assertEqual(Decimal(funding_info_resp["funding_rates"][0]["funding_rate"]), funding_info.rate)
        self.assertEqual(
            int(funding_info_resp["funding_rates"][0]["timestamp_ns"] * 1e-9),
            funding_info.next_funding_utc_timestamp,
        )

    # Dynamic subscription tests for subscribe_to_trading_pair and unsubscribe_from_trading_pair

    async def test_subscribe_to_trading_pair_websocket_not_connected(self):
        """Test subscription fails when WebSocket is not connected."""
        new_pair = "ETH-USDT"

        # Ensure ws_assistant is None
        self.data_source._ws_assistant = None

        result = await asyncio.wait_for(self.data_source.subscribe_to_trading_pair(new_pair), timeout=1)

        self.assertFalse(result)
        self.assertTrue(
            self.is_logged("WARNING", f"Cannot subscribe to {new_pair}: WebSocket not connected")
        )

    async def test_subscribe_to_trading_pair_raises_cancel_exception(self):
        """Test that CancelledError is properly raised during subscription."""
        new_pair = "ETH-USDT"
        ex_new_pair = "ETHUSDT-PERP"

        self.connector._set_trading_pair_symbol_map(
            bidict({self.ex_trading_pair: self.trading_pair, ex_new_pair: new_pair})
        )

        mock_ws = AsyncMock()
        mock_ws.send.side_effect = asyncio.CancelledError
        self.data_source._ws_assistant = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(self.data_source.subscribe_to_trading_pair(new_pair), timeout=1)

    async def test_subscribe_to_trading_pair_raises_exception_and_logs_error(self):
        """Test that exceptions during subscription are logged and return False."""
        new_pair = "ETH-USDT"
        ex_new_pair = "ETHUSDT-PERP"

        self.connector._set_trading_pair_symbol_map(
            bidict({self.ex_trading_pair: self.trading_pair, ex_new_pair: new_pair})
        )

        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Test Error")
        self.data_source._ws_assistant = mock_ws

        result = await asyncio.wait_for(self.data_source.subscribe_to_trading_pair(new_pair), timeout=1)

        self.assertFalse(result)
        self.assertTrue(
            self.is_logged(
                "ERROR",
                f"Unexpected error occurred subscribing to order book data streams for {new_pair}.",
            )
        )

    async def test_subscribe_to_trading_pair_successful(self):
        new_pair = "ETH-USDT"
        ex_new_pair = "ETHUSDT-PERP"

        # Set up the symbol map for the new pair
        self.connector._set_trading_pair_symbol_map(
            bidict({self.ex_trading_pair: self.trading_pair, ex_new_pair: new_pair})
        )

        # Create a mock WebSocket assistant
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        result = await asyncio.wait_for(self.data_source.subscribe_to_trading_pair(new_pair), timeout=1)

        self.assertTrue(result)
        self.assertEqual(1, mock_ws.send.call_count)

        # Verify trade subscription message
        trade_call = mock_ws.send.call_args_list[0]
        trade_payload = trade_call[0][0].payload
        self.assertEqual("subscribe", trade_payload["type"])
        self.assertEqual(ex_new_pair, trade_payload["symbol"])
        self.assertEqual("LEVEL_2", trade_payload["level"])

        # Verify pair was added to trading pairs
        self.assertIn(new_pair, self.data_source._trading_pairs)

        self.assertTrue(self.is_logged("INFO", f"Subscribed to public channels for {new_pair}..."))

    async def test_subscribe_to_already_subscribed_trading_pair_ignored(self):
        new_pair = self.trading_pair

        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        await asyncio.wait_for(self.data_source.subscribe_to_trading_pair(new_pair), timeout=1)
        result = await asyncio.wait_for(self.data_source.subscribe_to_trading_pair(new_pair), timeout=1)

        self.assertTrue(result)
        self.assertTrue(
            self.is_logged("WARNING", f"{new_pair} already subscribed. Ignoring request.")
        )

    async def test_unsubscribe_from_trading_pair_websocket_not_connected(self):
        """Test unsubscription fails when WebSocket is not connected."""
        self.data_source._ws_assistant = None

        result = await asyncio.wait_for(self.data_source.unsubscribe_from_trading_pair(self.trading_pair), timeout=1)

        self.assertFalse(result)
        self.assertTrue(
            self.is_logged("WARNING", f"Cannot unsubscribe from {self.trading_pair}: WebSocket not connected")
        )

    async def test_unsubscribe_from_trading_pair_raises_cancel_exception(self):
        """Test that CancelledError is properly raised during unsubscription."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = asyncio.CancelledError
        self.data_source._ws_assistant = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(self.data_source.unsubscribe_from_trading_pair(self.trading_pair), timeout=1)

    async def test_unsubscribe_from_trading_pair_raises_exception_and_logs_error(self):
        """Test that exceptions during unsubscription are logged and return False."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Test Error")
        self.data_source._ws_assistant = mock_ws

        result = await asyncio.wait_for(self.data_source.unsubscribe_from_trading_pair(self.trading_pair), timeout=1)

        self.assertFalse(result)
        self.assertTrue(
            self.is_logged(
                "ERROR",
                f"Unexpected error occurred unsubscribing from order book data streams for"
                f" {self.trading_pair}.",
            )
        )

    async def test_unsubscribe_from_trading_pair_successful(self):
        """Test successful unsubscription from a trading pair."""
        # The trading pair is already added in setup
        self.assertIn(self.trading_pair, self.data_source._trading_pairs)

        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        result = await asyncio.wait_for(self.data_source.unsubscribe_from_trading_pair(self.trading_pair), timeout=1)

        self.assertTrue(result)
        self.assertEqual(1, mock_ws.send.call_count)

        # Verify trade subscription message
        trade_call = mock_ws.send.call_args_list[0]
        trade_payload = trade_call[0][0].payload
        self.assertEqual("unsubscribe", trade_payload["type"])
        self.assertEqual(self.ex_trading_pair, trade_payload["symbol"])

        # Verify pair was removed from trading pairs
        self.assertNotIn(self.trading_pair, self.data_source._trading_pairs)

        self.assertTrue(
            self.is_logged("INFO", f"Unsubscribed from public channels for {self.trading_pair}.")
        )

    async def test_unsubscribe_from_non_subscribed_trading_pair_ignored(self):
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        await asyncio.wait_for(self.data_source.unsubscribe_from_trading_pair(self.trading_pair), timeout=1)
        result = await asyncio.wait_for(self.data_source.unsubscribe_from_trading_pair(self.trading_pair), timeout=1)

        self.assertTrue(result)
        self.assertTrue(
            self.is_logged("WARNING", f"{self.trading_pair} not subscribed. Ignoring request.")
        )
