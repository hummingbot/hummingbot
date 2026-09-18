import asyncio
import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_derivative import (
    KalshiPerpetualBudgetChecker,
    KalshiPerpetualDerivative,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_candidate import PerpetualOrderCandidate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import OrderFilledEvent, SellOrderCompletedEvent

# 2021-12-29T12:13:20Z, the time the generic tests set on the exchange
NOW = 1640780000


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _regex(url: str) -> re.Pattern:
    return re.compile(f"^{re.escape(url)}")


class KalshiPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    """
    The generic tests run with a contract size of 1, so exchange and Hummingbot units are the same there. The
    Kalshi-specific tests at the end use real contract sizes to cover the per-contract conversions.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "a952bcbe-ec3b-4b5b-b8f9-11dae589608c"
        # Generated at runtime: a committed PEM would trip the detect-private-key pre-commit hook.
        cls.private_key_pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        cls.quote_asset = "USD"  # every Kalshi margin market is quoted and margined in USD
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    # ---------------------------------------------------------------------------------------------------------
    # URLs

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(CONSTANTS.MARKETS_PATH_URL)

    @property
    def latest_prices_url(self):
        return web_utils.public_rest_url(CONSTANTS.MARKET_PATH_URL.format(ticker=self.exchange_trading_pair))

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(CONSTANTS.EXCHANGE_STATUS_PATH_URL)

    @property
    def trading_rules_url(self):
        return web_utils.public_rest_url(CONSTANTS.MARKETS_PATH_URL)

    @property
    def order_creation_url(self):
        return web_utils.private_rest_url(CONSTANTS.ORDERS_PATH_URL)

    @property
    def balance_url(self):
        return web_utils.private_rest_url(CONSTANTS.BALANCE_PATH_URL)

    @property
    def funding_info_url(self):
        return _regex(web_utils.public_rest_url(CONSTANTS.FUNDING_RATE_ESTIMATE_PATH_URL))

    @property
    def funding_payment_url(self):
        return _regex(web_utils.private_rest_url(CONSTANTS.FUNDING_HISTORY_PATH_URL))

    @property
    def market_url(self) -> str:
        return web_utils.public_rest_url(CONSTANTS.MARKET_PATH_URL.format(ticker=self.exchange_trading_pair))

    @property
    def fills_url(self) -> re.Pattern:
        return _regex(web_utils.private_rest_url(CONSTANTS.FILLS_PATH_URL))

    def _order_url(self, order: InFlightOrder) -> str:
        return web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(order_id=order.exchange_order_id))

    # ---------------------------------------------------------------------------------------------------------
    # Mock responses (shaped after real Kalshi payloads)

    def _market(self, ticker: str, status: str = "active", contract_size: str = "1.000000") -> Dict[str, Any]:
        return {
            "ticker": ticker, "status": status, "title": f"{contract_size} {self.base_asset}",
            "contract_size": contract_size, "tick_size": "0.0001", "fractional_trading_enabled": False,
            "exchange_index": 0, "schedule": None, "asset_class": "Crypto", "price": "10000.0000",
            "bid": "9999.9000", "ask": "10000.1000", "leverage_estimate": 6.0522,
            "leverage_estimates": {"1000": 6.0474, "10000": 6.0427, "100000": 6.0143, "1000000": 5.8945},
            "long_leverage_estimates": {"1000": 6.7084, "10000": 6.7026, "100000": 6.6677, "1000000": 6.5208},
            "short_leverage_estimates": {"1000": 6.0493, "10000": 6.0445, "100000": 6.0162, "1000000": 5.8963},
            "reference_price": {"price": "10000.0000", "ts_ms": NOW * 1000},
            "settlement_mark_price": {"price": "10000.0000", "ts_ms": NOW * 1000},
            "liquidation_mark_price": {"price": "10000.0000", "ts_ms": NOW * 1000},
        }

    @property
    def all_symbols_request_mock_response(self):
        return {"markets": [self._market(self.exchange_trading_pair)]}

    @property
    def latest_prices_request_mock_response(self):
        return {"market": {**self._market(self.exchange_trading_pair), "price": str(self.expected_latest_price)}}

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {"markets": [
            self._market(self.exchange_trading_pair),
            self._market(self.exchange_symbol_for_tokens("INVALID", self.quote_asset), status="inactive"),
        ]}
        return "INVALID-USD", response

    @property
    def network_status_request_successful_mock_response(self):
        return {"exchange_active": True, "trading_active": True}

    @property
    def trading_rules_request_mock_response(self):
        return {"markets": [self._market(self.exchange_trading_pair, contract_size="0.100000")]}

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {"markets": [self._erroneous_market]}

    @property
    def _erroneous_market(self) -> Dict[str, Any]:
        market = self._market(self.exchange_trading_pair)
        del market["fractional_trading_enabled"]
        return market

    @property
    def order_creation_request_successful_mock_response(self):
        return {"order_id": self.expected_exchange_order_id, "client_order_id": "11",
                "fill_count": "0.00", "remaining_count": "100.00"}

    def _balance_response(self, subaccounts: List[Tuple[int, str, str]]) -> Dict[str, Any]:
        return {"settled_funds": "0", "subaccount_balances": [
            {"subaccount": subaccount, "account_equity": equity, "available_balance": available,
             "position_value": "0", "maintenance_margin": "0", "initial_margin": "0", "resting_orders_margin": "0"}
            for subaccount, equity, available in subaccounts
        ]}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        # Kalshi only holds USD: see the test_update_balances override
        return self._balance_response([(0, "2000", "1500")])

    @property
    def balance_request_mock_response_only_base(self):
        return self._balance_response([(1, "10", "10")])

    @property
    def balance_event_websocket_update(self):
        return {}  # no balance channel: see the test_user_stream_balance_update override

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.100000"),
            min_base_amount_increment=Decimal("0.100000"),
            min_price_increment=Decimal("0.001"),
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        return f"Error parsing the trading pair rule {self._erroneous_market}. Skipping..."

    @property
    def expected_exchange_order_id(self):
        return "ee587a1c-8b87-4dcf-b721-9f6f790619fa"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

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
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "d91bc706-ee49-470d-82d8-11418bda6fed"

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def funding_info_mock_response(self):
        return {
            "computed_time": _iso(NOW), "funding_rate": self.target_funding_info_rate,
            "mark_price": str(self.target_funding_info_mark_price), "market_ticker": self.exchange_trading_pair,
            "next_funding_time": _iso(self.target_funding_info_next_funding_utc_timestamp),
        }

    @property
    def market_for_funding_info_mock_response(self):
        market = self._market(self.exchange_trading_pair)
        market["reference_price"] = {"price": str(self.target_funding_info_index_price), "ts_ms": NOW * 1000}
        return {"market": market}

    @property
    def empty_funding_payment_mock_response(self):
        return {"funding_history": []}

    @property
    def funding_payment_mock_response(self):
        return {"funding_history": [{
            "market_ticker": self.exchange_trading_pair,
            "funding_time": _iso(self.target_funding_payment_timestamp),
            "funding_rate": self.target_funding_payment_funding_rate,
            "mark_price": "10000.0000",
            "funding_amount": str(self.target_funding_payment_payment_amount),
            "quantity": "1.00",
            "subaccount_number": 0,
        }]}

    # ---------------------------------------------------------------------------------------------------------
    # Exchange instance and request validation

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{CONSTANTS.MARKET_TICKER_PREFIX}{base_token}{CONSTANTS.MARKET_TICKER_SUFFIX}"

    def create_exchange_instance(self):
        exchange = KalshiPerpetualDerivative(
            kalshi_perpetual_api_key=self.api_key,
            kalshi_perpetual_private_key=self.private_key_pem,
            trading_pairs=[self.trading_pair],
        )
        # The generic setUp builds the symbol map directly, so the contract specs it would load are seeded here.
        exchange._contract_sizes[self.trading_pair] = Decimal("1")
        exchange._tick_sizes[self.trading_pair] = Decimal("0.0001")
        exchange.ACCOUNT_REFRESH_MIN_INTERVAL = 0
        # Fills refresh positions and balances, which has its own tests below; elsewhere the refresh would send
        # requests no test mocks.
        exchange._schedule_account_refresh = MagicMock()
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        headers = request_call.kwargs["headers"]
        self.assertEqual("application/json", headers["Content-Type"])
        self.assertEqual(self.api_key, headers["KALSHI-ACCESS-KEY"])
        self.assertIn("KALSHI-ACCESS-SIGNATURE", headers)
        self.assertIn("KALSHI-ACCESS-TIMESTAMP", headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["ticker"])
        self.assertEqual(order.client_order_id, request_data["client_order_id"])
        self.assertEqual("bid" if order.trade_type is TradeType.BUY else "ask", request_data["side"])
        self.assertEqual(order.amount, Decimal(request_data["count"]))
        self.assertEqual(order.price, Decimal(request_data["price"]))
        self.assertEqual(CONSTANTS.TIME_IN_FORCE_GTC, request_data["time_in_force"])
        self.assertEqual(CONSTANTS.SELF_TRADE_PREVENTION_TYPE, request_data["self_trade_prevention_type"])
        # Resting orders can't be reduce_only on Kalshi, even when closing
        self.assertNotIn("reduce_only", request_data)

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        self.assertIsNone(request_call.kwargs["data"])  # the order id travels in the path

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        self.assertIsNone(request_call.kwargs["params"])  # the order id travels in the path

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        self.assertEqual({"min_ts": int(order.creation_timestamp), "limit": 1000}, request_call.kwargs["params"])

    # ---------------------------------------------------------------------------------------------------------
    # Order endpoints

    def _order_status_response(self, order: InFlightOrder, fill_count: Decimal, remaining_count: Decimal,
                               last_update_reason: str) -> Dict[str, Any]:
        return {"order": {
            "order_id": order.exchange_order_id, "user_id": "0c3e7a4d-6b1f-4c34-9f86-2d3c8a7a9b10",
            "client_order_id": order.client_order_id, "ticker": self.exchange_trading_pair,
            "side": "bid" if order.trade_type is TradeType.BUY else "ask", "price": str(order.price),
            "fill_count": str(fill_count), "remaining_count": str(remaining_count),
            "last_update_reason": last_update_reason, "created_time": _iso(NOW), "last_update_time": _iso(NOW),
            "self_trade_prevention_type": CONSTANTS.SELF_TRADE_PREVENTION_TYPE, "order_source": "user",
        }}

    @staticmethod
    def _error_body(code: str, message: str) -> str:
        return json.dumps({"error": {"code": code, "message": message}})

    def configure_successful_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self._order_url(order)
        response = {"order_id": order.exchange_order_id, "client_order_id": order.client_order_id,
                    "reduced_by": str(order.amount)}
        mock_api.delete(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self._order_url(order)
        mock_api.delete(url, status=400, body=self._error_body("invalid_parameters", "invalid parameters"),
                        callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self._order_url(order)
        mock_api.delete(url, status=404, body=self._error_body("not_found", "not found"), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        return [
            self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api),
            self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api),
        ]

    def _configure_order_status_response(self, order: InFlightOrder, mock_api: aioresponses, callback: Callable,
                                         fill_count: Decimal, remaining_count: Decimal, reason: str) -> str:
        url = self._order_url(order)
        response = self._order_status_response(order, fill_count, remaining_count, reason)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_completely_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        return self._configure_order_status_response(order, mock_api, callback, order.amount, Decimal("0"), "Trade")

    def configure_canceled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        return self._configure_order_status_response(
            order, mock_api, callback, Decimal("0"), Decimal("0"), "MarginCancel")

    def configure_open_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        return self._configure_order_status_response(order, mock_api, callback, Decimal("0"), order.amount, "")

    def configure_http_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self._order_url(order)
        mock_api.get(url, status=500, body=self._error_body("internal_error", "internal error"), callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        return self._configure_order_status_response(
            order, mock_api, callback, self.expected_partial_fill_amount,
            order.amount - self.expected_partial_fill_amount, "Trade")

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = self._order_url(order)
        mock_api.get(url, status=404, body=self._error_body("not_found", "not found"), callback=callback)
        return [url]

    def _fill(self, order: InFlightOrder, fill_id: str, price: Decimal, count: Decimal, fees: str = "30",
              created_time: float = NOW) -> Dict[str, Any]:
        return {
            "fill_id": fill_id, "order_id": order.exchange_order_id, "is_taker": True,
            "side": "bid" if order.trade_type is TradeType.BUY else "ask", "count": str(count),
            "created_time": _iso(created_time), "ticker": self.exchange_trading_pair, "price": str(price),
            "entry_price": str(price), "fees": fees, "realized_pnl": "0", "order_source": "user",
        }

    def configure_partial_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        fill = self._fill(order, self.expected_fill_trade_id, self.expected_partial_fill_price,
                          self.expected_partial_fill_amount)
        mock_api.get(self.fills_url, body=json.dumps({"fills": [fill], "cursor": ""}), callback=callback)
        return self.fills_url

    def configure_erroneous_http_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        mock_api.get(self.fills_url, status=400, body=self._error_body("invalid_parameters", "invalid"),
                     callback=callback)
        return self.fills_url

    def configure_full_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        fill = self._fill(order, self.expected_fill_trade_id, order.price, order.amount)
        mock_api.get(self.fills_url, body=json.dumps({"fills": [fill], "cursor": ""}), callback=callback)
        return self.fills_url

    # ---------------------------------------------------------------------------------------------------------
    # User stream messages (as queued by the user stream data source)

    def _user_order_event(self, order: InFlightOrder, fill_count: Decimal, remaining_count: Decimal):
        return {"type": "user_order", "sid": 2, "msg": {
            "order_id": order.exchange_order_id, "user_id": "0c3e7a4d-6b1f-4c34-9f86-2d3c8a7a9b10",
            "client_order_id": order.client_order_id, "ticker": self.exchange_trading_pair,
            "side": "bid" if order.trade_type is TradeType.BUY else "ask", "price": str(order.price),
            "fill_count": str(fill_count), "remaining_count": str(remaining_count),
            "created_ts_ms": NOW * 1000, "last_updated_ts_ms": NOW * 1000, "order_source": "user",
        }}

    def _fill_event(self, order: InFlightOrder, trade_id: str, price: Decimal, count: Decimal, fee_cost: str = "30",
                    ts: float = NOW) -> Dict[str, Any]:
        return {"type": "fill", "sid": 1, "msg": {
            "trade_id": trade_id, "order_id": order.exchange_order_id, "client_order_id": order.client_order_id,
            "market_ticker": self.exchange_trading_pair, "is_taker": True,
            "side": "bid" if order.trade_type is TradeType.BUY else "ask", "ts_ms": int(ts * 1000),
            "price": str(price), "count": str(count), "fee_cost": fee_cost, "post_position": str(count),
            "order_source": "user",
        }}

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return self._user_order_event(order, Decimal("0"), order.amount)

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return self._user_order_event(order, Decimal("0"), Decimal("0"))

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return self._user_order_event(order, order.amount, Decimal("0"))

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return self._fill_event(order, self.expected_fill_trade_id, order.price, order.amount)

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return None  # Kalshi has no position channel: see the test_user_stream_update_for_order_full_fill override

    def funding_info_event_for_websocket_update(self):
        return {"type": "ticker", "sid": 3, "msg": {
            "market_ticker": self.exchange_trading_pair, "price": "10000.0000",
            "reference_price": {"price": str(self.target_funding_info_index_price_ws_updated), "ts_ms": NOW * 1000},
            "settlement_mark_price": {"price": str(self.target_funding_info_mark_price_ws_updated),
                                      "ts_ms": NOW * 1000},
            "funding_rate": {"rate": self.target_funding_info_rate_ws_updated,
                             "next_funding_time_ms": self.target_funding_info_next_funding_utc_timestamp_ws_updated * 1000,
                             "ts_ms": NOW * 1000},
            "ts_ms": NOW * 1000,
        }}

    # Kalshi has no leverage or position-mode endpoints: these are unused, their tests are overridden below.

    def configure_successful_set_position_mode(self, position_mode: PositionMode, mock_api: aioresponses,
                                               callback: Optional[Callable] = lambda *args, **kwargs: None):
        return ""

    def configure_failed_set_position_mode(self, position_mode: PositionMode, mock_api: aioresponses,
                                           callback: Optional[Callable] = lambda *args, **kwargs: None
                                           ) -> Tuple[str, str]:
        return "", "Kalshi only supports one-way positions."

    def configure_successful_set_leverage(self, leverage: int, mock_api: aioresponses,
                                          callback: Optional[Callable] = lambda *args, **kwargs: None):
        return ""

    def configure_failed_set_leverage(self, leverage: int, mock_api: aioresponses,
                                      callback: Optional[Callable] = lambda *args, **kwargs: None) -> Tuple[str, str]:
        return "", ""

    # ---------------------------------------------------------------------------------------------------------
    # Generic tests overridden for Kalshi

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()
        self.assertEqual(self.quote_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(self.quote_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    @aioresponses()
    async def test_update_balances(self, mock_api):
        # Only USD exists: equity of the primary subaccount is the total, available_balance the available amount.
        response = self._balance_response([(0, "2000", "1500"), (1, "300", "300")])
        response["subaccount_balances"][0].update(
            initial_margin="12.500000", maintenance_margin="9.615384", resting_orders_margin="3.100000")
        self._configure_balance_response(response=response, mock_api=mock_api)

        await self.exchange._update_balances()

        self.assertEqual({"USD": Decimal("2000")}, self.exchange.get_all_balances())
        self.assertEqual({"USD": Decimal("1500")}, dict(self.exchange.available_balances))
        self.assertEqual({"initial_margin": Decimal("12.5"), "maintenance_margin": Decimal("9.615384"),
                          "resting_orders_margin": Decimal("3.1")}, self.exchange._margin_breakdown)
        request = self._all_executed_requests(mock_api, self.balance_url)[0]
        self.assertEqual({"compute_available_balance": "true"}, request.kwargs["params"])

        self._configure_balance_response(response=self.balance_request_mock_response_only_base, mock_api=mock_api)
        await self.exchange._update_balances()

        self.assertNotIn("USD", self.exchange.get_all_balances())
        self.assertNotIn("USD", self.exchange.available_balances)
        self.assertEqual({}, self.exchange._margin_breakdown)

    async def test_user_stream_balance_update(self):
        # No balance channel: order events and fills trigger a balance refresh over REST (tested below)
        pass

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
        # Same as the generic test, minus the position message: Kalshi positions are polled over REST.
        self.exchange._set_current_timestamp(NOW)
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
            asyncio.CancelledError,
        ]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)
        self.assertEqual(leverage, fill_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, fill_event.position)

        sell_event: SellOrderCompletedEvent = self.sell_order_completed_logger.event_log[0]
        self.assertEqual(order.amount, sell_event.base_asset_amount)
        self.assertEqual(order.amount * fill_event.price, sell_event.quote_asset_amount)
        self.assertEqual(order.exchange_order_id, sell_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)
        self.assertTrue(self.is_logged("INFO", f"SELL order {order.client_order_id} completely filled."))
        self.assertEqual(0, len(self.exchange.account_positions))

    def test_set_position_mode_success(self):
        success, message = self.async_run_with_timeout(
            self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair))

        self.assertTrue(success)
        self.assertEqual("", message)

    def test_set_position_mode_failure(self):
        success, message = self.async_run_with_timeout(
            self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair))
        self.exchange.set_position_mode(PositionMode.HEDGE)

        self.assertFalse(success)
        self.assertEqual("Kalshi only supports one-way positions.", message)
        self.assertTrue(self.is_logged("ERROR", f"Position mode {PositionMode.HEDGE} is not supported. Mode not set."))

    @aioresponses()
    def test_set_leverage_success(self, mock_api):
        # No leverage endpoint: up to Kalshi's leverage for small positions on both sides (6.05x short), the leverage
        # is recorded locally. Set before the markets were loaded, it loads them first.
        mock_api.get(self.trading_rules_url, body=json.dumps(self.all_symbols_request_mock_response))

        self.async_run_with_timeout(self.exchange._execute_set_leverage(self.trading_pair, 6))

        self.assertTrue(self.is_logged("INFO", f"Leverage for {self.trading_pair} successfully set to 6."))
        self.assertEqual(6, self.exchange.get_leverage(self.trading_pair))

    @aioresponses()
    def test_set_leverage_failure(self, mock_api):
        mock_api.get(self.trading_rules_url, body=json.dumps(self.all_symbols_request_mock_response))

        self.async_run_with_timeout(self.exchange._execute_set_leverage(self.trading_pair, 20))

        message = (f"Kalshi allows at most 6x on {self.trading_pair} (1 / its initial margin rate); requested 20x. "
                   "Lower the leverage in the configuration.")
        self.assertTrue(self.is_logged("ERROR", f"Leverage 20 not set for {self.trading_pair}: {message}"))
        self.assertEqual(1, self.exchange.get_leverage(self.trading_pair))

    def test_set_leverage_is_rejected_without_kalshi_margin_rates(self):
        self.exchange._leverage_estimates[self.trading_pair] = {TradeType.BUY: [], TradeType.SELL: []}

        success, message = self.async_run_with_timeout(
            self.exchange._set_trading_pair_leverage(self.trading_pair, 2))

        self.assertFalse(success)
        self.assertEqual(
            f"Kalshi publishes no margin rate for {self.trading_pair} right now, so its leverage is unknown.", message)

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        # Kalshi's funding snapshot takes two requests: the market (index price) and the funding estimate.
        mock_api.get(self.market_url, body=json.dumps(self.market_for_funding_info_mock_response))
        mock_api.get(self.funding_info_url, body=json.dumps(self.funding_info_mock_response))
        mock_queue_get.side_effect = [asyncio.CancelledError]

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        funding_info = self.exchange.get_funding_info(self.trading_pair)
        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(self.target_funding_info_index_price, funding_info.index_price)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
        self.assertEqual(self.target_funding_info_next_funding_utc_timestamp, funding_info.next_funding_utc_timestamp)
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        mock_api.get(self.market_url, body=json.dumps(self.market_for_funding_info_mock_response))
        mock_api.get(self.funding_info_url, body=json.dumps(self.funding_info_mock_response))
        mock_queue_get.side_effect = [self.funding_info_event_for_websocket_update(), asyncio.CancelledError]

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, self.exchange._perpetual_trading.funding_info_stream.qsize())

    # ---------------------------------------------------------------------------------------------------------
    # Kalshi-specific tests

    def _use_contract_size(self, contract_size: str):
        self._simulate_trading_rules_initialized()
        self.exchange._contract_sizes[self.trading_pair] = Decimal(contract_size)

    def test_authenticator_is_none_without_credentials(self):
        exchange = KalshiPerpetualDerivative(trading_pairs=[self.trading_pair], trading_required=False)

        self.assertIsNone(exchange.authenticator)

    def test_available_balance_is_kalshis_rather_than_a_local_estimate(self):
        # No balance channel, but Kalshi computes the available margin; the base class's estimate treats fills as spot
        self.assertTrue(self.exchange.real_time_balance_update)

    def test_max_leverage_follows_kalshi_tiers_per_side(self):
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(self.all_symbols_request_mock_response)

        max_leverage = self.exchange.max_leverage
        self.assertEqual(Decimal("6.7084"), max_leverage(self.trading_pair, TradeType.BUY))
        self.assertEqual(Decimal("6.0493"), max_leverage(self.trading_pair, TradeType.SELL, Decimal("1000")))
        # The tier covering the notional, or the largest one beyond it
        self.assertEqual(Decimal("6.0445"), max_leverage(self.trading_pair, TradeType.SELL, Decimal("1000.01")))
        self.assertEqual(Decimal("5.8963"), max_leverage(self.trading_pair, TradeType.SELL, Decimal("5000000")))

    def test_max_leverage_falls_back_to_the_two_sided_estimates_and_is_none_without_estimates(self):
        market = self._market(self.exchange_trading_pair)
        del market["long_leverage_estimates"], market["short_leverage_estimates"]
        no_estimates = {**self._market(self.exchange_symbol_for_tokens("ETH", self.quote_asset)),
                        "leverage_estimate": None, "leverage_estimates": None,
                        "long_leverage_estimates": None, "short_leverage_estimates": None}

        self.exchange._initialize_trading_pair_symbols_from_exchange_info({"markets": [market, no_estimates]})

        self.assertEqual(Decimal("6.0474"), self.exchange.max_leverage(self.trading_pair, TradeType.BUY))
        self.assertIsNone(self.exchange.max_leverage("ETH-USD", TradeType.SELL))

    def test_budget_checker_caps_order_leverage_at_kalshis(self):
        # Executors reserve margin with their configured leverage, capped here at Kalshi's for the side and notional
        self._simulate_trading_rules_initialized()
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(self.all_symbols_request_mock_response)

        def populated(side: TradeType, leverage: int, position_close: bool = False) -> PerpetualOrderCandidate:
            return self.exchange.budget_checker.populate_collateral_entries(PerpetualOrderCandidate(
                trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT, order_side=side,
                amount=Decimal("0.1"), price=Decimal("10000"), leverage=Decimal(leverage),
                position_close=position_close))

        buy, sell = populated(TradeType.BUY, 20), populated(TradeType.SELL, 20)

        self.assertIsInstance(self.exchange.budget_checker, KalshiPerpetualBudgetChecker)
        self.assertEqual(Decimal("6.7084"), buy.leverage)
        self.assertEqual(Decimal("1000") / Decimal("6.7084"), buy.order_collateral.amount)
        self.assertEqual(Decimal("6.0493"), sell.leverage)
        self.assertEqual(Decimal("1000") / Decimal("6.0493"), sell.order_collateral.amount)
        self.assertEqual(Decimal("2"), populated(TradeType.BUY, 2).leverage)
        self.assertEqual(Decimal("20"), populated(TradeType.SELL, 20, position_close=True).leverage)

    @aioresponses()
    def test_available_balance_takes_off_orders_the_last_balance_does_not_include(self, mock_api):
        # Kalshi's available balance is polled: an order sent since then holds its estimated margin (remaining notional
        # over Kalshi's leverage) until a balance response includes it. Closing orders reserve nothing.
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(self.all_symbols_request_mock_response)
        mock_api.get(_regex(self.balance_url), body=json.dumps(self._balance_response([(0, "2000", "1500")])),
                     repeat=True)
        self.async_run_with_timeout(self.exchange._update_balances())
        for order_id, exchange_order_id, trade_type, position_action in (
                ("11", "21", TradeType.BUY, PositionAction.OPEN),
                ("12", "22", TradeType.SELL, PositionAction.CLOSE),
                ("13", None, TradeType.SELL, PositionAction.OPEN)):  # still being created
            self.exchange.start_tracking_order(
                order_id=order_id, exchange_order_id=exchange_order_id, trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT, trade_type=trade_type, price=Decimal("10000"), amount=Decimal("0.1"),
                position_action=position_action)
        buy_margin, sell_margin = Decimal("1000") / Decimal("6.7084"), Decimal("1000") / Decimal("6.0493")

        self.assertEqual(Decimal("1500") - (buy_margin + sell_margin), self.exchange.get_available_balance("USD"))

        # Kalshi had acknowledged order 11 when the balance was requested, while order 13 was still being created
        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertEqual(Decimal("1500") - sell_margin, self.exchange.get_available_balance("USD"))

    def test_markets_define_symbols_contract_sizes_and_trading_rules(self):
        markets = {"markets": [
            {**self._market("KXBTCPERP", contract_size="0.000100"), "fractional_trading_enabled": False},
            {**self._market("KXDOGEPERP", contract_size="100.000000"), "fractional_trading_enabled": True},
            self._market("KXGOLDPERP", status="inactive", contract_size="0.001000"),
        ]}

        self.exchange._initialize_trading_pair_symbols_from_exchange_info(markets)
        rules = {rule.trading_pair: rule for rule in self.async_run_with_timeout(
            self.exchange._format_trading_rules(markets))}

        self.assertEqual({"KXBTCPERP": "BTC-USD", "KXDOGEPERP": "DOGE-USD"},
                         dict(self.async_run_with_timeout(self.exchange.trading_pair_symbol_map())))
        self.assertEqual(Decimal("0.0001"), self.exchange.get_contract_size("BTC-USD"))
        # BTC: whole contracts of 0.0001 BTC, $0.0001 per contract is $1 per BTC
        self.assertEqual(Decimal("0.0001"), rules["BTC-USD"].min_order_size)
        self.assertEqual(Decimal("0.0001"), rules["BTC-USD"].min_base_amount_increment)
        self.assertEqual(Decimal("1"), rules["BTC-USD"].min_price_increment)
        # DOGE: fractional trading allows hundredths of a 100 DOGE contract
        self.assertEqual(Decimal("1"), rules["DOGE-USD"].min_base_amount_increment)
        self.assertEqual(Decimal("0.000001"), rules["DOGE-USD"].min_price_increment)
        self.assertEqual("USD", rules["BTC-USD"].buy_order_collateral_token)
        self.assertNotIn("GOLD-USD", rules)

    @aioresponses()
    def test_create_order_converts_amount_and_price_to_contracts(self, mock_api):
        self._use_contract_size("0.0001")
        mock_api.post(self.order_creation_url, body=json.dumps(self.order_creation_request_successful_mock_response))

        exchange_order_id, _ = self.async_run_with_timeout(self.exchange._place_order(
            order_id="11", trading_pair=self.trading_pair, amount=Decimal("0.0003"), trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT, price=Decimal("77820"), position_action=PositionAction.OPEN))

        request = self._all_executed_requests(mock_api, self.order_creation_url)[0]
        self.assertEqual({
            "ticker": self.exchange_trading_pair, "client_order_id": "11", "side": "bid", "count": "3.00",
            "price": "7.7820", "time_in_force": "good_till_canceled", "self_trade_prevention_type": "taker_at_cross",
        }, json.loads(request.kwargs["data"]))
        self.assertEqual(self.expected_exchange_order_id, exchange_order_id)

    @aioresponses()
    def test_create_limit_maker_order_is_post_only(self, mock_api):
        self._simulate_trading_rules_initialized()
        mock_api.post(self.order_creation_url, body=json.dumps(self.order_creation_request_successful_mock_response))

        self.async_run_with_timeout(self.exchange._place_order(
            order_id="11", trading_pair=self.trading_pair, amount=Decimal("1"), trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT_MAKER, price=Decimal("10000"), position_action=PositionAction.OPEN))

        request_data = json.loads(self._all_executed_requests(mock_api, self.order_creation_url)[0].kwargs["data"])
        self.assertTrue(request_data["post_only"])
        self.assertEqual("ask", request_data["side"])
        self.assertEqual(CONSTANTS.TIME_IN_FORCE_GTC, request_data["time_in_force"])

    @aioresponses()
    def test_create_market_order_is_immediate_limit_order_through_the_book(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange.get_price = MagicMock(return_value=Decimal("10000"))
        mock_api.post(self.order_creation_url, body=json.dumps(self.order_creation_request_successful_mock_response),
                      repeat=True)

        for trade_type in (TradeType.BUY, TradeType.SELL):
            self.async_run_with_timeout(self.exchange._place_order(
                order_id="11", trading_pair=self.trading_pair, amount=Decimal("1"), trade_type=trade_type,
                order_type=OrderType.MARKET, price=Decimal("NaN"), position_action=PositionAction.CLOSE))

        buy, sell = [json.loads(request.kwargs["data"])
                     for request in self._all_executed_requests(mock_api, self.order_creation_url)]
        # 5% through the best price, immediate-or-cancel, and reduce_only because it closes a position
        self.assertEqual(("10500.0000", "immediate_or_cancel", True),
                         (buy["price"], buy["time_in_force"], buy["reduce_only"]))
        self.assertEqual("9500.0000", sell["price"])
        self.exchange.get_price.assert_any_call(self.trading_pair, is_buy=True)
        self.exchange.get_price.assert_any_call(self.trading_pair, is_buy=False)

    def _set_position(self, amount: str):
        position_side = PositionSide.LONG if Decimal(amount) > 0 else PositionSide.SHORT
        self.exchange._perpetual_trading.set_position(self.trading_pair, Position(
            trading_pair=self.trading_pair, position_side=position_side, unrealized_pnl=Decimal("0"),
            entry_price=Decimal("10000"), amount=Decimal(amount), leverage=Decimal("1")))

    def test_create_order_to_close_short_position(self):
        # Resting closes need a position to close
        self._set_position("-100")
        super().test_create_order_to_close_short_position()

    def test_create_order_to_close_long_position(self):
        self._set_position("100")
        super().test_create_order_to_close_long_position()

    @aioresponses()
    def test_resting_close_order_without_position_is_rejected_after_refreshing_positions(self, mock_api):
        self._simulate_trading_rules_initialized()
        self._set_position("1")  # a long position: a buy would add to it
        positions_url = web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL)
        mock_api.get(_regex(positions_url), body=json.dumps({"positions": []}))

        with self.assertRaises(ValueError):
            self.async_run_with_timeout(self.exchange._place_order(
                order_id="11", trading_pair=self.trading_pair, amount=Decimal("1"), trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT, price=Decimal("10000"), position_action=PositionAction.CLOSE))

        self.assertEqual(1, len(self._all_executed_requests(mock_api, positions_url)))
        self.assertEqual([], self._all_executed_requests(mock_api, self.order_creation_url))

    @aioresponses()
    def test_resting_close_order_is_placed_when_refreshed_positions_include_the_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        position = {"subaccount": 0, "market_ticker": self.exchange_trading_pair, "position": "-1.00",
                    "entry_price": "10000", "unrealized_pnl": "0", "fees": "0", "is_portfolio": False}
        mock_api.get(_regex(web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL)),
                     body=json.dumps({"positions": [position]}))
        mock_api.post(self.order_creation_url, body=json.dumps(self.order_creation_request_successful_mock_response))

        self.async_run_with_timeout(self.exchange._place_order(
            order_id="11", trading_pair=self.trading_pair, amount=Decimal("1"), trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT_MAKER, price=Decimal("10000"), position_action=PositionAction.CLOSE))

        request_data = json.loads(self._all_executed_requests(mock_api, self.order_creation_url)[0].kwargs["data"])
        self.assertNotIn("reduce_only", request_data)

    @aioresponses()
    def test_update_positions_cancels_resting_close_orders_left_without_a_position(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(NOW)
        self._set_position("-1")
        for order_id, trade_type, position_action in (("stale", TradeType.BUY, PositionAction.CLOSE),
                                                      ("open", TradeType.BUY, PositionAction.OPEN)):
            self.exchange.start_tracking_order(
                order_id=order_id, exchange_order_id=f"ex-{order_id}", trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT, trade_type=trade_type, price=Decimal("10000"), amount=Decimal("1"),
                position_action=position_action)
        self.exchange._set_current_timestamp(NOW + 1)
        # Placed as the request is sent: it may close a position the response doesn't include yet, so another
        # refresh checks it again
        self.exchange.start_tracking_order(
            order_id="fresh", exchange_order_id="ex-fresh", trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY, price=Decimal("10000"), amount=Decimal("1"), position_action=PositionAction.CLOSE)
        self.exchange._execute_cancel = AsyncMock()
        mock_api.get(_regex(web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL)), body=json.dumps({"positions": []}))

        self.async_run_with_timeout(self.exchange._update_positions())
        self.async_run_with_timeout(asyncio.sleep(0))

        self.exchange._execute_cancel.assert_awaited_once_with(self.trading_pair, "stale")
        self.exchange._schedule_account_refresh.assert_called_once_with()

    def test_order_state_is_derived_from_fill_and_remaining_counts(self):
        self._use_contract_size("0.0001")
        self.exchange.start_tracking_order(
            order_id="11", exchange_order_id="21", trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY, price=Decimal("77820"), amount=Decimal("0.0003"))
        order = self.exchange.in_flight_orders["11"]

        self.assertEqual(OrderState.OPEN, self.exchange._order_state(order, "0.00", "3.00"))
        self.assertEqual(OrderState.PARTIALLY_FILLED, self.exchange._order_state(order, "1.00", "2.00"))
        self.assertEqual(OrderState.FILLED, self.exchange._order_state(order, "3.00", "0.00"))
        # Partially filled, then the rest cancelled (or an unfilled IOC)
        self.assertEqual(OrderState.CANCELED, self.exchange._order_state(order, "1.00", "0.00"))
        self.assertEqual(OrderState.CANCELED, self.exchange._order_state(order, "0.00", "0.00"))

    def test_user_stream_fill_is_converted_to_underlying_units(self):
        self._use_contract_size("0.0001")
        self.exchange._set_current_timestamp(NOW)
        self.exchange.start_tracking_order(
            order_id="11", exchange_order_id="21", trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY, price=Decimal("77825"), amount=Decimal("0.0003"),
            position_action=PositionAction.OPEN)
        order = self.exchange.in_flight_orders["11"]

        self.exchange._process_fill_event(
            self._fill_event(order, "t-1", Decimal("7.7825"), Decimal("3.00"), fee_cost="0.0280")["msg"])

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("77825"), fill_event.price)
        self.assertEqual(Decimal("0.0003"), fill_event.amount)
        self.assertEqual([TokenAmount(token="USD", amount=Decimal("0.0280"))], fill_event.trade_fee.flat_fees)

    def test_user_stream_ignores_events_for_untracked_orders(self):
        self.exchange._set_current_timestamp(NOW)
        untracked = InFlightOrder(client_order_id="99", exchange_order_id="liquidation-1",
                                  trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
                                  trade_type=TradeType.SELL, amount=Decimal("1"), creation_timestamp=NOW,
                                  price=Decimal("10000"))

        self.exchange._process_fill_event(self._fill_event(untracked, "t-1", Decimal("10000"), Decimal("1"))["msg"])
        self.exchange._process_order_event(self._user_order_event(untracked, Decimal("1"), Decimal("0"))["msg"])

        self.assertEqual(0, len(self.order_filled_logger.event_log))

    def _track_order_for_rest_fills(self) -> InFlightOrder:
        self.exchange._set_current_timestamp(NOW - 100)
        self.exchange.start_tracking_order(
            order_id="11", exchange_order_id="21", trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY, price=Decimal("10000"), amount=Decimal("1"),
            position_action=PositionAction.OPEN)
        self.exchange._set_current_timestamp(NOW)
        return self.exchange.in_flight_orders["11"]

    @aioresponses()
    def test_rest_fills_add_only_the_fills_the_websocket_missed(self, mock_api):
        order = self._track_order_for_rest_fills()
        # The websocket missed the first fill and delivered the second, whose trade_id is the REST fill_id
        self.exchange._process_fill_event(
            self._fill_event(order, "fill-2", Decimal("10000"), Decimal("0.6"), ts=NOW - 30)["msg"])
        other_order_fill = {**self._fill(order, "fill-other", Decimal("10000"), Decimal("1"), created_time=NOW - 50),
                            "order_id": "99"}
        fills = [self._fill(order, "fill-2", Decimal("10000"), Decimal("0.6"), created_time=NOW - 30),
                 other_order_fill,
                 self._fill(order, "fill-1", Decimal("10000"), Decimal("0.4"), created_time=NOW - 60)]
        mock_api.get(self.fills_url, body=json.dumps({"fills": fills, "cursor": ""}))

        self.async_run_with_timeout(self.exchange._update_orders_fills([order]))

        self.assertEqual({"fill-1", "fill-2"}, set(order.order_fills))
        self.assertEqual(Decimal("1"), order.executed_amount_base)
        self.assertEqual(2, len(self.order_filled_logger.event_log))

    @aioresponses()
    def test_rest_fills_follow_the_pagination_cursor(self, mock_api):
        order = self._track_order_for_rest_fills()
        first_page = [self._fill(order, "rest-1", Decimal("10000"), Decimal("0.4"), created_time=NOW - 60)]
        second_page = [self._fill(order, "rest-2", Decimal("10000"), Decimal("0.6"), created_time=NOW - 30)]
        mock_api.get(self.fills_url, body=json.dumps({"fills": first_page, "cursor": "page-2"}))
        mock_api.get(self.fills_url, body=json.dumps({"fills": second_page, "cursor": ""}))

        trade_updates = self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))

        self.assertEqual(["rest-1", "rest-2"], [trade_update.trade_id for trade_update in trade_updates])
        requests = self._all_executed_requests(mock_api, self.fills_url)
        self.assertEqual({"min_ts": NOW - 100, "limit": 1000}, requests[0].kwargs["params"])
        self.assertEqual({"min_ts": NOW - 100, "limit": 1000, "cursor": "page-2"}, requests[1].kwargs["params"])

    @aioresponses()
    def test_rest_fills_of_all_orders_are_fetched_with_a_single_request(self, mock_api):
        first_order = self._track_order_for_rest_fills()
        self.exchange.start_tracking_order(
            order_id="12", exchange_order_id="22", trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL, price=Decimal("10000"), amount=Decimal("1"),
            position_action=PositionAction.OPEN)
        self.exchange.start_tracking_order(
            order_id="13", exchange_order_id=None, trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY, price=Decimal("10000"), amount=Decimal("1"),
            position_action=PositionAction.OPEN)
        second_order = self.exchange.in_flight_orders["12"]
        pending_order = self.exchange.in_flight_orders["13"]
        fills = [self._fill(first_order, "fill-1", Decimal("10000"), Decimal("0.4"), created_time=NOW - 60),
                 self._fill(second_order, "fill-2", Decimal("10000"), Decimal("0.6"), created_time=NOW - 30)]
        mock_api.get(self.fills_url, body=json.dumps({"fills": fills, "cursor": ""}))

        self.async_run_with_timeout(self.exchange._update_orders_fills([first_order, second_order, pending_order]))

        self.assertEqual({"fill-1"}, set(first_order.order_fills))
        self.assertEqual({"fill-2"}, set(second_order.order_fills))
        requests = self._all_executed_requests(mock_api, self.fills_url)
        self.assertEqual(1, len(requests))
        self.assertEqual({"min_ts": NOW - 100, "limit": 1000}, requests[0].kwargs["params"])

    @aioresponses()
    def test_rest_fills_network_error_logs_once_and_the_next_poll_recovers_the_fills(self, mock_api):
        order = self._track_order_for_rest_fills()
        error = aiohttp.ClientConnectionError("Cannot connect to host external-api.kalshi.com:443 ssl:default")
        mock_api.get(self.fills_url, exception=error)
        fills = [self._fill(order, "fill-1", Decimal("10000"), Decimal("0.4"), created_time=NOW - 60)]
        mock_api.get(self.fills_url, body=json.dumps({"fills": fills, "cursor": ""}))

        self.async_run_with_timeout(self.exchange._update_orders_fills([order]))

        failures = [record for record in self.log_records
                    if record.getMessage().startswith("Failed to fetch trade updates")]
        self.assertEqual(1, len(failures))
        self.assertEqual("WARNING", failures[0].levelname)
        self.assertIsNone(failures[0].exc_info)
        self.assertEqual({}, order.order_fills)

        self.async_run_with_timeout(self.exchange._update_orders_fills([order]))

        self.assertEqual({"fill-1"}, set(order.order_fills))

    @aioresponses()
    def test_repeated_rest_fill_triggers_only_one_event(self, mock_api):
        order = self._track_order_for_rest_fills()
        fills = [self._fill(order, "rest-1", Decimal("10000"), Decimal("0.4"), created_time=NOW - 60)]
        mock_api.get(self.fills_url, body=json.dumps({"fills": fills, "cursor": ""}), repeat=True)

        self.async_run_with_timeout(self.exchange._update_orders_fills([order]))
        self.async_run_with_timeout(self.exchange._update_orders_fills([order]))

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(Decimal("0.4"), order.executed_amount_base)

    @aioresponses()
    def test_update_positions_converts_units_and_removes_closed_positions(self, mock_api):
        self._use_contract_size("0.0001")
        positions_url = web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL)
        position = {"subaccount": 0, "market_ticker": self.exchange_trading_pair, "position": "-3.00",
                    "entry_price": "7.7825", "unrealized_pnl": "1.5000", "fees": "0.0280", "is_portfolio": False}
        untracked = {**position, "market_ticker": "KXUNKNOWNPERP", "position": "5.00"}
        mock_api.get(_regex(positions_url), body=json.dumps({"positions": [position, untracked]}))
        mock_api.get(_regex(positions_url), body=json.dumps({"positions": []}))

        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(1, len(self.exchange.account_positions))
        position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual(PositionSide.SHORT, position.position_side)
        self.assertEqual(Decimal("-0.0003"), position.amount)
        self.assertEqual(Decimal("77825"), position.entry_price)
        self.assertEqual(Decimal("1.5000"), position.unrealized_pnl)

        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(0, len(self.exchange.account_positions))

    def _track_pending_order(self) -> InFlightOrder:
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(NOW)
        self.exchange.start_tracking_order(
            order_id="11", exchange_order_id=None, trading_pair=self.trading_pair, order_type=OrderType.MARKET,
            trade_type=TradeType.BUY, price=Decimal("10000"), amount=Decimal("1"),
            position_action=PositionAction.OPEN)
        return self.exchange.in_flight_orders["11"]

    def _place_order_filled_by_the_stream_first(self, order: InFlightOrder, update_applied: bool):
        """
        The creation response comes back after the user stream reported the order filled, with the stream's order
        update either already applied or still queued.
        """
        async def place_order(**kwargs):
            fill = self._fill_event(order, "t-1", Decimal("10000"), Decimal("1"))["msg"]
            user_order = self._user_order_event(order, Decimal("1"), Decimal("0"))["msg"]
            for message in (fill, user_order):
                message["order_id"] = self.expected_exchange_order_id
            self.exchange._process_fill_event(fill)
            self.exchange._process_order_event(user_order)
            if update_applied:
                await asyncio.sleep(0.01)
            return self.expected_exchange_order_id, NOW

        self.exchange._place_order = place_order
        self.async_run_with_timeout(self.exchange._place_order_and_process_update(order))
        self.async_run_with_timeout(asyncio.sleep(0.01))  # lets a still-queued stream update run

    def _assert_filled_once(self, order: InFlightOrder):
        self.assertEqual(OrderState.FILLED, order.current_state)
        self.assertEqual(self.expected_exchange_order_id, order.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    def test_order_filled_by_the_stream_before_creation_returns_stays_filled(self):
        order = self._track_pending_order()

        self._place_order_filled_by_the_stream_first(order, update_applied=True)

        self._assert_filled_once(order)

    def test_order_filled_by_the_stream_with_its_update_still_queued_stays_filled(self):
        order = self._track_pending_order()

        self._place_order_filled_by_the_stream_first(order, update_applied=False)

        self._assert_filled_once(order)

    @aioresponses()
    def test_rest_fills_skip_orders_that_never_got_an_exchange_id(self, mock_api):
        # e.g. an order rejected on creation, still cached: waiting for its exchange id would stall the status
        # polling loop for GET_EX_ORDER_ID_TIMEOUT
        order = self._track_pending_order()

        trade_updates = self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))

        self.assertEqual([], trade_updates)
        self.assertEqual(0, len(mock_api.requests))

    def _configure_account_responses(self, mock_api: aioresponses, callback: Optional[Callable] = None):
        position = {"subaccount": 0, "market_ticker": self.exchange_trading_pair, "position": "3.00",
                    "entry_price": "7.7825", "unrealized_pnl": "0.0000", "fees": "0.0280", "is_portfolio": False}
        mock_api.get(_regex(web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL)),
                     body=json.dumps({"positions": [position]}), callback=callback, repeat=True)
        mock_api.get(_regex(web_utils.private_rest_url(CONSTANTS.BALANCE_PATH_URL)),
                     body=json.dumps(self._balance_response([(0, "1500", "1200")])), repeat=True)

    def _positions_requests(self, mock_api: aioresponses) -> int:
        return len(self._all_executed_requests(
            mock_api, _regex(web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL))))

    def _track_open_order(self) -> InFlightOrder:
        self._use_contract_size("0.0001")
        self.exchange._set_current_timestamp(NOW)
        self.exchange.start_tracking_order(
            order_id="11", exchange_order_id="21", trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY, price=Decimal("77825"), amount=Decimal("0.0003"),
            position_action=PositionAction.OPEN)
        del self.exchange._schedule_account_refresh  # stubbed in create_exchange_instance
        return self.exchange.in_flight_orders["11"]

    @aioresponses()
    def test_fill_refreshes_positions_and_balances(self, mock_api):
        # Neither has a websocket channel, and the status polling loop only refreshes them every LONG_POLL_INTERVAL
        order = self._track_open_order()
        self._configure_account_responses(mock_api)

        self.exchange._process_fill_event(self._fill_event(order, "t-1", Decimal("7.7825"), Decimal("3.00"))["msg"])
        self.async_run_with_timeout(self.exchange._account_refresh_task)

        self.assertEqual(Decimal("0.0003"), self.exchange.account_positions[self.trading_pair].amount)
        self.assertEqual(Decimal("1200"), self.exchange.available_balances["USD"])
        self.assertEqual(1, self._positions_requests(mock_api))

    @aioresponses()
    def test_fills_during_a_refresh_trigger_a_single_extra_refresh(self, mock_api):
        order = self._track_open_order()
        fills = [self._fill_event(order, f"t-{i}", Decimal("7.7825"), Decimal("0.50"))["msg"] for i in range(4)]
        refreshes = []

        def fills_arrive_during_the_first_refresh(*args, **kwargs):
            refreshes.append(args)
            if len(refreshes) == 1:
                for fill in fills[1:]:
                    self.exchange._process_fill_event(fill)

        self._configure_account_responses(mock_api, callback=fills_arrive_during_the_first_refresh)
        self.exchange._process_fill_event(fills[0])
        self.async_run_with_timeout(self.exchange._account_refresh_task)

        self.assertEqual(2, self._positions_requests(mock_api))

    @aioresponses()
    def test_fills_of_untracked_orders_also_refresh_positions(self, mock_api):
        # e.g. liquidations, or take-profit/stop-loss orders placed by Kalshi
        order = self._track_open_order()
        self._configure_account_responses(mock_api)
        liquidation = {**self._fill_event(order, "t-1", Decimal("7.7825"), Decimal("3.00"))["msg"],
                       "order_id": "liquidation-1", "client_order_id": ""}

        self.exchange._process_fill_event(liquidation)
        self.async_run_with_timeout(self.exchange._account_refresh_task)

        self.assertEqual(0, len(self.order_filled_logger.event_log))
        self.assertIn(self.trading_pair, self.exchange.account_positions)

    @aioresponses()
    def test_failed_refresh_is_logged_and_the_next_fill_refreshes_again(self, mock_api):
        order = self._track_open_order()
        mock_api.get(_regex(web_utils.private_rest_url(CONSTANTS.POSITIONS_PATH_URL)), status=500, body="{}")
        mock_api.get(_regex(web_utils.private_rest_url(CONSTANTS.BALANCE_PATH_URL)),
                     body=json.dumps(self._balance_response([(0, "1500", "1200")])))

        self.exchange._process_fill_event(self._fill_event(order, "t-1", Decimal("7.7825"), Decimal("1.00"))["msg"])
        self.async_run_with_timeout(self.exchange._account_refresh_task)

        self.assertTrue(self.is_logged("NETWORK", "Error refreshing balances and positions."))
        self.assertNotIn(self.trading_pair, self.exchange.account_positions)

        self._configure_account_responses(mock_api)
        self.exchange._process_fill_event(self._fill_event(order, "t-2", Decimal("7.7825"), Decimal("1.00"))["msg"])
        self.async_run_with_timeout(self.exchange._account_refresh_task)

        self.assertIn(self.trading_pair, self.exchange.account_positions)

    def test_orders_without_a_price_hold_no_estimated_margin_and_only_usd_is_adjusted(self):
        self.exchange._account_available_balances.update({"USD": Decimal("1500"), "BTC": Decimal("2")})
        self.exchange.start_tracking_order(
            order_id="11", exchange_order_id="21", trading_pair=self.trading_pair, order_type=OrderType.MARKET,
            trade_type=TradeType.BUY, price=Decimal("NaN"), amount=Decimal("0.1"), position_action=PositionAction.OPEN)

        self.assertEqual(Decimal("0"), self.exchange.estimated_order_margin(self.exchange.in_flight_orders["11"]))
        self.assertEqual(Decimal("1500"), self.exchange.get_available_balance("USD"))
        self.assertEqual(Decimal("2"), self.exchange.get_available_balance("BTC"))

    @aioresponses()
    def test_order_event_refreshes_balances_but_not_positions(self, mock_api):
        # Order events change the margin held by resting orders; only fills move positions
        order = self._track_open_order()
        self._configure_account_responses(mock_api)

        self.exchange._process_order_event(self._user_order_event(order, Decimal("0"), Decimal("3"))["msg"])
        self.async_run_with_timeout(self.exchange._account_refresh_task)

        self.assertEqual(Decimal("1200"), self.exchange.available_balances["USD"])
        self.assertEqual(0, self._positions_requests(mock_api))

    def test_events_before_a_refresh_starts_share_it_and_refreshes_are_spaced(self):
        self._track_open_order()
        self.exchange.ACCOUNT_REFRESH_MIN_INTERVAL = 1.0
        self.exchange._update_balances = AsyncMock()
        self.exchange._update_positions = AsyncMock()
        self.exchange._sleep = AsyncMock()

        self.exchange._schedule_account_refresh(positions=False)
        self.exchange._schedule_account_refresh()
        self.async_run_with_timeout(self.exchange._account_refresh_task)

        self.assertEqual(1, self.exchange._update_balances.await_count)
        self.assertEqual(1, self.exchange._update_positions.await_count)
        self.assertTrue(0 < self.exchange._sleep.await_args.args[0] <= 1.0)

    def test_stop_network_cancels_a_running_refresh(self):
        self._track_open_order()
        self.exchange._update_positions = AsyncMock(side_effect=asyncio.Event().wait)
        self.exchange._update_balances = AsyncMock()
        self.exchange._schedule_account_refresh()
        refresh = self.exchange._account_refresh_task
        self.async_run_with_timeout(asyncio.sleep(0.01))

        self.async_run_with_timeout(self.exchange.stop_network())
        self.async_run_with_timeout(asyncio.sleep(0.01))

        self.assertTrue(refresh.cancelled())
        self.assertIsNone(self.exchange._account_refresh_task)

    @aioresponses()
    def test_get_last_traded_price_is_per_underlying_unit(self, mock_api):
        self._use_contract_size("0.0001")
        mock_api.get(self.market_url, body=json.dumps(
            {"market": {**self._market(self.exchange_trading_pair, contract_size="0.000100"), "price": "7.7826"}}))

        price = self.async_run_with_timeout(self.exchange._get_last_traded_price(self.trading_pair))

        self.assertEqual(77826.0, price)

    @aioresponses()
    def test_fetch_last_fee_payment_queries_recent_funding_history(self, mock_api):
        mock_api.get(self.funding_payment_url, body=json.dumps(self.funding_payment_mock_response))
        # The generic setUp seeds a 0 ms offset sample, which pins the synchronizer to the perf counter: patch time().
        self.exchange._time_synchronizer.time = MagicMock(return_value=self.target_funding_payment_timestamp)

        timestamp, rate, amount = self.async_run_with_timeout(
            self.exchange._fetch_last_fee_payment(self.trading_pair))

        self.assertEqual((self.target_funding_payment_timestamp, Decimal("100"), Decimal("200")),
                         (timestamp, rate, amount))
        request = self._all_executed_requests(mock_api, self.funding_payment_url)[0]
        self.assertEqual({"ticker": self.exchange_trading_pair, "start_date": "2022-07-05", "end_date": "2022-07-06"},
                         request.kwargs["params"])

    def test_not_found_errors_are_recognized(self):
        not_found = IOError('Error executing request DELETE https://x. HTTP status is 404. '
                            'Error: {"error":{"code":"not_found","message":"not found"}}')
        other = IOError('Error executing request DELETE https://x. HTTP status is 400. '
                        'Error: {"error":{"code":"invalid_parameters","message":"invalid"}}')

        self.assertTrue(self.exchange._is_order_not_found_during_cancelation_error(not_found))
        self.assertTrue(self.exchange._is_order_not_found_during_status_update_error(not_found))
        self.assertFalse(self.exchange._is_order_not_found_during_cancelation_error(other))
        self.assertFalse(self.exchange._is_order_not_found_during_status_update_error(other))

    @aioresponses()
    async def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
        # Overrides the generic test: only Kalshi's not_found counts towards losing an order, not any failed request
        order = self._track_open_order()
        self.configure_http_error_order_status_response(order=order, mock_api=mock_api)

        await self.exchange._update_orders()

        self.assertTrue(order.is_open)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker._order_not_found_records)
        self.assertTrue(any(
            record.levelname == "WARNING"
            and record.getMessage().startswith(f"Error fetching status update for the active order {order.client_order_id}")
            for record in self.log_records))

    async def test_network_errors_during_status_updates_do_not_lose_the_order(self):
        order = self._track_open_order()
        self.exchange._request_order_status = AsyncMock(
            side_effect=IOError("Cannot connect to host external-api.kalshi.com:443 ssl:default"))

        for _ in range(self.exchange._order_tracker.lost_order_count_limit + 2):
            await self.exchange._update_orders()

        self.assertTrue(order.is_open)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEqual(0, len(self.order_failure_logger.event_log))

    @aioresponses()
    async def test_not_found_during_status_updates_loses_the_order(self, mock_api):
        order = self._track_open_order()
        for _ in range(self.exchange._order_tracker.lost_order_count_limit + 1):
            self.configure_order_not_found_error_order_status_response(order=order, mock_api=mock_api)
            await self.exchange._update_orders()

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_failure)

    async def test_status_update_timeout_without_exchange_order_id_counts_towards_losing_the_order(self):
        self.exchange._set_current_timestamp(NOW)
        self.exchange.start_tracking_order(
            order_id="11", exchange_order_id=None, trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY, price=Decimal("77825"), amount=Decimal("1"), position_action=PositionAction.OPEN)
        self.exchange._request_order_status = AsyncMock(side_effect=asyncio.TimeoutError())

        await self.exchange._update_orders()

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records["11"])

    async def test_status_update_timeout_with_exchange_order_id_is_retried(self):
        order = self._track_open_order()
        self.exchange._request_order_status = AsyncMock(side_effect=asyncio.TimeoutError())

        await self.exchange._update_orders()

        self.assertNotIn(order.client_order_id, self.exchange._order_tracker._order_not_found_records)

    async def test_cancel_request_timeout_does_not_count_towards_losing_the_order(self):
        order = self._track_open_order()
        self.exchange._api_delete = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await self.exchange._execute_order_cancel(order)

        self.assertIsNone(result)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker._order_not_found_records)
        self.assertTrue(self.is_logged("ERROR", f"Failed to cancel order {order.client_order_id}"))
        self.assertFalse(self.is_logged(
            "WARNING", f"Failed to cancel the order {order.client_order_id} because it does not have an exchange "
                       f"order id yet"))

    # Time synchronizer: Kalshi has no server time, so the connector keeps local time and never resyncs.

    def test_update_time_synchronizer_successfully(self):
        self.exchange._time_synchronizer.clear_time_offset_ms_samples()

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        # Offsets are relative to the perf counter, so compare the synchronized time with the wall clock instead.
        self.assertLess(abs(self.exchange._time_synchronizer.time() - time.time()), 1)

    @patch("hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils.get_current_server_time")
    def test_update_time_synchronizer_failure_is_logged(self, server_time_mock):
        async def failing_time_provider(*args, **kwargs):
            raise Exception("Dummy error")

        server_time_mock.side_effect = failing_time_provider

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self.is_logged("NETWORK", "Error getting server time."))

    @patch("hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils.get_current_server_time")
    def test_update_time_synchronizer_raises_cancelled_error(self, server_time_mock):
        server_time_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._update_time_synchronizer())

    def test_time_synchronizer_related_request_error_detection(self):
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(
            IOError('HTTP status is 401. Error: {"error":{"code":"token_authentication_failure"}}')))
