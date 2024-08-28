import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.okx import okx_constants as CONSTANTS, okx_web_utils as web_utils
from hummingbot.connector.exchange.okx.okx_exchange import OkxExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import BuyOrderCreatedEvent, OrderCancelledEvent, OrderType, TradeType


class OkxExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_passphrase = "somePassPhrase"
        cls.api_secret_key = "someSecretKey"

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.OKX_INSTRUMENTS_PATH)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.OKX_TICKER_PATH)
        url = f"{url}?instId={self.base_asset}-{self.quote_asset}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        return regex_url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.OKX_SERVER_TIME_PATH)
        return url

    @property
    def trading_rules_url(self):
        return self.all_symbols_url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_PLACE_ORDER_PATH)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_BALANCE_PATH)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "code": "0",
            "data": [
                {
                    "alias": "",
                    "baseCcy": self.base_asset,
                    "category": "1",
                    "ctMult": "",
                    "ctType": "",
                    "ctVal": "",
                    "ctValCcy": "",
                    "expTime": "",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "instType": "SPOT",
                    "lever": "10",
                    "listTime": "1548133413000",
                    "lotSz": "0.00000001",
                    "minSz": "0.00001",
                    "optType": "",
                    "quoteCcy": self.quote_asset,
                    "settleCcy": "",
                    "state": "live",
                    "stk": "",
                    "tickSz": "0.1",
                    "uly": ""
                },
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "code": "0",
            "data": [
                {
                    "alias": "",
                    "baseCcy": "INVALID",
                    "category": "1",
                    "ctMult": "",
                    "ctType": "",
                    "ctVal": "",
                    "ctValCcy": "",
                    "expTime": "",
                    "instId": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "instType": "OPTION",
                    "lever": "10",
                    "listTime": "1548133413000",
                    "lotSz": "0.000001",
                    "minSz": "0.1",
                    "optType": "",
                    "quoteCcy": "PAIR",
                    "settleCcy": "",
                    "state": "live",
                    "stk": "",
                    "tickSz": "0.001",
                    "uly": ""
                },
            ]
        }

        return "INVALID-PAIR", response

    @property
    def latest_prices_request_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.trading_pair,
                    "last": str(self.expected_latest_price),
                    "lastSz": "0.1",
                    "askPx": "9999.99",
                    "askSz": "11",
                    "bidPx": "8888.88",
                    "bidSz": "5",
                    "open24h": "9000",
                    "high24h": "10000",
                    "low24h": "8888.88",
                    "volCcy24h": "2222",
                    "vol24h": "2222",
                    "sodUtc0": "2222",
                    "sodUtc8": "2222",
                    "ts": "1597026383085"
                }
            ]
        }

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "ts": "1597026383085"
                }
            ]
        }

    @property
    def trading_rules_request_mock_response(self):
        response = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "uly": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "category": "1",
                    "baseCcy": self.base_asset,
                    "quoteCcy": self.quote_asset,
                    "settleCcy": "LTC",
                    "ctVal": "10",
                    "ctMult": "1",
                    "ctValCcy": "USD",
                    "optType": "C",
                    "stk": "",
                    "listTime": "1597026383085",
                    "expTime": "1597026383085",
                    "lever": "10",
                    "tickSz": "0.01",
                    "lotSz": "1",
                    "minSz": "1",
                    "ctType": "inverse",
                    "alias": "this_week",
                    "state": "live"
                }
            ]
        }
        return response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        response = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "uly": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "category": "1",
                    "baseCcy": self.base_asset,
                    "quoteCcy": self.quote_asset,
                }
            ]
        }
        return response

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "clOrdId": "oktswap6",
                    "ordId": self.expected_exchange_order_id,
                    "tag": "",
                    "sCode": "0",
                    "sMsg": ""
                }
            ]
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "code": "0",
            "data": [
                {
                    "adjEq": "10679688.0460531643092577",
                    "details": [
                        {
                            "availBal": "10",
                            "availEq": "",
                            "cashBal": "",
                            "ccy": self.base_asset,
                            "crossLiab": "0",
                            "disEq": "9439737.0772999514",
                            "eq": "",
                            "eqUsd": "9933041.196999946",
                            "frozenBal": "5",
                            "interest": "0",
                            "isoEq": "0",
                            "isoLiab": "0",
                            "isoUpl": "0",
                            "liab": "0",
                            "maxLoan": "10000",
                            "mgnRatio": "",
                            "notionalLever": "",
                            "ordFrozen": "0",
                            "twap": "0",
                            "uTime": "1620722938250",
                            "upl": "0",
                            "uplLiab": "0",
                            "stgyEq": "0"
                        },
                        {
                            "availBal": "",
                            "availEq": "2000",
                            "cashBal": "",
                            "ccy": self.quote_asset,
                            "crossLiab": "0",
                            "disEq": "1239950.9687532129092577",
                            "eq": "2000",
                            "eqUsd": "1239950.9687532129092577",
                            "frozenBal": "0.0918492093160816",
                            "interest": "0",
                            "isoEq": "0",
                            "isoLiab": "0",
                            "isoUpl": "0",
                            "liab": "0",
                            "maxLoan": "1453.92289531493594",
                            "mgnRatio": "",
                            "notionalLever": "",
                            "ordFrozen": "0",
                            "twap": "0",
                            "uTime": "1620722938250",
                            "upl": "0.570822125136023",
                            "uplLiab": "0",
                            "stgyEq": "0"
                        }
                    ],
                    "imr": "3372.2942371050594217",
                    "isoEq": "0",
                    "mgnRatio": "70375.35408747017",
                    "mmr": "134.8917694842024",
                    "notionalUsd": "33722.9423710505978888",
                    "ordFroz": "0",
                    "totalEq": "11172992.1657531589092577",
                    "uTime": "1623392334718"
                }
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "code": "0",
            "data": [
                {
                    "adjEq": "10679688.0460531643092577",
                    "details": [
                        {
                            "availBal": "10",
                            "availEq": "",
                            "cashBal": "",
                            "ccy": self.base_asset,
                            "crossLiab": "0",
                            "disEq": "9439737.0772999514",
                            "eq": "",
                            "eqUsd": "9933041.196999946",
                            "frozenBal": "5",
                            "interest": "0",
                            "isoEq": "0",
                            "isoLiab": "0",
                            "isoUpl": "0",
                            "liab": "0",
                            "maxLoan": "10000",
                            "mgnRatio": "",
                            "notionalLever": "",
                            "ordFrozen": "0",
                            "twap": "0",
                            "uTime": "1620722938250",
                            "upl": "0",
                            "uplLiab": "0",
                            "stgyEq": "0"
                        },
                    ],
                    "imr": "3372.2942371050594217",
                    "isoEq": "0",
                    "mgnRatio": "70375.35408747017",
                    "mmr": "134.8917694842024",
                    "notionalUsd": "33722.9423710505978888",
                    "ordFroz": "0",
                    "totalEq": "11172992.1657531589092577",
                    "uTime": "1623392334718"
                }
            ],
            "msg": ""
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "arg": {
                "channel": "account",
                "ccy": "BTC"
            },
            "data": [
                {
                    "uTime": "1597026383085",
                    "totalEq": "41624.32",
                    "isoEq": "3624.32",
                    "adjEq": "41624.32",
                    "ordFroz": "0",
                    "imr": "4162.33",
                    "mmr": "4",
                    "notionalUsd": "",
                    "mgnRatio": "41624.32",
                    "details": [
                        {
                            "availBal": "10",
                            "availEq": "",
                            "ccy": self.base_asset,
                            "cashBal": "",
                            "uTime": "1617279471503",
                            "disEq": "50559.01",
                            "eq": "",
                            "eqUsd": "45078.3790756226851775",
                            "frozenBal": "5",
                            "interest": "0",
                            "isoEq": "0",
                            "liab": "0",
                            "maxLoan": "",
                            "mgnRatio": "",
                            "notionalLever": "0.0022195262185864",
                            "ordFrozen": "0",
                            "upl": "0",
                            "uplLiab": "0",
                            "crossLiab": "0",
                            "isoLiab": "0",
                            "coinUsdPrice": "60000",
                            "stgyEq": "0",
                            "isoUpl": ""
                        }
                    ]
                }
            ]
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
            min_order_size=Decimal(self.trading_rules_request_mock_response["data"][0]["minSz"]),
            min_price_increment=Decimal(self.trading_rules_request_mock_response["data"][0]["tickSz"]),
            min_base_amount_increment=Decimal(self.trading_rules_request_mock_response["data"][0]["lotSz"]),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "312269865356374016"

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
        return "TrID1"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return OkxExchange(
            client_config_map,
            self.api_key,
            self.api_secret_key,
            self.api_passphrase,
            trading_pairs=[self.trading_pair]
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("OK-ACCESS-KEY", request_headers)
        self.assertEqual(self.api_key, request_headers["OK-ACCESS-KEY"])
        self.assertIn("OK-ACCESS-TIMESTAMP", request_headers)
        self.assertIn("OK-ACCESS-SIGN", request_headers)
        self.assertIn("OK-ACCESS-PASSPHRASE", request_headers)
        self.assertEqual(self.api_passphrase, request_headers["OK-ACCESS-PASSPHRASE"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["instId"])
        self.assertEqual("cash", request_data["tdMode"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(order.order_type.name.lower(), request_data["ordType"])
        self.assertEqual(Decimal("100"), Decimal(request_data["sz"]))
        self.assertEqual(order.client_order_id, request_data["clOrdId"])
        if request_data["ordType"] == "market":
            self.assertNotIn("px", request_data)
            self.assertEqual("base_ccy", request_data["tgtCcy"])
        else:
            self.assertEqual(Decimal("10000"), Decimal(request_data["px"]))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["instId"])
        self.assertEqual(order.client_order_id, request_data["clOrdId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["instId"])
        self.assertEqual(order.client_order_id, request_params["clOrdId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual("SPOT", request_params["instType"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["instId"])
        self.assertEqual(order.exchange_order_id, request_params["ordId"])

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            response_scode: int = 0,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_ORDER_CANCEL_PATH)
        response = self._order_cancelation_request_successful_mock_response(response_scode=response_scode, order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_ORDER_CANCEL_PATH)
        response = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "clOrdId": order.client_order_id,
                    "ordId": order.exchange_order_id or "dummyExchangeOrderId",
                    "sCode": "1",
                    "sMsg": "Error"
                }
            ]
        }
        mock_api.post(url, body=json.dumps(response), callback=callback)
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
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_ORDER_DETAILS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_ORDER_DETAILS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_ORDER_DETAILS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_ORDER_DETAILS_PATH)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_ORDER_DETAILS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_TRADE_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_TRADE_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.OKX_TRADE_FILLS_PATH)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "arg": {
                "channel": "orders",
                "uid": "77982378738415879",
                "instType": "SPOT",
                "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset)
            },
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "ccy": "BTC",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "notionalUsd": "",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "cross",
                    "tgtCcy": "",
                    "fillSz": "0",
                    "fillPx": "0",
                    "tradeId": "0",
                    "accFillSz": "323",
                    "fillNotionalUsd": "",
                    "fillTime": "0",
                    "fillFee": "0",
                    "fillFeeCcy": "",
                    "execType": "T",
                    "state": "live",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "0",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "20",
                    "slTriggerPx": "0",
                    "slTriggerPxType": "last",
                    "slOrdPx": "20",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "source": "",
                    "pnl": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085",
                    "reqId": "",
                    "amendResult": "",
                    "code": "0",
                    "msg": ""
                }
            ]
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "arg": {
                "channel": "orders",
                "uid": "77982378738415879",
                "instType": "SPOT",
                "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset)
            },
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "ccy": "BTC",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "notionalUsd": "",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "cross",
                    "tgtCcy": "",
                    "fillSz": "0",
                    "fillPx": "0",
                    "tradeId": "0",
                    "accFillSz": "323",
                    "fillNotionalUsd": "",
                    "fillTime": "0",
                    "fillFee": "0",
                    "fillFeeCcy": "",
                    "execType": "T",
                    "state": "canceled",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "0",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "20",
                    "slTriggerPx": "0",
                    "slTriggerPxType": "last",
                    "slOrdPx": "20",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "source": "",
                    "pnl": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085",
                    "reqId": "",
                    "amendResult": "",
                    "code": "0",
                    "msg": ""
                }
            ]
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "arg": {
                "channel": "orders",
                "uid": "77982378738415879",
                "instType": "SPOT",
                "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset)
            },
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "ccy": "BTC",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "notionalUsd": "",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "cross",
                    "tgtCcy": "",
                    "fillSz": "",
                    "fillPx": "",
                    "tradeId": "",
                    "accFillSz": "323",
                    "fillNotionalUsd": "",
                    "fillTime": "0",
                    "fillFee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "fillFeeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "execType": "T",
                    "state": "filled",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "0",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "20",
                    "slTriggerPx": "0",
                    "slTriggerPxType": "last",
                    "slOrdPx": "20",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "source": "",
                    "pnl": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085",
                    "reqId": "",
                    "amendResult": "",
                    "code": "0",
                    "msg": ""
                }
            ]
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "arg": {
                "channel": "orders",
                "uid": "77982378738415879",
                "instType": "SPOT",
                "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset)
            },
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "ccy": "BTC",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "notionalUsd": "",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "cross",
                    "tgtCcy": "",
                    "fillSz": str(order.amount),
                    "fillPx": str(order.price),
                    "tradeId": self.expected_fill_trade_id,
                    "accFillSz": "323",
                    "fillNotionalUsd": "",
                    "fillTime": "0",
                    "fillFee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "fillFeeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "execType": "T",
                    "state": "filled",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "0",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "20",
                    "slTriggerPx": "0",
                    "slTriggerPxType": "last",
                    "slOrdPx": "20",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "source": "",
                    "pnl": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085",
                    "reqId": "",
                    "amendResult": "",
                    "code": "0",
                    "msg": ""
                }
            ]
        }

    @patch("hummingbot.connector.utils.get_tracking_nonce")
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
            hbot_order_id_prefix=CONSTANTS.CLIENT_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ID_LEN,
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
            hbot_order_id_prefix=CONSTANTS.CLIENT_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError("Error executing request POST https://okx.com/api/v3/order. HTTP status is 401. "
                            'Error: {"code":"50113","msg":"message"}')
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://okx.com/api/v3/order. HTTP status is 401. "
                            'Error: {"code":"50114","msg":"message"}')
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

    def _order_cancelation_request_successful_mock_response(self, response_scode: int, order: InFlightOrder) -> Any:
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "clOrdId": order.client_order_id,
                    "ordId": order.exchange_order_id or "dummyOrdId",
                    "sCode": str(response_scode),
                    "sMsg": ""
                }
            ]
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "ccy": "",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "pnl": "5",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "isolated",
                    "accFillSz": "0",
                    "fillPx": "0",
                    "tradeId": "1",
                    "fillSz": str(order.amount),
                    "fillTime": "0",
                    "state": "filled",
                    "avgPx": str(order.price + Decimal(2)),
                    "lever": "20",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "last",
                    "slOrdPx": "",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085"
                }
            ]
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "ccy": "",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "pnl": "5",
                    "ordType": "limit",
                    "side": order.order_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "isolated",
                    "accFillSz": "0",
                    "fillPx": "0",
                    "tradeId": "1",
                    "fillSz": "0",
                    "fillTime": "0",
                    "state": "canceled",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "last",
                    "slOrdPx": "",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085"
                }
            ]
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "ccy": "",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "pnl": "5",
                    "ordType": "limit",
                    "side": order.order_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "isolated",
                    "accFillSz": "0",
                    "fillPx": "0",
                    "tradeId": "1",
                    "fillSz": "0",
                    "fillTime": "0",
                    "state": "live",
                    "avgPx": "0",
                    "lever": "20",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "last",
                    "slOrdPx": "",
                    "feeCcy": "",
                    "fee": "",
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085"
                }
            ]
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "ccy": "",
                    "ordId": order.exchange_order_id or "EOID1",
                    "clOrdId": order.client_order_id,
                    "tag": "",
                    "px": str(order.price),
                    "sz": str(order.amount),
                    "pnl": "5",
                    "ordType": "limit",
                    "side": order.trade_type.name.lower(),
                    "posSide": "long",
                    "tdMode": "isolated",
                    "accFillSz": "0",
                    "fillPx": str(self.expected_partial_fill_price),
                    "tradeId": "1",
                    "fillSz": str(self.expected_partial_fill_amount),
                    "fillTime": "0",
                    "state": "partially_filled",
                    "avgPx": str(order.price + Decimal(2)),
                    "lever": "20",
                    "tpTriggerPx": "",
                    "tpTriggerPxType": "last",
                    "tpOrdPx": "",
                    "slTriggerPx": "",
                    "slTriggerPxType": "last",
                    "slOrdPx": "",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "rebateCcy": "",
                    "rebate": "",
                    "tgtCcy": "",
                    "category": "",
                    "uTime": "1597026383085",
                    "cTime": "1597026383085"
                }
            ]
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "tradeId": self.expected_fill_trade_id,
                    "ordId": order.exchange_order_id,
                    "clOrdId": order.client_order_id,
                    "billId": "1111",
                    "tag": "",
                    "fillPx": str(self.expected_partial_fill_price),
                    "fillSz": str(self.expected_partial_fill_amount),
                    "side": order.order_type.name.lower(),
                    "posSide": "long",
                    "execType": "M",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "ts": "1597026383085"
                },
            ]
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "tradeId": self.expected_fill_trade_id,
                    "ordId": order.exchange_order_id,
                    "clOrdId": order.client_order_id,
                    "billId": "1111",
                    "tag": "",
                    "fillPx": str(order.price),
                    "fillSz": str(order.amount),
                    "side": order.order_type.name.lower(),
                    "posSide": "long",
                    "execType": "M",
                    "feeCcy": self.expected_fill_fee.flat_fees[0].token,
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "ts": "1597026383085"
                },
            ]
        }

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("11", self.exchange.in_flight_orders)
        order: InFlightOrder = self.exchange.in_flight_orders["11"]

        for response_scode in (0, 51400, 51401):
            url = self.configure_successful_cancelation_response(
                order=order,
                mock_api=mock_api,
                response_scode=response_scode,
                callback=lambda *args, **kwargs: request_sent_event.set())

            self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)
            self.async_run_with_timeout(request_sent_event.wait())

            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

            if self.exchange.is_cancel_request_in_exchange_synchronous:
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
            else:
                self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
                self.assertTrue(order.is_pending_cancel_confirmation)

    @aioresponses()
    def test_create_buy_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_order(order_type=OrderType.MARKET)
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.MARKET, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.MARKET.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} {self.trading_pair} at {Decimal('10000')}."
            )
        )
