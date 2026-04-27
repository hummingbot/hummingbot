import asyncio
import base64
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class GeminiExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.SYMBOLS_PATH_URL, domain=self.exchange._domain)

    @property
    def latest_prices_url(self):
        symbol = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
        return web_utils.public_rest_url(
            path_url=CONSTANTS.TICKER_V2_PATH_URL.format(symbol=symbol),
            domain=self.exchange._domain)

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(
            path_url=CONSTANTS.SYMBOLS_PATH_URL, domain=self.exchange._domain)

    @property
    def trading_rules_url(self):
        return web_utils.public_rest_url(
            path_url=CONSTANTS.SYMBOLS_PATH_URL, domain=self.exchange._domain)

    @property
    def order_creation_url(self):
        return web_utils.private_rest_url(
            path_url=CONSTANTS.NEW_ORDER_PATH_URL, domain=self.exchange._domain)

    @property
    def balance_url(self):
        return web_utils.private_rest_url(
            path_url=CONSTANTS.BALANCES_PATH_URL, domain=self.exchange._domain)

    @property
    def all_symbols_request_mock_response(self):
        return [
            {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset).upper(),
                "base_currency": self.base_asset,
                "quote_currency": self.quote_asset,
                "tick_size": 1e-8,
                "quote_increment": 0.01,
                "min_order_size": "0.00001",
                "status": "open",
                "wrap_enabled": False,
            }
        ]

    @property
    def latest_prices_request_mock_response(self):
        return {
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset).upper(),
            "open": "9500.0",
            "high": "10100.0",
            "low": "9400.0",
            "close": str(self.expected_latest_price),
            "changes": [],
            "bid": "9998.0",
            "ask": "10001.0",
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        valid = self.all_symbols_request_mock_response[0]
        invalid = {
            "symbol": "INVALIDPAIR",
            "base_currency": "INVALID",
            "quote_currency": "PAIR",
            "tick_size": 1e-8,
            "quote_increment": 0.01,
            "min_order_size": "0.00001",
            "status": "closed",
            "wrap_enabled": False,
        }
        return "INVALID-PAIR", [valid, invalid]

    @property
    def network_status_request_successful_mock_response(self):
        return ["btcusd", "ethusd"]

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        erroneous = self.all_symbols_request_mock_response[0].copy()
        del erroneous["tick_size"]
        del erroneous["min_order_size"]
        return [erroneous]

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "order_id": str(self.expected_exchange_order_id),
            "id": str(self.expected_exchange_order_id),
            "client_order_id": "test_order_id",
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "price": "10000.00",
            "avg_execution_price": "0.00",
            "side": "buy",
            "type": "exchange limit",
            "timestampms": 1640780000000,
            "timestamp": 1640780000,
            "is_live": True,
            "is_cancelled": False,
            "is_hidden": False,
            "was_forced": False,
            "executed_amount": "0",
            "remaining_amount": "100",
            "original_amount": "100",
            "options": [],
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [
            {
                "type": "exchange",
                "currency": self.base_asset,
                "amount": "15",
                "available": "10",
                "availableForWithdrawal": "10",
            },
            {
                "type": "exchange",
                "currency": self.quote_asset,
                "amount": "2000",
                "available": "2000",
                "availableForWithdrawal": "2000",
            },
        ]

    @property
    def balance_request_mock_response_only_base(self):
        return [
            {
                "type": "exchange",
                "currency": self.base_asset,
                "amount": "15",
                "available": "10",
                "availableForWithdrawal": "10",
            },
        ]

    @property
    def balance_event_websocket_update(self):
        return {}

    async def test_user_stream_balance_update(self):
        # Gemini does not provide balance updates through websocket.
        pass

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        detail = self.trading_rules_request_mock_response[0]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(str(detail["min_order_size"])),
            min_price_increment=Decimal(str(detail["quote_increment"])),
            min_base_amount_increment=Decimal(str(detail["tick_size"])),
            min_notional_size=Decimal("0"),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule {erroneous}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 28

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
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token.lower()}{quote_token.lower()}"

    def create_exchange_instance(self):
        return GeminiExchange(
            gemini_api_key="testAPIKey",
            gemini_api_secret="testAPISecret",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs.get("headers", {})
        self.assertIn("X-GEMINI-APIKEY", request_headers)
        self.assertIn("X-GEMINI-PAYLOAD", request_headers)
        self.assertIn("X-GEMINI-SIGNATURE", request_headers)
        self.assertEqual("testAPIKey", request_headers["X-GEMINI-APIKEY"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_headers = request_call.kwargs.get("headers", {})
        b64_payload = request_headers["X-GEMINI-PAYLOAD"]
        payload = json.loads(base64.b64decode(b64_payload).decode("utf-8"))
        self.assertEqual(
            self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            payload["symbol"])
        self.assertEqual(
            "buy" if order.trade_type == TradeType.BUY else "sell",
            payload["side"])
        self.assertEqual("exchange limit", payload["type"])
        self.assertEqual(Decimal("100"), Decimal(payload["amount"]))
        self.assertEqual(Decimal("10000"), Decimal(payload["price"]))
        self.assertEqual(order.client_order_id, payload["client_order_id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_headers = request_call.kwargs.get("headers", {})
        b64_payload = request_headers["X-GEMINI-PAYLOAD"]
        payload = json.loads(base64.b64decode(b64_payload).decode("utf-8"))
        self.assertEqual(int(order.exchange_order_id), payload["order_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_headers = request_call.kwargs.get("headers", {})
        b64_payload = request_headers["X-GEMINI-PAYLOAD"]
        payload = json.loads(base64.b64decode(b64_payload).decode("utf-8"))
        self.assertEqual(int(order.exchange_order_id), payload["order_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_headers = request_call.kwargs.get("headers", {})
        b64_payload = request_headers["X-GEMINI-PAYLOAD"]
        payload = json.loads(base64.b64decode(b64_payload).decode("utf-8"))
        self.assertEqual(
            self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
            payload["symbol"])

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"result": "error", "reason": "OrderNotFound", "message": "order not found"}
        mock_api.post(regex_url, status=400, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
        all_urls = []
        url = self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api)
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api)
        all_urls.append(url)
        return all_urls

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"result": "error", "reason": "OrderNotFound", "message": "order not found"}
        mock_api.post(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": "accepted",
            "order_id": order.exchange_order_id,
            "event_id": "accepted_event_1",
            "client_order_id": order.client_order_id,
            "api_session": "test_session",
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "buy" if order.trade_type == TradeType.BUY else "sell",
            "order_type": "exchange limit",
            "timestampms": 1640780000000,
            "timestamp": 1640780000,
            "is_live": True,
            "is_cancelled": False,
            "is_hidden": False,
            "original_amount": str(order.amount),
            "price": str(order.price),
            "executed_amount": "0",
            "remaining_amount": str(order.amount),
            "avg_execution_price": "0",
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": "cancelled",
            "order_id": order.exchange_order_id,
            "event_id": "cancelled_event_1",
            "client_order_id": order.client_order_id,
            "api_session": "test_session",
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "buy" if order.trade_type == TradeType.BUY else "sell",
            "order_type": "exchange limit",
            "timestampms": 1640780000000,
            "timestamp": 1640780000,
            "is_live": False,
            "is_cancelled": True,
            "original_amount": str(order.amount),
            "price": str(order.price),
            "executed_amount": "0",
            "remaining_amount": str(order.amount),
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "type": "fill",
            "order_id": order.exchange_order_id,
            "event_id": "fill_event_1",
            "client_order_id": order.client_order_id,
            "api_session": "test_session",
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "buy" if order.trade_type == TradeType.BUY else "sell",
            "order_type": "exchange limit",
            "timestampms": 1640780000000,
            "timestamp": 1640780000,
            "is_live": False,
            "is_cancelled": False,
            "original_amount": str(order.amount),
            "price": str(order.price),
            "executed_amount": str(order.amount),
            "remaining_amount": "0",
            "avg_execution_price": str(order.price),
            "fill": {
                "trade_id": self.expected_fill_trade_id,
                "liquidity": "Taker",
                "price": str(order.price),
                "amount": str(order.amount),
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "fee_currency": self.expected_fill_fee.flat_fees[0].token,
            },
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    def test_real_time_balance_update_disabled(self):
        self.assertFalse(self.exchange.real_time_balance_update)

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError("InvalidNonce: nonce must be strictly increasing")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Nonce is too low")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Some other error")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    # === Override base methods that assume GET for Gemini's POST-based endpoints ===

    def configure_all_symbols_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        # Gemini symbols list is GET, but details per symbol require more calls
        # The base class sets up the _all_symbols_url, which in our case is /v1/symbols
        # That returns a list of symbol strings, but our _make_trading_rules_request
        # actually fetches details. For the abstract tests, the base_class does:
        #   mock_api.get(url, body=json.dumps(response))
        # But our all_symbols_request_mock_response returns a list of detail dicts
        # which is what _initialize_trading_pair_symbols_from_exchange_info expects
        url = self.all_symbols_url
        response = self.all_symbols_request_mock_response
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        url = self.trading_rules_url
        response = self.trading_rules_request_mock_response
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_erroneous_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        url = self.trading_rules_url
        response = self.trading_rules_request_erroneous_mock_response
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return [url]

    def _configure_balance_response(
            self,
            response: Any,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        # Gemini balances is POST
        url = self.balance_url
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "client_order_id": order.client_order_id,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "price": str(order.price),
            "avg_execution_price": "0",
            "side": "buy" if order.trade_type == TradeType.BUY else "sell",
            "type": "exchange limit",
            "timestampms": 1640780000000,
            "timestamp": 1640780000,
            "is_live": True,
            "is_cancelled": False,
            "executed_amount": "0",
            "remaining_amount": str(order.amount),
            "original_amount": str(order.amount),
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "client_order_id": order.client_order_id,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "buy" if order.trade_type == TradeType.BUY else "sell",
            "type": "exchange limit",
            "timestampms": 1640780000000,
            "timestamp": 1640780000,
            "is_live": False,
            "is_cancelled": True,
            "executed_amount": "0",
            "remaining_amount": str(order.amount),
            "original_amount": str(order.amount),
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return self._order_cancelation_request_successful_mock_response(order)

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "client_order_id": order.client_order_id,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "price": str(order.price),
            "avg_execution_price": str(order.price),
            "side": "buy" if order.trade_type == TradeType.BUY else "sell",
            "type": "exchange limit",
            "timestampms": 1640780000000,
            "timestamp": 1640780000,
            "is_live": False,
            "is_cancelled": False,
            "executed_amount": str(order.amount),
            "remaining_amount": "0",
            "original_amount": str(order.amount),
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "client_order_id": order.client_order_id,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "price": str(order.price),
            "avg_execution_price": str(self.expected_partial_fill_price),
            "side": "buy" if order.trade_type == TradeType.BUY else "sell",
            "type": "exchange limit",
            "timestampms": 1640780000000,
            "timestamp": 1640780000,
            "is_live": True,
            "is_cancelled": False,
            "executed_amount": str(self.expected_partial_fill_amount),
            "remaining_amount": str(order.amount - self.expected_partial_fill_amount),
            "original_amount": str(order.amount),
        }

    def _order_fill_template(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "price": str(order.price),
            "amount": str(order.amount),
            "timestamp": 1640780000,
            "timestampms": 1640780000000,
            "type": "Buy" if order.trade_type == TradeType.BUY else "Sell",
            "aggressor": True,
            "fee_currency": self.expected_fill_fee.flat_fees[0].token,
            "fee_amount": str(self.expected_fill_fee.flat_fees[0].amount),
            "tid": int(self.expected_fill_trade_id),
            "order_id": str(order.exchange_order_id),
            "client_order_id": order.client_order_id,
            "exchange": "gemini",
            "is_auction_fill": False,
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [self._order_fill_template(order)]

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        partial_fill = self._order_fill_template(order)
        partial_fill["amount"] = str(self.expected_partial_fill_amount)
        partial_fill["price"] = str(self.expected_partial_fill_price)
        return [partial_fill]

    def test_user_stream_update_for_order_failure(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "type": "rejected",
            "order_id": "100234",
            "event_id": "rejected_event_1",
            "client_order_id": "OID1",
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": "buy",
            "order_type": "exchange limit",
            "timestampms": 1640780000000,
            "reason": "InsufficientFunds",
            "is_live": False,
            "is_cancelled": False,
            "original_amount": "1",
            "price": "10000",
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        from hummingbot.core.event.events import MarketOrderFailureEvent
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_failure)
        self.assertTrue(order.is_done)

    async def test_user_stream_logs_errors(self):
        self.exchange._set_current_timestamp(1640780000)

        incomplete_event = "Invalid message"

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        with patch(f"{type(self.exchange).__module__}.{type(self.exchange).__qualname__}._sleep"):
            try:
                await self.exchange._user_stream_event_listener()
            except asyncio.CancelledError:
                pass
        await asyncio.sleep(0.1)

        self.assertTrue(
            self.is_logged(
                "ERROR",
                "Unexpected error in user stream listener loop."
            )
        )

    @aioresponses()
    def test_update_balances_removes_old_assets(self, mock_api):
        self.exchange._account_balances["OLD_TOKEN"] = Decimal("50")
        self.exchange._account_available_balances["OLD_TOKEN"] = Decimal("40")

        url = self.balance_url
        response = [
            {
                "type": "exchange",
                "currency": "SOL",
                "amount": "110.5",
                "available": "100.5",
                "availableForWithdrawal": "100.5",
            }
        ]

        mock_api.post(url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn("OLD_TOKEN", available_balances)
        self.assertNotIn("OLD_TOKEN", total_balances)
        self.assertEqual(Decimal("100.5"), available_balances["SOL"])
        self.assertEqual(Decimal("110.5"), total_balances["SOL"])

    def test_gemini_order_type_limit(self):
        self.assertEqual("exchange limit", GeminiExchange.gemini_order_type(OrderType.LIMIT))

    def test_gemini_order_type_limit_maker(self):
        self.assertEqual("exchange limit", GeminiExchange.gemini_order_type(OrderType.LIMIT_MAKER))

    def test_gemini_order_type_market(self):
        self.assertEqual("exchange market", GeminiExchange.gemini_order_type(OrderType.MARKET))
