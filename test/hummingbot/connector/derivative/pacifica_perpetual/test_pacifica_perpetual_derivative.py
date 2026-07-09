import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Callable, Dict, Optional

import pandas as pd
from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_api_order_book_data_source import (
    PacificaPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_derivative import (
    PacificaPerpetualDerivative,
    PacificaPerpetualPriceRecord,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class PacificaPerpetualDerivativeUnitTest(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "ETH"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN
        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()

        self.exchange = PacificaPerpetualDerivative(
            pacifica_perpetual_agent_wallet_public_key="testAgentPublic",
            pacifica_perpetual_agent_wallet_private_key="2baSsQyyhz6k8p4hFgYy7uQewKSjn3meyW1W5owGYeasVL9Sqg3GgMRWgSpmw86PQmZXWQkCMrTLgLV8qrC6XQR2",
            pacifica_perpetual_user_wallet_public_key="testUserPublic",
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        if hasattr(self.exchange, "_time_synchronizer"):
            self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
            self.exchange._time_synchronizer.logger().setLevel(1)
            self.exchange._time_synchronizer.logger().addHandler(self)

        PacificaPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.symbol: self.trading_pair})
        }

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self.exchange._set_trading_pair_symbol_map(bidict({self.symbol: self.trading_pair}))
        self._initialize_event_loggers()

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.GET_MARKET_INFO_URL)
        return url

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        PacificaPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.funding_payment_completed_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.FundingPaymentCompleted, self.funding_payment_completed_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def _get_exchange_info_mock_response(
            self,
            lot_size: float = 0.0001,
            tick_size: float = 0.01,
            min_order_size: float = 10.0,
            max_order_size: float = 1000000.0,
    ) -> Dict[str, Any]:
        mocked_exchange_info = {
            "data": [
                {
                    "symbol": self.symbol,
                    "lot_size": str(lot_size),
                    "tick_size": str(tick_size),
                    "min_order_size": str(min_order_size),
                    "max_order_size": str(max_order_size),
                    "min_tick": "0.01",
                    "max_leverage": 50,
                    "maintenance_margin": 0.05,
                    "base_asset_precision": 8,
                    "quote_asset_precision": 6,
                }
            ]
        }
        return mocked_exchange_info

    async def _simulate_trading_rules_initialized(self):
        mocked_response = self._get_exchange_info_mock_response()
        trading_rules = await self.exchange._format_trading_rules(mocked_response)
        self.exchange._trading_rules = {
            self.trading_pair: trading_rules[0]
        }

    async def test_format_trading_rules(self):
        lot_size = 0.0001
        tick_size = 0.01
        min_order_size = 10.0
        max_order_size = 1000000.0

        mocked_response = self._get_exchange_info_mock_response(
            lot_size, tick_size, min_order_size, max_order_size
        )

        # We need to mock the API call because _format_trading_rules is typically called
        # with the RESULT of the API call, assuming the connector handles the request/response wrapping.
        # But looking at Pacifica implementation, _format_trading_rules takes the LIST of market info.

        trading_rules = await self.exchange._format_trading_rules(mocked_response)

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[0]

        self.assertEqual(Decimal(str(lot_size)), trading_rule.min_order_size)
        self.assertEqual(Decimal(str(tick_size)), trading_rule.min_price_increment)
        self.assertEqual(Decimal(str(lot_size)), trading_rule.min_base_amount_increment)
        self.assertEqual(Decimal(str(min_order_size)), trading_rule.min_notional_size)
        self.assertEqual(Decimal(str(min_order_size)), trading_rule.min_order_value)
        # Verify max_order_size is NOT set to the USD value (should be default)
        self.assertNotEqual(Decimal(str(max_order_size)), trading_rule.max_order_size)

    @aioresponses()
    async def test_update_balances(self, req_mock):
        self.exchange._account_balances.clear()
        self.exchange._account_available_balances.clear()

        url = web_utils.public_rest_url(CONSTANTS.GET_ACCOUNT_INFO_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "success": True,
            "data": {
                "account_equity": "1000.50",
                "available_to_spend": "500.25",
            }
        }

        req_mock.get(regex_url, body=json.dumps(mock_response))

        await self.exchange._update_balances()

        self.assertEqual(Decimal("1000.50"), self.exchange.get_balance("USDC"))
        self.assertEqual(Decimal("500.25"), self.exchange.get_available_balance("USDC"))

    @aioresponses()
    async def test_update_positions(self, req_mock):
        await self._simulate_trading_rules_initialized()
        self.exchange._perpetual_trading.account_positions.clear()

        # Set price record
        self.exchange._prices[self.trading_pair] = PacificaPerpetualPriceRecord(
            timestamp=self.start_timestamp,
            index_price=Decimal("1900"),
            mark_price=Decimal("1900")
        )

        get_positions_url = web_utils.public_rest_url(CONSTANTS.GET_POSITIONS_PATH_URL, domain=self.domain)
        get_positions_url = re.compile(f"^{get_positions_url}".replace(".", r"\.").replace("?", r"\?"))

        get_positions_mocked_response = {
            "success": True,
            "data": [
                {
                    "symbol": self.symbol,
                    "side": "bid",
                    "amount": "1.0",
                    "entry_price": "1800.0",
                    "leverage": "10",
                }
            ]
        }

        req_mock.get(get_positions_url, body=json.dumps(get_positions_mocked_response))

        get_prices_url = web_utils.public_rest_url(CONSTANTS.GET_PRICES_PATH_URL, domain=self.domain)

        get_prices_mocked_response = {
            "success": True,
            "data": [
                {
                    "funding": "0.00010529",
                    "mark": "1900",
                    "mid": "1900",
                    "next_funding": "0.00011096",
                    "open_interest": "3634796",
                    "oracle": "1900",
                    "symbol": self.symbol,
                    "timestamp": 1759222967974,
                    "volume_24h": "20896698.0672",
                    "yesterday_price": "1.3412"
                }
            ],
            "error": None,
            "code": None
        }

        req_mock.get(get_prices_url, body=json.dumps(get_prices_mocked_response))

        await self.exchange._update_positions()

        self.assertEqual(1, len(self.exchange.account_positions))
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(self.trading_pair, pos.trading_pair)
        self.assertEqual(Decimal("1.0"), pos.amount)
        self.assertEqual(Decimal("1800.0"), pos.entry_price)
        # PnL = (1900 - 1800) * 1.0 = 100.0
        self.assertEqual(Decimal("100.0"), pos.unrealized_pnl)

    @aioresponses()
    async def test_place_order(self, req_mock):
        await self._simulate_trading_rules_initialized()
        url = web_utils.public_rest_url(CONSTANTS.CREATE_LIMIT_ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "success": True,
            "data": {
                "order_id": 123456789
            }
        }

        req_mock.post(regex_url, body=json.dumps(mock_response))

        order_id = "test_order_1"
        exchange_order_id, timestamp = await self.exchange._place_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            amount=Decimal("1.0"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("1900.0"),
            position_action=PositionAction.OPEN
        )

        self.assertEqual("123456789", exchange_order_id)

    @aioresponses()
    async def test_place_market_order(self, req_mock):
        """Verify market orders hit /orders/create_market with slippage_percent."""
        await self._simulate_trading_rules_initialized()
        url = web_utils.public_rest_url(CONSTANTS.CREATE_MARKET_ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "success": True,
            "data": {
                "order_id": 987654321
            }
        }

        req_mock.post(regex_url, body=json.dumps(mock_response))

        order_id = "test_market_order_1"
        exchange_order_id, timestamp = await self.exchange._place_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            amount=Decimal("1.0"),
            trade_type=TradeType.SELL,
            order_type=OrderType.MARKET,
            price=Decimal("1900.0"),
            position_action=PositionAction.CLOSE
        )

        self.assertEqual("987654321", exchange_order_id)

        # Verify the request was sent to the market order endpoint
        sent_request = None
        for key, calls in req_mock.requests.items():
            if key[0] == "POST":
                sent_request = calls[0]
                break

        self.assertIsNotNone(sent_request)
        sent_data = json.loads(sent_request.kwargs["data"])

        # Market order must include slippage_percent (required by Pacifica API)
        self.assertEqual(CONSTANTS.MARKET_ORDER_MAX_SLIPPAGE, sent_data["slippage_percent"])
        # Note: "type" field is popped by the auth layer during signing, so it won't be in sent_data
        self.assertEqual("ask", sent_data["side"])
        self.assertTrue(sent_data["reduce_only"])

    def test_properties(self):
        self.assertEqual(self.domain, self.exchange.name)
        self.assertEqual(CONSTANTS.RATE_LIMITS, self.exchange.rate_limits_rules)
        self.assertEqual(CONSTANTS.DEFAULT_DOMAIN, self.exchange.domain)
        self.assertEqual(32, self.exchange.client_order_id_max_length)
        self.assertEqual(CONSTANTS.HB_OT_ID_PREFIX, self.exchange.client_order_id_prefix)
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.exchange.trading_rules_request_path)
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.exchange.trading_pairs_request_path)
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.exchange.check_network_request_path)
        self.assertTrue(self.exchange.is_cancel_request_in_exchange_synchronous)
        self.assertTrue(self.exchange.is_trading_required)
        self.assertEqual(120, self.exchange.funding_fee_poll_interval)
        self.assertEqual([OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET], self.exchange.supported_order_types())
        self.assertEqual([PositionMode.ONEWAY], self.exchange.supported_position_modes())
        self.assertEqual("USDC", self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual("USDC", self.exchange.get_sell_collateral_token(self.trading_pair))

    @aioresponses()
    async def test_place_cancel(self, req_mock):
        await self._simulate_trading_rules_initialized()
        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "success": True,
            "data": "some_data"
        }

        req_mock.post(regex_url, body=json.dumps(mock_response))

        tracked_order = InFlightOrder(
            client_order_id="test_client_order_id",
            exchange_order_id="123456789",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            price=Decimal("1900.0"),
            creation_timestamp=1640780000
        )

        result = await self.exchange._place_cancel("123456789", tracked_order)
        self.assertTrue(result)

    @aioresponses()
    async def test_all_trade_updates_for_order(self, req_mock):
        await self._simulate_trading_rules_initialized()

        self.exchange._trading_fees[self.trading_pair] = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.0002"),
            taker_percent_fee_decimal=Decimal("0.0005")
        )

        url = web_utils.public_rest_url(CONSTANTS.GET_TRADE_HISTORY_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # First response: 1 item, has_more=True
        mock_response_1 = {
            "success": True,
            "data": [
                {
                    "history_id": 19329801,
                    "order_id": 123456789,
                    "client_order_id": "acf...",
                    "symbol": self.symbol,
                    "amount": "0.6",
                    "price": "1900.0",
                    "entry_price": "1899.0",
                    "fee": "0.1",
                    "pnl": "-0.001",
                    "event_type": "fulfill_taker",
                    "side": "open_long",
                    "created_at": 1640780000000,
                    "cause": "normal"
                }
            ],
            "next_cursor": "cursor_1",
            "has_more": True
        }

        # Second response: 1 item, has_more=False
        mock_response_2 = {
            "success": True,
            "data": [
                {
                    "history_id": 19329800,
                    "order_id": 123456789,
                    "client_order_id": "acf...",
                    "symbol": self.symbol,
                    "amount": "0.4",
                    "price": "1900.0",
                    "entry_price": "1899.0",
                    "fee": "0.05",
                    "pnl": "-0.001",
                    "event_type": "fulfill_taker",
                    "side": "open_long",
                    "created_at": 1640770000000,
                    "cause": "normal"
                }
            ],
            "next_cursor": "",
            "has_more": False
        }

        # The first call matches the URL without cursor
        req_mock.get(regex_url, body=json.dumps(mock_response_1))
        # The second call matches the URL with cursor (regex_url handles query params essentially by just matching the base path prefix unless strict matching is done, but aioresponses mocks are FIFO for same url pattern if not using 'repeat')
        # Since regex_url matches the base, we can just queue the second response for the same regex.
        req_mock.get(regex_url, body=json.dumps(mock_response_2))

        tracked_order = InFlightOrder(
            client_order_id="test_client_order_id",
            exchange_order_id="123456789",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            price=Decimal("1900.0"),
            creation_timestamp=1640700000
        )

        trade_updates = await self.exchange._all_trade_updates_for_order(tracked_order)

        self.assertEqual(2, len(trade_updates))
        # Item 0 (amount 0.6)
        self.assertEqual(Decimal("0.6"), trade_updates[0].fill_base_amount)
        self.assertEqual(Decimal("0.1"), trade_updates[0].fee.flat_fees[0].amount)
        self.assertTrue(trade_updates[0].is_taker)

        # Item 1 (amount 0.4)
        self.assertEqual(Decimal("0.4"), trade_updates[1].fill_base_amount)
        self.assertEqual(Decimal("0.05"), trade_updates[1].fee.flat_fees[0].amount)

    @aioresponses()
    async def test_get_last_fee_payment(self, req_mock):
        await self._simulate_trading_rules_initialized()
        url = web_utils.public_rest_url(CONSTANTS.GET_FUNDING_HISTORY_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "success": True,
            "data": [
                {
                    "symbol": self.symbol,
                    "rate": "0.0001",
                    "payout": "1.5",
                    "created_at": 1640780000000
                }
            ]
        }

        req_mock.get(regex_url, body=json.dumps(mock_response))

        timestamp, rate, payout = await self.exchange._fetch_last_fee_payment(self.trading_pair)

        self.assertEqual(1640780000000, timestamp)
        self.assertEqual(Decimal("0.0001"), rate)
        self.assertEqual(Decimal("1.5"), payout)

    @aioresponses()
    async def test_set_trading_pair_leverage(self, req_mock):
        await self._simulate_trading_rules_initialized()
        url = web_utils.public_rest_url(CONSTANTS.SET_LEVERAGE_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"success": True}
        req_mock.post(regex_url, body=json.dumps(mock_response))

        success, msg = await self.exchange._set_trading_pair_leverage(self.trading_pair, 10)
        self.assertTrue(success)

    @aioresponses()
    async def test_fetch_last_fee_payment_pagination(self, req_mock):
        await self._simulate_trading_rules_initialized()
        url = web_utils.public_rest_url(CONSTANTS.GET_FUNDING_HISTORY_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # Page 1: Not found, has_more=True
        mock_response_1 = {
            "success": True,
            "data": [
                {
                    "symbol": "OTHER",
                    "rate": "0.0001",
                    "payout": "1.5",
                    "created_at": 1640780000000
                }
            ],
            "has_more": True,
            "next_cursor": "cursor_2"
        }

        # Page 2: Found
        mock_response_2 = {
            "success": True,
            "data": [
                {
                    "symbol": self.symbol,
                    "rate": "0.0002",
                    "payout": "2.0",
                    "created_at": 1640779000000
                }
            ],
            "has_more": False
        }

        # Queue responses
        req_mock.get(regex_url, body=json.dumps(mock_response_1))
        req_mock.get(regex_url, body=json.dumps(mock_response_2))

        timestamp, rate, payout = await self.exchange._fetch_last_fee_payment(self.trading_pair)

        self.assertEqual(1640779000000, timestamp)
        self.assertEqual(Decimal("0.0002"), rate)
        self.assertEqual(Decimal("2.0"), payout)

    @aioresponses()
    async def test_check_network(self, req_mock):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps({"success": True}))

        status = await self.exchange.check_network()
        self.assertEqual(NetworkStatus.CONNECTED, status)

    @aioresponses()
    async def test_api_request_header_injection(self, req_mock):
        url = web_utils.public_rest_url("/test")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        req_mock.get(regex_url, payload={"ok": True})

        # Set config key to test header injection
        self.exchange.api_config_key = "testkey"

        result = await self.exchange._api_request(
            path_url="/test",
            method=RESTMethod.GET,
            is_auth_required=False,
            limit_id=CONSTANTS.PACIFICA_LIMIT_ID
        )

        self.assertEqual({"ok": True}, result)

        request = None
        for key, calls in req_mock.requests.items():
            if key[0] == "GET" and key[1] == regex_url:
                request = calls[0]
                break

        # Fallback if specific regex object match fails (e.g. slight internal copy or something),
        # though regex equality should hold.
        # Since this test only makes one request, we could also just grab the first one.
        if request is None and len(req_mock.requests) > 0:
            request = list(req_mock.requests.values())[0][0]

        self.assertIsNotNone(request)
        self.assertEqual("testkey", request.kwargs["headers"]["PF-API-KEY"])

    @aioresponses()
    async def test_fetch_or_create_api_config_key_existing(self, req_mock):
        self.exchange.api_config_key = "existing"
        # call should return immediately
        await self.exchange._fetch_or_create_api_config_key()
        self.assertEqual("existing", self.exchange.api_config_key)
        # No requests should be made
        self.assertEqual(0, len(req_mock.requests))

    @aioresponses()
    async def test_fetch_or_create_api_config_key_fetch_and_create(self, req_mock):
        self.exchange.api_config_key = ""

        # Mock GET keys -> Success but empty list (no active keys)
        url_get = web_utils.private_rest_url(CONSTANTS.GET_ACCOUNT_API_CONFIG_KEYS, domain=self.domain)
        regex_url_get = re.compile(f"^{url_get}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url_get, payload={
            "success": True,
            "data": {"active_api_keys": []}
        })

        # Mock CREATE key -> Success
        url_create = web_utils.private_rest_url(CONSTANTS.CREATE_ACCOUNT_API_CONFIG_KEY, domain=self.domain)
        regex_url_create = re.compile(f"^{url_create}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url_create, payload={
            "success": True,
            "data": {"api_key": "newkey"}
        })

        await self.exchange._fetch_or_create_api_config_key()

        self.assertEqual("newkey", self.exchange.api_config_key)

    @aioresponses()
    async def test_request_order_status_mapping(self, req_mock):
        order = InFlightOrder(
            client_order_id="test_id",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1000"),
            creation_timestamp=1640780000
        )

        url = web_utils.public_rest_url(CONSTANTS.GET_ORDER_HISTORY_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, payload={
            "success": True,
            "data": [{"order_status": "filled", "created_at": 1234567890}]
        })

        update = await self.exchange._request_order_status(order)
        self.assertEqual(OrderType.LIMIT, order.order_type)  # Just checking object integrity
        # The important part is mapping 'filled' to the correct internal state, which likely happened inside
        # But _request_order_status returns OrderUpdate
        self.assertEqual(CONSTANTS.ORDER_STATE["filled"], update.new_state)

    @aioresponses()
    async def test_get_last_traded_price(self, req_mock):
        url = web_utils.public_rest_url(CONSTANTS.GET_CANDLES_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, payload={
            "success": True,
            "data": [{"c": "123.45"}]
        })

        price = await self.exchange._get_last_traded_price(self.trading_pair)
        self.assertIsInstance(price, float)
        self.assertEqual(123.45, price)

    @aioresponses()
    async def test_update_trading_fees(self, req_mock):
        url = web_utils.public_rest_url(CONSTANTS.GET_ACCOUNT_INFO_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, payload={
            "success": True,
            "data": {
                "fee_level": 0,
                "maker_fee": "0.00015",
                "taker_fee": "0.0004",
            }
        })

        await self.exchange._update_trading_fees()

        self.assertEqual(
            self.exchange._trading_fees[self.trading_pair],
            TradeFeeSchema(
                maker_percent_fee_decimal=Decimal("0.00015"),
                taker_percent_fee_decimal=Decimal("0.0004"),
            )
        )
