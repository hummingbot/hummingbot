import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.exchange.bitget.bitget_constants as CONSTANTS
import hummingbot.connector.exchange.bitget.bitget_web_utils as web_utils
from hummingbot.connector.exchange.bitget.bitget_exchange import BitgetExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class BitgetExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_SYMBOLS_ENDPOINT)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TICKERS_ENDPOINT)
        url = f"{url}?symbol={self.exchange_trading_pair}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PUBLIC_TIME_ENDPOINT)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PUBLIC_SYMBOLS_ENDPOINT)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PLACE_ORDER_ENDPOINT)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ASSETS_ENDPOINT)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1744276707885,
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "baseCoin": self.base_asset,
                    "quoteCoin": self.quote_asset,
                    "minTradeAmount": "0",
                    "maxTradeAmount": "900000000000000000000",
                    "takerFeeRate": str(self.expected_fill_fee.flat_fees[0].amount),
                    "makerFeeRate": str(self.expected_fill_fee.flat_fees[0].amount),
                    "pricePrecision": "2",
                    "quantityPrecision": "6",
                    "quotePrecision": "8",
                    "status": "online",
                    "minTradeUSDT": "1",
                    "buyLimitPriceRatio": "0.05",
                    "sellLimitPriceRatio": "0.05",
                    "areaSymbol": "no",
                    "orderQuantity": "200",
                    "openTime": "1532454360000",
                    "offTime": ""
                }
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "code": "00000",
            "msg": "success",
            "requestTime": 1744276707885,
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "baseCoin": self.base_asset,
                    "quoteCoin": self.quote_asset,
                    "minTradeAmount": "0",
                    "maxTradeAmount": "900000000000000000000",
                    "takerFeeRate": "0.002",
                    "makerFeeRate": "0.002",
                    "pricePrecision": "2",
                    "quantityPrecision": "6",
                    "quotePrecision": "8",
                    "status": "online",
                    "minTradeUSDT": "1",
                    "buyLimitPriceRatio": "0.05",
                    "sellLimitPriceRatio": "0.05",
                    "areaSymbol": "no",
                    "orderQuantity": "200",
                    "openTime": "1532454360000",
                    "offTime": ""
                }
            ]
        }

        return "INVALID-PAIR", response

    @property
    def latest_prices_request_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695808949356,
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "high24h": "37775.65",
                    "open": "35134.2",
                    "low24h": "34413.1",
                    "lastPr": str(self.expected_latest_price),
                    "quoteVolume": "0",
                    "baseVolume": "0",
                    "usdtVolume": "0",
                    "bidPr": "0",
                    "askPr": "0",
                    "bidSz": "0.0663",
                    "askSz": "0.0119",
                    "openUtc": "23856.72",
                    "ts": "1625125755277",
                    "changeUtc24h": "0.00301",
                    "change24h": "0.00069"
                }
            ]
        }

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1688008631614,
            "data": {
                "serverTime": "1688008631614"
            }
        }

    @property
    def trading_rules_request_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1744276707885,
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "baseCoin": self.base_asset,
                    "quoteCoin": self.quote_asset,
                    "minTradeAmount": "0",
                    "maxTradeAmount": "900000000000000000000",
                    "takerFeeRate": "0.002",
                    "makerFeeRate": "0.002",
                    "pricePrecision": "2",
                    "quantityPrecision": "6",
                    "quotePrecision": "8",
                    "status": "online",
                    "minTradeUSDT": "1",
                    "buyLimitPriceRatio": "0.05",
                    "sellLimitPriceRatio": "0.05",
                    "areaSymbol": "no",
                    "orderQuantity": "200",
                    "openTime": "1532454360000",
                    "offTime": ""
                }
            ]
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "code": "00000",
            "data": [
                {
                    "baseCoin": self.base_asset,
                    "quoteCoin": self.quote_asset,
                    "symbol": self.exchange_trading_pair,
                }
            ],
            "msg": "success",
            "requestTime": 1627114525850
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695808949356,
            "data": {
                "orderId": self.expected_exchange_order_id,
                "clientOid": "121211212122"
            }
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "code": "00000",
            "message": "success",
            "requestTime": 1695808949356,
            "data": [
                {
                    "coin": self.base_asset,
                    "available": "10",
                    "frozen": "5",
                    "locked": "0",
                    "limitAvailable": "0",
                    "uTime": "1622697148"
                },
                {
                    "coin": self.quote_asset,
                    "available": "2000",
                    "frozen": "0",
                    "locked": "0",
                    "limitAvailable": "0",
                    "uTime": "1622697148"
                }
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "code": "00000",
            "message": "success",
            "requestTime": 1695808949356,
            "data": [
                {
                    "coin": self.base_asset,
                    "available": "10",
                    "frozen": "5",
                    "locked": "0",
                    "limitAvailable": "0",
                    "uTime": "1622697148"
                }
            ]
        }

    @property
    def expected_fee_details(self) -> str:
        """
        Value for the feeDetails field in the order status update
        """
        details = {
            "BGB": {
                "deduction": True,
                "feeCoinCode": "BGB",
                "totalDeductionFee": -0.0041,
                "totalFee": -0.0041
            },
            "newFees": {
                "c": 0,
                "d": 0,
                "deduction": False,
                "r": -0.112079256,
                "t": -0.112079256,
                "totalDeductionFee": 0
            }
        }
        return json.dumps(details)

    @property
    def balance_event_websocket_update(self):
        return {
            "action": "snapshot",
            "arg": {
                "instType": "SPOT",
                "channel": CONSTANTS.WS_ACCOUNT_ENDPOINT,
                "coin": "default"
            },
            "data": [
                {
                    "coin": self.base_asset,
                    "available": "10",
                    "frozen": "5",
                    "locked": "0",
                    "limitAvailable": "0",
                    "uTime": "1622697148"
                },
                {
                    "coin": self.quote_asset,
                    "available": "2000",
                    "frozen": "0",
                    "locked": "0",
                    "limitAvailable": "0",
                    "uTime": "1622697148"
                }
            ],
            "ts": 1695713887792
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        rule = self.trading_rules_request_mock_response["data"][0]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(f"1e-{rule['quantityPrecision']}"),
            min_price_increment=Decimal(f"1e-{rule['pricePrecision']}"),
            min_base_amount_increment=Decimal(f"1e-{rule['quantityPrecision']}"),
            min_quote_amount_increment=Decimal(f"1e-{rule['quotePrecision']}"),
            min_notional_size=Decimal(rule["minTradeUSDT"]),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "1234567890"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("10500.0")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=None,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return "12345678"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return base_token + quote_token

    def create_exchange_instance(self):
        return BitgetExchange(
            bitget_api_key="test_api_key",
            bitget_secret_key="test_secret_key",
            bitget_passphrase="test_passphrase",
            trading_pairs=[self.trading_pair],
        )

    # validate functions (auth, order creation, order cancellation, order status, trades)
    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_data = request_call.kwargs["headers"]

        self.assertIn("ACCESS-TIMESTAMP", request_data)
        self.assertIn("ACCESS-KEY", request_data)
        self.assertIn("ACCESS-SIGN", request_data)
        self.assertEqual("test_api_key", request_data["ACCESS-KEY"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(
            self.exchange_trading_pair,
            request_data["symbol"]
        )
        self.assertEqual(
            "limit" if order.order_type.is_limit_type() else "market",
            request_data["orderType"]
        )
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(order.amount, Decimal(request_data["size"]))
        if order.order_type.is_limit_type():
            self.assertEqual(order.price, Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["clientOid"])
        self.assertEqual(CONSTANTS.DEFAULT_TIME_IN_FORCE.lower(), request_data["force"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.client_order_id, request_data["clientOid"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.client_order_id, request_params["clientOid"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(str(order.exchange_order_id), request_params["orderId"])
        self.assertEqual(order.trading_pair, request_params["symbol"])

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args,
            **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses
    ) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """
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

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {
            "code": "31007",
            "msg": "Order does not exist",
            "requestTime": 1695808949356,
            "data": None
        }
        mock_api.post(regex_url, body=json.dumps(response), status=400, callback=callback)
        return url

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_INFO_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args,
        **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_INFO_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_INFO_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_INFO_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_INFO_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_INFO_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695808949356,
            "data": []
        }
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_FILLS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_FILLS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_FILLS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "action": "snapshot",
            "arg": {
                "instType": "SPOT",
                "channel": CONSTANTS.WS_FILL_ENDPOINT,
                "instId": self.exchange_trading_pair
            },
            "data": [
                {
                    "tradeId": self.expected_fill_trade_id,
                    "orderId": order.exchange_order_id,
                    "clientOid": order.client_order_id,
                    "symbol": self.exchange_trading_pair,
                    "side": order.trade_type.name.lower(),
                    "priceAvg": str(order.price),
                    "size": str(order.amount),
                    "amount": str(order.amount * order.price),
                    "feeDetail": [
                        {
                            "totalFee": str(self.expected_fill_fee.flat_fees[0].amount),
                            "feeCoin": self.expected_fill_fee.flat_fees[0].token
                        }
                    ],
                    "uTime": int(order.creation_timestamp * 1000)
                }
            ],
            "ts": int(order.creation_timestamp * 1000)
        }

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "action": "snapshot",
            "arg": {
                "instType": "SPOT",
                "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                "instId": self.exchange_trading_pair
            },
            "data": [
                {
                    "instId": self.exchange_trading_pair,
                    "orderId": order.exchange_order_id,
                    "clientOid": order.client_order_id,
                    "size": str(order.amount),
                    "newSize": "0.0000",
                    "notional": "0.000000",
                    "orderType": order.order_type.name.lower(),
                    "force": CONSTANTS.DEFAULT_TIME_IN_FORCE.lower(),
                    "side": order.trade_type.name.lower(),
                    "fillPrice": "0.0",
                    "tradeId": self.expected_fill_trade_id,
                    "baseVolume": "0.0000",
                    "fillTime": "1695797773286",
                    "fillFee": "-0.00000018",
                    "fillFeeCoin": "BTC",
                    "tradeScope": "T",
                    "accBaseVolume": "0.0000",
                    "priceAvg": str(order.price),
                    "status": "live",
                    "cTime": "1695797773257",
                    "uTime": "1695797773326",
                    "stpMode": "cancel_taker",
                    "feeDetail": [
                        {
                            "feeCoin": "BTC",
                            "fee": "-0.00000018"
                        }
                    ],
                    "enterPointSource": "WEB"
                }
            ],
            "ts": 1695797773370
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "action": "snapshot",
            "arg": {
                "instType": "SPOT",
                "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                "instId": self.exchange_trading_pair
            },
            "data": [
                {
                    "instId": self.exchange_trading_pair,
                    "orderId": order.exchange_order_id,
                    "clientOid": order.client_order_id,
                    "size": str(order.amount),
                    "newSize": "0.0000",
                    "notional": "0.000000",
                    "orderType": order.order_type.name.lower(),
                    "force": CONSTANTS.DEFAULT_TIME_IN_FORCE.lower(),
                    "side": order.trade_type.name.lower(),
                    "fillPrice": "0.0",
                    "tradeId": self.expected_fill_trade_id,
                    "baseVolume": "0.0000",
                    "fillTime": "1695797773286",
                    "fillFee": "-0.00000018",
                    "fillFeeCoin": "BTC",
                    "tradeScope": "T",
                    "accBaseVolume": "0.0000",
                    "priceAvg": str(order.price),
                    "status": "cancelled",
                    "cTime": "1695797773257",
                    "uTime": "1695797773326",
                    "stpMode": "cancel_taker",
                    "feeDetail": [
                        {
                            "feeCoin": "BTC",
                            "fee": "-0.00000018"
                        }
                    ],
                    "enterPointSource": "WEB"
                }
            ],
            "ts": 1695797773370
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "action": "snapshot",
            "arg": {
                "instType": "SPOT",
                "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                "instId": self.exchange_trading_pair
            },
            "data": [
                {
                    "instId": self.exchange_trading_pair,
                    "orderId": order.exchange_order_id,
                    "clientOid": order.client_order_id,
                    "size": str(order.amount),
                    "newSize": str(order.amount),
                    "notional": str(order.amount * order.price),
                    "orderType": order.order_type.name.lower(),
                    "force": CONSTANTS.DEFAULT_TIME_IN_FORCE.lower(),
                    "side": order.trade_type.name.lower(),
                    "fillPrice": str(order.price),
                    "tradeId": self.expected_fill_trade_id,
                    "baseVolume": str(order.amount),
                    "fillTime": "1695797773286",
                    "fillFee": "-0.00000018",
                    "fillFeeCoin": "BTC",
                    "tradeScope": "T",
                    "accBaseVolume": "0.0000",
                    "priceAvg": str(order.price),
                    "status": "filled",
                    "cTime": "1695797773257",
                    "uTime": "1695797773326",
                    "stpMode": "cancel_taker",
                    "feeDetail": [
                        {
                            "feeCoin": "BTC",
                            "fee": "-0.00000018"
                        }
                    ],
                    "enterPointSource": "WEB"
                }
            ],
            "ts": 1695797773370
        }

    @aioresponses()
    async def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        pass

    @aioresponses()
    async def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        pass

    @aioresponses()
    async def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        pass

    def _order_cancelation_request_successful_mock_response(
        self, order: InFlightOrder
    ) -> Dict[str, Any]:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1234567891234,
            "data": {
                "orderId": exchange_order_id,
                "clientOid": order.client_order_id
            }
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695808949356,
            "data": [
                {
                    "tradeId": self.expected_fill_trade_id,
                    "orderId": exchange_order_id,
                    "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                    "uTime": "1590462303000",
                    "side": order.trade_type.name.lower(),
                    "feeDetail": [
                        {
                            "totalFee": str(self.expected_fill_fee.flat_fees[0].amount),
                            "feeCoin": self.expected_fill_fee.flat_fees[0].token
                        }
                    ],
                    "priceAvg": str(order.price),
                    "size": str(order.amount),
                    "amount": str(order.amount * order.price),
                    "clientOid": order.client_order_id
                },
            ]
        }

    def _order_fills_request_partial_fill_mock_response(
        self, order: InFlightOrder
    ) -> Dict[str, Any]:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695808949356,
            "data": [
                {
                    "tradeId": self.expected_fill_trade_id,
                    "orderId": exchange_order_id,
                    "symbol": self.exchange_trading_pair,
                    "uTime": "1590462303000",
                    "side": order.trade_type.name.lower(),
                    "feeDetail": [
                        {
                            "totalFee": str(self.expected_fill_fee.flat_fees[0].amount),
                            "feeCoin": self.expected_fill_fee.flat_fees[0].token
                        }
                    ],
                    "priceAvg": str(self.expected_partial_fill_price),
                    "size": str(self.expected_partial_fill_amount),
                    "amount": str(
                        self.expected_partial_fill_amount * self.expected_partial_fill_price
                    ),
                    "clientOid": order.client_order_id
                },
            ]
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695865476577,
            "data": [
                {
                    "userId": "**********",
                    "symbol": self.exchange_trading_pair,
                    "orderId": exchange_order_id,
                    "clientOid": order.client_order_id,
                    "price": str(order.price),
                    "size": str(order.amount),
                    "orderType": order.order_type.name.lower(),
                    "side": order.trade_type.name.lower(),
                    "status": "cancelled",
                    "priceAvg": "13000.0000000000000000",
                    "baseVolume": "0.0007000000000000",
                    "quoteVolume": "9.1000000000000000",
                    "enterPointSource": "API",
                    "feeDetail": self.expected_fee_details,
                    "orderSource": "market",
                    "cancelReason": "",
                    "cTime": "1695865232127",
                    "uTime": "1695865233051"
                }
            ]
        }

    def _order_status_request_completely_filled_mock_response(
        self, order: InFlightOrder
    ) -> Dict[str, Any]:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695865476577,
            "data": [
                {
                    "userId": "**********",
                    "symbol": self.exchange_trading_pair,
                    "orderId": exchange_order_id,
                    "clientOid": order.client_order_id,
                    "price": str(order.price),
                    "size": str(order.amount),
                    "orderType": order.order_type.name.lower(),
                    "side": order.trade_type.name.lower(),
                    "status": "filled",
                    "priceAvg": str(order.price),
                    "baseVolume": str(order.amount),
                    "quoteVolume": str(order.amount * order.price),
                    "enterPointSource": "API",
                    "feeDetail": self.expected_fee_details,
                    "orderSource": "market",
                    "cancelReason": "",
                    "cTime": "1695865232127",
                    "uTime": "1695865233051"
                }
            ]
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695865476577,
            "data": [
                {
                    "userId": "**********",
                    "symbol": self.exchange_trading_pair,
                    "orderId": exchange_order_id,
                    "clientOid": order.client_order_id,
                    "price": str(order.price),
                    "size": str(order.amount),
                    "orderType": order.order_type.name.lower(),
                    "side": order.trade_type.name.lower(),
                    "status": "live",
                    "priceAvg": "0.00",
                    "baseVolume": "0.00",
                    "quoteVolume": "9.00",
                    "enterPointSource": "API",
                    "feeDetail": self.expected_fee_details,
                    "orderSource": "market",
                    "cancelReason": "",
                    "cTime": "1695865232127",
                    "uTime": "1695865233051"
                }
            ]
        }

    def _order_status_request_partially_filled_mock_response(
        self, order: InFlightOrder
    ) -> Dict[str, Any]:
        exchange_order_id = order.exchange_order_id or self.expected_exchange_order_id
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695865476577,
            "data": [
                {
                    "userId": "**********",
                    "symbol": self.exchange_trading_pair,
                    "orderId": exchange_order_id,
                    "clientOid": order.client_order_id,
                    "price": str(order.price),
                    "size": str(order.amount),
                    "orderType": order.order_type.name.lower(),
                    "side": order.trade_type.name.lower(),
                    "status": "partially_filled",
                    "priceAvg": str(self.expected_partial_fill_price),
                    "baseVolume": str(self.expected_partial_fill_amount),
                    "quoteVolume": str(
                        self.expected_partial_fill_amount * self.expected_partial_fill_price
                    ),
                    "enterPointSource": "API",
                    "feeDetail": self.expected_fee_details,
                    "orderSource": "market",
                    "cancelReason": "",
                    "cTime": "1591096004000",
                    "uTime": "1591096004000"
                }
            ]
        }

    def test_create_market_buy_order_update(self) -> None:
        """
        Check the order status update is correctly parsed
        """
        order_id = self.client_order_id_prefix + "1"
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal("1000"),
            amount=Decimal("1"),
            initial_state=OrderState.OPEN
        )
        order: InFlightOrder = self.exchange.in_flight_orders[order_id]
        order_update_response = self._order_status_request_completely_filled_mock_response(
            order=order
        )
        order_update = self.exchange._create_order_update(
            order=order,
            order_update_response=order_update_response
        )
        self.assertEqual(order_update.new_state, OrderState.FILLED)
