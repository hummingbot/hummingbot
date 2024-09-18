import asyncio
import json
import re
from copy import deepcopy
from decimal import Decimal
from itertools import chain, product
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_derivative import BybitPerpetualDerivative
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class BybitPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.quote_asset = "USDT"  # linear
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)
        cls.non_linear_quote_asset = "USD"
        cls.non_linear_trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.non_linear_quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)
        params = {"category": "linear"}
        encoded_params = urlencode(params)
        url = f"{url}?{encoded_params}"
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT, trading_pair=self.trading_pair
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
        params = {"category": "linear"}
        encoded_params = urlencode(params)
        url = f"{url}?{encoded_params}"
        return url

    @property
    def order_creation_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL, trading_pair=self.trading_pair
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.GET_WALLET_BALANCE_PATH_URL)
        params = {"accountType": "UNIFIED"}
        encoded_params = urlencode(params)
        url = f"{url}?{encoded_params}"
        return url

    @property
    def funding_info_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT, trading_pair=self.trading_pair
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL, trading_pair=self.trading_pair
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    def configure_all_symbols_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        linear_url = self.all_symbols_url
        non_linear_url = linear_url.replace("linear", "inverse")
        linear_response = self.all_symbols_request_mock_response
        non_linear_response = linear_response.copy()
        non_linear_response["result"]["category"] = "inverse"
        mock_api.side_effect = [
            mock_api.get(linear_url, body=json.dumps(linear_response)),
            mock_api.get(non_linear_url, body=json.dumps(non_linear_response))
        ]
        return [linear_url]

    def configure_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        linear_url = self.trading_rules_url
        non_linear_url = self.trading_rules_url.replace("linear", "inverse")
        response = self.trading_rules_request_mock_response
        mock_api.side_effect = [
            mock_api.get(linear_url, body=json.dumps(response), callback=callback),
            mock_api.get(non_linear_url, body=json.dumps(response), callback=callback)
        ]
        return [linear_url]

    def configure_erroneous_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        linear_url = self.trading_rules_url
        non_linear_url = self.trading_rules_url.replace("linear", "inverse")
        response = self.trading_rules_request_erroneous_mock_response
        mock_api.side_effect = [
            mock_api.get(linear_url, body=json.dumps(response), callback=callback),
            mock_api.get(non_linear_url, body=json.dumps(response), callback=callback)
        ]
        return [linear_url]

    @property
    def all_symbols_request_mock_response(self):
        mock_response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "category": "linear",
                "list": [
                    {
                        "symbol": f"{self.exchange_trading_pair}",
                        "contractType": "LinearPerpetual",
                        "status": "Trading",
                        "baseCoin": f"{self.base_asset}",
                        "quoteCoin": f"{self.quote_asset}",
                        "launchTime": "1585526400000",
                        "deliveryTime": "0",
                        "deliveryFeeRate": "",
                        "priceScale": "2",
                        "leverageFilter": {
                            "minLeverage": "1",
                            "maxLeverage": "100.00",
                            "leverageStep": "0.01"
                        },
                        "priceFilter": {
                            "minPrice": "0.10",
                            "maxPrice": "199999.80",
                            "tickSize": "0.10"
                        },
                        "lotSizeFilter": {
                            "maxOrderQty": "100.000",
                            "maxMktOrderQty": "100.000",
                            "minOrderQty": "0.001",
                            "qtyStep": "0.001",
                            "postOnlyMaxOrderQty": "1000.000",
                            "minNotionalValue": "5"
                        },
                        "unifiedMarginTrade": True,
                        "fundingInterval": 480,
                        "settleCoin": f"{self.quote_asset}",
                        "copyTrading": "both",
                        "upperFundingRate": "0.00375",
                        "lowerFundingRate": "-0.00375"
                    }
                ],
                "nextPageCursor": ""
            },
            "retExtInfo": {},
            "time": 1707186451514
        }

        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "category": "inverse",
                "list": [
                    {
                        "symbol": self.exchange_trading_pair,
                        "lastPrice": str(self.expected_latest_price),
                        "indexPrice": "16598.54",
                        "markPrice": "16596.00",
                        "prevPrice24h": "16464.50",
                        "price24hPcnt": "0.008047",
                        "highPrice24h": "30912.50",
                        "lowPrice24h": "15700.00",
                        "prevPrice1h": "16595.50",
                        "openInterest": "373504107",
                        "openInterestValue": "22505.67",
                        "turnover24h": "2352.94950046",
                        "volume24h": "49337318",
                        "fundingRate": "-0.001034",
                        "nextFundingTime": self.target_funding_info_next_funding_utc_str,
                        "predictedDeliveryPrice": "",
                        "basisRate": "",
                        "deliveryFeeRate": "",
                        "deliveryTime": "0",
                        "ask1Size": "1",
                        "bid1Price": "16596.00",
                        "ask1Price": "16597.50",
                        "bid1Size": "1",
                        "basis": ""
                    }
                ]
            },
            "retExtInfo": {},
            "time": 1672376496682
        }
        return mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        mock_response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "category": "linear",
                "list": [
                    {
                        "symbol": f"{self.exchange_trading_pair}",
                        "contractType": "LinearPerpetual",
                        "status": "Trading",
                        "baseCoin": f"{self.base_asset}",
                        "quoteCoin": f"{self.quote_asset}",
                        "launchTime": "1585526400000",
                        "upperFundingRate": "0.00375",
                        "lowerFundingRate": "-0.00375"
                    }
                ],
                "nextPageCursor": ""
            },
            "retExtInfo": {},
            "time": 1707186451514
        }

        return "INVALID-PAIR", mock_response

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "timeSecond": "1688639403",
                "timeNano": "1688639403423213947"
            },
            "retExtInfo": {},
            "time": 1688639403423
        }
        return mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "category": "other_mistaken_category",
                "list": [
                    {
                        "symbol": f"{self.exchange_trading_pair}",
                        "contractType": "LinearPerpetual",
                        "status": "Trading",
                        "baseCoin": f"{self.base_asset}",
                        "quoteCoin": f"{self.quote_asset}",
                        "launchTime": "1585526400000",
                        "deliveryTime": "0",
                        "deliveryFeeRate": "",
                        "priceScale": "2",
                        "upperFundingRate": "0.00375",
                        "lowerFundingRate": "-0.00375"
                    }
                ],
                "nextPageCursor": ""
            },
            "retExtInfo": {},
            "time": 1707186451514
        }
        return mock_response

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "orderId": self.expected_exchange_order_id,
                "orderLinkId": "perpetual-test-postonly"
            },
            "retExtInfo": {},
            "time": 1672211918471
        }
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        mock_response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "list": [
                    {
                        "totalEquity": "3.31216591",
                        "accountIMRate": "0",
                        "totalMarginBalance": "3.00326056",
                        "totalInitialMargin": "0",
                        "accountType": "UNIFIED",
                        "totalAvailableBalance": "3.00326056",
                        "accountMMRate": "0",
                        "totalPerpUPL": "0",
                        "totalWalletBalance": "3.00326056",
                        "accountLTV": "0",
                        "totalMaintenanceMargin": "0",
                        "coin": [
                            {
                                "availableToBorrow": "3",
                                "bonus": "0",
                                "accruedInterest": "0",
                                "availableToWithdraw": "10",
                                "totalOrderIM": "0",
                                "equity": "15",
                                "totalPositionMM": "0",
                                "usdValue": "0",
                                "spotHedgingQty": "0.01592413",
                                "unrealisedPnl": "0",
                                "collateralSwitch": True,
                                "borrowAmount": "0.0",
                                "totalPositionIM": "0",
                                "walletBalance": "0",
                                "cumRealisedPnl": "0",
                                "locked": "0",
                                "marginCollateral": True,
                                "coin": self.base_asset
                            },
                            {
                                "availableToBorrow": "3",
                                "bonus": "0",
                                "accruedInterest": "0",
                                "availableToWithdraw": "2000",
                                "totalOrderIM": "0",
                                "equity": "2000",
                                "totalPositionMM": "0",
                                "usdValue": "0",
                                "spotHedgingQty": "0.01592413",
                                "unrealisedPnl": "0",
                                "collateralSwitch": True,
                                "borrowAmount": "0.0",
                                "totalPositionIM": "0",
                                "walletBalance": "0",
                                "cumRealisedPnl": "0",
                                "locked": "0",
                                "marginCollateral": True,
                                "coin": self.quote_asset
                            },

                        ]
                    }
                ]
            },
            "retExtInfo": {},
            "time": 1690872862481
        }
        return mock_response

    def _configure_balance_response(
            self,
            response: Dict[str, Any],
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        linear_url = self.balance_url
        non_linear_url = linear_url.replace("UNIFIED", "CONTRACT")
        mock_api.side_effect = [
            mock_api.get(
                re.compile(f"^{linear_url}".replace(".", r"\.").replace("?", r"\?")),
                body=json.dumps(response),
                callback=callback),
            mock_api.get(
                re.compile(f"^{non_linear_url}".replace(".", r"\.").replace("?", r"\?")),
                body=json.dumps(response),
                callback=callback),
        ]
        return linear_url

    def configure_trade_fills_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.USER_TRADE_RECORDS_PATH_URL, trading_pair=self.trading_pair
        )
        params = {
            "category": "linear" if web_utils.is_linear_perpetual(self.trading_pair) else "inverse",
            "limit": 200,
            "startTime": int(int(self.exchange._last_trade_history_timestamp) * 1e3),
            "symbol": self.exchange_trading_pair,
        }
        encoded_params = urlencode(params)
        url = f"{url}?{encoded_params}"
        response = self._trade_fills_request_mock_response()
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_erroneous_trade_fills_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.USER_TRADE_RECORDS_PATH_URL, trading_pair=self.trading_pair
        )
        params = {
            "category": "linear" if web_utils.is_linear_perpetual(self.trading_pair) else "inverse",
            "limit": 200,
            "startTime": int(int(self.exchange._last_trade_history_timestamp) * 1e3),
            "symbol": self.exchange_trading_pair,
        }
        encoded_params = urlencode(params)
        url = f"{url}?{encoded_params}"
        resp = {"retCode": 10001, "retMsg": "SOME ERROR"}
        mock_api.get(url, body=json.dumps(resp), status=404, callback=callback)
        return [url]

    @property
    def balance_request_mock_response_only_base(self):
        mock_response = self.balance_request_mock_response_for_base_and_quote
        for coin in mock_response["result"]["list"][0]["coin"]:
            if coin["coin"] == self.quote_asset:
                mock_response["result"]["list"][0]["coin"].remove(coin)
        return mock_response

    def _trade_fills_request_mock_response(self):
        return {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "nextPageCursor": "132766%3A2%2C132766%3A2",
                "category": "linear",
                "list": [
                    {
                        "symbol": self.exchange_trading_pair,
                        "orderType": "Limit",
                        "underlyingPrice": "",
                        "orderLinkId": "",
                        "side": "Buy",
                        "indexPrice": "",
                        "orderId": "",
                        "stopOrderType": "UNKNOWN",
                        "leavesQty": "0",
                        "execTime": "1672282722429",
                        "feeCurrency": "",
                        "isMaker": False,
                        "execFee": str(self.expected_fill_fee.flat_fees[0].amount),
                        "feeRate": "0.0006",
                        "execId": self.expected_fill_trade_id,
                        "tradeIv": "",
                        "blockTradeId": "",
                        "markPrice": "1183.54",
                        "execPrice": "10.0",
                        "markIv": "",
                        "orderQty": "0.1",
                        "orderPrice": "1236.9",
                        "execValue": "119.015",
                        "execType": "Trade",
                        "execQty": "1.0",
                        "closedSize": "",
                        "seq": 4688002127
                    }
                ]
            },
            "retExtInfo": {},
            "time": 1672283754510
        }

    @property
    def balance_event_websocket_update(self):
        mock_response = {
            "id": "592324d2bce751-ad38-48eb-8f42-4671d1fb4d4e",
            "topic": "wallet",
            "creationTime": 1700034722104,
            "data": [
                {
                    "accountIMRate": "0",
                    "accountMMRate": "0",
                    "totalEquity": "10262.91335023",
                    "totalWalletBalance": "9684.46297164",
                    "totalMarginBalance": "9684.46297164",
                    "totalAvailableBalance": "9556.6056555",
                    "totalPerpUPL": "0",
                    "totalInitialMargin": "0",
                    "totalMaintenanceMargin": "0",
                    "coin": [
                        {
                            "coin": self.base_asset,
                            "equity": "0.00102964",
                            "usdValue": "36.70759517",
                            "walletBalance": "0.00102964",
                            "availableToWithdraw": "0.00102964",
                            "availableToBorrow": "",
                            "borrowAmount": "0",
                            "accruedInterest": "0",
                            "totalOrderIM": "",
                            "totalPositionIM": "",
                            "totalPositionMM": "",
                            "unrealisedPnl": "0",
                            "cumRealisedPnl": "-0.00000973",
                            "bonus": "0",
                            "collateralSwitch": True,
                            "marginCollateral": True,
                            "locked": "0",
                            "spotHedgingQty": "0.01592413"
                        }
                    ],
                    "accountLTV": "0",
                    "accountType": "UNIFIED"
                }
            ]
        }
        return mock_response

    @property
    def non_linear_balance_event_websocket_update(self):
        mock_response = {
            "id": "592324d2bce751-ad38-48eb-8f42-4671d1fb4d4e",
            "topic": "wallet",
            "creationTime": 1700034722104,
            "data": [
                {
                    "accountIMRate": "0",
                    "accountMMRate": "0",
                    "totalEquity": "10262.91335023",
                    "totalWalletBalance": "9684.46297164",
                    "totalMarginBalance": "9684.46297164",
                    "totalAvailableBalance": "9556.6056555",
                    "totalPerpUPL": "0",
                    "totalInitialMargin": "0",
                    "totalMaintenanceMargin": "0",
                    "coin": [
                        {
                            "coin": self.base_asset,
                            "equity": "15",
                            "usdValue": "36.70759517",
                            "walletBalance": "0.00102964",
                            "availableToWithdraw": "10",
                            "availableToBorrow": "",
                            "borrowAmount": "0",
                            "accruedInterest": "0",
                            "totalOrderIM": "",
                            "totalPositionIM": "",
                            "totalPositionMM": "",
                            "unrealisedPnl": "0",
                            "cumRealisedPnl": "-0.00000973",
                            "bonus": "0",
                            "collateralSwitch": True,
                            "marginCollateral": True,
                            "locked": "0",
                            "spotHedgingQty": "0.01592413"
                        }
                    ],
                    "accountLTV": "0",
                    "accountType": "CONTRACT"
                }
            ]
        }
        return mock_response

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def empty_funding_payment_mock_response(self):
        return {
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": None,
            "ext_info": None,
            "time_now": "1577446900.717204",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1577446900724,
            "rate_limit": 120
        }

    @property
    def funding_payment_mock_response(self):
        return {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "nextPageCursor": "21963%3A1%2C14954%3A1",
                "list": [
                    {
                        "id": "592324_XRPUSDT_161440249321",
                        "symbol": self.exchange_trading_pair,
                        "side": "Buy",
                        "funding": self.target_funding_payment_funding_rate,
                        "orderLinkId": "",
                        "orderId": "1672128000-8-592324-1-2",
                        "fee": "0.00000000",
                        "change": "-0.003676",
                        "cashFlow": "0",
                        "transactionTime": self.target_funding_payment_timestamp_str,
                        "type": "SETTLEMENT",
                        "feeRate": "0.0001",
                        "bonusChange": "",
                        "size": float(self.target_funding_payment_payment_amount / self.target_funding_payment_funding_rate),
                        "qty": "100",
                        "cashBalance": "5086.55825002",
                        "currency": "USDT",
                        "category": "linear",
                        "tradePrice": "0.3676",
                        "tradeId": "534c0003-4bf7-486f-aa02-78cee36825e4"
                    },
                    {
                        "id": "592324_XRPUSDT_161440249321",
                        "symbol": "XRPUSDT",
                        "side": "Buy",
                        "funding": "",
                        "orderLinkId": "linear-order",
                        "orderId": "592b7e41-78fd-42e2-9aa3-91e1835ef3e1",
                        "fee": "0.01908720",
                        "change": "-0.0190872",
                        "cashFlow": "0",
                        "transactionTime": "1672121182224",
                        "type": "TRADE",
                        "feeRate": "0.0006",
                        "bonusChange": "-0.1430544",
                        "size": "100",
                        "qty": "88",
                        "cashBalance": "5086.56192602",
                        "currency": "USDT",
                        "category": "linear",
                        "tradePrice": "0.3615",
                        "tradeId": "5184f079-88ec-54c7-8774-5173cafd2b4e"
                    },
                    {
                        "id": "592324_XRPUSDT_161407743011",
                        "symbol": "XRPUSDT",
                        "side": "Buy",
                        "funding": "",
                        "orderLinkId": "linear-order",
                        "orderId": "592b7e41-78fd-42e2-9aa3-91e1835ef3e1",
                        "fee": "0.00260280",
                        "change": "-0.0026028",
                        "cashFlow": "0",
                        "transactionTime": "1672121182224",
                        "type": "TRADE",
                        "feeRate": "0.0006",
                        "bonusChange": "",
                        "size": "12",
                        "qty": "12",
                        "cashBalance": "5086.58101322",
                        "currency": "USDT",
                        "category": "linear",
                        "tradePrice": "0.3615",
                        "tradeId": "8569c10f-5061-5891-81c4-a54929847eb3"
                    }
                ]
            },
            "retExtInfo": {},
            "time": 1672132481405
        }

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        raise NotImplementedError  # test is overwritten

    @property
    def target_funding_info_next_funding_utc_str(self):
        return "1657099053000"

    @property
    def target_funding_payment_timestamp_str(self):
        return "1657110053000"

    @property
    def funding_info_mock_response(self):
        mock_response = self.latest_prices_request_mock_response
        funding_info = mock_response["result"]["list"][0]
        funding_info["indexPrice"] = self.target_funding_info_index_price
        funding_info["markPrice"] = self.target_funding_info_mark_price
        funding_info["nextFundingTime"] = self.target_funding_info_next_funding_utc_str
        funding_info["fundingRate"] = self.target_funding_info_rate
        return mock_response

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        trading_rules_resp = self.trading_rules_request_mock_response["result"]["list"][0]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(str(trading_rules_resp["lotSizeFilter"]["minOrderQty"])),
            max_order_size=Decimal(str(trading_rules_resp["lotSizeFilter"]["maxOrderQty"])),
            min_price_increment=Decimal(str(trading_rules_resp["priceFilter"]["tickSize"])),
            min_base_amount_increment=Decimal(str(trading_rules_resp["lotSizeFilter"]["qtyStep"])),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["result"]["list"][0]
        return f"Error parsing the trading pair rule: {erroneous_rule}. Skipping..."

    @property
    def expected_exchange_order_id(self):
        return "335fd977-e5a5-4781-b6d0-c772d5bfb95b"

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
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.1"))],
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
        exchange = BybitPerpetualDerivative(
            client_config_map,
            self.api_key,
            self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        exchange._last_trade_history_timestamp = self.latest_trade_hist_timestamp
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertEqual("application/json", request_headers["Content-Type"])

        request_data = request_call.kwargs["headers"]
        if request_data is None:
            request_data = json.loads(request_call.kwargs["headers"])

        self.assertIn("X-BAPI-TIMESTAMP", request_data)
        self.assertIn("X-BAPI-API-KEY", request_data)
        self.assertEqual(self.api_key, request_data["X-BAPI-API-KEY"])
        self.assertIn("X-BAPI-SIGN", request_data)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.trade_type.name.capitalize(), request_data["side"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(Decimal(str(order.amount)), Decimal(request_data["qty"]))
        self.assertEqual(CONSTANTS.DEFAULT_TIME_IN_FORCE, request_data["timeInForce"])
        self.assertEqual(order.position == PositionAction.CLOSE, request_data["closeOnTrigger"])
        self.assertEqual(order.client_order_id, request_data["orderLinkId"])
        self.assertEqual(order.position == PositionAction.CLOSE, request_data["reduceOnly"])
        self.assertIn("positionIdx", request_data)
        self.assertEqual(order.order_type.name.capitalize(), request_data["orderType"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(order.exchange_order_id, request_data["orderId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["orderLinkId"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

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
            endpoint=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL, trading_pair=order.trading_pair
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL, trading_pair=order.trading_pair
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {
            "ret_code": 20000,
            "ret_msg": "Could not find order",
        }
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
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
        callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, trading_pair=order.trading_pair
        )
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, trading_pair=order.trading_pair
        )
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, trading_pair=order.trading_pair
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
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, trading_pair=order.trading_pair
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
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, trading_pair=order.trading_pair
        )
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, trading_pair=order.trading_pair
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
            endpoint=CONSTANTS.USER_TRADE_RECORDS_PATH_URL, trading_pair=order.trading_pair
        )
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, trading_pair=order.trading_pair
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
            endpoint=CONSTANTS.SET_POSITION_MODE_URL, trading_pair=self.trading_pair
        )
        response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {},
            "retExtInfo": {},
            "time": 1675249072814
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
            endpoint=CONSTANTS.SET_POSITION_MODE_URL, trading_pair=self.trading_pair
        )
        regex_url = re.compile(f"^{url}")

        error_code = 1_000
        error_msg = "Some problem"
        mock_response = {
            "retCode": error_code,
            "retMsg": error_msg,
            "result": {},
            "retExtInfo": {},
            "time": 1675249072814
        }
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url, f"ret_code <{error_code}> - {error_msg}"

    def configure_failed_set_leverage(
        self,
        leverage: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.SET_LEVERAGE_PATH_URL, trading_pair=self.trading_pair
        )
        regex_url = re.compile(f"^{url}")

        err_code = 1
        err_msg = "Some problem"
        mock_response = {
            "retCode": err_code,
            "retMsg": err_msg,
            "result": {},
            "retExtInfo": {},
            "time": 1672281607343
        }
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url, f"ret_code <{err_code}> - {err_msg}"

    def configure_successful_set_leverage(
        self,
        leverage: int,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.SET_LEVERAGE_PATH_URL, trading_pair=self.trading_pair
        )
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {},
            "retExtInfo": {},
            "time": 1672281607343
        }

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "id": "5923240c6880ab-c59f-420b-9adb-3639adc9dd90",
            "topic": "order",
            "creationTime": 1672364262474,
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "orderId": order.exchange_order_id,
                    "side": order.trade_type.name.capitalize(),
                    "orderType": order.order_type.name.capitalize(),
                    "cancelType": "UNKNOWN",
                    "price": str(order.price),
                    "qty": str(order.amount),
                    "orderIv": "",
                    "timeInForce": "IOC",
                    "orderStatus": "New",
                    "orderLinkId": order.client_order_id,
                    "lastPriceOnCreated": "",
                    "reduceOnly": order.position == PositionAction.CLOSE,
                    "leavesQty": "",
                    "leavesValue": "",
                    "cumExecQty": "1",
                    "cumExecValue": "75",
                    "avgPrice": "75",
                    "blockTradeId": "",
                    "positionIdx": 0,
                    "cumExecFee": "0.358635",
                    "createdTime": "1672364262444",
                    "updatedTime": "1672364262457",
                    "rejectReason": "EC_NoError",
                    "stopOrderType": "",
                    "tpslMode": "",
                    "triggerPrice": "",
                    "takeProfit": "",
                    "stopLoss": "",
                    "tpTriggerBy": "",
                    "slTriggerBy": "",
                    "tpLimitPrice": "",
                    "slLimitPrice": "",
                    "triggerDirection": 0,
                    "triggerBy": "",
                    "closeOnTrigger": order.position == PositionAction.CLOSE,
                    "category": "option",
                    "placeType": "price",
                    "smpType": "None",
                    "smpGroup": 0,
                    "smpOrderId": "",
                    "feeCurrency": ""
                }
            ]
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        order_event = self.order_event_for_new_order_websocket_update(order)
        order_event["data"][0]["orderStatus"] = "Cancelled"
        return order_event

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        order_event = self.order_event_for_new_order_websocket_update(order)
        order_event["data"][0]["orderStatus"] = "Filled"
        return order_event

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "id": "592324803b2785-26fa-4214-9963-bdd4727f07be",
            "topic": "execution",
            "creationTime": 1672364174455,
            "data": [
                {
                    "category": "linear",
                    "symbol": self.exchange_trading_pair,
                    "execFee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "execId": self.expected_fill_trade_id,
                    "execPrice": str(order.price),
                    "execQty": str(order.amount),
                    "execType": "Trade",
                    "execValue": "8.435",
                    "isMaker": False,
                    "feeRate": "0.0006",
                    "tradeIv": "",
                    "markIv": "",
                    "blockTradeId": "",
                    "markPrice": "0.3391",
                    "indexPrice": "",
                    "underlyingPrice": "",
                    "leavesQty": "0",
                    "orderId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "orderLinkId": order.client_order_id or "",
                    "orderPrice": "0.3207",
                    "orderQty": "25",
                    "orderType": "Market",
                    "stopOrderType": "UNKNOWN",
                    "side": order.trade_type.name.capitalize(),
                    "execTime": "1672364174443",
                    "isLeverage": "0",
                    "closedSize": "",
                    "seq": 4688002127
                }
            ]
        }

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        position_value = unrealized_pnl + order.amount * order.price * order.leverage
        return {
            "id": "1003076014fb7eedb-c7e6-45d6-a8c1-270f0169171a",
            "topic": "position",
            "creationTime": 1697682317044,
            "data": [
                {
                    "positionIdx": 2,
                    "tradeMode": 0,
                    "riskId": 1,
                    "riskLimitValue": "2000000",
                    "symbol": self.exchange_trading_pair,
                    "side": order.trade_type.name.capitalize(),
                    "size": str(order.amount),
                    "entryPrice": str(order.price),
                    "leverage": str(order.leverage),
                    "positionValue": str(position_value),
                    "positionBalance": "0",
                    "markPrice": "28184.5",
                    "positionIM": "0",
                    "positionMM": "0",
                    "takeProfit": "0",
                    "stopLoss": "0",
                    "trailingStop": "0",
                    "unrealisedPnl": "0",
                    "curRealisedPnl": "1.26",
                    "cumRealisedPnl": "-25.06579337",
                    "sessionAvgPrice": "0",
                    "createdTime": "1694402496913",
                    "updatedTime": "1697682317038",
                    "tpslMode": "Full",
                    "liqPrice": "0",
                    "bustPrice": "",
                    "category": "linear",
                    "positionStatus": "Normal",
                    "adlRankIndicator": 0,
                    "autoAddMargin": 0,
                    "leverageSysUpdatedTime": "",
                    "mmrSysUpdatedTime": "",
                    "seq": 8327597863,
                    "isReduceOnly": False
                }
            ]
        }

    def funding_info_event_for_websocket_update(self):
        return {
            "topic": f"instrument_info.100ms.{self.exchange_trading_pair}",
            "type": "delta",
            "data": {
                "delete": [],
                "update": [
                    {
                        "id": 1,
                        "symbol": self.exchange_trading_pair,
                        "prev_price_24h_e4": 81565000,
                        "prev_price_24h": "81565000",
                        "price_24h_pcnt_e6": -4904,
                        "open_value_e8": 2000479681106,
                        "total_turnover_e8": 2029370495672976,
                        "turnover_24h_e8": 9066215468687,
                        "volume_24h": 735316391,
                        "cross_seq": 1053192657,
                        "created_at": "2018-11-14T16:33:26Z",
                        "updated_at": "2020-01-12T18:25:25Z",
                        "index_price": self.target_funding_info_index_price_ws_updated,
                        "mark_price": self.target_funding_info_mark_price_ws_updated,
                        "next_funding_time": self.target_funding_info_next_funding_utc_str,
                        "predicted_funding_rate_e6": self.target_funding_info_rate_ws_updated * 1e6,
                    }
                ],
                "insert": []
            },
            "cross_seq": 1053192657,
            "timestamp_e6": 1578853525691123
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
        non_linear_connector = BybitPerpetualDerivative(
            client_config_map=client_config_map,
            bybit_perpetual_api_key=self.api_key,
            bybit_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.non_linear_trading_pair],
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
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

    @aioresponses()
    def test_trade_history_fetch_raises_exception(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.configure_erroneous_trade_fills_response(mock_api=mock_api,
                                                      callback=lambda *args, **kwargs: request_sent_event.set())
        resp = {"retCode": 10001, "retMsg": "SOME ERROR"}
        asyncio.get_event_loop().run_until_complete(self.exchange._update_trade_history())
        self.is_logged("network", f"Error fetching status update for {self.trading_pair}: {resp}.")

    def test_supported_position_modes(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        linear_connector = BybitPerpetualDerivative(
            client_config_map=client_config_map,
            bybit_perpetual_api_key=self.api_key,
            bybit_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        non_linear_connector = BybitPerpetualDerivative(
            client_config_map=client_config_map,
            bybit_perpetual_api_key=self.api_key,
            bybit_perpetual_secret_key=self.api_secret,
            trading_pairs=[self.non_linear_trading_pair],
        )

        expected_result = [PositionMode.ONEWAY, PositionMode.HEDGE]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

        expected_result = [PositionMode.ONEWAY]
        self.assertEqual(expected_result, non_linear_connector.supported_position_modes())

    def test_set_position_mode_nonlinear(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        non_linear_connector = BybitPerpetualDerivative(
            client_config_map=client_config_map,
            bybit_perpetual_api_key=self.api_key,
            bybit_perpetual_secret_key=self.api_secret,
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

    def test_get_position_index(self):
        perpetual_trading: PerpetualTrading = self.exchange._perpetual_trading
        perpetual_trading.set_position_mode(value=PositionMode.ONEWAY)

        for trade_type, position_action in product(
            [TradeType.BUY, TradeType.SELL], [PositionAction.OPEN, PositionAction.CLOSE]
        ):
            position_idx = self.exchange._get_position_idx(trade_type=trade_type, position_action=position_action)
            self.assertEqual(
                CONSTANTS.POSITION_IDX_ONEWAY, position_idx, msg=f"Failed on {trade_type} and {position_action}."
            )

        perpetual_trading.set_position_mode(value=PositionMode.HEDGE)

        for trade_type, position_action in zip(
            [TradeType.BUY, TradeType.SELL], [PositionAction.OPEN, PositionAction.CLOSE]
        ):
            position_idx = self.exchange._get_position_idx(trade_type=trade_type, position_action=position_action)
            self.assertEqual(
                CONSTANTS.POSITION_IDX_HEDGE_BUY, position_idx, msg=f"Failed on {trade_type} and {position_action}."
            )

        for trade_type, position_action in zip(
            [TradeType.BUY, TradeType.SELL], [PositionAction.CLOSE, PositionAction.OPEN]
        ):
            position_idx = self.exchange._get_position_idx(trade_type=trade_type, position_action=position_action)
            self.assertEqual(
                CONSTANTS.POSITION_IDX_HEDGE_SELL, position_idx, msg=f"Failed on {trade_type} and {position_action}."
            )

        for trade_type, position_action in chain(
            product([TradeType.RANGE], [PositionAction.CLOSE, PositionAction.OPEN]),
            product([TradeType.BUY, TradeType.SELL], [PositionAction.NIL]),
        ):
            with self.assertRaises(NotImplementedError, msg=f"Failed on {trade_type} and {position_action}."):
                self.exchange._get_position_idx(trade_type=trade_type, position_action=position_action)

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_first_is_good(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url
        response = self.trading_rules_request_mock_response
        results = response["result"]["list"]
        duplicate = deepcopy(results[0])
        duplicate["symbol"] = f"{self.exchange_trading_pair}_12345"
        duplicate["lotSizeFilter"]["minOrderQty"] = str(float(duplicate["lotSizeFilter"]["minOrderQty"]) + 1.0)
        results.append(duplicate)

        mock_api.side_effect = [
            mock_api.get(url, body=json.dumps(response)),
            mock_api.get(url.replace("linear", "inverse"), body=json.dumps(response))
        ]
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_second_is_good(self, mock_api):
        self.exchange._set_current_timestamp(1000)
        url = self.trading_rules_url
        response = self.trading_rules_request_mock_response
        results = response["result"]["list"]
        duplicate = deepcopy(results[0])
        min_order_qty = float(duplicate["lotSizeFilter"]["minOrderQty"])
        duplicate["symbol"] = f"{self.exchange_trading_pair}_12345"
        duplicate["lotSizeFilter"]["minOrderQty"] = min_order_qty + 1
        results.insert(0, duplicate)

        mock_api.side_effect = [
            mock_api.get(url, body=json.dumps(response)),
            mock_api.get(url.replace("linear", "inverse"), body=json.dumps(response))
        ]

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_cannot_resolve(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url
        response = self.trading_rules_request_mock_response
        results = response["result"]["list"]
        min_order_qty = float(results[0]["lotSizeFilter"]["minOrderQty"])
        first_duplicate = deepcopy(results[0])
        first_duplicate["symbol"] = f"{self.exchange_trading_pair}_12345"
        first_duplicate["lotSizeFilter"]["minOrderQty"] = min_order_qty + 1
        second_duplicate = deepcopy(results[0])
        second_duplicate["symbol"] = f"{self.exchange_trading_pair}_67890"
        second_duplicate["lotSizeFilter"]["minOrderQty"] = min_order_qty + 2
        results.pop(0)
        results.append(first_duplicate)
        results.append(second_duplicate)

        mock_api.side_effect = [
            mock_api.get(url, body=json.dumps(response)),
            mock_api.get(url.replace("linear", "inverse"), body=json.dumps(response))
        ]

        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange.trading_rules))
        self.assertNotIn(self.trading_pair, self.exchange.trading_rules)
        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message=(
                    f"Could not resolve the exchange symbols"
                    f" {self.exchange_trading_pair}_67890"
                    f" and {self.exchange_trading_pair}_12345"
                ),
            )
        )

    def test_time_synchronizer_related_reqeust_error_detection(self):
        error_code_str = self.exchange._format_ret_code_for_print(ret_code=CONSTANTS.RET_CODE_AUTH_TIMESTAMP_ERROR)
        exception = IOError(f"{error_code_str} - Failed to cancel order for timestamp reason.")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        error_code_str = self.exchange._format_ret_code_for_print(ret_code=CONSTANTS.RET_CODE_ORDER_NOT_EXISTS)
        exception = IOError(f"{error_code_str} - Failed to cancel order because it was not found.")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        url = self.funding_info_url

        response = self.funding_info_mock_response
        mock_api.get(url, body=json.dumps(response))

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
        self.assertEqual(
            self.target_funding_info_next_funding_utc_timestamp, funding_info.next_funding_utc_timestamp
        )
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        url = self.funding_info_url

        response = self.funding_info_mock_response
        mock_api.get(url, body=json.dumps(response))

        funding_info_event = self.funding_info_event_for_websocket_update()

        event_messages = [funding_info_event, asyncio.CancelledError]
        mock_queue_get.side_effect = event_messages

        try:
            self.async_run_with_timeout(
                self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, self.exchange._perpetual_trading.funding_info_stream.qsize())  # rest in OB DS tests

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

    @staticmethod
    def _order_cancelation_request_successful_mock_response(order: InFlightOrder) -> Any:
        return {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "orderId": order.exchange_order_id,
                "orderLinkId": order.client_order_id
            },
            "retExtInfo": {},
            "time": 1672217377164
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "list": [
                    {
                        "orderId": order.exchange_order_id,
                        "orderLinkId": order.client_order_id,
                        "blockTradeId": "",
                        "symbol": self.exchange_trading_pair,
                        "price": str(order.price),
                        "qty": str(order.amount),
                        "side": "Buy",
                        "isLeverage": "",
                        "positionIdx": 1,
                        "orderStatus": "Filled",
                        "cancelType": "UNKNOWN",
                        "rejectReason": "EC_PostOnlyWillTakeLiquidity",
                        "avgPrice": str(order.average_executed_price),
                        "leavesQty": "0.000",
                        "leavesValue": "0",
                        "cumExecQty": "0.000",
                        "cumExecValue": "0",
                        "cumExecFee": "0",
                        "timeInForce": "PostOnly",
                        "orderType": "Limit",
                        "stopOrderType": "UNKNOWN",
                        "orderIv": "",
                        "triggerPrice": "0.00",
                        "takeProfit": "0.00",
                        "stopLoss": "0.00",
                        "tpTriggerBy": "UNKNOWN",
                        "slTriggerBy": "UNKNOWN",
                        "triggerDirection": 0,
                        "triggerBy": "UNKNOWN",
                        "lastPriceOnCreated": "0.00",
                        "reduceOnly": False,
                        "closeOnTrigger": False,
                        "smpType": "None",
                        "smpGroup": 0,
                        "smpOrderId": "",
                        "tpslMode": "",
                        "tpLimitPrice": "",
                        "slLimitPrice": "",
                        "placeType": "",
                        "createdTime": order.creation_timestamp,
                        "updatedTime": order.last_update_timestamp
                    }
                ],
                "nextPageCursor": "page_token%3D39380%26",
                "category": "linear"
            },
            "retExtInfo": {},
            "time": 1684766282976
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["result"]["list"][0]["orderStatus"] = "Cancelled"
        resp["result"]["list"][0]["cumExecQty"] = "0"
        resp["result"]["list"][0]["cumExecValue"] = "0"
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["result"]["list"][0]["orderStatus"] = "New"
        resp["result"]["list"][0]["cumExecQty"] = "0"
        resp["result"]["list"][0]["cumExecValue"] = "0"
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["result"]["list"][0]["orderStatus"] = "PartiallyFilled"
        resp["result"]["list"][0]["cumExecQty"] = str(self.expected_partial_fill_amount)
        resp["result"]["list"][0]["cumExecValue"] = str(self.expected_partial_fill_price)
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        mock_resp = self._order_fills_request_full_fill_mock_response(order=order)
        mock_resp["result"]["list"][0]["execQty"] = str(self.expected_partial_fill_amount)
        mock_resp["result"]["list"][0]["execValue"] = str(self.expected_partial_fill_price)
        return mock_resp

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "nextPageCursor": "132766%3A2%2C132766%3A2",
                "category": "linear",
                "list": [
                    {
                        "symbol": self.exchange_trading_pair,
                        "orderType": order.order_type.name.capitalize(),
                        "underlyingPrice": "",
                        "orderLinkId": "",
                        "side": order.trade_type.name.capitalize(),
                        "indexPrice": "",
                        "orderId": order.exchange_order_id,
                        "stopOrderType": "UNKNOWN",
                        "leavesQty": "0",
                        "execTime": "1672282722429",
                        "feeCurrency": "",
                        "isMaker": False,
                        "execFee": str(self.expected_fill_fee.flat_fees[0].amount),
                        "feeRate": "0.0006",
                        "execId": self.expected_fill_trade_id,
                        "tradeIv": "",
                        "blockTradeId": "",
                        "markPrice": "1183.54",
                        "execPrice": str(order.price),
                        "markIv": "",
                        "orderQty": "0.1",
                        "orderPrice": "1236.9",
                        "execValue": "119.015",
                        "execType": "Trade",
                        "execQty": str(order.amount),
                        "closedSize": "",
                        "seq": 4688002127
                    }
                ]
            },
            "retExtInfo": {},
            "time": 1672283754510
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
