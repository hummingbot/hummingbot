import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest.mock import patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.htx import htx_constants as CONSTANTS, htx_web_utils as web_utils
from hummingbot.connector.exchange.htx.htx_exchange import HtxExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent


class HtxExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.TRADE_INFO_URL)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.MOST_RECENT_TRADE_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_URL)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.TRADE_INFO_URL)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PLACE_ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_BALANCE_URL)
        url = url.format(self.get_dummy_account_id())
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "status": "ok",
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "online",
                    "bc": "coinalpha",
                    "qc": "hbot",
                    "pp": 4,
                    "ap": 4,
                    "sp": "main",
                    "vp": 8,
                    "minoa": 0.01,
                    "maxoa": 199.0515,
                    "minov": 5,
                    "lominoa": 0.01,
                    "lomaxoa": 199.0515,
                    "lomaxba": 199.0515,
                    "lomaxsa": 199.0515,
                    "smminoa": 0.01,
                    "blmlt": 1.1,
                    "slmgt": 0.9,
                    "smmaxoa": 199.0515,
                    "bmmaxov": 2500,
                    "msormlt": 0.1,
                    "mbormlt": 0.1,
                    "maxov": 2500,
                    "u": "btcusdt",
                    "mfr": 0.035,
                    "ct": "23:55:00",
                    "rt": "00:00:00",
                    "rthr": 4,
                    "in": 16.3568,
                    "at": "enabled",
                    "tags": "etp,nav,holdinglimit,activities",
                }
            ],
            "ts": "1641880897191",
            "full": 1,
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "ch": f"market.{self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}.trade.detail",
            "status": "ok",
            "ts": 1629792192037,
            "tick": {
                "id": 136107843051,
                "ts": 1629792191928,
                "data": [
                    {
                        "id": 136107843051348400221001656,
                        "ts": 1629792191928,
                        "trade-id": 102517374388,
                        "amount": 0.028416,
                        "price": self.expected_latest_price,
                        "direction": "buy",
                    },
                    {
                        "id": 136107843051348400229813302,
                        "ts": 1629792191928,
                        "trade-id": 102517374387,
                        "amount": 0.025794,
                        "price": 49806.0,
                        "direction": "buy",
                    },
                ],
            },
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "status": "ok",
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "online",
                    "bc": self.base_asset.lower(),
                    "qc": self.quote_asset.lower(),
                    "pp": 4,
                    "ap": 4,
                    "sp": "main",
                    "vp": 8,
                    "minoa": 0.01,
                    "maxoa": 199.0515,
                    "minov": 5,
                    "lominoa": 0.01,
                    "lomaxoa": 199.0515,
                    "lomaxba": 199.0515,
                    "lomaxsa": 199.0515,
                    "smminoa": 0.01,
                    "blmlt": 1.1,
                    "slmgt": 0.9,
                    "smmaxoa": 199.0515,
                    "bmmaxov": 2500,
                    "msormlt": 0.1,
                    "mbormlt": 0.1,
                    "maxov": 2500,
                    "u": "btcusdt",
                    "mfr": 0.035,
                    "ct": "23:55:00",
                    "rt": "00:00:00",
                    "rthr": 4,
                    "in": 16.3568,
                    "at": "enabled",
                    "tags": "etp,nav,holdinglimit,activities",
                },
                {
                    "symbol": self.exchange_symbol_for_tokens("invalid", "pair"),
                    "state": "offline",
                    "bc": "invalid",
                    "qc": "pair",
                    "pp": 4,
                    "ap": 4,
                    "sp": "main",
                    "vp": 8,
                    "minoa": 0.01,
                    "maxoa": 199.0515,
                    "minov": 5,
                    "lominoa": 0.01,
                    "lomaxoa": 199.0515,
                    "lomaxba": 199.0515,
                    "lomaxsa": 199.0515,
                    "smminoa": 0.01,
                    "blmlt": 1.1,
                    "slmgt": 0.9,
                    "smmaxoa": 199.0515,
                    "bmmaxov": 2500,
                    "msormlt": 0.1,
                    "mbormlt": 0.1,
                    "maxov": 2500,
                    "u": "btcusdt",
                    "mfr": 0.035,
                    "ct": "23:55:00",
                    "rt": "00:00:00",
                    "rthr": 4,
                    "in": 16.3568,
                    "at": "enabled",
                    "tags": "etp,nav,holdinglimit,activities",
                },
            ],
            "ts": "1641880897191",
            "full": 1,
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return {
            "status": "ok",
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "online",
                    "bc": self.base_asset,
                    "qc": self.quote_asset,
                    "pp": 4,
                    "ap": 4,
                    "sp": "main",
                    "vp": 8,
                    "minoa": 0.01,
                    "maxoa": 199.0515,
                    "minov": 5,
                    "lominoa": 0.01,
                    "lomaxoa": 199.0515,
                    "lomaxba": 199.0515,
                    "lomaxsa": 199.0515,
                    "smminoa": 0.01,
                    "blmlt": 1.1,
                    "slmgt": 0.9,
                    "smmaxoa": 199.0515,
                    "bmmaxov": 2500,
                    "msormlt": 0.1,
                    "mbormlt": 0.1,
                    "maxov": 2500,
                    "u": "btcusdt",
                    "mfr": 0.035,
                    "ct": "23:55:00",
                    "rt": "00:00:00",
                    "rthr": 4,
                    "in": 16.3568,
                    "at": "enabled",
                    "tags": "etp,nav,holdinglimit,activities",
                }
            ],
            "ts": "1565246363776",
            "full": 1,
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "status": "ok",
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "online",
                    "bc": self.base_asset,
                    "qc": self.quote_asset,
                    "pp": 4,
                    "ap": 4,
                    "sp": "main",
                    "vp": 8,
                    "lominoa": 0.01,
                    "lomaxoa": 199.0515,
                    "lomaxba": 199.0515,
                    "lomaxsa": 199.0515,
                    "smminoa": 0.01,
                    "blmlt": 1.1,
                    "slmgt": 0.9,
                    "smmaxoa": 199.0515,
                    "bmmaxov": 2500,
                    "msormlt": 0.1,
                    "mbormlt": 0.1,
                    "maxov": 2500,
                    "u": "btcusdt",
                    "mfr": 0.035,
                    "ct": "23:55:00",
                    "rt": "00:00:00",
                    "rthr": 4,
                    "in": 16.3568,
                    "at": "enabled",
                    "tags": "etp,nav,holdinglimit,activities",
                }
            ],
            "ts": "1565246363776",
            "full": 1,
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {"status": "ok", "data": "356501383558845"}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "status": "ok",
            "data": {
                "id": 1000001,
                "type": "spot",
                "state": "working",
                "list": [
                    {"currency": self.base_asset, "type": "trade", "balance": "10.0", "seq-num": "477"},
                    {"currency": self.quote_asset, "type": "trade", "balance": "2000.0", "seq-num": "477"},
                ],
            },
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "status": "ok",
            "data": {
                "id": 1000001,
                "type": "spot",
                "state": "working",
                "list": [
                    {
                        "currency": self.base_asset.lower(),
                        "type": "trade",
                        "balance": "91.850043797676510303",
                        "seq-num": "477",
                    },
                ],
            },
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "action": "push",
            "ch": "accounts.update#2",
            "data": {
                "currency": "COINALPHA",
                "accountId": 123456,
                "balance": "15.0",
                "available": "10.0",
                "changeType": "transfer",
                "accountType": "trade",
                "seqNum": "86872993928",
                "changeTime": 1568601800000,
            },
        }

    @property
    def expected_latest_price(self):
        return 0.00468

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        price_precision = self.trading_rules_request_mock_response["data"][0]["pp"]
        amount_precision = self.trading_rules_request_mock_response["data"][0]["ap"]
        value_precision = self.trading_rules_request_mock_response["data"][0]["vp"]

        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(self.trading_rules_request_mock_response["data"][0]["minoa"]),
            max_order_size=Decimal(self.trading_rules_request_mock_response["data"][0]["maxoa"]),
            min_price_increment=Decimal(str(10**-price_precision)),
            min_base_amount_increment=Decimal(str(10**-amount_precision)),
            min_quote_amount_increment=Decimal(str(10**-value_precision)),
            min_notional_size=Decimal(self.trading_rules_request_mock_response["data"][0]["minov"]),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 356501383558845

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
            percent_token=self.quote_asset, flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

    @property
    def expected_partial_fill_fee(self) -> TradeFeeBase:
        return self.expected_fill_fee

    @property
    def expected_fill_trade_id(self) -> str:
        return "30000"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token.lower()}{quote_token.lower()}"

    def get_dummy_account_id(self):
        return "100001"

    def create_exchange_instance(self):

        instance = HtxExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap()),
            htx_api_key="testAPIKey",
            htx_secret_key="testSecret",
            trading_pairs=[self.trading_pair],
        )
        instance._account_id = self.get_dummy_account_id()

        return instance

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call, params=request_call.kwargs["params"] or request_call.kwargs["data"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        test_order_type = f"{order.trade_type.name.lower()}-limit"
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])
        self.assertEqual(test_order_type, request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["amount"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["client-order-id"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["params"])
        self.assertEqual(order.exchange_order_id, request_data["order-id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        expected_params_keys = ["AccessKeyId", "SignatureMethod", "SignatureVersion", "Timestamp", "Signature"]
        self.assertEqual(expected_params_keys, list(request_params.keys()))

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        request_data = request_call.kwargs["data"]
        expected_params_keys = ["AccessKeyId", "SignatureMethod", "SignatureVersion", "Timestamp", "Signature"]
        self.assertEqual(expected_params_keys, list(request_params.keys()))
        self.assertIsNone(request_data)

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        url = url.format(order.exchange_order_id)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        url = url.format(order.exchange_order_id)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
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
        url = web_utils.private_rest_url(CONSTANTS.ORDER_DETAIL_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + r"\?.*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> Union[str, List[str]]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_DETAIL_URL).format(order.exchange_order_id)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + r"\?.*")
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return regex_url

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_MATCHES_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.ORDER_DETAIL_URL).format(order.exchange_order_id)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + r"\?.*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_DETAIL_URL).format(order.exchange_order_id)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + r"\?.*")
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_DETAIL_URL).format(order.exchange_order_id)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + r"\?.*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_MATCHES_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_MATCHES_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        test_type = f"{order.trade_type.name.lower()}-limit"
        return {
            "action": "push",
            "ch": f"orders#{self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}",
            "data": {
                "orderSize": str(order.amount),
                "orderCreateTime": 1640780000,
                "accountld": 10001,
                "orderPrice": str(order.price),
                "type": test_type,
                "orderId": order.exchange_order_id,
                "clientOrderId": order.client_order_id,
                "orderSource": "spot-api",
                "orderStatus": "submitted",
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "eventType": "creation",
            },
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        test_type = f"{order.trade_type.name.lower()}-limit"
        return {
            "action": "push",
            "ch": "orders#btcusdt",
            "data": {
                "lastActTime": 1583853475406,
                "remainAmt": str(order.amount),
                "execAmt": "2",
                "orderId": order.exchange_order_id,
                "type": test_type,
                "clientOrderId": order.client_order_id,
                "orderSource": "spot-api",
                "orderPrice": str(order.price),
                "orderSize": str(order.amount),
                "orderStatus": "canceled",
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "eventType": "cancellation",
            },
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        test_type = f"{order.trade_type.name.lower()}-limit"
        return {
            "action": "push",
            "ch": f"orders#{self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}",
            "data": {
                "tradePrice": "10000.0",
                "tradeVolume": "1.0",
                "tradeId": 301,
                "tradeTime": 1583854188883,
                "aggressor": True,
                "remainAmt": "0.0",
                "execAmt": "1.0",
                "orderId": order.exchange_order_id,
                "type": test_type,
                "clientOrderId": order.client_order_id,
                "orderSource": "spot-api",
                "orderPrice": "10000.0",
                "orderSize": "1.0",
                "orderStatus": "filled",
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "eventType": "trade",
            },
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "ch": f"trade.clearing#{self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}#0",
            "data": {
                "eventType": "trade",
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "orderId": int(order.exchange_order_id),
                "tradePrice": str(order.price),
                "tradeVolume": str(order.amount),
                "orderSide": "buy",
                "aggressor": True,
                "tradeId": 919219323232,
                "tradeTime": 998787897878,
                "transactFee": str(self.expected_fill_fee.flat_fees[0].amount),
                "feeDeduct": "0",
                "feeDeductType": "",
                "feeCurrency": self.expected_fill_fee.flat_fees[0].token.lower(),
                "accountId": 9912791,
                "source": "spot-api",
                "orderPrice": str(order.price),
                "orderSize": str(order.amount),
                "clientOrderId": order.client_order_id,
                "orderCreateTime": 998787897878,
                "orderStatus": "filled",
            },
        }

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        seconds_counter_mock.side_effect = [0, 0, 0]
        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"status": "ok", "data": 1640000003000}
        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_time_synchronizer())
        self.assertEqual(response["data"] * 1e-3, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"status": "fail"}
        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_time_synchronizer())
        self.assertTrue(self.is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, exception=asyncio.CancelledError)
        self.assertRaises(
            asyncio.CancelledError, self.async_run_with_timeout, self.exchange._update_time_synchronizer()
        )

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = self.balance_url
        response = self.balance_request_mock_response_for_base_and_quote
        mock_api.get(url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())
        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()
        self.assertEqual(Decimal("10"), available_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("10"), total_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), total_balances[self.quote_asset])

    @aioresponses()
    def test_create_order_fails_if_response_does_not_include_exchange_order_id(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = {"status": "ok", "data": None}

        mock_api.post(
            url, body=json.dumps(creation_response), callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.exchange.buy(
            trading_pair=self.trading_pair, amount=Decimal("100"), order_type=OrderType.LIMIT, price=Decimal("10000")
        )
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "NETWORK",
                f"Error submitting {TradeType.BUY.name.lower()} {OrderType.LIMIT.name} order to "
                f"{self.exchange.name_cap} for {Decimal('100.000000')} {self.trading_pair} {Decimal('10000.0000')}.",
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

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "status": "ok",
            "data": {
                "id": order.exchange_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "account-id": 10001,
                "client-order-id": order.client_order_id,
                "amount": "5.000000000000000000",
                "price": "1.000000000000000000",
                "created-at": 1640780000,
                "type": "buy-limit-maker",
                "field-amount": "0.0",
                "field-cash-amount": "0.0",
                "field-fees": "0.0",
                "finished-at": 0,
                "source": "spot-api",
                "state": "partial-filled",
                "canceled-at": 0,
            },
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "status": "ok",
            "data": {
                "id": order.exchange_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "account-id": 10001,
                "client-order-id": order.client_order_id,
                "amount": "5.000000000000000000",
                "price": "1.000000000000000000",
                "created-at": 1640780000,
                "type": "buy-limit-maker",
                "field-amount": "0.0",
                "field-cash-amount": "0.0",
                "field-fees": "0.0",
                "finished-at": 0,
                "source": "spot-api",
                "state": "submitted",
                "canceled-at": 0,
            },
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "status": "ok",
            "data": {
                "id": order.exchange_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "account-id": 10001,
                "client-order-id": order.client_order_id,
                "amount": "5.000000000000000000",
                "price": "1.000000000000000000",
                "created-at": 1640780000,
                "type": "buy-limit-maker",
                "field-amount": "0.0",
                "field-cash-amount": "0.0",
                "field-fees": "0.0",
                "finished-at": 0,
                "source": "spot-api",
                "state": "canceled",
                "canceled-at": 0,
            },
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "status": "ok",
            "data": {
                "id": 357632718898331,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "account-id": 10001,
                "client-order-id": order.client_order_id,
                "amount": "5.000000000000000000",
                "price": "1.000000000000000000",
                "created-at": 1640780000,
                "type": "buy-limit-maker",
                "field-amount": "0.0",
                "field-cash-amount": "0.0",
                "field-fees": "0.0",
                "finished-at": 0,
                "source": "spot-api",
                "state": "filled",
                "canceled-at": 0,
            },
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "status": "ok",
            "data": order.exchange_order_id,
        }

    def _validate_auth_credentials_taking_parameters_from_argument(
        self, request_call_tuple: RequestCall, params: Dict[str, Any]
    ):
        self.assertIn("Timestamp", params)
        self.assertIn("Signature", params)
        self.assertEqual("testAPIKey", params["AccessKeyId"])

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "status": "ok",
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset),
                    "fee-currency": self.expected_fill_fee.flat_fees[0].token.lower(),
                    "source": "spot-web",
                    "order-id": int(order.exchange_order_id),
                    "price": str(self.expected_partial_fill_price),
                    "created-at": 1629443051839,
                    "role": "taker",
                    "match-id": 5014,
                    "filled-amount": str(self.expected_partial_fill_amount),
                    "filled-fees": str(self.expected_fill_fee.flat_fees[0].amount),
                    "filled-points": "0.1",
                    "fee-deduct-currency": "hbpoint",
                    "fee-deduct-state": "done",
                    "trade-id": int(self.expected_fill_trade_id),
                    "id": 313288753120940,
                    "type": "buy-market",
                }
            ],
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "status": "ok",
            "data": [
                {
                    "symbol": self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset),
                    "fee-currency": self.expected_fill_fee.flat_fees[0].token.lower(),
                    "source": "spot-web",
                    "order-id": int(order.exchange_order_id),
                    "price": str(order.price),
                    "created-at": 1629443051839,
                    "role": "taker",
                    "match-id": 5014,
                    "filled-amount": str(order.amount),
                    "filled-fees": str(self.expected_fill_fee.flat_fees[0].amount),
                    "filled-points": "0.1",
                    "fee-deduct-currency": "hbpoint",
                    "fee-deduct-state": "done",
                    "trade-id": int(self.expected_fill_trade_id),
                    "id": 313288753120940,
                    "type": "buy-market",
                }
            ],
        }
