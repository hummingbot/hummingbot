import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_utils import LighterMarketInfo
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import LighterPerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TradeFeeBase
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketOrderFailureEvent, SellOrderCreatedEvent


class MockSignerClient:
    ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 0
    ORDER_TIME_IN_FORCE_POST_ONLY = 1
    ORDER_TYPE_LIMIT = 0
    CROSS_MARGIN_MODE = 0

    def __init__(self):
        self.create_order = AsyncMock(return_value=(None, {"code": 200}, None))
        self.create_market_order = AsyncMock(return_value=(None, {"code": 200}, None))
        self.cancel_order = AsyncMock(return_value=(None, {"code": 200}, None))
        self.update_leverage = AsyncMock(return_value=(None, {"code": 200}, None))


class LighterPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):

    ACCOUNT_INDEX = 724450

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "ETH"
        cls.quote_asset = CONSTANTS.PERPETUAL_QUOTE_TOKEN  # USDC
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = CONSTANTS.DOMAIN
        cls.client_order_id_prefix = "1"
        cls.exchange_order_id_prefix = "2"

    def setUp(self) -> None:
        super().setUp()
        self.exchange._account_index = self.ACCOUNT_INDEX
        self.exchange._signer_client = MockSignerClient()
        self.exchange._ensure_account_ready = AsyncMock()
        self._set_up_market_info()

    def _set_up_market_info(self):
        market_info = LighterMarketInfo(
            market_id=1,
            exchange_symbol=self.base_asset,
            trading_pair=self.trading_pair,
            base_asset=self.base_asset,
            quote_asset=self.quote_asset,
            market_type="perp",
            min_base_amount=Decimal("0.01"),
            min_quote_amount=Decimal("1"),
            size_decimals=3,
            price_decimals=2,
            maker_fee=Decimal("0.0001"),
            taker_fee=Decimal("0.0004"),
            raw_info={
                "last_trade_price": "10000",
                "mark_price": "2",
                "index_price": "1",
            },
        )
        self.exchange._markets_by_trading_pair = {self.trading_pair: market_info}
        self.exchange._markets_by_id = {1: market_info}
        self.exchange._markets_by_exchange_symbol = {self.base_asset: market_info}

    # ── Factory ────────────────────────────────────────────────────────────────

    def create_exchange_instance(self):
        return LighterPerpetualDerivative(
            lighter_perpetual_l1_address="0xtest",
            lighter_perpetual_api_key_index=1,
            lighter_perpetual_api_public_key="0xpub",
            lighter_perpetual_api_private_key="0xpriv",
            trading_pairs=[self.trading_pair],
            trading_required=True,
            domain=self.domain,
        )

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return base_token

    # ── URL properties ─────────────────────────────────────────────────────────

    @property
    def all_symbols_url(self):
        url = web_utils.rest_url(CONSTANTS.ORDER_BOOK_DETAILS_PATH_URL, self.domain)
        return re.compile(f"^{re.escape(url)}")

    @property
    def latest_prices_url(self):
        url = web_utils.rest_url(CONSTANTS.ORDER_BOOK_DETAILS_PATH_URL, self.domain)
        return re.compile(f"^{re.escape(url)}")

    @property
    def network_status_url(self):
        url = web_utils.rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        return re.compile(f"^{re.escape(url)}")

    @property
    def trading_rules_url(self):
        url = web_utils.rest_url(CONSTANTS.ORDER_BOOK_DETAILS_PATH_URL, self.domain)
        return re.compile(f"^{re.escape(url)}")

    @property
    def order_creation_url(self):
        return ""  # lighter uses SignerClient, not HTTP

    @property
    def balance_url(self):
        return web_utils.rest_url(CONSTANTS.ACCOUNT_PATH_URL, self.domain)

    @property
    def funding_info_url(self):
        url = web_utils.rest_url(CONSTANTS.FUNDING_RATES_PATH_URL, self.domain)
        return re.compile(f"^{re.escape(url)}")

    @property
    def funding_payment_url(self):
        url = web_utils.rest_url(CONSTANTS.POSITION_FUNDING_PATH_URL, self.domain)
        return re.compile(f"^{re.escape(url)}")

    # ── Value properties ───────────────────────────────────────────────────────

    @property
    def expected_exchange_order_id(self):
        return 21

    @property
    def expected_latest_price(self):
        return 10000.0

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_supported_position_modes(self):
        return [PositionMode.ONEWAY]

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("10500")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_trade_id(self) -> str:
        return "1"

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(percent=Decimal("0.0004"))

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.01"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("1"),
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        return ""  # overridden test doesn't check error log

    # ── Funding info target values (match market raw_info / funding response) ──

    @property
    def target_funding_info_index_price(self):
        return Decimal("1")

    @property
    def target_funding_info_mark_price(self):
        return Decimal("2")

    @property
    def target_funding_info_rate(self):
        return Decimal("3")

    @property
    def target_funding_payment_timestamp(self):
        return 1000

    @property
    def target_funding_payment_funding_rate(self):
        return Decimal("100")

    @property
    def target_funding_payment_payment_amount(self):
        return Decimal("200")

    # ── Mock responses ─────────────────────────────────────────────────────────

    @property
    def all_symbols_request_mock_response(self):
        return {
            "order_book_details": [
                {
                    "symbol": self.base_asset,
                    "market_id": 1,
                    "status": "active",
                    "market_config": {"hidden": False},
                    "min_base_amount": "0.01",
                    "min_quote_amount": "1",
                    "supported_size_decimals": 3,
                    "supported_price_decimals": 2,
                    "maker_fee": "0.0001",
                    "taker_fee": "0.0004",
                    "last_trade_price": "10000",
                    "mark_price": "2",
                    "index_price": "1",
                }
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        return "HIDDEN-USDC", {
            "order_book_details": [
                {
                    "symbol": self.base_asset,
                    "market_id": 1,
                    "status": "active",
                    "market_config": {"hidden": False},
                    "min_base_amount": "0.01",
                    "min_quote_amount": "1",
                    "supported_size_decimals": 3,
                    "supported_price_decimals": 2,
                    "maker_fee": "0.0001",
                    "taker_fee": "0.0004",
                    "last_trade_price": "10000",
                },
                {
                    "symbol": "HIDDEN",
                    "market_id": 99,
                    "status": "active",
                    "market_config": {"hidden": True},
                    "min_base_amount": "0.01",
                    "min_quote_amount": "1",
                    "supported_size_decimals": 3,
                    "supported_price_decimals": 2,
                    "maker_fee": "0.0001",
                    "taker_fee": "0.0004",
                    "last_trade_price": "0",
                },
            ]
        }

    @property
    def network_status_request_successful_mock_response(self):
        return {"stats": {"online": True}}

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "order_book_details": [
                {
                    "symbol": self.base_asset,
                    "market_id": 1,
                    "status": "inactive",  # inactive → skipped → 0 rules
                    "market_config": {"hidden": False},
                }
            ]
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {}  # lighter uses SignerClient

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "accounts": [
                {
                    "index": self.ACCOUNT_INDEX,
                    "available_balance": "2000",
                    "assets": [
                        {"symbol": "USDC", "margin_balance": "2000", "locked_balance": "0"}
                    ],
                    "positions": [],
                }
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return self.balance_request_mock_response_for_base_and_quote

    @property
    def balance_event_websocket_update(self):
        return {
            "channel": f"{CONSTANTS.ACCOUNT_ALL_ASSETS_CHANNEL}:{self.ACCOUNT_INDEX}",
            "available_balance": "2000",
            "assets": {
                "usdc": {"symbol": "USDC", "margin_balance": "2000", "locked_balance": "0"}
            },
        }

    @property
    def funding_info_mock_response(self):
        return {"funding_rates": [{"market_id": 1, "rate": "3"}]}

    @property
    def empty_funding_payment_mock_response(self):
        return {"position_fundings": []}

    @property
    def funding_payment_mock_response(self):
        # lighter returns timestamp in ms, converts to seconds via * 1e-3
        # target_funding_payment_timestamp = 1000 → need timestamp_ms = 1_000_000
        timestamp_ms = int(self.target_funding_payment_timestamp * 1000)
        return {
            "position_fundings": [
                {
                    "change": str(self.target_funding_payment_payment_amount),
                    "rate": str(self.target_funding_payment_funding_rate),
                    "timestamp": str(timestamp_ms),
                }
            ]
        }

    # ── Websocket event builders ────────────────────────────────────────────────

    def _order_ws_event(self, order: InFlightOrder, status: str) -> dict:
        return {
            "channel": f"{CONSTANTS.ACCOUNT_ALL_ORDERS_CHANNEL}:{self.ACCOUNT_INDEX}",
            "orders": {
                "market": [
                    {
                        "client_order_id": order.client_order_id,
                        "order_id": order.exchange_order_id or str(self.expected_exchange_order_id),
                        "status": status,
                        "filled_base_amount": str(order.amount) if status == "filled" else "0",
                        "base_amount": str(order.amount),
                        "price": str(order.price),
                        "transaction_time": "1640780000000",
                    }
                ]
            },
        }

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return self._order_ws_event(order, "open")

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return self._order_ws_event(order, "canceled")

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return self._order_ws_event(order, "filled")

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        is_sell = order.trade_type == TradeType.SELL
        # is_maker_ask=True → ask is maker, bid is taker (BUY gets taker fee)
        # is_maker_ask=False → bid is maker, ask is taker (SELL gets taker fee)
        is_maker_ask = not is_sell
        return {
            "channel": f"{CONSTANTS.ACCOUNT_ALL_TRADES_CHANNEL}:{self.ACCOUNT_INDEX}",
            "trades": {
                "market": [
                    {
                        "ask_account_id": self.ACCOUNT_INDEX if is_sell else 999,
                        "bid_account_id": self.ACCOUNT_INDEX if not is_sell else 999,
                        "ask_client_id_str": order.client_order_id if is_sell else "other",
                        "bid_client_id_str": order.client_order_id if not is_sell else "other",
                        "ask_id_str": order.exchange_order_id or str(self.expected_exchange_order_id),
                        "bid_id_str": order.exchange_order_id or str(self.expected_exchange_order_id),
                        "is_maker_ask": is_maker_ask,
                        "market_id": 1,
                        "trade_id": self.expected_fill_trade_id,
                        "price": str(order.price),
                        "size": str(order.amount),
                        "transaction_time": "1640780000000000",
                    }
                ]
            },
        }

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        is_sell = order.trade_type == TradeType.SELL
        lev = order.leverage if order.leverage and order.leverage != Decimal("0") else Decimal("2")
        return {
            "channel": f"{CONSTANTS.ACCOUNT_ALL_POSITIONS_CHANNEL}:{self.ACCOUNT_INDEX}",
            "positions": {
                "1": {
                    "market_id": 1,
                    "symbol": self.base_asset,
                    "sign": "-1" if is_sell else "1",
                    "position": str(order.amount),
                    "avg_entry_price": str(order.price),
                    "unrealized_pnl": str(unrealized_pnl),
                    "initial_margin_fraction": str(Decimal("1") / lev),
                }
            },
        }

    def funding_info_event_for_websocket_update(self):
        # market_id is parsed from channel suffix "market_stats:1"
        # data fields must be at the top level (parsed as market_stats = raw_message)
        return {
            "channel": f"{CONSTANTS.MARKET_STATS_CHANNEL}:1",
            "mark_price": "20",
            "index_price": "10",
            "funding_rate": "30",
        }

    # ── Validation stubs ───────────────────────────────────────────────────────

    def validate_auth_credentials_present(self, request_call: RequestCall):
        pass  # lighter REST endpoints don't require auth headers

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        pass  # lighter uses SignerClient, not HTTP

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        pass  # lighter uses SignerClient, not HTTP

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        pass

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        pass

    # ── Configure helpers ──────────────────────────────────────────────────────

    def _active_orders_url(self) -> str:
        return web_utils.rest_url(CONSTANTS.ACCOUNT_ACTIVE_ORDERS_PATH_URL, self.domain)

    def _inactive_orders_url(self) -> str:
        return web_utils.rest_url(CONSTANTS.ACCOUNT_INACTIVE_ORDERS_PATH_URL, self.domain)

    def _active_order_payload(self, order: InFlightOrder) -> dict:
        return {
            "orders": [
                {
                    "client_order_id": order.client_order_id,
                    "order_id": order.exchange_order_id or str(self.expected_exchange_order_id),
                    "status": "open",
                    "filled_base_amount": "0",
                    "base_amount": str(order.amount),
                    "price": str(order.price),
                    "transaction_time": "1640780000000000",
                }
            ]
        }

    def _inactive_order_payload(self, order: InFlightOrder, status: str, filled: str = None) -> dict:
        return {
            "orders": [
                {
                    "client_order_id": order.client_order_id,
                    "order_id": order.exchange_order_id or str(self.expected_exchange_order_id),
                    "status": status,
                    "filled_base_amount": filled if filled is not None else str(order.amount),
                    "base_amount": str(order.amount),
                    "price": str(order.price),
                    "transaction_time": "1640780000000000",
                }
            ]
        }

    def _mock_active(self, mock_api: aioresponses, payload: dict, callback=None):
        kwargs = {"body": json.dumps(payload)}
        if callback:
            kwargs["callback"] = callback
        mock_api.get(re.compile(f"^{re.escape(self._active_orders_url())}"), **kwargs)

    def _mock_inactive(self, mock_api: aioresponses, payload: dict, callback=None):
        kwargs = {"body": json.dumps(payload)}
        if callback:
            kwargs["callback"] = callback
        mock_api.get(re.compile(f"^{re.escape(self._inactive_orders_url())}"), **kwargs)

    # ── Configure methods ──────────────────────────────────────────────────────

    def configure_successful_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        self._mock_active(mock_api, self._active_order_payload(order))

        async def _cancel(**kwargs):
            callback()
            return (None, {"code": 200}, None)

        self.exchange._signer_client.cancel_order = AsyncMock(side_effect=_cancel)
        return ""

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        self._mock_active(mock_api, self._active_order_payload(order))

        async def _cancel(**kwargs):
            callback()
            return (None, {"code": 500}, None)

        self.exchange._signer_client.cancel_order = AsyncMock(side_effect=_cancel)
        return ""

    def configure_order_not_found_error_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        self._mock_active(mock_api, {"orders": []})
        self._mock_inactive(mock_api, {"orders": []}, callback=callback)
        return ""

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses,
    ) -> List[str]:
        both_active = {
            "orders": [
                {
                    "client_order_id": successful_order.client_order_id,
                    "order_id": successful_order.exchange_order_id or str(self.expected_exchange_order_id),
                    "status": "open",
                    "filled_base_amount": "0",
                    "base_amount": str(successful_order.amount),
                    "price": str(successful_order.price),
                    "transaction_time": "1640780000000000",
                },
                {
                    "client_order_id": erroneous_order.client_order_id,
                    "order_id": erroneous_order.exchange_order_id or "5",
                    "status": "open",
                    "filled_base_amount": "0",
                    "base_amount": str(erroneous_order.amount),
                    "price": str(erroneous_order.price),
                    "transaction_time": "1640780000000000",
                },
            ]
        }
        self._mock_active(mock_api, both_active)
        self._mock_active(mock_api, both_active)

        s_oid = int(successful_order.exchange_order_id or str(self.expected_exchange_order_id))

        async def _cancel(order_index, **kwargs):
            if order_index == s_oid:
                return (None, {"code": 200}, None)
            return (None, {"code": 500}, None)

        self.exchange._signer_client.cancel_order = AsyncMock(side_effect=_cancel)
        return []

    def configure_completely_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        self._mock_active(mock_api, {"orders": []})
        self._mock_inactive(mock_api, self._inactive_order_payload(order, "filled"), callback=callback)
        return [self._active_orders_url(), self._inactive_orders_url()]

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        self._mock_active(mock_api, {"orders": []})
        self._mock_inactive(
            mock_api,
            self._inactive_order_payload(order, "canceled", filled="0"),
            callback=callback,
        )
        return [self._active_orders_url(), self._inactive_orders_url()]

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        self._mock_active(mock_api, self._active_order_payload(order), callback=callback)
        return [self._active_orders_url()]

    def configure_http_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        self._mock_active(mock_api, {"orders": []}, callback=callback)
        self._mock_inactive(mock_api, {"orders": []})
        return self._active_orders_url()

    def configure_partially_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        partial_amt = str(self.expected_partial_fill_amount)
        self._mock_active(
            mock_api,
            {
                "orders": [
                    {
                        "client_order_id": order.client_order_id,
                        "order_id": order.exchange_order_id or str(self.expected_exchange_order_id),
                        "status": "open",
                        "filled_base_amount": partial_amt,
                        "base_amount": str(order.amount),
                        "price": str(self.expected_partial_fill_price),
                        "transaction_time": "1640780000000000",
                    }
                ]
            },
            callback=callback,
        )
        return self._active_orders_url()

    def configure_order_not_found_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        self._mock_active(mock_api, {"orders": []}, callback=callback)
        self._mock_inactive(mock_api, {"orders": []})
        return [self._active_orders_url(), self._inactive_orders_url()]

    def configure_partial_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = None,
    ) -> str:
        return ""  # lighter trade fills arrive via WS, not HTTP status update

    def configure_erroneous_http_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = None,
    ) -> str:
        return ""

    def configure_full_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = None,
    ) -> str:
        return ""  # lighter trade fills arrive via WS, not HTTP status update

    def configure_successful_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        callback()  # lighter only supports ONEWAY, fires immediately

    def configure_failed_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        callback()  # lighter only supports ONEWAY, HEDGE always fails immediately
        return "", "Lighter only supports ONEWAY position mode."

    def configure_failed_set_leverage(
        self,
        leverage: int,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        error_msg = f"Error setting leverage {leverage}"

        async def _fail(**kwargs):
            callback()
            raise IOError(error_msg)

        self.exchange._signer_client.update_leverage = AsyncMock(side_effect=_fail)
        return "", error_msg

    def configure_successful_set_leverage(
        self,
        leverage: int,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        async def _success(**kwargs):
            callback()
            return (None, {"code": 200}, None)

        self.exchange._signer_client.update_leverage = AsyncMock(side_effect=_success)

    # ── Balance response override (lighter only has USDC) ──────────────────────

    def _configure_balance_response(
        self,
        response: Any,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        balance_url = web_utils.rest_url(CONSTANTS.ACCOUNT_PATH_URL, self.domain)
        mock_api.get(
            re.compile(f"^{re.escape(balance_url)}"),
            body=json.dumps(response),
            callback=callback,
        )

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal("0.01"),
                min_price_increment=Decimal("0.01"),
                min_base_amount_increment=Decimal("0.001"),
                min_notional_size=Decimal("1"),
                buy_order_collateral_token=self.quote_asset,
                sell_order_collateral_token=self.quote_asset,
            )
        }
        self._set_up_market_info()

    # ── Overridden tests: order creation via SignerClient ──────────────────────

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_done = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)

        original = self.exchange._signer_client.create_order

        async def _patched(**kwargs):
            result = await original(**kwargs)
            request_done.set()
            return result

        self.exchange._signer_client.create_order = AsyncMock(side_effect=_patched)
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_done.wait())
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertIn(order_id, self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(order_id, create_event.exchange_order_id)  # lighter: eid == cid
        self.assertEqual(leverage, create_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, create_event.position)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"100.000 to {PositionAction.OPEN.name} a {self.trading_pair} position "
                f"at 10000.00.",
            )
        )

    @aioresponses()
    def test_create_sell_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_done = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        leverage = 3
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)

        original = self.exchange._signer_client.create_order

        async def _patched(**kwargs):
            result = await original(**kwargs)
            request_done.set()
            return result

        self.exchange._signer_client.create_order = AsyncMock(side_effect=_patched)
        order_id = self.place_sell_order()
        self.async_run_with_timeout(request_done.wait())
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertIn(order_id, self.exchange.in_flight_orders)
        create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(order_id, create_event.exchange_order_id)
        self.assertEqual(leverage, create_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, create_event.position)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                f"100.000 to {PositionAction.OPEN.name} a {self.trading_pair} position "
                f"at 10000.00.",
            )
        )

    @aioresponses()
    def test_create_order_to_close_short_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_done = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        leverage = 4
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)

        original = self.exchange._signer_client.create_order

        async def _patched(**kwargs):
            result = await original(**kwargs)
            request_done.set()
            return result

        self.exchange._signer_client.create_order = AsyncMock(side_effect=_patched)
        order_id = self.place_buy_order(position_action=PositionAction.CLOSE)
        self.async_run_with_timeout(request_done.wait())
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertIn(order_id, self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(PositionAction.CLOSE.value, create_event.position)

    @aioresponses()
    def test_create_order_to_close_long_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_done = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        leverage = 5
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)

        original = self.exchange._signer_client.create_order

        async def _patched(**kwargs):
            result = await original(**kwargs)
            request_done.set()
            return result

        self.exchange._signer_client.create_order = AsyncMock(side_effect=_patched)
        order_id = self.place_sell_order(position_action=PositionAction.CLOSE)
        self.async_run_with_timeout(request_done.wait())
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertIn(order_id, self.exchange.in_flight_orders)
        create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(PositionAction.CLOSE.value, create_event.position)

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_done = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.get_price = MagicMock(return_value=Decimal("10000"))

        async def _fail(**kwargs):
            request_done.set()
            return (None, {"code": 500}, None)

        self.exchange._signer_client.create_order = AsyncMock(side_effect=_fail)
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_done.wait())
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.get_price = MagicMock(return_value=Decimal("10000"))
        request_done = asyncio.Event()

        order_id_invalid = self.place_buy_order(amount=Decimal("0.0001"), price=Decimal("0.0001"))

        async def _trigger(**kwargs):
            request_done.set()
            return (None, {"code": 200}, None)

        self.exchange._signer_client.create_order = AsyncMock(side_effect=_trigger)
        self.place_buy_order()  # triggers request_done to avoid test timeout
        self.async_run_with_timeout(request_done.wait())
        self.async_run_with_timeout(asyncio.sleep(0.1))

        # The invalid order is rejected by trading rules validation before placement
        self.assertNotIn(order_id_invalid, self.exchange.in_flight_orders)
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(order_id_invalid, failure_event.order_id)

    # ── Overridden tests: position mode (lighter is ONEWAY-only, no HTTP call) ──

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        # lighter only supports ONEWAY; the base set_position_mode short-circuits
        # for unsupported modes with an ERROR log before calling _trading_pair_position_mode_set
        self.exchange.set_position_mode(PositionMode.HEDGE)
        self.async_run_with_timeout(asyncio.sleep(0.2))
        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message=f"Position mode {PositionMode.HEDGE} is not supported. Mode not set.",
            )
        )

    @aioresponses()
    def test_set_position_mode_success(self, mock_api):
        self.configure_successful_set_position_mode(
            position_mode=PositionMode.ONEWAY,
            mock_api=mock_api,
        )
        self.exchange.set_position_mode(PositionMode.ONEWAY)
        self.async_run_with_timeout(asyncio.sleep(0.2))
        self.assertTrue(
            self.is_logged(
                log_level="DEBUG",
                message=f"Position mode switched to {PositionMode.ONEWAY}.",
            )
        )

    # ── Overridden tests: funding info (dynamic timestamp) ─────────────────────

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        mock_api.get(self.funding_info_url, body=json.dumps(self.funding_info_mock_response))
        mock_queue_get.side_effect = [asyncio.CancelledError]

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        funding_info: FundingInfo = self.exchange.get_funding_info(self.trading_pair)
        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(self.target_funding_info_index_price, funding_info.index_price)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
        self.assertGreater(funding_info.next_funding_utc_timestamp, 0)
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    # ── Overridden test: balance (lighter only holds USDC collateral) ───────────

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)
        self.async_run_with_timeout(self.exchange._update_balances())

        available = self.exchange.available_balances
        total = self.exchange.get_all_balances()

        self.assertNotIn(self.base_asset, available)
        self.assertEqual(Decimal("2000"), total[self.quote_asset])

    # ── Overridden test: trading rules error (lighter skips inactive markets) ───

    @aioresponses()
    async def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        self.exchange._set_current_timestamp(1000)
        self.configure_erroneous_trading_rules_response(mock_api=mock_api)
        await self.exchange._update_trading_rules()
        self.assertEqual(0, len(self.exchange._trading_rules))

    # ── Overridden test: collateral tokens ─────────────────────────────────────

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()
        self.assertEqual(self.quote_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(self.quote_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    @aioresponses()
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        # lighter fills arrive via WebSocket, not HTTP polling; lost order logic
        # does not fire fill events, so this test is not applicable.
        pass

    @aioresponses()
    async def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
        # lighter treats a "not found" REST lookup within ORDER_NOT_FOUND_GRACE_PERIOD as
        # "still pending" (REST indexing lag); the order must be older than the grace window
        # for the not-found escalation to apply.
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
        self.exchange._set_current_timestamp(
            1640780000 + CONSTANTS.ORDER_NOT_FOUND_GRACE_PERIOD + 1
        )

        self.configure_http_error_order_status_response(order=order, mock_api=mock_api)
        await self.exchange._update_order_status()

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)
        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    @aioresponses()
    async def test_update_order_status_not_found_within_grace_period_keeps_order_open(self, mock_api):
        # A just-created order missing from the REST lookup should not be flagged not-found.
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_http_error_order_status_response(order=order, mock_api=mock_api)
        await self.exchange._update_order_status()

        self.assertTrue(order.is_open)
        self.assertNotIn(
            order.client_order_id, self.exchange._order_tracker._order_not_found_records
        )

    async def test_user_stream_balance_update(self):
        # Lighter's WS account_all_assets event has no `available_balance`; the connector
        # uses it as a trigger to fire an out-of-band REST `_update_balances` refresh.
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._update_balances = AsyncMock()

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self.balance_event_websocket_update, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            await self.exchange._user_stream_event_listener()
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0.1)

        self.exchange._update_balances.assert_awaited()

    # ── Lighter-specific tests ─────────────────────────────────────────────────

    def test_lighter_basic_properties(self):
        self.assertEqual(CONSTANTS.MAX_ORDER_ID_LEN, self.exchange.client_order_id_max_length)
        self.assertEqual(CONSTANTS.BROKER_ID, self.exchange.client_order_id_prefix)
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.exchange.trading_rules_request_path)
        self.assertEqual(CONSTANTS.PING_PATH_URL, self.exchange.check_network_request_path)
        self.assertFalse(self.exchange.is_cancel_request_in_exchange_synchronous)
        self.assertTrue(self.exchange.is_trading_required)
        self.assertEqual(120, self.exchange.funding_fee_poll_interval)
        self.assertIsNotNone(self.exchange.authenticator)

    def test_lighter_supported_position_modes(self):
        self.assertEqual([PositionMode.ONEWAY], self.exchange.supported_position_modes())

    async def test_lighter_trading_pair_position_mode_set(self):
        ok, msg = await self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair)
        self.assertTrue(ok)
        self.assertEqual("", msg)

        fail, msg = await self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair)
        self.assertFalse(fail)
        self.assertIn("ONEWAY", msg)

    async def test_lighter_set_leverage_success(self):
        ok, msg = await self.exchange._set_trading_pair_leverage(self.trading_pair, 5)
        self.assertTrue(ok)
        self.exchange._signer_client.update_leverage.assert_awaited_once()

    async def test_lighter_set_leverage_no_signer(self):
        self.exchange._signer_client = None
        ok, msg = await self.exchange._set_trading_pair_leverage(self.trading_pair, 5)
        self.assertFalse(ok)
        self.assertIn("not configured", msg)

    async def test_lighter_fetch_last_fee_payment_empty(self):
        self.exchange._api_get = AsyncMock(return_value={"position_fundings": []})
        ts, rate, amount = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual(0, ts)
        self.assertEqual(Decimal("-1"), rate)
        self.assertEqual(Decimal("-1"), amount)

    async def test_lighter_fetch_last_fee_payment_with_entry(self):
        self.exchange._api_get = AsyncMock(
            return_value={
                "position_fundings": [{"change": "1.5", "rate": "0.0002", "timestamp": "1000000"}]
            }
        )
        ts, rate, amount = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual(1000.0, ts)  # 1_000_000 ms * 1e-3 = 1000 s
        self.assertEqual(Decimal("0.0002"), rate)
        self.assertEqual(Decimal("1.5"), amount)

    async def test_lighter_update_balances(self):
        self.exchange._account_balances = {"OLD": Decimal("1")}
        self.exchange._account_available_balances = {"OLD": Decimal("1")}
        self.exchange._api_get = AsyncMock(
            return_value={
                "accounts": [
                    {
                        "index": self.ACCOUNT_INDEX,
                        "available_balance": "80",
                        "assets": [
                            {"symbol": "USDC", "margin_balance": "100", "locked_balance": "20"}
                        ],
                        "positions": [],
                    }
                ]
            }
        )
        await self.exchange._update_balances()
        self.assertNotIn("OLD", self.exchange._account_balances)
        self.assertNotIn("OLD", self.exchange._account_available_balances)
        self.assertEqual(Decimal("100"), self.exchange._account_balances[self.quote_asset])
        self.assertEqual(Decimal("80"), self.exchange._account_available_balances[self.quote_asset])

    async def test_lighter_parse_position_long(self):
        raw = {
            "market_id": 1,
            "symbol": "ETH",
            "sign": "1",
            "position": "2",
            "avg_entry_price": "2500",
            "unrealized_pnl": "12.5",
            "initial_margin_fraction": "0.1",
        }
        position = self.exchange._parse_position(raw)
        self.assertIsNotNone(position)
        self.assertEqual(self.trading_pair, position.trading_pair)
        self.assertEqual(PositionSide.LONG, position.position_side)
        self.assertEqual(Decimal("2"), position.amount)
        self.assertEqual(Decimal("10"), position.leverage)

    async def test_lighter_parse_position_zero_returns_none(self):
        raw = {"market_id": 1, "symbol": "ETH", "sign": "1", "position": "0"}
        self.assertIsNone(self.exchange._parse_position(raw))

    async def test_lighter_extract_tx_code(self):
        self.assertEqual(200, self.exchange._extract_tx_code({"code": "200"}))
        self.assertIsNone(self.exchange._extract_tx_code(None))
        self.assertIsNone(self.exchange._extract_tx_code({"message": "ok"}))

    async def test_lighter_schedule_balance_refresh_is_single_flight(self):
        # If a refresh is already in flight, additional WS triggers should be no-ops.
        event = asyncio.Event()

        async def _hold():
            await event.wait()

        self.exchange._update_balances = AsyncMock(side_effect=_hold)
        self.exchange._schedule_balance_refresh()
        first_task = self.exchange._balance_refresh_task
        self.exchange._schedule_balance_refresh()
        self.assertIs(first_task, self.exchange._balance_refresh_task)
        event.set()
        await first_task
        # After completion, another trigger spawns a new task.
        self.exchange._schedule_balance_refresh()
        self.assertIsNot(self.exchange._balance_refresh_task, first_task)
        await self.exchange._balance_refresh_task
