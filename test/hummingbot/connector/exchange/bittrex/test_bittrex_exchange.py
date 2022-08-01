import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple, Union
from unittest.mock import patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bittrex import bittrex_constants as CONSTANTS, bittrex_web_utils as web_utils
from hummingbot.connector.exchange.bittrex.bittrex_exchange import BittrexExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class BittrexExchangeTest(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.secret_key = "someSecret"

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        exchange_symbol = f"{self.base_asset}{self.quote_asset}"
        url = web_utils.public_rest_url(path_url=CONSTANTS.SYMBOL_TICKER_PATH.format(exchange_symbol))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SERVER_TIME_URL)
        return url

    @property
    def trading_rules_url(self):
        return self.all_symbols_url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_CREATION_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BALANCES_URL)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return [
            {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "baseCurrencySymbol": self.base_asset,
                "quoteCurrencySymbol": self.quote_asset,
                "minTradeSize": "number (double)",
                "precision": "integer (int32)",
                "status": "ONLINE",
                "createdAt": "string (date-time)",
                "notice": "string",
                "prohibitedIn": [
                    "string"
                ],
                "associatedTermsOfService": [
                    "string"
                ],
                "tags": [
                    "string"
                ]
            }
        ]

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = [
            {
                "symbol": "string",
                "baseCurrencySymbol": "string",
                "quoteCurrencySymbol": "string",
                "minTradeSize": "number (double)",
                "precision": "integer (int32)",
                "status": "string",
                "createdAt": "string (date-time)",
                "notice": "string",
                "prohibitedIn": [
                    "string"
                ],
                "associatedTermsOfService": [
                    "string"
                ],
                "tags": [
                    "string"
                ]
            }
        ]
        return "INVALID-PAIR", response

    @property
    def latest_prices_request_mock_response(self):
        return {
            "symbol": "string",
            "lastTradeRate": 45.0,
            "bidRate": "number (double)",
            "askRate": "number (double)"
        }

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "serverTime": "integer (int64)"
        }

    @property
    def trading_rules_request_mock_response(self):
        response = [
            {
                "symbol": "COINALPHAHBOT",
                "baseCurrencySymbol": "COINALPHA",
                "quoteCurrencySymbol": "HBOT",
                "minTradeSize": 20,
                "precision": 2,
                "status": "ONLINE",
                "createdAt": "string (date-time)",
                "notice": "string",
                "prohibitedIn": [
                    "string"
                ],
                "associatedTermsOfService": [
                    "string"
                ],
                "tags": [
                    "string"
                ]
            }
        ]
        return response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        response = [
            {
                "symbol": "string",
                "baseCurrencySymbol": "string",
                "quoteCurrencySymbol": "string",
                "minTradeSize": "number (double)",
                "precision": "integer (int32)",
                "status": "string",
                "createdAt": "string (date-time)",
                "notice": "string",
                "prohibitedIn": [
                    "string"
                ],
                "associatedTermsOfService": [
                    "string"
                ],
                "tags": [
                    "string"
                ]
            }
        ]
        return response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [
            {
                "currencySymbol": "COINALPHA",
                "total": 15.0,
                "available": 10.0,
                "updatedAt": "string (date-time)"
            },
            {
                "currencySymbol": "HBOT",
                "total": 2000.0,
                "available": 2000.0,
                "updatedAt": "string (date-time)"
            }
        ]

    @property
    def balance_request_mock_response_only_base(self):
        return [
            {
                "currencySymbol": "COINALPHA",
                "total": 15.0,
                "available": 10.0,
                "updatedAt": "string (date-time)"
            }
        ]

    @property
    def balance_event_websocket_update(self):
        return {
            "accountId": "string (uuid)",
            "sequence": "int",
            "delta": {
                "currencySymbol": "COINALPHA",
                "total": 15.0,
                "available": 10.0,
                "updatedAt": "string (date-time)"
            }
        }

    @property
    def expected_latest_price(self):
        return 45.0

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        precision = self.trading_rules_request_mock_response[0]["precision"]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(self.trading_rules_request_mock_response[0]["minTradeSize"]),
            min_price_increment=Decimal(precision),
            min_base_amount_increment=Decimal(precision),
            min_notional_size=Decimal(precision)
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "EOID1"

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10000)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("17")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("63"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return "TrID1"

    @property
    def is_cancel_request_executed_synchronously_by_server(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return True

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return BittrexExchange(
            client_config_map=client_config_map,
            bittrex_api_key=self.api_key,
            bittrex_secret_key=self.secret_key,
            trading_pairs=[self.trading_pair]
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("Api-Key", request_headers)
        self.assertEqual(self.api_key, request_headers["Api-Key"])
        self.assertIn("Api-Timestamp", request_headers)
        self.assertIn("Api-Content-Hash", request_headers)
        self.assertIn("Api-Signature", request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["marketSymbol"])
        self.assertEqual(order.trade_type.name, request_data["direction"])
        self.assertEqual(order.order_type.name, request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["limit"]))
        self.assertEqual(order.client_order_id, request_data["clientOrderId"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_data["id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(None, request_params)

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {
            "limit": "number (double)",
            "ceiling": "number (double)",
            "timeInForce": "string",
            "clientOrderId": "string (uuid)",
            "fillQuantity": "number (double)",
            "commission": "number (double)",
            "proceeds": "number (double)",
        }
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """
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
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=404, callback=callback)
        return regex_url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ALL_TRADES_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._trade_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ALL_TRADES_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._trade_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ALL_TRADES_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400, callback=callback)
        return regex_url

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "id": "EOID1",
            "marketSymbol": "string",
            "direction": "string",
            "type": "string",
            "quantity": "number (double)",
            "limit": "number (double)",
            "ceiling": "number (double)",
            "timeInForce": "string",
            "clientOrderId": "string (uuid)",
            "fillQuantity": "number (double)",
            "commission": "number (double)",
            "proceeds": "number (double)",
            "status": "string",
            "createdAt": '2018-06-29 08:15:27.243860',
            "updatedAt": "string (date-time)",
            "closedAt": "string (date-time)",
            "orderToCancel": {
                "type": "string",
                "id": "string (uuid)"
            }
        }

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "accountId": "string (uuid)",
            "sequence": "int",
            "delta": {
                "id": "string (uuid)",
                "marketSymbol": "COINALPHAHBOT",
                "direction": "string",
                "type": "string",
                "quantity": 20.0,
                "limit": "number (double)",
                "ceiling": "number (double)",
                "timeInForce": "string",
                "clientOrderId": "OID1",
                "fillQuantity": 0.0,
                "commission": "number (double)",
                "proceeds": "number (double)",
                "status": "OPEN",
                "createdAt": "string (date-time)",
                "updatedAt": "2018-06-29 08:15:27.243860",
                "closedAt": "string (date-time)",
                "orderToCancel": {
                    "type": "string",
                    "id": "string (uuid)"
                }
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "accountId": "string (uuid)",
            "sequence": "int",
            "delta": {
                "id": "string (uuid)",
                "marketSymbol": "COINALPHAHBOT",
                "direction": "string",
                "type": "string",
                "quantity": 20.0,
                "limit": "number (double)",
                "ceiling": "number (double)",
                "timeInForce": "string",
                "clientOrderId": "OID1",
                "fillQuantity": 12.0,
                "commission": "number (double)",
                "proceeds": "number (double)",
                "status": "CLOSED",
                "createdAt": "string (date-time)",
                "updatedAt": "2018-06-29 08:15:27.243860",
                "closedAt": "string (date-time)",
                "orderToCancel": {
                    "type": "string",
                    "id": "string (uuid)"
                }
            }
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "accountId": "string (uuid)",
            "sequence": "int",
            "delta": {
                "id": "EOID1",
                "marketSymbol": "COINALPHAHBOT",
                "direction": "BUY",
                "type": "LIMIT",
                "quantity": 1.0,
                "limit": 10000.0,
                "ceiling": "number (double)",
                "timeInForce": "string",
                "clientOrderId": "OID1",
                "fillQuantity": 1.0,
                "commission": "number (double)",
                "proceeds": "number (double)",
                "status": "CLOSED",
                "createdAt": "string (date-time)",
                "updatedAt": "2018-06-29 08:15:27.243860",
                "closedAt": "string (date-time)",
                "orderToCancel": {
                    "type": "string",
                    "id": "string (uuid)"
                }
            }
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "accountId": "string (uuid)",
            "sequence": "int",
            "deltas": [
                {
                    "id": "string (uuid)",
                    "marketSymbol": "COINALPHAHBOT",
                    "executedAt": "2018-06-29 08:15:27.243860",
                    "quantity": 1.0,
                    "rate": 10000.0,
                    "orderId": "EOID1",
                    "commission": 63.0,
                    "isTaker": True
                }
            ]
        }

    @patch("hummingbot.connector.utils.get_tracking_nonce_low_res")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 9
        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix="",
            max_id_len=40,
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
            hbot_order_id_prefix="",
            max_id_len=40,
        )

        self.assertEqual(result, expected_client_order_id)

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": "string (uuid)",
            "marketSymbol": "string",
            "direction": "string",
            "type": "string",
            "quantity": 20.0,
            "limit": "number (double)",
            "ceiling": "number (double)",
            "timeInForce": "string",
            "clientOrderId": "string (uuid)",
            "fillQuantity": 11.0,
            "commission": "number (double)",
            "proceeds": "number (double)",
            "status": "CLOSED",
            "createdAt": "string (date-time)",
            "updatedAt": "string (date-time)",
            "closedAt": "string (date-time)",
            "orderToCancel": {
                "type": "string",
                "id": "string (uuid)"
            }
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": "4",
            "marketSymbol": "COINALPHAHBOT",
            "direction": "BUY",
            "type": "LIMIT",
            "quantity": 10.0,
            "limit": "number (double)",
            "ceiling": "number (double)",
            "timeInForce": "string",
            "clientOrderId": "string (uuid)",
            "fillQuantity": 10.0,
            "commission": "number (double)",
            "proceeds": "number (double)",
            "status": "CLOSED",
            "createdAt": "string (date-time)",
            "updatedAt": "2018-06-29 08:15:27.243860",
            "closedAt": "string (date-time)",
            "orderToCancel": {
                "type": "string",
                "id": "string (uuid)"
            }
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": "string (uuid)",
            "marketSymbol": "COINALPHAHBOT",
            "direction": "string",
            "type": "string",
            "quantity": 20.0,
            "limit": "number (double)",
            "ceiling": "number (double)",
            "timeInForce": "string",
            "clientOrderId": "string (uuid)",
            "fillQuantity": 11.0,
            "commission": "number (double)",
            "proceeds": "number (double)",
            "status": "CLOSED",
            "createdAt": "string (date-time)",
            "updatedAt": "2018-06-29 08:15:27.243860",
            "closedAt": "string (date-time)",
            "orderToCancel": {
                "type": "string",
                "id": "string (uuid)"
            }
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": "4",
            "marketSymbol": "COINALPHAHBOT",
            "direction": "string",
            "type": "string",
            "quantity": "number (double)",
            "limit": "number (double)",
            "ceiling": "number (double)",
            "timeInForce": "string",
            "clientOrderId": "string (uuid)",
            "fillQuantity": "number (double)",
            "commission": "number (double)",
            "proceeds": "number (double)",
            "status": "OPEN",
            "createdAt": "string (date-time)",
            "updatedAt": "2018-06-29 08:15:27.243860",
            "closedAt": "string (date-time)",
            "orderToCancel": {
                "type": "string",
                "id": "string (uuid)"
            }
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "id": "4",
            "marketSymbol": "COINALPHAHBOT",
            "direction": "string",
            "type": "string",
            "quantity": 20.0,
            "limit": "number (double)",
            "ceiling": "number (double)",
            "timeInForce": "string",
            "clientOrderId": "string (uuid)",
            "fillQuantity": 17.0,
            "commission": "number (double)",
            "proceeds": "number (double)",
            "status": "OPEN",
            "createdAt": "string (date-time)",
            "updatedAt": "2018-06-29 08:15:27.243860",
            "closedAt": "string (date-time)",
            "orderToCancel": {
                "type": "string",
                "id": "string (uuid)"
            }
        }

    def _all_executed_requests(self, api_mock: aioresponses, url: Union[str, re.Pattern]) -> List[RequestCall]:
        request_calls = []
        if isinstance(url, str):
            url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        for key, value in api_mock.requests.items():
            if url.search(key[1].human_repr()):
                request_calls.extend(value)
        return request_calls

    def _trade_fills_request_full_fill_mock_response(self, order):
        return [
            {
                "id": "EOID1",
                "marketSymbol": "COINALPHAHBOT",
                "executedAt": "2018-06-29 08:15:27.243860",
                "quantity": 1.0,
                "rate": 10000.0,
                "orderId": str(order.exchange_order_id),
                "commission": 63.0,
                "isTaker": "boolean"
            }
        ]

    def _trade_fills_request_partial_fill_mock_response(self, order):
        return [
            {
                "id": "EOID1",
                "marketSymbol": "COINALPHAHBOT",
                "executedAt": "2018-06-29 08:15:27.243860",
                "quantity": 17.0,
                "rate": 10000.0,
                "orderId": str(order.exchange_order_id),
                "commission": 63.0,
                "isTaker": "boolean"
            }
        ]
