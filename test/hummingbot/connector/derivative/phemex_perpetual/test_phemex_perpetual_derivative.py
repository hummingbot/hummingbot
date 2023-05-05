import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple, Union
from unittest.mock import patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.phemex_perpetual import (
    phemex_perpetual_constants as CONSTANTS,
    phemex_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_derivative import PhemexPerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import OrderCancelledEvent


class PhemexPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.quote_asset = "USDT"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    def setUp(self) -> None:
        super().setUp()
        self.exchange._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}{self.quote_asset}": self.trading_pair, "ABCDEF": "ABC-DEF"})
        )

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    @property
    def funding_info_url(self):
        return CONSTANTS.TICKER_PRICE_URL

    @property
    def funding_payment_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.FUNDING_PAYMENT)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_info_mock_response(self):
        return {
            "error": None,
            "id": 0,
            "result": {
                "closeRp": "20731",
                "fundingRateRr": "3",
                "highRp": "20818.8",
                "indexPriceRp": "1",
                "lowRp": "20425.2",
                "markPriceRp": "2",
                "openInterestRv": "0",
                "openRp": "20709",
                "predFundingRateRr": "3",
                "symbol": self.exchange_trading_pair,
                "timestamp": self.exchange._orderbook_ds._next_funding_time(),
                "turnoverRv": "139029311.7517",
                "volumeRq": "6747.727",
            },
        }

    @property
    def target_funding_payment_timestamp(self):
        return 1666226932259

    @property
    def empty_funding_payment_mock_response(self):
        return {"code": 0, "msg": "OK", "data": {"total": 4, "rows": []}}

    @property
    def funding_payment_mock_response(self):
        return {
            "code": 0,
            "msg": "OK",
            "data": {
                "rows": [
                    {
                        "createTime": 1666226932259,
                        "symbol": self.exchange_trading_pair,
                        "currency": "USDT",
                        "action": 1,
                        "tradeType": 1,
                        "execQtyRq": "0.01",
                        "execPriceRp": "1271.9",
                        "side": 1,
                        "orderQtyRq": "0.78",
                        "priceRp": "1271.9",
                        "execValueRv": "200",
                        "feeRateRr": "100",
                        "execFeeRv": "200",
                        "ordType": 2,
                        "execId": "8718cae",
                        "execStatus": 6,
                    },
                ],
            }
        }

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return {
            "positions_p": [
                {
                    "accountID": 9328670003,
                    "assignedPosBalanceRv": "30.861734862748",
                    "avgEntryPriceRp": str(order.price),
                    "bankruptCommRv": "0.0000006",
                    "bankruptPriceRp": "0.1",
                    "buyLeavesQty": "0",
                    "buyLeavesValueRv": "0",
                    "buyValueToCostRr": "0.10114",
                    "createdAtNs": 0,
                    "crossSharedBalanceRv": "1165.319989135354",
                    "cumClosedPnlRv": "0",
                    "cumFundingFeeRv": "0.089061821453",
                    "cumTransactFeeRv": "0.57374652",
                    "curTermRealisedPnlRv": "-0.662808341453",
                    "currency": "USDT",
                    "dataVer": 11,
                    "deleveragePercentileRr": "0",
                    "displayLeverageRr": "0.79941382",
                    "estimatedOrdLossRv": "0",
                    "execSeq": 77751555,
                    "freeCostRv": "0",
                    "freeQty": "-0.046",
                    "initMarginReqRr": "0.1",
                    "lastFundingTime": 1666857600000000000,
                    "lastTermEndTime": 0,
                    "leverageRr": str(order.leverage),
                    "liquidationPriceRp": "0.1",
                    "maintMarginReqRr": "0.01",
                    "makerFeeRateRr": "-1",
                    "markPriceRp": "20735.47347096",
                    "minPosCostRv": "0",
                    "orderCostRv": "0",
                    "posCostRv": "30.284669572349",
                    "posMode": "Oneway",
                    "posSide": "Merged",
                    "positionMarginRv": "1196.181723398102",
                    "positionStatus": "Normal",
                    "riskLimitRv": "1000000",
                    "sellLeavesQty": "0",
                    "sellLeavesValueRv": "0",
                    "sellValueToCostRr": "0.10126",
                    "side": "Sell",
                    "size": str(order.amount),
                    "symbol": self.exchange_trading_pair,
                    "takerFeeRateRr": "-1",
                    "term": 1,
                    "transactTimeNs": 1666858780881545305,
                    "unrealisedPnlRv": str(unrealized_pnl),
                    "updatedAtNs": 0,
                    "usedBalanceRv": "30.861734862748",
                    "userID": 932867,
                    "valueRv": "956.2442",
                }
            ],
            "sequence": 68744,
            "timestamp": 1666858780883525030,
            "type": "incremental",
            "version": 0,
        }

    def configure_successful_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.private_rest_url(path_url=CONSTANTS.POSITION_MODE)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"code": 0, "data": "", "msg": ""}
        mock_api.put(regex_url, body=json.dumps(response), callback=callback)

        return url

    def configure_failed_set_position_mode(
        self,
        position_mode: PositionMode,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.private_rest_url(path_url=CONSTANTS.POSITION_MODE)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"code": -1, "data": "", "msg": "Error."}
        mock_api.put(regex_url, body=json.dumps(response), callback=callback)

        return url, response["msg"]

    def configure_failed_set_leverage(
        self, leverage: int, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> Tuple[str, str]:
        url = web_utils.private_rest_url(path_url=CONSTANTS.POSITION_LEVERAGE)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"code": -1, "data": "", "msg": "Error."}
        mock_api.put(regex_url, body=json.dumps(response), callback=callback)

        return url, response["msg"]

    def configure_successful_set_leverage(
        self, leverage: int, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        url = web_utils.private_rest_url(path_url=CONSTANTS.POSITION_LEVERAGE)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"code": 0, "data": "", "msg": ""}
        mock_api.put(regex_url, body=json.dumps(response), callback=callback)

        return url

    def funding_info_event_for_websocket_update(self):
        return {
            "data": [
                [
                    self.exchange_trading_pair,
                    "1533.72",
                    "1594.17",
                    "1510.05",
                    "1547.52",
                    "545942.34",
                    "848127644.5712",
                    "0",
                    "1548.31694379",
                    "1548.44513153",
                    "0.0001",
                    "0.0001",
                ]
            ],
            "fields": [
                "symbol",
                "openRp",
                "highRp",
                "lowRp",
                "lastRp",
                "volumeRq",
                "turnoverRv",
                "openInterestRv",
                "indexRp",
                "markRp",
                "fundingRateRr",
                "predFundingRateRr",
            ],
            "method": "perp_market24h_pack_p.update",
            "timestamp": 1666862556850547000,
            "type": "snapshot",
        }

    def test_get_buy_and_sell_collateral_tokens(self):
        return "USDT"

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return regex_url

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL)

    @property
    def trading_rules_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL)

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
                        "assetsPrecision": 8,
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
                        "tickSize": 1.0e-4,
                        "priceScale": 4,
                        "ratioScale": 8,
                        "pricePrecision": 4,
                        "minPriceEp": 1,
                        "maxPriceEp": 2000000,
                        "maxOrderQty": 500000,
                        "description": (
                            "XRP/USD perpetual contracts are priced on the .XRP Index. Each contract is "
                            "worth 5 XRP. Funding fees are paid and received every 8 hours at UTC "
                            "time: 00:00, 08:00 and 16:00."
                        ),
                        "status": "Listed",
                        "tipOrderQty": 100000,
                        "listTime": 1574650800000,
                        "majorSymbol": False,
                        "defaultLeverage": "-10",
                        "fundingInterval": 28800,
                        "maxLeverage": 100,
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
                        "description": (
                            "ETH/USDT perpetual contracts are priced on the .ETHUSDT Index. Each contract "
                            "is worth 1 ETH. Funding fees are paid and received every 8 hours at UTC "
                            "time: 00:00, 08:00 and 16:00."
                        ),
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
                        "tipOrderQtyRq": "100000",
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
                                "maintenanceMarginEr": 500000,
                            },
                            {
                                "limit": 150,
                                "initialMargin": "1.5%",
                                "initialMarginEr": 1500000,
                                "maintenanceMargin": "1.0%",
                                "maintenanceMarginEr": 1000000,
                            },
                            {
                                "limit": 200,
                                "initialMargin": "2.0%",
                                "initialMarginEr": 2000000,
                                "maintenanceMargin": "1.5%",
                                "maintenanceMarginEr": 1500000,
                            },
                            {
                                "limit": 250,
                                "initialMargin": "2.5%",
                                "initialMarginEr": 2500000,
                                "maintenanceMargin": "2.0%",
                                "maintenanceMarginEr": 2000000,
                            },
                            {
                                "limit": 300,
                                "initialMargin": "3.0%",
                                "initialMarginEr": 3000000,
                                "maintenanceMargin": "2.5%",
                                "maintenanceMarginEr": 2500000,
                            },
                            {
                                "limit": 350,
                                "initialMargin": "3.5%",
                                "initialMarginEr": 3500000,
                                "maintenanceMargin": "3.0%",
                                "maintenanceMarginEr": 3000000,
                            },
                            {
                                "limit": 400,
                                "initialMargin": "4.0%",
                                "initialMarginEr": 4000000,
                                "maintenanceMargin": "3.5%",
                                "maintenanceMarginEr": 3500000,
                            },
                            {
                                "limit": 450,
                                "initialMargin": "4.5%",
                                "initialMarginEr": 4500000,
                                "maintenanceMargin": "4.0%",
                                "maintenanceMarginEr": 4000000,
                            },
                            {
                                "limit": 500,
                                "initialMargin": "5.0%",
                                "initialMarginEr": 5000000,
                                "maintenanceMargin": "4.5%",
                                "maintenanceMarginEr": 4500000,
                            },
                            {
                                "limit": 550,
                                "initialMargin": "5.5%",
                                "initialMarginEr": 5500000,
                                "maintenanceMargin": "5.0%",
                                "maintenanceMarginEr": 5000000,
                            },
                        ],
                    },
                ],
                "riskLimitsV2": [
                    {
                        "symbol": "BTCUSDT",
                        "steps": "2000K",
                        "riskLimits": [
                            {"limit": 2000000, "initialMarginRr": "0.01", "maintenanceMarginRr": "0.005"},
                            {"limit": 4000000, "initialMarginRr": "0.015", "maintenanceMarginRr": "0.0075"},
                            {"limit": 6000000, "initialMarginRr": "0.02", "maintenanceMarginRr": "0.01"},
                            {"limit": 8000000, "initialMarginRr": "0.025", "maintenanceMarginRr": "0.0125"},
                            {"limit": 10000000, "initialMarginRr": "0.03", "maintenanceMarginRr": "0.015"},
                            {"limit": 12000000, "initialMarginRr": "0.035", "maintenanceMarginRr": "0.0175"},
                            {"limit": 14000000, "initialMarginRr": "0.04", "maintenanceMarginRr": "0.02"},
                            {"limit": 16000000, "initialMarginRr": "0.045", "maintenanceMarginRr": "0.0225"},
                            {"limit": 18000000, "initialMarginRr": "0.05", "maintenanceMarginRr": "0.025"},
                            {"limit": 20000000, "initialMarginRr": "0.055", "maintenanceMarginRr": "0.0275"},
                        ],
                    },
                ],
                "ratioScale": 8,
                "md5Checksum": "1c894ae8fa2f98163af663e288752ad4",
            },
        }

    @property
    def latest_prices_request_mock_response(self):
        return {"code": 0, "msg": "OK", "data": {"total": -1, "rows": [[0, 0, 1]]}}

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
            "description": (
                "ETH/USDT perpetual contracts are priced on the .ETHUSDT Index. Each contract "
                "is worth 1 ETH. Funding fees are paid and received every 8 hours at UTC "
                "time: 00:00, 08:00 and 16:00."
            ),
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
            "tipOrderQtyRq": "100000",
        }
        response["data"]["perpProductsV2"].append(invalid_product)

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {"code": 0, "msg": "", "data": {"serverTime": 1680564306718}}

    @property
    def trading_rules_request_mock_response(self):
        return {
            "code": 0,
            "msg": "",
            "data": {
                "perpProductsV2": [
                    {
                        "symbol": self.exchange_trading_pair,
                        "code": 41541,
                        "type": "PerpetualV2",
                        "displaySymbol": "COINALPHA / USDT",
                        "indexSymbol": ".COINALPHAUSDT",
                        "markSymbol": ".MCOINALPHAUSDT",
                        "fundingRateSymbol": ".BCOINALPHAUSDTFR",
                        "fundingRate8hSymbol": ".BTCUSDTFR8H",
                        "contractUnderlyingAssets": "COINALPHA",
                        "settleCurrency": "USDT",
                        "quoteCurrency": "USDT",
                        "tickSize": "0.1",
                        "priceScale": 0,
                        "ratioScale": 0,
                        "pricePrecision": 1,
                        "baseCurrency": "COINALPHA",
                        "description": "COINALPHA/USDT perpetual contracts are priced on the .BTCUSDT Index. Each contract is worth 1 BTC. Funding fees are paid and received every 8 hours at UTC time: 00:00, 08:00 and 16:00.",
                        "status": "Listed",
                        "tipOrderQty": 0,
                        "listTime": 1668225600000,
                        "majorSymbol": True,
                        "defaultLeverage": "-10",
                        "fundingInterval": 28800,
                        "maxLeverage": 100,
                        "maxOrderQtyRq": "100000",
                        "maxPriceRp": "2000000000",
                        "minOrderValueRv": "1",
                        "minPriceRp": "1000.0",
                        "qtyPrecision": 3,
                        "qtyStepSize": "0.001",
                        "tipOrderQtyRq": "20000",
                    }
                ],
                "ratioScale": 8,
                "md5Checksum": "e90521d639d35356ccb76643d0b7e57c",
            },
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "code": -1,
            "data": {
                "perpProductsV2": [
                    {
                        "symbol": self.exchange_trading_pair,
                        "code": 41541,
                        "type": "PerpetualV2",
                        "displaySymbol": "COINALPHA / USDT",
                        "indexSymbol": ".COINALPHAUSDT",
                        "markSymbol": ".MCOINALPHAUSDT",
                        "fundingRateSymbol": ".BCOINALPHAUSDTFR",
                        "fundingRate8hSymbol": ".BTCUSDTFR8H",
                        "contractUnderlyingAssets": "COINALPHA",
                        "settleCurrency": "USDT",
                        "quoteCurrency": "USDT",
                        "tickSize": "0.1",
                        "priceScale": 0,
                        "ratioScale": 0,
                        "pricePrecision": 1,
                        "baseCurrency": "COINALPHA",
                        "description": "COINALPHA/USDT perpetual contracts are priced on the .BTCUSDT Index. Each contract is worth 1 BTC. Funding fees are paid and received every 8 hours at UTC time: 00:00, 08:00 and 16:00.",
                        "status": "Listed",
                        "tipOrderQty": 0,
                        "listTime": 1668225600000,
                        "majorSymbol": True,
                        "defaultLeverage": "-10",
                        "fundingInterval": 28800,
                        "maxLeverage": 100,
                        "maxOrderQtyRq": "100000",
                        "maxPriceRp": "2000000000",
                        "minOrderValueRv": "1",
                        "minPriceRp": "1000.0",
                        "qtyPrecision": 3,
                        "qtyStepSize": "ERROR",
                        "tipOrderQtyRq": "20000",
                    }
                ],
            },
            "msg": "Unable to set position mode.",
        }

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
                "trigger": "ByMarkPrice",
            },
            "msg": "",
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
                    "bonusBalanceRv": "0",
                },
                "positions": [],
            },
        }

    @property
    def balance_request_mock_response_only_base(self):
        return self.balance_request_mock_response_for_base_and_quote

    @property
    def balance_event_websocket_update(self):
        return {
            "accounts_p": [
                {
                    "accountBalanceRv": "15",
                    "accountID": 9328670003,
                    "bonusBalanceRv": "0",
                    "currency": self.base_asset,
                    "totalUsedBalanceRv": "5",
                    "userID": 932867,
                }
            ],
            "sequence": 68744,
            "timestamp": 1666858780883525030,
            "type": "incremental",
            "version": 0,
        }

    @property
    def expected_latest_price(self):
        return Decimal("1.0")

    @property
    def expected_supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        trading_rules_resp = self.trading_rules_request_mock_response["data"]["perpProductsV2"][0]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(str(trading_rules_resp["qtyStepSize"])),
            min_price_increment=Decimal(str(trading_rules_resp["tickSize"])),
            min_base_amount_increment=Decimal(str(trading_rules_resp["qtyStepSize"])),
            min_notional_size=Decimal(str(trading_rules_resp["minOrderValueRv"])),
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"]["perpProductsV2"][0]
        return f"Error parsing the trading pair rule: {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "ab90a08c-b728-4b6b-97c4-36fa497335bf"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return True

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
        if self.exchange.position_mode == PositionMode.ONEWAY:
            position_side = "Merged"
        else:
            if order.position in [PositionAction.OPEN, PositionAction.NIL]:
                position_side = "Long" if order.trade_type == TradeType.BUY else "Short"
            else:
                position_side = "Short" if order.trade_type == TradeType.BUY else "Long"
        self.assertEqual(position_side, request_data["posSide"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]

        if self.exchange._position_mode is PositionMode.ONEWAY:
            posSide = "Merged"
        else:
            if order.position is PositionAction.OPEN:
                posSide = "Long" if order.trade_type is TradeType.BUY else "Short"
            else:
                posSide = "Short" if order.trade_type is TradeType.BUY else "Long"
        self.assertEqual(order.client_order_id, request_params["clOrdID"])
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(posSide, request_params["posSide"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(200, request_params["limit"])
        self.assertIn("start", request_params)

    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CANCEL_ORDERS)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_cancel_all_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = {
            "code": 0 if order.trading_pair == self.trading_pair else 10003,
            "msg": "",
        }
        url = web_utils.private_rest_url(path_url=CONSTANTS.CANCEL_ALL_ORDERS)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CANCEL_ORDERS)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {
            "code": 10003,
            "msg": "OM_ORDER_PENDING_CANCEL",
        }
        mock_api.delete(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
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
        self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[str]:
        all_urls = []
        url = self.configure_cancel_all_response(order=successful_order, mock_api=mock_api)
        all_urls.append(url)
        url = self.configure_cancel_all_response(order=erroneous_order, mock_api=mock_api)
        all_urls.append(url)
        return all_urls

    def configure_completely_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> Union[str, List[str]]:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_open_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_ORDERS)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_TRADES)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_TRADES)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_full_fill_trade_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.GET_TRADES)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "orders_p": [
                {
                    "accountID": 9328670003,
                    "action": "New",
                    "actionBy": "ByUser",
                    "actionTimeNs": 1666858780876924611,
                    "addedSeq": 77751555,
                    "apRp": "0",
                    "bonusChangedAmountRv": "0",
                    "bpRp": "0",
                    "clOrdID": order.client_order_id,
                    "closedPnlRv": "0",
                    "closedSize": "0",
                    "code": 0,
                    "cumFeeRv": "0",
                    "cumQty": "0",
                    "cumValueRv": "0",
                    "curAccBalanceRv": "1508.489893982237",
                    "curAssignedPosBalanceRv": "24.62786650928",
                    "curBonusBalanceRv": "0",
                    "curLeverageRr": "-10",
                    "curPosSide": order.trade_type.name.capitalize(),
                    "curPosSize": "0.043",
                    "curPosTerm": 1,
                    "curPosValueRv": "894.0689",
                    "curRiskLimitRv": "1000000",
                    "currency": "USDT",
                    "cxlRejReason": 0,
                    "displayQty": "0.003",
                    "execFeeRv": "0",
                    "execID": "00000000-0000-0000-0000-000000000000",
                    "execPriceRp": "20723.7",
                    "execQty": "0",
                    "execSeq": 77751555,
                    "execStatus": "New",
                    "execValueRv": "0",
                    "feeRateRr": "0",
                    "leavesQty": "0.003",
                    "leavesValueRv": "63.4503",
                    "message": "No error",
                    "ordStatus": "New",
                    "ordType": "Market",
                    "orderID": order.exchange_order_id,
                    "orderQty": "0.003",
                    "pegOffsetValueRp": "0",
                    "posSide": "Long",
                    "priceRp": "21150.1",
                    "relatedPosTerm": 1,
                    "relatedReqNum": 11,
                    "side": "Buy",
                    "slTrigger": "ByMarkPrice",
                    "stopLossRp": "0",
                    "stopPxRp": "0",
                    "symbol": self.exchange_trading_pair,
                    "takeProfitRp": "0",
                    "timeInForce": "ImmediateOrCancel",
                    "tpTrigger": "ByLastPrice",
                    "tradeType": "Amend",
                    "transactTimeNs": 1666858780881545305,
                    "userID": 932867,
                }
            ],
            "sequence": 68744,
            "timestamp": 1666858780883525030,
            "type": "incremental",
            "version": 0,
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "orders_p": [
                {
                    "accountID": 9328670003,
                    "action": "Canceled",
                    "actionBy": "ByUser",
                    "actionTimeNs": 1666858780876924611,
                    "addedSeq": 77751555,
                    "apRp": "0",
                    "bonusChangedAmountRv": "0",
                    "bpRp": "0",
                    "clOrdID": order.client_order_id,
                    "closedPnlRv": "0",
                    "closedSize": "0",
                    "code": 0,
                    "cumFeeRv": "0",
                    "cumQty": "0",
                    "cumValueRv": "0",
                    "curAccBalanceRv": "1508.489893982237",
                    "curAssignedPosBalanceRv": "24.62786650928",
                    "curBonusBalanceRv": "0",
                    "curLeverageRr": "-10",
                    "curPosSide": order.trade_type.name.capitalize(),
                    "curPosSize": "0.043",
                    "curPosTerm": 1,
                    "curPosValueRv": "894.0689",
                    "curRiskLimitRv": "1000000",
                    "currency": "USDT",
                    "cxlRejReason": 0,
                    "displayQty": "0.003",
                    "execFeeRv": "0",
                    "execID": "00000000-0000-0000-0000-000000000000",
                    "execPriceRp": "20723.7",
                    "execQty": "0",
                    "execSeq": 77751555,
                    "execStatus": "New",
                    "execValueRv": "0",
                    "feeRateRr": "0",
                    "leavesQty": "0.003",
                    "leavesValueRv": "63.4503",
                    "message": "No error",
                    "ordStatus": "Canceled",
                    "ordType": "Market",
                    "orderID": order.exchange_order_id,
                    "orderQty": "0.003",
                    "pegOffsetValueRp": "0",
                    "posSide": "Long",
                    "priceRp": "21150.1",
                    "relatedPosTerm": 1,
                    "relatedReqNum": 11,
                    "side": "Buy",
                    "slTrigger": "ByMarkPrice",
                    "stopLossRp": "0",
                    "stopPxRp": "0",
                    "symbol": self.exchange_trading_pair,
                    "takeProfitRp": "0",
                    "timeInForce": "ImmediateOrCancel",
                    "tpTrigger": "ByLastPrice",
                    "tradeType": "Amend",
                    "transactTimeNs": 1666858780881545305,
                    "userID": 932867,
                }
            ],
            "sequence": 68744,
            "timestamp": 1666858780883525030,
            "type": "incremental",
            "version": 0,
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "orders_p": [
                {
                    "accountID": 9328670003,
                    "action": "Filled",
                    "actionBy": "ByUser",
                    "actionTimeNs": 1666858780876924611,
                    "addedSeq": 77751555,
                    "apRp": "0",
                    "bonusChangedAmountRv": "0",
                    "bpRp": "0",
                    "clOrdID": order.client_order_id,
                    "closedPnlRv": "0",
                    "closedSize": "0",
                    "code": 0,
                    "cumFeeRv": "0",
                    "cumQty": "0",
                    "cumValueRv": "0",
                    "curAccBalanceRv": "1508.489893982237",
                    "curAssignedPosBalanceRv": "24.62786650928",
                    "curBonusBalanceRv": "0",
                    "curLeverageRr": "-10",
                    "curPosSide": order.trade_type.name.capitalize(),
                    "curPosSize": "0.043",
                    "curPosTerm": 1,
                    "curPosValueRv": "894.0689",
                    "curRiskLimitRv": "1000000",
                    "currency": "USDT",
                    "cxlRejReason": 0,
                    "displayQty": "0.003",
                    "execFeeRv": "0",
                    "execID": "00000000-0000-0000-0000-000000000000",
                    "execPriceRp": "20723.7",
                    "execQty": "0",
                    "execSeq": 77751555,
                    "execStatus": "New",
                    "execValueRv": "0",
                    "feeRateRr": "0",
                    "leavesQty": "0.003",
                    "leavesValueRv": "63.4503",
                    "message": "No error",
                    "ordStatus": "Filled",
                    "ordType": "Market",
                    "orderID": order.exchange_order_id,
                    "orderQty": "0.003",
                    "pegOffsetValueRp": "0",
                    "posSide": "Long",
                    "priceRp": "21150.1",
                    "relatedPosTerm": 1,
                    "relatedReqNum": 11,
                    "side": "Buy",
                    "slTrigger": "ByMarkPrice",
                    "stopLossRp": "0",
                    "stopPxRp": "0",
                    "symbol": self.exchange_trading_pair,
                    "takeProfitRp": "0",
                    "timeInForce": "ImmediateOrCancel",
                    "tpTrigger": "ByLastPrice",
                    "tradeType": "Amend",
                    "transactTimeNs": 1666858780881545305,
                    "userID": 932867,
                }
            ],
            "sequence": 68744,
            "timestamp": 1666858780883525030,
            "type": "incremental",
            "version": 0,
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "orders_p": [
                {
                    "accountID": 9328670003,
                    "action": "Filled",
                    "actionBy": "ByUser",
                    "actionTimeNs": 1666858780876924611,
                    "addedSeq": 77751555,
                    "apRp": "0",
                    "bonusChangedAmountRv": "0",
                    "bpRp": "0",
                    "clOrdID": order.client_order_id,
                    "closedPnlRv": "0",
                    "closedSize": "0",
                    "code": 0,
                    "cumFeeRv": "0",
                    "cumQty": "0",
                    "cumValueRv": "0",
                    "curAccBalanceRv": "1508.489893982237",
                    "curAssignedPosBalanceRv": "24.62786650928",
                    "curBonusBalanceRv": "0",
                    "curLeverageRr": "-10",
                    "curPosSide": order.trade_type.name.capitalize(),
                    "curPosSize": "0.043",
                    "curPosTerm": 1,
                    "curPosValueRv": "894.0689",
                    "curRiskLimitRv": "1000000",
                    "currency": "USDT",
                    "cxlRejReason": 0,
                    "displayQty": "0.003",
                    "execFeeRv": str(self.expected_fill_fee.flat_fees[0].amount),
                    "execID": "00000000-0000-0000-0000-000000000000",
                    "execPriceRp": "10000",
                    "execQty": str(order.amount),
                    "execSeq": 77751555,
                    "execStatus": "New",
                    "execValueRv": "10000",
                    "feeRateRr": "0",
                    "leavesQty": "0.003",
                    "leavesValueRv": "63.4503",
                    "message": "No error",
                    "ordStatus": "Filled",
                    "ordType": "Market",
                    "orderID": order.exchange_order_id,
                    "orderQty": "0.003",
                    "pegOffsetValueRp": "0",
                    "posSide": "Long",
                    "priceRp": "21150.1",
                    "relatedPosTerm": 1,
                    "relatedReqNum": 11,
                    "side": "Buy",
                    "slTrigger": "ByMarkPrice",
                    "stopLossRp": "0",
                    "stopPxRp": "0",
                    "symbol": self.exchange_trading_pair,
                    "takeProfitRp": "0",
                    "timeInForce": "ImmediateOrCancel",
                    "tpTrigger": "ByLastPrice",
                    "tradeType": "Amend",
                    "transactTimeNs": 1666858780881545305,
                    "userID": 932867,
                }
            ],
            "sequence": 68744,
            "timestamp": 1666858780883525030,
            "type": "incremental",
            "version": 0,
        }

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
                "trigger": "ByMarkPrice",
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
                        "bizError": 0,
                    }
                ]
            },
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
                        "bizError": 0,
                    }
                ]
            },
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
                        "bizError": 0,
                    }
                ]
            },
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
                        "leavesValueRv": str(
                            (order.amount * order.price)
                            - (self.expected_partial_fill_amount * self.expected_partial_fill_price)
                        ),
                        "stopDirection": "UNSPECIFIED",
                        "ordStatus": "PartiallyFilled",
                        "transactTimeNs": 1667562110221077395,
                        "bizError": 0,
                    }
                ]
            },
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "code": 0,
            "msg": "OK",
            "data": {
                "rows": [
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
                        "transactTimeNs": 1669407633926215067,
                    }
                ]
            },
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "code": 0,
            "msg": "OK",
            "data": {
                "rows": [
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
                        "transactTimeNs": 1669407633926215067,
                    }
                ]
            },
        }

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        mark_regex_url = re.compile(
            f"^{web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_URL)}".replace(".", r"\.").replace("?", r"\?")
        )
        resp = self.funding_info_mock_response
        mock_api.get(mark_regex_url, body=json.dumps(resp))

        funding_info_event = self.funding_info_event_for_websocket_update()

        event_messages = [funding_info_event, asyncio.CancelledError]
        mock_queue_get.side_effect = event_messages

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, self.exchange._perpetual_trading.funding_info_stream.qsize())  # rest in OB DS tests

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        mark_regex_url = re.compile(
            f"^{web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_URL)}".replace(".", r"\.").replace("?", r"\?")
        )
        resp = self.funding_info_mock_response
        mock_api.get(mark_regex_url, body=json.dumps(resp))

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
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order1 = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.exchange.start_tracking_order(
            order_id="12",
            exchange_order_id="5",
            trading_pair="ABC-DEF",
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("12", self.exchange.in_flight_orders)
        order2 = self.exchange.in_flight_orders["12"]

        urls = self.configure_one_successful_one_erroneous_cancel_all_response(
            successful_order=order1, erroneous_order=order2, mock_api=mock_api
        )

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        for url in urls:
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)

        self.assertEqual(2, len(cancellation_results))
        self.assertEqual(CancellationResult(order1.client_order_id, True), cancellation_results[0])
        self.assertEqual(CancellationResult(order2.client_order_id, False), cancellation_results[1])

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertEqual(1, len(self.order_cancelled_logger.event_log))
            cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
            self.assertEqual(order1.client_order_id, cancel_event.order_id)

            self.assertTrue(self.is_logged("INFO", f"Successfully canceled order {order1.client_order_id}."))
