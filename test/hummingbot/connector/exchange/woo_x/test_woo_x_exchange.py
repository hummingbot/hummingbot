import json
import logging
import re
import secrets
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.woo_x import woo_x_constants as CONSTANTS, woo_x_web_utils as web_utils
from hummingbot.connector.exchange.woo_x.woo_x_exchange import WooXExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase


class WooXExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def latest_prices_url(self):
        params = {
            'symbol': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
        }

        query = ('?' + '&'.join([f"{key}={value}" for key, value in sorted(params.items())])) if len(
            params) != 0 else ''

        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKET_TRADES_PATH, domain=self.exchange._domain) + query

        return url

    @property
    def network_status_url(self):
        raise NotImplementedError

    @property
    def trading_rules_url(self):
        return web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def order_creation_url(self):
        return web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)

    @property
    def balance_url(self):
        return web_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain)

    @property
    def all_symbols_request_mock_response(self):
        return {
            "rows": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "quote_min": 0,
                    "quote_max": 200000,
                    "quote_tick": 0.01,
                    "base_min": 0.00001,
                    "base_max": 300,
                    "base_tick": 0.00000001,
                    "min_notional": 1,
                    "price_range": 0.1,
                    "price_scope": None,
                    "created_time": "1571824137.000",
                    "updated_time": "1686530374.000",
                    "is_stable": 0,
                    "precisions": [
                        1,
                        10,
                        100,
                        500,
                        1000,
                        10000
                    ]
                }
            ],
            "success": True
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "success": True,
            "rows": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "side": "BUY",
                    "source": 0,
                    "executed_price": self.expected_latest_price,
                    "executed_quantity": 0.00025,
                    "executed_timestamp": "1567411795.000"
                }
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        mock_response = self.all_symbols_request_mock_response

        return None, mock_response

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return {
            "rows": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "quote_min": 0,
                    "quote_max": 200000,
                    "quote_tick": 0.01,
                    "base_min": 0.00001,
                    "base_max": 300,
                    "base_tick": 0.00000001,
                    "min_notional": 1,
                    "price_range": 0.1,
                    "price_scope": None,
                    "created_time": "1571824137.000",
                    "updated_time": "1686530374.000",
                    "is_stable": 0,
                    "precisions": [
                        1,
                        10,
                        100,
                        500,
                        1000,
                        10000
                    ]
                }
            ],
            "success": None
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "rows": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "min_notional": 1,
                    "price_range": 0.1,
                    "price_scope": None,
                    "created_time": "1571824137.000",
                    "updated_time": "1686530374.000",
                    "is_stable": 0,
                    "precisions": [
                        1,
                        10,
                        100,
                        500,
                        1000,
                        10000
                    ]
                }
            ],
            "success": None
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "success": True,
            "timestamp": "1686537643.701",
            "order_id": self.expected_exchange_order_id,
            "order_type": "LIMIT",
            "order_price": 20000,
            "order_quantity": 0.001,
            "order_amount": None,
            "client_order_id": 0
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "holding": [{
                "token": self.base_asset,
                "holding": 10,
                "frozen": 5,
                "interest": 0.0,
                "outstanding_holding": -0.00080,
                "pending_exposure": 0.0,
                "opening_cost": -126.36839957,
                "holding_cost": -125.69703515,
                "realised_pnl": 73572.86125165,
                "settled_pnl": 73573.5326161,
                "fee_24_h": 0.01432411,
                "settled_pnl_24_h": 0.67528081,
                "updated_time": "1675220398"
            }, {
                "token": self.quote_asset,
                "holding": 2000,
                "frozen": 0,
                "interest": 0.0,
                "outstanding_holding": -0.00080,
                "pending_exposure": 0.0,
                "opening_cost": -126.36839957,
                "holding_cost": -125.69703515,
                "realised_pnl": 73572.86125165,
                "settled_pnl": 73573.5326161,
                "fee_24_h": 0.01432411,
                "settled_pnl_24_h": 0.67528081,
                "updated_time": "1675220398"
            }],
            "success": True
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "holding": [{
                "token": self.base_asset,
                "holding": 10,
                "frozen": 5,
                "interest": 0.0,
                "outstanding_holding": -0.00080,
                "pending_exposure": 0.0,
                "opening_cost": -126.36839957,
                "holding_cost": -125.69703515,
                "realised_pnl": 73572.86125165,
                "settled_pnl": 73573.5326161,
                "fee_24_h": 0.01432411,
                "settled_pnl_24_h": 0.67528081,
                "updated_time": "1675220398"
            }],
            "success": True
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "topic": "balance",
            "ts": 1686539285351,
            "data": {
                "balances": {
                    self.base_asset: {
                        "holding": 10,
                        "frozen": 5,
                        "interest": 0.0,
                        "pendingShortQty": 0.0,
                        "pendingExposure": 0.0,
                        "pendingLongQty": 0.004,
                        "pendingLongExposure": 0.0,
                        "version": 9,
                        "staked": 0.0,
                        "unbonding": 0.0,
                        "vault": 0.0,
                        "averageOpenPrice": 0.0,
                        "pnl24H": 0.0,
                        "fee24H": 0.00773214,
                        "markPrice": 25772.05,
                        "pnl24HPercentage": 0.0
                    }
                }
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
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(str(self.trading_rules_request_mock_response["rows"][0]["base_min"])),
            min_price_increment=Decimal(str(self.trading_rules_request_mock_response["rows"][0]["quote_tick"])),
            min_base_amount_increment=Decimal(str(self.trading_rules_request_mock_response["rows"][0]['base_tick'])),
            min_notional_size=Decimal(str(self.trading_rules_request_mock_response["rows"][0]["min_notional"]))
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["rows"][0]
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
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"SPOT_{base_token}_{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())

        return WooXExchange(
            client_config_map=client_config_map,
            public_api_key="testAPIKey",
            secret_api_key="testSecret",
            application_id="applicationId",
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(request_call)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])
        self.assertEqual(order.trade_type.name.upper(), request_data["side"])
        self.assertEqual(WooXExchange.woo_x_order_type(OrderType.LIMIT), request_data["order_type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["order_quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["order_price"]))
        self.assertEqual(order.client_order_id, request_data["client_order_id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["params"])

        self.assertEqual(
            self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            request_data["symbol"]
        )

        self.assertEqual(order.client_order_id, request_data["client_order_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        return True
        # request_params = request_call.kwargs["params"]
        #
        #
        # logging.info(f"request params: {request_params}")
        # logging.info(f"request: {request_call}")
        #
        # self.assertEqual(order.exchange_order_id, request_params["order_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        return True

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        params = {
            "client_order_id": order.client_order_id,
            'symbol': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
        }

        query = ('?' + '&'.join([f"{key}={value}" for key, value in sorted(params.items())])) if len(
            params) != 0 else ''

        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL) + query

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self._order_cancelation_request_successful_mock_response(order=order)

        mock_api.delete(regex_url, body=json.dumps(response), callback=callback, repeat=True)

        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        params = {
            "client_order_id": order.client_order_id,
            'symbol': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
        }

        query = ('?' + '&'.join([f"{key}={value}" for key, value in sorted(params.items())])) if len(
            params) != 0 else ''

        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_PATH_URL) + query

        response = {"status": "CANCEL_FAILED"}

        mock_api.delete(url, body=json.dumps(response), callback=callback, repeat=True)

        return url

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2011, "msg": "Unknown order sent."}
        mock_api.delete(regex_url, status=400, body=json.dumps(response), callback=callback)
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
        url = web_utils.public_rest_url(CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(order.client_order_id))

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self._order_status_request_completely_filled_mock_response(order=order)

        mock_api.get(regex_url, body=json.dumps(response), callback=callback, repeat=True)

        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(order.client_order_id))

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self._order_status_request_canceled_mock_response(order=order)

        mock_api.get(regex_url, body=json.dumps(response), callback=callback, repeat=True)

        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(order.client_order_id))

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
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(order.client_order_id))

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self._order_status_request_open_mock_response(order=order)

        mock_api.get(regex_url, body=json.dumps(response), callback=callback, repeat=True)

        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(order.client_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback, repeat=True)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(order.client_order_id))

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self._order_status_request_partially_filled_mock_response(order=order)

        mock_api.get(regex_url, body=json.dumps(response), callback=callback, repeat=True)

        return url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2013, "msg": "Order does not exist."}
        mock_api.get(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(order.client_order_id))

        regex_url = re.compile(url + r"\?.*")

        response = self._order_fills_request_partial_fill_mock_response(order=order)

        mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(order.client_order_id))

        regex_url = re.compile(url + r"\?.*")

        response = self._order_fills_request_full_fill_mock_response(order=order)

        mock_api.get(regex_url, body=json.dumps(response), callback=callback, repeat=True)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "topic": "executionreport",
            "ts": 1686588154387,
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "clientOrderId": int(order.client_order_id),
                "orderId": int(order.exchange_order_id),
                "type": order.order_type.name.upper(),
                "side": order.trade_type.name.upper(),
                "quantity": float(order.amount),
                "price": float(order.price),
                "tradeId": 0,
                "executedPrice": 0.0,
                "executedQuantity": 0.0,
                "fee": 0.0,
                "feeAsset": "BTC",
                "totalExecutedQuantity": 0.0,
                "status": "NEW",
                "reason": "",
                "orderTag": "default",
                "totalFee": 0.0,
                "visible": 0.001,
                "timestamp": 1686588154387,
                "reduceOnly": False,
                "maker": False
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "topic": "executionreport",
            "ts": 1686588270140,
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "clientOrderId": int(order.client_order_id),
                "orderId": int(order.exchange_order_id),
                "type": order.order_type.name.upper(),
                "side": order.trade_type.name.upper(),
                "quantity": float(order.amount),
                "price": float(order.price),
                "tradeId": 0,
                "executedPrice": 0.0,
                "executedQuantity": 0.0,
                "fee": 0.0,
                "feeAsset": "BTC",
                "totalExecutedQuantity": 0.0,
                "status": "CANCELLED",
                "reason": "",
                "orderTag": "default",
                "totalFee": 0.0,
                "visible": 0.001,
                "timestamp": 1686588270140,
                "reduceOnly": False,
                "maker": False
            }
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "topic": "executionreport",
            "ts": 1686588450683,
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "clientOrderId": int(order.client_order_id),
                "orderId": 199270655,
                "type": order.order_type.name.upper(),
                "side": order.trade_type.name.upper(),
                "quantity": float(order.amount),
                "price": float(order.price),
                "tradeId": 250106703,
                "executedPrice": float(order.price),
                "executedQuantity": float(order.amount),
                "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                "feeAsset": self.expected_fill_fee.flat_fees[0].token,
                "totalExecutedQuantity": float(order.amount),
                "avgPrice": float(order.price),
                "status": "FILLED",
                "reason": "",
                "orderTag": "default",
                "totalFee": 0.00000030,
                "visible": 0.001,
                "timestamp": 1686588450683,
                "reduceOnly": False,
                "maker": True
            }
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    @patch("secrets.randbelow")
    def test_client_order_id_on_order(self, mocked_secret):
        mocked_secret.return_value = 10

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )

        expected_client_order_id = str(secrets.randbelow(9223372036854775807))

        logging.error(expected_client_order_id)

        self.assertEqual(result, expected_client_order_id)

        mocked_secret.return_value = 20

        expected_client_order_id = str(secrets.randbelow(9223372036854775807))

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )

        self.assertEqual(result, expected_client_order_id)

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
    def test_check_network_failure(self, mock_api):
        # Disabling this test because Woo X does not have an endpoint to check health.
        pass

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        # Disabling this test because Woo X does not have an endpoint to check health.
        pass

    @aioresponses()
    def test_check_network_success(self, mock_api):
        # Disabling this test because Woo X does not have an endpoint to check health.
        pass

    @aioresponses()
    def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self, mock_api):
        pass

    def _validate_auth_credentials_taking_parameters_from_argument(self, request_call: RequestCall):
        headers = request_call.kwargs["headers"]

        self.assertIn("x-api-key", headers)
        self.assertIn("x-api-signature", headers)
        self.assertIn("x-api-timestamp", headers)

        self.assertEqual("testAPIKey", headers["x-api-key"])

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "success": True,
            "status": "CANCEL_SENT"
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "success": True,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "status": "FILLED",
            "side": "BUY",
            "created_time": "1686558570.495",
            "order_id": int(order.exchange_order_id),
            "order_tag": "default",
            "price": float(order.price),
            "type": "LIMIT",
            "quantity": float(order.amount),
            "amount": None,
            "visible": float(order.amount),
            "executed": float(order.amount),
            "total_fee": 3e-07,
            "fee_asset": "BTC",
            "client_order_id": int(order.client_order_id),
            "reduce_only": False,
            "realized_pnl": None,
            "average_executed_price": 10500,
            "Transactions": [
                {
                    "id": self.expected_fill_trade_id,
                    "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "order_id": int(order.exchange_order_id),
                    "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                    "side": "BUY",
                    "executed_timestamp": "1686558583.434",
                    "executed_price": float(order.price),
                    "executed_quantity": float(order.amount),
                    "fee_asset": self.expected_fill_fee.flat_fees[0].token,
                    "is_maker": 1,
                    "realized_pnl": None
                }
            ]
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "success": True,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "status": "CANCELLED",
            "side": order.trade_type.name.upper(),
            "created_time": "1686558863.782",
            "order_id": int(order.exchange_order_id),
            "order_tag": "default",
            "price": float(order.price),
            "type": order.order_type.name.upper(),
            "quantity": float(order.amount),
            "amount": None,
            "visible": float(order.amount),
            "executed": 0,
            "total_fee": 0,
            "fee_asset": "BTC",
            "client_order_id": int(order.client_order_id),
            "reduce_only": False,
            "realized_pnl": None,
            "average_executed_price": None,
            "Transactions": []
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "success": True,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "status": "NEW",
            "side": order.trade_type.name.upper(),
            "created_time": "1686559699.983",
            "order_id": int(order.exchange_order_id),
            "order_tag": "default",
            "price": float(order.price),
            "type": order.order_type.name.upper(),
            "quantity": float(order.amount),
            "amount": None,
            "visible": float(order.amount),
            "executed": 0,
            "total_fee": 0,
            "fee_asset": "BTC",
            "client_order_id": int(order.client_order_id),
            "reduce_only": False,
            "realized_pnl": None,
            "average_executed_price": None,
            "Transactions": []
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "success": True,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "status": "PARTIAL_FILLED",
            "side": "BUY",
            "created_time": "1686558570.495",
            "order_id": order.exchange_order_id,
            "order_tag": "default",
            "price": float(order.price),
            "type": "LIMIT",
            "quantity": float(order.amount),
            "amount": None,
            "visible": float(order.amount),
            "executed": float(order.amount),
            "total_fee": 3e-07,
            "fee_asset": "BTC",
            "client_order_id": order.client_order_id,
            "reduce_only": False,
            "realized_pnl": None,
            "average_executed_price": 10500,
            "Transactions": [
                {
                    "id": self.expected_fill_trade_id,
                    "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "order_id": int(order.exchange_order_id),
                    "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                    "side": "BUY",
                    "executed_timestamp": "1686558583.434",
                    "executed_price": float(self.expected_partial_fill_price),
                    "executed_quantity": float(self.expected_partial_fill_amount),
                    "fee_asset": self.expected_fill_fee.flat_fees[0].token,
                    "is_maker": 1,
                    "realized_pnl": None
                }
            ]
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "success": True,
            "meta": {
                "total": 65,
                "records_per_page": 100,
                "current_page": 1
            },
            "rows": [
                {
                    "id": self.expected_fill_trade_id,
                    "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                    "side": "BUY",
                    "executed_timestamp": "1686585723.908",
                    "order_id": int(order.exchange_order_id),
                    "order_tag": "default",
                    "executed_price": float(self.expected_partial_fill_price),
                    "executed_quantity": float(self.expected_partial_fill_amount),
                    "fee_asset": self.expected_fill_fee.flat_fees[0].token,
                    "is_maker": 0,
                    "realized_pnl": None
                }
            ]
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "success": True,
            "meta": {
                "total": 65,
                "records_per_page": 100,
                "current_page": 1
            },
            "rows": [
                {
                    "id": self.expected_fill_trade_id,
                    "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                    "side": "BUY",
                    "executed_timestamp": "1686585723.908",
                    "order_id": int(order.exchange_order_id),
                    "order_tag": "default",
                    "executed_price": float(order.price),
                    "executed_quantity": float(order.amount),
                    "fee_asset": self.expected_fill_fee.flat_fees[0].token,
                    "is_maker": 0,
                    "realized_pnl": None
                }
            ]
        }
