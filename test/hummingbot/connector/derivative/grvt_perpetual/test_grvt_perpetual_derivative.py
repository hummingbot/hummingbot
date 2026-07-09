import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict

from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GrvtPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    DeductedFromReturnsTradeFee,
    TokenAmount,
    TradeFeeBase,
)
from hummingbot.core.event.events import FundingPaymentCompletedEvent
from hummingbot.core.network_iterator import NetworkStatus


class GrvtPerpetualDerivativeUnitTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.exchange = GrvtPerpetualDerivative(
            grvt_perpetual_api_key="api-key",
            grvt_perpetual_private_key="0x59c6995e998f97a5a0044966f094538e37d1d5cbf1e6fa7e87e55ce49963cf34",  # noqa: mock
            grvt_perpetual_trading_account_id="123456",
            trading_pairs=["BTC-USDT"],
        )
        self.exchange._symbol_map = bidict({"BTC_USDT_Perp": "BTC-USDT"})
        self.exchange._set_trading_pair_symbol_map(self.exchange._symbol_map)
        self.exchange._instrument_info_by_symbol = {
            "BTC_USDT_Perp": {
                "instrument": "BTC_USDT_Perp",
                "instrument_hash": "0x030501",
                "base": "BTC",
                "quote": "USDT",
                "kind": "PERPETUAL",
                "base_decimals": 3,
                "tick_size": "0.1",
                "min_size": "0.001",
                "min_notional": "5",
                "max_position_size": "100",
            }
        }
        self.exchange._trading_rules["BTC-USDT"] = TradingRule(
            trading_pair="BTC-USDT",
            min_order_size=Decimal("0.001"),
            max_order_size=Decimal("100"),
            min_price_increment=Decimal("0.1"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("5"),
            buy_order_collateral_token="USDT",
            sell_order_collateral_token="USDT",
        )

    async def test_new_client_order_id_is_in_uint64_upper_half(self):
        order_id = int(self.exchange._new_client_order_id())
        self.assertGreaterEqual(order_id, 2**63)

    async def test_place_order(self):
        self.exchange._api_post = AsyncMock(return_value={"result": {"order_id": "exchange-1"}})
        exchange_order_id, timestamp = await self.exchange._place_order(
            order_id="9223372036854775808",
            trading_pair="BTC-USDT",
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("62000"),
        )
        self.assertEqual("exchange-1", exchange_order_id)
        self.assertIsInstance(timestamp, float)

    async def test_create_order_normalizes_opposite_oneway_open_to_close(self):
        position = Position(
            trading_pair="BTC-USDT",
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal("0"),
            entry_price=Decimal("62000"),
            amount=Decimal("-1"),
            leverage=Decimal("5"),
        )
        position_key = self.exchange._perpetual_trading.position_key("BTC-USDT", PositionSide.SHORT)
        self.exchange._perpetual_trading.set_position(position_key, position)
        self.exchange._place_order = AsyncMock(return_value=("exchange-1", 1.0))

        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="9223372036854775808",
            trading_pair="BTC-USDT",
            amount=Decimal("1"),
            order_type=OrderType.MARKET,
            price=Decimal("62000"),
            position_action=PositionAction.OPEN,
        )

        tracked_order = self.exchange.in_flight_orders["9223372036854775808"]
        self.assertEqual(PositionAction.CLOSE, tracked_order.position)
        self.exchange._place_order.assert_awaited_once_with(
            order_id="9223372036854775808",
            trading_pair="BTC-USDT",
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.MARKET,
            price=Decimal("62000"),
            position_action=PositionAction.CLOSE,
        )

    async def test_create_order_normalizes_opposite_oneway_open_to_close_when_amount_exceeds_position(self):
        position = Position(
            trading_pair="BTC-USDT",
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal("0"),
            entry_price=Decimal("62000"),
            amount=Decimal("-0.99"),
            leverage=Decimal("5"),
        )
        position_key = self.exchange._perpetual_trading.position_key("BTC-USDT", PositionSide.SHORT)
        self.exchange._perpetual_trading.set_position(position_key, position)
        self.exchange._place_order = AsyncMock(return_value=("exchange-1", 1.0))

        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="9223372036854775808",
            trading_pair="BTC-USDT",
            amount=Decimal("1"),
            order_type=OrderType.MARKET,
            price=Decimal("62000"),
            position_action=PositionAction.OPEN,
        )

        tracked_order = self.exchange.in_flight_orders["9223372036854775808"]
        self.assertEqual(PositionAction.CLOSE, tracked_order.position)

    async def test_create_order_refreshes_positions_before_classifying_oneway_open(self):
        async def refresh_positions():
            position = Position(
                trading_pair="BTC-USDT",
                position_side=PositionSide.SHORT,
                unrealized_pnl=Decimal("0"),
                entry_price=Decimal("62000"),
                amount=Decimal("-1"),
                leverage=Decimal("5"),
            )
            position_key = self.exchange._perpetual_trading.position_key("BTC-USDT", PositionSide.SHORT)
            self.exchange._perpetual_trading.set_position(position_key, position)

        self.exchange._update_positions = AsyncMock(side_effect=refresh_positions)
        self.exchange._place_order = AsyncMock(return_value=("exchange-1", 1.0))

        await self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="9223372036854775809",
            trading_pair="BTC-USDT",
            amount=Decimal("1"),
            order_type=OrderType.MARKET,
            price=Decimal("62000"),
            position_action=PositionAction.OPEN,
        )

        tracked_order = self.exchange.in_flight_orders["9223372036854775809"]
        self.assertEqual(PositionAction.CLOSE, tracked_order.position)
        self.exchange._update_positions.assert_awaited_once()

    async def test_request_order_status_maps_partially_filled_open_order(self):
        self.exchange._api_post = AsyncMock(return_value={
            "result": {
                "order_id": "exchange-1",
                "state": {
                    "status": "OPEN",
                    "traded_size": ["0.4"],
                    "book_size": ["0.6"],
                    "update_time": "1700000000000000000",
                },
            }
        })
        tracked_order = InFlightOrder(
            client_order_id="9223372036854775808",
            exchange_order_id="exchange-1",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("62000"),
            creation_timestamp=0,
        )
        update = await self.exchange._request_order_status(tracked_order)
        self.assertEqual(OrderState.PARTIALLY_FILLED, update.new_state)

    async def test_place_cancel_uses_client_order_id_when_exchange_order_id_is_placeholder(self):
        self.exchange._api_post = AsyncMock(return_value={"result": {"ack": True}})
        tracked_order = InFlightOrder(
            client_order_id="9223372036854775808",
            exchange_order_id="0x00",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("62000"),
            creation_timestamp=0,
        )

        result = await self.exchange._place_cancel(tracked_order.client_order_id, tracked_order)

        self.assertTrue(result)
        self.exchange._api_post.assert_awaited_once_with(
            path_url="full/v1/cancel_order",
            data={
                "sub_account_id": "123456",
                "client_order_id": "9223372036854775808",
            },
            is_auth_required=True,
        )

    async def test_format_trading_rules_uses_min_notional(self):
        rules = await self.exchange._format_trading_rules(list(self.exchange._instrument_info_by_symbol.values()))
        self.assertEqual(Decimal("5"), rules[0].min_notional_size)

    async def test_update_balances(self):
        self.exchange._api_post = AsyncMock(return_value={
            "result": {
                "settle_currency": "USDT",
                "available_balance": "95",
                "spot_balances": [
                    {"currency": "USDT", "balance": "100"},
                    {"currency": "BTC", "balance": "0.5"},
                ],
            }
        })
        await self.exchange._update_balances()
        self.assertEqual(Decimal("100"), self.exchange.available_balances["USDT"] + Decimal("5"))
        self.assertEqual(Decimal("95"), self.exchange.available_balances["USDT"])
        self.assertEqual(Decimal("0.5"), self.exchange.available_balances["BTC"])

    async def test_update_positions(self):
        self.exchange._api_post = AsyncMock(return_value={
            "result": [
                {
                    "instrument": "BTC_USDT_Perp",
                    "size": "-2",
                    "entry_price": "62000",
                    "unrealized_pnl": "10",
                    "leverage": "5",
                }
            ]
        })
        await self.exchange._update_positions()
        position_key = self.exchange._perpetual_trading.position_key("BTC-USDT", PositionSide.SHORT)
        position = self.exchange.account_positions[position_key]
        self.assertEqual(Decimal("-2"), position.amount)
        self.assertEqual(Decimal("5"), position.leverage)

    async def test_fetch_last_fee_payment(self):
        self.exchange._api_post = AsyncMock(side_effect=[
            {"result": [{"event_time": "1700000000000000000", "amount": "-12.5", "instrument": "BTC_USDT_Perp"}]},
            {"result": [{"funding_rate": "0.0001"}]},
        ])
        timestamp, rate, amount = await self.exchange._fetch_last_fee_payment("BTC-USDT")
        self.assertEqual(1700000000.0, timestamp)
        self.assertEqual(Decimal("0.0001"), rate)
        self.assertEqual(Decimal("-12.5"), amount)

    async def test_all_trade_updates_for_order_uses_fee_currency(self):
        self.exchange._api_post = AsyncMock(return_value={
            "result": [
                {
                    "client_order_id": "9223372036854775808",
                    "order_id": "exchange-1",
                    "trade_id": "trade-1",
                    "event_time": "1700000000000000000",
                    "size": "0.4",
                    "price": "62000",
                    "fee": "1.2",
                    "fee_currency": "USDC",
                    "is_taker": True,
                }
            ]
        })
        tracked_order = InFlightOrder(
            client_order_id="9223372036854775808",
            exchange_order_id="exchange-1",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("62000"),
            creation_timestamp=0,
            position=PositionAction.OPEN,
        )
        updates = await self.exchange._all_trade_updates_for_order(tracked_order)
        self.assertEqual("USDC", updates[0].fee.flat_fees[0].token)
        self.exchange._api_post.assert_awaited_once_with(
            path_url=CONSTANTS.FILL_HISTORY_PATH_URL,
            data={
                "sub_account_id": "123456",
                "kind": ["PERPETUAL"],
                "base": ["BTC"],
                "quote": ["USDT"],
                "limit": 1000,
            },
            is_auth_required=True,
        )

    async def test_set_trading_pair_leverage_initializes_symbol_map(self):
        instrument_info = dict(self.exchange._instrument_info_by_symbol["BTC_USDT_Perp"])
        self.exchange._symbol_map = bidict()
        self.exchange._instrument_info_by_symbol = {}
        self.exchange._set_trading_pair_symbol_map(None)
        self.exchange._make_trading_pairs_request = AsyncMock(return_value=[instrument_info])
        self.exchange._api_post = AsyncMock(return_value={"result": {"success": True}})

        success, error = await self.exchange._set_trading_pair_leverage("BTC-USDT", 3)

        self.assertTrue(success)
        self.assertEqual("", error)

    async def test_is_user_stream_initialized_when_user_stream_received_data(self):
        self.exchange._user_stream_tracker.data_source._ws_assistant = MagicMock(last_recv_time=1)

        self.assertTrue(self.exchange._is_user_stream_initialized())

    async def test_trading_pair_position_mode_set(self):
        success, error = await self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, "BTC-USDT")
        self.assertTrue(success)
        self.assertEqual("", error)

        success, error = await self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, "BTC-USDT")
        self.assertFalse(success)
        self.assertIn("ONEWAY", error)

    async def test_user_stream_fill_event(self):
        order = InFlightOrder(
            client_order_id="9223372036854775808",
            exchange_order_id="exchange-1",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("62000"),
            creation_timestamp=0,
            position=PositionAction.OPEN,
        )
        self.exchange._order_tracker.start_tracking_order(order)
        self.exchange._user_stream_tracker._user_stream = asyncio.Queue()
        self.exchange._user_stream_tracker._user_stream.put_nowait(
            {
                "stream": "v1.fill",
                "feed": {
                    "client_order_id": order.client_order_id,
                    "order_id": order.exchange_order_id,
                    "trade_id": "trade-1",
                    "event_time": "1700000000000000000",
                    "size": "0.4",
                    "price": "62000",
                    "fee": "1.2",
                    "fee_currency": "USDC",
                    "is_taker": True,
                },
            }
        )
        listener = asyncio.create_task(self.exchange._user_stream_event_listener())
        await asyncio.sleep(0)
        listener.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await listener

    async def test_user_stream_fill_event_triggers_balance_refresh(self):
        order = InFlightOrder(
            client_order_id="9223372036854775808",
            exchange_order_id="exchange-1",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("62000"),
            creation_timestamp=0,
            position=PositionAction.OPEN,
        )
        self.exchange._order_tracker.start_tracking_order(order)
        self.exchange._user_stream_tracker._user_stream = asyncio.Queue()
        self.exchange._user_stream_tracker._user_stream.put_nowait(
            {
                "stream": "v1.fill",
                "feed": {
                    "client_order_id": order.client_order_id,
                    "order_id": order.exchange_order_id,
                    "trade_id": "trade-1",
                    "event_time": "1700000000000000000",
                    "size": "0.4",
                    "price": "62000",
                    "fee": "1.2",
                    "fee_currency": "USDC",
                    "is_taker": True,
                },
            }
        )
        self.exchange._update_balances = AsyncMock()
        self.exchange._update_positions = AsyncMock()

        with patch(
            "hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative.safe_ensure_future"
        ) as safe_future:
            safe_future.side_effect = lambda coro: coro.close()
            listener = asyncio.create_task(self.exchange._user_stream_event_listener())
            await asyncio.sleep(0)
            listener.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await listener

        self.assertEqual(2, safe_future.call_count)

    async def test_on_order_failure_marks_absent_reduce_only_close_as_canceled(self):
        self.exchange._update_positions = AsyncMock()
        self.exchange._update_balances = AsyncMock()
        self.exchange._order_tracker.process_order_update = MagicMock()

        with patch(
            "hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative.safe_ensure_future"
        ) as safe_future:
            safe_future.side_effect = lambda coro: coro.close()
            self.exchange._on_order_failure(
                order_id="9223372036854775808",
                trading_pair="BTC-USDT",
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("62000"),
                exception=IOError("Reduce only order with no position"),
                position_action=PositionAction.CLOSE,
            )

        self.exchange._order_tracker.process_order_update.assert_called_once()
        order_update = self.exchange._order_tracker.process_order_update.call_args.args[0]
        self.assertEqual("9223372036854775808", order_update.client_order_id)
        self.assertEqual("BTC-USDT", order_update.trading_pair)
        self.assertEqual(OrderState.CANCELED, order_update.new_state)
        self.assertEqual(2, safe_future.call_count)


class GrvtPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "api-key"
        cls.private_key = "0x59c6995e998f97a5a0044966f094538e37d1d5cbf1e6fa7e87e55ce49963cf34"  # noqa: mock
        cls.trading_account_id = "123456"
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(CONSTANTS.INSTRUMENTS_PATH_URL)
        return re.compile(f"^{url}".replace(".", r"\.") + ".*")

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PATH_URL)
        return re.compile(f"^{url}".replace(".", r"\.") + ".*")

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.INSTRUMENTS_PATH_URL)
        return re.compile(f"^{url}".replace(".", r"\.") + ".*")

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.INSTRUMENTS_PATH_URL)
        return re.compile(f"^{url}".replace(".", r"\.") + ".*")

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.CREATE_ORDER_PATH_URL)
        return re.compile(f"^{url}".replace(".", r"\.") + ".*")

    @property
    def balance_url(self):
        return web_utils.private_rest_url(CONSTANTS.ACCOUNT_SUMMARY_PATH_URL)

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PATH_URL)
        return re.compile(f"^{url}".replace(".", r"\.") + ".*")

    @property
    def funding_payment_url(self):
        url = web_utils.private_rest_url(CONSTANTS.FUNDING_PAYMENT_HISTORY_PATH_URL)
        return re.compile(f"^{url}".replace(".", r"\.") + ".*")

    @property
    def all_symbols_request_mock_response(self):
        return {"result": [self._instrument_response()]}

    @property
    def latest_prices_request_mock_response(self):
        return {
            "result": {
                "instrument": self.exchange_trading_pair,
                "last_price": str(self.expected_latest_price),
                "index_price": "100",
                "mark_price": "100.1",
                "funding_rate_8h_curr": "0.0001",
                "next_funding_time": str(self.target_funding_info_next_funding_utc_timestamp * 1_000_000_000),
            }
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        invalid_rule = self._instrument_response()
        invalid_rule["instrument"] = "INVALID-PAIR"
        invalid_rule["kind"] = "SPOT"
        return "INVALID-PAIR", {"result": [invalid_rule]}

    @property
    def network_status_request_successful_mock_response(self):
        return {"result": [self._instrument_response()]}

    @property
    def trading_rules_request_mock_response(self):
        return {"result": [self._instrument_response()]}

    @property
    def trading_rules_request_erroneous_mock_response(self):
        erroneous = self._instrument_response()
        erroneous.pop("base_decimals")
        return {"result": [erroneous]}

    @property
    def order_creation_request_successful_mock_response(self):
        return {"result": {"order_id": self.expected_exchange_order_id}}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "result": {
                "settle_currency": self.quote_asset,
                "available_balance": "2000",
                "spot_balances": [
                    {"currency": self.base_asset, "balance": "15"},
                    {"currency": self.quote_asset, "balance": "2000"},
                ],
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "result": {
                "settle_currency": self.quote_asset,
                "available_balance": "0",
                "spot_balances": [
                    {"currency": self.base_asset, "balance": "15"},
                ],
            }
        }

    @property
    def balance_event_websocket_update(self):
        return {}

    @property
    def expected_latest_price(self):
        return 62000.5

    @property
    def empty_funding_payment_mock_response(self):
        return {"result": []}

    @property
    def funding_payment_mock_response(self):
        return {
            "result": [
                {
                    "event_time": str(self.target_funding_payment_timestamp * 1_000_000_000),
                    "amount": str(self.target_funding_payment_payment_amount),
                    "instrument": self.exchange_trading_pair,
                }
            ]
        }

    @property
    def funding_info_mock_response(self):
        return {
            "result": {
                "instrument": self.exchange_trading_pair,
                "index_price": str(self.target_funding_info_index_price),
                "mark_price": str(self.target_funding_info_mark_price),
                "funding_rate_8h_curr": str(self.target_funding_info_rate),
                "next_funding_time": str(self.target_funding_info_next_funding_utc_timestamp * 1_000_000_000),
            }
        }

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            max_order_size=Decimal("100"),
            min_price_increment=Decimal("0.1"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("5"),
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["result"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "0x00"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("10000")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.1"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "trade-1"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}_Perp"

    def create_exchange_instance(self):
        exchange = GrvtPerpetualDerivative(
            grvt_perpetual_api_key=self.api_key,
            grvt_perpetual_private_key=self.private_key,
            grvt_perpetual_trading_account_id=self.trading_account_id,
            trading_pairs=[self.trading_pair],
        )
        exchange._symbol_map = bidict({self.exchange_trading_pair: self.trading_pair})
        exchange._instrument_info_by_symbol = {self.exchange_trading_pair: self._instrument_response()}
        exchange._set_trading_pair_symbol_map(exchange._symbol_map)
        exchange._auth._ensure_authenticated = AsyncMock()
        exchange._auth._session_cookie = "gravity-cookie"
        exchange._auth._grvt_account_id = "grvt-account-id"
        exchange.real_time_balance_update = False
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        headers = request_call.kwargs["headers"]
        self.assertEqual("application/json", headers["Content-Type"])
        self.assertEqual("gravity=gravity-cookie", headers["Cookie"])
        self.assertEqual("grvt-account-id", headers["X-Grvt-Account-Id"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = self._request_json(request_call)
        payload = request_data["order"]
        self.assertEqual(self.trading_account_id, payload["sub_account_id"])
        self.assertEqual(order.client_order_id, payload["metadata"]["client_order_id"])
        self.assertEqual(order.trade_type == TradeType.BUY, payload["legs"][0]["is_buying_asset"])
        self.assertEqual(self.exchange_trading_pair, payload["legs"][0]["instrument"])
        self.assertEqual(Decimal(str(order.amount)), Decimal(payload["legs"][0]["size"]))
        self.assertEqual(Decimal(str(order.price)), Decimal(payload["legs"][0]["limit_price"]))
        self.assertEqual(order.position == PositionAction.CLOSE, payload["reduce_only"])
        self.assertEqual(order.order_type == OrderType.LIMIT_MAKER, payload["post_only"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = self._request_json(request_call)
        self.assertEqual(self.trading_account_id, request_data["sub_account_id"])
        self.assertEqual(order.exchange_order_id, request_data["order_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = self._request_json(request_call)
        self.assertEqual(self.trading_account_id, request_data["sub_account_id"])
        self.assertEqual(order.client_order_id, request_data["client_order_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = self._request_json(request_call)
        self.assertEqual(self.trading_account_id, request_data["sub_account_id"])
        self.assertEqual(["PERPETUAL"], request_data["kind"])
        self.assertEqual([self.base_asset], request_data["base"])
        self.assertEqual([self.quote_asset], request_data["quote"])
        self.assertEqual(1000, request_data["limit"])

    def configure_all_symbols_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        mock_api.post(self.all_symbols_url, body=json.dumps(self.all_symbols_request_mock_response), callback=callback)
        return [self.all_symbols_url]

    def configure_trading_rules_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        mock_api.post(self.trading_rules_url, body=json.dumps(self.trading_rules_request_mock_response), callback=callback)
        return [self.trading_rules_url]

    def configure_erroneous_trading_rules_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        mock_api.post(
            self.trading_rules_url,
            body=json.dumps(self.trading_rules_request_erroneous_mock_response),
            callback=callback,
        )
        return [self.trading_rules_url]

    def configure_successful_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + ".*")
        mock_api.post(regex_url, body=json.dumps({"result": {"ack": True}}), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + ".*")
        mock_api.post(regex_url, status=400, body="cancel failed", callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + ".*")
        mock_api.post(regex_url, status=404, body=CONSTANTS.ORDER_NOT_FOUND_MESSAGE, callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses,
    ) -> List[str]:
        return [
            self.configure_successful_cancelation_response(successful_order, mock_api),
            self.configure_erroneous_cancelation_response(erroneous_order, mock_api),
        ]

    def configure_completely_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        return [self._configure_order_status(mock_api, "FILLED", order, order.amount, Decimal("0"), callback=callback)]

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Union[str, List[str]]:
        return self._configure_order_status(mock_api, "CANCELLED", order, Decimal("0"), order.amount, callback=callback)

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        return [self._configure_order_status(mock_api, "OPEN", order, Decimal("0"), order.amount, callback=callback)]

    def configure_http_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + ".*")
        mock_api.post(regex_url, status=404, body=CONSTANTS.ORDER_NOT_FOUND_MESSAGE, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        return self._configure_order_status(
            mock_api,
            "OPEN",
            order,
            self.expected_partial_fill_amount,
            order.amount - self.expected_partial_fill_amount,
            callback=callback,
        )

    def configure_order_not_found_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        return [self.configure_http_error_order_status_response(order, mock_api, callback=callback)]

    def configure_partial_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        return self._configure_fill_history(
            mock_api=mock_api,
            order=order,
            size=self.expected_partial_fill_amount,
            price=self.expected_partial_fill_price,
            fee=Decimal("0.1"),
            callback=callback,
        )

    def configure_erroneous_http_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.FILL_HISTORY_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + ".*")
        mock_api.post(regex_url, status=400, body="fill history failed", callback=callback)
        return url

    def configure_full_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = None,
    ) -> str:
        return self._configure_fill_history(
            mock_api=mock_api,
            order=order,
            size=order.amount,
            price=order.price,
            fee=Decimal("0.1"),
            callback=callback,
        )

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "stream": CONSTANTS.PRIVATE_WS_CHANNEL_ORDER,
            "feed": {
                "order_id": order.exchange_order_id,
                "metadata": {"client_order_id": order.client_order_id},
                "state": {
                    "status": "OPEN",
                    "traded_size": ["0"],
                    "book_size": [str(order.amount)],
                    "update_time": "1700000000000000000",
                },
            },
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "stream": CONSTANTS.PRIVATE_WS_CHANNEL_STATE,
            "feed": {
                "order_id": order.exchange_order_id,
                "client_order_id": order.client_order_id,
                "order_state": {
                    "status": "CANCELLED",
                    "traded_size": ["0"],
                    "book_size": [str(order.amount)],
                    "update_time": "1700000000000000000",
                },
            },
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "stream": CONSTANTS.PRIVATE_WS_CHANNEL_STATE,
            "feed": {
                "order_id": order.exchange_order_id,
                "client_order_id": order.client_order_id,
                "order_state": {
                    "status": "FILLED",
                    "traded_size": [str(order.amount)],
                    "book_size": ["0"],
                    "update_time": "1700000000000000000",
                },
            },
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "stream": CONSTANTS.PRIVATE_WS_CHANNEL_FILL,
            "feed": {
                "client_order_id": order.client_order_id,
                "order_id": order.exchange_order_id,
                "trade_id": self.expected_fill_trade_id,
                "event_time": "1700000000000000000",
                "size": str(order.amount),
                "price": str(order.price),
                "fee": "0.1",
                "fee_currency": self.quote_asset,
                "is_taker": True,
            },
        }

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        size = order.amount if order.trade_type == TradeType.BUY else -order.amount
        side = PositionSide.LONG if size > 0 else PositionSide.SHORT
        return {
            "stream": CONSTANTS.PRIVATE_WS_CHANNEL_POSITION,
            "feed": {
                "instrument": self.exchange_trading_pair,
                "size": str(size),
                "entry_price": str(order.price),
                "unrealized_pnl": str(unrealized_pnl),
                "leverage": str(self.exchange.get_leverage(self.trading_pair)),
                "position_side": side.name,
            },
        }

    def funding_info_event_for_websocket_update(self):
        return {
            "stream": CONSTANTS.PUBLIC_WS_CHANNEL_TICKER,
            "feed": {
                "instrument": self.exchange_trading_pair,
                "index_price": str(self.target_funding_info_index_price_ws_updated),
                "mark_price": str(self.target_funding_info_mark_price_ws_updated),
                "funding_rate_8h_curr": str(self.target_funding_info_rate_ws_updated),
                "next_funding_time": str(self.target_funding_info_next_funding_utc_timestamp_ws_updated * 1_000_000_000),
            },
        }

    def configure_failed_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        callback()
        return "", "GRVT only supports the ONEWAY position mode."

    def configure_successful_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        callback()

    def configure_failed_set_leverage(
        self,
        leverage: int,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        url = web_utils.private_rest_url(CONSTANTS.SET_INITIAL_LEVERAGE_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + ".*")
        mock_api.post(regex_url, body=json.dumps({"result": {"success": False}}), callback=callback)
        return url, "Failed to set leverage for BTC-USDT: {'result': {'success': False}}"

    def configure_successful_set_leverage(
        self,
        leverage: int,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.private_rest_url(CONSTANTS.SET_INITIAL_LEVERAGE_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + ".*")
        mock_api.post(regex_url, body=json.dumps({"result": {"success": True}}), callback=callback)

    def test_get_buy_and_sell_collateral_tokens(self):
        self.exchange._trading_rules[self.trading_pair] = self.expected_trading_rule
        self.assertEqual(self.quote_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(self.quote_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        urls = self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set(),
        )
        trade_url = self.configure_full_fill_trade_response(order=order, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_order_status())
        self.async_run_with_timeout(request_sent_event.wait())

        for url in (urls if isinstance(urls, list) else [urls]):
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(order=order, request_call=order_status_request)

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)
        self.assertTrue(order.is_filled)

        trades_request = self._all_executed_requests(mock_api, trade_url)[0]
        self.validate_auth_credentials_present(trades_request)
        self.validate_trades_request(order=order, request_call=trades_request)

        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(self._expected_open_position_fill_fee(), fill_event.trade_fee)

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [
            self.trade_event_for_full_fill_websocket_update(order=order),
            self.order_event_for_full_fill_websocket_update(order=order),
            self.position_event_for_full_fill_websocket_update(order=order, unrealized_pnl=12),
            asyncio.CancelledError,
        ]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.async_run_with_timeout(order.wait_until_completely_filled())
        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(self._expected_open_position_fill_fee(), fill_event.trade_fee)

    @aioresponses()
    async def test_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        mock_api.post(self.all_symbols_url, body=json.dumps(self.all_symbols_request_mock_response))
        all_trading_pairs = await self.exchange.all_trading_pairs()
        self.assertEqual([self.trading_pair], all_trading_pairs)

    @aioresponses()
    async def test_invalid_trading_pair_not_in_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        _, response = self.all_symbols_including_invalid_pair_mock_response
        mock_api.post(self.all_symbols_url, body=json.dumps(response))
        self.assertEqual([], await self.exchange.all_trading_pairs())

    @aioresponses()
    async def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        mock_api.post(self.all_symbols_url, exception=Exception)
        self.assertEqual([], await self.exchange.all_trading_pairs())

    @aioresponses()
    async def test_get_last_trade_prices(self, mock_api):
        mock_api.post(self.latest_prices_url, body=json.dumps(self.latest_prices_request_mock_response))
        latest_prices = await self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

    @aioresponses()
    async def test_check_network_success(self, mock_api):
        mock_api.post(self.network_status_url, body=json.dumps(self.network_status_request_successful_mock_response))
        self.assertEqual(NetworkStatus.CONNECTED, await self.exchange.check_network())

    @aioresponses()
    async def test_check_network_failure(self, mock_api):
        mock_api.post(self.network_status_url, status=500)
        self.assertEqual(NetworkStatus.NOT_CONNECTED, await self.exchange.check_network())

    @aioresponses()
    async def test_check_network_raises_cancel_exception(self, mock_api):
        mock_api.post(self.network_status_url, exception=asyncio.CancelledError)
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange.check_network()

    @aioresponses()
    async def test_update_balances(self, mock_api):
        self._configure_balance_response(self.balance_request_mock_response_for_base_and_quote, mock_api)
        await self.exchange._update_balances()
        self.assertEqual(Decimal("15"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_all_balances()[self.base_asset])
        self.assertEqual(Decimal("2000"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("2000"), self.exchange.get_all_balances()[self.quote_asset])

        self._configure_balance_response(self.balance_request_mock_response_only_base, mock_api)
        await self.exchange._update_balances()
        self.assertEqual(Decimal("15"), self.exchange.available_balances[self.base_asset])
        self.assertNotIn(self.quote_asset, self.exchange.available_balances)

    async def test_set_position_mode_failure(self):
        success, error = await self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair)
        self.assertFalse(success)
        self.assertIn("ONEWAY", error)

    async def test_set_position_mode_success(self):
        success, error = await self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair)
        self.assertTrue(success)
        self.assertEqual("", error)

    async def test_user_stream_balance_update(self):
        self.assertFalse(self.exchange.real_time_balance_update)

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        mock_api.post(self.funding_info_url, body=json.dumps(self.funding_info_mock_response))
        mock_queue_get.side_effect = [asyncio.CancelledError]
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())

        funding_info: FundingInfo = self.exchange.get_funding_info(self.trading_pair)
        self.assertEqual(self.target_funding_info_index_price, funding_info.index_price)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
        self.assertEqual(self.target_funding_info_next_funding_utc_timestamp, funding_info.next_funding_utc_timestamp)
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        mock_api.post(self.funding_info_url, body=json.dumps(self.funding_info_mock_response))
        mock_queue_get.side_effect = [self.funding_info_event_for_websocket_update(), asyncio.CancelledError]
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        self.assertEqual(1, self.exchange._perpetual_trading.funding_info_stream.qsize())

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, mock_api):
        private_url = re.compile(f"^{web_utils.private_rest_url(CONSTANTS.FUNDING_PAYMENT_HISTORY_PATH_URL)}".replace(".", r"\.") + ".*")
        public_url = re.compile(f"^{web_utils.public_rest_url(CONSTANTS.FUNDING_PATH_URL)}".replace(".", r"\.") + ".*")
        request_sent_event = asyncio.Event()

        async def run_test():
            mock_api.post(private_url, body=json.dumps(self.empty_funding_payment_mock_response), callback=lambda *args, **kwargs: request_sent_event.set())
            task = asyncio.create_task(self.exchange._funding_payment_polling_loop())
            await asyncio.sleep(0.1)
            self.assertEqual(0, len(self.funding_payment_logger.event_log))

            mock_api.post(private_url, body=json.dumps(self.funding_payment_mock_response), callback=lambda *args, **kwargs: request_sent_event.set(), repeat=True)
            mock_api.post(
                public_url,
                body=json.dumps({"result": [{"funding_rate": str(self.target_funding_payment_funding_rate)}]}),
                callback=lambda *args, **kwargs: request_sent_event.set(),
                repeat=True,
            )

            request_sent_event.clear()
            self.exchange._funding_fee_poll_notifier.set()
            await request_sent_event.wait()
            await asyncio.sleep(0.1)

            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.async_run_with_timeout(run_test())

        self.assertEqual(1, len(self.funding_payment_logger.event_log))
        event: FundingPaymentCompletedEvent = self.funding_payment_logger.event_log[0]
        self.assertEqual(self.target_funding_payment_timestamp, event.timestamp)
        self.assertEqual(self.target_funding_payment_payment_amount, event.amount)
        self.assertEqual(self.target_funding_payment_funding_rate, event.funding_rate)

    async def test_all_trade_updates_for_order_uses_fee_currency(self):
        self.exchange._symbol_map = bidict({self.exchange_trading_pair: self.trading_pair})
        self.exchange._set_trading_pair_symbol_map(self.exchange._symbol_map)
        self.exchange._instrument_info_by_symbol = {self.exchange_trading_pair: self._instrument_response()}
        self.exchange._api_post = AsyncMock(return_value={
            "result": [
                {
                    "client_order_id": "1",
                    "order_id": "0x00",
                    "trade_id": "trade-1",
                    "event_time": "1700000000000000000",
                    "size": "1",
                    "price": "10000",
                    "fee": "0.1",
                    "fee_currency": "USDC",
                    "is_taker": True,
                }
            ]
        })
        order = InFlightOrder(
            client_order_id="1",
            exchange_order_id="0x00",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("10000"),
            creation_timestamp=0,
            position=PositionAction.OPEN,
        )
        trade_updates = await self.exchange._all_trade_updates_for_order(order)
        self.assertEqual("USDC", trade_updates[0].fee.flat_fees[0].token)

    def _configure_balance_response(
        self,
        response: Dict[str, Any],
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = self.balance_url
        mock_api.post(re.compile(f"^{url}".replace(".", r"\.") + ".*"), body=json.dumps(response), callback=callback)
        return url

    def _configure_order_status(
        self,
        mock_api: aioresponses,
        status: str,
        order: InFlightOrder,
        traded_size: Decimal,
        book_size: Decimal,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + ".*")
        response = {
            "result": {
                "order_id": order.exchange_order_id,
                "state": {
                    "status": status,
                    "traded_size": [str(traded_size)],
                    "book_size": [str(book_size)],
                    "update_time": "1700000000000000000",
                },
            }
        }
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def _configure_fill_history(
        self,
        mock_api: aioresponses,
        order: InFlightOrder,
        size: Decimal,
        price: Decimal,
        fee: Decimal,
        callback: Optional[Callable] = None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.FILL_HISTORY_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.") + ".*")
        response = {
            "result": [
                {
                    "client_order_id": order.client_order_id,
                    "order_id": order.exchange_order_id,
                    "trade_id": self.expected_fill_trade_id,
                    "event_time": "1700000000000000000",
                    "size": str(size),
                    "price": str(price),
                    "fee": str(fee),
                    "fee_currency": self.quote_asset,
                    "is_taker": True,
                }
            ]
        }
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def _instrument_response(self) -> Dict[str, Any]:
        return {
            "instrument": self.exchange_trading_pair,
            "instrument_hash": "0x030501",
            "base": self.base_asset,
            "quote": self.quote_asset,
            "kind": "PERPETUAL",
            "base_decimals": 9,
            "quote_decimals": 6,
            "tick_size": "0.1",
            "min_size": "0.001",
            "min_notional": "5",
            "max_position_size": "100",
            "funding_interval_hours": 8,
        }

    def _expected_open_position_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.1"))],
        )

    @staticmethod
    def _request_json(request_call: RequestCall) -> Dict[str, Any]:
        raw_data = request_call.kwargs["data"]
        if isinstance(raw_data, (bytes, bytearray)):
            raw_data = raw_data.decode("utf-8")
        if isinstance(raw_data, str):
            return json.loads(raw_data)
        return raw_data
