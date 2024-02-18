import json
import logging
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.kraken import kraken_constants as CONSTANTS, kraken_web_utils as web_utils
from hummingbot.connector.exchange.kraken.kraken_exchange import KrakenExchange
from hummingbot.connector.exchange.kraken.kraken_utils import (
    convert_to_exchange_trading_pair,
)
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent, OrderFilledEvent


class KrakenExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    _logger = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5nE9qa99HAZtuZuj6F1huXg=="  # noqa: mock
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"  # linear
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.ws_ex_trading_pairs = cls.base_asset + "/" + cls.quote_asset

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.ASSET_PAIRS_PATH_URL)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL)
        url = f"{url}?symbol={self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.private_rest_url(CONSTANTS.TICKER_PATH_URL)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ASSET_PAIRS_PATH_URL)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ADD_ORDER_PATH_URL)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.BALANCE_PATH_URL)
        return url

    @property
    def latest_prices_request_mock_response(self):
        return {
            "error": [],
            "result": {
                "XXBTZUSD": {
                    "a": [
                        "30300.10000",
                        "1",
                        "1.000"
                    ],
                    "b": [
                        "30300.00000",
                        "1",
                        "1.000"
                    ],
                    "c": [
                        "30303.20000",
                        "0.00067643"
                    ],
                    "v": [
                        "4083.67001100",
                        "4412.73601799"
                    ],
                    "p": [
                        "30706.77771",
                        "30689.13205"
                    ],
                    "t": [
                        34619,
                        38907
                    ],
                    "l": [
                        "29868.30000",
                        "29868.30000"
                    ],
                    "h": [
                        "31631.00000",
                        "31631.00000"
                    ],
                    "o": "30502.80000"
                }
            }
        }

    @property
    def balance_event_websocket_update(self):
        pass

    @property
    def all_symbols_request_mock_response(self):
        return {
            self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset): {
                "altname": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "wsname": f"{self.base_asset}/{self.quote_asset}",
                "aclass_base": "currency",
                "base": self.base_asset,
                "aclass_quote": "currency",
                "quote": self.quote_asset,
                "lot": "unit",
                "pair_decimals": 1,
                "lot_decimals": 8,
                "lot_multiplier": 1,
                "leverage_buy": [2, 3],
                "leverage_sell": [2, 3],
                "fees": [
                    [0, 0.26],
                    [50000, 0.24],
                    [100000, 0.22],
                    [250000, 0.2],
                    [500000, 0.18],
                    [1000000, 0.16],
                    [2500000, 0.14],
                    [5000000, 0.12],
                    [10000000, 0.1]
                ],
                "fees_maker": [
                    [0, 0.16],
                    [50000, 0.14],
                    [100000, 0.12],
                    [250000, 0.1],
                    [500000, 0.08],
                    [1000000, 0.06],
                    [2500000, 0.04],
                    [5000000, 0.02],
                    [10000000, 0]
                ],
                "fee_volume_currency": "ZUSD",
                "margin_call": 80,
                "margin_stop": 40,
                "ordermin": "0.0002"
            }
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset): {
                "altname": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "wsname": f"{self.base_asset}/{self.quote_asset}",
                "aclass_base": "currency",
                "base": self.base_asset,
                "aclass_quote": "currency",
                "quote": self.quote_asset,
                "lot": "unit",
                "pair_decimals": 1,
                "lot_decimals": 8,
                "lot_multiplier": 1,
                "leverage_buy": [2, 3],
                "leverage_sell": [2, 3],
                "fees": [
                    [0, 0.26],
                    [50000, 0.24],
                    [100000, 0.22],
                    [250000, 0.2],
                    [500000, 0.18],
                    [1000000, 0.16],
                    [2500000, 0.14],
                    [5000000, 0.12],
                    [10000000, 0.1]
                ],
                "fees_maker": [
                    [0, 0.16],
                    [50000, 0.14],
                    [100000, 0.12],
                    [250000, 0.1],
                    [500000, 0.08],
                    [1000000, 0.06],
                    [2500000, 0.04],
                    [5000000, 0.02],
                    [10000000, 0]
                ],
                "fee_volume_currency": "ZUSD",
                "margin_call": 80,
                "margin_stop": 40,
                "ordermin": "0.0002"
            },
            "ETHUSDT.d": {
                "altname": "ETHUSDT.d",
                "wsname": "XBT/USDT",
                "aclass_base": "currency",
                "base": "XXBT",
                "aclass_quote": "currency",
                "quote": "USDT",
                "lot": "unit",
                "pair_decimals": 1,
                "lot_decimals": 8,
                "lot_multiplier": 1,
                "leverage_buy": [2, 3],
                "leverage_sell": [2, 3],
                "fees": [
                    [0, 0.26],
                    [50000, 0.24],
                    [100000, 0.22],
                    [250000, 0.2],
                    [500000, 0.18],
                    [1000000, 0.16],
                    [2500000, 0.14],
                    [5000000, 0.12],
                    [10000000, 0.1]
                ],
                "fees_maker": [
                    [0, 0.16],
                    [50000, 0.14],
                    [100000, 0.12],
                    [250000, 0.1],
                    [500000, 0.08],
                    [1000000, 0.06],
                    [2500000, 0.04],
                    [5000000, 0.02],
                    [10000000, 0]
                ],
                "fee_volume_currency": "ZUSD",
                "margin_call": 80,
                "margin_stop": 40,
                "ordermin": "0.0002"
            }
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return {
            self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset): {
                "altname": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "wsname": f"{self.base_asset}/{self.quote_asset}",
                "aclass_base": "currency",
                "base": self.base_asset,
                "aclass_quote": "currency",
                "quote": self.quote_asset,
                "lot": "unit",
                "pair_decimals": 1,
                "lot_decimals": 8,
                "lot_multiplier": 1,
                "leverage_buy": [2, 3],
                "leverage_sell": [2, 3],
                "fees": [
                    [0, 0.26],
                    [50000, 0.24],
                    [100000, 0.22],
                    [250000, 0.2],
                    [500000, 0.18],
                    [1000000, 0.16],
                    [2500000, 0.14],
                    [5000000, 0.12],
                    [10000000, 0.1]
                ],
                "fees_maker": [
                    [0, 0.16],
                    [50000, 0.14],
                    [100000, 0.12],
                    [250000, 0.1],
                    [500000, 0.08],
                    [1000000, 0.06],
                    [2500000, 0.04],
                    [5000000, 0.02],
                    [10000000, 0]
                ],
                "fee_volume_currency": "ZUSD",
                "margin_call": 80,
                "margin_stop": 40,
                "ordermin": "0.0002"
            }
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "XBTUSDT": {
                "altname": "XBTUSDT",
                "wsname": "XBT/USDT",
                "aclass_base": "currency",
                "base": "XXBT",
                "aclass_quote": "currency",
                "quote": "USDT",
                "lot": "unit",
                "leverage_buy": [2, 3],
                "leverage_sell": [2, 3],
                "fees": [
                    [0, 0.26],
                    [50000, 0.24],
                    [100000, 0.22],
                    [250000, 0.2],
                    [500000, 0.18],
                    [1000000, 0.16],
                    [2500000, 0.14],
                    [5000000, 0.12],
                    [10000000, 0.1]
                ],
                "fees_maker": [
                    [0, 0.16],
                    [50000, 0.14],
                    [100000, 0.12],
                    [250000, 0.1],
                    [500000, 0.08],
                    [1000000, 0.06],
                    [2500000, 0.04],
                    [5000000, 0.02],
                    [10000000, 0]
                ],
                "fee_volume_currency": "ZUSD",
                "margin_call": 80,
                "margin_stop": 40,
            }
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
                "descr": {
                    "order": "",
                },
                "txid": [
                    self.expected_exchange_order_id,
                ]
            }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "error": [],
            "result": {
                self.base_asset: str(10),
                self.quote_asset: str(2000),
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "error": [],
            "result": {
                self.base_asset: str(10),
            }
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        rule = list(self.trading_rules_request_mock_response.values())[0]
        min_order_size = Decimal(rule.get('ordermin', 0))
        min_price_increment = Decimal(f"1e-{rule.get('pair_decimals')}")
        min_base_amount_increment = Decimal(f"1e-{rule.get('lot_decimals')}")
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=min_order_size,
            min_price_increment=min_price_increment,
            min_base_amount_increment=min_base_amount_increment,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["symbols"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

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
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return KrakenExchange(
            client_config_map=client_config_map,
            kraken_api_key=self.api_key,
            kraken_secret_key=self.api_secret,
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call,
            params=request_call.kwargs["data"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["pair"])
        self.assertEqual(order.trade_type.name.upper(), request_data["type"])
        self.assertEqual(KrakenExchange.kraken_order_type(OrderType.LIMIT), request_data["ordertype"])
        self.assertEqual(Decimal("100"), Decimal(request_data["volume"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["data"])
        self.assertEqual(order.exchange_order_id, request_data["txid"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["txid"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["data"]
        self.assertEqual(order.exchange_order_id, str(request_params["txid"]))

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
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {
            "error": [
                "API key doesn't have permission to make this request"
            ]
        }
        mock_api.post(regex_url, status=400, body=json.dumps(response), callback=callback)
        return url

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
        url = web_utils.private_rest_url(CONSTANTS.QUERY_ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.QUERY_ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.QUERY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.QUERY_ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.QUERY_ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.QUERY_ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.QUERY_ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2013, "msg": "Order does not exist."}
        mock_api.get(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.QUERY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.QUERY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return [
            [
                {
                    order.exchange_order_id: {
                        "avg_price": "34.50000",
                        "cost": "0.00000",
                        "descr": {
                            "close": "",
                            "leverage": "0:1",
                            "order": "sell 10.00345345 XBT/EUR @ limit 34.50000 with 0:1 leverage",
                            "ordertype": "limit",
                            "pair": convert_to_exchange_trading_pair(self.trading_pair, '/'),
                            "price": str(order.price),
                            "price2": "0.00000",
                            "type": "sell"
                        },
                        "expiretm": "0.000000",
                        "fee": "0.00000",
                        "limitprice": "34.50000",
                        "misc": "",
                        "oflags": "fcib",
                        "opentm": "0.000000",
                        "refid": "OKIVMP-5GVZN-Z2D2UA",
                        "starttm": "0.000000",
                        "status": "open",
                        "stopprice": "0.000000",
                        "userref": 0,
                        "vol": str(order.amount, ),
                        "vol_exec": "0.00000000"
                    }
                }
            ],
            "openOrders",
            {
                "sequence": 234
            }
        ]

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "c": "spot@private.orders.v3.api",
            "d": {
                "A": 8.0,
                "O": 1661938138000,
                "S": 1,
                "V": 10,
                "a": 8,
                "c": order.client_order_id,
                "i": order.exchange_order_id,
                "m": 0,
                "o": 1,
                "p": order.price,
                "s": 4,
                "v": order.amount,
                "ap": 0,
                "cv": 0,
                "ca": 0
            },
            "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "t": 1499405658657
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "c": "spot@private.orders.v3.api",
            "d": {
                "A": 8.0,
                "O": 1661938138000,
                "S": 1,
                "V": 10,
                "a": 8,
                "c": order.client_order_id,
                "i": order.exchange_order_id,
                "m": 0,
                "o": 1,
                "p": order.price,
                "s": 2,
                "v": order.amount,
                "ap": 0,
                "cv": 0,
                "ca": 0
            },
            "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "t": 1499405658657
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "c": "spot@private.deals.v3.api",
            "d": {
                "p": order.price,
                "v": order.amount,
                "a": order.price * order.amount,
                "S": 1,
                "T": 1678901086198,
                "t": "5bbb6ad8b4474570b155610e3960cd",
                "c": order.client_order_id,
                "i": order.exchange_order_id,
                "m": 0,
                "st": 0,
                "n": Decimal(self.expected_fill_fee.flat_fees[0].amount),
                "N": self.quote_asset
            },
            "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "t": 1661938980285
        }

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        pass

    def test_user_stream_balance_update(self):
        pass

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        pass

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        pass

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
            price=Decimal("10000"),
            amount=Decimal("1"),
            userref=1,

        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(CONSTANTS.QUERY_TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "error": [],
            "result": {
                28457: {
                    "ordertxid": order.exchange_order_id,
                    "postxid": "TKH2SE-M7IF5-CFI7LT",
                    "pair": "XXBTZUSD",
                    "time": 1499865549.590,
                    "type": "buy",
                    "ordertype": "limit",
                    "price": str(self.expected_partial_fill_price),
                    "cost": "600.20000",
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "vol": str(self.expected_partial_fill_amount),
                    "margin": "0.00000",
                    "misc": "",
                    "trade_id": 93748276,
                    "maker": "true"
                }
            }
        }

        trade_fill_non_tracked_order = {
            "error": [],
            "result": {
                30000: {
                    "ordertxid": 9999,
                    "postxid": "TKH2SE-M7IF5-CFI7LT",
                    "pair": "XXBTZUSD",
                    "time": 1499865549.590,
                    "type": "buy",
                    "ordertype": "limit",
                    "price": str(self.expected_partial_fill_price),
                    "cost": "600.20000",
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "vol": str(self.expected_partial_fill_amount),
                    "margin": "0.00000",
                    "misc": "",
                    "trade_id": 93748276,
                    "maker": "true"
                }
            }
        }

        mock_response = [trade_fill, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill_non_tracked_order["orderId"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill["vol"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(self.quote_asset, Decimal(trade_fill["fee"]))],
                         fill_event.trade_fee.flat_fees)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(float(trade_fill_non_tracked_order["time"]) * 1e-3, fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["vol"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                self.quote_asset,
                Decimal(trade_fill_non_tracked_order["fee"]))],
            fill_event.trade_fee.flat_fees)
        self.assertTrue(self.is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

    @aioresponses()
    def test_update_order_status_when_failed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            userref=1,
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(CONSTANTS.QUERY_ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "error": [],
            "result": {
                "open": {
                    order.exchange_order_id: {
                        "refid": "None",
                        "userref": 0,
                        "status": "open",
                        "opentm": 1499827319.559,
                        "starttm": 0,
                        "expiretm": 0,
                        "descr": {},
                        "vol": "1.0",
                        "vol_exec": "0.0",
                        "cost": "11253.7",
                        "fee": "0.00000",
                        "price": "10000.0",
                        "stopprice": "0.00000",
                        "limitprice": "0.00000",
                        "misc": "",
                        "oflags": "fciq",
                        "trades": []
                    }
                }
            }
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["txid"])

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
                f" update_timestamp={order_status['updateTime'] * 1e-3}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id='{order.exchange_order_id}', "
                "misc_updates=None)")
        )

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

    @aioresponses()
    def test_place_order_manage_server_overloaded_error_unkown_order(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        url = web_utils.private_rest_url(CONSTANTS.ADD_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {"code": -1003, "msg": "Unknown error, please check your request or try again later."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        o_id, transact_time = self.async_run_with_timeout(self.exchange._place_order(
            order_id="test_order_id",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        ))
        self.assertEqual(o_id, "UNKNOWN")

    @aioresponses()
    def test_place_order_manage_server_overloaded_error_failure(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        url = web_utils.private_rest_url(CONSTANTS.ADD_ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {"code": -1003, "msg": "Service Unavailable."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="test_order_id",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

        mock_response = {"code": -1003, "msg": "Internal error; unable to process your request. Please try again."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="test_order_id",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

    def _validate_auth_credentials_taking_parameters_from_argument(self,
                                                                   request_call_tuple: RequestCall,
                                                                   params: Dict[str, Any]):
        self.assertIn("nonce", params)
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("API-Sign", request_headers)
        self.assertIn("API-Key", request_headers)
        self.assertEqual("testAPIKey", request_headers["API-Key"])

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "error": [],
            "result": {
                "count": 1
            }
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return \
            {
                "error": [],
                "result": {
                    "open": {
                        order.exchange_order_id: {
                            "refid": "None",
                            "userref": 0,
                            "status": "closed",
                            "opentm": 1688666559.8974,
                            "starttm": 0,
                            "expiretm": 0,
                            "descr": {},
                            "vol": str(order.amount),
                            "vol_exec": str(order.amount),
                            "cost": "11253.7",
                            "fee": "0.00000",
                            "price": str(order.price),
                            "stopprice": "0.00000",
                            "limitprice": "0.00000",
                            "misc": "",
                            "oflags": "fciq",
                            "trades": []
                        }
                    }
                }
            }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "error": [],
            "result": {
                "count": 1
            }
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "error": [],
            "result": {
                "open": {
                    order.exchange_order_id: {
                        "refid": "None",
                        "userref": 0,
                        "status": "open",
                        "opentm": 1688666559.8974,
                        "starttm": 0,
                        "expiretm": 0,
                        "descr": {},
                        "vol": str(order.amount),
                        "vol_exec": "0",
                        "cost": "11253.7",
                        "fee": "0.00000",
                        "price": str(order.price),
                        "stopprice": "0.00000",
                        "limitprice": "0.00000",
                        "misc": "",
                        "oflags": "fciq",
                        "trades": []
                    }
                }
            }
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "error": [],
            "result": {
                "open": {
                    order.exchange_order_id: {
                        "refid": "None",
                        "userref": 0,
                        "status": "open",
                        "opentm": 1688666559.8974,
                        "starttm": 0,
                        "expiretm": 0,
                        "descr": {},
                        "vol": str(order.amount),
                        "vol_exec": str(order.amount / 2),
                        "cost": "11253.7",
                        "fee": "0.00000",
                        "price": str(order.price),
                        "stopprice": "0.00000",
                        "limitprice": "0.00000",
                        "misc": "",
                        "oflags": "fciq",
                        "trades": []
                    }
                }
            }
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "error": [],
            "result": {
                self.expected_fill_trade_id: {
                    "ordertxid": "OQCLML-BW3P3-BUCMWZ",
                    "postxid": "TKH2SE-M7IF5-CFI7LT",
                    "pair": "XXBTZUSD",
                    "time": 1499865549.590,
                    "type": "buy",
                    "ordertype": "limit",
                    "price": str(self.expected_partial_fill_price),
                    "cost": "600.20000",
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "vol": str(self.expected_partial_fill_amount),
                    "margin": "0.00000",
                    "misc": "",
                    "trade_id": 93748276,
                    "maker": "true"
                }
            }
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "error": [],
            "result": {
                self.expected_fill_trade_id: {
                    "ordertxid": "OQCLML-BW3P3-BUCMWZ",
                    "postxid": "TKH2SE-M7IF5-CFI7LT",
                    "pair": "XXBTZUSD",
                    "time": 1499865549.590,
                    "type": "buy",
                    "ordertype": "limit",
                    "price": str(order.price),
                    "cost": "600.20000",
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "vol": str(order.amount),
                    "margin": "0.00000",
                    "misc": "",
                    "trade_id": 93748276,
                    "maker": "true"
                }
            }
        }
