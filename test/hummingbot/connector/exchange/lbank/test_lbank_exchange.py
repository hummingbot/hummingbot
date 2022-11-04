import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS, lbank_web_utils as web_utils
from hummingbot.connector.exchange.lbank.lbank_exchange import LbankExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import OrderType


class LbankExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    def setUp(self) -> None:
        self.api_key = "someKey"
        self.api_secret_key = "someSecretKey"
        self.auth_method = "HmacSHA256"
        self.ex_trading_pair = self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)
        super().setUp()

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.LBANK_TRADING_PAIRS_PATH_URL)
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.LBANK_CURRENT_MARKET_DATA_PATH_URL)
        url = f"{url}?symbol={self.base_asset.lower()}_{self.quote_asset.lower()}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.LBANK_GET_TIMESTAMP_PATH_URL)
        return url

    @property
    def trading_rules_url(self):
        return self.all_symbols_url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_ORDER_PATH_URL)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_USER_ASSET_PATH_URL)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "result": True,
            "data": [
                {
                    "symbol": f"{self.base_asset.lower()}_{self.quote_asset.lower()}",
                    "quantityAccuracy": "4",
                    "minTranQua": "0.0001",
                    "priceAccuracy": "2",
                }
            ],
            "error_code": 0,
            "ts": 1655827232443,
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "result": True,
            "data": [{"unrecognized_data_field": "INVALID-PAIR"}],
            "error_code": 0,
            "ts": 1655827232443,
        }
        return "INVALID-PAIR", response

    @property
    def latest_prices_request_mock_response(self):
        return {
            "result": True,
            "data": [
                {
                    "symbol": f"{self.base_asset.lower()}_{self.quote_asset.lower()}",
                    "ticker": {
                        "high": 10000,
                        "vol": 33281.2314,
                        "low": 9998,
                        "change": 2,
                        "turnover": 688968000.92,
                        "latest": self.expected_latest_price,
                    },
                    "timestamp": 1655827019966,
                }
            ],
            "error_code": 0,
            "ts": 1655827021679,
        }

    @property
    def network_status_request_successful_mock_response(self):
        return {"result": True, "data": 1655827102315, "error_code": 0, "ts": 1655827102315}

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        # Missing data fields for Trading Rules
        response = {
            "result": True,
            "data": [{"symbol": f"{self.base_asset.lower()}_{self.quote_asset.lower()}"}],
            "error_code": 0,
            "ts": 1655827232443,
        }
        return response

    @property
    def order_creation_request_successful_mock_response(self):
        return {"result": True, "data": {"order_id": self.expected_exchange_order_id}}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "result": True,
            "data": {
                "freeze": {  # Locked Balance
                    self.base_asset.lower(): 5.0,
                    self.quote_asset.lower(): 0.0
                },
                "asset": {  # Total Balance
                    self.base_asset.lower(): 15.0,
                    self.quote_asset.lower(): 2000.0
                },
                "free": {  # Available Balance
                    self.base_asset.lower(): 10.0,
                    self.quote_asset.lower(): 2000.0
                },
            },
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "result": True,
            "data": {
                "freeze": {  # Locked Balance
                    self.base_asset.lower(): 5.0
                },
                "asset": {  # Total Balance
                    self.base_asset.lower(): 15.0
                },
                "free": {  # Available Balance
                    self.base_asset.lower(): 10.0
                },
            },
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "data": {
                "asset": "15",
                "assetCode": self.base_asset.lower(),
                "free": "10",
                "freeze": "5",
                "time": 1655785565477,
                "type": "ORDER_CREATE",
            },
            "SERVER": "V2",
            "type": "assetUpdate",
            "TS": "2022-06-21T12:26:05.478",
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(self.trading_rules_request_mock_response["data"][0]["minTranQua"]),
            min_base_amount_increment=Decimal(
                f"1e-{self.trading_rules_request_mock_response['data'][0]['quantityAccuracy']}"
            ),
            min_price_increment=Decimal(
                f"1e-{self.trading_rules_request_mock_response['data'][0]['priceAccuracy']}"),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "07b37475-6624-46ba-8668-09cc609e7032"

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            flat_fees=[TokenAmount(token=self.base_asset, amount=Decimal("1e-6"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "TrID1"

    @property
    def is_cancel_request_executed_synchronously_by_server(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return True

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token.lower()}_{quote_token.lower()}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return LbankExchange(
            client_config_map=client_config_map,
            lbank_api_key=self.api_key,
            lbank_secret_key=self.api_secret_key,
            lbank_auth_method=self.auth_method,
            trading_pairs=[self.trading_pair])

    def validate_auth_credentials_present(self, request_call: RequestCall):

        request_headers = request_call.kwargs["headers"]
        request_data = request_call.kwargs["data"]
        self.assertIn("echostr", request_headers)
        self.assertIn("signature_method", request_headers)
        self.assertEqual(self.auth_method, request_headers["signature_method"])
        self.assertIn("timestamp", request_headers)
        self.assertIn("Content-Type", request_headers)
        self.assertEqual("application/x-www-form-urlencoded", request_headers["Content-Type"])
        self.assertIn("sign", request_data)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])

        self.assertIn("sign", request_data)
        self.assertIn("api_key", request_data)
        self.assertEqual(self.api_key, request_data["api_key"])
        self.assertIn("type", request_data)
        self.assertEqual(order.trade_type.name.lower(), request_data["type"])
        self.assertIn("price", request_data)
        self.assertEqual(order.price, Decimal(request_data["price"]))
        self.assertIn("amount", request_data)
        self.assertEqual(order.amount, Decimal(request_data["amount"]))
        self.assertIn("custom_id", request_data)
        self.assertEqual(order.client_order_id, request_data["custom_id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]

        self.assertIn("sign", request_data)
        self.assertIn("api_key", request_data)
        self.assertEqual(self.api_key, request_data["api_key"])
        self.assertIn("symbol", request_data)
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])
        self.assertIn("customer_id", request_data)
        self.assertEqual(order.client_order_id, request_data["customer_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]

        self.assertIn("sign", request_data)
        self.assertIn("api_key", request_data)
        self.assertEqual(self.api_key, request_data["api_key"])
        self.assertIn("symbol", request_data)
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])
        self.assertIn("order_id", request_data)
        self.assertEqual(order.exchange_order_id, request_data["order_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]

        self.assertIn("api_key", request_data)
        self.assertEqual(self.api_key, request_data["api_key"])
        self.assertIn("symbol", request_data)
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])
        self.assertIn("order_id", request_data)
        self.assertEqual(order.exchange_order_id, request_data["order_id"])

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CANCEL_ORDER_PATH_URL)
        response = {"result": True, "data": {"customer_id": order.client_order_id}}
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CANCEL_ORDER_PATH_URL)
        response = {"result": False, "data": {"error": [order.client_order_id]}}
        mock_api.post(url, body=json.dumps(response), callback=callback)
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

    def configure_completely_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_ORDER_UPDATES_PATH_URL)
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_ORDER_UPDATES_PATH_URL)
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_ORDER_UPDATES_PATH_URL)
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_ORDER_UPDATES_PATH_URL)
        mock_api.post(url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_ORDER_UPDATES_PATH_URL)
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_TRADE_UPDATES_PATH_URL)
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_TRADE_UPDATES_PATH_URL)
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_TRADE_UPDATES_PATH_URL)
        mock_api.post(url, status=400, callback=callback)
        return url

    def _configure_balance_response(
        self, response: Dict[str, Any], mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = self.balance_url
        mock_api.post(url, body=json.dumps(response))

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "SERVER": "V2",
            "orderUpdate": {
                "accAmt": "0",
                "amount": "0",
                "avgPrice": "0",
                "customerID": order.client_order_id,
                "orderAmt": str(order.amount),
                "orderPrice": str(order.price),
                "orderStatus": 0,
                "price": "0",
                "remainAmt": str(order.amount),
                "role": "taker",
                "symbol": self.ex_trading_pair,
                "type": "buy",
                "updateTime": 1655785565476,
                "uuid": self.expected_exchange_order_id,
                "volumePrice": "0",
            },
            "type": "orderUpdate",
            "pair": self.ex_trading_pair,
            "TS": "2022-06-21T12:26:05.479",
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "SERVER": "V2",
            "orderUpdate": {
                "accAmt": "0",
                "amount": "0",
                "avgPrice": "0",
                "customerID": order.client_order_id,
                "orderAmt": str(order.amount),
                "orderPrice": str(order.price),
                "orderStatus": -1,
                "price": "0",
                "remainAmt": "0",
                "role": "taker",
                "symbol": self.ex_trading_pair,
                "type": "buy",
                "updateTime": 1655785577941,
                "uuid": self.expected_exchange_order_id,
                "volumePrice": "0",
            },
            "type": "orderUpdate",
            "pair": self.ex_trading_pair,
            "TS": "2022-06-21T12:26:17.943",
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "SERVER": "V2",
            "orderUpdate": {
                "accAmt": str(order.amount),
                "amount": str(order.amount),
                "avgPrice": str(order.price),
                "customerID": order.client_order_id,
                "orderAmt": str(order.amount),
                "orderPrice": str(order.price),
                "orderStatus": 2,
                "price": str(order.price),
                "remainAmt": "0",
                "role": "taker",
                "symbol": self.ex_trading_pair,
                "type": "buy",
                "updateTime": 1655785577941,
                "uuid": self.expected_exchange_order_id,
                "volumePrice": "0",
            },
            "type": "orderUpdate",
            "pair": self.ex_trading_pair,
            "TS": "2022-06-21T12:26:17.943",
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        # NOTE: LBank does not have any trade events over their private stream channels
        return None

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "result": True,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "amount": str(order.amount),
                    "create_time": int(order.creation_timestamp),
                    "price": str(order.price),
                    "avg_price": str(order.price),
                    "type": order.trade_type.name.lower(),
                    "order_id": order.exchange_order_id,
                    "deal_amount": 0,
                    "status": 2
                }
            ],
            "error_code": 0,
            "ts": 1656406392759
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "result": True,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "amount": str(order.amount),
                    "create_time": int(order.creation_timestamp),
                    "price": str(order.price),
                    "avg_price": 0,
                    "type": order.trade_type.name.lower(),
                    "order_id": order.exchange_order_id,
                    "deal_amount": 0,
                    "status": -1
                }
            ],
            "error_code": 0,
            "ts": 1656406392759
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "result": True,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "amount": str(order.amount),
                    "create_time": int(order.creation_timestamp),
                    "price": str(order.price),
                    "avg_price": 0,
                    "type": order.trade_type.name.lower(),
                    "order_id": order.exchange_order_id,
                    "deal_amount": 0,
                    "status": 0
                }
            ],
            "error_code": 0,
            "ts": 1656406392759
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "result": True,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "amount": str(order.amount),
                    "create_time": order.creation_timestamp,
                    "price": str(order.price),
                    "avg_price": str(self.expected_partial_fill_price),
                    "type": order.trade_type.name.lower(),
                    "order_id": order.exchange_order_id,
                    "deal_amount": str(self.expected_partial_fill_amount),
                    "status": 1,
                    "customer_id": order.client_order_id,
                }
            ],
            "error_code": 0,
            "ts": 1656406392759
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "result": True,
            "data": [
                {
                    "txUuid": self.expected_fill_trade_id,
                    "orderUuid": order.exchange_order_id,
                    "tradeType": order.trade_type.name.lower(),
                    "dealTime": 1562553793113,
                    "dealPrice": str(self.expected_partial_fill_price),
                    "dealQuantity": str(self.expected_partial_fill_amount),
                    "dealVolumePrice": str(self.expected_partial_fill_price * self.expected_partial_fill_amount),
                    "tradeFee": 0.0000010000,
                    "tradeFeeRate": 0.000001,
                }
            ],
            "error_code": 0,
            "ts": 1656406325921
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "result": True,
            "data": [
                {
                    "txUuid": self.expected_fill_trade_id,
                    "orderUuid": order.exchange_order_id,
                    "tradeType": order.trade_type.name.lower(),
                    "dealTime": 1562553793113,
                    "dealPrice": str(order.price),
                    "dealQuantity": str(order.amount),
                    "dealVolumePrice": str(order.price * order.amount),
                    "tradeFee": 0.0000010000,
                    "tradeFeeRate": 0.000001,
                }
            ],
            "error_code": 0,
            "ts": 1656406325921
        }
