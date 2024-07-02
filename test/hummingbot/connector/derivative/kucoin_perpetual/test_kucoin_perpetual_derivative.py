import asyncio
import json
import re
from copy import deepcopy
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

import pandas as pd
from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_derivative import KucoinPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class KucoinPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.passphrase = "somePassphrase"
        cls.quote_asset = "USDT"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)
        cls.non_linear_quote_asset = "USD"
        cls.non_linear_trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.non_linear_quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT.format(symbol=self.exchange_trading_pair),
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.SERVER_TIME_PATH_URL)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.CREATE_ORDER_PATH_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.GET_WALLET_BALANCE_PATH_URL.format(currency="USDT"))
        return url

    @property
    def funding_info_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_CONTRACT_INFO_PATH_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_FUNDING_HISTORY_PATH_URL.format(symbol=self.exchange_trading_pair),
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def all_symbols_request_mock_response(self):
        mock_response = {
            "code": "200000",
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "rootSymbol": self.quote_asset,
                    "type": "FFWCSX",
                    "firstOpenDate": 1585555200000,
                    "expireDate": None,
                    "settleDate": None,
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "settleCurrency": self.quote_asset,
                    "maxOrderQty": 1000000,
                    "maxPrice": 1000000.0,
                    "lotSize": 1,
                    "tickSize": 1.0,
                    "indexPriceTickSize": 0.01,
                    "multiplier": 0.001,
                    "initialMargin": 0.01,
                    "maintainMargin": 0.005,
                    "maxRiskLimit": 2000000,
                    "minRiskLimit": 2000000,
                    "riskStep": 1000000,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                    "takerFixFee": 0.0,
                    "makerFixFee": 0.0,
                    "settlementFee": None,
                    "isDeleverage": True,
                    "isQuanto": True,
                    "isInverse": False,
                    "markMethod": "FairPrice",
                    "fairMethod": "FundingRate",
                    "settlementSymbol": "",
                    "status": "Open",
                    "fundingFeeRate": 0.0001,
                    "predictedFundingFeeRate": 0.0001,
                    "openInterest": "5191275",
                    "turnoverOf24h": 2361994501.712677,
                    "volumeOf24h": 56067.116,
                    "markPrice": 44514.03,
                    "indexPrice": 44510.78,
                    "lastTradePrice": 44493.0,
                    "nextFundingRateTime": 21031525,
                    "maxLeverage": 100,
                    "sourceExchanges": [
                        "htx",
                        "Okex",
                        "Binance",
                        "Kucoin",
                        "Poloniex",
                        "Hitbtc"
                    ],
                    "lowPrice": 38040,
                    "highPrice": 44948,
                    "priceChgPct": 0.1702,
                    "priceChg": 6476
                }
            ]
        }
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = {
            "code": "200000",
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "rootSymbol": self.quote_asset,
                    "type": "FFWCSX",
                    "firstOpenDate": 1610697600000,
                    "expireDate": None,
                    "settleDate": None,
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "settleCurrency": self.quote_asset,
                    "maxOrderQty": 1000000,
                    "maxPrice": 1000000.0,
                    "lotSize": 1,
                    "tickSize": 0.01,
                    "indexPriceTickSize": 0.01,
                    "multiplier": 0.01,
                    "initialMargin": 0.05,
                    "maintainMargin": 0.025,
                    "maxRiskLimit": 100000,
                    "minRiskLimit": 100000,
                    "riskStep": 50000,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                    "takerFixFee": 0.0,
                    "makerFixFee": 0.0,
                    "settlementFee": "",
                    "isDeleverage": True,
                    "isQuanto": False,
                    "isInverse": False,
                    "markMethod": "FairPrice",
                    "fairMethod": "FundingRate",
                    "fundingBaseSymbol": self.exchange_trading_pair,
                    "fundingQuoteSymbol": self.exchange_trading_pair,
                    "fundingRateSymbol": self.exchange_trading_pair,
                    "indexSymbol": self.exchange_trading_pair,
                    "settlementSymbol": "",
                    "status": "Open",
                    "fundingFeeRate": 0.0001,
                    "predictedFundingFeeRate": 0.0001,
                    "openInterest": "2487402",
                    "turnoverOf24h": 3166644.36115288,
                    "volumeOf24h": 32299.4,
                    "markPrice": 101.6,
                    "indexPrice": 101.59,
                    "lastTradePrice": str(self.expected_latest_price),
                    "nextFundingRateTime": 22646889,
                    "maxLeverage": 20,
                    "sourceExchanges": [
                        "htx",
                        "Okex",
                        "Binance",
                        "Kucoin",
                        "Poloniex",
                        "Hitbtc"
                    ],
                    "premiumsSymbol1M": self.exchange_trading_pair,
                    "premiumsSymbol8H": self.exchange_trading_pair,
                    "fundingBaseSymbol1M": self.base_asset,
                    "fundingQuoteSymbol1M": self.quote_asset,
                    "lowPrice": 88.88,
                    "highPrice": 102.21,
                    "priceChgPct": 0.1401,
                    "priceChg": 12.48
                }
            ]
        }
        return mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        mock_response = {
            "code": "200000",
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "rootSymbol": self.quote_asset,
                    "type": "FFWCSX",
                    "firstOpenDate": 1585555200000,
                    "expireDate": None,
                    "settleDate": None,
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "settleCurrency": self.quote_asset,
                    "maxOrderQty": 1000000,
                    "maxPrice": 1000000.0,
                    "lotSize": 1,
                    "tickSize": 1.0,
                    "indexPriceTickSize": 0.01,
                    "multiplier": 0.001,
                    "initialMargin": 0.01,
                    "maintainMargin": 0.005,
                    "maxRiskLimit": 2000000,
                    "minRiskLimit": 2000000,
                    "riskStep": 1000000,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                    "takerFixFee": 0.0,
                    "makerFixFee": 0.0,
                    "settlementFee": None,
                    "isDeleverage": True,
                    "isQuanto": True,
                    "isInverse": False,
                    "markMethod": "FairPrice",
                    "fairMethod": "FundingRate",
                    "settlementSymbol": "",
                    "status": "Open",
                    "fundingFeeRate": 0.0001,
                    "predictedFundingFeeRate": 0.0001,
                    "openInterest": "5191275",
                    "turnoverOf24h": 2361994501.712677,
                    "volumeOf24h": 56067.116,
                    "markPrice": 44514.03,
                    "indexPrice": 44510.78,
                    "lastTradePrice": 44493.0,
                    "nextFundingRateTime": 21031525,
                    "maxLeverage": 100,
                    "sourceExchanges": [
                        "htx",
                        "Okex",
                        "Binance",
                        "Kucoin",
                        "Poloniex",
                        "Hitbtc"
                    ],
                    "lowPrice": 38040,
                    "highPrice": 44948,
                    "priceChgPct": 0.1702,
                    "priceChg": 6476
                },
                {
                    "symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "rootSymbol": self.quote_asset,
                    "type": "FFWCSX",
                    "firstOpenDate": 1585555200000,
                    "expireDate": None,
                    "settleDate": None,
                    "baseCurrency": "INVALID",
                    "quoteCurrency": "PAIR",
                    "settleCurrency": "PAIR",
                    "maxOrderQty": 1000000,
                    "maxPrice": 1000000.0,
                    "lotSize": 1,
                    "tickSize": 1.0,
                    "indexPriceTickSize": 0.01,
                    "multiplier": 0.001,
                    "initialMargin": 0.01,
                    "maintainMargin": 0.005,
                    "maxRiskLimit": 2000000,
                    "minRiskLimit": 2000000,
                    "riskStep": 1000000,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                    "takerFixFee": 0.0,
                    "makerFixFee": 0.0,
                    "settlementFee": None,
                    "isDeleverage": True,
                    "isQuanto": True,
                    "isInverse": False,
                    "markMethod": "FairPrice",
                    "fairMethod": "FundingRate",
                    "settlementSymbol": "",
                    "status": "Closed",
                    "fundingFeeRate": 0.0001,
                    "predictedFundingFeeRate": 0.0001,
                    "openInterest": "5191275",
                    "turnoverOf24h": 2361994501.712677,
                    "volumeOf24h": 56067.116,
                    "markPrice": 44514.03,
                    "indexPrice": 44510.78,
                    "lastTradePrice": 44493.0,
                    "nextFundingRateTime": 21031525,
                    "maxLeverage": 100,
                    "sourceExchanges": [
                        "htx",
                        "Okex",
                        "Binance",
                        "Kucoin",
                        "Poloniex",
                        "Hitbtc"
                    ],
                    "lowPrice": 38040,
                    "highPrice": 44948,
                    "priceChgPct": 0.1702,
                    "priceChg": 6476
                },
            ]
        }
        return "INVALID-PAIR", mock_response

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = {
            "code": "200000",
            "data": {
                "status": "open",
                "msg": "upgrade match engine"
            }
        }
        return mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = {
            "code": "200000",
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "rootSymbol": self.quote_asset,
                    "type": "FFWCSX",
                    "firstOpenDate": 1610697600000,
                    "expireDate": None,
                    "settleDate": None,
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "settleCurrency": self.quote_asset,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                }
            ]
        }
        return mock_response

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {
            "code": "200000",
            "data": {
                "orderId": "335fd977-e5a5-4781-b6d0-c772d5bfb95b"
            }
        }
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        mock_response = {
            "code": "200000",
            "data": [{
                    "accountEquity": 15,
                    "unrealisedPNL": 0,
                    "marginBalance": 15,
                    "positionMargin": 0,
                    "orderMargin": 0,
                    "frozenFunds": 0,
                    "availableBalance": 10,
                    "currency": self.base_asset,
            },
                {
                "accountEquity": 2000,
                    "unrealisedPNL": 0,
                    "marginBalance": 2000,
                    "positionMargin": 0,
                    "orderMargin": 0,
                    "frozenFunds": 0,
                    "availableBalance": 2000,
                    "currency": self.quote_asset,
            }
            ]
        }
        return mock_response

    @property
    def balance_request_mock_response_only_base(self):
        mock_response = self.balance_request_mock_response_for_base_and_quote
        del mock_response["data"][1]
        return mock_response

    @property
    def balance_event_websocket_update(self):
        mock_response = {
            "userId": 738713,
            "topic": "/contractAccount/wallet",
            "subject": "availableBalance.change",
            "data": {
                "availableBalance": 10,
                "holdBalance": 15,
                "currency": self.base_asset,
                "timestamp": 1553842862614
            }
        }
        return mock_response

    @property
    def non_linear_balance_event_websocket_update(self):
        return self.balance_event_websocket_update

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def empty_funding_payment_mock_response(self):
        return {
            "code": "200000",
            "dataList": [{}],
        }

    @property
    def funding_payment_mock_response(self):
        return {
            "code": "200000",
            "dataList": [
                {
                    "id": 36275152660006,
                    "symbol": self.exchange_trading_pair,
                    "timePoint": self.target_funding_payment_timestamp_str,
                    "fundingRate": float(self.target_funding_payment_funding_rate),
                    "markPrice": 8058.27,
                    "positionQty": float(self.target_funding_payment_payment_amount / self.target_funding_payment_funding_rate),
                    "positionCost": -0.001241,
                    "funding": -0.00000464,
                    "settleCurrency": self.base_asset,
                }]
        }

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        raise NotImplementedError  # test is overwritten

    @property
    def target_funding_info_next_funding_utc_str(self):
        datetime_str = str(
            pd.Timestamp.utcfromtimestamp(
                self.target_funding_info_next_funding_utc_timestamp)
        ).replace(" ", "T") + "Z"
        return datetime_str

    @property
    def target_funding_info_next_funding_utc_str_ws_updated(self):
        datetime_str = str(
            pd.Timestamp.utcfromtimestamp(
                self.target_funding_info_next_funding_utc_timestamp_ws_updated)
        ).replace(" ", "T") + "Z"
        return datetime_str

    @property
    def target_funding_payment_timestamp_str(self):
        datetime_str = str(
            pd.Timestamp.utcfromtimestamp(
                self.target_funding_payment_timestamp)
        ).replace(" ", "T") + "Z"
        return datetime_str

    @property
    def funding_info_mock_response(self):
        mock_response = self.latest_prices_request_mock_response
        funding_info = mock_response["data"][0]
        funding_info["indexPrice"] = self.target_funding_info_index_price
        funding_info["markPrice"] = self.target_funding_info_mark_price
        funding_info["nextFundingRateTime"] = self.target_funding_info_next_funding_utc_str
        funding_info["predictedFundingFeeRate"] = self.target_funding_info_rate
        return mock_response

    @property
    def get_predicted_funding_info(self):
        return self.latest_prices_request_mock_response

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        trading_rules_resp = self.trading_rules_request_mock_response["data"][0]
        multiplier = Decimal(str(trading_rules_resp["multiplier"]))
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(str(trading_rules_resp["lotSize"])) * multiplier,
            max_order_size=Decimal(str(trading_rules_resp["maxOrderQty"])) * multiplier,
            min_price_increment=Decimal(str(trading_rules_resp["tickSize"])),
            min_base_amount_increment=multiplier,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing the trading pair rule: {erroneous_rule}. Skipping..."

    @property
    def expected_exchange_order_id(self):
        return "335fd977-e5a5-4781-b6d0-c772d5bfb95b"

    @property
    def is_cancel_request_executed_synchronously_by_server(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("100")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("10")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent=Decimal('0.0002'),
            percent_token=self.quote_asset,
        )

    @property
    def expected_trade_history_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent=Decimal('0'),
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(amount=Decimal('0.0002'), token=self.quote_asset)]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6"

    @property
    def latest_trade_hist_timestamp(self) -> int:
        return 1234

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = KucoinPerpetualDerivative(
            client_config_map,
            self.api_key,
            self.api_secret,
            self.passphrase,
            trading_pairs=[self.trading_pair],
        )
        exchange._last_trade_history_timestamp = self.latest_trade_hist_timestamp
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertEqual("application/json", request_headers["Content-Type"])

        self.assertIn("KC-API-TIMESTAMP", request_headers)
        self.assertIn("KC-API-KEY", request_headers)
        self.assertEqual(self.api_key, request_headers["KC-API-KEY"])
        self.assertIn("KC-API-SIGN", request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(order.amount, request_data["size"] * 1e-6)
        self.assertEqual(CONSTANTS.DEFAULT_TIME_IN_FORCE, request_data["timeInForce"])
        self.assertEqual(order.client_order_id, request_data["clientOid"])
        self.assertIn("clientOid", request_data)
        self.assertEqual(order.order_type.name.lower(), request_data["type"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.exchange_order_id, request_data["order_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        request_data = request_call.kwargs["data"]
        self.assertIsNone(request_params)
        self.assertIsNone(request_data)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(self.latest_trade_hist_timestamp * 1e3, request_params["start_time"])

    def configure_successful_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        """
        :return: the URL configured for the cancelation
        """
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.CANCEL_ORDER_PATH_URL.format(orderid=order.exchange_order_id)
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.CANCEL_ORDER_PATH_URL.format(orderid=order.exchange_order_id)
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {
            "code": str(CONSTANTS.RET_CODE_PARAMS_ERROR),
            "msg": "Order does not exist",
        }
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses,
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
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_ORDER_BY_EXCHANGE_ORDER_ID_PATH_URL.format(orderid=order.exchange_order_id))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ORDER_BY_EXCHANGE_ORDER_ID_PATH_URL.format(orderid=order.exchange_order_id)
        )
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ORDER_BY_EXCHANGE_ORDER_ID_PATH_URL.format(orderid=order.exchange_order_id)
        )
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ORDER_BY_EXCHANGE_ORDER_ID_PATH_URL.format(orderid=order.exchange_order_id)
        )
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ORDER_BY_EXCHANGE_ORDER_ID_PATH_URL.format(orderid=order.exchange_order_id)
        )
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ALL_ORDER_PATH_URL, exchange_order_id=order.exchange_order_id
        )
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_FILL_INFO_PATH_URL.format(orderid=order.exchange_order_id),
        )
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_fill_history_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_RECENT_FILLS_INFO_PATH_URL,
        )
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.ACTIVE_ORDER_PATH_URL, exchange_order_id=order.exchange_order_id
        )
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_successful_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.SET_LEVERAGE_PATH_URL
        )
        response = {
            "code": "200000",
            "data": True
        }
        mock_api.post(url, body=json.dumps(response), callback=callback)

        return url

    def configure_failed_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.SET_LEVERAGE_PATH_URL
        )
        error_code = "300016"
        error_msg = "Some problem"
        response = {
            "code": "300016",
            "data": False
        }
        mock_api.post(url, body=json.dumps(response), callback=callback)

        return url, f"ret_code <{error_code}> - {error_msg}"

    def configure_failed_set_leverage(
        self,
        leverage: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_RISK_LIMIT_LEVEL_PATH_URL.format(symbol=self.exchange_trading_pair)
        )
        regex_url = re.compile(f"^{url}")

        error_code = "300016"
        error_msg = "Some problem"
        mock_response = {
            "code": "300016",
            "data": [
                {
                    "symbol": "ADAUSDTM",
                    "level": 1,
                    "maxRiskLimit": 500,
                    "minRiskLimit": 0,
                    "maxLeverage": 1,
                    "initialMargin": 0.05,
                    "maintainMargin": 0.025
                },
                {
                    "symbol": "ADAUSDTM",
                    "level": 2,
                    "maxRiskLimit": 1000,
                    "minRiskLimit": 500,
                    "maxLeverage": 1,
                    "initialMargin": 0.5,
                    "maintainMargin": 0.25
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(mock_response), callback=callback)

        return url, f"ret_code <{error_code}> - {error_msg}"

    def configure_successful_set_leverage(
        self,
        leverage: int,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_RISK_LIMIT_LEVEL_PATH_URL.format(symbol=self.exchange_trading_pair)
        )
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "code": "200000",
            "data": [
                {
                    "symbol": "ADAUSDTM",
                    "level": 1,
                    "maxRiskLimit": 500,
                    "minRiskLimit": 0,
                    "maxLeverage": 20,
                    "initialMargin": 0.05,
                    "maintainMargin": 0.025
                },
                {
                    "symbol": "ADAUSDTM",
                    "level": 2,
                    "maxRiskLimit": 1000,
                    "minRiskLimit": 500,
                    "maxLeverage": 2,
                    "initialMargin": 0.5,
                    "maintainMargin": 0.25
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": "message",
            "topic": "/contractMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {
                "orderId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                "symbol": self.exchange_trading_pair,
                "type": "open",
                "status": "open",
                "orderType": order.order_type.name.lower(),
                "side": order.trade_type.name.lower(),
                "price": str(order.price),
                "size": float(order.amount),
                "remainSize": float(order.amount),
                "filledSize": "0",
                "canceledSize": "0",
                "clientOid": order.client_order_id or "",
                "orderTime": 1545914149935808589,
                "liquidity": "maker",
                "ts": 1545914149935808589
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": "message",
            "topic": "/contractMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {
                "orderId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                "symbol": self.exchange_trading_pair,
                "type": "canceled",
                "status": "done",
                "orderType": order.order_type.name.lower(),
                "side": order.trade_type.name.lower(),
                "price": str(order.price),
                "size": float(order.amount),
                "remainSize": "0",
                "filledSize": "0",
                "canceledSize": float(order.amount),
                "clientOid": order.client_order_id or "",
                "orderTime": 1545914149935808589,
                "liquidity": "maker",
                "ts": 1545914149935808589
            }
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "type": "message",
            "topic": "/contractMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {
                "orderId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                "symbol": self.exchange_trading_pair,
                "type": "filled",
                "status": "done",
                "orderType": order.order_type.name.lower(),
                "side": order.trade_type.name.lower(),
                "matchPrice": str(order.price),
                "size": float(order.amount) * 1000,
                "remainSize": "0",
                "matchSize": float(order.amount) * 1000,
                "fee": str(self.expected_fill_fee.percent),
                "canceledSize": "0",
                "clientOid": order.client_order_id or "",
                "orderTime": 1545914149935808589,
                "liquidity": "maker",
                "ts": 1545914149935808589
            }
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "type": "message",
            "topic": "/contractMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {
                "orderId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                "tradeId": self.expected_fill_trade_id,
                "symbol": self.exchange_trading_pair,
                "type": "match",
                "status": "done",
                "orderType": order.order_type.name.lower(),
                "side": order.trade_type.name.lower(),
                "matchPrice": str(order.price),
                "size": float(order.amount) * 1000,
                "fee": str(self.expected_fill_fee.percent),
                "remainSize": "0",
                "matchSize": float(order.amount) * 1000000,
                "canceledSize": "0",
                "clientOid": order.client_order_id or "",
                "orderTime": 1545914149935808589,
                "liquidity": "maker",
                "ts": 1545914149935808589
            }
        }

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        position_value = unrealized_pnl + order.amount * order.price * order.leverage
        return {
            "type": "message",
            "userId": 533285,
            "channelType": "private",
            "topic": "/contract/position:" + self.exchange_trading_pair,
            "subject": "position.change",
            "data": {
                "realisedGrossPnl": "0.00055631",
                "symbol": self.exchange_trading_pair,
                "crossMode": False,
                "liquidationPrice": "489",
                "posLoss": 0E-8,
                "avgEntryPrice": str(order.price),
                "unrealisedPnl": unrealized_pnl,
                "markPrice": str(order.price),
                "posMargin": 0.00266779,
                "autoDeposit": False,
                "riskLimit": 100000,
                "unrealisedCost": 0.00266375,
                "posComm": 0.00000392,
                "posMaint": 0.00001724,
                "posCost": str(position_value),
                "maintMarginReq": 0.005,
                "bankruptPrice": 1000000.0,
                "realisedCost": 0.00000271,
                "markValue": 0.00251640,
                "posInit": 0.39929535,
                "realisedPnl": -0.00000253,
                "maintMargin": 0.39929535,
                "realLeverage": str(order.leverage),
                "changeReason": "positionChange",
                "currentCost": str(position_value),
                "openingTimestamp": 1558433191000,
                "currentQty": -int(order.amount),
                "delevPercentage": 0.52,
                "currentComm": 0.00000271,
                "realisedGrossCost": 0E-8,
                "isOpen": True,
                "posCross": 1.2E-7,
                "currentTimestamp": 1558506060394,
                "unrealisedRoePcnt": -0.0553,
                "unrealisedPnlPcnt": -0.0553,
                "settleCurrency": self.quote_asset,
            }
        }

    def funding_info_event_for_websocket_update(self):
        return {
            "userId": "xbc453tg732eba53a88ggyt8c",  # Deprecated, will detele later
            "topic": "/contract/position:" + self.exchange_trading_pair,
            "subject": "position.settlement",
            "data": {
                "fundingTime": 1551770400000,         # Funding time
                "qty": 100,                           # Position size
                "markPrice": self.target_funding_info_mark_price_ws_updated,  # Settlement price
                "fundingRate": self.target_funding_info_rate_ws_updated,             # Funding rate
                "fundingFee": -296,                   # Funding fees
                "ts": 1547697294838004923,            # Current time (nanosecond)
                "settleCurrency": "XBT"               # Currency used to clear and settle the trades
            }
        }

    def test_create_order_with_invalid_position_action_raises_value_error(self):
        self._simulate_trading_rules_initialized()

        with self.assertRaises(ValueError) as exception_context:
            asyncio.get_event_loop().run_until_complete(
                self.exchange._create_order(
                    trade_type=TradeType.BUY,
                    order_id="C1",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    order_type=OrderType.LIMIT,
                    price=Decimal("46000"),
                    position_action=PositionAction.NIL,
                ),
            )

        self.assertEqual(
            f"Invalid position action {PositionAction.NIL}. Must be one of {[PositionAction.OPEN, PositionAction.CLOSE]}",
            str(exception_context.exception)
        )

    def test_user_stream_balance_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        non_linear_connector = KucoinPerpetualDerivative(
            client_config_map=client_config_map,
            kucoin_perpetual_api_key=self.api_key,
            kucoin_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.base_asset],
        )
        non_linear_connector._set_current_timestamp(1640780000)

        balance_event = self.non_linear_balance_event_websocket_update

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [balance_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("25"), self.exchange.get_balance(self.base_asset))

    def test_supported_position_modes(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        linear_connector = KucoinPerpetualDerivative(
            client_config_map=client_config_map,
            kucoin_perpetual_api_key=self.api_key,
            kucoin_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        non_linear_connector = KucoinPerpetualDerivative(
            client_config_map=client_config_map,
            kucoin_perpetual_api_key=self.api_key,
            kucoin_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.non_linear_trading_pair],
        )

        expected_result = [PositionMode.ONEWAY]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

        expected_result = [PositionMode.ONEWAY]
        self.assertEqual(expected_result, non_linear_connector.supported_position_modes())

    def test_set_position_mode_nonlinear(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        non_linear_connector = KucoinPerpetualDerivative(
            client_config_map=client_config_map,
            kucoin_perpetual_api_key=self.api_key,
            kucoin_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.non_linear_trading_pair],
        )
        non_linear_connector.set_position_mode(PositionMode.HEDGE)

        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message=f"Position mode {PositionMode.HEDGE} is not supported. Mode not set.",
            )
        )

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()

        linear_buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        linear_sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote_asset, linear_buy_collateral_token)
        self.assertEqual(self.quote_asset, linear_sell_collateral_token)

        non_linear_buy_collateral_token = self.exchange.get_buy_collateral_token(self.non_linear_trading_pair)
        non_linear_sell_collateral_token = self.exchange.get_sell_collateral_token(self.non_linear_trading_pair)

        self.assertEqual(self.non_linear_quote_asset, non_linear_buy_collateral_token)
        self.assertEqual(self.non_linear_quote_asset, non_linear_sell_collateral_token)

    def test_time_synchronizer_related_request_error_detection(self):
        error_code = CONSTANTS.RET_CODE_AUTH_TIMESTAMP_ERROR
        response = {"code": error_code, "msg": "Invalid KC-API-TIMESTAMP"}
        exception = IOError(f"Error executing request GET https://someurl. HTTP status is 400. Error: {json.dumps(response)}")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        error_code = CONSTANTS.RET_CODE_ORDER_NOT_EXISTS
        exception = IOError(f"{error_code} - Failed to cancel order because it was not found.")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    def place_buy_limit_maker_order(
        self,
        amount: Decimal = Decimal("100"),
        price: Decimal = Decimal("10_000"),
        position_action: PositionAction = PositionAction.OPEN,
    ):
        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=amount,
            order_type=OrderType.LIMIT_MAKER,
            price=price,
            position_action=position_action,
        )
        return order_id

    def place_buy_market_order(
        self,
        amount: Decimal = Decimal("100"),
        price: Decimal = Decimal("10_000"),
        position_action: PositionAction = PositionAction.OPEN,
    ):
        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=amount,
            order_type=OrderType.MARKET,
            price=price,
            position_action=position_action,
        )
        return order_id

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        url = self.funding_info_url

        response = self.funding_info_mock_response

        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.GET_CONTRACT_INFO_PATH_URL.format(symbol=self.exchange_trading_pair))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(response))

        event_messages = [asyncio.CancelledError]
        mock_queue_get.side_effect = event_messages

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        funding_info: FundingInfo = self.exchange.get_funding_info(self.trading_pair)

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(self.target_funding_info_index_price, funding_info.index_price)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        url = self.funding_info_url

        response = self.funding_info_mock_response
        mock_api.get(url, body=json.dumps(response))

        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.GET_CONTRACT_INFO_PATH_URL.format(symbol=self.exchange_trading_pair))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        funding_resp = self.get_predicted_funding_info
        mock_api.get(regex_url, body=json.dumps(funding_resp))

        funding_info_event = self.funding_info_event_for_websocket_update()

        event_messages = [funding_info_event, asyncio.CancelledError]
        mock_queue_get.side_effect = event_messages

        try:
            self.async_run_with_timeout(
                self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, self.exchange._perpetual_trading.funding_info_stream.qsize())  # rest in OB DS tests

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": "200000",
            "data": {
                "cancelledOrderIds": [
                    order.exchange_order_id
                ]
            }
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": "200000",
            "data": {
                    "id": order.exchange_order_id or "2b1d811c-8ff0-4ef0-92ed-b4ed5fd6de34",
                    "symbol": self.exchange_trading_pair,
                    "type": "limit",
                    "side": order.trade_type.name.lower(),
                    "price": str(order.price),
                    "size": float(order.amount),
                    "value": float(order.price + 2),
                    "dealValue": float(order.price + 2),
                    "dealSize": float(order.amount),
                    "stp": "",
                    "stop": "",
                    "stopPriceType": "",
                    "stopTriggered": True,
                    "stopPrice": None,
                    "timeInForce": "GTC",
                    "postOnly": False,
                    "hidden": False,
                    "iceberg": False,
                    "leverage": "5",
                    "forceHold": False,
                    "closeOrder": False,
                    "visibleSize": "",
                    "clientOid": order.client_order_id or "",
                    "remark": None,
                    "tags": None,
                    "isActive": False,
                    "cancelExist": False,
                    "createdAt": 1558167872000,
                    "updatedAt": 1558167872000,
                    "endAt": 1558167872000,
                    "orderTime": 1558167872000000000,
                    "settleCurrency": order.quote_asset,
                    "status": "done",
                    "filledValue": float(order.price + 2),
                    "filledSize": float(order.amount),
                    "reduceOnly": False,
            }
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"]["cancelExist"] = True
        resp["data"]["dealSize"] = 0
        resp["data"]["dealValue"] = 0
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"]["status"] = "open"
        resp["data"]["dealSize"] = 0
        resp["data"]["dealValue"] = 0
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"]["status"] = "open"
        resp["data"]["dealSize"] = float(self.expected_partial_fill_amount)
        resp["data"]["dealValue"] = float(self.expected_partial_fill_price)
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "code": "200000",
            "data": {
                "currentPage": 1,
                "pageSize": 1,
                "totalNum": 251915,
                "totalPage": 251915,
                "items": [
                    {
                        "symbol": self.exchange_trading_pair,
                        "tradeId": self.expected_fill_trade_id,
                        "orderId": order.exchange_order_id,
                        "side": order.trade_type.name.lower(),
                        "liquidity": "taker",
                        "forceTaker": True,
                        "price": str(self.expected_partial_fill_price),  # Filled price
                        "size": float(self.expected_partial_fill_amount),  # Filled amount
                        "filledSize": float(self.expected_partial_fill_amount),  # Filled amount
                        "value": "0.00012227",  # Order value
                        "feeRate": "0.0005",  # Floating fees
                        "fixFee": "0.00000006",  # Fixed fees
                        "feeCurrency": "XBT",  # Charging currency
                        "stop": "",  # A mark to the stop order type
                        "fee": str(self.expected_fill_fee.percent),  # Transaction fee
                        "orderType": order.order_type.name.lower(),  # Order type
                        "tradeType": "trade",  # Trade type (trade, liquidation, ADL or settlement)
                        "createdAt": 1558334496000,  # Time the order created
                        "settleCurrency": order.base_asset,  # settlement currency
                        "tradeTime": 1558334496000000000  # trade time in nanosecond
                    }]
            }
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            "code": "200000",
            "data": {
                    "currentPage": 1,
                    "pageSize": 100,
                    "totalNum": 1000,
                    "totalPage": 10,
                    "items": [
                        {
                            "symbol": self.exchange_trading_pair,  # Symbol of the contract
                            "tradeId": self.expected_fill_trade_id,  # Trade ID
                            "orderId": order.exchange_order_id,  # Order ID
                            "side": order.trade_type.name.lower(),  # Transaction side
                            "liquidity": "taker",  # Liquidity- taker or maker
                            "forceTaker": True,  # Whether to force processing as a taker
                            "price": str(order.price),  # Filled price
                            "matchPrice": str(order.price),  # Filled price
                            "size": float(self.exchange.get_quantity_of_contracts(self.trading_pair, order.amount)),   # Order amount
                            "filledSize": float(order.amount),   # Filled amount
                            "matchSize": float(order.amount),   # Filled amount
                            "value": "0.001204529",  # Order value
                            "feeRate": "0.0005",  # Floating fees
                            "fixFee": "0.00000006",  # Fixed fees
                            "feeCurrency": "USDT",  # Charging currency
                            "stop": "",  # A mark to the stop order type
                            "fee": str(self.expected_fill_fee.percent),  # Transaction fee
                            "orderType": order.order_type.name.lower(),  # Order type
                            "tradeType": "trade",  # Trade type (trade, liquidation, ADL or settlement)
                            "createdAt": 1558334496000,  # Time the order created
                            "settleCurrency": order.base_asset,  # settlement currency
                            "tradeTime": 1558334496000000000,  # trade time in nanosecond
                            "ts": 1558334496000000000  # trade time in nanosecond
                        }
                    ]
            }
        }

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            ),
            self.non_linear_trading_pair: TradingRule(  # non-linear
                trading_pair=self.non_linear_trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            ),
        }

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        # KuCoin has no partial fill status
        pass

    @aioresponses()
    def test_update_order_status_when_order_partially_filled_and_cancelled(self, mock_api):
        # KuCoin has no partial fill status
        pass

    @aioresponses()
    def test_user_stream_update_for_partially_cancelled_order(self, mock_api):
        # KuCoin has no partial fill status
        pass

    @aioresponses()
    def test_set_position_mode_success(self, mock_api):
        # There's only ONEWAY position mode
        pass

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        # There's only ONEWAY position mode
        pass

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
    def test_create_buy_limit_maker_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_limit_maker_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(order_request)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        request_data = json.loads(order_request.kwargs["data"])
        self.assertEqual(True, request_data["postOnly"])

    @aioresponses()
    @patch("hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_derivative.KucoinPerpetualDerivative.get_price")
    def test_create_buy_market_order_successfully(self, mock_api, get_price_mock):
        get_price_mock.return_value = Decimal(10000)
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

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
        self.assertEqual("IOC", request_data["timeInForce"])

    @aioresponses()
    def test_update_order_status_processes_trade_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        self.configure_fill_history_trade_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())
        self.async_run_with_timeout(self.exchange._update_trade_history())

        self.async_run_with_timeout(request_sent_event.wait())
        fill_event = self.order_filled_logger.event_log[0]

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_trade_history_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)

    @aioresponses()
    def test_start_network_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response
        duplicate = deepcopy(results['data'][0])
        duplicate["symbol"] = f"{self.exchange_trading_pair}_12345"
        duplicate["multiplier"] = str(float(duplicate["multiplier"]) + 1)
        results['data'].append(duplicate)
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange.start_network())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self._simulate_trading_rules_initialized()
        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        order_event = self.order_event_for_full_fill_websocket_update(order=order)
        trade_event = self.trade_event_for_full_fill_websocket_update(order=order)
        expected_unrealized_pnl = 12
        position_event = self.position_event_for_full_fill_websocket_update(
            order=order, unrealized_pnl=expected_unrealized_pnl
        )

        mock_queue = AsyncMock()
        event_messages = []
        if trade_event:
            event_messages.append(trade_event)
        if order_event:
            event_messages.append(order_event)
        if position_event:
            event_messages.append(position_event)
        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        if self.is_order_fill_http_update_executed_during_websocket_order_event_processing:
            self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api)

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)
        self.assertEqual(leverage, fill_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, fill_event.position)

        sell_event = self.sell_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, sell_event.timestamp)
        self.assertEqual(order.client_order_id, sell_event.order_id)
        self.assertEqual(order.base_asset, sell_event.base_asset)
        self.assertEqual(order.quote_asset, sell_event.quote_asset)
        self.assertEqual(order.amount, sell_event.base_asset_amount)
        self.assertEqual(order.amount * fill_event.price, sell_event.quote_asset_amount)
        self.assertEqual(order.order_type, sell_event.order_type)
        self.assertEqual(order.exchange_order_id, sell_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"SELL order {order.client_order_id} completely filled."
            )
        )

        self.assertEqual(1, len(self.exchange.account_positions))

        position: Position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual(self.trading_pair, position.trading_pair)
        self.assertEqual(PositionSide.SHORT, position.position_side)
        self.assertEqual(expected_unrealized_pnl, position.unrealized_pnl)
        self.assertEqual(fill_event.price, position.entry_price)
        self.assertEqual(-fill_event.amount, (self.exchange.get_quantity_of_contracts(self.trading_pair, position.amount)))
        self.assertEqual(leverage, position.leverage)

    @aioresponses()
    def test_lost_order_user_stream_full_fill_events_are_processed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        order_event = self.order_event_for_full_fill_websocket_update(order=order)
        trade_event = self.trade_event_for_full_fill_websocket_update(order=order)

        mock_queue = AsyncMock()
        event_messages = []
        if trade_event:
            event_messages.append(trade_event)
        if order_event:
            event_messages.append(order_event)
        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        if self.is_order_fill_http_update_executed_during_websocket_order_event_processing:
            self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api)

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_failure)

    @aioresponses()
    def test_fail_max_leverage(self, mock_api, callback: Optional[Callable] = lambda *args, **kwargs: None):
        target_leverage = 10000
        request_sent_event = asyncio.Event()
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_RISK_LIMIT_LEVEL_PATH_URL.format(symbol=self.exchange_trading_pair)
        )
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "code": "200000",
            "data": [
                {
                    "symbol": "ADAUSDTM",
                    "level": 1,
                    "maxRiskLimit": 500,
                    "minRiskLimit": 0,
                    "maxLeverage": 20,
                    "initialMargin": 0.05,
                    "maintainMargin": 0.025
                },
                {
                    "symbol": "ADAUSDTM",
                    "level": 2,
                    "maxRiskLimit": 1000,
                    "minRiskLimit": 500,
                    "maxLeverage": 2,
                    "initialMargin": 0.5,
                    "maintainMargin": 0.25
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(mock_response), callback=lambda *args, **kwargs: request_sent_event.set())
        self.exchange.set_leverage(trading_pair=self.trading_pair, leverage=target_leverage)
        self.async_run_with_timeout(request_sent_event.wait())
        max_leverage = mock_response["data"][0]["maxLeverage"]
        self.assertTrue(
            self.is_logged(
                log_level="NETWORK",
                message=f"Error setting leverage {target_leverage} for {self.trading_pair}: Max leverage for {self.trading_pair} is {max_leverage}.",
            )
        )
