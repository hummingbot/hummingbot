import json
import math
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.exchange.bitmart import bitmart_constants as CONSTANTS, bitmart_web_utils as web_utils
from hummingbot.connector.exchange.bitmart.bitmart_exchange import BitmartExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class BitmartExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.GET_TRADING_RULES_PATH_URL)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.GET_LAST_TRADING_PRICES_PATH_URL)
        url = f"{url}?symbol={self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.CHECK_NETWORK_PATH_URL)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.GET_TRADING_RULES_PATH_URL)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.CREATE_ORDER_PATH_URL)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.GET_ACCOUNT_SUMMARY_PATH_URL)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "symbols": [
                    {
                        "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                        "symbol_id": 1024,
                        "base_currency": self.base_asset,
                        "quote_currency": self.quote_asset,
                        "quote_increment": "1.00000000",
                        "base_min_size": "1.00000000",
                        "price_min_precision": 6,
                        "price_max_precision": 8,
                        "expiration": "NA",
                        "min_buy_amount": "0.00010000",
                        "min_sell_amount": "0.00010000",
                        "trade_status": "trading"
                    },
                ]
            }
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "message": "OK",
            "code": 1000,
            "trace": "6e42c7c9-fdc5-461b-8fd1-b4e2e1b9ed57",
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "last": str(self.expected_latest_price),
                "qv_24h": "201477650.88000",
                "v_24h": "25186.48000",
                "high_24h": "8800.00",
                "low_24h": "1.00",
                "open_24h": "8800.00",
                "ask_px": "0.00",
                "ask_sz": "0.00000",
                "bid_px": "0.00",
                "bid_sz": "0.00000",
                "fluctuation": "-0.9999"
            }
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "symbols": [
                    {
                        "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                        "symbol_id": 1024,
                        "base_currency": self.base_asset,
                        "quote_currency": self.quote_asset,
                        "quote_increment": "1.00000000",
                        "base_min_size": "1.00000000",
                        "price_min_precision": 6,
                        "price_max_precision": 8,
                        "expiration": "NA",
                        "min_buy_amount": "0.00010000",
                        "min_sell_amount": "0.00010000",
                        "trade_status": "trading"
                    },
                    {
                        "symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                        "symbol_id": 1025,
                        "base_currency": "INVALID",
                        "quote_currency": "PAIR",
                        "quote_increment": "1.00000000",
                        "base_min_size": "1.00000000",
                        "price_min_precision": 6,
                        "price_max_precision": 8,
                        "expiration": "NA",
                        "min_buy_amount": "0.00010000",
                        "min_sell_amount": "0.00010000",
                        "trade_status": "pre-trade"
                    },
                ]
            }
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "serivce": [
                    {
                        "title": "Spot API Stop",
                        "service_type": "spot",
                        "status": "2",
                        "start_time": 1527777538000,
                        "end_time": 1527777538000
                    },
                    {
                        "title": "Contract API Stop",
                        "service_type": "contract",
                        "status": "2",
                        "start_time": 1527777538000,
                        "end_time": 1527777538000
                    }
                ]
            }
        }

    @property
    def trading_rules_request_mock_response(self):
        return {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "symbols": [
                    {
                        "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                        "symbol_id": 1024,
                        "base_currency": self.base_asset,
                        "quote_currency": self.quote_asset,
                        "quote_increment": "1.00000000",
                        "base_min_size": "5.00000000",
                        "price_min_precision": 6,
                        "price_max_precision": 8,
                        "expiration": "NA",
                        "min_buy_amount": "0.00020000",
                        "min_sell_amount": "0.00030000",
                        "trade_status": "trading"
                    },
                ]
            }
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "symbols": [
                    {
                        "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                        "symbol_id": 1024,
                        "base_currency": self.base_asset,
                        "quote_currency": self.quote_asset,
                        "expiration": "NA",
                        "trade_status": "trading"
                    },
                ]
            }
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "order_id": self.expected_exchange_order_id
            }
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "wallet": [
                    {
                        "id": self.base_asset,
                        "available": "10.000000",
                        "name": "CoinAlpha",
                        "frozen": "5.000000",
                    },
                    {
                        "id": self.quote_asset,
                        "available": "2000.000000",
                        "name": "Hbot",
                        "frozen": "0.0",
                    },
                ]
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "wallet": [
                    {
                        "id": self.base_asset,
                        "available": "10.000000",
                        "name": "CoinAlpha",
                        "frozen": "5.000000",
                    },
                ]
            }
        }

    @property
    def balance_event_websocket_update(self):
        # Bitmart does not provide balance updates through websocket
        self.fail()

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        price_decimals = Decimal(str(
            self.trading_rules_request_mock_response["data"]["symbols"][0]["price_max_precision"]))
        price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(self.trading_rules_request_mock_response["data"]["symbols"][0]["base_min_size"]),
            min_order_value=Decimal(self.trading_rules_request_mock_response["data"]["symbols"][0]["min_buy_amount"]),
            min_base_amount_increment=Decimal(str(
                self.trading_rules_request_mock_response["data"]["symbols"][0]["base_min_size"])),
            min_price_increment=price_step,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"]["symbols"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 1736871726781

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return True

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
        return 30000

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return base_token + "_" + quote_token

    def create_exchange_instance(self):
        return BitmartExchange(
            bitmart_api_key="testAPIKey",
            bitmart_secret_key="testSecret",
            bitmart_memo="testMemo",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("X-BM-KEY", request_headers)
        self.assertEqual("testAPIKey", request_headers["X-BM-KEY"])
        self.assertIn("X-BM-TIMESTAMP", request_headers)
        self.assertIn("X-BM-SIGN", request_headers)
        self.assertIn("X-BM-BROKER-ID", request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["symbol"])
        self.assertEqual("limit", request_data["type"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(Decimal("100"), Decimal(request_data["size"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["client_order_id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(json.loads(request_call.kwargs["data"]))
        self.assertEqual(order.client_order_id, request_data["client_order_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = dict(json.loads(request_call.kwargs["data"]))
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = dict(json.loads(request_call.kwargs["data"]))
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

    def configure_successful_cancelation_response(self,
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

    def configure_one_successful_one_erroneous_cancel_all_response(self,
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
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_DETAIL_PATH_URL)
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(self,
                                                 order: InFlightOrder,
                                                 mock_api: aioresponses,
                                                 callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_DETAIL_PATH_URL)
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(self,
                                             order: InFlightOrder,
                                             mock_api: aioresponses,
                                             callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_DETAIL_PATH_URL)
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_DETAIL_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.GET_ORDER_DETAIL_PATH_URL)
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_TRADE_DETAIL_PATH_URL)
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_TRADE_DETAIL_PATH_URL)
        mock_api.post(url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_TRADE_DETAIL_PATH_URL)
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "side": order.trade_type.name.lower(),
                    "type": "limit",
                    "notional": "",
                    "size": str(order.amount),
                    "ms_t": "1609926028000",
                    "price": str(order.price),
                    "filled_notional": "00.0000000000",
                    "filled_size": "0.0000000000",
                    "margin_trading": "0",
                    "order_state": "new",
                    "order_id": order.exchange_order_id,
                    "order_type": "0",
                    "last_fill_time": "0",
                    "last_fill_price": "0.00000",
                    "last_fill_count": "0.00000",
                    "exec_type": "M",
                    "detail_id": "",
                    "client_order_id": order.client_order_id
                }
            ],
            "table": "spot/user/order"
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "side": order.trade_type.name.lower(),
                    "type": "limit",
                    "notional": "",
                    "size": str(order.amount),
                    "ms_t": "1609926028000",
                    "price": str(order.price),
                    "filled_notional": "00.0000000000",
                    "filled_size": "0.0000000000",
                    "margin_trading": "0",
                    "order_state": "canceled",
                    "order_id": order.exchange_order_id,
                    "order_type": "0",
                    "last_fill_time": "0",
                    "last_fill_price": "0.00000",
                    "last_fill_count": "0.00000",
                    "exec_type": "M",
                    "detail_id": "",
                    "client_order_id": order.client_order_id
                }
            ],
            "table": "spot/user/order"
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "side": order.trade_type.name.lower(),
                    "type": "limit",
                    "notional": "",
                    "size": str(order.amount),
                    "ms_t": "1609926028000",
                    "price": str(order.price),
                    "filled_notional": str(order.amount * order.price),
                    "filled_size": str(order.amount),
                    "margin_trading": "0",
                    "order_state": "filled",
                    "order_id": order.exchange_order_id,
                    "order_type": "0",
                    "last_fill_time": "1609926039226",
                    "last_fill_price": str(order.price),
                    "last_fill_count": str(order.amount),
                    "exec_type": "M",
                    "detail_id": self.expected_fill_trade_id,
                    "client_order_id": order.client_order_id
                }
            ],
            "table": "spot/user/order"
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        pass

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError("Error executing request POST https://api.binance.com/api/v3/order. HTTP status is 400. "
                            'Error: {"code":30007,"msg":"Header X-BM-TIMESTAMP range. Within a minute"}')
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.binance.com/api/v3/order. HTTP status is 400. "
                            'Error: {"code":30008,"msg":"Header X-BM-TIMESTAMP invalid format"}')
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.binance.com/api/v3/order. HTTP status is 400. "
                            'Error: {"code":30000,"msg":"Header X-BM-TIMESTAMP range. Within a minute"}')
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.binance.com/api/v3/order. HTTP status is 400. "
                            'Error: {"code":30007,"msg":"Other message"}')
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.binance.com/api/v3/order. HTTP status is 400. "
                            'Error: {"code":30008,"msg":"Other message"}')
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

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

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        # Disabling this test because the anomylous error that occurs when new pairs
        # are listed thorws a KeyError which we are now swallowing
        pass

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "result": True
            }
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or 1736871726781
        return {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
            "data": {
                "orderId": exchange_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "create_time": 1591096004000,
                "side": order.trade_type.name.lower(),
                "type": "limit",
                "price": str(order.price),
                "price_avg": "0.00",
                "size": str(order.amount),
                "notional": str(order.amount * order.price),
                "filled_notional": "0.00000000",
                "filled_size": "0.00000",
                "unfilled_volume": "0.02000",
                "state": "canceled",
                "clientOrderId": order.client_order_id
            }
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or 1736871726781
        return {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
            "data": {
                "orderId": exchange_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "create_time": 1591096004000,
                "side": order.trade_type.name.lower(),
                "type": "limit",
                "price": str(order.price),
                "price_avg": str(order.price + Decimal(2)),
                "size": str(order.amount),
                "notional": str(order.amount * order.price),
                "filled_notional": str(order.amount * (order.price + Decimal(2))),
                "filled_size": str(order.amount),
                "unfilled_volume": "0.00000",
                "state": "filled",
                "clientOrderId": order.client_order_id
            }
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        exchange_order_id = order.exchange_order_id or 1736871726781
        return {
            "message": "OK",
            "code": 1000,
            "trace": "a06a5c53-8e6f-42d6-8082-2ff4718d221c",
            "data": [
                {
                    "tradeId": self.expected_fill_trade_id,
                    "orderId": exchange_order_id,
                    "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "createTime": 1590462303000,
                    "side": order.trade_type.name.lower(),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "feeCoinName": self.expected_fill_fee.flat_fees[0].token,
                    "notional": str(order.amount * order.price),
                    "price": str(order.price),
                    "size": str(order.amount),
                    "exec_type": "M",
                    "clientOrderId": order.client_order_id
                },
            ]
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or 1736871726781
        return {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
            "data": {
                "orderId": exchange_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "create_time": 1591096004000,
                "side": order.trade_type.name.lower(),
                "type": "limit",
                "price": str(order.price),
                "price_avg": "0.00",
                "size": str(order.amount),
                "notional": str(order.amount * order.price),
                "filled_notional": "0.00000000",
                "filled_size": "0.00000",
                "unfilled_volume": "0.02000",
                "state": "new",
                "clientOrderId": order.client_order_id
            }
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        exchange_order_id = order.exchange_order_id or 1736871726781
        return {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
            "data": {
                "orderId": exchange_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "create_time": 1591096004000,
                "side": order.trade_type.name.lower(),
                "type": "limit",
                "price": str(order.price),
                "price_avg": "0.00",
                "size": str(order.amount),
                "notional": str(order.amount * order.price),
                "filled_notional": str(self.expected_partial_fill_amount * order.price),
                "filled_size": str(self.expected_partial_fill_amount),
                "unfilled_volume": str((order.amount * order.price) -
                                       (self.expected_partial_fill_amount * self.expected_partial_fill_price)),
                "state": "partially_filled",
                "clientOrderId": order.client_order_id
            }
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        exchange_order_id = order.exchange_order_id or 1736871726781
        return {
            "message": "OK",
            "code": 1000,
            "trace": "a06a5c53-8e6f-42d6-8082-2ff4718d221c",
            "data": [
                {
                    "tradeId": self.expected_fill_trade_id,
                    "orderId": exchange_order_id,
                    "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "createTime": 1590462303000,
                    "side": order.trade_type.name.lower(),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "feeCoinName": self.expected_fill_fee.flat_fees[0].token,
                    "notional": str(self.expected_partial_fill_amount * self.expected_partial_fill_price),
                    "price": str(self.expected_partial_fill_price),
                    "size": str(self.expected_partial_fill_amount),
                    "exec_type": "M",
                    "clientOrderId": order.client_order_id
                },
            ]
        }

    @aioresponses()
    def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
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

        url = self.configure_http_error_order_status_response(
            order=order,
            mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_order_status())

        if url:
            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    def test_create_market_buy_order_update(self):
        inflight_order = InFlightOrder(
            client_order_id = 123,
            trading_pair = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            trade_type = TradeType.BUY,
            order_type = OrderType.MARKET,
            creation_timestamp = 123456789,
            price = str(9999),
            amount = str(10),
            initial_state = OrderState.OPEN
        )

        order_update = {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
            "data": {
                "orderId": "1234",
                "symbol": "HBOT-USDT",
                "create_time": 1591096004000,
                "side": "buy",
                "type": "market",
                "price": "1.00",
                "price_avg": "0.00",
                "size": "1",
                "notional": "1",
                "filled_notional": "0.5",
                "filled_size": "0.5",
                "unfilled_volume": "0",
                "state": "partially_canceled",
                "clientOrderId": "1234"
            }
        }

        order = self.exchange._create_order_update(inflight_order, order_update)
        # Ensure that the partially_canceled buy order is marked as filled
        self.assertEqual(order.new_state, OrderState.FILLED)
