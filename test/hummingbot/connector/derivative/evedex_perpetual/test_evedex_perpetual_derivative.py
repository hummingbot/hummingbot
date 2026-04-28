"""Unit tests for Evedex Perpetual Derivative connector."""
import asyncio
import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Awaitable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses

import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import EvedexPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent


class EvedexPerpetualDerivativeUnitTest(IsolatedAsyncioWrapperTestCase):
    """
    Test suite for EvedexPerpetualDerivative connector.

    Based on official Evedex Swagger API:
    - https://swagger.evedex.com/?urls.primaryName=Exchange

    API Endpoints:
    - GET /api/market/instrument - Trading pairs/instruments
    - GET /api/market/{instrument}/deep - Order book
    - POST /api/v2/order/limit - Create limit order
    - POST /api/v2/order/market - Create market order
    - DELETE /api/order/{orderId} - Cancel order
    - GET /api/order/{orderId} - Get order details
    - GET /api/order/opened - Open orders
    - GET /api/fill - Order fills
    - GET /api/user/balance - User balance
    - GET /api/user/me - User info (for exchangeId)
    - GET /api/position - Positions
    """

    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN
        cls.user_exchange_id = "12345"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()

        self.exchange = EvedexPerpetualDerivative(
            evedex_perpetual_api_key="testAPIKey",
            evedex_perpetual_private_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",  # noqa: mock
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)
        self.test_task: Optional[asyncio.Task] = None
        self._initialize_event_loggers()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 5) -> Any:
        """Run async coroutine with timeout."""
        return self.local_event_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.INSTRUMENTS_PATH_URL)

    @property
    def latest_prices_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.INSTRUMENTS_PATH_URL)

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.PING_PATH_URL)

    @property
    def trading_rules_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.INSTRUMENTS_PATH_URL)

    @property
    def balance_url(self):
        return web_utils.private_rest_url(path_url=CONSTANTS.AVAILABLE_BALANCE_PATH_URL)

    @property
    def positions_url(self):
        return web_utils.private_rest_url(path_url=CONSTANTS.POSITIONS_PATH_URL)

    def tearDown(self) -> None:
        if self.test_task is not None:
            self.test_task.cancel()
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
            (MarketEvent.FundingPaymentCompleted, self.funding_payment_completed_logger)
        ]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _instruments_response(self) -> List[Dict[str, Any]]:
        """
        Mock response for GET /api/market/instrument based on Swagger API.
        Instrument schema from official OpenAPI spec.
        """
        return [
            {
                "id": "1",
                "name": self.ex_trading_pair,
                "displayName": f"{self.base_asset}/{self.quote_asset}",
                "from": {
                    "id": "1",
                    "name": self.base_asset,
                    "symbol": self.base_asset,
                    "image": None,
                    "precision": 8,
                    "showPrecision": 8,
                    "createdAt": "2024-01-01T00:00:00.000Z",
                    "avgLastPrice": 50000.0
                },
                "to": {
                    "id": "2",
                    "name": self.quote_asset,
                    "symbol": self.quote_asset,
                    "image": None,
                    "precision": 8,
                    "showPrecision": 8,
                    "createdAt": "2024-01-01T00:00:00.000Z"
                },
                "maxLeverage": 100,
                "leverageLimit": {"100000": 50, "500000": 20},
                "lotSize": 0.001,
                "priceIncrement": 0.01,
                "quantityIncrement": 0.001,
                "multiplier": 1.0,
                "maintenanceMargin": {},
                "minVolume": 10.0,
                "minPrice": 0.01,
                "maxPrice": 1000000.0,
                "minQuantity": 0.001,
                "maxQuantity": 10000.0,
                "slippageLimit": 0.1,
                "lastPrice": 50000.0,
                "markPrice": 50000.0,
                "fatFingerPriceProtection": 0.1,
                "markPriceLimit": 0.1,
                "visibility": "all",
                "trading": "all",
                "marketState": "OPEN",
                "updatedAt": "2024-01-01T00:00:00.000Z",
                "startDate": None,
                "isPopular": True,
                "newLabel": False
            }
        ]

    def _ping_response(self) -> Dict[str, Any]:
        """Mock response for GET /api/ping."""
        return {"time": 1640780000}

    def _balance_response(self) -> Dict[str, Any]:
        """
        Mock response for GET /api/market/available-balance based on actual API.
        Returns funding balance info with availableBalance.
        """
        return {
            "currency": "usdt",
            "funding": {
                "currency": "usdt",
                "balance": 5000.0
            },
            "availableBalance": 4500.0,
            "maintenanceMargin": 100.0
        }

    def _positions_response(self) -> Dict[str, Any]:
        """
        Mock response for GET /api/position based on Swagger API.
        Position schema from official OpenAPI spec.
        """
        return {
            "list": [
                {
                    "id": "pos_123456",
                    "user": "user_001",
                    "instrument": self.ex_trading_pair,
                    "quantity": 1.0,
                    "entryPrice": 49000.0,
                    "markPrice": 50000.0,
                    "liquidationPrice": 45000.0,
                    "leverage": 10,
                    "unrealizedPnL": 1000.0,
                    "realizedPnL": 0.0,
                    "marginMode": "CROSS",
                    "side": "LONG",
                    "createdAt": "2024-01-01T00:00:00.000Z",
                    "updatedAt": "2024-01-01T00:00:00.000Z"
                }
            ],
            "count": 1
        }

    def _order_response(self, status: str = "NEW") -> Dict[str, Any]:
        """
        Mock response for order operations based on Swagger API Order schema.
        """
        return {
            "id": "00001:00000000000000000000000001",
            "user": "user_001",
            "instrument": self.ex_trading_pair,
            "type": "LIMIT",
            "side": "BUY",
            "status": status,
            "rejectedReason": "",
            "quantity": 1.0,
            "limitPrice": 50000.0,
            "stopPrice": None,
            "group": "manually",
            "unFilledQuantity": 1.0 if status == "NEW" else 0.0,
            "cashQuantity": 50000.0,
            "filledAvgPrice": 0.0 if status == "NEW" else 50000.0,
            "realizedPnL": 0.0,
            "fee": [] if status == "NEW" else [{"coin": self.quote_asset, "quantity": 10.0}],
            "triggeredAt": None,
            "exchangeRequestId": "req_123",
            "createdAt": "2024-01-01T00:00:00.000Z",
            "updatedAt": "2024-01-01T00:00:00.000Z"
        }

    def _fills_response(self) -> Dict[str, Any]:
        """
        Mock response for GET /api/fill based on Swagger API.
        """
        return {
            "list": [
                {
                    "id": "fill_123456",
                    "order": "00001:00000000000000000000000001",
                    "instrument": self.ex_trading_pair,
                    "fillQuantity": 1.0,
                    "fillPrice": 50000.0,
                    "fillRole": "TAKER",
                    "fee": [{"coin": self.quote_asset, "quantity": 10.0}],
                    "pnl": 0.0,
                    "isPnlRealized": False,
                    "createdAt": "2024-01-01T00:00:00.000Z"
                }
            ],
            "count": 1
        }

    def _user_me_response(self) -> Dict[str, Any]:
        """Mock response for GET /api/user/me."""
        return {
            "id": "user_001",
            "exchangeId": self.user_exchange_id,
            "email": "test@example.com",
            "status": "ACTIVE",
            "createdAt": "2024-01-01T00:00:00.000Z"
        }

    @aioresponses()
    def test_check_network_success(self, mock_api):
        """Test network check with /api/ping endpoint."""
        url = self.network_status_url
        mock_api.get(url, body=json.dumps(self._ping_response()), repeat=True)
        # Also mock instruments endpoint since it may be called during network check
        mock_api.get(self.all_symbols_url, body=json.dumps(self._instruments_response()), repeat=True)

        result = self.async_run_with_timeout(self.exchange.check_network())

        from hummingbot.core.network_iterator import NetworkStatus
        self.assertEqual(result, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        """Test network check failure."""
        url = self.network_status_url
        mock_api.get(url, status=500, repeat=True)
        # Also mock instruments endpoint since it may be called during network check
        mock_api.get(self.all_symbols_url, body=json.dumps(self._instruments_response()), repeat=True)

        result = self.async_run_with_timeout(self.exchange.check_network())

        from hummingbot.core.network_iterator import NetworkStatus
        self.assertNotEqual(result, NetworkStatus.CONNECTED)  # Not connected

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        """Test trading rules update from /api/market/instrument."""
        url = self.trading_rules_url
        # Mock the instruments endpoint multiple times - once for symbol map initialization, once for trading rules
        mock_api.get(url, body=json.dumps(self._instruments_response()), repeat=True)

        # Initialize symbol map first with the mocked response data (sync method)
        exchange_info = self._instruments_response()
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(exchange_info)

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        trading_rule = self.exchange.trading_rules[self.trading_pair]
        self.assertEqual(trading_rule.min_order_size, Decimal("0.001"))
        self.assertEqual(trading_rule.min_price_increment, Decimal("0.01"))
        self.assertEqual(trading_rule.min_base_amount_increment, Decimal("0.001"))

    @aioresponses()
    def test_update_balances(self, mock_api):
        """Test balance update from /api/market/available-balance."""
        url = self.balance_url
        mock_api.get(url, body=json.dumps(self._balance_response()))

        self.async_run_with_timeout(self.exchange._update_balances())

        # The perpetual connector uses USDT as the funding currency
        self.assertEqual(self.exchange.available_balances["USDT"], Decimal("4500.0"))
        self.assertEqual(self.exchange.get_balance("USDT"), Decimal("5000.0"))

    def test_supported_order_types(self):
        """Test supported order types match API capabilities."""
        supported_types = self.exchange.supported_order_types()

        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.MARKET, supported_types)
        self.assertIn(OrderType.LIMIT_MAKER, supported_types)

    def test_supported_position_modes(self):
        """Test supported position modes (Evedex uses one-way mode)."""
        supported_modes = self.exchange.supported_position_modes()

        self.assertIn(PositionMode.ONEWAY, supported_modes)

    def test_exchange_symbol_format(self):
        """Test exchange symbol format: BASE-QUOTE."""
        symbol = f"{self.base_asset}-{self.quote_asset}"
        self.assertEqual(symbol, self.ex_trading_pair)

    def test_client_order_id_prefix(self):
        """Test client order ID prefix."""
        self.assertEqual(self.exchange.client_order_id_prefix, CONSTANTS.HBOT_ORDER_ID_PREFIX)

    def test_is_cancel_request_synchronous(self):
        """Test that cancel requests are synchronous."""
        self.assertTrue(self.exchange.is_cancel_request_in_exchange_synchronous)

    def test_order_state_mapping(self):
        """Test order state mapping matches Swagger API OrderStatus enum."""
        # From OrderStatus enum: INTENTION, NEW, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED, EXPIRED, REPLACED, ERROR
        self.assertEqual(CONSTANTS.ORDER_STATE["INTENTION"], OrderState.PENDING_CREATE)
        self.assertEqual(CONSTANTS.ORDER_STATE["NEW"], OrderState.OPEN)
        self.assertEqual(CONSTANTS.ORDER_STATE["PARTIALLY_FILLED"], OrderState.PARTIALLY_FILLED)
        self.assertEqual(CONSTANTS.ORDER_STATE["FILLED"], OrderState.FILLED)
        self.assertEqual(CONSTANTS.ORDER_STATE["CANCELLED"], OrderState.CANCELED)
        self.assertEqual(CONSTANTS.ORDER_STATE["REJECTED"], OrderState.FAILED)
        self.assertEqual(CONSTANTS.ORDER_STATE["EXPIRED"], OrderState.CANCELED)
        self.assertEqual(CONSTANTS.ORDER_STATE["REPLACED"], OrderState.OPEN)
        self.assertEqual(CONSTANTS.ORDER_STATE["ERROR"], OrderState.FAILED)

    def test_is_trading_required_and_funding_fee_poll_interval(self):
        self.assertTrue(self.exchange.is_trading_required)
        self.assertEqual(self.exchange.funding_fee_poll_interval, 600)

    def test_get_collateral_tokens(self):
        trading_rule = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("1"),
            min_price_increment=Decimal("0.1"),
            min_base_amount_increment=Decimal("0.1"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )
        self.exchange._trading_rules[self.trading_pair] = trading_rule
        self.assertEqual(self.exchange.get_buy_collateral_token(self.trading_pair), "USDT")
        self.assertEqual(self.exchange.get_sell_collateral_token(self.trading_pair), "USDT")

    def test_is_order_not_found_helpers(self):
        self.assertTrue(self.exchange._is_order_not_found_during_status_update_error(Exception(CONSTANTS.ORDER_NOT_EXIST_MESSAGE)))
        self.assertTrue(self.exchange._is_order_not_found_during_cancelation_error(Exception(CONSTANTS.ORDER_NOT_EXIST_MESSAGE)))

    def test_get_fee(self):
        fee = self.exchange._get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            position_action=PositionAction.OPEN,
            amount=Decimal("1"),
            price=Decimal("100"),
        )
        self.assertIsNotNone(fee)

    def test_update_trading_fees_noop(self):
        self.assertIsNone(self.async_run_with_timeout(self.exchange._update_trading_fees()))

    def test_status_polling_loop_fetch_updates_calls_methods(self):
        self.exchange._update_order_fills_from_trades = AsyncMock()
        self.exchange._update_order_status = AsyncMock()
        self.exchange._update_balances = AsyncMock()
        self.exchange._update_positions = AsyncMock()

        self.async_run_with_timeout(self.exchange._status_polling_loop_fetch_updates())

        self.exchange._update_order_fills_from_trades.assert_awaited_once()
        self.exchange._update_order_status.assert_awaited_once()
        self.exchange._update_balances.assert_awaited_once()
        self.exchange._update_positions.assert_awaited_once()

    def test_create_order_preserves_open_action_even_with_opposite_position_when_no_transition_pending(self):
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )
        position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal("0"),
            entry_price=Decimal("62000"),
            amount=Decimal("-1"),
            leverage=Decimal("5"),
        )
        position_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.SHORT)
        self.exchange._perpetual_trading.set_position(position_key, position)
        self.exchange._place_order = AsyncMock(return_value=("exchange-1", 1.0))

        self.async_run_with_timeout(
            self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id="OID_CREATE_OPEN",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.MARKET,
                price=Decimal("62000"),
                position_action=PositionAction.OPEN,
            )
        )

        tracked_order = self.exchange.in_flight_orders["OID_CREATE_OPEN"]
        self.assertEqual(PositionAction.OPEN, tracked_order.position)
        self.exchange._place_order.assert_awaited_once_with(
            order_id="OID_CREATE_OPEN",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.MARKET,
            price=Decimal("62000"),
            position_action=PositionAction.OPEN,
        )

    def test_create_close_order_marks_position_transition(self):
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )

        self.exchange._place_order = AsyncMock(return_value=("exchange-close", 1.0))
        self.exchange._schedule_position_update = MagicMock()

        self.async_run_with_timeout(
            self.exchange._create_order(
                trade_type=TradeType.SELL,
                order_id="OID_CREATE_CLOSE",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.MARKET,
                price=Decimal("62000"),
                position_action=PositionAction.CLOSE,
            )
        )

        tracked_order = self.exchange.in_flight_orders["OID_CREATE_CLOSE"]
        self.assertEqual(PositionAction.CLOSE, tracked_order.position)
        self.assertEqual("OID_CREATE_CLOSE", self.exchange._position_transition_order_id(self.trading_pair))
        self.exchange._place_order.assert_awaited_once_with(
            order_id="OID_CREATE_CLOSE",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.SELL,
            order_type=OrderType.MARKET,
            price=Decimal("62000"),
            position_action=PositionAction.CLOSE,
        )
        self.exchange._schedule_position_update.assert_called_once()

    def test_create_market_close_order_marks_filled_when_position_is_already_flat(self):
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=2)
        self.exchange.get_price = MagicMock(return_value=Decimal("62000"))
        self.exchange._update_positions = AsyncMock()
        self.exchange._api_post = AsyncMock()

        self.async_run_with_timeout(
            self.exchange._create_order(
                trade_type=TradeType.SELL,
                order_id="OID_CREATE_CLOSE_FLAT",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.MARKET,
                price=Decimal("NaN"),
                position_action=PositionAction.CLOSE,
            )
        )
        self.async_run_with_timeout(asyncio.sleep(0))

        cached_order = self.exchange._order_tracker.fetch_cached_order("OID_CREATE_CLOSE_FLAT")
        self.assertIsNotNone(cached_order)
        self.assertEqual(OrderState.FILLED, cached_order.current_state)
        self.assertEqual(Decimal("1"), cached_order.executed_amount_base)
        self.assertEqual(Decimal("62000"), cached_order.price)
        self.exchange._api_post.assert_not_called()
        self.assertIsNone(self.exchange._position_transition_order_id(self.trading_pair))

    def test_place_open_order_rejects_while_position_transition_pending(self):
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )
        position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal("0"),
            entry_price=Decimal("62000"),
            amount=Decimal("-1"),
            leverage=Decimal("5"),
        )
        position_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.SHORT)
        self.exchange._perpetual_trading.set_position(position_key, position)
        self.exchange._begin_position_transition(self.trading_pair, "OID_CLOSE")
        self.exchange._update_positions = AsyncMock()
        self.exchange._api_post = AsyncMock()
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=2)
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_market_order = MagicMock(return_value="0xsig")

        with self.assertRaisesRegex(
            ValueError,
            "Position transition in progress for BTC-USDT. Close order OID_CLOSE is awaiting flat-position confirmation.",
        ):
            self.async_run_with_timeout(
                self.exchange._place_order(
                    order_id="OID_OPEN_BLOCKED",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.MARKET,
                    price=Decimal("62000"),
                    position_action=PositionAction.OPEN,
                )
            )

        self.exchange._update_positions.assert_awaited_once()
        self.exchange._api_post.assert_not_called()

    def test_place_market_close_order_clamps_amount_to_live_position(self):
        self.exchange.start_tracking_order(
            order_id="OID_CLOSE_CLAMPED",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            price=Decimal("NaN"),
            amount=Decimal("13.4"),
            position_action=PositionAction.CLOSE,
        )
        position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal("0"),
            entry_price=Decimal("62000"),
            amount=Decimal("13.3"),
            leverage=Decimal("5"),
        )
        position_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.LONG)
        self.exchange._perpetual_trading.set_position(position_key, position)
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=2)
        self.exchange._update_positions = AsyncMock()
        self.exchange._api_post = AsyncMock(return_value={"id": "ex_close_clamped", "createdAt": 456})
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_position_close = MagicMock(return_value="0xsig")

        exchange_order_id, transact_time = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID_CLOSE_CLAMPED",
                trading_pair=self.trading_pair,
                amount=Decimal("13.4"),
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                price=Decimal("NaN"),
                position_action=PositionAction.CLOSE,
            )
        )

        self.assertEqual("ex_close_clamped", exchange_order_id)
        self.assertEqual(456, transact_time)
        tracked_order = self.exchange._order_tracker.fetch_tracked_order("OID_CLOSE_CLAMPED")
        self.assertEqual(Decimal("13.3"), tracked_order.amount)
        self.exchange._update_positions.assert_awaited_once()
        self.exchange._auth.sign_position_close.assert_called_once()
        self.exchange._api_post.assert_awaited_once()
        api_post_kwargs = self.exchange._api_post.await_args.kwargs
        self.assertEqual("13.3", api_post_kwargs["data"]["quantity"])

    def test_place_open_order_rejects_when_refresh_is_temporarily_flat_but_close_order_is_not_terminal(self):
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )
        position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal("0"),
            entry_price=Decimal("62000"),
            amount=Decimal("-1"),
            leverage=Decimal("5"),
        )
        position_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.SHORT)
        self.exchange._perpetual_trading.set_position(position_key, position)
        self.exchange.start_tracking_order(
            order_id="OID_CLOSE",
            exchange_order_id="EX_CLOSE",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal("62000"),
            amount=Decimal("1"),
            position_action=PositionAction.CLOSE,
        )
        self.exchange._begin_position_transition(self.trading_pair, "OID_CLOSE")

        async def refresh_positions():
            self.exchange._perpetual_trading.remove_position(position_key)
            self.exchange._reconcile_position_transitions()

        self.exchange._update_positions = AsyncMock(side_effect=refresh_positions)
        self.exchange._api_post = AsyncMock()
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=2)
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_market_order = MagicMock(return_value="0xsig")

        with self.assertRaisesRegex(
            ValueError,
            "Position transition in progress for BTC-USDT. Close order OID_CLOSE is awaiting flat-position confirmation.",
        ):
            self.async_run_with_timeout(
                self.exchange._place_order(
                    order_id="OID_OPEN_BLOCKED_BY_ACTIVE_CLOSE",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.MARKET,
                    price=Decimal("62000"),
                    position_action=PositionAction.OPEN,
                )
            )

        self.exchange._update_positions.assert_awaited_once()
        self.assertEqual("OID_CLOSE", self.exchange._position_transition_order_id(self.trading_pair))
        self.exchange._api_post.assert_not_called()

    def test_place_open_order_allows_after_transition_refresh_confirms_flat_position(self):
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )
        position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal("0"),
            entry_price=Decimal("62000"),
            amount=Decimal("-1"),
            leverage=Decimal("5"),
        )
        position_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.SHORT)
        self.exchange._perpetual_trading.set_position(position_key, position)
        self.exchange.start_tracking_order(
            order_id="OID_CLOSE",
            exchange_order_id="EX_CLOSE",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal("62000"),
            amount=Decimal("1"),
            position_action=PositionAction.CLOSE,
        )
        self.exchange._begin_position_transition(self.trading_pair, "OID_CLOSE")

        async def refresh_positions():
            tracked_close_order = self.exchange._order_tracker.fetch_tracked_order("OID_CLOSE")
            tracked_close_order.current_state = OrderState.FILLED
            self.exchange._order_tracker.stop_tracking_order("OID_CLOSE")
            self.exchange._perpetual_trading.remove_position(position_key)
            self.exchange._reconcile_position_transitions()

        self.exchange._update_positions = AsyncMock(side_effect=refresh_positions)
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=2)
        self.exchange._api_post = AsyncMock(return_value={"id": "ex_open_after_transition", "createdAt": 456})
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_market_order = MagicMock(return_value="0xsig")

        exchange_order_id, transact_time = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID_OPEN_AFTER_TRANSITION",
                trading_pair=self.trading_pair,
                amount=Decimal("2"),
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                price=Decimal("10"),
                position_action=PositionAction.OPEN,
            )
        )

        self.assertEqual(exchange_order_id, "ex_open_after_transition")
        self.assertEqual(transact_time, 456)
        self.exchange._update_positions.assert_awaited_once()
        self.assertIsNone(self.exchange._position_transition_order_id(self.trading_pair))
        self.exchange._api_post.assert_awaited_once()

    def test_place_order_requires_private_key(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = None
        with self.assertRaises(ValueError):
            self.async_run_with_timeout(
                self.exchange._place_order(
                    order_id="OIDX",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.LIMIT,
                    price=Decimal("10"),
                    position_action=PositionAction.OPEN,
                )
            )

    def test_place_order_raises_non_503(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=1)
        self.exchange._api_post = AsyncMock(side_effect=IOError("400 Bad Request"))
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_limit_order = MagicMock(return_value="0xsig")
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.exchange._place_order(
                    order_id="OIDR",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.LIMIT,
                    price=Decimal("10"),
                    position_action=PositionAction.OPEN,
                )
            )

    def test_all_trade_updates_for_order_timeout(self):
        order = InFlightOrder(
            client_order_id="OIDT",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("10"),
            creation_timestamp=self.exchange.current_timestamp,
        )
        order.get_exchange_order_id = AsyncMock(side_effect=asyncio.TimeoutError)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))

    def test_process_order_fill_updates(self):
        tracked_order = InFlightOrder(
            client_order_id="OIDF",
            exchange_order_id="EX123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("10"),
            creation_timestamp=self.exchange.current_timestamp,
        )
        self.exchange._order_tracker.start_tracking_order(tracked_order)
        self.exchange._order_tracker.process_trade_update = MagicMock()
        self.exchange._schedule_balance_update = MagicMock()
        fill_data = {"id": "EX123", "executionId": "F1", "fillPrice": "10", "fillQuantity": "1"}
        self.async_run_with_timeout(self.exchange._process_order_fill(fill_data))
        self.exchange._order_tracker.process_trade_update.assert_called()

    def test_process_order_fill_schedules_balance_and_position_refresh(self):
        tracked_order = InFlightOrder(
            client_order_id="OIDF",
            exchange_order_id="EX123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("10"),
            creation_timestamp=self.exchange.current_timestamp,
        )
        self.exchange._order_tracker.start_tracking_order(tracked_order)
        self.exchange._order_tracker.process_trade_update = MagicMock()
        self.exchange._update_balances = AsyncMock()
        self.exchange._update_positions = AsyncMock()
        scheduled_task = MagicMock()
        scheduled_task.done.return_value = False

        def schedule(coro):
            coro.close()
            return scheduled_task

        fill_data = {"id": "EX123", "executionId": "F1", "fillPrice": "10", "fillQuantity": "1"}
        with patch(
            "hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative.safe_ensure_future",
            side_effect=schedule,
        ) as schedule_mock:
            self.async_run_with_timeout(self.exchange._process_order_fill(fill_data))

        self.assertEqual(2, schedule_mock.call_count)

    def test_process_order_fill_with_documented_payload_marks_order_filled(self):
        self.exchange.start_tracking_order(
            order_id="OIDF_DOC",
            exchange_order_id="EX123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        self.exchange._schedule_balance_update = MagicMock()

        fill_data = {
            "id": "EX123",
            "status": "FILLED",
            "quantity": "1",
            "filledAvgPrice": "10",
            "fillQuantity": "1",
            "fee": [{"coin": "usdt", "quantity": "0.1"}, {"coin": "total", "quantity": "0"}],
            "exchangeRequestId": "REQ-1",
            "completedAt": "2026-03-20T02:42:54.964Z",
        }

        self.async_run_with_timeout(self.exchange._process_order_fill(fill_data))
        self.async_run_with_timeout(asyncio.sleep(0))

        cached_order = self.exchange._order_tracker.fetch_cached_order("OIDF_DOC")
        self.assertIsNotNone(cached_order)
        self.assertEqual(OrderState.FILLED, cached_order.current_state)
        self.assertIsNone(self.exchange._order_tracker.fetch_tracked_order("OIDF_DOC"))
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    def test_process_order_fill_untracked_fill_refreshes_balance_and_positions(self):
        self.exchange._schedule_balance_update = MagicMock()
        self.exchange._schedule_position_update = MagicMock()

        fill_data = {
            "id": "EX123",
            "status": "FILLED",
            "side": "SELL",
            "quantity": "1",
            "unFilledQuantity": "0",
            "filledAvgPrice": "10",
            "fillQuantity": "1",
            "updatedAt": "2026-03-20T02:42:54.964Z",
        }

        self.async_run_with_timeout(self.exchange._process_order_fill(fill_data))

        self.exchange._schedule_balance_update.assert_called_once()
        self.exchange._schedule_position_update.assert_called_once()

    def test_process_order_update_with_fill_and_status(self):
        tracked_order = InFlightOrder(
            client_order_id="OIDU",
            exchange_order_id="EXU",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("5"),
            price=Decimal("10"),
            creation_timestamp=self.exchange.current_timestamp,
        )
        self.exchange._order_tracker.start_tracking_order(tracked_order)
        self.exchange._order_tracker.process_trade_update = MagicMock()
        self.exchange._order_tracker.process_order_update = MagicMock()
        self.exchange._schedule_balance_update = MagicMock()
        self.exchange._schedule_position_update = MagicMock()
        order_data = {
            "id": "EXU",
            "status": "PARTIALLY_FILLED",
            "quantity": "5",
            "unFilledQuantity": "3",
            "filledAvgPrice": "10",
            "fee": [{"coin": "total", "quantity": "1"}, {"coin": "USDT", "quantity": "0.1"}]
        }
        self.async_run_with_timeout(self.exchange._process_order_update(order_data))
        self.exchange._order_tracker.process_trade_update.assert_called()
        self.exchange._order_tracker.process_order_update.assert_called()
        self.exchange._schedule_position_update.assert_called_once()

    def test_process_order_update_marks_filled_order_closed(self):
        self.exchange.start_tracking_order(
            order_id="OIDU_FILLED",
            exchange_order_id="EXU",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("5"),
            position_action=PositionAction.OPEN,
        )
        self.exchange._schedule_balance_update = MagicMock()

        order_data = {
            "id": "EXU",
            "status": "FILLED",
            "quantity": "5",
            "unFilledQuantity": "0",
            "filledAvgPrice": "10",
            "fee": [{"coin": "usdt", "quantity": "0.1"}, {"coin": "total", "quantity": "0"}],
            "exchangeRequestId": "REQ-2",
            "completedAt": "2026-03-20T02:41:34.067Z",
        }

        self.async_run_with_timeout(self.exchange._process_order_update(order_data))
        self.async_run_with_timeout(asyncio.sleep(0))

        cached_order = self.exchange._order_tracker.fetch_cached_order("OIDU_FILLED")
        self.assertIsNotNone(cached_order)
        self.assertEqual(OrderState.FILLED, cached_order.current_state)
        self.assertIsNone(self.exchange._order_tracker.fetch_tracked_order("OIDU_FILLED"))
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    def test_process_order_update_treats_partial_market_cancel_as_filled(self):
        self.exchange.start_tracking_order(
            order_id="OIDU_PARTIAL_IOC",
            exchange_order_id="EX_PARTIAL",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            price=Decimal("10"),
            amount=Decimal("20"),
            position_action=PositionAction.OPEN,
        )
        self.exchange._schedule_balance_update = MagicMock()

        order_data = {
            "id": "EX_PARTIAL",
            "status": "CANCELLED",
            "type": "MARKET",
            "timeInForce": "IOC",
            "side": "SELL",
            "quantity": "20",
            "unFilledQuantity": "1",
            "fillQuantity": "19",
            "filledAvgPrice": "1.4577",
            "updatedAt": "2026-03-20T05:16:14.681Z",
            "fee": [{"coin": "usdt", "quantity": "0.01246334"}],
        }

        self.async_run_with_timeout(self.exchange._process_order_update(order_data))
        self.async_run_with_timeout(asyncio.sleep(0))

        cached_order = self.exchange._order_tracker.fetch_cached_order("OIDU_PARTIAL_IOC")
        self.assertIsNotNone(cached_order)
        self.assertEqual(OrderState.FILLED, cached_order.current_state)
        self.assertEqual(Decimal("19"), cached_order.amount)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.sell_order_completed_logger.event_log))
        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

    def test_process_order_update_treats_smaller_filled_market_order_as_filled(self):
        self.exchange._order_tracker.TRADE_FILLS_WAIT_TIMEOUT = 0.01
        self.exchange.start_tracking_order(
            order_id="OIDU_FILLED_MARKET_MISMATCH",
            exchange_order_id="EX_FILLED_MARKET_MISMATCH",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("6.8"),
            position_action=PositionAction.OPEN,
        )
        self.exchange._schedule_balance_update = MagicMock()

        order_data = {
            "id": "EX_FILLED_MARKET_MISMATCH",
            "status": "FILLED",
            "type": "MARKET",
            "timeInForce": "IOC",
            "side": "BUY",
            "quantity": "6.7",
            "unFilledQuantity": "0",
            "fillQuantity": "6.7",
            "filledAvgPrice": "1.3157",
            "updatedAt": "2026-03-20T05:16:14.681Z",
            "fee": [{"coin": "usdt", "quantity": "0.01246334"}],
        }

        self.async_run_with_timeout(self.exchange._process_order_update(order_data))
        self.async_run_with_timeout(asyncio.sleep(0.05))

        cached_order = self.exchange._order_tracker.fetch_cached_order("OIDU_FILLED_MARKET_MISMATCH")
        self.assertIsNotNone(cached_order)
        self.assertEqual(OrderState.FILLED, cached_order.current_state)
        self.assertEqual(Decimal("6.7"), cached_order.amount)
        self.assertEqual(Decimal("6.7"), cached_order.executed_amount_base)
        self.assertTrue(cached_order.completely_filled_event.is_set())
        self.assertFalse(
            self._is_logged(
                "WARNING",
                "The order fill updates did not arrive on time for OIDU_FILLED_MARKET_MISMATCH. "
                "The complete update will be processed with incomplete information.",
            )
        )
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    def test_process_order_update_does_not_duplicate_explicit_fill(self):
        self.exchange.start_tracking_order(
            order_id="OIDU_NO_DUP",
            exchange_order_id="EX_NO_DUP",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("2"),
            position_action=PositionAction.OPEN,
        )

        fill_data = {
            "id": "EX_NO_DUP",
            "status": "PARTIALLY_FILLED",
            "fillPrice": "10",
            "fillQuantity": "1",
            "createdAt": "2026-03-20T02:42:54.804Z",
            "updatedAt": "2026-03-20T02:42:54.804Z",
        }
        self.async_run_with_timeout(self.exchange._process_order_fill(fill_data))

        tracked_order = self.exchange._order_tracker.fetch_tracked_order("OIDU_NO_DUP")
        self.assertEqual(Decimal("1"), tracked_order.executed_amount_base)
        self.assertEqual(1, len(tracked_order.order_fills))

        order_data = {
            "id": "EX_NO_DUP",
            "status": "PARTIALLY_FILLED",
            "type": "MARKET",
            "timeInForce": "IOC",
            "quantity": "2",
            "unFilledQuantity": "1",
            "filledAvgPrice": "10",
            "fillQuantity": "1",
            "updatedAt": "2026-03-20T02:42:54.804Z",
        }
        self.async_run_with_timeout(self.exchange._process_order_update(order_data))

        tracked_order = self.exchange._order_tracker.fetch_tracked_order("OIDU_NO_DUP")
        self.assertEqual(Decimal("1"), tracked_order.executed_amount_base)
        self.assertEqual(1, len(tracked_order.order_fills))

    def test_process_order_update_schedules_balance_refresh_for_cancel(self):
        self.exchange.start_tracking_order(
            order_id="OIDU_CANCEL",
            exchange_order_id="EXC",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("5"),
            position_action=PositionAction.OPEN,
        )
        self.exchange._update_balances = AsyncMock()
        scheduled_task = MagicMock()
        scheduled_task.done.return_value = False

        def schedule(coro):
            coro.close()
            return scheduled_task

        with patch(
            "hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative.safe_ensure_future",
            side_effect=schedule,
        ) as schedule_mock:
            self.async_run_with_timeout(
                self.exchange._process_order_update(
                    {
                        "id": "EXC",
                        "status": "CANCELLED",
                        "quantity": "5",
                        "unFilledQuantity": "5",
                        "updatedAt": "2026-03-20T02:41:33.799Z",
                    }
                )
            )

        schedule_mock.assert_called_once()

    def test_process_order_update_untracked_filled_refreshes_balance_and_positions(self):
        self.exchange._schedule_balance_update = MagicMock()
        self.exchange._schedule_position_update = MagicMock()

        self.async_run_with_timeout(
            self.exchange._process_order_update(
                {
                    "id": "EXC",
                    "status": "FILLED",
                    "side": "SELL",
                    "quantity": "5",
                    "unFilledQuantity": "0",
                    "fillQuantity": "5",
                    "updatedAt": "2026-03-20T02:41:33.799Z",
                }
            )
        )

        self.exchange._schedule_balance_update.assert_called_once()
        self.exchange._schedule_position_update.assert_called_once()

    def test_process_order_update_untracked_cancelled_refreshes_balance_only(self):
        self.exchange._schedule_balance_update = MagicMock()
        self.exchange._schedule_position_update = MagicMock()

        self.async_run_with_timeout(
            self.exchange._process_order_update(
                {
                    "id": "EXC",
                    "status": "CANCELLED",
                    "side": "BUY",
                    "quantity": "5",
                    "unFilledQuantity": "5",
                    "updatedAt": "2026-03-20T02:41:33.799Z",
                }
            )
        )

        self.exchange._schedule_balance_update.assert_called_once()
        self.exchange._schedule_position_update.assert_not_called()

    def test_process_order_update_cached_cancelled_refreshes_balance_only(self):
        self.exchange.start_tracking_order(
            order_id="OIDU_CACHED_CANCEL",
            exchange_order_id="EXC",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("5"),
            position_action=PositionAction.OPEN,
        )
        self.exchange._order_tracker.stop_tracking_order("OIDU_CACHED_CANCEL")
        self.exchange._schedule_balance_update = MagicMock()
        self.exchange._schedule_position_update = MagicMock()

        self.async_run_with_timeout(
            self.exchange._process_order_update(
                {
                    "id": "EXC",
                    "status": "CANCELLED",
                    "side": "BUY",
                    "quantity": "5",
                    "unFilledQuantity": "5",
                    "updatedAt": "2026-03-20T02:41:33.799Z",
                }
            )
        )

        self.exchange._schedule_balance_update.assert_called_once()
        self.exchange._schedule_position_update.assert_not_called()

    def test_process_position_update_sets_and_removes(self):
        self.exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.exchange._perpetual_trading.set_position = MagicMock()
        self.exchange._perpetual_trading.remove_position = MagicMock()
        position_data = [
            {"instrument": self.ex_trading_pair, "quantity": "1", "side": "BUY", "leverage": "2"},
            {"instrument": self.ex_trading_pair, "quantity": "0", "side": "BUY", "leverage": "2"},
        ]
        self.async_run_with_timeout(self.exchange._process_position_update(position_data))
        self.exchange._perpetual_trading.set_position.assert_called()
        self.exchange._perpetual_trading.remove_position.assert_called()

    def test_process_position_update_keeps_long_position_from_ws_event(self):
        from hummingbot.connector.derivative.position import Position
        from hummingbot.core.data_type.common import PositionSide

        other_pair = "ETH-USDT"
        other_pos_key = self.exchange._perpetual_trading.position_key(other_pair, PositionSide.LONG)
        self.exchange._perpetual_trading.set_position(
            other_pos_key,
            Position(
                trading_pair=other_pair,
                position_side=PositionSide.LONG,
                unrealized_pnl=Decimal("0"),
                entry_price=Decimal("2000"),
                amount=Decimal("1"),
                leverage=Decimal("3"),
            ),
        )
        self.exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)

        self.async_run_with_timeout(
            self.exchange._process_position_update(
                {
                    "instrument": self.ex_trading_pair,
                    "quantity": "1",
                    "side": "BUY",
                    "avgPrice": "100",
                    "leverage": "2",
                    "unRealizedPnL": "5",
                }
            )
        )

        pos_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.LONG)
        position = self.exchange._perpetual_trading.account_positions[pos_key]

        self.assertEqual(position.position_side, PositionSide.LONG)
        self.assertEqual(position.amount, Decimal("1"))
        self.assertIn(other_pos_key, self.exchange._perpetual_trading.account_positions)

    def test_format_trading_rules_and_initialize_mapping(self):
        rule = {
            "name": self.ex_trading_pair,
            "trading": "all",
            "visibility": "all",
            "from": {"symbol": self.base_asset},
            "to": {"symbol": "USD"},
            "minQuantity": "0.1",
            "priceIncrement": "0.01",
            "quantityIncrement": "0.01",
            "minPrice": "1",
        }
        self.exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        rules = self.async_run_with_timeout(self.exchange._format_trading_rules([rule]))
        self.assertEqual(len(rules), 1)
        self.exchange._initialize_trading_pair_symbols_from_exchange_info([rule])
        mapping = self.async_run_with_timeout(self.exchange.trading_pair_symbol_map())
        self.assertIn(self.ex_trading_pair, mapping)

    def test_format_trading_rules_uses_min_volume_and_collateral_token(self):
        """Test that _format_trading_rules uses minVolume directly and extracts collateral token from to.symbol."""
        rule = {
            "name": self.ex_trading_pair,
            "trading": "all",
            "visibility": "all",
            "from": {"symbol": self.base_asset},
            "to": {"symbol": "USD"},  # Should be converted to USDT
            "minQuantity": "0.1",
            "priceIncrement": "0.01",
            "quantityIncrement": "0.01",
            "minPrice": "100",
            "minVolume": 25.0,  # Should be used directly for min_notional_size
        }
        self.exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        rules = self.async_run_with_timeout(self.exchange._format_trading_rules([rule]))
        self.assertEqual(len(rules), 1)
        trading_rule = rules[0]
        # min_notional should be minVolume (25.0), not minQuantity * minPrice (0.1 * 100 = 10)
        self.assertEqual(trading_rule.min_notional_size, Decimal("25"))
        # collateral_token should be USDT (converted from USD)
        self.assertEqual(trading_rule.buy_order_collateral_token, "USDT")
        self.assertEqual(trading_rule.sell_order_collateral_token, "USDT")

    def test_format_trading_rules_error_path(self):
        self.exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=Exception("boom"))
        rule = {"name": self.ex_trading_pair, "trading": "all", "visibility": "all"}
        rules = self.async_run_with_timeout(self.exchange._format_trading_rules([rule]))
        self.assertEqual(rules, [])

    def test_get_last_traded_price_success_and_error(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange._api_get = AsyncMock(return_value=[{"name": self.ex_trading_pair, "lastPrice": "100"}])
        price = self.async_run_with_timeout(self.exchange._get_last_traded_price(self.trading_pair))
        self.assertEqual(price, 100.0)

        self.exchange._api_get = AsyncMock(side_effect=Exception("boom"))
        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.exchange._get_last_traded_price(self.trading_pair))

    def test_update_positions_sets_and_removes(self):
        self.exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.exchange._perpetual_trading.set_position = MagicMock()
        self.exchange._perpetual_trading.remove_position = MagicMock()
        self.exchange._api_get = AsyncMock(return_value={
            "list": [
                {"instrument": self.ex_trading_pair, "quantity": "1", "side": "BUY", "leverage": "2"},
                {"instrument": self.ex_trading_pair, "quantity": "0", "side": "BUY", "leverage": "2"},
            ]
        })
        self.async_run_with_timeout(self.exchange._update_positions())
        self.exchange._perpetual_trading.set_position.assert_called()
        self.exchange._perpetual_trading.remove_position.assert_called()

    def test_update_positions_sets_short_amount_as_negative(self):
        from hummingbot.core.data_type.common import PositionSide

        self.exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.exchange._api_get = AsyncMock(return_value={
            "list": [
                {
                    "instrument": self.ex_trading_pair,
                    "quantity": "2",
                    "side": "SELL",
                    "avgPrice": "100",
                    "leverage": "2",
                    "unRealizedPnL": "-3",
                }
            ]
        })

        self.async_run_with_timeout(self.exchange._update_positions())

        pos_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.SHORT)
        position = self.exchange._perpetual_trading.account_positions[pos_key]

        self.assertEqual(position.position_side, PositionSide.SHORT)
        self.assertEqual(position.amount, Decimal("-2"))

    def test_update_order_fills_from_trades_processes_fill(self):
        self.exchange._last_poll_timestamp = 0
        self.exchange._set_current_timestamp(self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2)
        order_id = "EX1"
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange._api_get = AsyncMock(return_value={
            "list": [{
                "order": order_id,
                "id": "E1",
                "fillPrice": "10",
                "fillQuantity": "1",
                "createdAt": "2026-02-09T01:24:54.937Z",
            }]
        })
        self.exchange._order_tracker.process_trade_update = MagicMock()
        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())
        self.exchange._order_tracker.process_trade_update.assert_called()

    def test_update_order_fills_from_trades_preserves_open_short_position_action(self):
        self.exchange._last_poll_timestamp = 0
        self.exchange._set_current_timestamp(self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2)
        order_id = "EX_SHORT_FILL"
        self.exchange.start_tracking_order(
            order_id="OID_SHORT_FILL",
            exchange_order_id=order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            price=Decimal("10"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange._api_get = AsyncMock(return_value={
            "list": [{
                "order": order_id,
                "id": "E_SHORT",
                "fillPrice": "10",
                "fillQuantity": "1",
                "createdAt": "2026-02-09T01:24:54.937Z",
            }]
        })
        self.exchange._order_tracker.process_trade_update = MagicMock()

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        trade_update = self.exchange._order_tracker.process_trade_update.call_args.args[0]
        self.assertIsInstance(trade_update.fee, AddedToCostTradeFee)

    def test_update_order_fills_from_trades_dedupes_fill_seen_on_user_stream(self):
        self.exchange._last_poll_timestamp = 0
        self.exchange._set_current_timestamp(self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2)
        order_id = "EX_DEDUPE"
        self.exchange.start_tracking_order(
            order_id="OID_DEDUPE",
            exchange_order_id=order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            price=Decimal("10"),
            amount=Decimal("2"),
            position_action=PositionAction.OPEN,
        )
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)

        fill_data = {
            "id": order_id,
            "status": "PARTIALLY_FILLED",
            "fillPrice": "10",
            "fillQuantity": "1",
            "createdAt": "2026-02-09T01:24:54.937Z",
            "updatedAt": "2026-02-09T01:24:54.937Z",
        }
        self.async_run_with_timeout(self.exchange._process_order_fill(fill_data))

        tracked_order = self.exchange._order_tracker.fetch_tracked_order("OID_DEDUPE")
        self.assertEqual(Decimal("1"), tracked_order.executed_amount_base)
        self.assertEqual(1, len(tracked_order.order_fills))

        self.exchange._api_get = AsyncMock(return_value={
            "list": [{
                "order": order_id,
                "id": "REST_FILL_1",
                "fillPrice": "10",
                "fillQuantity": "1",
                "createdAt": "2026-02-09T01:24:54.937Z",
            }]
        })

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        tracked_order = self.exchange._order_tracker.fetch_tracked_order("OID_DEDUPE")
        self.assertEqual(Decimal("1"), tracked_order.executed_amount_base)
        self.assertEqual(1, len(tracked_order.order_fills))

    def test_update_order_status_processes_update(self):
        self.exchange._last_poll_timestamp = 0
        self.exchange._set_current_timestamp(self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2)
        order_id = "EX2"
        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id=order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        self.exchange._api_get = AsyncMock(return_value={"id": order_id, "status": "FILLED"})
        self.exchange._order_tracker.process_order_update = MagicMock()
        self.async_run_with_timeout(self.exchange._update_order_status())
        self.exchange._order_tracker.process_order_update.assert_called()

    def test_update_order_status_handles_error(self):
        self.exchange._last_poll_timestamp = 0
        self.exchange._set_current_timestamp(self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2)
        self.exchange.start_tracking_order(
            order_id="OID3",
            exchange_order_id="EX3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        self.exchange._api_get = AsyncMock(side_effect=Exception("boom"))
        self.async_run_with_timeout(self.exchange._update_order_status())

    def test_get_position_mode_and_set_mode(self):
        mode = self.async_run_with_timeout(self.exchange._get_position_mode())
        self.assertEqual(mode, PositionMode.ONEWAY)
        result, msg = self.async_run_with_timeout(self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair))
        self.assertTrue(result)
        self.assertEqual(msg, "")
        result, msg = self.async_run_with_timeout(self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair))
        self.assertFalse(result)
        self.assertNotEqual(msg, "")

    def test_set_trading_pair_leverage_success_and_error(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange._api_put = AsyncMock(return_value={"leverage": 3})
        result, msg = self.async_run_with_timeout(self.exchange._set_trading_pair_leverage(self.trading_pair, 3))
        self.assertTrue(result)
        self.assertEqual(msg, "")

        self.exchange._api_put = AsyncMock(side_effect=Exception("boom"))
        result, msg = self.async_run_with_timeout(self.exchange._set_trading_pair_leverage(self.trading_pair, 5))
        self.assertFalse(result)
        self.assertIn("Unable to set leverage", msg)

    def test_fetch_last_fee_payment_success_and_error(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange._api_get = AsyncMock(return_value={"list": [{"coin": self.base_asset, "quantity": "1", "fundingRate": "0.1", "updatedAt": 123}]})
        ts, rate, payment = self.async_run_with_timeout(self.exchange._fetch_last_fee_payment(self.trading_pair))
        self.assertEqual(ts, 123)
        self.assertEqual(rate, Decimal("0.1"))
        self.assertEqual(payment, Decimal("1"))

        self.exchange._api_get = AsyncMock(side_effect=Exception("boom"))
        ts, rate, payment = self.async_run_with_timeout(self.exchange._fetch_last_fee_payment(self.trading_pair))
        self.assertEqual(rate, Decimal("-1"))


class EvedexPerpetualOrderCreationTests(IsolatedAsyncioWrapperTestCase):
    """Test order creation functionality."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.exchange = EvedexPerpetualDerivative(
            evedex_perpetual_api_key="testAPIKey",
            evedex_perpetual_private_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",  # noqa: mock
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )
        self.exchange._set_current_timestamp(1640780000)

    def _limit_order_response(self) -> Dict[str, Any]:
        """Mock response for POST /api/v2/order/limit."""
        return {
            "id": "00001:00000000000000000000000001",
            "user": "user_001",
            "instrument": self.ex_trading_pair,
            "type": "LIMIT",
            "side": "BUY",
            "status": "NEW",
            "rejectedReason": "",
            "quantity": 1.0,
            "limitPrice": 50000.0,
            "stopPrice": None,
            "group": "manually",
            "unFilledQuantity": 1.0,
            "cashQuantity": 50000.0,
            "filledAvgPrice": 0.0,
            "realizedPnL": 0.0,
            "fee": [],
            "triggeredAt": None,
            "exchangeRequestId": "req_123",
            "createdAt": "2024-01-01T00:00:00.000Z",
            "updatedAt": "2024-01-01T00:00:00.000Z"
        }

    def _market_order_response(self) -> Dict[str, Any]:
        """Mock response for POST /api/v2/order/market."""
        return {
            "id": "00001:00000000000000000000000002",
            "user": "user_001",
            "instrument": self.ex_trading_pair,
            "type": "MARKET",
            "side": "BUY",
            "status": "FILLED",
            "rejectedReason": "",
            "quantity": 1.0,
            "limitPrice": None,
            "stopPrice": None,
            "group": "manually",
            "unFilledQuantity": 0.0,
            "cashQuantity": 50000.0,
            "filledAvgPrice": 50000.0,
            "realizedPnL": 0.0,
            "fee": [{"coin": self.quote_asset, "quantity": 10.0}],
            "triggeredAt": None,
            "exchangeRequestId": "req_124",
            "createdAt": "2024-01-01T00:00:00.000Z",
            "updatedAt": "2024-01-01T00:00:00.000Z"
        }

    @aioresponses()
    def test_create_limit_buy_order(self, mock_api):
        """Test limit buy order creation via POST /api/v2/order/limit."""
        url = web_utils.private_rest_url(CONSTANTS.LIMIT_ORDER_PATH_URL)
        mock_api.post(url, body=json.dumps(self._limit_order_response()))

        # Set up trading rules
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
        )

        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("50000"),
            position_action=PositionAction.OPEN
        )

        self.assertIsNotNone(order_id)

    @aioresponses()
    def test_create_limit_sell_order(self, mock_api):
        """Test limit sell order creation."""
        response = self._limit_order_response()
        response["side"] = "SELL"
        url = web_utils.private_rest_url(CONSTANTS.LIMIT_ORDER_PATH_URL)
        mock_api.post(url, body=json.dumps(response))

        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
        )

        order_id = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("50000"),
            position_action=PositionAction.CLOSE
        )

        self.assertIsNotNone(order_id)


class EvedexPerpetualPositionTests(IsolatedAsyncioWrapperTestCase):
    """Test position management functionality."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.exchange = EvedexPerpetualDerivative(
            evedex_perpetual_api_key="testAPIKey",
            evedex_perpetual_private_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",  # noqa: mock
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )
        self.exchange._set_current_timestamp(1640780000)

    def _positions_response(self) -> Dict[str, Any]:
        """Mock response for GET /api/position."""
        return {
            "list": [
                {
                    "id": "pos_123456",
                    "user": "user_001",
                    "instrument": self.ex_trading_pair,
                    "quantity": 1.0,
                    "entryPrice": 49000.0,
                    "markPrice": 50000.0,
                    "liquidationPrice": 45000.0,
                    "leverage": 10,
                    "unrealizedPnL": 1000.0,
                    "realizedPnL": 0.0,
                    "marginMode": "CROSS",
                    "side": "LONG",
                    "createdAt": "2024-01-01T00:00:00.000Z",
                    "updatedAt": "2024-01-01T00:00:00.000Z"
                }
            ],
            "count": 1
        }

    def test_position_mode_is_oneway(self):
        """Test that Evedex uses one-way position mode."""
        self.assertEqual(self.exchange._position_mode, PositionMode.ONEWAY)


class EvedexPerpetualWebSocketTests(IsolatedAsyncioWrapperTestCase):
    """Test WebSocket functionality with Centrifuge protocol."""
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.user_exchange_id = "12345"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.exchange = EvedexPerpetualDerivative(
            evedex_perpetual_api_key="testAPIKey",
            evedex_perpetual_private_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",  # noqa: mock
            trading_pairs=[self.trading_pair],
            domain=CONSTANTS.DEFAULT_DOMAIN,
        )
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine, timeout: float = 5):
        return self.local_event_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def _order_ws_update(self, status: str = "NEW") -> Dict[str, Any]:
        """
        Mock WebSocket message from order-{userExchangeId} channel.
        """
        return {
            "channel": f"order-{self.user_exchange_id}",
            "data": {
                "id": "00001:00000000000000000000000001",
                "user": "user_001",
                "instrument": self.ex_trading_pair,
                "type": "LIMIT",
                "side": "BUY",
                "status": status,
                "rejectedReason": "",
                "quantity": 1.0,
                "limitPrice": 50000.0,
                "stopPrice": None,
                "group": "manually",
                "unFilledQuantity": 1.0 if status != "FILLED" else 0.0,
                "cashQuantity": 50000.0,
                "filledAvgPrice": 0.0 if status != "FILLED" else 50000.0,
                "realizedPnL": 0.0,
                "fee": [] if status != "FILLED" else [{"coin": self.quote_asset, "quantity": 10.0}],
                "triggeredAt": None,
                "exchangeRequestId": "req_123",
                "createdAt": "2024-01-01T00:00:00.000Z",
                "updatedAt": "2024-01-01T00:00:00.000Z"
            }
        }

    def _fill_ws_update(self) -> Dict[str, Any]:
        """
        Mock WebSocket message from orderFills-{userExchangeId} channel.
        """
        return {
            "channel": f"orderFills-{self.user_exchange_id}",
            "data": {
                "executionId": "fill_123456",
                "orderId": "00001:00000000000000000000000001",
                "instrumentName": self.ex_trading_pair,
                "side": "BUY",
                "fillPrice": 50000.0,
                "fillQuantity": 1.0,
                "fillValue": 50000.0,
                "fee": [{"coin": self.quote_asset, "quantity": 10.0}],
                "pnl": 0.0,
                "isPnlRealized": False,
                "createdAt": "2024-01-01T00:00:00.000Z"
            }
        }

    def _funding_ws_update(self) -> Dict[str, Any]:
        """
        Mock WebSocket message from funding-{userExchangeId} channel.
        """
        return {
            "channel": f"funding-{self.user_exchange_id}",
            "data": {
                "coin": self.quote_asset.lower(),
                "quantity": "8.0",
                "updatedAt": "2024-01-01T00:00:00.000Z"
            }
        }

    def _position_ws_update(self) -> Dict[str, Any]:
        """
        Mock WebSocket message for position update from position-{userExchangeId} channel.
        """
        return {
            "channel": f"position-{self.user_exchange_id}",
            "data": {
                "instrument": self.ex_trading_pair,
                "quantity": 1.0,
                "entryPrice": 49000.0,
                "markPrice": 50000.0,
                "unrealizedPnL": 1000.0,
                "leverage": 10,
                "side": "LONG",
                "updatedAt": "2024-01-01T00:00:00.000Z"
            }
        }

    def test_centrifuge_channel_naming(self):
        """Test Centrifuge channel naming patterns."""
        order_channel = f"order-{self.user_exchange_id}"
        funding_channel = f"funding-{self.user_exchange_id}"
        fills_channel = f"orderFills-{self.user_exchange_id}"
        orderbook_channel = f"orderBook-{self.ex_trading_pair}-OneTenth"
        trade_channel = f"trade-{self.ex_trading_pair}"

        self.assertEqual(order_channel, "order-12345")
        self.assertEqual(funding_channel, "funding-12345")
        self.assertEqual(fills_channel, "orderFills-12345")
        self.assertEqual(orderbook_channel, f"orderBook-{self.ex_trading_pair}-OneTenth")
        self.assertEqual(trade_channel, f"trade-{self.ex_trading_pair}")

    def test_order_status_values(self):
        """Test all order status values from Swagger API OrderStatus enum."""
        statuses = [
            "INTENTION",
            "NEW",
            "PARTIALLY_FILLED",
            "FILLED",
            "CANCELLED",
            "REJECTED",
            "EXPIRED",
            "REPLACED",
            "ERROR"
        ]
        for status in statuses:
            self.assertIn(status, CONSTANTS.ORDER_STATE)

    def test_fetch_access_token_success(self):
        self.exchange._api_get = AsyncMock(return_value={"token": "abc", "tokenId": "1"})
        result = self.async_run_with_timeout(self.exchange._fetch_access_token())
        self.assertEqual(result["token"], "abc")

    def test_fetch_access_token_failure(self):
        self.exchange._api_get = AsyncMock(side_effect=Exception("boom"))
        result = self.async_run_with_timeout(self.exchange._fetch_access_token())
        self.assertEqual(result, {})
        self.assertTrue(self._is_logged("WARNING", "Failed to fetch access token: boom"))

    def test_get_all_pairs_prices_list_response(self):
        self.exchange._api_get = AsyncMock(return_value=[
            {"name": self.ex_trading_pair, "markPrice": 100.5}
        ])
        result = self.async_run_with_timeout(self.exchange.get_all_pairs_prices())
        self.assertEqual(result, [{"symbol": self.ex_trading_pair, "price": "100.5"}])

    def test_get_all_pairs_prices_single_response(self):
        self.exchange._api_get = AsyncMock(return_value={"name": self.ex_trading_pair, "markPrice": 99.1})
        result = self.async_run_with_timeout(self.exchange.get_all_pairs_prices())
        self.assertEqual(result, [{"symbol": self.ex_trading_pair, "price": "99.1"}])

    def test_generate_order_id_format(self):
        order_id = self.exchange._generate_order_id()
        self.assertRegex(order_id, r"^\d{5}:[0-9a-f]{26}$")

    def test_place_limit_order(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=3)
        self.exchange._api_post = AsyncMock(return_value={"id": "ex_1", "createdAt": "2026-03-24T00:00:00.000Z"})
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_limit_order = MagicMock(return_value="0xsig")

        exchange_order_id, transact_time = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID1",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("100"),
                position_action=PositionAction.OPEN,
            )
        )

        self.assertEqual(exchange_order_id, "ex_1")
        self.assertEqual(transact_time, 1774310400.0)
        call_kwargs = self.exchange._api_post.call_args.kwargs
        self.assertEqual(call_kwargs["path_url"], CONSTANTS.LIMIT_ORDER_PATH_URL)
        self.assertEqual(call_kwargs["data"]["leverage"], 3)
        self.assertEqual(call_kwargs["data"]["quantity"], "1")
        self.assertEqual(call_kwargs["data"]["limitPrice"], "100")
        self.assertEqual(call_kwargs["data"]["signature"], "0xsig")

    def test_place_market_order(self):
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=2)
        self.exchange._api_post = AsyncMock(return_value={"id": "ex_2", "createdAt": 456})
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_market_order = MagicMock(return_value="0xsig")

        exchange_order_id, transact_time = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID2",
                trading_pair=self.trading_pair,
                amount=Decimal("2"),
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                price=Decimal("10"),
                position_action=PositionAction.OPEN,
            )
        )

        self.assertEqual(exchange_order_id, "ex_2")
        self.assertEqual(transact_time, 456)
        call_kwargs = self.exchange._api_post.call_args.kwargs
        self.assertEqual(call_kwargs["path_url"], CONSTANTS.MARKET_ORDER_PATH_URL)
        self.assertEqual(Decimal(call_kwargs["data"]["cashQuantity"]), Decimal("20"))
        self.assertEqual(call_kwargs["data"]["signature"], "0xsig")

    def test_place_market_order_uses_order_price_when_price_is_nan(self):
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=2)
        self.exchange.get_order_price = AsyncMock(return_value=Decimal("10"))
        self.exchange._api_post = AsyncMock(return_value={"id": "ex_2b", "createdAt": 456})
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_market_order = MagicMock(return_value="0xsig")

        exchange_order_id, transact_time = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID2B",
                trading_pair=self.trading_pair,
                amount=Decimal("2"),
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                price=Decimal("NaN"),
                position_action=PositionAction.OPEN,
            )
        )

        self.assertEqual(exchange_order_id, "ex_2b")
        self.assertEqual(transact_time, 456)
        call_kwargs = self.exchange._api_post.call_args.kwargs
        self.assertEqual(Decimal(call_kwargs["data"]["cashQuantity"]), Decimal("20"))
        self.exchange.get_order_price.assert_awaited_once_with(
            trading_pair=self.trading_pair,
            is_buy=False,
            amount=Decimal("2"),
        )

    def test_place_market_order_quantizes_cash_quantity_to_price_increment(self):
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.0001"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=2)
        self.exchange._api_post = AsyncMock(return_value={"id": "ex_quantized", "createdAt": 456})
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_market_order = MagicMock(return_value="0xsig")

        exchange_order_id, transact_time = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID2C",
                trading_pair=self.trading_pair,
                amount=Decimal("6.8"),
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                price=Decimal("1.31865"),
                position_action=PositionAction.OPEN,
            )
        )

        self.assertEqual(exchange_order_id, "ex_quantized")
        self.assertEqual(transact_time, 456)
        call_kwargs = self.exchange._api_post.call_args.kwargs
        self.assertEqual(call_kwargs["data"]["cashQuantity"], "8.9668")

    def test_place_limit_maker_order_uses_limit_endpoint(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=3)
        self.exchange._api_post = AsyncMock(return_value={"id": "ex_limit_maker", "createdAt": 123})
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_limit_order = MagicMock(return_value="0xsig")

        exchange_order_id, transact_time = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID_LIMIT_MAKER",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT_MAKER,
                price=Decimal("10"),
                position_action=PositionAction.OPEN,
            )
        )

        self.assertEqual(exchange_order_id, "ex_limit_maker")
        self.assertEqual(transact_time, 123)
        call_kwargs = self.exchange._api_post.call_args.kwargs
        self.assertEqual(call_kwargs["path_url"], CONSTANTS.LIMIT_ORDER_PATH_URL)
        self.assertEqual(call_kwargs["data"]["timeInForce"], CONSTANTS.TIME_IN_FORCE_GTC)
        self.assertEqual(call_kwargs["data"]["limitPrice"], "10")
        self.assertEqual(call_kwargs["data"]["signature"], "0xsig")

    def test_place_limit_close_order_uses_limit_endpoint(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=4)
        self.exchange._api_post = AsyncMock(return_value={"id": "ex_3", "createdAt": 789})
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_limit_order = MagicMock(return_value="0xsig")

        exchange_order_id, transact_time = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID3",
                trading_pair=self.trading_pair,
                amount=Decimal("3"),
                trade_type=TradeType.SELL,
                order_type=OrderType.LIMIT,
                price=Decimal("10"),
                position_action=PositionAction.CLOSE,
            )
        )

        self.assertEqual(exchange_order_id, "ex_3")
        self.assertEqual(transact_time, 789)
        call_kwargs = self.exchange._api_post.call_args.kwargs
        self.assertEqual(call_kwargs["path_url"], CONSTANTS.LIMIT_ORDER_PATH_URL)
        self.assertEqual(call_kwargs["data"]["side"], CONSTANTS.SIDE_SELL)
        self.assertEqual(call_kwargs["data"]["quantity"], "3")
        self.assertEqual(call_kwargs["data"]["limitPrice"], "10")
        self.assertEqual(call_kwargs["data"]["timeInForce"], CONSTANTS.TIME_IN_FORCE_GTC)
        self.assertEqual(call_kwargs["data"]["signature"], "0xsig")

    def test_place_market_close_order_uses_close_position_endpoint(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=4)
        self.exchange._api_post = AsyncMock(return_value={"id": "ex_4", "createdAt": 987})
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_position_close = MagicMock(return_value="0xsig")

        exchange_order_id, transact_time = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID4",
                trading_pair=self.trading_pair,
                amount=Decimal("3"),
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                price=Decimal("10"),
                position_action=PositionAction.CLOSE,
            )
        )

        self.assertEqual(exchange_order_id, "ex_4")
        self.assertEqual(transact_time, 987)
        call_kwargs = self.exchange._api_post.call_args.kwargs
        self.assertEqual(
            call_kwargs["path_url"],
            CONSTANTS.CLOSE_POSITION_PATH_URL.format(instrument=self.ex_trading_pair),
        )
        self.assertEqual(call_kwargs["data"]["signature"], "0xsig")

    def test_place_order_handles_503(self):
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=1)
        self.exchange._api_post = AsyncMock(side_effect=IOError("503 Service Unavailable"))
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_limit_order = MagicMock(return_value="0xsig")

        exchange_order_id, _ = self.async_run_with_timeout(
            self.exchange._place_order(
                order_id="OID4",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("100"),
                position_action=PositionAction.OPEN,
            )
        )

        self.assertEqual(exchange_order_id, "UNKNOWN")

    def test_place_cancel(self):
        order = InFlightOrder(
            client_order_id="OIDC",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=self.exchange.current_timestamp,
        )
        self.exchange._api_delete = AsyncMock()
        result = self.async_run_with_timeout(self.exchange._place_cancel("OIDC", order))
        self.assertTrue(result)
        self.exchange._api_delete.assert_called_once()

    def test_all_trade_updates_for_order(self):
        order = InFlightOrder(
            client_order_id="OIDT",
            exchange_order_id="200",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("10"),
            creation_timestamp=self.exchange.current_timestamp,
        )
        self.exchange._api_get = AsyncMock(return_value={
            "list": [
                {
                    "id": "200",
                    "exchangeRequestId": "req_1",
                    "quantity": "2",
                    "unFilledQuantity": "0",
                    "filledAvgPrice": "10",
                    "fee": [
                        {"coin": "usdt", "quantity": "0.1"},
                        {"coin": "total", "quantity": "0"}
                    ]
                }
            ]
        })
        updates = self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].trade_id, "req_1")
        self.assertEqual(updates[0].fee.flat_fees[0].token, "USDT")
        self.exchange._api_get.assert_called_once_with(
            path_url=CONSTANTS.GET_ORDERS_PATH_URL,
            params={"status": "FILLED", "offset": 0, "limit": 500},
            is_auth_required=True,
            limit_id=CONSTANTS.GET_ORDERS_PATH_URL,
        )

    def test_all_trade_updates_for_order_preserves_open_short_position_action(self):
        order = InFlightOrder(
            client_order_id="OIDT_SHORT",
            exchange_order_id="201",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal("1"),
            price=Decimal("10"),
            creation_timestamp=self.exchange.current_timestamp,
            position=PositionAction.OPEN,
        )
        self.exchange._api_get = AsyncMock(return_value={
            "list": [
                {
                    "id": "201",
                    "exchangeRequestId": "req_short",
                    "quantity": "2",
                    "unFilledQuantity": "0",
                    "filledAvgPrice": "10",
                    "fee": [
                        {"coin": "usdt", "quantity": "0.1"},
                    ]
                }
            ]
        })

        updates = self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))

        self.assertEqual(len(updates), 1)
        self.assertIsInstance(updates[0].fee, AddedToCostTradeFee)

    def test_request_order_status(self):
        order = InFlightOrder(
            client_order_id="OIDU",
            exchange_order_id="300",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal("1"),
            price=Decimal("10"),
            creation_timestamp=self.exchange.current_timestamp,
        )
        self.exchange._api_get = AsyncMock(return_value={"id": "300", "status": "CANCELLED"})
        order_update = self.async_run_with_timeout(self.exchange._request_order_status(order))
        self.assertEqual(order_update.new_state, OrderState.CANCELED)

    def test_process_user_stream_event_order_update(self):
        self.exchange._process_order_update = AsyncMock()
        event_message = {
            "push": {"channel": "futures-perp:order:123", "pub": {"data": {"id": "1"}}}
        }
        self.async_run_with_timeout(self.exchange._process_user_stream_event(event_message))
        self.exchange._process_order_update.assert_awaited_once()

    def test_process_user_stream_event_order_filled(self):
        self.exchange._process_order_fill = AsyncMock()
        event_message = {
            "push": {"channel": "futures-perp:orderFilled:123", "pub": {"data": {"id": "1"}}}
        }
        self.async_run_with_timeout(self.exchange._process_user_stream_event(event_message))
        self.exchange._process_order_fill.assert_awaited_once()

    def test_process_user_stream_event_user_update_is_ignored(self):
        self.exchange._process_order_update = AsyncMock()
        self.exchange._process_position_update = AsyncMock()
        self.exchange._process_order_fill = AsyncMock()
        event_message = {
            "push": {"channel": "futures-perp:user:123", "pub": {"data": {"id": "1"}}}
        }

        self.async_run_with_timeout(self.exchange._process_user_stream_event(event_message))

        self.exchange._process_order_update.assert_not_awaited()
        self.exchange._process_position_update.assert_not_awaited()
        self.exchange._process_order_fill.assert_not_awaited()

    def test_process_user_stream_event_funding_update_is_ignored(self):
        self.exchange._process_order_update = AsyncMock()
        self.exchange._process_position_update = AsyncMock()
        self.exchange._process_order_fill = AsyncMock()
        event_message = {
            "push": {"channel": "futures-perp:funding:123", "pub": {"data": {"coin": "usdt", "quantity": "1"}}}
        }

        self.async_run_with_timeout(self.exchange._process_user_stream_event(event_message))

        self.exchange._process_order_update.assert_not_awaited()
        self.exchange._process_position_update.assert_not_awaited()
        self.exchange._process_order_fill.assert_not_awaited()

    @aioresponses()
    def test_update_positions_removes_stale_positions(self, mock_api):
        """Test that _update_positions removes positions that no longer exist on exchange."""
        # First, set up a position in the connector's state
        from hummingbot.connector.derivative.position import Position
        from hummingbot.core.data_type.common import PositionSide

        pos_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.LONG)
        stale_position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal("100"),
            entry_price=Decimal("50000"),
            amount=Decimal("1"),
            leverage=Decimal("10"),
        )
        self.exchange._perpetual_trading.set_position(pos_key, stale_position)

        # Verify position exists
        self.assertIn(pos_key, self.exchange._perpetual_trading.account_positions)

        # Mock the exchange response with empty positions list (position closed on exchange)
        positions_url = web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL)
        mock_api.get(positions_url, body=json.dumps({"list": [], "count": 0}))

        # Mock trading pair symbol mapping
        self.exchange._set_trading_pair_symbol_map(
            {self.ex_trading_pair: self.trading_pair}
        )

        # Run update_positions
        self.async_run_with_timeout(self.exchange._update_positions())

        # Verify position was removed
        self.assertNotIn(pos_key, self.exchange._perpetual_trading.account_positions)

    def test_place_order_insufficient_funds_error(self):
        """Test that insufficient funds error triggers balance refresh and raises ValueError."""
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=1)
        self.exchange._update_balances = AsyncMock()
        self.exchange._api_post = AsyncMock(side_effect=IOError("400 Insufficient funds for order"))
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_limit_order = MagicMock(return_value="0xsig")

        with self.assertRaises(ValueError) as context:
            self.async_run_with_timeout(
                self.exchange._place_order(
                    order_id="OID_INSUFFICIENT",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.LIMIT,
                    price=Decimal("10"),
                    position_action=PositionAction.OPEN,
                )
            )

        self.assertIn("Insufficient funds", str(context.exception))
        # Balance refresh should be scheduled (via safe_ensure_future)

    def test_place_order_too_many_quantity_error(self):
        """Test that 'Too many quantity' error triggers position refresh and raises ValueError."""
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=1)
        position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal("0"),
            entry_price=Decimal("10"),
            amount=Decimal("1"),
            leverage=Decimal("1"),
        )
        position_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.LONG)
        self.exchange._perpetual_trading.set_position(position_key, position)
        self.exchange._update_positions = AsyncMock()
        self.exchange._api_post = AsyncMock(side_effect=IOError("400 Too many quantity"))
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_position_close = MagicMock(return_value="0xsig")

        with self.assertRaises(ValueError) as context:
            self.async_run_with_timeout(
                self.exchange._place_order(
                    order_id="OID_TOO_MANY",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.SELL,
                    order_type=OrderType.MARKET,
                    price=Decimal("10"),
                    position_action=PositionAction.CLOSE,
                )
            )

        self.assertIn("Position error", str(context.exception))

    def test_place_order_unknown_position_error(self):
        """Test that 'Unknown position' error triggers position refresh and raises ValueError."""
        self.exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.exchange.get_leverage = MagicMock(return_value=1)
        position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal("0"),
            entry_price=Decimal("10"),
            amount=Decimal("1"),
            leverage=Decimal("1"),
        )
        position_key = self.exchange._perpetual_trading.position_key(self.trading_pair, PositionSide.LONG)
        self.exchange._perpetual_trading.set_position(position_key, position)
        self.exchange._update_positions = AsyncMock()
        self.exchange._api_post = AsyncMock(side_effect=IOError("400 Unknown position"))
        self.exchange._auth = MagicMock()
        self.exchange._auth.wallet_address = "0xabc"
        self.exchange._auth.sign_position_close = MagicMock(return_value="0xsig")

        with self.assertRaises(ValueError) as context:
            self.async_run_with_timeout(
                self.exchange._place_order(
                    order_id="OID_UNKNOWN_POS",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.SELL,
                    order_type=OrderType.MARKET,
                    price=Decimal("10"),
                    position_action=PositionAction.CLOSE,
                )
            )

        self.assertIn("Position error", str(context.exception))


if __name__ == "__main__":
    import unittest
    unittest.main()
