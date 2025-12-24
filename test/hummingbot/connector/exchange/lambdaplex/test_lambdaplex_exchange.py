import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.exchange.lambdaplex import (
    lambdaplex_constants as CONSTANTS,
    lambdaplex_web_utils as web_utils,
)
from hummingbot.connector.exchange.lambdaplex.lambdaplex_exchange import LambdaplexExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import OrderCancelledEvent


class LambdaplexExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    exchange_order_id_prefix = "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208f"  # noqa: mock

    @property
    def exchange_trading_pair(self) -> str:
        return self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.LAST_PRICE_URL)
        url = f"{url}?symbol={self.exchange_trading_pair}"
        return url

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.SERVER_AVAILABILITY_URL)

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        return url

    @property
    def user_fee_url(self):
        url = web_utils.private_rest_url(CONSTANTS.USER_FEES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def balance_url(self):
        return web_utils.private_rest_url(path_url=CONSTANTS.ACCOUNTS_PATH_URL)

    @property
    def all_symbols_request_mock_response(self):
        response = self._exchange_rules_mock_response()
        return response

    @property
    def latest_prices_request_mock_response(self):
        response = {
            "symbol": self.exchange_trading_pair,
            "price": str(self.expected_latest_price),
        }
        return response

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = self._exchange_rules_mock_response()
        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        response = ""
        return response

    @property
    def trading_rules_request_mock_response(self):
        response = self._exchange_rules_mock_response()
        return response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        response = self._exchange_rules_mock_response()
        response["exchangeSymbols"][0]["filters"].pop(0)
        return response

    @property
    def order_creation_request_successful_mock_response(self):
        response = {
            "symbol": self.exchange_trading_pair,
            "orderId": self.expected_exchange_order_id,
            "clientOrderId": "myorder-001a",
            "transactTime": self.exchange.current_timestamp,
        }
        return response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        response = {
            "balances": [
                {
                    "asset": self.base_asset,
                    "free": "10.0",
                    "locked": "5.0"
                },
                {
                    "asset": self.quote_asset,
                    "free": "2000",
                    "locked": "0.00000000"
                },
            ],
        }
        return response

    @property
    def balance_request_mock_response_only_base(self):
        response = {
            "balances": [
                {
                    "asset": self.base_asset,
                    "free": "10.0",
                    "locked": "5.0"
                },
            ],
        }
        return response

    @property
    def balance_event_websocket_update(self):
        return {
            "e": "balanceChange",
            "E": 1564034571105,
            "u": 1564034571073,
            "B": [{"a": self.base_asset, "f": "10", "l": "5"}],
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        rule_filters = self.trading_rules_request_mock_response["exchangeSymbols"][0]["filters"]
        rule = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(rule_filters[1]["minQty"]),
            min_price_increment=Decimal(rule_filters[0]["tickSize"]),
            min_base_amount_increment=Decimal(rule_filters[1]["stepSize"]),
            min_notional_size=Decimal(rule_filters[2]["minNotional"]),
        )
        return rule

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["exchangeSymbols"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "26a911ff-f546-eaaf-4b22-e57657b57571"

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
        return DeductedFromReturnsTradeFee(
            flat_fees=[TokenAmount(token=self.base_asset, amount=Decimal("1"))],  # assuming BUY order
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return str(28458)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "testApiKey"
        cls.private_key = "MC4CAQAwBQYDK2VwBCIEIJETIXjnIFeh11KAJZVv45sLhH8gCrWbL902cBfzCHE3"  # noqa: invalidated

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    def create_exchange_instance(self):
        return LambdaplexExchange(
            lambdaplex_api_key=self.api_key,
            lambdaplex_private_key=self.private_key,
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        kwargs = request_call.kwargs
        self.assertEqual(self.api_key, kwargs["headers"]["X-API-KEY"])
        params = kwargs["params"]
        data = kwargs["data"]
        if params is not None:
            self.assertIsNone(data)
            self.assertEqual(CONSTANTS.RECEIVE_WINDOW, params["recvWindow"])
            self.assertIn("timestamp", params)
            self.assertIn("signature", params)
        else:
            self.assertIsNone(params)
            self.assertIn("recvWindow=5000", data)
            self.assertIn("timestamp=", data)
            self.assertIn("signature=", data)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        params = request_call.kwargs["params"]

        self.assertEqual(self.exchange_trading_pair, params["symbol"])
        self.assertEqual(order.amount, Decimal(params["quantity"]))
        self.assertEqual(order.client_order_id, params["newClientOrderId"])

        if order.order_type == OrderType.LIMIT:
            self.assertEqual("GTC", params["timeInForce"])
            self.assertEqual(order.price, Decimal(params["price"]))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        params = request_call.kwargs["params"]
        self.assertEqual(order.client_order_id, params["origClientOrderId"])
        self.assertEqual(self.exchange_trading_pair, params["symbol"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(
            self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            request_params["symbol"],
        )
        self.assertEqual(order.client_order_id, request_params["origClientOrderId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(
            self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            request_params["symbol"],
        )
        self.assertEqual(order.exchange_order_id, str(request_params["orderId"]))

    def configure_successful_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.delete(
            regex_url,
            status=404,
            callback=callback,
            body=json.dumps(
                {
                    "timestamp": "2025-11-17T05:42:03.001+00:00",
                    "path": "/api/v1/order",
                    "status": 400,
                    "error": "Bad Request",
                    "requestId": "9e0d5d0e-2442",
                    "message": "Invalid symbol"
                }
            ),
        )
        return url

    def configure_order_not_found_error_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.delete(
            regex_url,
            status=404,
            callback=callback,
            body=json.dumps(
                {
                    "timestamp": "2025-11-02T09:02:27.801+00:00",
                    "path": "/api/v1/order",
                    "status": 404,
                    "error": "Not Found",
                    "requestId": "b1667c87-3223",
                    "message": None,
                }
            ),
        )
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses,
    ) -> List[str]:
        all_urls = []
        url = self.configure_successful_cancelation_response(
            order=successful_order,
            mock_api=mock_api
        )
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(
            order=erroneous_order,
            mock_api=mock_api
        )
        all_urls.append(url)
        return all_urls

    def configure_completely_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Union[str, List[str]]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)  # unauthorized
        return url

    def configure_partially_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {
            "timestamp": "2025-11-17T05:31:34.168+00:00",
            "path": "/api/v1/order",
            "status": 404,
            "error": "Not Found",
            "requestId": "d6c6d48b-2431",
            "message": None
        }
        mock_api.get(regex_url, body=json.dumps(response), status=404, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        expected_fill_fee = self.expected_fill_fee
        return {
            "e": "orderUpdate",
            "E": 1499405658658,
            "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "c": order.client_order_id,
            "S": order.trade_type.name.upper(),
            "o": order.order_type.name.upper(),
            "f": "GTC",
            "q": str(order.amount),
            "p": str(order.price),
            "g": -1,
            "C": None,
            "x": "CREATE",
            "X": "OPEN",
            "r": None,
            "i": order.exchange_order_id,
            "l": "0.00000000",
            "z": "0.00000000",
            "L": "0.00000000",
            "n": str(expected_fill_fee.flat_fees[0].amount),
            "N": expected_fill_fee.flat_fees[0].token,
            "T": 1499405658657,
            "t": -1,
            "I": 8641984,
            "w": True,
            "m": False,
            "M": False,
            "O": 1499405658657,
            "Z": "0.00000000",
            "Y": "0.00000000",
            "W": 1499405658657,
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        response = {
            "e": "orderUpdate",
            "E": 1499405658658,
            "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "c": "dummyText",
            "S": order.trade_type.name.upper(),
            "o": order.order_type.name.upper(),
            "f": "GTC",
            "q": str(order.amount),
            "p": str(order.price),
            "P": "0.00000000",
            "F": "0.00000000",
            "g": -1,
            "C": order.client_order_id,
            "x": "CANCELED",
            "X": "CANCELED",
            "r": "NONE",
            "i": order.exchange_order_id,
            "l": "0.00000000",
            "z": "0.00000000",
            "L": "0.00000000",
            "n": "0",
            "N": None,
            "T": 1499405658657,
            "t": -1,
            "I": 8641984,
            "w": True,
            "m": False,
            "M": False,
            "O": 1499405658657,
            "Z": "0.00000000",
            "Y": "0.00000000",
            "Q": "0.00000000"
        }
        return response

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        update = {
            "e": "orderUpdate",
            "E": 1499405658658,
            "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "c": order.client_order_id,
            "S": order.trade_type.name.upper(),
            "o": order.order_type.name.upper(),
            "f": "GTC",
            "q": str(order.amount),
            "p": str(order.price),
            "P": "0.00000000",
            "F": "0.00000000",
            "g": -1,
            "C": "",
            "x": "TRADE",
            "X": "FILLED",
            "r": "NONE",
            "i": order.exchange_order_id,
            "l": str(order.amount),
            "z": str(order.amount),
            "L": str(order.price),
            "n": str(self.expected_fill_fee.flat_fees[0].amount),
            "N": self.expected_fill_fee.flat_fees[0].token,
            "T": 1499405658657,
            "t": 1,
            "I": 8641984,
            "w": True,
            "m": False,
            "M": False,
            "O": 1499405658657,
            "Z": "10050.00000000",
            "Y": "10050.00000000",
            "Q": "10000.00000000"
        }
        return update

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    def configure_user_fees_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = self.user_fee_url
        response = {
            "maker": "0.1",
            "taker": "0.5",
        }
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return [url]

    def get_expected_user_fee(self, is_maker: bool) -> TradeFeeBase:
        if is_maker:
            fee = DeductedFromReturnsTradeFee(
                percent_token=self.base_asset,
                percent=Decimal("0.1"),
            )
        else:
            fee = DeductedFromReturnsTradeFee(
                percent_token=self.base_asset,
                percent=Decimal("0.5"),
            )
        return fee

    def _exchange_rules_mock_response(self):
        response = {
            "exchangeSymbols": [
                {
                    "symbol": self.exchange_trading_pair,
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "baseAssetPrecision": 6,
                    "quoteAssetPrecision": 8,
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "0.01000000",
                            "maxPrice": "100000.00000000",
                            "tickSize": "0.01000000"
                        },
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.00001000",
                            "maxQty": "9000.00000000",
                            "stepSize": "0.00001000"
                        },
                        {
                            "filterType": "MIN_NOTIONAL",
                            "minNotional": "10.00",
                            "applyToMarket": True,
                            "avgPriceMins": 5
                        }
                    ]
                }
            ]
        }
        return response

    def _order_cancelation_request_successful_mock_response(
        self, order: InFlightOrder
    ) -> Dict[str, Any]:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "symbol": self.exchange_trading_pair,
            "origClientOrderId": order.client_order_id,
            "orderId": exchange_order_id,
            "clientOrderId": None,
            "transactTime": self.exchange.current_timestamp,
            "price": str(order.price) if order.price else None,
            "origQty": str(order.amount),
            "executedQty": "0",
            "cumulativeQuoteQty": "0",
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": order.order_type.name,
            "side": order.trade_type.name,
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "id": self.expected_fill_trade_id,
                "orderId": order.exchange_order_id,
                "price": str(self.expected_partial_fill_price),
                "qty": str(self.expected_partial_fill_amount),
                "quoteQty": str(self.expected_partial_fill_amount * self.expected_partial_fill_price),
                "commission": str(self.expected_fill_fee.flat_fees[0].amount),
                "commissionAsset": self.expected_fill_fee.flat_fees[0].token,
                "time": 1499865549590,
                "isBuyer": True,
                "isMaker": False,
            }
        ]

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "id": self.expected_fill_trade_id,
                "orderId": order.exchange_order_id,
                "price": str(order.price),
                "qty": str(order.amount),
                "quoteQty": str(order.amount * order.price),
                "commission": "1",
                "commissionAsset": self.base_asset,
                "time": 1499865549590,
                "isBuyer": True,
                "isMaker": False,
            }
        ]

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "orderId": order.exchange_order_id,
            "clientOrderId": order.client_order_id,
            "price": str(order.price),
            "origQty": str(order.amount),
            "executedQty": "0.0",
            "cumulativeQuoteQty": "0.0",
            "status": "NEW",
            "timeInForce": "GTC",
            "type": order.order_type.name.upper(),
            "side": order.trade_type.name.upper(),
            "stopPrice": None,
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": True,
            "workingTime": 1763356604988,
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "orderId": order.exchange_order_id,
            "clientOrderId": order.client_order_id,
            "price": str(order.price),
            "origQty": str(order.amount),
            "executedQty": str(self.expected_partial_fill_amount),
            "cumulativeQuoteQty": str(self.expected_partial_fill_amount * order.price),
            "status": "FILLED",
            "timeInForce": "GTC",
            "type": order.order_type.name.upper(),
            "side": order.trade_type.name.upper(),
            "stopPrice": None,
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": True,
            "workingTime": 1763356604988,
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "orderId": order.exchange_order_id,
            "clientOrderId": order.client_order_id,
            "price": str(order.price),
            "origQty": str(order.amount),
            "executedQty": str(order.amount),
            "cumulativeQuoteQty": str(order.price + Decimal(2)),
            "status": "FILLED",
            "timeInForce": "GTC",
            "type": order.order_type.name,
            "side": order.trade_type.name,
            "stopPrice": None,
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": True,
            "workingTime": 60000,
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "orderId": order.exchange_order_id,
            "clientOrderId": order.client_order_id,
            "price": str(order.price),
            "origQty": str(order.amount),
            "executedQty": "0.0",
            "cumulativeQuoteQty": "0.0",
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": order.order_type.name.upper(),
            "side": order.trade_type.name.upper(),
            "stopPrice": None,
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": True,
            "workingTime": 1763356604988,
        }

    @aioresponses()
    async def test_updating_trading_fees_for_authenticated_user(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        self.configure_user_fees_response(mock_api=mock_api)

        await asyncio.wait_for(self.exchange._update_trading_fees(), timeout=1)

        user_maker_fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("5"),
            price=Decimal("100"),
            is_maker=True,
        )
        user_taker_fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("5"),
            price=Decimal("100"),
            is_maker=False,
        )

        expected_user_maker_fee = self.get_expected_user_fee(is_maker=True)
        expected_user_taker_fee = self.get_expected_user_fee(is_maker=False)

        self.assertEqual(expected_user_maker_fee, user_maker_fee)
        self.assertEqual(expected_user_taker_fee, user_taker_fee)

    @aioresponses()
    async def test_canceling_an_order_that_has_already_been_canceled_detects_order_as_already_canceled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.delete(
            regex_url,
            status=400,
            callback=lambda *_, **__: request_sent_event.set(),
            body=json.dumps(
                {
                    "timestamp": "2025-11-02T09:02:27.801+00:00",
                    "path": "/api/v1/order",
                    "status": 400,
                    "error": "Bad Request",
                    "requestId": "b1667c87-3223",
                    "message": "Order cannot be canceled (already CANCELED)",
                }
            ),
        )

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=self.client_order_id_prefix + "1")
        await asyncio.wait_for(request_sent_event.wait(), timeout=1)
        await asyncio.sleep(0.1)

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Successfully canceled order {order.client_order_id}."
            )
        )
