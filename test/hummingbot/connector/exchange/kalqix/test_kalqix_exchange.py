import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.exchange.kalqix import kalqix_constants as CONSTANTS, kalqix_web_utils as web_utils
from hummingbot.connector.exchange.kalqix.kalqix_exchange import KalqixExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase


class KalqixExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    """Generic-suite implementation for the REST-only KalqiX connector.

    The base suite is WebSocket-shaped; KalqiX has no WS, so the
    `*_websocket_update` hooks return the synthetic user-stream event dicts
    the connector's REST poller emits ({"event_type": ..., "order"/"trade": ...}),
    which `_user_stream_event_listener` consumes identically.
    """

    # KalqiX scales human-readable Decimals to base-unit integers on the wire.
    base_asset_decimals = 8
    quote_asset_decimals = 6

    # ------------------------------------------------------------------
    # URLs
    # ------------------------------------------------------------------

    @property
    def all_symbols_url(self):
        return web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def latest_prices_url(self):
        ticker_path = self.base_asset + "_" + self.quote_asset
        return web_utils.rest_url(f"/markets/{ticker_path}/price", domain=self.exchange._domain)

    @property
    def network_status_url(self):
        return web_utils.rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)

    @property
    def trading_rules_url(self):
        return web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def order_creation_url(self):
        return web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL, domain=self.exchange._domain)

    @property
    def balance_url(self):
        return web_utils.rest_url(CONSTANTS.POSITIONS_PATH_URL, domain=self.exchange._domain)

    # ------------------------------------------------------------------
    # Mock responses
    # ------------------------------------------------------------------

    def _market_entry(self, base: str, quote: str, status: str = "ACTIVE") -> dict:
        return {
            "ticker": self.exchange_symbol_for_tokens(base, quote),
            "base_asset": base,
            "quote_asset": quote,
            "base_asset_decimals": self.base_asset_decimals,
            "quote_asset_decimals": self.quote_asset_decimals,
            "status": status,
            "tick_size": "0.01",
            "step_size": "0.0001",
            "min_quantity_formatted": "0.001",
            "min_trade_size_formatted": "10",
            "maker_fee": "0.1",
            "taker_fee": "0.1",
        }

    @property
    def all_symbols_request_mock_response(self):
        return [self._market_entry(self.base_asset, self.quote_asset)]

    @property
    def latest_prices_request_mock_response(self):
        return {"price_formatted": str(self.expected_latest_price), "price": "0"}

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = [
            self._market_entry(self.base_asset, self.quote_asset),
            self._market_entry("INVALID", "PAIR", status="PAUSED"),
        ]
        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return [self._market_entry(self.base_asset, self.quote_asset)]

    @property
    def trading_rules_request_erroneous_mock_response(self):
        # ACTIVE (so it passes the validity filter) but missing the decimal
        # fields -> _format_trading_rules raises and skips it.
        return [{"ticker": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), "status": "ACTIVE"}]

    @property
    def order_creation_request_successful_mock_response(self):
        return {"order_id": self.expected_exchange_order_id, "client_order_id": "OID1"}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "data": [
                {"asset": self.base_asset, "available_formatted": "10", "locked_formatted": "5",
                 "total_formatted": "15"},
                {"asset": self.quote_asset, "available_formatted": "2000", "locked_formatted": "0",
                 "total_formatted": "2000"},
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "data": [
                {"asset": self.base_asset, "available_formatted": "10", "locked_formatted": "5",
                 "total_formatted": "15"},
            ]
        }

    @property
    def balance_event_websocket_update(self):
        # KalqiX does not push balances on the user stream (real_time_balance_update
        # is False), so test_user_stream_balance_update is a no-op. Required abstract.
        return {}

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        market = self._market_entry(self.base_asset, self.quote_asset)
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(market["min_quantity_formatted"]),
            min_price_increment=Decimal(market["tick_size"]),
            min_base_amount_increment=Decimal(market["step_size"]),
            min_notional_size=Decimal(market["min_trade_size_formatted"]),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_ticker = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
        return f"Error parsing market rule {erroneous_ticker}; skipping."

    @property
    def expected_exchange_order_id(self):
        return "EOID1"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        # KalqiX's order-status endpoint carries no fill detail; fills come
        # from the separate /orders/{id}/trades endpoint.
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        # Fills arrive as their own synthetic TRADE user-stream event, not via
        # an HTTP call triggered during order-event processing.
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("10500")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return TradeFeeBase.new_spot_fee(
            fee_schema=self.exchange.trade_fee_schema(),
            trade_type=TradeType.BUY,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "30000"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        # KalqiX market ticker (body form) is BASE/QUOTE.
        return f"{base_token}/{quote_token}"

    def create_exchange_instance(self):
        return KalqixExchange(
            kalqix_api_key="testAPIKey",
            kalqix_api_secret="testSecret",
            kalqix_agent_index=6,
            kalqix_agent_private_key="0" * 63 + "1",
            trading_pairs=[self.trading_pair],
        )

    def _simulate_trading_rules_initialized(self):
        super()._simulate_trading_rules_initialized()
        # KalqiX needs per-pair decimals cached before it can place orders.
        self.exchange._market_decimals[self.trading_pair] = (
            self.base_asset_decimals, self.quote_asset_decimals,
        )

    def _orders_list_regex(self):
        url = web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL)
        return re.compile(r"^" + re.escape(url) + r"\?")

    def _order_by_id_regex(self, order: InFlightOrder):
        url = web_utils.rest_url(CONSTANTS.ORDER_BY_ID_PATH_URL.format(id=order.exchange_order_id))
        return re.compile(r"^" + re.escape(url))

    def _order_trades_regex(self, order: InFlightOrder):
        url = web_utils.rest_url(CONSTANTS.ORDER_TRADES_PATH_URL.format(id=order.exchange_order_id))
        return re.compile(r"^" + re.escape(url))

    # ------------------------------------------------------------------
    # Request validation
    # ------------------------------------------------------------------

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("x-api-key", request_headers)
        self.assertIn("x-api-signature", request_headers)
        self.assertIn("x-api-timestamp", request_headers)
        self.assertEqual("testAPIKey", request_headers["x-api-key"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual("PLACE_ORDER", request_data["action"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["ticker"])
        self.assertEqual(order.trade_type.name.upper(), request_data["side"])
        self.assertEqual(CONSTANTS.ORDER_TYPE_LIMIT, request_data["order_type"])
        # Base units: 100 * 10^8 and 10000 * 10^6.
        self.assertEqual(str(int(Decimal("100") * (10 ** self.base_asset_decimals))), request_data["quantity"])
        self.assertEqual(str(int(Decimal("10000") * (10 ** self.quote_asset_decimals))), request_data["price"])
        self.assertEqual(order.client_order_id, request_data["client_order_id"])
        self.assertIn("signature", request_data)

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange.agent_index, request_params["agent_index"])
        self.assertIn("signature", request_params)

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.client_order_id, request_params["client_order_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertIn("page", request_params)
        self.assertIn("page_size", request_params)

    # ------------------------------------------------------------------
    # Cancelation configuration
    # ------------------------------------------------------------------

    def configure_successful_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._order_by_id_regex(order)
        mock_api.delete(regex_url, body=json.dumps({}), callback=callback)
        # _place_cancel confirms the outcome via GET /orders/{id}; return a
        # terminal CANCELLED status so the confirmation resolves immediately.
        confirm_response = {
            "order_id": order.exchange_order_id,
            "client_order_id": order.client_order_id,
            "status": "CANCELLED",
            "remaining_quantity": str(order.amount),
        }
        mock_api.get(regex_url, body=json.dumps(confirm_response), repeat=True)
        return regex_url

    def configure_erroneous_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._order_by_id_regex(order)
        mock_api.delete(regex_url, status=400, callback=callback)
        return regex_url

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._order_by_id_regex(order)
        response = {"code": CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE, "message": "Order not found"}
        mock_api.delete(regex_url, status=400, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self, successful_order: InFlightOrder, erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
        all_urls = []
        all_urls.append(self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api))
        all_urls.append(self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api))
        return all_urls

    # ------------------------------------------------------------------
    # Order-status configuration
    # ------------------------------------------------------------------

    def configure_completely_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._orders_list_regex()
        response = {"data": [self._order_status(order, status="FILLED", remaining="0")]}
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_canceled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._orders_list_regex()
        response = {"data": [self._order_status(order, status="CANCELLED", remaining=str(order.amount))]}
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_open_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._orders_list_regex()
        response = {"data": [self._order_status(order, status="PENDING", remaining=str(order.amount))]}
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_http_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._orders_list_regex()
        mock_api.get(regex_url, status=401, callback=callback)
        return regex_url

    def configure_partially_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._orders_list_regex()
        remaining = str(order.amount - self.expected_partial_fill_amount)
        response = {"data": [self._order_status(order, status="PARTIALLY_FILLED", remaining=remaining)]}
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        regex_url = self._orders_list_regex()
        # KalqiX signals "not found" with an empty result set; the connector
        # raises an IOError containing NOT_FOUND.
        mock_api.get(regex_url, body=json.dumps({"data": []}), callback=callback)
        return [regex_url]

    # ------------------------------------------------------------------
    # Trade (fill) configuration
    # ------------------------------------------------------------------

    def configure_partial_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._order_trades_regex(order)
        response = {"data": [self._trade_fill(
            order, price=self.expected_partial_fill_price, quantity=self.expected_partial_fill_amount)]}
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_erroneous_http_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._order_trades_regex(order)
        mock_api.get(regex_url, status=400, callback=callback)
        return regex_url

    def configure_full_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        regex_url = self._order_trades_regex(order)
        response = {"data": [self._trade_fill(order, price=order.price, quantity=order.amount)]}
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    # ------------------------------------------------------------------
    # User-stream synthetic events (REST-poll shaped)
    # ------------------------------------------------------------------

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {"event_type": "ORDER_UPDATE", "order": self._order_status(
            order, status="PENDING", remaining=str(order.amount))}

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {"event_type": "ORDER_UPDATE", "order": self._order_status(
            order, status="CANCELLED", remaining=str(order.amount))}

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {"event_type": "ORDER_UPDATE", "order": self._order_status(
            order, status="FILLED", remaining="0")}

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {"event_type": "TRADE", "trade": self._trade_fill(
            order, price=order.price, quantity=order.amount)}

    # ------------------------------------------------------------------
    # Response builders
    # ------------------------------------------------------------------

    def _order_status(self, order: InFlightOrder, status: str, remaining: str) -> dict:
        return {
            "order_id": order.exchange_order_id or "EOID1",
            "client_order_id": order.client_order_id,
            "status": status,
            "remaining_quantity": remaining,
        }

    def _trade_fill(self, order: InFlightOrder, price: Decimal, quantity: Decimal) -> dict:
        return {
            "trade_id": self.expected_fill_trade_id,
            "timestamp": 1640780000000000,
            "price_formatted": str(price),
            "quantity_formatted": str(quantity),
            "fee_formatted": str(self.expected_fill_fee.flat_fees[0].amount),
            "maker_order_id": None,
            "taker_order_id": order.exchange_order_id,
        }
