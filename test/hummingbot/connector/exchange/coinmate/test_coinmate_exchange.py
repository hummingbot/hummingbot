import asyncio
import json
import re
from decimal import Decimal
from urllib.parse import parse_qs
from typing import Any, Callable, List, Optional, Tuple, Dict
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.exchange.coinmate import (
    coinmate_constants as CONSTANTS,
    coinmate_web_utils as web_utils
)
from hummingbot.connector.exchange.coinmate.coinmate_exchange import CoinmateExchange
from hummingbot.connector.test_support.exchange_connector_test import (
    AbstractExchangeConnectorTests
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import (
    DeductedFromReturnsTradeFee,
    TokenAmount,
    TradeFeeBase,
)
from hummingbot.core.event.events import OrderFilledEvent


class CoinmateExchangeTests(
    AbstractExchangeConnectorTests.ExchangeConnectorTests
):

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(
            path_url=CONSTANTS.TRADING_PAIRS_PATH_URL, domain=self.exchange._domain
        )

    @property
    def balance_event_websocket_update(self):
        return {
            "event": "data",
            "channel": "private-user_balances-test_client_id",
            "payload": {
                "balances": {
                    self.base_asset: {
                        "currency": self.base_asset,
                        "balance": "15",
                        "reserved": "5",
                        "available": "10"
                    }
                }
            }
        }

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        pair_name = erroneous_rule.get("name", "")
        return f"Error parsing trading rules for {pair_name}: invalid literal for int() with base 10: 'invalid'"

    @property
    def latest_prices_url(self):
        return web_utils.public_rest_url(
            path_url=CONSTANTS.TICKER_PATH_URL, domain=self.exchange._domain
        )

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(
            CONSTANTS.SERVER_TIME_PATH_URL, domain=self.exchange._domain
        )

    @property
    def trading_rules_url(self):
        return web_utils.public_rest_url(
            CONSTANTS.TRADING_PAIRS_PATH_URL, domain=self.exchange._domain
        )

    @property
    def order_creation_url(self):
        return web_utils.private_rest_url(
            CONSTANTS.BUY_LIMIT_PATH_URL, domain=self.exchange._domain
        )

    @property
    def balance_url(self):
        return web_utils.private_rest_url(
            CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain
        )

    @property
    def all_symbols_request_mock_response(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": [
                {
                    "name": f"{self.base_asset}_{self.quote_asset}",
                    "firstCurrency": self.base_asset,
                    "secondCurrency": self.quote_asset,
                    "priceDecimals": 2,
                    "lotDecimals": 8,
                    "minAmount": 0.001
                }
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                "last": str(self.expected_latest_price),
                "high": "55000.00",
                "low": "49000.00",
                "amount": "123.45",
                "bid": "49900.00",
                "ask": "50100.00",
                "change": "2.5",
                "open": "49000.00",
                "timestamp": 1234567890123
            }
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "error": False,
            "errorMessage": None,
            "data": [
                {
                    "name": f"{self.base_asset}_{self.quote_asset}",
                    "firstCurrency": self.base_asset,
                    "secondCurrency": self.quote_asset,
                    "priceDecimals": 2,
                    "lotDecimals": 8,
                    "minAmount": 0.001
                },
                {
                    "name": "INVALID_PAIR"
                }
            ]
        }
        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {"serverTime": 1234567890123}

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": [
                {
                    "name": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "firstCurrency": self.base_asset,
                    "secondCurrency": self.quote_asset,
                    "priceDecimals": "invalid",  # This will cause int() to fail
                    "minAmount": "0.001",
                    "lotDecimals": 8
                }
            ]
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": int(self.expected_exchange_order_id)
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                self.base_asset: {
                    "currency": self.base_asset,
                    "balance": "15.0",
                    "reserved": "5.0",
                    "available": "10.0"
                },
                self.quote_asset: {
                    "currency": self.quote_asset,
                    "balance": "2000.0",
                    "reserved": "0.0",
                    "available": "2000.0"
                }
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                self.base_asset: {
                    "currency": self.base_asset,
                    "balance": "15.0",
                    "reserved": "5.0",
                    "available": "10.0"
                }
            }
        }

    @property
    def expected_latest_price(self):
        return 50000.0

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("1e-8"),
        )

    @property
    def expected_exchange_order_id(self):
        return "12345"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("50000")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("75"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "67890"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        return CoinmateExchange(
            coinmate_api_key="test_api_key",
            coinmate_secret_key="test_secret_key",
            coinmate_client_id="test_client_id",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_data_str = request_call.kwargs.get("data") or request_call.kwargs.get("params") or ""
        request_data = parse_qs(request_data_str)
        self.assertIn("clientId", request_data)
        self.assertIn("nonce", request_data)
        self.assertIn("signature", request_data)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data_str = request_call.kwargs["data"]
        request_data = parse_qs(request_data_str)
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["currencyPair"][0])
        self.assertAlmostEqual(float(order.amount), float(request_data["amount"][0]), places=6)
        self.assertAlmostEqual(float(order.price), float(request_data["price"][0]), places=4)

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data_str = request_call.kwargs["data"]
        request_data = parse_qs(request_data_str)
        self.assertEqual(order.exchange_order_id, request_data["orderId"][0])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data_str = request_call.kwargs["data"]
        request_data = parse_qs(request_data_str)
        self.assertEqual(order.exchange_order_id, request_data["orderId"][0])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data_str = request_call.kwargs["data"]
        request_data = parse_qs(request_data_str)
        self.assertEqual(order.exchange_order_id, request_data["orderId"][0])

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
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"error": True, "errorMessage": "Order does not exist", "data": None}
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
        url = web_utils.private_rest_url(CONSTANTS.ORDER_BY_ID_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_BY_ID_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.TRADE_HISTORY_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_BY_ID_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_BY_ID_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_BY_ID_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_BY_ID_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"error": True, "errorMessage": "Order does not exist", "data": None}
        mock_api.post(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.TRADE_HISTORY_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.TRADE_HISTORY_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "event": "data",
            "channel": f"private-open_orders-test_client_id-{self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}",
            "payload": {
                "id": order.exchange_order_id,
                "type": order.trade_type.name,
                "amount": str(order.amount),
                "price": str(order.price),
                "original": str(order.amount),
                "currencyPair": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "date": 1234567890123,
                "orderChangePushEvent": "CREATION",
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "event": "data",
            "channel": f"private-open_orders-test_client_id-{self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}",
            "payload": {
                "id": order.exchange_order_id,
                "type": order.trade_type.name,
                "amount": str(order.amount),  # Remaining amount (not filled)
                "price": str(order.price),
                "original": str(order.amount),
                "currencyPair": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "date": 1234567890123,
                "orderChangePushEvent": "REMOVAL",
            }
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "event": "data",
            "channel": f"private-open_orders-test_client_id-{self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}",
            "payload": {
                "id": order.exchange_order_id,
                "type": order.trade_type.name,
                "amount": "0",
                "price": str(order.price),
                "original": str(order.amount),
                "currencyPair": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "date": 1234567890123,
                "orderChangePushEvent": "REMOVAL",
            }
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "event": "data",
            "channel": f"private-user-trades-test_client_id-{self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}",
            "payload": {
                "transactionId": self.expected_fill_trade_id,
                "date": 1234567890123,
                "amount": str(order.amount),
                "price": str(order.price),
                "buyOrderId": order.exchange_order_id if order.trade_type == TradeType.BUY else "99999",
                "sellOrderId": order.exchange_order_id if order.trade_type == TradeType.SELL else "99999",
                "orderType": order.trade_type.name,
                "type": order.trade_type.name,
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "tradeFeeType": "TAKER",
                "currencyPair": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            }
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "error": False,
            "errorMessage": None,
            "data": True
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                "id": order.exchange_order_id,
                "timestamp": 1234567890123,
                "type": order.trade_type.name,
                "price": str(order.price),
                "remainingAmount": "0",
                "originalAmount": str(order.amount),
                "status": "FILLED",
                "orderTradeType": "LIMIT",
            }
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                "id": order.exchange_order_id,
                "timestamp": 1234567890123,
                "type": order.trade_type.name,
                "price": str(order.price),
                "remainingAmount": str(order.amount),
                "originalAmount": str(order.amount),
                "status": "CANCELLED",
                "orderTradeType": "LIMIT",
            }
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                "id": order.exchange_order_id,
                "timestamp": 1234567890123,
                "type": order.trade_type.name,
                "price": str(order.price),
                "remainingAmount": str(order.amount),
                "originalAmount": str(order.amount),
                "status": "OPEN",
                "orderTradeType": "LIMIT",
            }
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "error": False,
            "errorMessage": None,
            "data": {
                "id": order.exchange_order_id,
                "timestamp": 1234567890123,
                "type": order.trade_type.name,
                "price": str(order.price),
                "remainingAmount": str(order.amount - self.expected_partial_fill_amount),
                "originalAmount": str(order.amount),
                "status": "PARTIALLY_FILLED",
                "orderTradeType": "LIMIT",
            }
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "error": False,
            "errorMessage": None,
            "data": [
                {
                    "transactionId": self.expected_fill_trade_id,
                    "createdTimestamp": 1234567890123,
                    "currencyPair": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "type": order.trade_type.name,
                    "orderType": "LIMIT",
                    "orderId": order.exchange_order_id,
                    "amount": str(self.expected_partial_fill_amount),
                    "price": str(self.expected_partial_fill_price),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "feeType": "TAKER"
                }
            ]
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "error": False,
            "errorMessage": None,
            "data": [
                {
                    "transactionId": self.expected_fill_trade_id,
                    "createdTimestamp": 1234567890123,
                    "currencyPair": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "type": order.trade_type.name,
                    "orderType": "LIMIT",
                    "orderId": order.exchange_order_id,
                    "amount": str(order.amount),
                    "price": str(order.price),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "feeType": "TAKER"
                }
            ]
        }

    def _configure_balance_response(
            self,
            response: Dict[str, Any],
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = self.balance_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    @aioresponses()
    async def test_get_last_trade_prices(self, mock_api):
        url = self.latest_prices_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + r".*")
        response = self.latest_prices_request_mock_response
        
        mock_api.get(regex_url, body=json.dumps(response))
        
        latest_prices = await self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        
        self.assertEqual(1, len(latest_prices))
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = web_utils.private_rest_url(CONSTANTS.BUY_LIMIT_PATH_URL, domain=self.exchange._domain)
        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        self.assertEqual(str(self.expected_exchange_order_id), 
                        self.exchange.in_flight_orders[order_id].exchange_order_id)

    @aioresponses()
    def test_create_sell_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = web_utils.private_rest_url(CONSTANTS.SELL_LIMIT_PATH_URL, domain=self.exchange._domain)
        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_sell_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        self.assertEqual(str(self.expected_exchange_order_id), 
                        self.exchange.in_flight_orders[order_id].exchange_order_id)

    @aioresponses()
    def test_update_order_fills_from_trades_triggers_filled_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("50000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "transactionId": "28457",
            "createdTimestamp": 1234567890123,
            "currencyPair": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "type": "BUY",
            "orderType": "LIMIT",
            "orderId": order.exchange_order_id,
            "amount": "1",
            "price": "49990",
            "fee": "10.10",
            "feeType": "TAKER"
        }

        mock_response = {"error": False, "errorMessage": None, "data": [trade_fill]}
        mock_api.post(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill["amount"]), fill_event.amount)

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 7

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    def test_user_stream_update_for_order_failure(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("50000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        # Simulate order removal event (which could indicate failure/cancellation)
        event_message = self.order_event_for_canceled_order_websocket_update(order)

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        # Order should be removed from tracking
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
