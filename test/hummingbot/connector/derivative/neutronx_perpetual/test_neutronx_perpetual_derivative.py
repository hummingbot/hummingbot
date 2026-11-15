import asyncio
import math
import re
from datetime import datetime, timezone
from decimal import Decimal
from test.hummingbot.connector.derivative.neutronx_perpetual.fixtures import (
    ACCOUNT,
    BLOCK_TIME,
    FILL_FEE,
    INDEXER_URL,
    NETWORK,
    FakeDataSource,
    chain_order,
    chain_position,
    fill_json,
    frame,
    market,
    order_json,
)
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, PropertyMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall
from neutronx_sdk import OrderType as ChainOrderType, Side, TimeInForce
from neutronx_sdk.indexer import FillV1, StreamFrame

from hummingbot.connector.derivative.neutronx_perpetual import neutronx_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.neutronx_perpetual.data_sources import translators
from hummingbot.connector.derivative.neutronx_perpetual.data_sources.tx_queue import CancelOutcome, PlacedOrder
from hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_derivative import NeutronxPerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.network_iterator import NetworkStatus

PAIR = "BTC-USDC"
NOW = 1640780000
NOW_ISO = datetime.fromtimestamp(NOW, tz=timezone.utc).isoformat()
STATUS_URL = f"{INDEXER_URL}/status"
TICKERS_URL = f"{INDEXER_URL}/markets/tickers"
FILLS_URL = re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/fills.*")
ORDERS_URL = re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/orders.*")
FUNDING_URL = re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/funding.*")
SAFE_ENSURE_FUTURE = "hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_derivative.safe_ensure_future"
EMPTY_PAGE: Dict[str, Any] = {"items": [], "next_cursor": None}


class NeutronxPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = CONSTANTS.QUOTE_ASSET
        cls.trading_pair = PAIR

    def setUp(self) -> None:
        self.data_source = FakeDataSource()
        super().setUp()
        self.connector = self.exchange

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await self.exchange._update_trading_rules()

    def create_exchange_instance(self) -> NeutronxPerpetualDerivative:
        return NeutronxPerpetualDerivative(
            neutronx_perpetual_account_address=ACCOUNT,
            trading_pairs=[PAIR],
            trading_required=True,
            network=NETWORK,
            data_source=self.data_source,
        )

    @property
    def all_symbols_url(self) -> str:
        return STATUS_URL

    @property
    def latest_prices_url(self) -> str:
        return TICKERS_URL

    @property
    def network_status_url(self) -> str:
        return STATUS_URL

    @property
    def trading_rules_url(self) -> str:
        return STATUS_URL

    @property
    def order_creation_url(self) -> str:
        return STATUS_URL

    @property
    def balance_url(self) -> str:
        return STATUS_URL

    @property
    def funding_info_url(self) -> str:
        return TICKERS_URL

    @property
    def funding_payment_url(self) -> re.Pattern:
        return FUNDING_URL

    @property
    def all_symbols_request_mock_response(self) -> Dict[str, Any]:
        return {}

    @property
    def latest_prices_request_mock_response(self) -> List[Dict[str, Any]]:
        return [{"pair": "BTCUSDC", "last_price": str(self.expected_latest_price)}]

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Dict[str, Any]]:
        return "OLD-USDC", {}

    @property
    def network_status_request_successful_mock_response(self) -> Dict[str, Any]:
        return self._status(1)

    @property
    def trading_rules_request_mock_response(self) -> Dict[str, Any]:
        return {}

    @property
    def trading_rules_request_erroneous_mock_response(self) -> Dict[str, Any]:
        return {}

    @property
    def order_creation_request_successful_mock_response(self) -> Dict[str, Any]:
        return {}

    @property
    def balance_request_mock_response_for_base_and_quote(self) -> Dict[str, Any]:
        return {}

    @property
    def balance_request_mock_response_only_base(self) -> Dict[str, Any]:
        return {}

    @property
    def balance_event_websocket_update(self) -> Dict[str, Any]:
        return frame("balances", [])

    @property
    def funding_info_mock_response(self) -> List[Dict[str, Any]]:
        return [self._ticker(
            self.target_funding_info_mark_price,
            self.target_funding_info_rate,
            self.target_funding_info_next_funding_utc_timestamp,
        )]

    @property
    def empty_funding_payment_mock_response(self) -> Dict[str, Any]:
        return EMPTY_PAGE

    @property
    def funding_payment_mock_response(self) -> Dict[str, Any]:
        payment = {
            "position_id": 1,
            "subaccount_id": 0,
            "pair": "BTCUSDC",
            "side": "LONG",
            "quantity": "1",
            "amount": str(self.target_funding_payment_payment_amount),
            "rate": str(self.target_funding_payment_funding_rate),
            "mark_price": "10000",
            "block_height": 8,
            "time": datetime.fromtimestamp(self.target_funding_payment_timestamp, tz=timezone.utc).isoformat(),
        }
        return {"items": [payment], "next_cursor": None}

    @property
    def target_funding_info_index_price(self) -> int:
        return self.target_funding_info_mark_price

    @property
    def expected_latest_price(self) -> float:
        return 9999.9

    @property
    def expected_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def expected_trading_rule(self) -> TradingRule:
        return translators.trading_rule(market(), Decimal(self.data_source.params.min_order_notional))

    @property
    def expected_logged_error_for_erroneous_trading_rule(self) -> str:
        return ""

    @property
    def expected_exchange_order_id(self) -> str:
        return str(self.data_source.place_result.order_id)

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return self._fill_fee(PositionAction.OPEN)

    @property
    def expected_fill_trade_id(self) -> str:
        return "30000:1"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}/{quote_token}"

    def validate_auth_credentials_present(self, request_call: RequestCall) -> None:
        self.assertNotIn("Authorization", request_call.kwargs.get("headers") or {})

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall) -> None:
        raise NotImplementedError

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall) -> None:
        raise NotImplementedError

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall) -> None:
        raise NotImplementedError

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall) -> None:
        self.assertEqual(
            {"pair": translators.to_exchange_pair(order.trading_pair), "limit": CONSTANTS.HISTORY_PAGE_LIMIT},
            request_call.kwargs["params"],
        )

    def configure_all_symbols_response(self, mock_api: aioresponses, callback: Optional[Callable] = None) -> List[str]:
        return []

    def configure_trading_rules_response(
        self, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> List[str]:
        return []

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> str:
        self._expect_cancel(order, callback)
        self.data_source.orders[int(order.exchange_order_id)] = self._chain_order(order, "CANCELLED")
        return ""

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> str:
        self._expect_cancel(order, callback)
        self.data_source.cancel_errors[int(order.exchange_order_id)] = IOError("the node refused the transaction")
        return ""

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> str:
        self._expect_cancel(order, callback)
        self.data_source.cancel_outcomes[int(order.exchange_order_id)] = CancelOutcome.REJECTED
        return ""

    def configure_one_successful_one_erroneous_cancel_all_response(
        self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        self.configure_successful_cancelation_response(successful_order, mock_api)
        self.configure_erroneous_cancelation_response(erroneous_order, mock_api)
        return []

    def configure_completely_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> List[str]:
        self._expect_missing_from_open_orders(order, callback)
        self.data_source.orders[int(order.exchange_order_id)] = self._chain_order(order, "FILLED", filled=order.amount)
        return []

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> List[str]:
        self._expect_missing_from_open_orders(order, callback)
        self.data_source.orders[int(order.exchange_order_id)] = self._chain_order(order, "CANCELLED")
        return []

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> List[str]:
        self.data_source.open_orders_result = (self._chain_order(order, "OPEN"),)
        return []

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> str:
        self._expect_missing_from_open_orders(order, callback)
        self.data_source.order_error = IOError("the node is unreachable")
        return ""

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> str:
        filled = self.expected_partial_fill_amount
        self.data_source.open_orders_result = (self._chain_order(order, "PARTIALLY_FILLED", filled=filled),)
        return ""

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> List[str]:
        self._expect_missing_from_open_orders(order)
        mock_api.get(ORDERS_URL, payload=EMPTY_PAGE, callback=callback)
        return []

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> re.Pattern:
        fill = self._fill(order, str(self.expected_partial_fill_amount), str(self.expected_partial_fill_price))
        mock_api.get(FILLS_URL, payload={"items": [fill], "next_cursor": None}, callback=callback)
        return FILLS_URL

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> re.Pattern:
        mock_api.get(FILLS_URL, status=400, callback=callback)
        return FILLS_URL

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> re.Pattern:
        fill = self._fill(order, str(order.amount), str(order.price))
        mock_api.get(FILLS_URL, payload={"items": [fill], "next_cursor": None}, callback=callback)
        return FILLS_URL

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return self._order_frame(order, "OPEN")

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return self._order_frame(order, "CANCELLED")

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return self._order_frame(order, "FILLED", filled=str(order.amount))

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return frame("fills", [self._fill(order, str(order.amount), str(order.price))], "update")

    def position_event_for_full_fill_websocket_update(
        self, order: InFlightOrder, unrealized_pnl: float
    ) -> Dict[str, Any]:
        position = {
            "id": 1,
            "subaccount_id": 0,
            "pair": "BTCUSDC",
            "side": "LONG" if order.trade_type is TradeType.BUY else "SHORT",
            "status": "OPEN",
            "quantity": str(order.amount),
            "entry_price": str(order.price),
            "leverage": str(self.exchange.get_leverage(order.trading_pair)),
            "unrealized_pnl": str(unrealized_pnl),
        }
        return frame("positions", [position], "update")

    def funding_info_event_for_websocket_update(self) -> Dict[str, Any]:
        ticker = self._ticker(
            self.target_funding_info_mark_price_ws_updated,
            self.target_funding_info_rate_ws_updated,
            self.target_funding_info_next_funding_utc_timestamp_ws_updated,
        )
        return frame("ticker", ticker, "update", stream_id="BTC/USDC")

    def configure_successful_set_position_mode(
        self, position_mode: PositionMode, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> None:
        return None

    def configure_failed_set_position_mode(
        self, position_mode: PositionMode, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> Tuple[str, str]:
        return "", f"Position mode {position_mode} is not supported. Mode not set."

    def configure_successful_set_leverage(
        self, leverage: int, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> None:
        if callback is not None:
            callback()

    def configure_failed_set_leverage(
        self, leverage: int, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> Tuple[str, str]:
        capped = market(max_leverage=leverage - 1)
        self.exchange._markets[PAIR] = capped
        if callback is not None:
            callback()
        return "", f"leverage on {PAIR} must be between 1 and {capped.max_leverage}"

    def _expected_valid_trading_pairs(self) -> List[str]:
        return [PAIR, "ETH-USDC"]

    def _expect_cancel(self, order: InFlightOrder, callback: Optional[Callable]) -> None:
        self.data_source.on_cancel = callback
        self.data_source.open_orders_result = (self._chain_order(order, "OPEN"),)

    def _expect_missing_from_open_orders(self, order: InFlightOrder, callback: Optional[Callable] = None) -> None:
        order.creation_timestamp = self.exchange.current_timestamp - 2 * CONSTANTS.ORDER_VISIBILITY_GRACE_SECONDS
        self.data_source.on_order = callback

    @staticmethod
    def _chain_order(order: InFlightOrder, status: str, filled: Decimal = Decimal(0)):
        return chain_order(int(order.exchange_order_id), status, quantity=str(order.amount), filled=str(filled))

    @staticmethod
    def _order_frame(order: InFlightOrder, status: str, filled: str = "0") -> Dict[str, Any]:
        row = order_json(int(order.exchange_order_id), status, filled, quantity=str(order.amount))
        return frame("orders", [row], "update")

    def _fill(self, order: InFlightOrder, quantity: str, price: str) -> Dict[str, Any]:
        return fill_json(
            self.expected_fill_trade_id, int(order.exchange_order_id), quantity=quantity, price=price, time=NOW_ISO
        )

    def _fill_fee(self, position_action: PositionAction) -> TradeFeeBase:
        return TradeFeeBase.new_perpetual_fee(
            fee_schema=self.exchange.trade_fee_schema(),
            position_action=position_action,
            percent_token=CONSTANTS.QUOTE_ASSET,
            flat_fees=[TokenAmount(token=CONSTANTS.QUOTE_ASSET, amount=Decimal(FILL_FEE))],
        )

    @staticmethod
    def _ticker(mark_price: int, funding_rate: int, next_funding: int) -> Dict[str, Any]:
        return {
            "pair": "BTCUSDC",
            "mark_price": str(mark_price),
            "funding_rate": str(funding_rate),
            "next_funding_at": datetime.fromtimestamp(next_funding, tz=timezone.utc).isoformat(),
        }

    @staticmethod
    async def _settle():
        for _ in range(5):
            await asyncio.sleep(0)

    @staticmethod
    def _requests(mock: aioresponses) -> int:
        return sum(len(calls) for calls in mock.requests.values())

    def _track(self, client_id: str, exchange_id: str = "555", amount: str = "0.01", order_type=OrderType.LIMIT):
        self.connector.start_tracking_order(
            order_id=client_id,
            exchange_order_id=exchange_id,
            trading_pair=PAIR,
            trade_type=TradeType.BUY,
            price=Decimal(65000),
            amount=Decimal(amount),
            order_type=order_type,
            position_action=PositionAction.OPEN,
            leverage=Decimal(3),
        )
        return self.connector.in_flight_orders[client_id]

    def test_initial_status_dict(self):
        self.exchange._trading_rules.clear()
        super().test_initial_status_dict()

    async def test_all_trading_pairs_does_not_raise_exception(self):
        self.exchange._set_trading_pair_symbol_map(None)
        self.data_source.markets_error = IOError("the node is unreachable")
        self.assertEqual([], await self.exchange.all_trading_pairs())

    async def test_update_trading_rules_ignores_rule_with_error(self):
        self.data_source.markets_result = (market(status="DELISTED"),)
        await self.exchange._update_trading_rules()
        self.assertEqual({}, self.exchange.trading_rules)

    async def test_create_buy_limit_order_successfully(self):
        await self._create_order(self.place_buy_order, TradeType.BUY, 2, PositionAction.OPEN)

    async def test_create_sell_limit_order_successfully(self):
        await self._create_order(self.place_sell_order, TradeType.SELL, 3, PositionAction.OPEN)

    async def test_create_order_to_close_short_position(self):
        await self._create_order(self.place_buy_order, TradeType.BUY, 4, PositionAction.CLOSE)

    async def test_create_order_to_close_long_position(self):
        await self._create_order(self.place_sell_order, TradeType.SELL, 5, PositionAction.CLOSE)

    async def test_create_order_fails_and_raises_failure_event(self):
        self.data_source.place_error = IOError("the node refused the transaction")
        order_id = await self._place(self.place_buy_order)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure = self.order_failure_logger.event_log[0]
        self.assertEqual((NOW, OrderType.LIMIT, order_id), (failure.timestamp, failure.order_type, failure.order_id))
        self.assertTrue(self.is_logged("NETWORK", self._submit_error_log()))

    async def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self):
        self.data_source.place_error = IOError("the node refused the transaction")
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(NOW)
        too_small = self.place_buy_order(amount=Decimal("0.0001"), price=Decimal("0.0001"))
        order_id = await self._place(self.place_buy_order)
        self.assertNotIn(too_small, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure = self.order_failure_logger.event_log[0]
        self.assertEqual((NOW, OrderType.LIMIT, too_small), (failure.timestamp, failure.order_type, failure.order_id))
        self.assertTrue(self.is_logged("NETWORK", self._submit_error_log()))
        self.assertTrue(any(
            record.getMessage().startswith(f"Order {too_small} has failed.")
            and "is lower than minimum order size 0.01" in record.getMessage()
            for record in self.log_records
        ))

    async def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self):
        order = await self._lose_tracked_order()
        with aioresponses() as mock_api:
            self.configure_full_fill_trade_response(order, mock_api)
            self.configure_completely_filled_order_status_response(order, mock_api)
            await self.exchange._update_trade_history()
            await order.wait_until_completely_filled()
            await self._settle()
            self.assertTrue(order.is_done and order.is_failure)
            fill = self.order_filled_logger.event_log[0]
            self.assertEqual((NOW, order.client_order_id, order.price, order.amount),
                             (fill.timestamp, fill.order_id, fill.price, fill.amount))
            self.assertEqual(self.expected_fill_fee, fill.trade_fee)
            await self.exchange._update_lost_orders_status()
            await self._settle()
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled."))

    async def test_update_balances(self):
        await self.exchange._update_balances()
        self.assertEqual({CONSTANTS.QUOTE_ASSET: Decimal(1000)}, self.exchange.get_all_balances())
        self.assertEqual({CONSTANTS.QUOTE_ASSET: Decimal(900)}, self.exchange.available_balances)

    async def test_user_stream_balance_update(self):
        await self.exchange._update_balances()
        queue = AsyncMock()
        queue.get.side_effect = [self.balance_event_websocket_update, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = queue
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange._user_stream_event_listener()
        self.assertEqual(Decimal(1000), self.exchange.get_balance(CONSTANTS.QUOTE_ASSET))
        self.assertEqual(Decimal(900), self.exchange.get_available_balance(CONSTANTS.QUOTE_ASSET))

    async def test_update_order_status_when_request_fails_marks_order_as_not_found(self):
        order = self._track_unit_order()
        self.configure_http_error_order_status_response(order, mock_api=None)
        await self.exchange._update_order_status()
        self.assertTrue(order.is_open)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker._order_not_found_records)
        self.assertTrue(self.is_logged(
            "NETWORK", f"Error refreshing NeutronX order {order.client_order_id}: the node is unreachable"
        ))

    async def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self):
        order = self._track_unit_order()
        with aioresponses() as mock_api:
            self.configure_partial_fill_trade_response(order, mock_api)
            self.configure_partially_filled_order_status_response(order, mock_api)
            await self.exchange._update_order_status()
            await self.exchange._update_trade_history()
            await asyncio.sleep(0.05)
        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)
        fill = self.order_filled_logger.event_log[0]
        self.assertEqual(
            (NOW, order.client_order_id, self.expected_partial_fill_price, self.expected_partial_fill_amount),
            (fill.timestamp, fill.order_id, fill.price, fill.amount),
        )
        self.assertEqual(self.expected_fill_fee, fill.trade_fee)

    async def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self):
        order = self._track_unit_order()
        with aioresponses() as mock_api, patch.object(self.exchange, "_time", return_value=1000.0) as clock:
            mock_api.get(FILLS_URL, status=400, repeat=True)
            self.configure_completely_filled_order_status_response(order, mock_api)
            await self.exchange._update_order_status()
            self.assertTrue(order.is_open)
            self.assertIn(order.client_order_id, self.exchange._settling)
            clock.return_value = 1000.0 + CONSTANTS.FILL_SETTLE_TIMEOUT
            order.completely_filled_event.set()
            await self.exchange._update_order_status()
            await asyncio.sleep(0.05)
        self.assertTrue(order.is_filled)
        self.assertEqual(0, len(self.order_filled_logger.event_log))
        completed = self.buy_order_completed_logger.event_log[0]
        self.assertEqual((order.client_order_id, Decimal(0)), (completed.order_id, completed.base_asset_amount))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._settling)

    def test_set_position_mode_failure(self):
        self.exchange.set_position_mode(PositionMode.HEDGE)
        _, error = self.configure_failed_set_position_mode(PositionMode.HEDGE, mock_api=None)
        self.assertTrue(self.is_logged("ERROR", error))

    async def test_set_position_mode_success(self):
        self.exchange.set_position_mode(PositionMode.ONEWAY)
        await self._settle()
        self.assertTrue(self.is_logged("INFO", f"Position mode switched to {PositionMode.ONEWAY}."))
        self.assertIs(PositionMode.ONEWAY, self.exchange.position_mode)

    async def test_funding_payment_polling_loop_sends_update_event(self):
        self._simulate_trading_rules_initialized()
        with aioresponses() as mock_api:
            mock_api.get(FUNDING_URL, payload=self.empty_funding_payment_mock_response)
            self.async_tasks.append(asyncio.create_task(self.exchange._funding_payment_polling_loop()))
            await asyncio.sleep(0.05)
            self.assertEqual(0, len(self.funding_payment_logger.event_log))
            mock_api.get(FUNDING_URL, payload=self.funding_payment_mock_response, repeat=True)
            for _ in range(2):
                self.exchange._funding_fee_poll_notifier.set()
                await asyncio.sleep(0.05)
        self.assertEqual(1, len(self.funding_payment_logger.event_log))
        event = self.funding_payment_logger.event_log[0]
        self.assertEqual(
            (self.target_funding_payment_timestamp, self.exchange.name, PAIR,
             self.target_funding_payment_payment_amount, self.target_funding_payment_funding_rate),
            (event.timestamp, event.market, event.trading_pair, event.amount, event.funding_rate),
        )

    async def _place(self, place: Callable[..., str], **kwargs) -> str:
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(NOW)
        sent = asyncio.Event()
        self.data_source.on_place = sent.set
        order_id = place(**kwargs)
        await asyncio.wait_for(sent.wait(), timeout=1)
        await self._settle()
        return order_id

    async def _create_order(
        self, place: Callable[..., str], trade_type: TradeType, leverage: int, position_action: PositionAction
    ) -> None:
        self.exchange._perpetual_trading.set_leverage(PAIR, leverage)
        order_id = await self._place(place, position_action=position_action)
        request = self.data_source.placed[0]
        self.assertEqual(
            (int(order_id), translators.to_side(trade_type), Decimal(10000), Decimal(100), Decimal(leverage)),
            (request.client_id, request.side, request.price, request.quantity, request.leverage),
        )
        self.assertEqual(position_action is PositionAction.CLOSE, request.reduce_only)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        created = self.buy_order_created_logger if trade_type is TradeType.BUY else self.sell_order_created_logger
        event = created.event_log[0]
        self.assertEqual(
            (NOW, PAIR, OrderType.LIMIT, Decimal(100), Decimal(10000), order_id, self.expected_exchange_order_id),
            (event.timestamp, event.trading_pair, event.type, event.amount, event.price, event.order_id,
             event.exchange_order_id),
        )
        self.assertEqual((leverage, position_action.value), (event.leverage, event.position))
        self.assertTrue(self.is_logged(
            "INFO",
            f"Created LIMIT {trade_type.name} order {order_id} for {Decimal('100.000000')} "
            f"to {position_action.name} a {PAIR} position at {Decimal('10000.0000')}.",
        ))

    def _submit_error_log(self) -> str:
        return f"Error submitting buy LIMIT order to {self.exchange.name_cap} for 100.000000 {PAIR} 10000.0000."

    def _track_unit_order(self) -> InFlightOrder:
        self.exchange._set_current_timestamp(NOW)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=PAIR,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
        )
        return self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

    async def _lose_tracked_order(self) -> InFlightOrder:
        order = self._track_unit_order()
        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            await self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        return order

    def test_get_buy_and_sell_collateral_tokens(self):
        self.assertEqual(CONSTANTS.QUOTE_ASSET, self.exchange.get_buy_collateral_token(PAIR))
        self.assertEqual(CONSTANTS.QUOTE_ASSET, self.exchange.get_sell_collateral_token(PAIR))

    async def test_trading_rules_and_symbols_cover_active_markets(self):
        self.assertEqual({"BTC-USDC", "ETH-USDC"}, set(self.connector.trading_rules))
        self.assertEqual("BTC/USDC", await self.connector.exchange_symbol_associated_to_pair(PAIR))
        self.assertEqual(PAIR, self.connector.trading_pair_for_indexer("BTCUSDC"))
        self.assertEqual(Decimal(10), self.connector.trading_rules[PAIR].min_notional_size)
        self.assertEqual(Decimal("0.0045"), self.connector.quantize_order_amount(PAIR, Decimal("0.0045")))

    async def test_trading_starts_after_the_base_restart(self):
        def discard(coroutine):
            coroutine.close()

        with patch.object(self.connector.order_book_tracker, "start"), \
                patch.object(self.connector._perpetual_trading, "start"), \
                patch("hummingbot.connector.exchange_py_base.safe_ensure_future", side_effect=discard), \
                patch("hummingbot.connector.perpetual_derivative_py_base.safe_ensure_future", side_effect=discard), \
                patch.object(self.connector, "_create_user_stream_tracker_task", return_value=None):
            await self.connector.start_network()
            self.assertTrue(self.data_source.started)
            await self.connector.stop_network()
        self.assertFalse(self.data_source.started)

    async def test_network_outage_keeps_trading_until_the_clock_stops(self):
        def discard(coroutine):
            coroutine.close()

        status = PropertyMock(return_value=NetworkStatus.NOT_CONNECTED)
        with patch.object(self.connector.order_book_tracker, "start"), \
                patch.object(self.connector._perpetual_trading, "start"), \
                patch("hummingbot.connector.exchange_py_base.safe_ensure_future", side_effect=discard), \
                patch("hummingbot.connector.perpetual_derivative_py_base.safe_ensure_future", side_effect=discard), \
                patch.object(self.connector, "_create_user_stream_tracker_task", return_value=None), \
                patch.object(NeutronxPerpetualDerivative, "network_status", new_callable=lambda: status):
            await self.connector.start_network()
            await self.connector.stop_network()
            self.assertTrue(self.data_source.started)
            status.return_value = NetworkStatus.CONNECTED
            await self.connector.start_network()
            self.assertEqual(1, self.data_source.start_calls)
            status.return_value = NetworkStatus.STOPPED
            await self.connector.stop_network()
        self.assertFalse(self.data_source.started)

    def test_order_request_shapes(self):
        self.connector._perpetual_trading.set_leverage(PAIR, 50)
        limit = self.connector._order_request(
            "101", PAIR, Decimal("0.01"), TradeType.BUY, OrderType.LIMIT, Decimal("65000.7"), PositionAction.OPEN
        )
        self.assertEqual((Side.BUY, Decimal("65000.5"), TimeInForce.GTC), (limit.side, limit.price, limit.time_in_force))
        self.assertEqual((Decimal(10), False, False, 101), (limit.leverage, limit.post_only, limit.reduce_only, limit.client_id))
        maker = self.connector._order_request(
            "102", PAIR, Decimal("0.01"), TradeType.SELL, OrderType.LIMIT_MAKER, Decimal("65000.2"), PositionAction.CLOSE
        )
        self.assertEqual((Decimal("65000.5"), True, True), (maker.price, maker.post_only, maker.reduce_only))
        with patch.object(self.connector, "get_mid_price", return_value=Decimal(100)):
            taker = self.connector._order_request(
                "103", PAIR, Decimal("0.01"), TradeType.BUY, OrderType.MARKET, Decimal("NaN"), PositionAction.OPEN
            )
        self.assertEqual((ChainOrderType.LIMIT, TimeInForce.IOC, Decimal(101)), (taker.order_type, taker.time_in_force, taker.price))
        listed = self.connector._markets[PAIR]
        self.assertEqual(Decimal(198), self.connector._market_order_price(listed, PAIR, TradeType.SELL, Decimal(200)))
        unguarded = market(max_slippage="0")
        self.assertEqual(Decimal(190), self.connector._market_order_price(unguarded, PAIR, TradeType.SELL, Decimal(200)))
        with patch.object(self.connector, "get_mid_price", return_value=Decimal("NaN")):
            with self.assertRaises(ValueError):
                self.connector._market_order_price(listed, PAIR, TradeType.BUY, Decimal("NaN"))

    async def test_orders_carry_the_leverage_open_interest_allows(self):
        self.connector._markets[PAIR] = market(effective_max_leverage=2)
        self.assertEqual((True, ""), await self.connector._set_trading_pair_leverage(PAIR, 5))
        self.assertTrue(self.is_logged(
            "WARNING",
            f"Open interest on {PAIR} limits leverage to 2 for now; orders go out with it until the market allows 5 again.",
        ))
        self.connector._perpetual_trading.set_leverage(PAIR, 5)
        request = self.connector._order_request(
            "104", PAIR, Decimal("0.01"), TradeType.BUY, OrderType.LIMIT, Decimal(65000), PositionAction.OPEN
        )
        self.assertEqual(Decimal(2), request.leverage)
        self.connector._perpetual_trading.set_leverage(PAIR, 1)
        self.assertEqual(Decimal(1), self.connector._order_leverage(PAIR, self.connector._markets[PAIR]))

    async def test_born_cancelled_post_only_order_is_cancelled(self):
        self.data_source.place_result = PlacedOrder(order_id=556, status="CANCELLED", filled=Decimal(0))
        self.data_source.client_ids.seed([901])
        await self.connector._create_order(
            trade_type=TradeType.SELL,
            order_id="901",
            trading_pair=PAIR,
            amount=Decimal("0.01"),
            order_type=OrderType.LIMIT_MAKER,
            price=Decimal(65000),
            position_action=PositionAction.OPEN,
        )
        await self._settle()
        self.assertNotIn("901", self.connector.in_flight_orders)
        self.assertNotIn(901, self.data_source.client_ids)

    async def test_cancel_outcomes(self):
        self._track("101", "555")
        self.data_source.orders[555] = chain_order(555, "CANCELLED")
        self.assertTrue(await self.connector._place_cancel("101", self.connector.in_flight_orders["101"]))
        self.assertEqual([555], self.data_source.cancelled)
        self.assertNotIn("101", self.connector._settling)
        self.data_source.cancel_outcome = CancelOutcome.REJECTED
        with self.assertRaises(IOError) as raised:
            await self.connector._place_cancel("101", self.connector.in_flight_orders["101"])
        self.assertTrue(self.connector._is_order_not_found_during_cancelation_error(raised.exception))
        self.data_source.cancel_outcome = CancelOutcome.GONE
        self.data_source.orders[555] = chain_order(555, "FILLED")
        with patch("hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_derivative.safe_ensure_future") as future:
            self.assertFalse(await self.connector._place_cancel("101", self.connector.in_flight_orders["101"]))
        future.assert_called_once()
        future.call_args.args[0].close()

    async def test_outage_refuses_new_orders_and_keeps_cancelling(self):
        order = self._track("101", "555")
        self.data_source.orders[555] = chain_order(555, "CANCELLED")
        with patch.object(NeutronxPerpetualDerivative, "network_status", new_callable=PropertyMock,
                          return_value=NetworkStatus.NOT_CONNECTED):
            with self.assertRaises(IOError):
                await self.connector._place_order_and_process_update(order)
            with self.assertRaises(IOError):
                await self.connector._place_order("102", PAIR, Decimal("0.01"), TradeType.BUY, OrderType.LIMIT, Decimal(65000))
            self.assertTrue(await self.connector._place_cancel("101", order))
        self.assertEqual([], self.data_source.placed)
        self.assertEqual([555], self.data_source.cancelled)

    async def test_status_reconciliation_uses_chain_then_indexer(self):
        open_order = self._track("101", "555")
        open_order.creation_timestamp = 0
        gone = self._track("102", "556")
        gone.creation_timestamp = 0
        self.data_source.open_orders_result = (chain_order(555, "PARTIALLY_FILLED"),)
        self.data_source.orders[556] = chain_order(556, "CANCELLED")
        with patch.object(NeutronxPerpetualDerivative, "current_timestamp", 1000.0):
            await self.connector._update_order_status()
            await self._settle()
        self.assertEqual(OrderState.PARTIALLY_FILLED, open_order.current_state)
        self.assertNotIn("102", self.connector.in_flight_orders)

    async def test_status_falls_back_to_indexer_history(self):
        order = self._track("101", "557")
        with aioresponses() as mock:
            mock.get(
                re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/orders.*"),
                payload={"items": [order_json(557, "FILLED", "0.01")], "next_cursor": None},
            )
            mock.get(
                re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/fills.*"),
                payload={"items": [fill_json("301:1", 557)], "next_cursor": None},
            )
            update = await self.connector._request_order_status(order)
        self.assertIs(OrderState.FILLED, update.new_state)
        self.assertEqual(Decimal("0.01"), order.executed_amount_base)
        unknown = self._track("102", "558")
        with aioresponses() as mock:
            mock.get(re.compile(rf"^{INDEXER_URL}/accounts/.*"), payload={"items": [], "next_cursor": None})
            with self.assertRaises(IOError) as raised:
                await self.connector._request_order_status(unknown)
        self.assertTrue(self.connector._is_order_not_found_during_status_update_error(raised.exception))

    async def test_finished_order_waits_for_its_fills(self):
        order = self._track("101", "555", amount="0.02")
        self.data_source.orders[555] = chain_order(555, "FILLED", quantity="0.02", filled="0.02")
        with aioresponses() as mock, patch.object(self.connector, "_time", return_value=1000.0) as clock:
            mock.get(FILLS_URL, payload={"items": [fill_json("401:1", 555)], "next_cursor": None})
            waiting = await self.connector._request_order_status(order)
            self.assertIs(OrderState.PARTIALLY_FILLED, waiting.new_state)
            self.assertIn("101", self.connector._settling)
            await self.connector._request_order_status(order)
            self.assertEqual(1, self._requests(mock))
            clock.return_value = 1000.0 + CONSTANTS.FILL_BACKFILL_INTERVAL
            mock.get(FILLS_URL, payload={"items": [fill_json("401:2", 555), fill_json("401:1", 555)], "next_cursor": None})
            done = await self.connector._request_order_status(order)
        self.assertIs(OrderState.FILLED, done.new_state)
        self.assertEqual(Decimal("0.02"), order.executed_amount_base)
        self.assertNotIn("101", self.connector._settling)
        lookups = len(self.data_source.order_lookups)
        self.assertIs(done, await self.connector._request_order_status(order))
        self.assertEqual(lookups, len(self.data_source.order_lookups))

    async def test_reduce_only_order_shrunk_by_the_chain_ends_cancelled_with_its_fills(self):
        order = self._track("101", "555", amount="0.02")
        self.data_source.orders[555] = chain_order(555, "FILLED", quantity="0.01", filled="0.01")
        with aioresponses() as mock:
            mock.get(FILLS_URL, payload={"items": [fill_json("402:1", 555)], "next_cursor": None})
            update = await self.connector._request_order_status(order)
        self.assertIs(OrderState.CANCELED, update.new_state)
        self.assertEqual(Decimal("0.01"), order.executed_amount_base)

    async def test_cancel_reports_the_fills_made_before_it(self):
        order = self._track("101", "555", amount="0.02")
        self.data_source.orders[555] = chain_order(555, "CANCELLED", quantity="0.02", filled="0.01")
        with aioresponses() as mock:
            mock.get(FILLS_URL, payload={"items": [fill_json("403:1", 555)], "next_cursor": None})
            self.assertTrue(await self.connector._place_cancel("101", order))
        self.assertEqual(Decimal("0.01"), order.executed_amount_base)
        self.assertNotIn("101", self.connector._settling)

    async def test_cancel_with_late_fills_waits_and_sends_no_second_tx(self):
        order = self._track("101", "555", amount="0.02")
        self.data_source.orders[555] = chain_order(555, "CANCELLED", quantity="0.02", filled="0.01")
        with aioresponses() as mock:
            mock.get(FILLS_URL, payload={"items": [], "next_cursor": None})
            self.assertFalse(await self.connector._place_cancel("101", order))
        self.assertIn("101", self.connector._settling)
        with patch(SAFE_ENSURE_FUTURE) as future:
            self.assertFalse(await self.connector._place_cancel("101", order))
        future.call_args.args[0].close()
        self.assertEqual([555], self.data_source.cancelled)
        with patch(SAFE_ENSURE_FUTURE) as future:
            self.connector._process_fills([FillV1.from_json(fill_json("404:1", 555))])
        await future.call_args.args[0]
        await self._settle()
        self.assertIs(OrderState.CANCELED, order.current_state)
        self.assertEqual(Decimal("0.01"), order.executed_amount_base)
        self.assertNotIn("101", self.connector.in_flight_orders)

    async def test_history_scan_stops_at_the_order_creation(self):
        order = self._track("101", "559")
        order.creation_timestamp = datetime.fromisoformat(BLOCK_TIME).timestamp() + 3600
        with aioresponses() as mock:
            mock.get(
                re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/orders.*"),
                payload={"items": [order_json(1, "FILLED", "0.01")], "next_cursor": "100:1"},
                repeat=True,
            )
            with self.assertRaises(IOError):
                await self.connector._request_order_status(order)
            self.assertEqual(1, self._requests(mock))

    async def test_final_frame_from_the_stream_waits_for_the_fills(self):
        order = self._track("101", "555", amount="0.02")
        cancelled = order_json(555, "CANCELLED", "0.01", quantity="0.02")
        with aioresponses() as mock:
            mock.get(FILLS_URL, payload={"items": [fill_json("405:1", 555)], "next_cursor": None})
            self.connector._process_orders_frame(StreamFrame.from_json(frame("orders", [cancelled], "update")))
            for _ in range(50):
                if not order.is_open:
                    break
                await asyncio.sleep(0.01)
        self.assertIs(OrderState.CANCELED, order.current_state)
        self.assertEqual(Decimal("0.01"), order.executed_amount_base)

    async def test_user_stream_orders_and_fills(self):
        order = self._track("101", "555", amount="0.02")
        orders_frame = frame("orders", [order_json(555, "PARTIALLY_FILLED", "0.01")])
        self.connector._process_orders_frame(StreamFrame.from_json(orders_frame))
        await self._settle()
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)
        fills = StreamFrame.from_json(frame("fills", [fill_json("101:1", 555), fill_json("101:1", 555), fill_json("102:1", 999)]))
        self.connector._process_fills(FillV1.from_json(row) for row in fills.rows())
        self.assertEqual(Decimal("0.01"), order.executed_amount_base)
        self.connector._process_fills([FillV1.from_json(fill_json("103:1", 555))])
        await self._settle()
        self.assertNotIn("101", self.connector.in_flight_orders)

    async def test_user_stream_listener_dispatches_frames(self):
        order = self._track("101", "555")
        self.data_source.client_ids.seed([101])
        self.connector._user_stream_tracker._user_stream.put_nowait(frame("fills", [fill_json("104:1", 555)], "update"))
        self.connector._user_stream_tracker._user_stream.put_nowait(
            frame("positions", [{"id": 1, "pair": "BTCUSDC", "side": "LONG", "quantity": "0.1", "entry_price": "1"}])
        )
        self.connector._user_stream_tracker._user_stream.put_nowait({"type": "update", "channel": "fills", "data": [{}]})
        listener = self.local_event_loop.create_task(self.connector._user_stream_event_listener())
        for _ in range(50):
            if PAIR in self.connector.account_positions:
                break
            await asyncio.sleep(0.01)
        listener.cancel()
        self.assertEqual(OrderState.FILLED, order.current_state)
        self.assertNotIn(101, self.data_source.client_ids)
        self.assertEqual(Decimal("0.1"), self.connector.account_positions[PAIR].amount)

    async def test_orders_snapshot_refreshes_orders_that_vanished(self):
        order = self._track("101", "555")
        order.creation_timestamp = 0
        with patch.object(NeutronxPerpetualDerivative, "current_timestamp", 1000.0), \
                patch("hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_derivative.safe_ensure_future") as future:
            self.connector._process_orders_frame(StreamFrame.from_json(frame("orders", [])))
        future.assert_called_once()
        future.call_args.args[0].close()

    async def test_positions_follow_the_chain(self):
        self.data_source.positions_result = (chain_position(side="SHORT"),)
        await self.connector._update_positions()
        position = self.connector.account_positions[PAIR]
        self.assertEqual((PositionSide.SHORT, Decimal("-0.2")), (position.position_side, position.amount))
        self.connector._apply_positions(self.connector._indexer_positions([]))
        self.assertEqual({}, self.connector.account_positions)

    async def test_fees_follow_the_fee_tier(self):
        default = self.connector._get_fee("BTC", "USDC", OrderType.LIMIT, TradeType.BUY, PositionAction.OPEN, Decimal(1))
        self.assertEqual(Decimal("0.0005"), default.percent)
        await self.connector._update_trading_fees()
        maker = self.connector._get_fee("BTC", "USDC", OrderType.LIMIT_MAKER, TradeType.BUY, PositionAction.OPEN, Decimal(1))
        taker = self.connector._get_fee("BTC", "USDC", OrderType.LIMIT, TradeType.BUY, PositionAction.OPEN, Decimal(1))
        self.assertEqual((Decimal(0), Decimal("0.0004")), (maker.percent, taker.percent))

    async def test_leverage_and_position_mode(self):
        self.assertEqual((True, ""), await self.connector._set_trading_pair_leverage(PAIR, 5))
        self.assertFalse((await self.connector._set_trading_pair_leverage(PAIR, 11))[0])
        self.assertFalse((await self.connector._set_trading_pair_leverage("XYZ-USDC", 1))[0])
        self.assertEqual((True, ""), await self.connector._trading_pair_position_mode_set(PositionMode.ONEWAY, PAIR))
        self.assertFalse((await self.connector._trading_pair_position_mode_set(PositionMode.HEDGE, PAIR))[0])

    async def test_leverage_set_before_trading_rules_load_them(self):
        connector = NeutronxPerpetualDerivative(
            neutronx_perpetual_account_address=ACCOUNT,
            trading_pairs=[PAIR],
            trading_required=True,
            network=NETWORK,
            data_source=FakeDataSource(),
        )
        self.assertEqual({}, connector.trading_rules)
        await connector._execute_set_leverage(PAIR, 5)
        self.assertEqual(5, connector.get_leverage(PAIR))
        self.assertIn(PAIR, connector.trading_rules)

    async def test_leverage_reports_a_market_load_failure(self):
        connector = NeutronxPerpetualDerivative(
            neutronx_perpetual_account_address=ACCOUNT,
            trading_pairs=[PAIR],
            trading_required=True,
            network=NETWORK,
            data_source=FakeDataSource(),
        )
        with patch.object(connector._data_source, "markets", side_effect=IOError("node down")):
            success, message = await connector._set_trading_pair_leverage(PAIR, 5)
        self.assertFalse(success)
        self.assertIn("node down", message)

    async def test_network_check_gates_on_indexer_lag(self):
        with aioresponses() as mock:
            mock.get(f"{INDEXER_URL}/status", payload=self._status(1))
            await self.connector._make_network_check_request()
            mock.get(f"{INDEXER_URL}/status", payload=self._status(CONSTANTS.MAX_INDEXER_LAG_BLOCKS + 1))
            with self.assertRaises(IOError):
                await self.connector._make_network_check_request()
        self.assertEqual(1, self.data_source.node_checks)

    async def test_last_traded_prices_share_one_tickers_request(self):
        tickers = [{"pair": "BTCUSDC", "last_price": "65001"}, {"pair": "ETHUSDC", "mark_price": "2500"}]
        with aioresponses() as mock:
            mock.get(f"{INDEXER_URL}/markets/tickers", payload=tickers)
            prices = await asyncio.gather(*(self.connector._get_last_traded_price(pair) for pair in (PAIR, "ETH-USDC", "SOL-USDC")))
            self.assertEqual(1, self._requests(mock))
        self.assertEqual([65001.0, 2500.0], prices[:2])
        self.assertTrue(math.isnan(prices[2]))

    def test_shared_limits_keep_room_for_every_network_check(self):
        shared = NeutronxPerpetualDerivative(
            rate_limits_share_pct=Decimal(10),
            neutronx_perpetual_account_address=ACCOUNT,
            trading_required=False,
            network=NETWORK,
            data_source=FakeDataSource(),
        )
        limits = shared._throttler._id_to_limit_map
        self.assertEqual(11, limits[CONSTANTS.INDEXER_REST_LIMIT_ID].limit)
        self.assertGreaterEqual(limits[CONSTANTS.INDEXER_STATUS_LIMIT_ID].limit, CONSTANTS.NETWORK_CHECKS_PER_MINUTE)

    async def test_network_check_survives_one_failure(self):
        check = AsyncMock(side_effect=[IOError("blip"), IOError("down"), None, IOError("blip")])
        status = PropertyMock(return_value=NetworkStatus.CONNECTED)
        with patch.object(self.connector, "_make_network_check_request", check), \
                patch.object(NeutronxPerpetualDerivative, "network_status", new_callable=lambda: status):
            self.assertIs(NetworkStatus.CONNECTED, await self.connector.check_network())
            self.assertIs(NetworkStatus.NOT_CONNECTED, await self.connector.check_network())
            status.return_value = NetworkStatus.NOT_CONNECTED
            self.assertIs(NetworkStatus.CONNECTED, await self.connector.check_network())
            status.return_value = NetworkStatus.CONNECTED
            self.assertIs(NetworkStatus.CONNECTED, await self.connector.check_network())
        status.return_value = NetworkStatus.NOT_CONNECTED
        with patch.object(self.connector, "_make_network_check_request", AsyncMock(side_effect=IOError("down"))), \
                patch.object(NeutronxPerpetualDerivative, "network_status", new_callable=lambda: status):
            self.assertIs(NetworkStatus.NOT_CONNECTED, await self.connector.check_network())

    async def test_network_check_times_out_on_its_own(self):
        async def slow():
            await asyncio.sleep(10)

        with patch.object(self.connector, "_make_network_check_request", slow), \
                patch.object(CONSTANTS, "NETWORK_CHECK_TIMEOUT", 0.01):
            self.assertIs(NetworkStatus.NOT_CONNECTED, await self.connector.check_network())

    async def test_rate_limited_status_still_means_reachable(self):
        with aioresponses() as mock:
            mock.get(f"{INDEXER_URL}/status", status=429, headers={"Retry-After": "2"}, body="{}")
            await self.connector._make_network_check_request()
        self.assertEqual(1, self.data_source.node_checks)
        self.assertGreater(self.connector._indexer_backoff.remaining, 1)
        with patch.object(self.connector, "_api_get", AsyncMock(return_value=self._status(1))) as api_get:
            await self.connector._make_network_check_request()
        self.assertEqual(CONSTANTS.INDEXER_STATUS_LIMIT_ID, api_get.call_args.kwargs["limit_id"])

    async def test_funding_payments_of_every_pair_come_from_one_request(self):
        payments = {"items": [
            {"position_id": 2, "subaccount_id": 0, "pair": "ETHUSDC", "side": "LONG", "quantity": "1", "amount": "0.5",
             "rate": "0.0002", "mark_price": "2500", "block_height": 8, "time": "2026-11-10T12:00:00+00:00"},
        ], "next_cursor": None}
        with aioresponses() as mock:
            mock.get(re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/funding.*"), payload=payments)
            btc, eth = await asyncio.gather(self.connector._fetch_last_fee_payment(PAIR),
                                            self.connector._fetch_last_fee_payment("ETH-USDC"))
            self.assertEqual(1, self._requests(mock))
        self.assertEqual((0, Decimal(-1), Decimal(-1)), btc)
        self.assertEqual((Decimal("0.0002"), Decimal("0.5")), eth[1:])

    async def test_trade_history_pages_and_deduplicates(self):
        order = self._track("101", "555", amount="0.03")
        page_one = {"items": [fill_json("201:1", 555), fill_json("201:2", 777)], "next_cursor": "201:2"}
        page_two = {"items": [fill_json("202:1", 555)], "next_cursor": None}
        with aioresponses() as mock:
            mock.get(re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/fills\?limit=200&pair=.*"), payload=page_one)
            mock.get(re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/fills\?cursor=201.*"), payload=page_two)
            updates = await self.connector._all_trade_updates_for_order(order)
        self.assertEqual(["201:1", "202:1"], [u.trade_id for u in updates])
        with aioresponses() as mock:
            mock.get(re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/fills\?limit=200$"), payload=page_one, repeat=True)
            await self.connector._update_trade_history()
            await self.connector._update_trade_history()
        self.assertEqual(Decimal("0.01"), order.executed_amount_base)

    async def test_trade_history_skips_when_nothing_is_tracked(self):
        with aioresponses():
            await self.connector._update_trade_history()

    async def test_lost_orders_are_checked_before_any_cancel_tx(self):
        open_lost = self._track("101", "555")
        gone_lost = self._track("102", "556")
        for order in (open_lost, gone_lost):
            self.connector._order_tracker._lost_orders[order.client_order_id] = order
        self.data_source.open_orders_result = (chain_order(555),)
        self.data_source.orders[556] = chain_order(556, "CANCELLED")
        await self.connector._cancel_lost_orders()
        self.assertEqual([555], self.data_source.cancelled)

    async def test_polling_cycle_reads_everything(self):
        with patch.object(self.connector, "_update_trade_history") as history:
            await self.connector._status_polling_loop_fetch_updates()
        history.assert_awaited_once()
        self.assertEqual(Decimal(1000), self.connector.get_balance("USDC"))

    async def test_funding_payment_comes_from_the_indexer(self):
        payments = {
            "items": [
                {"position_id": 1, "subaccount_id": 3, "pair": "BTCUSDC", "side": "LONG", "quantity": "1",
                 "amount": "9", "rate": "0.1", "mark_price": "1", "block_height": 9, "time": "2026-11-10T13:00:00+00:00"},
                {"position_id": 2, "subaccount_id": 0, "pair": "BTCUSDC", "side": "LONG", "quantity": "1",
                 "amount": "-0.25", "rate": "0.0001", "mark_price": "65000", "block_height": 8,
                 "time": "2026-11-10T12:00:00+00:00"},
            ],
            "next_cursor": None,
        }
        with aioresponses() as mock:
            mock.get(re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/funding.*"), payload=payments)
            timestamp, rate, amount = await self.connector._fetch_last_fee_payment(PAIR)
            mock.get(re.compile(rf"^{INDEXER_URL}/accounts/{ACCOUNT}/funding.*"), payload={"items": [], "next_cursor": None})
            empty = await self.connector._fetch_last_fee_payment(PAIR)
        self.assertEqual((Decimal("0.0001"), Decimal("-0.25")), (rate, amount))
        self.assertEqual(datetime(2026, 11, 10, 12, tzinfo=timezone.utc).timestamp(), timestamp)
        self.assertEqual((0, Decimal(-1), Decimal(-1)), empty)

    async def test_final_status_from_the_stream_frees_the_client_id(self):
        order = self._track("101", "555")
        self.data_source.client_ids.seed([101])
        cancelled = {**order_json(555, "CANCELLED", client_id=101), "cancel_reason": "user_cancelled"}
        self.connector._process_orders_frame(StreamFrame.from_json(frame("orders", [cancelled])))
        await self._settle()
        self.assertNotIn("101", self.connector.in_flight_orders)
        self.assertNotIn(101, self.data_source.client_ids)
        self.assertIs(OrderState.CANCELED, order.current_state)

    def test_indexer_api_key_raises_limits(self):
        keyed = NeutronxPerpetualDerivative(
            neutronx_perpetual_account_address=ACCOUNT,
            neutronx_perpetual_indexer_api_key=" nx_key ",
            trading_required=False,
            network=NETWORK,
            data_source=FakeDataSource(),
        )
        self.assertEqual(("nx_key", 200, 594), (keyed.api_key, keyed.max_subscriptions, keyed.rate_limits_rules[0].limit))
        self.assertEqual((None, 50, 114), (self.connector.api_key, self.connector.max_subscriptions,
                                           self.connector.rate_limits_rules[0].limit))

    @staticmethod
    def _status(lag: int) -> Dict[str, Any]:
        return {"indexed_height": 10, "chain_height": 10 + lag, "lag_blocks": lag, "indexed_age_seconds": 1.0}
