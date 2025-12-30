import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.exchange.backpack.backpack_constants as CONSTANTS
import hummingbot.connector.exchange.backpack.backpack_web_utils as web_utils
from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase


class BackpackExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    """Test suite for Backpack Exchange connector."""

    _logger = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Mock ED25519 keys (base64 encoded)
        cls.api_key = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY="  # noqa: mock
        cls.api_secret = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVmMDEyMzQ1Njc4OWFiY2RlZg=="  # noqa: mock
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)
        cls.exchange_symbol = f"{cls.base_asset}_{cls.quote_asset}"

    @property
    def all_symbols_url(self):
        url = web_utils.rest_url(CONSTANTS.MARKETS_URL, self.exchange.domain)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.rest_url(CONSTANTS.TICKER_URL, self.exchange.domain)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.rest_url(CONSTANTS.STATUS_URL, self.exchange.domain)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.rest_url(CONSTANTS.MARKETS_URL, self.exchange.domain)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def order_creation_url(self):
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.rest_url(CONSTANTS.CAPITAL_URL, self.exchange.domain)
        return url

    @property
    def all_symbols_request_mock_response(self) -> List[Dict[str, Any]]:
        return [
            {
                "symbol": "BTC_USDC",
                "baseSymbol": "BTC",
                "quoteSymbol": "USDC",
                "minOrderSize": "0.0001",
                "tickSize": "0.01",
                "stepSize": "0.0001",
                "minNotional": "1",
            },
        ]

    @property
    def latest_prices_request_mock_response(self) -> Dict[str, Any]:
        return {
            "symbol": self.exchange_symbol,
            "lastPrice": str(self.expected_latest_price),
            "priceChange": "-100.50",
            "priceChangePercent": "-1.5",
            "high": "45000.00",
            "low": "42000.00",
            "volume": "1234.5678",
            "quoteVolume": "52500000.00",
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        mock_response = [
            {
                "symbol": "BTC_USDC",
                "baseSymbol": "BTC",
                "quoteSymbol": "USDC",
                "minOrderSize": "0.0001",
                "tickSize": "0.01",
                "stepSize": "0.0001",
                "minNotional": "1",
            },
            {
                "symbol": "INVALID_PAIR",
                "baseSymbol": "",
                "quoteSymbol": "",
            },
        ]
        return "INVALID-PAIR", mock_response

    @property
    def network_status_request_successful_mock_response(self) -> Dict[str, Any]:
        return {"status": "ok"}

    @property
    def trading_rules_request_mock_response(self) -> List[Dict[str, Any]]:
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self) -> List[Dict[str, Any]]:
        return [
            {
                "symbol": "BTC_USDC",
                # Missing required fields
            }
        ]

    @property
    def order_creation_request_successful_mock_response(self) -> Dict[str, Any]:
        return {
            "id": self.expected_exchange_order_id,
            "orderId": self.expected_exchange_order_id,
            "clientId": 12345,
            "symbol": self.exchange_symbol,
            "side": "Bid",
            "orderType": "Limit",
            "price": "10000.00",
            "quantity": "1.0",
            "status": "New",
            "createdAt": 1234567890000,
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self) -> Dict[str, Any]:
        return {
            self.base_asset: {
                "available": "10.0",
                "locked": "5.0",
            },
            self.quote_asset: {
                "available": "50000.0",
                "locked": "10000.0",
            },
        }

    @property
    def balance_request_mock_response_only_base(self) -> Dict[str, Any]:
        return {
            self.base_asset: {
                "available": "10.0",
                "locked": "5.0",
            },
        }

    @property
    def balance_event_websocket_update(self):
        # Backpack does not provide balance updates through websocket
        self.fail()

    @property
    def expected_latest_price(self) -> float:
        return 43000.50

    @property
    def expected_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self) -> TradingRule:
        market = self.trading_rules_request_mock_response[0]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(str(market["minOrderSize"])),
            min_price_increment=Decimal(str(market["tickSize"])),
            min_base_amount_increment=Decimal(str(market["stepSize"])),
            min_notional_size=Decimal(str(market["minNotional"])),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self) -> str:
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing trading rule for {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self) -> str:
        return "12345678"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("42000.00")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("21.0"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "trade_123456"

    @property
    def latest_trade_hist_timestamp(self) -> int:
        return 1234567890

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(coroutine, timeout)
        )
        return ret

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        exchange = BackpackExchange(
            backpack_api_key=self.api_key,
            backpack_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
            trading_required=True,
        )
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        expected_headers = ["X-API-Key", "X-Signature", "X-Timestamp", "X-Window"]
        self.assertEqual(self.api_key, request_headers["X-API-Key"])
        for header in expected_headers:
            self.assertIn(header, request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.amount, abs(Decimal(str(request_data["quantity"]))))
        self.assertEqual(int(order.client_order_id), request_data["clientId"])
        expected_side = "Bid" if order.trade_type is TradeType.BUY else "Ask"
        self.assertEqual(expected_side, request_data["side"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs.get("params", {})
        # Check that either clientId or orderId is in params
        self.assertTrue(
            "clientId" in request_params or "orderId" in request_params,
            "Cancel request should include clientId or orderId"
        )

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs.get("params", {})
        self.assertIn("symbol", request_params)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs.get("params", {})
        self.assertIn("symbol", request_params)

    def configure_successful_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"error": "Order not found"}
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses,
    ) -> List[str]:
        urls = []
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        # First call succeeds
        response_success = self._order_cancelation_request_successful_mock_response(
            order=successful_order
        )
        mock_api.delete(regex_url, body=json.dumps(response_success))
        urls.append(url)

        # Second call fails
        response_fail = {"error": "Order not found"}
        mock_api.delete(regex_url, body=json.dumps(response_fail))
        urls.append(url)

        return urls

    def configure_order_not_found_error_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"error": CONSTANTS.UNKNOWN_ORDER_MESSAGE}
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"error": CONSTANTS.ORDER_NOT_EXIST_MESSAGE}
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_completely_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.FILLS_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"error": "Invalid request"}
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.FILLS_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.FILLS_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def _configure_balance_response(
        self,
        response: Dict[str, Any],
        mock_api: aioresponses,
        callback: Optional[Callable] = None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.CAPITAL_URL, self.exchange.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "id": order.exchange_order_id or self.expected_exchange_order_id,
            "clientId": int(order.client_order_id),
            "symbol": self.exchange_symbol,
            "status": "Cancelled",
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "id": order.exchange_order_id or self.expected_exchange_order_id,
            "clientId": int(order.client_order_id),
            "symbol": self.exchange_symbol,
            "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "orderType": "Limit",
            "price": str(order.price),
            "quantity": str(order.amount),
            "executedQuantity": str(order.amount),
            "status": "Filled",
            "createdAt": 1234567890000,
            "updatedAt": 1234567891000,
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "id": order.exchange_order_id or self.expected_exchange_order_id,
            "clientId": int(order.client_order_id),
            "symbol": self.exchange_symbol,
            "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "orderType": "Limit",
            "price": str(order.price),
            "quantity": str(order.amount),
            "executedQuantity": "0",
            "status": "Cancelled",
            "createdAt": 1234567890000,
            "updatedAt": 1234567891000,
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "id": order.exchange_order_id or self.expected_exchange_order_id,
            "clientId": int(order.client_order_id),
            "symbol": self.exchange_symbol,
            "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "orderType": "Limit",
            "price": str(order.price),
            "quantity": str(order.amount),
            "executedQuantity": "0",
            "status": "New",
            "createdAt": 1234567890000,
            "updatedAt": 1234567890000,
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "id": order.exchange_order_id or self.expected_exchange_order_id,
            "clientId": int(order.client_order_id),
            "symbol": self.exchange_symbol,
            "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "orderType": "Limit",
            "price": str(order.price),
            "quantity": str(order.amount),
            "executedQuantity": str(self.expected_partial_fill_amount),
            "status": "PartiallyFilled",
            "createdAt": 1234567890000,
            "updatedAt": 1234567891000,
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder) -> List[Dict[str, Any]]:
        return [
            {
                "tradeId": self.expected_fill_trade_id,
                "orderId": order.exchange_order_id or self.expected_exchange_order_id,
                "symbol": self.exchange_symbol,
                "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
                "price": str(order.price),
                "quantity": str(order.amount),
                "fee": "21.0",
                "feeSymbol": self.quote_asset,
                "timestamp": 1234567891000,
                "isMaker": True,
            }
        ]

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder) -> List[Dict[str, Any]]:
        return [
            {
                "tradeId": self.expected_fill_trade_id,
                "orderId": order.exchange_order_id or self.expected_exchange_order_id,
                "symbol": self.exchange_symbol,
                "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
                "price": str(self.expected_partial_fill_price),
                "quantity": str(self.expected_partial_fill_amount),
                "fee": "21.0",
                "feeSymbol": self.quote_asset,
                "timestamp": 1234567891000,
                "isMaker": True,
            }
        ]

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "stream": "account.orderUpdate",
            "data": {
                "e": "orderAccepted",
                "i": order.exchange_order_id or self.expected_exchange_order_id,
                "c": int(order.client_order_id),
                "s": self.exchange_symbol,
                "S": "Bid" if order.trade_type == TradeType.BUY else "Ask",
                "o": "Limit",
                "p": str(order.price),
                "q": str(order.amount),
                "z": "0",
                "X": "New",
                "T": 1234567890000000,
            },
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "stream": "account.orderUpdate",
            "data": {
                "e": "orderCancelled",
                "i": order.exchange_order_id or self.expected_exchange_order_id,
                "c": int(order.client_order_id),
                "s": self.exchange_symbol,
                "S": "Bid" if order.trade_type == TradeType.BUY else "Ask",
                "o": "Limit",
                "p": str(order.price),
                "q": str(order.amount),
                "z": "0",
                "X": "Cancelled",
                "T": 1234567891000000,
            },
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return {
            "stream": "account.orderUpdate",
            "data": {
                "e": "orderFill",
                "t": self.expected_fill_trade_id,
                "i": order.exchange_order_id or self.expected_exchange_order_id,
                "c": int(order.client_order_id),
                "s": self.exchange_symbol,
                "S": "Bid" if order.trade_type == TradeType.BUY else "Ask",
                "o": "Limit",
                "p": str(order.price),
                "q": str(order.amount),
                "l": str(order.amount),
                "L": str(order.price),
                "n": "21.0",
                "N": self.quote_asset,
                "m": True,
                "X": "Filled",
                "T": 1234567891000000,
            },
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return None

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("50000.0"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("60000.0"), total_balances[self.quote_asset])
        self.assertEqual(Decimal("10.0"), available_balances[self.base_asset])
        self.assertEqual(Decimal("15.0"), total_balances[self.base_asset])

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        url = self.trading_rules_url
        mock_api.get(url, body=json.dumps(self.trading_rules_request_mock_response))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        trading_rule = self.exchange.trading_rules[self.trading_pair]
        self.assertEqual(Decimal("0.0001"), trading_rule.min_order_size)
        self.assertEqual(Decimal("0.01"), trading_rule.min_price_increment)
        self.assertEqual(Decimal("0.0001"), trading_rule.min_base_amount_increment)

    def is_cancel_request_executed_synchronously_by_server(self) -> bool:
        return True

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = self.network_status_url
        mock_api.get(url, body=json.dumps(self.network_status_request_successful_mock_response))

        result = self.async_run_with_timeout(self.exchange.check_network())

        from hummingbot.core.network_iterator import NetworkStatus
        self.assertEqual(NetworkStatus.CONNECTED, result)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        url = self.network_status_url
        mock_api.get(url, status=500)

        result = self.async_run_with_timeout(self.exchange.check_network())

        from hummingbot.core.network_iterator import NetworkStatus
        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertEqual(self.expected_supported_order_types, supported_types)

    def test_client_order_id_max_length(self):
        self.assertEqual(CONSTANTS.MAX_ORDER_ID_LEN, self.exchange.client_order_id_max_length)

    def test_name(self):
        self.assertEqual(CONSTANTS.DOMAIN, self.exchange.name)
