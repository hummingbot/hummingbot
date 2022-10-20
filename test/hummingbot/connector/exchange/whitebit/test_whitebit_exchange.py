import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.whitebit import whitebit_constants as CONSTANTS, whitebit_web_utils as web_utils
from hummingbot.connector.exchange.whitebit.whitebit_exchange import WhitebitExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class WhitebitExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.WHITEBIT_INSTRUMENTS_PATH)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.WHITEBIT_TICKER_PATH)
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.WHITEBIT_SERVER_STATUS_PATH)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.WHITEBIT_INSTRUMENTS_PATH)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_CREATION_PATH)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_BALANCE_PATH)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "success": True,
            "message": None,
            "result": [
                {
                    "name": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "stock": self.base_asset,
                    "money": self.quote_asset,
                    "stockPrec": "3",
                    "moneyPrec": "2",
                    "feePrec": "4",
                    "makerFee": "0.001",
                    "takerFee": "0.001",
                    "minAmount": "0.001",
                    "minTotal": "0.001",
                    "tradesEnabled": True,
                }
            ],
        }

    @property
    def latest_prices_request_mock_response(self):
        exchange_trading_pair = self.exchange_symbol_for_tokens(
            base_token=self.base_asset, quote_token=self.quote_asset
        )
        return {
            exchange_trading_pair: {
                "base_id": 1,
                "quote_id": 825,
                "last_price": str(self.expected_latest_price),
                "quote_volume": "43341942.90416876",
                "base_volume": "4723.286463",
                "isFrozen": False,
                "change": "0.57",
            },
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "success": True,
            "message": None,
            "result": [
                {
                    "name": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "stock": self.base_asset,
                    "money": self.quote_asset,
                    "stockPrec": "3",
                    "moneyPrec": "2",
                    "feePrec": "4",
                    "makerFee": "0.001",
                    "takerFee": "0.001",
                    "minAmount": "0.001",
                    "minTotal": "0.001",
                    "tradesEnabled": True,
                },
                {
                    "name": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "stock": "INVALID",
                    "money": "PAIR",
                    "stockPrec": "3",
                    "moneyPrec": "2",
                    "feePrec": "4",
                    "makerFee": "0.001",
                    "takerFee": "0.001",
                    "minAmount": "0.001",
                    "minTotal": "0.001",
                    "tradesEnabled": False,
                },
            ],
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return ["pong"]

    @property
    def trading_rules_request_mock_response(self):
        response = {
            "success": True,
            "message": None,
            "result": [
                {
                    "name": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "stock": self.base_asset,
                    "money": self.quote_asset,
                    "stockPrec": "3",
                    "moneyPrec": "2",
                    "feePrec": "4",
                    "makerFee": "0.001",
                    "takerFee": "0.001",
                    "minAmount": "0.001",
                    "minTotal": "0.001",
                    "tradesEnabled": True,
                }
            ],
        }
        return response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        response = {
            "success": True,
            "message": None,
            "result": [
                {
                    "name": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "stock": self.base_asset,
                    "money": self.quote_asset,
                    "tradesEnabled": True,
                }
            ],
        }
        return response

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "orderId": self.expected_exchange_order_id,
            "clientOrderId": "OID1",
            "market": self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset),
            "side": "buy",
            "type": "limit",
            "timestamp": 1595792396.165973,
            "dealMoney": "0",
            "dealStock": "0",
            "amount": "1",
            "takerFee": "0.001",
            "makerFee": "0.001",
            "left": "1",
            "dealFee": "0",
            "price": "10000",
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            self.base_asset: {"available": "10", "freeze": "5"},
            self.quote_asset: {"available": "2000", "freeze": "0"},
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            self.base_asset: {"available": "10", "freeze": "5"},
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "id": None,
            "method": CONSTANTS.WHITEBIT_WS_PRIVATE_BALANCE_CHANNEL,
            "params": [
                {self.base_asset: {"available": "10", "freeze": "5"}},
            ],
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(self.trading_rules_request_mock_response["result"][0]["minAmount"]),
            min_order_value=Decimal(self.trading_rules_request_mock_response["result"][0]["minTotal"]),
            max_price_significant_digits=Decimal(self.trading_rules_request_mock_response["result"][0]["moneyPrec"]),
            min_base_amount_increment=(
                Decimal(1)
                / (Decimal(10) ** Decimal(str(self.trading_rules_request_mock_response["result"][0]["stockPrec"])))
            ),
            min_quote_amount_increment=(
                Decimal(1)
                / (Decimal(10) ** Decimal(str(self.trading_rules_request_mock_response["result"][0]["moneyPrec"])))
            ),
            min_price_increment=(
                Decimal(1)
                / (Decimal(10) ** Decimal(str(self.trading_rules_request_mock_response["result"][0]["moneyPrec"])))
            ),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["result"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 4180284841

    @property
    def is_cancel_request_executed_synchronously_by_server(self) -> bool:
        return True

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
            percent_token=self.quote_asset, flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "21"

    @property
    def exchange_order_id(self) -> str:
        return "4986126152"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = WhitebitExchange(
            client_config_map=client_config_map,
            whitebit_api_key=self.api_key,
            whitebit_secret_key=self.api_secret_key,
            trading_pairs=[self.trading_pair],
        )
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("X-TXC-APIKEY", request_headers)
        self.assertEqual(self.api_key, request_headers["X-TXC-APIKEY"])
        self.assertIn("X-TXC-PAYLOAD", request_headers)
        self.assertIn("X-TXC-SIGNATURE", request_headers)

        data = json.loads(request_call.kwargs["data"])
        self.assertIn("request", data)
        self.assertTrue(data["request"].startswith("/api/"))
        self.assertIn("nonce", data)
        self.assertTrue(data["nonceWindow"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["market"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(order.amount, Decimal(request_data["amount"]))
        self.assertEqual(order.price, Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["clientOrderId"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["market"])
        self.assertEqual(int(order.exchange_order_id), request_data["orderId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        endpoint = request_data["request"]

        if endpoint == f"/{CONSTANTS.WHITEBIT_ACTIVE_ORDER_STATUS_PATH}":
            self.assertEqual(order.client_order_id, request_data["clientOrderId"])
            self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["market"])
        elif endpoint == f"/{CONSTANTS.WHITEBIT_EXECUTED_ORDER_STATUS_PATH}":
            self.assertEqual(str(order.exchange_order_id), request_data["orderId"])
        else:
            self.fail()

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(int(order.exchange_order_id), request_data["orderId"])

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_CANCEL_PATH)
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_CANCEL_PATH)
        response = {"code": 0, "message": "Validation failed", "errors": {"market": ["Market is not available"]}}
        mock_api.post(url, body=json.dumps(response), status=422, callback=callback)
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
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ACTIVE_ORDER_STATUS_PATH)
        regex_url = re.compile(url)
        response = []
        mock_api.post(regex_url, body=json.dumps(response))
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_EXECUTED_ORDER_STATUS_PATH)
        regex_url = re.compile(url)
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        # WhiteBit does not provide HTTP updates for canceled orders
        pass

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_EXECUTED_ORDER_STATUS_PATH)
        regex_url = re.compile(url)
        response = []
        mock_api.post(regex_url, body=json.dumps(response))
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ACTIVE_ORDER_STATUS_PATH)
        regex_url = re.compile(url)
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_EXECUTED_ORDER_STATUS_PATH)
        regex_url = re.compile(url)
        mock_api.post(regex_url, status=404)
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ACTIVE_ORDER_STATUS_PATH)
        regex_url = re.compile(url)
        mock_api.post(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ACTIVE_ORDER_STATUS_PATH)
        regex_url = re.compile(url)
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_EXECUTED_ORDER_STATUS_PATH)
        regex_url = re.compile(url)
        response = []
        mock_api.post(regex_url, body=json.dumps(response))
        return url

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_TRADES_PATH)
        regex_url = re.compile(url)
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_TRADES_PATH)
        regex_url = re.compile(url)
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_TRADES_PATH)
        regex_url = re.compile(url)
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "id": None,
            "method": "ordersPending_update",
            "params": [
                1,  # 1 is for new orders
                {
                    "id": int(order.exchange_order_id) or 621879,
                    "market": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "type": 1,
                    "side": 2,
                    "ctime": 1601475234.656275,
                    "mtime": 1601475266.733574,
                    "price": str(order.price),
                    "amount": str(order.amount),
                    "left": str(order.amount),
                    "deal_stock": "0",
                    "deal_money": "0",
                    "deal_fee": "0",
                    "client_order_id": order.client_order_id,
                },
            ],
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "id": None,
            "method": "ordersPending_update",
            "params": [
                3,  # 3 is both for canceled and executed orders
                {
                    "id": int(order.exchange_order_id) or 621879,
                    "market": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "type": 1,
                    "side": 2,
                    "ctime": 1601475234.656275,
                    "mtime": 1601475266.733574,
                    "price": str(order.price),
                    "amount": str(order.amount),
                    "left": str(order.amount),
                    "deal_stock": "0",
                    "deal_money": "0",
                    "deal_fee": "0",
                    "client_order_id": order.client_order_id,
                },
            ],
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "id": None,
            "method": "ordersPending_update",
            "params": [
                3,  # 3 is both for canceled and executed orders
                {
                    "id": int(order.exchange_order_id) or 621879,
                    "market": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "type": 1,
                    "side": 2,
                    "ctime": 1601475234.656275,
                    "mtime": 1601475266.733574,
                    "price": str(order.price),
                    "amount": str(order.amount),
                    "left": "0",
                    "deal_stock": str(order.amount),
                    "deal_money": str(order.amount * order.price),
                    "deal_fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "client_order_id": order.client_order_id,
                },
            ],
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "id": None,
            "method": "deals_update",
            "params": [
                int(self.expected_fill_trade_id),
                1602770801.015587,
                self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                int(order.exchange_order_id) or 7425988844,
                str(order.price),
                str(order.amount),
                str(self.expected_fill_fee.flat_fees[0].amount),
                order.client_order_id,
            ],
        }

    @aioresponses()
    def test_update_order_status_when_canceled(self, mock_api):
        # WhiteBit does not provide HTTP updates for canceled orders
        pass

    @aioresponses()
    def test_order_fills_error_response_when_no_fills_is_ignored(self, mock_api):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=self.exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_TRADES_PATH)
        regex_url = re.compile(url)

        response = {
            "response": None,
            "status": 422,
            "errors": {"orderId": ["Finished order id 97773367680 not found on your account"]},
            "notification": None,
            "warning": "Finished order id 97773367680 not found on your account",
            "_token": None,
        }
        mock_api.post(regex_url, body=json.dumps(response))

        order_fills = self.async_run_with_timeout(self.exchange._request_order_fills(order=order))

        self.assertEquals(0, len(order_fills))

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": order.exchange_order_id or "dummyExchangeOrderId",
            "clientOrderId": order.client_order_id,
            "market": self.exchange_symbol_for_tokens(base_token=order.base_asset, quote_token=order.quote_asset),
            "side": order.trade_type.name.lower(),
            "type": "limit",
            "timestamp": 1595792396.165973,
            "dealMoney": "0",
            "dealStock": "0",
            "amount": str(order.amount),
            "takerFee": "0.001",
            "makerFee": "0.001",
            "left": str(order.amount),
            "dealFee": "0",
            "price": str(order.price),
            "activation_price": "0",
        }

    def _configure_balance_response(
        self,
        response: Dict[str, Any],
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = self.balance_url
        mock_api.post(
            re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")), body=json.dumps(response), callback=callback
        )
        return url

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder):
        symbol = self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset)
        return {
            symbol: [
                {
                    "amount": str(order.amount),
                    "price": str(order.price),
                    "type": "limit",
                    "id": order.exchange_order_id or 4986126152,
                    "clientOrderId": order.client_order_id,
                    "side": order.trade_type.name.lower(),
                    "ctime": 1597486960.311311,
                    "takerFee": "0.001",
                    "ftime": 1597486960.311332,
                    "makerFee": "0.001",
                    "dealFee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "dealStock": str(order.amount),
                    "dealMoney": str(order.price),
                },
            ]
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "records": [
                {
                    "time": 1593342324.613711,
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "price": str(order.price),
                    "amount": str(order.amount),
                    "id": int(order.exchange_order_id),
                    "dealOrderId": self.expected_fill_trade_id,
                    "clientOrderId": order.client_order_id,
                    "role": 2,
                    "deal": str(order.amount * order.price),
                }
            ],
            "offset": 0,
            "limit": 100,
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": order.exchange_order_id or 3686033640,
            "clientOrderId": order.client_order_id,
            "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": order.trade_type.name.lower(),
            "type": "limit",
            "timestamp": 1594605801.49815,
            "dealMoney": "0",
            "dealStock": "0",
            "amount": str(order.amount),
            "takerFee": "0.001",
            "makerFee": "0.001",
            "left": str(order.amount),
            "dealFee": "0",
            "price": str(order.price),
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": order.exchange_order_id or 3686033640,
            "clientOrderId": order.client_order_id,
            "market": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": order.trade_type.name.lower(),
            "type": "limit",
            "timestamp": 1594605801.49815,
            "dealMoney": str(self.expected_partial_fill_price),
            "dealStock": str(self.expected_partial_fill_amount),
            "amount": str(order.amount),
            "takerFee": "0.001",
            "makerFee": "0.001",
            "left": str(order.amount - self.expected_partial_fill_amount),
            "dealFee": str(self.expected_fill_fee.flat_fees[0].amount),
            "price": str(order.price),
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "records": [
                {
                    "time": 1593342324.613711,
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "price": str(self.expected_partial_fill_price),
                    "amount": str(self.expected_partial_fill_amount),
                    "id": int(order.exchange_order_id),
                    "dealOrderId": self.expected_fill_trade_id,
                    "clientOrderId": order.client_order_id,
                    "role": 2,
                    "deal": str(self.expected_partial_fill_amount * self.expected_partial_fill_price),
                }
            ],
            "offset": 0,
            "limit": 100,
        }
