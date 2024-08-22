import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS, ascend_ex_web_utils as web_utils
from hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange import AscendExExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import BuyOrderCompletedEvent, MarketOrderFailureEvent, OrderFilledEvent


class AscendExExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.PRODUCTS_PATH_URL)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL)
        url = f"{url}?symbol={self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_LIMIT_INFO)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PRODUCTS_PATH_URL)
        return url

    @property
    def order_creation_url(self):
        url = self.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        return url

    @property
    def balance_url(self):
        url = self.private_rest_url(CONSTANTS.BALANCE_PATH_URL)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "code": 0,
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "displayName": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "domain": "USDS",
                    "tradingStartTime": 1546300800000,
                    "collapseDecimals": "1,0.1,0.01",
                    "minQty": "0.000000001",
                    "maxQty": "1000000000",
                    "minNotional": "5",
                    "maxNotional": "400000",
                    "statusCode": "Normal",
                    "statusMessage": "",
                    "tickSize": "0.01",
                    "useTick": False,
                    "lotSize": "0.00001",
                    "useLot": False,
                    "commissionType": "Quote",
                    "commissionReserveRate": "0.001",
                    "qtyScale": 5,
                    "priceScale": 2,
                    "notionalScale": 4,
                },
            ],
        }
        self.exchange._trading_rules[self.trading_pair].min_order_size = Decimal(str(0.01))

    @property
    def latest_prices_request_mock_response(self):
        return {
            "code": 0,
            "data": {
                "symbol": "ASD/USDT",
                "open": "0.06777",
                "close": "0.06809",
                "high": "0.06899",
                "low": "0.06708",
                "volume": "19823722",
                "ask": ["0.0681", "43641"],
                "bid": ["0.0676", "443"],
            },
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "code": 0,
            "data": [
                {
                    "symbol": "INVALID/PAIR",
                    "displayName": "INVALID/PAIR",
                    "domain": "USDS",
                    "tradingStartTime": 1546300800000,
                    "collapseDecimals": "1,0.1,0.01",
                    "minQty": "0.000000001",
                    "maxQty": "1000000000",
                    "minNotional": "5",
                    "maxNotional": "400000",
                    "statusCode": "Normal",
                    "statusMessage": "",
                    "tickSize": "0.01",
                    "useTick": False,
                    "lotSize": "0.00001",
                    "useLot": False,
                    "commissionType": "Quote",
                    "commissionReserveRate": "0.001",
                    "qtyScale": 5,
                    "priceScale": 2,
                    "notionalScale": 4,
                },
            ],
        }

        return response

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return {
            "code": 0,
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "displayName": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "domain": "USDS",
                    "tradingStartTime": 1546300800000,
                    "collapseDecimals": "1,0.1,0.01",
                    "minQty": "0.000000001",
                    "maxQty": "1000000000",
                    "minNotional": "5",
                    "maxNotional": "400000",
                    "statusCode": "Normal",
                    "statusMessage": "",
                    "tickSize": "0.01",
                    "useTick": False,
                    "lotSize": "0.00001",
                    "useLot": False,
                    "commissionType": "Quote",
                    "commissionReserveRate": "0.001",
                    "qtyScale": 5,
                    "priceScale": 2,
                    "notionalScale": 4,
                },
            ],
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "code": 0,
            "data": [
                {
                    "symbol": "A/B",
                    "displayName": None,
                    "domain": "USDS",
                    "tradingStartTime": 1546300800000,
                    "collapseDecimals": "1,0.1,0.01",
                    "minQty": "0.000000001",
                    "maxQty": "1000000000",
                    "minNotional": "5",
                    "maxNotional": "400000",
                    "statusCode": "Normal",
                    "statusMessage": "Normal",
                    "tickSize": "0.01",
                    "useTick": False,
                    "lotSize": "0.00001",
                    "useLot": False,
                    "commissionType": "Quote",
                    "commissionReserveRate": "0.001",
                    "qtyScale": 5,
                    "priceScale": 2,
                    "notionalScale": 4,
                },
            ],
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "code": 0,
            "data": {
                "ac": "CASH",
                "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
                "action": "place-order",
                "info": {
                    "id": "11",
                    "orderId": self.expected_exchange_order_id,
                    "orderType": "Market",
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "timestamp": 1573576916201,
                },
                "status": "Ack",
            },
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "code": 0,
            "data": [
                {"asset": self.quote_asset, "totalBalance": "2000", "availableBalance": "2000"},
                {"asset": self.base_asset, "totalBalance": "15", "availableBalance": "10"},
                {"asset": "ETH", "totalBalance": "0.6", "availableBalance": "0.6"},
            ],
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "code": 0,
            "data": [
                {"asset": self.base_asset, "totalBalance": "15", "availableBalance": "10"},
            ],
        }

    @property
    def balance_event_websocket_update(self):
        # AscendEx sends balance update information inside the order events
        return {
            "m": "order",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "ac": "CASH",
            "data": {
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "sn": "30000",
                "sd": "Buy",
                "ap": "0",
                "bab": "10",
                "btb": "15",
                "cf": "0",
                "cfq": "0",
                "err": "",
                "fa": self.quote_asset,
                "orderId": "testId1",
                "ot": "Limit",
                "p": "7967.62",
                "q": "0.0083",
                "qab": "0.0",
                "qtb": "0.0",
                "sp": "",
                "st": "New",
                "t": 1576019215402,
                "ei": "NULL_VAL",
            },
        }

    @property
    def expected_latest_price(self):
        return 0.06809

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(self.trading_rules_request_mock_response["data"][0]["minQty"]),
            max_order_size=Decimal(self.trading_rules_request_mock_response["data"][0]["maxQty"]),
            min_price_increment=Decimal(self.trading_rules_request_mock_response["data"][0]["tickSize"]),
            min_base_amount_increment=Decimal(self.trading_rules_request_mock_response["data"][0]["lotSize"]),
            min_notional_size=Decimal(self.trading_rules_request_mock_response["data"][0]["minNotional"]),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 21

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10000)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.1")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset, flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

    @property
    def expected_partial_fill_fee(self) -> TradeFeeBase:
        return self.expected_fill_fee

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    @staticmethod
    def private_rest_url(endpoint: str):
        return web_utils.private_rest_url(path_url=endpoint).format(group_id="6")

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}/{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return AscendExExchange(
            client_config_map=client_config_map,
            ascend_ex_api_key="testAPIKey",
            ascend_ex_secret_key="testSecret",
            ascend_ex_group_id="6",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call, params=request_call.kwargs["headers"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(OrderType.LIMIT.name.lower(), request_data["orderType"])
        self.assertEqual(Decimal("100"), Decimal(request_data["orderQty"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["orderPrice"]))
        self.assertEqual(order.client_order_id, request_data["id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertIn("sn", request_params)

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.delete(regex_url, status=400, callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """
        all_urls = []
        url = self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api)
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api)
        all_urls.append(url)
        return all_urls

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        # Implement the expected not found response when enabling test_cancel_order_not_found_in_the_exchange
        raise NotImplementedError

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        # Implement the expected not found response when enabling
        # test_lost_order_removed_if_not_found_during_order_status_update
        raise NotImplementedError

    def configure_completely_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = f"{self.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)}?orderId=21"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = f"{self.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)}?orderId=21"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(path_url="")
        url = url.replace("/v1/", f"/{CONSTANTS.BALANCE_HISTORY_PATH_URL}")
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = f"{self.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)}?orderId=21"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # hist_url = f"{self.private_rest_url(CONSTANTS.HIST_PATH_URL)}?symbol=COINALPHA/HBOT"
        # hist_regex_url = re.compile(f"^{hist_url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        # mock_api.get(hist_regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = f"{self.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)}?orderId=21"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # hist_url = f"{self.private_rest_url(CONSTANTS.HIST_PATH_URL)}?symbol=COINALPHA/HBOT"
        # hist_regex_url = re.compile(f"^{hist_url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        # mock_api.get(hist_regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = f"{self.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)}?orderId=21"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        # hist_url = f"{self.private_rest_url(CONSTANTS.HIST_PATH_URL)}?symbol=COINALPHA/HBOT"
        # hist_regex_url = re.compile(f"^{hist_url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        # mock_api.get(hist_regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(path_url="")
        url = url.replace("/v1/", f"/{CONSTANTS.BALANCE_HISTORY_PATH_URL}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(path_url="")
        url = url.replace("/v1/", f"/{CONSTANTS.BALANCE_HISTORY_PATH_URL}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "m": "order",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "ac": "CASH",
            "data": {
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "sn": "30000",
                "sd": order.trade_type.name.capitalize(),
                "ap": "0",
                "bab": "2006.5974027",
                "btb": "2006.5974027",
                "cf": "0",
                "cfq": "0",
                "err": "",
                "fa": self.quote_asset,
                "orderId": order.exchange_order_id,
                "ot": order.order_type.name.capitalize(),
                "p": str(order.price),
                "q": str(order.amount),
                "qab": "793.23",
                "qtb": "860.23",
                "sp": "",
                "st": "New",
                "t": 1576019215402,
                "ei": "NULL_VAL",
            },
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "m": "order",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "ac": "CASH",
            "data": {
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "sn": "30000",
                "sd": order.trade_type.name.capitalize(),
                "ap": "0",
                "bab": "2006.5974027",
                "btb": "2006.5974027",
                "cf": "0",
                "cfq": "0",
                "err": "",
                "fa": self.quote_asset,
                "orderId": order.exchange_order_id,
                "ot": order.order_type.name.capitalize(),
                "p": str(order.price),
                "q": str(order.amount),
                "qab": "793.23",
                "qtb": "860.23",
                "sp": "",
                "st": "Canceled",
                "t": 1576019215402,
                "ei": "NULL_VAL",
            },
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "m": "order",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "ac": "CASH",
            "data": {
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "sn": "30000",
                "sd": order.trade_type.name.capitalize(),
                "ap": str(order.price),
                "bab": "2006.5974027",
                "btb": "2006.5974027",
                "cf": str(self.expected_fill_fee.flat_fees[0].amount),
                "cfq": str(order.amount),
                "err": "",
                "fa": self.expected_fill_fee.flat_fees[0].token,
                "orderId": order.exchange_order_id,
                "ot": order.order_type.name.capitalize(),
                "p": str(order.price),
                "q": str(order.amount),
                "qab": "793.23",
                "qtb": "860.23",
                "sp": "",
                "st": "Filled",
                "t": 1576019215402,
                "ei": "NULL_VAL",
            },
        }

    def order_event_for_partially_filled_websocket_update(self, order: InFlightOrder):
        return {
            "m": "order",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "ac": "CASH",
            "data": {
                "s": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "sn": "30000",
                "sd": order.trade_type.name.capitalize(),
                "ap": str(self.expected_partial_fill_price),
                "bab": "2006.5974027",
                "btb": "2006.5974027",
                "cf": str(self.expected_partial_fill_fee.flat_fees[0].amount),
                "cfq": str(self.expected_partial_fill_amount),
                "err": "",
                "fa": self.expected_partial_fill_fee.flat_fees[0].token,
                "orderId": order.exchange_order_id,
                "ot": order.order_type.name.capitalize(),
                "p": str(order.price),
                "q": str(order.amount),
                "qab": "793.23",
                "qtb": "860.23",
                "sp": "",
                "st": "PartiallyFilled",
                "t": 1576019215402,
                "ei": "NULL_VAL",
            },
        }

    def order_event_for_partially_canceled_websocket_update(self, order: InFlightOrder):
        return self.order_event_for_canceled_order_websocket_update(order=order)

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    def trade_event_for_partial_fill_websocket_update(self, order: InFlightOrder):
        return None

    @aioresponses()
    def test_update_order_status_when_canceled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (
            self.exchange.current_timestamp - self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1
        )

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["11"]

        url = f"{self.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL)}?orderId=100234"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        hist_url = f"{self.private_rest_url(CONSTANTS.HIST_PATH_URL)}?symbol=COINALPHA/HBOT"
        hist_regex_url = re.compile(f"^{hist_url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "code": 0,
            "accountCategory": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "price": "8130.24",
                "orderQty": "0.00082",
                "orderType": "Limit",
                "avgPx": "7391.13",
                "cumFee": "0.005151618",
                "cumFilledQty": "0.00082",
                "errorCode": "",
                "feeAsset": self.quote_asset,
                "lastExecTime": 1575953134011,
                "orderId": order.exchange_order_id,
                "seqNum": 2622058,
                "side": "Buy",
                "status": "Canceled",
                "stopPrice": "",
                "execInst": "NULL_VAL",
            },
        }

        history_status = {
            "code": 0,
            "accountCategory": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "price": "8130.24",
                    "orderQty": "0.00082",
                    "orderType": "Limit",
                    "avgPx": "7391.13",
                    "cumFee": "0.005151618",
                    "cumFilledQty": "0.00082",
                    "errorCode": "",
                    "feeAsset": self.quote_asset,
                    "lastExecTime": 1575953134011,
                    "orderId": order.exchange_order_id,
                    "seqNum": 2622058,
                    "side": "Buy",
                    "status": "Canceled",
                    "stopPrice": "",
                    "execInst": "NULL_VAL",
                },
            ],
        }

        mock_api.get(regex_url, body=json.dumps(order_status))
        mock_api.get(hist_regex_url, body=json.dumps(history_status))

        self.async_run_with_timeout(self.exchange._update_order_status())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)

        canceled_event: MarketOrderFailureEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, canceled_event.timestamp)
        self.assertEqual(order.client_order_id, canceled_event.order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}."))

    @aioresponses()
    def test_user_stream_update_for_order_full_fill_when_it_had_a_partial_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["11"]

        previous_fill_fee = AddedToCostTradeFee(
            percent_token=self.quote_asset, flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("10"))]
        )

        trade_update = TradeUpdate(
            trade_id="98765",
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fee=previous_fill_fee,
            fill_base_amount=self.expected_partial_fill_amount,
            fill_quote_amount=self.expected_partial_fill_amount * self.expected_partial_fill_price,
            fill_price=self.expected_partial_fill_price,
            fill_timestamp=1640001112.223,
        )
        order.update_with_trade_update(trade_update=trade_update)

        order_event = self.order_event_for_full_fill_websocket_update(order=order)

        mock_queue = AsyncMock()
        event_messages = []
        if order_event:
            event_messages.append(order_event)
        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        if self.is_order_fill_http_update_executed_during_websocket_order_event_processing:
            self.configure_full_fill_trade_response(order=order, mock_api=mock_api)

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount + self.expected_partial_fill_amount)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * fill_event.price, buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(self.is_logged("INFO", f"BUY order {order.client_order_id} completely filled."))

    @aioresponses()
    def test_create_order_fails_with_error_response_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = self.order_creation_url
        creation_response = {
            "code": 300011,
            "ac": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "action": "place-order",
            "info": {"id": "JkpnjJRuBtFpW7F7PWDB7uwBEJtUOISZ", "symbol": self.exchange_trading_pair},
            "message": "Not Enough Account Balance",
            "reason": "INVALID_BALANCE",
            "status": "Err",
        }
        mock_api.post(
            url, body=json.dumps(creation_response), callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        order_to_validate_request = InFlightOrder(
            client_order_id=order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            creation_timestamp=self.exchange.current_timestamp,
            price=Decimal("10000"),
        )
        self.validate_order_creation_request(order=order_to_validate_request, request_call=order_request)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "NETWORK",
                f"Error submitting {order_to_validate_request.trade_type.name.lower()} "
                f"{order_to_validate_request.order_type.name} order to Ascend_ex for 100.000000 {self.trading_pair} "
                f"10000.0000.",
            )
        )
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)",
            )
        )

    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        # Disabling this test because the connector has not been updated yet to validate
        # order not found during cancellation (check _is_order_not_found_during_cancelation_error)
        pass

    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        # Disabling this test because the connector has not been updated yet to validate
        # order not found during status update (check _is_order_not_found_during_status_update_error)
        pass

    def _validate_auth_credentials_taking_parameters_from_argument(
        self, request_call_tuple: RequestCall, params: Dict[str, Any]
    ):
        self.assertIn("x-auth-timestamp", params)
        self.assertIn("x-auth-signature", params)
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("x-auth-key", request_headers)
        self.assertEqual("testAPIKey", request_headers["x-auth-key"])

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {"code": 0}

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "accountCategory": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "price": "10000",
                "orderQty": "1",
                "orderType": "Limit",
                "avgPx": "10000",
                "cumFee": "0.1",
                "cumFilledQty": "0",
                "errorCode": "",
                "feeAsset": self.quote_asset,
                "lastExecTime": 1575953134011,
                "orderId": order.exchange_order_id,
                "seqNum": 2622058,
                "side": "Buy",
                "status": "Filled",
                "stopPrice": "",
                "execInst": "NULL_VAL",
            },
        }

    def _order_trade_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        base_amount = str(order.amount) if order.trade_type == TradeType.BUY else str(-1 * order.amount)
        quote_amount = (
            str(order.amount * order.price)
            if order.trade_type == TradeType.SELL
            else str(-1 * order.amount * order.price)
        )
        return {
            "meta": {"ac": "cash", "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo"},
            "order": [
                {
                    "data": [
                        {
                            "asset": order.base_asset,
                            "curBalance": base_amount,
                            "dataType": "trade",
                            "deltaQty": base_amount,
                        },
                        {
                            "asset": order.quote_asset,
                            "curBalance": quote_amount,
                            "dataType": "trade",
                            "deltaQty": quote_amount,
                        },
                        {
                            "asset": self.expected_fill_fee.flat_fees[0].token,
                            "curBalance": str(self.expected_fill_fee.flat_fees[0].amount * -1),
                            "dataType": "fee",
                            "deltaQty": str(self.expected_fill_fee.flat_fees[0].amount * -1),
                        },
                    ],
                    "liquidityInd": "RemovedLiquidity",
                    "orderId": order.exchange_order_id,
                    "orderType": "Limit",
                    "side": order.trade_type.name.capitalize(),
                    "sn": int(self.expected_fill_trade_id),
                    "transactTime": 1616852892564,
                }
            ],
            "balance": [],
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "accountCategory": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "price": "8130.24",
                "orderQty": "1",
                "orderType": "Limit",
                "avgPx": "7391.13",
                "cumFee": "0.005151618",
                "cumFilledQty": "1",
                "errorCode": "",
                "feeAsset": self.quote_asset,
                "lastExecTime": 1575953134011,
                "orderId": order.exchange_order_id,
                "seqNum": 2622058,
                "side": "Buy",
                "status": "Canceled",
                "stopPrice": "",
                "execInst": "NULL_VAL",
            },
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "accountCategory": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "price": "8130.24",
                "orderQty": "1",
                "orderType": "Limit",
                "avgPx": "7391.13",
                "cumFee": "0.005151618",
                "cumFilledQty": "1",
                "errorCode": "",
                "feeAsset": self.quote_asset,
                "lastExecTime": 1575953134011,
                "orderId": order.exchange_order_id,
                "seqNum": 2622058,
                "side": "Buy",
                "status": "New",
                "stopPrice": "",
                "execInst": "NULL_VAL",
            },
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "accountCategory": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "price": "10000",
                "orderQty": "10",
                "orderType": "Limit",
                "avgPx": "7391.13",
                "cumFee": "3",
                "cumFilledQty": "10",
                "errorCode": "",
                "feeAsset": self.quote_asset,
                "lastExecTime": 1575953134011,
                "orderId": order.exchange_order_id,
                "seqNum": 30000,
                "side": "Buy",
                "status": "PartiallyFilled",
                "stopPrice": "",
                "execInst": "NULL_VAL",
            },
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        base_amount = (
            str(self.expected_partial_fill_amount)
            if order.trade_type == TradeType.BUY
            else str(-1 * self.expected_partial_fill_amount)
        )
        quote_amount = (
            str(self.expected_partial_fill_amount * self.expected_partial_fill_price)
            if order.trade_type == TradeType.SELL
            else str(-1 * self.expected_partial_fill_amount * self.expected_partial_fill_price)
        )
        return {
            "meta": {"ac": "cash", "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo"},
            "order": [
                {
                    "data": [
                        {
                            "asset": order.base_asset,
                            "curBalance": base_amount,
                            "dataType": "trade",
                            "deltaQty": base_amount,
                        },
                        {
                            "asset": order.quote_asset,
                            "curBalance": quote_amount,
                            "dataType": "trade",
                            "deltaQty": quote_amount,
                        },
                        {
                            "asset": self.expected_partial_fill_fee.flat_fees[0].token,
                            "curBalance": str(self.expected_partial_fill_fee.flat_fees[0].amount * -1),
                            "dataType": "fee",
                            "deltaQty": str(self.expected_partial_fill_fee.flat_fees[0].amount * -1),
                        },
                    ],
                    "liquidityInd": "RemovedLiquidity",
                    "orderId": order.exchange_order_id,
                    "orderType": "Limit",
                    "side": order.trade_type.name.capitalize(),
                    "sn": int(self.expected_fill_trade_id),
                    "transactTime": 1616852892564,
                }
            ],
            "balance": [],
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return self._order_trade_request_completely_filled_mock_response(order)

    def place_buy_market_order(self, amount: Decimal = Decimal("100"), price: Decimal = Decimal("10_000")):
        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=amount,
            order_type=OrderType.MARKET,
            price=price,
        )
        return order_id

    @aioresponses()
    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    def test_create_buy_market_order_successfully(self, mock_api, get_price_mock):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        get_price_mock.return_value = Decimal("10_000")
        url = self.order_creation_url

        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_market_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        request_data = json.loads(order_request.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])
        self.assertEqual(self.exchange.in_flight_orders[order_id].trade_type.name.lower(), request_data["side"])
        self.assertEqual(OrderType.MARKET.name.lower(), request_data["orderType"])
        self.assertEqual(Decimal("100"), Decimal(request_data["orderQty"]))
        self.assertEqual("IOC", request_data["timeInForce"])
        self.assertEqual(self.exchange.in_flight_orders[order_id].client_order_id, request_data["id"])
        create_event = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.MARKET, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.MARKET.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} {self.trading_pair} at {Decimal('10000')}."
            )
        )
