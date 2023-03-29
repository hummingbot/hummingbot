import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple, Union

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.phemex_perpetual import (
    phemex_perpetual_constants as CONSTANTS,
    phemex_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_derivative import PhemexPerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class PhemexPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.quote_asset = "USDT"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    @property
    def funding_info_url(self):
        raise NotImplementedError()

    @property
    def funding_payment_url(self):
        raise NotImplementedError()

    @property
    def funding_info_mock_response(self):
        raise NotImplementedError()

    @property
    def empty_funding_payment_mock_response(self):
        raise NotImplementedError()

    @property
    def funding_payment_mock_response(self):
        raise NotImplementedError()

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        raise NotImplementedError()

    def configure_successful_set_position_mode(self, position_mode: PositionMode, mock_api: aioresponses,
                                               callback: Optional[Callable] = lambda *args, **kwargs: None):
        raise NotImplementedError()

    def configure_failed_set_position_mode(self, position_mode: PositionMode, mock_api: aioresponses,
                                           callback: Optional[Callable] = lambda *args, **kwargs: None
                                           ) -> Tuple[str, str]:
        raise NotImplementedError()

    def configure_failed_set_leverage(self, leverage: int, mock_api: aioresponses,
                                      callback: Optional[Callable] = lambda *args, **kwargs: None) -> Tuple[str, str]:
        raise NotImplementedError()

    def configure_successful_set_leverage(self, leverage: int, mock_api: aioresponses,
                                          callback: Optional[Callable] = lambda *args, **kwargs: None):
        raise NotImplementedError()

    def funding_info_event_for_websocket_update(self):
        raise NotImplementedError()

    def test_get_buy_and_sell_collateral_tokens(self):
        raise NotImplementedError()

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL)
        return url

    @property
    def latest_prices_url(self):
        raise NotImplementedError()

    @property
    def network_status_url(self):
        raise NotImplementedError()

    @property
    def trading_rules_url(self):
        raise NotImplementedError()

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PLACE_ORDERS)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_INFO)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "currencies": [
                    {
                        "currency": "BTC",
                        "name": "Bitcoin",
                        "code": 1,
                        "valueScale": 8,
                        "minValueEv": 1,
                        "maxValueEv": 5000000000000000000,
                        "needAddrTag": 0,
                        "status": "Listed",
                        "displayCurrency": "BTC",
                        "inAssetsDisplay": 1,
                        "perpetual": 0,
                        "stableCoin": 0,
                        "assetsPrecision": 8
                    },
                ],
                "products": [
                    {
                        "symbol": "XRPUSD",
                        "code": 21,
                        "type": "Perpetual",
                        "displaySymbol": "XRP / USD",
                        "indexSymbol": ".XRP",
                        "markSymbol": ".MXRP",
                        "fundingRateSymbol": ".XRPFR",
                        "fundingRate8hSymbol": ".XRPFR8H",
                        "contractUnderlyingAssets": "XRP",
                        "settleCurrency": "USD",
                        "quoteCurrency": "USD",
                        "contractSize": 5.0,
                        "lotSize": 1,
                        "tickSize": 1.0E-4,
                        "priceScale": 4,
                        "ratioScale": 8,
                        "pricePrecision": 4,
                        "minPriceEp": 1,
                        "maxPriceEp": 2000000,
                        "maxOrderQty": 500000,
                        "description": ("XRP/USD perpetual contracts are priced on the .XRP Index. Each contract is "
                                        "worth 5 XRP. Funding fees are paid and received every 8 hours at UTC "
                                        "time: 00:00, 08:00 and 16:00."),
                        "status": "Listed",
                        "tipOrderQty": 100000,
                        "listTime": 1574650800000,
                        "majorSymbol": False,
                        "defaultLeverage": "-10",
                        "fundingInterval": 28800,
                        "maxLeverage": 100
                    },
                ],
                "perpProductsV2": [
                    {
                        "symbol": self.exchange_trading_pair,
                        "code": 41641,
                        "type": "PerpetualV2",
                        "displaySymbol": f"{self.base_asset} / {self.quote_asset}",
                        "indexSymbol": f".{self.exchange_trading_pair}",
                        "markSymbol": ".METHUSDT",
                        "fundingRateSymbol": ".ETHUSDTFR",
                        "fundingRate8hSymbol": ".ETHUSDTFR8H",
                        "contractUnderlyingAssets": self.base_asset,
                        "settleCurrency": self.quote_asset,
                        "quoteCurrency": self.quote_asset,
                        "tickSize": "0.01",
                        "priceScale": 0,
                        "ratioScale": 0,
                        "pricePrecision": 2,
                        "baseCurrency": self.base_asset,
                        "description": ("ETH/USDT perpetual contracts are priced on the .ETHUSDT Index. Each contract "
                                        "is worth 1 ETH. Funding fees are paid and received every 8 hours at UTC "
                                        "time: 00:00, 08:00 and 16:00."),
                        "status": "Listed",
                        "tipOrderQty": 0,
                        "listTime": 1668225600000,
                        "majorSymbol": False,
                        "defaultLeverage": "-10",
                        "fundingInterval": 28800,
                        "maxLeverage": 100,
                        "maxOrderQtyRq": "500000",
                        "maxPriceRp": "200000000",
                        "minOrderValueRv": "1",
                        "minPriceRp": "100.0",
                        "qtyPrecision": 2,
                        "qtyStepSize": "0.01",
                        "tipOrderQtyRq": "100000"
                    },
                ],
                "riskLimits": [
                    {
                        "symbol": "BTCUSD",
                        "steps": "50",
                        "riskLimits": [
                            {
                                "limit": 100,
                                "initialMargin": "1.0%",
                                "initialMarginEr": 1000000,
                                "maintenanceMargin": "0.5%",
                                "maintenanceMarginEr": 500000
                            },
                            {
                                "limit": 150,
                                "initialMargin": "1.5%",
                                "initialMarginEr": 1500000,
                                "maintenanceMargin": "1.0%",
                                "maintenanceMarginEr": 1000000
                            },
                            {
                                "limit": 200,
                                "initialMargin": "2.0%",
                                "initialMarginEr": 2000000,
                                "maintenanceMargin": "1.5%",
                                "maintenanceMarginEr": 1500000
                            },
                            {
                                "limit": 250,
                                "initialMargin": "2.5%",
                                "initialMarginEr": 2500000,
                                "maintenanceMargin": "2.0%",
                                "maintenanceMarginEr": 2000000
                            },
                            {
                                "limit": 300,
                                "initialMargin": "3.0%",
                                "initialMarginEr": 3000000,
                                "maintenanceMargin": "2.5%",
                                "maintenanceMarginEr": 2500000
                            },
                            {
                                "limit": 350,
                                "initialMargin": "3.5%",
                                "initialMarginEr": 3500000,
                                "maintenanceMargin": "3.0%",
                                "maintenanceMarginEr": 3000000
                            },
                            {
                                "limit": 400,
                                "initialMargin": "4.0%",
                                "initialMarginEr": 4000000,
                                "maintenanceMargin": "3.5%",
                                "maintenanceMarginEr": 3500000
                            },
                            {
                                "limit": 450,
                                "initialMargin": "4.5%",
                                "initialMarginEr": 4500000,
                                "maintenanceMargin": "4.0%",
                                "maintenanceMarginEr": 4000000
                            },
                            {
                                "limit": 500,
                                "initialMargin": "5.0%",
                                "initialMarginEr": 5000000,
                                "maintenanceMargin": "4.5%",
                                "maintenanceMarginEr": 4500000
                            },
                            {
                                "limit": 550,
                                "initialMargin": "5.5%",
                                "initialMarginEr": 5500000,
                                "maintenanceMargin": "5.0%",
                                "maintenanceMarginEr": 5000000
                            }
                        ]
                    },
                ],
                "riskLimitsV2": [
                    {
                        "symbol": "BTCUSDT",
                        "steps": "2000K",
                        "riskLimits": [
                            {
                                "limit": 2000000,
                                "initialMarginRr": "0.01",
                                "maintenanceMarginRr": "0.005"
                            },
                            {
                                "limit": 4000000,
                                "initialMarginRr": "0.015",
                                "maintenanceMarginRr": "0.0075"
                            },
                            {
                                "limit": 6000000,
                                "initialMarginRr": "0.02",
                                "maintenanceMarginRr": "0.01"
                            },
                            {
                                "limit": 8000000,
                                "initialMarginRr": "0.025",
                                "maintenanceMarginRr": "0.0125"
                            },
                            {
                                "limit": 10000000,
                                "initialMarginRr": "0.03",
                                "maintenanceMarginRr": "0.015"
                            },
                            {
                                "limit": 12000000,
                                "initialMarginRr": "0.035",
                                "maintenanceMarginRr": "0.0175"
                            },
                            {
                                "limit": 14000000,
                                "initialMarginRr": "0.04",
                                "maintenanceMarginRr": "0.02"
                            },
                            {
                                "limit": 16000000,
                                "initialMarginRr": "0.045",
                                "maintenanceMarginRr": "0.0225"
                            },
                            {
                                "limit": 18000000,
                                "initialMarginRr": "0.05",
                                "maintenanceMarginRr": "0.025"
                            },
                            {
                                "limit": 20000000,
                                "initialMarginRr": "0.055",
                                "maintenanceMarginRr": "0.0275"
                            }
                        ]
                    },
                ],
                "ratioScale": 8,
                "md5Checksum": "1c894ae8fa2f98163af663e288752ad4"
            }
        }

    @property
    def latest_prices_request_mock_response(self):
        raise NotImplementedError()

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = self.all_symbols_request_mock_response
        invalid_product = {
            "symbol": "INVALIDPAIR",
            "code": 41641,
            "type": "PerpetualV2",
            "displaySymbol": "INVALID / PAIR",
            "indexSymbol": f".{self.exchange_trading_pair}",
            "markSymbol": ".METHUSDT",
            "fundingRateSymbol": ".ETHUSDTFR",
            "fundingRate8hSymbol": ".ETHUSDTFR8H",
            "contractUnderlyingAssets": "INVALID",
            "settleCurrency": "PAIR",
            "quoteCurrency": "PAIR",
            "tickSize": "0.01",
            "priceScale": 0,
            "ratioScale": 0,
            "pricePrecision": 2,
            "baseCurrency": self.base_asset,
            "description": ("ETH/USDT perpetual contracts are priced on the .ETHUSDT Index. Each contract "
                            "is worth 1 ETH. Funding fees are paid and received every 8 hours at UTC "
                            "time: 00:00, 08:00 and 16:00."),
            "status": "Delisted",
            "tipOrderQty": 0,
            "listTime": 1668225600000,
            "majorSymbol": False,
            "defaultLeverage": "-10",
            "fundingInterval": 28800,
            "maxLeverage": 100,
            "maxOrderQtyRq": "500000",
            "maxPriceRp": "200000000",
            "minOrderValueRv": "1",
            "minPriceRp": "100.0",
            "qtyPrecision": 2,
            "qtyStepSize": "0.01",
            "tipOrderQtyRq": "100000"
        }
        response["data"]["perpProductsV2"].append(invalid_product)

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        raise NotImplementedError()

    @property
    def trading_rules_request_mock_response(self):
        raise NotImplementedError()

    @property
    def trading_rules_request_erroneous_mock_response(self):
        raise NotImplementedError()

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "code": 0,
            "data": {
                "actionTimeNs": 1580547265848034600,
                "bizError": 0,
                "clOrdID": "137e1928-5d25-fecd-dbd1-705ded659a4f",
                "closedPnlRv": "1271.9",
                "closedSizeRq": "0.01",
                "cumQtyRq": "0.01",
                "cumValueRv": "1271.9",
                "displayQtyRq": "0.01",
                "execInst": "ReduceOnly",
                "execStatus": "Init",
                "leavesQtyRq": "0.01",
                "leavesValueRv": "1271.9",
                "ordStatus": "Init",
                "orderID": "ab90a08c-b728-4b6b-97c4-36fa497335bf",
                "orderQtyRq": "0.01",
                "orderType": "Limit",
                "pegOffsetValueRp": "1271.9",
                "pegPriceType": "LastPeg",
                "priceRq": "98970000",
                "reduceOnly": True,
                "side": "Sell",
                "stopDirection": "Rising",
                "stopPxRp": "1271.9",
                "symbol": self.exchange_trading_pair,
                "timeInForce": "GoodTillCancel",
                "transactTimeNs": 0,
                "trigger": "ByMarkPrice"
            },
            "msg": ""
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "account": {
                    "userID": 4724193,
                    "accountId": 47241930003,
                    "currency": "USDT",
                    "accountBalanceRv": "15",
                    "totalUsedBalanceRv": "5",
                    "bonusBalanceRv": "0"},
                "positions": []
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return self.balance_request_mock_response_for_base_and_quote

    @property
    def balance_event_websocket_update(self):
        raise NotImplementedError()

    @property
    def expected_latest_price(self):
        raise NotImplementedError()

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        raise NotImplementedError()

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        raise NotImplementedError()

    @property
    def expected_exchange_order_id(self):
        return "ab90a08c-b728-4b6b-97c4-36fa497335bf"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        raise NotImplementedError()

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("10500")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "5c3d96e1-8874-53b6-b6e5-9dcc4d28b4ab"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = PhemexPerpetualDerivative(
            client_config_map,
            self.api_key,
            self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_data = request_call.kwargs["headers"]

        self.assertIn("x-phemex-request-expiry", request_data)
        self.assertIn("x-phemex-access-token", request_data)
        self.assertEqual(self.api_key, request_data["x-phemex-access-token"])
        self.assertIn("x-phemex-request-signature", request_data)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.client_order_id, request_data["clOrdID"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(order.amount, Decimal(request_data["orderQtyRq"]))
        self.assertEqual(order.order_type.name.capitalize(), request_data["ordType"])
        self.assertEqual(order.price, Decimal(request_data["priceRp"]))
        self.assertEqual(order.trade_type.name.capitalize(), request_data["side"])
        if order.position == PositionAction.OPEN:
            position_side = "Long" if order.trade_type == TradeType.BUY else "Short"
        else:
            position_side = "Short" if order.trade_type == TradeType.BUY else "Long"
        self.assertEqual(position_side, request_data["posSide"])
        self.assertEqual(order.position == PositionAction.CLOSE, request_data["reduceOnly"])
        self.assertEqual(order.position == PositionAction.CLOSE, request_data["closeOnTrigger"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.client_order_id, request_params["clOrdID"])
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual("Long" if order.trade_type == TradeType.BUY else "Short", request_params["posSide"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["clOrdID"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(200, request_params["limit"])
        self.assertIn("start", request_params)

    def configure_successful_cancelation_response(self, order: InFlightOrder, mock_api: aioresponses,
                                                  callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CANCEL_ORDERS)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(self, order: InFlightOrder, mock_api: aioresponses,
                                                 callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CANCEL_ORDERS)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {
            "code": 10003,
            "msg": "OM_ORDER_PENDING_CANCEL",
        }
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CANCEL_ORDERS)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {
            "code": CONSTANTS.ORDER_NOT_FOUND_ERROR_CODE,
            "msg": CONSTANTS.ORDER_NOT_FOUND_ERROR_MESSAGE,
        }
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses
    ) -> List[str]:
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
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> Union[str, List[str]]:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        raise NotImplementedError()

    def configure_partial_fill_trade_response(self, order: InFlightOrder, mock_api: aioresponses,
                                              callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_TRADES)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_TRADES)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(self, order: InFlightOrder, mock_api: aioresponses,
                                           callback: Optional[Callable] = None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_TRADES)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError()

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError()

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError()

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        raise NotImplementedError()

    @aioresponses()
    def test_update_balances(self, mock_api):
        # Phemex only returns balance for the collateral token (USDT in the connector supported markets)

        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("15"), total_balances[self.quote_asset])
        self.assertNotIn(self.base_asset, available_balances)
        self.assertNotIn(self.base_asset, total_balances)

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "data": {
                "actionTimeNs": 450000000,
                "bizError": 0,
                "clOrdID": order.client_order_id,
                "closedPnlRv": "1271.9",
                "closedSizeRq": "0.01",
                "cumQtyRq": "0.01",
                "cumValueRv": "1271.9",
                "displayQtyRq": "0.01",
                "execInst": "ReduceOnly",
                "execStatus": "Init",
                "leavesQtyRq": "0.01",
                "leavesValueRv": "0.01",
                "ordStatus": "Canceled",
                "orderID": order.exchange_order_id,
                "orderQtyRq": str(order.amount),
                "orderType": "Market" if order.order_type == OrderType.MARKET else "Limit",
                "pegOffsetValueRp": "1271.9",
                "pegPriceType": "LastPeg",
                "priceRq": str(order.price),
                "reduceOnly": True,
                "side": order.trade_type.name.capitalize(),
                "stopDirection": "Rising",
                "stopPxRp": "0.01",
                "symbol": self.exchange_trading_pair,
                "timeInForce": "GoodTillCancel",
                "transactTimeNs": 450000000,
                "trigger": "ByMarkPrice"
            },
            "msg": "",
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "msg": "OK",
            "data": {
                "rows": [
                    {
                        "orderId": order.exchange_order_id,
                        "clOrdId": order.client_order_id,
                        "symbol": self.exchange_trading_pair,
                        "side": order.trade_type.name.capitalize(),
                        "ordType": "Market" if order.order_type == OrderType.MARKET else "Limit",
                        "actionTimeNs": 1667562110213260743,
                        "priceRp": str(order.price),
                        "orderQtyRq": str(order.amount),
                        "displayQtyRq": str(order.amount),
                        "timeInForce": "ImmediateOrCancel",
                        "reduceOnly": False,
                        "takeProfitRp": "0",
                        "stopLossRp": "0",
                        "closedPnlRv": "0",
                        "closedSizeRq": "0",
                        "cumQtyRq": "0.001",
                        "cumValueRv": "20.5795",
                        "leavesQtyRq": "0",
                        "leavesValueRv": "0",
                        "stopDirection": "UNSPECIFIED",
                        "ordStatus": "Filled",
                        "transactTimeNs": 1667562110221077395,
                        "bizError": 0
                    }
                ]
            }
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "msg": "OK",
            "data": {
                "rows": [
                    {
                        "orderId": order.exchange_order_id,
                        "clOrdId": order.client_order_id,
                        "symbol": self.exchange_trading_pair,
                        "side": order.trade_type.name.capitalize(),
                        "ordType": "Market" if order.order_type == OrderType.MARKET else "Limit",
                        "actionTimeNs": 1667562110213260743,
                        "priceRp": str(order.price),
                        "orderQtyRq": str(order.amount),
                        "displayQtyRq": str(order.amount),
                        "timeInForce": "ImmediateOrCancel",
                        "reduceOnly": False,
                        "takeProfitRp": "0",
                        "stopLossRp": "0",
                        "closedPnlRv": "0",
                        "closedSizeRq": "0",
                        "cumQtyRq": "0.001",
                        "cumValueRv": "20.5795",
                        "leavesQtyRq": "0",
                        "leavesValueRv": "0",
                        "stopDirection": "UNSPECIFIED",
                        "ordStatus": "Canceled",
                        "transactTimeNs": 1667562110221077395,
                        "bizError": 0
                    }
                ]
            }
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "msg": "OK",
            "data": {
                "rows": [
                    {
                        "orderId": order.exchange_order_id,
                        "clOrdId": order.client_order_id,
                        "symbol": self.exchange_trading_pair,
                        "side": order.trade_type.name.capitalize(),
                        "ordType": "Market" if order.order_type == OrderType.MARKET else "Limit",
                        "actionTimeNs": 1667562110213260743,
                        "priceRp": str(order.price),
                        "orderQtyRq": str(order.amount),
                        "displayQtyRq": str(order.amount),
                        "timeInForce": "ImmediateOrCancel",
                        "reduceOnly": False,
                        "takeProfitRp": "0",
                        "stopLossRp": "0",
                        "closedPnlRv": "0",
                        "closedSizeRq": "0",
                        "cumQtyRq": "0.001",
                        "cumValueRv": "20.5795",
                        "leavesQtyRq": "0",
                        "leavesValueRv": "0",
                        "stopDirection": "UNSPECIFIED",
                        "ordStatus": "New",
                        "transactTimeNs": 1667562110221077395,
                        "bizError": 0
                    }
                ]
            }
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "msg": "OK",
            "data": {
                "rows": [
                    {
                        "orderId": order.exchange_order_id,
                        "clOrdId": order.client_order_id,
                        "symbol": self.exchange_trading_pair,
                        "side": order.trade_type.name.capitalize(),
                        "ordType": "Market" if order.order_type == OrderType.MARKET else "Limit",
                        "actionTimeNs": 1667562110213260743,
                        "priceRp": str(order.price),
                        "orderQtyRq": str(order.amount),
                        "displayQtyRq": str(order.amount),
                        "timeInForce": "ImmediateOrCancel",
                        "reduceOnly": False,
                        "takeProfitRp": "0",
                        "stopLossRp": "0",
                        "closedPnlRv": "0",
                        "closedSizeRq": "0",
                        "cumQtyRq": str(self.expected_partial_fill_amount),
                        "cumValueRv": str(self.expected_partial_fill_amount * self.expected_partial_fill_price),
                        "leavesQtyRq": str(order.amount - self.expected_partial_fill_amount),
                        "leavesValueRv": str((order.amount * order.price)
                                             - (self.expected_partial_fill_amount * self.expected_partial_fill_price)),
                        "stopDirection": "UNSPECIFIED",
                        "ordStatus": "PartiallyFilled",
                        "transactTimeNs": 1667562110221077395,
                        "bizError": 0
                    }
                ]
            }
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "action": "New",
                "clOrdID": order.client_order_id,
                "closedPnlRv": "0",
                "closedSizeRq": "0",
                "currency": self.quote_asset,
                "execFeeRv": str(self.expected_fill_fee.flat_fees[0].amount),
                "execID": self.expected_fill_trade_id,
                "execPriceRp": str(order.price),
                "execQtyRq": str(order.amount),
                "execStatus": "MakerFill",
                "execValueRv": str(order.amount * order.price),
                "feeRateRr": "0.0001",
                "orderID": order.exchange_order_id,
                "orderQtyRq": str(order.amount),
                "ordType": "LimitIfTouched",
                "priceRp": str(order.price),
                "side": order.trade_type.name.capitalize(),
                "symbol": self.exchange_trading_pair,
                "tradeType": "Trade",
                "transactTimeNs": 1669407633926215067
            }
        ]

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "action": "New",
                "clOrdID": order.client_order_id,
                "closedPnlRv": "0",
                "closedSizeRq": "0",
                "currency": self.quote_asset,
                "execFeeRv": str(self.expected_fill_fee.flat_fees[0].amount),
                "execID": self.expected_fill_trade_id,
                "execPriceRp": str(self.expected_partial_fill_price),
                "execQtyRq": str(self.expected_partial_fill_amount),
                "execStatus": "MakerFill",
                "execValueRv": str(self.expected_partial_fill_amount * self.expected_partial_fill_price),
                "feeRateRr": "0.0001",
                "orderID": order.exchange_order_id,
                "orderQtyRq": str(order.amount),
                "ordType": "LimitIfTouched",
                "priceRp": str(order.price),
                "side": order.trade_type.name.capitalize(),
                "symbol": self.exchange_trading_pair,
                "tradeType": "Trade",
                "transactTimeNs": 1669407633926215067
            }
        ]
