import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase, TradeFeeSchema


class BitgetPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "test_api_key"
        cls.api_secret = "test_secret_key"
        cls.passphrase = "test_passphrase"
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        return regex_url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TICKER_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        return regex_url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TIME_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        return regex_url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        return regex_url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.PLACE_ORDER_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        return regex_url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.ACCOUNTS_INFO_ENDPOINT)

        return url

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_FUNDING_RATE_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        return regex_url

    @property
    def funding_payment_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.ACCOUNT_BILLS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        return regex_url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695793701269,
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "baseCoin": self.base_asset,
                    "quoteCoin": self.quote_asset,
                    "buyLimitPriceRatio": "0.9",
                    "sellLimitPriceRatio": "0.9",
                    "feeRateUpRatio": "0.1",
                    "makerFeeRate": "0.0004",
                    "takerFeeRate": "0.0006",
                    "openCostUpRatio": "0.1",
                    "supportMarginCoins": [
                        self.quote_asset
                    ],
                    "minTradeNum": "0.01",
                    "priceEndStep": "1",
                    "volumePlace": "2",
                    "pricePlace": "4",  # price as 10000.0000
                    "sizeMultiplier": "0.000001",  # size as 100.000000
                    "symbolType": "perpetual",
                    "minTradeUSDT": "5",
                    "maxSymbolOrderNum": "999999",
                    "maxProductOrderNum": "999999",
                    "maxPositionNum": "150",
                    "symbolStatus": "normal",
                    "offTime": "-1",
                    "limitOpenTime": "-1",
                    "deliveryTime": "",
                    "deliveryStartTime": "",
                    "launchTime": "",
                    "fundInterval": "8",
                    "minLever": "1",
                    "maxLever": "125",
                    "posLimit": "0.05",
                    "maintainTime": "1680165535278",
                    "maxMarketOrderQty": "220",
                    "maxOrderQty": "1200"
                }
            ]
        }

    @property
    def _all_usd_symbols_request_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695793701269,
            "data": [
                {
                    "symbol": f"{self.base_asset}USD",
                    "baseCoin": self.base_asset,
                    "quoteCoin": "USD",
                    "buyLimitPriceRatio": "0.9",
                    "sellLimitPriceRatio": "0.9",
                    "feeRateUpRatio": "0.1",
                    "makerFeeRate": "0.0004",
                    "takerFeeRate": "0.0006",
                    "openCostUpRatio": "0.1",
                    "supportMarginCoins": [
                        "BTC", "ETH", "USDC", "XRP", "BGB"
                    ],
                    "minTradeNum": "0.01",
                    "priceEndStep": "1",
                    "volumePlace": "2",
                    "pricePlace": "4",  # price as 10000.0000
                    "sizeMultiplier": "0.000001",  # size as 100.000000
                    "symbolType": "perpetual",
                    "minTradeUSDT": "5",
                    "maxSymbolOrderNum": "999999",
                    "maxProductOrderNum": "999999",
                    "maxPositionNum": "150",
                    "symbolStatus": "normal",
                    "offTime": "-1",
                    "limitOpenTime": "-1",
                    "deliveryTime": "",
                    "deliveryStartTime": "",
                    "launchTime": "",
                    "fundInterval": "8",
                    "minLever": "1",
                    "maxLever": "125",
                    "posLimit": "0.05",
                    "maintainTime": "1680165535278",
                    "maxMarketOrderQty": "220",
                    "maxOrderQty": "1200"
                }
            ]
        }

    @property
    def _all_usdc_symbols_request_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695793701269,
            "data": [
                {
                    "symbol": f"{self.base_asset}PERP",
                    "baseCoin": self.base_asset,
                    "quoteCoin": "USDC",
                    "buyLimitPriceRatio": "0.9",
                    "sellLimitPriceRatio": "0.9",
                    "feeRateUpRatio": "0.1",
                    "makerFeeRate": "0.0004",
                    "takerFeeRate": "0.0006",
                    "openCostUpRatio": "0.1",
                    "supportMarginCoins": [
                        "USDC"
                    ],
                    "minTradeNum": "0.01",
                    "priceEndStep": "1",
                    "volumePlace": "2",
                    "pricePlace": "4",  # price as 10000.0000
                    "sizeMultiplier": "0.000001",  # size as 100.000000
                    "symbolType": "perpetual",
                    "minTradeUSDT": "5",
                    "maxSymbolOrderNum": "999999",
                    "maxProductOrderNum": "999999",
                    "maxPositionNum": "150",
                    "symbolStatus": "normal",
                    "offTime": "-1",
                    "limitOpenTime": "-1",
                    "deliveryTime": "",
                    "deliveryStartTime": "",
                    "launchTime": "",
                    "fundInterval": "8",
                    "minLever": "1",
                    "maxLever": "125",
                    "posLimit": "0.05",
                    "maintainTime": "1680165535278",
                    "maxMarketOrderQty": "220",
                    "maxOrderQty": "1200"
                }
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695794269124,
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "lastPr": "29904.5",
                    "askPr": "29904.5",
                    "bidPr": "29903.5",
                    "bidSz": "0.5091",
                    "askSz": "2.2694",
                    "high24h": "0",
                    "low24h": "0",
                    "ts": "1695794271400",
                    "change24h": "0",
                    "baseVolume": "0",
                    "quoteVolume": "0",
                    "usdtVolume": "0",
                    "openUtc": "0",
                    "changeUtc24h": "0",
                    "indexPrice": "29132.353333",
                    "fundingRate": "-0.0007",
                    "holdingAmount": "125.6844",
                    "deliveryStartTime": "1693538723186",
                    "deliveryTime": "1703836799000",
                    "deliveryStatus": "delivery_normal",
                    "open24h": "0",
                    "markPrice": "12345"
                }
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        mock_response = self.all_symbols_request_mock_response
        return "INVALID-PAIR", mock_response

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
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695793701269,
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "baseCoin": self.base_asset,
                    "quoteCoin": self.quote_asset,
                }
            ]
        }

    @property
    def set_position_mode_request_mock_response(self):
        """
        :return: the mock response for the set position mode request
        """
        return {
            "code": "00000",
            "msg": "success",
            "data": {
                "symbol": self.exchange_trading_pair,
                "marginCoin": self.quote_asset,
                "longLeverage": "25",
                "shortLeverage": "20",
                "marginMode": "crossed"
            },
            "requestTime": 1627293445916
        }

    @property
    def set_leverage_request_mock_response(self):
        """
        :return: the mock response for the set leverage request
        """
        return {
            "code": "00000",
            "data": {
                "symbol": self.exchange_trading_pair,
                "marginCoin": self.quote_asset,
                "longLeverage": "25",
                "shortLeverage": "20",
                "crossMarginLeverage": "20",
                "marginMode": "crossed"
            },
            "msg": "success",
            "requestTime": 1627293049406
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695806875837,
            "data": {
                "clientOid": "1627293504612",
                "orderId": "1627293504612"
            }
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "code": "00000",
            "data": [
                {
                    "marginCoin": self.quote_asset,
                    "locked": "0",
                    "available": "2000",
                    "crossedMaxAvailable": "2000",
                    "isolatedMaxAvailable": "2000",
                    "maxTransferOut": "10572.92904289",
                    "accountEquity": "2000",
                    "usdtEquity": "10582.902657719473",
                    "btcEquity": "0.204885807029",
                    "crossedRiskRate": "0",
                    "unrealizedPL": "",
                    "coupon": "0",
                    "unionTotalMagin": "111,1",
                    "unionAvailable": "1111.1",
                    "unionMm": "111",
                    "assetList": [
                        {
                            "coin": self.base_asset,
                            "balance": "15",
                            "available": "10"
                        }
                    ],
                    "isolatedMargin": "23.43",
                    "crossedMargin": "34.34",
                    "crossedUnrealizedPL": "23",
                    "isolatedUnrealizedPL": "0",
                    "assetMode": "union"
                }
            ],
            "msg": "success",
            "requestTime": 1630901215622
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "code": "00000",
            "data": [
                {
                    "marginCoin": self.base_asset,
                    "locked": "5",
                    "available": "10",
                    "crossedMaxAvailable": "10",
                    "isolatedMaxAvailable": "10",
                    "maxTransferOut": "10572.92904289",
                    "accountEquity": "15",
                    "usdtEquity": "10582.902657719473",
                    "btcEquity": "0.204885807029",
                    "crossedRiskRate": "0",
                    "unrealizedPL": "",
                    "coupon": "0",
                    "unionTotalMagin": "111,1",
                    "unionAvailable": "1111.1",
                    "unionMm": "111",
                    "assetList": [],
                    "isolatedMargin": "23.43",
                    "crossedMargin": "34.34",
                    "crossedUnrealizedPL": "23",
                    "isolatedUnrealizedPL": "0",
                    "assetMode": "union"
                }
            ],
            "msg": "success",
            "requestTime": 1630901215622
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "action": "snapshot",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": CONSTANTS.WS_ACCOUNT_ENDPOINT,
                "coin": "default"
            },
            "data": [
                {
                    "marginCoin": self.base_asset,
                    "frozen": "0.00000000",
                    "available": "10",
                    "maxOpenPosAvailable": "10",
                    "maxTransferOut": "10",
                    "equity": "15",
                    "usdtEquity": "11.985457617660",
                    "crossedRiskRate": "0",
                    "unrealizedPL": "0.000000000000",
                    "unionTotalMargin": "100",
                    "unionAvailable": "20",
                    "unionMm": "15",
                    "assetMode": "union"
                }
            ],
            "ts": 1695717225146
        }

    @property
    def expected_latest_price(self):
        return 29904.5

    @property
    def empty_funding_payment_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695809161807,
            "data": {
                "bills": []
            },
            "endId": "0"
        }

    @property
    def funding_payment_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695809161807,
            "data": {
                "bills": [
                    {
                        "billId": "1",
                        "symbol": self.exchange_trading_pair,
                        "amount": str(self.target_funding_payment_payment_amount),
                        "fee": "0.1",
                        "feeByCoupon": "",
                        "businessType": "contract_settle_fee",
                        "coin": self.quote_asset,
                        "balance": "232.21",
                        "cTime": "1657110053000"
                    }
                ],
                "endId": "1"
            }
        }

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return list(CONSTANTS.POSITION_MODE_TYPES.keys())

    @property
    def target_funding_info_next_funding_utc_str(self):
        return self.target_funding_info_next_funding_utc_timestamp * 1e3

    @property
    def target_funding_info_next_funding_utc_str_ws_updated(self):
        return self.target_funding_info_next_funding_utc_timestamp_ws_updated * 1e3

    @property
    def target_funding_payment_timestamp_str(self):
        return self.target_funding_payment_timestamp * 1e3

    @property
    def funding_info_mock_response(self):
        return {
            "data": [{
                "indexPrice": self.target_funding_info_index_price,
                "markPrice": self.target_funding_info_mark_price,
                "nextUpdate": self.target_funding_info_next_funding_utc_str,
                "fundingRate": self.target_funding_info_rate,
            }]
        }

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        rule = self.trading_rules_request_mock_response["data"][0]
        collateral_token = rule["supportMarginCoins"][0]

        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_value=Decimal(rule.get("minTradeUSDT", "0")),
            max_order_size=Decimal(rule.get("maxOrderQty", "0")),
            min_order_size=Decimal(rule["minTradeNum"]),
            min_price_increment=Decimal(f"1e-{int(rule['pricePlace'])}"),
            min_base_amount_increment=Decimal(rule["sizeMultiplier"]),
            buy_order_collateral_token=collateral_token,
            sell_order_collateral_token=collateral_token,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing the trading pair rule: {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "1627293504612"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

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
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.1"))],
        )

    @property
    def expected_partial_fill_fee(self) -> TradeFeeBase:
        return self.expected_fill_fee

    @property
    def expected_fill_trade_id(self) -> str:
        return "xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6"

    @property
    def latest_trade_hist_timestamp(self) -> int:
        return 1234

    def _expected_valid_trading_pairs(self):
        return [self.trading_pair, "BTC-USD", "BTC-USDC"]

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        reversed_order_states = {v: k for k, v in CONSTANTS.STATE_TYPES.items()}
        current_state = reversed_order_states[order.current_state] \
            if order.current_state in reversed_order_states else "live"
        side = order.trade_type.name.lower()
        trade_side = f"{side}_single" if order.position is PositionAction.NIL else order.position.name.lower()

        return {
            "action": "snapshot",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                "instId": "default"
            },
            "data": [
                {
                    "accBaseVolume": "0.01",
                    "cTime": "1695718781129",
                    "clientOid": order.client_order_id or "",
                    "feeDetail": [
                        {
                            "feeCoin": self.quote_asset,
                            "fee": str(self.expected_partial_fill_fee.flat_fees[0].amount)
                        }
                    ],
                    "fillFee": str(self.expected_partial_fill_fee.flat_fees[0].amount),
                    "fillFeeCoin": self.quote_asset,
                    "fillNotionalUsd": "270.005",
                    "fillPrice": "0",
                    "baseVolume": "0.01",
                    "fillTime": "1695718781146",
                    "force": CONSTANTS.DEFAULT_TIME_IN_FORCE,
                    "instId": self.exchange_trading_pair,
                    "leverage": "20",
                    "marginCoin": self.quote_asset,
                    "marginMode": "crossed",
                    "notionalUsd": "270",
                    "orderId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "orderType": order.order_type.name.lower(),
                    "pnl": "0",
                    "posMode": "hedge_mode",
                    "posSide": "long",
                    "price": str(order.price),
                    "priceAvg": str(order.price),
                    "reduceOnly": "no",
                    "stpMode": "cancel_taker",
                    "side": side,
                    "size": str(order.amount),
                    "enterPointSource": "WEB",
                    "status": current_state,
                    "tradeScope": "T",
                    "tradeId": "1111111111",
                    "tradeSide": trade_side,
                    "presetStopSurplusPrice": "21.4",
                    "totalProfits": "11221.45",
                    "presetStopLossPrice": "21.5",
                    "cancelReason": "normal_cancel",
                    "uTime": "1695718781146"
                }
            ],
            "ts": 1695718781206
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "action": "snapshot",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                "instId": "default"
            },
            "data": [
                {
                    "accBaseVolume": "0.01",
                    "cTime": "1695718781129",
                    "clientOid": order.client_order_id,
                    "feeDetail": [
                        {
                            "feeCoin": self.quote_asset,
                            "fee": str(self.expected_partial_fill_fee.flat_fees[0].amount)
                        }
                    ],
                    "fillFee": str(self.expected_partial_fill_fee.flat_fees[0].amount),
                    "fillFeeCoin": self.quote_asset,
                    "fillNotionalUsd": "270.005",
                    "fillPrice": "0",
                    "baseVolume": "0.01",
                    "fillTime": "1695718781146",
                    "force": CONSTANTS.DEFAULT_TIME_IN_FORCE,
                    "instId": self.exchange_trading_pair,
                    "leverage": "20",
                    "marginCoin": self.quote_asset,
                    "marginMode": "crossed",
                    "notionalUsd": "270",
                    "orderId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "orderType": order.order_type.name.lower(),
                    "pnl": "0",
                    "posMode": "hedge_mode",
                    "posSide": "long",
                    "price": str(order.price),
                    "priceAvg": str(order.price),
                    "reduceOnly": "no",
                    "stpMode": "cancel_taker",
                    "side": order.trade_type.name.lower(),
                    "size": str(order.amount),
                    "enterPointSource": "WEB",
                    "status": "cancelled",
                    "tradeScope": "T",
                    "tradeId": "1111111111",
                    "tradeSide": "close",
                    "presetStopSurplusPrice": "21.4",
                    "totalProfits": "11221.45",
                    "presetStopLossPrice": "21.5",
                    "cancelReason": "normal_cancel",
                    "uTime": "1695718781146"
                }
            ],
            "ts": 1695718781206
        }

    def order_event_for_partially_canceled_websocket_update(self, order: InFlightOrder):
        return self.order_event_for_canceled_order_websocket_update(order=order)

    def order_event_for_partially_filled_websocket_update(self, order: InFlightOrder):
        return {
            "action": "snapshot",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                "instId": "default"
            },
            "data": [
                {
                    "accBaseVolume": str(self.expected_partial_fill_amount),
                    "cTime": "1695718781129",
                    "clientOid": order.client_order_id,
                    "feeDetail": [
                        {
                            "feeCoin": self.quote_asset,
                            "fee": str(self.expected_partial_fill_fee.flat_fees[0].amount)
                        }
                    ],
                    "fillFee": str(self.expected_partial_fill_fee.flat_fees[0].amount),
                    "fillFeeCoin": self.quote_asset,
                    "fillNotionalUsd": "270.005",
                    "fillPrice": str(self.expected_partial_fill_price),
                    "baseVolume": str(self.expected_partial_fill_amount),
                    "fillTime": "1695718781146",
                    "force": CONSTANTS.DEFAULT_TIME_IN_FORCE,
                    "instId": self.exchange_trading_pair,
                    "leverage": "20",
                    "marginCoin": self.quote_asset,
                    "marginMode": "crossed",
                    "notionalUsd": "270",
                    "orderId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "orderType": order.order_type.name.lower(),
                    "pnl": "0",
                    "posMode": "hedge_mode",
                    "posSide": "long",
                    "price": str(order.price),
                    "priceAvg": str(self.expected_partial_fill_price),
                    "reduceOnly": "no",
                    "stpMode": "cancel_taker",
                    "side": order.trade_type.name.lower(),
                    "size": str(order.amount),
                    "enterPointSource": "WEB",
                    "status": "partially_filled",
                    "tradeScope": "T",
                    "tradeId": "1111111111",
                    "tradeSide": "open",
                    "presetStopSurplusPrice": "21.4",
                    "totalProfits": "11221.45",
                    "presetStopLossPrice": "21.5",
                    "cancelReason": "normal_cancel",
                    "uTime": "1695718781146"
                }
            ],
            "ts": 1695718781206
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "action": "snapshot",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                "instId": "default"
            },
            "data": [
                {
                    "accBaseVolume": str(order.amount),
                    "cTime": "1695718781129",
                    "clientOid": order.client_order_id or "",
                    "feeDetail": [
                        {
                            "feeCoin": self.quote_asset,
                            "fee": str(self.expected_partial_fill_fee.flat_fees[0].amount)
                        }
                    ],
                    "fillFee": str(self.expected_partial_fill_fee.flat_fees[0].amount),
                    "fillFeeCoin": self.quote_asset,
                    "fillNotionalUsd": "270.005",
                    "fillPrice": str(order.price),
                    "baseVolume": str(order.amount),
                    "fillTime": "1695718781146",
                    "force": CONSTANTS.DEFAULT_TIME_IN_FORCE,
                    "instId": self.exchange_trading_pair,
                    "leverage": "20",
                    "marginCoin": self.quote_asset,
                    "marginMode": "crossed",
                    "notionalUsd": "270",
                    "orderId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "orderType": order.order_type.name.lower(),
                    "pnl": "0",
                    "posMode": "hedge_mode",
                    "posSide": "long",
                    "price": str(order.price),
                    "priceAvg": str(order.price),
                    "reduceOnly": "no",
                    "stpMode": "cancel_taker",
                    "side": order.trade_type.name.lower(),
                    "size": str(order.amount),
                    "enterPointSource": "WEB",
                    "status": "filled",
                    "tradeScope": "T",
                    "tradeId": "1111111111",
                    "tradeSide": "close",
                    "presetStopSurplusPrice": "21.4",
                    "totalProfits": "11221.45",
                    "presetStopLossPrice": "21.5",
                    "cancelReason": "normal_cancel",
                    "uTime": "1695718781146"
                }
            ],
            "ts": 1695718781206
        }

    def trade_event_for_partial_fill_websocket_update(self, order: InFlightOrder):
        return self.order_event_for_partially_filled_websocket_update(order)

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return self.order_event_for_full_fill_websocket_update(order)

    def position_event_for_full_fill_websocket_update(
        self,
        order: InFlightOrder,
        unrealized_pnl: float
    ):
        return {
            "action": "snapshot",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": CONSTANTS.WS_POSITIONS_ENDPOINT,
                "instId": "default"
            },
            "data": [
                {
                    "posId": "1",
                    "instId": self.exchange_trading_pair,
                    "marginCoin": self.quote_asset,
                    "marginSize": str(order.amount),
                    "marginMode": "crossed",
                    "holdSide": "short",
                    "posMode": "hedge_mode",
                    "total": str(order.amount),
                    "available": str(order.amount),
                    "frozen": "0",
                    "openPriceAvg": str(order.price),
                    "leverage": str(order.leverage),
                    "achievedProfits": "0",
                    "unrealizedPL": str(unrealized_pnl),
                    "unrealizedPLR": "0",
                    "liquidationPrice": "5788.108475905242",
                    "keepMarginRate": "0.005",
                    "marginRate": "0.004416374196",
                    "cTime": "1695649246169",
                    "breakEvenPrice": "24778.97",
                    "totalFee": "1.45",
                    "deductedFee": "0.388",
                    "markPrice": "2500",
                    "uTime": "1695711602568",
                    "assetMode": "union",
                    "autoMargin": "off"
                }
            ],
            "ts": 1695717430441
        }

    def funding_info_event_for_websocket_update(self):
        return {
            "arg": {
                "channel": CONSTANTS.PUBLIC_WS_TICKER,
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "instId": self.exchange_trading_pair
            },
            "data": [
                {
                    "instId": self.exchange_trading_pair,
                    "lastPr": "27000.5",
                    "bidPr": "27000",
                    "askPr": "27000.5",
                    "bidSz": "2.71",
                    "askSz": "8.76",
                    "open24h": "27000.5",
                    "high24h": "30668.5",
                    "low24h": "26999.0",
                    "change24h": "-0.00002",
                    "fundingRate": "0.000010",
                    "nextFundingTime": "1695722400000",
                    "markPrice": "27000.0",
                    "indexPrice": "25702.4",
                    "holdingAmount": "929.502",
                    "baseVolume": "368.900",
                    "quoteVolume": "10152429.961",
                    "openUtc": "27000.5",
                    "symbolType": 1,
                    "symbol": self.exchange_trading_pair,
                    "deliveryPrice": "0",
                    "ts": "1695715383021"
                }
            ],
        }

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}"

    def create_exchange_instance(self):
        exchange = BitgetPerpetualDerivative(
            bitget_perpetual_api_key=self.api_key,
            bitget_perpetual_secret_key=self.api_secret,
            bitget_perpetual_passphrase=self.passphrase,
            trading_pairs=[self.trading_pair],
        )
        exchange._last_trade_history_timestamp = self.latest_trade_hist_timestamp
        funding_info = FundingInfo(
            trading_pair=self.trading_pair,
            index_price=Decimal(-1),
            mark_price=Decimal(-1),
            next_funding_utc_timestamp=1640001119,
            rate=self.target_funding_payment_funding_rate
        )
        exchange._perpetual_trading._funding_info[self.trading_pair] = funding_info

        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_data = request_call.kwargs["headers"]

        self.assertIn("ACCESS-TIMESTAMP", request_data)
        self.assertIn("ACCESS-KEY", request_data)
        self.assertEqual(self.api_key, request_data["ACCESS-KEY"])
        self.assertIn("ACCESS-SIGN", request_data)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])

        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(order.amount, Decimal(request_data["size"]))
        self.assertEqual(CONSTANTS.DEFAULT_TIME_IN_FORCE, request_data["force"])
        self.assertEqual(order.client_order_id, request_data["clientOid"])

        if self.exchange.position_mode == PositionMode.HEDGE:
            self.assertIn("tradeSide", request_data)
            self.assertEqual(order.position.name.lower(), request_data["tradeSide"])
        else:
            self.assertNotIn("tradeSide", request_data)

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(order.exchange_order_id, request_data["orderId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.exchange_order_id, request_params["orderId"])

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        """
        :return: the URL configured for the cancelation
        """
        url = web_utils.private_rest_url(path_url=CONSTANTS.CANCEL_ORDER_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, body=json.dumps(
            self._order_cancelation_request_successful_mock_response(order=order)
        ), callback=callback)

        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.CANCEL_ORDER_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, body=json.dumps({
            "code": "43026",
            "msg": "Could not find order",
        }), callback=callback)

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
        return [
            self.configure_successful_cancelation_response(
                order=successful_order,
                mock_api=mock_api
            ),
            self.configure_erroneous_cancelation_response(
                order=erroneous_order,
                mock_api=mock_api
            )
        ]

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        pass

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        pass

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, body=json.dumps(
            self._order_status_request_completely_filled_mock_response(order=order)
        ), callback=callback)

        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, body=json.dumps(
            self._order_status_request_canceled_mock_response(order=order)
        ), callback=callback)

        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)

        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=404, callback=callback)

        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_DETAIL_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, body=json.dumps(
            self._order_status_request_partially_filled_mock_response(order=order)
        ), callback=callback)

        return url

    def configure_partial_cancelled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        return self.configure_canceled_order_status_response(
            order=order,
            mock_api=mock_api,
            callback=callback
        )

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_FILLS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, body=json.dumps(
            self._order_fills_request_partial_fill_mock_response(order=order)
        ), callback=callback)

        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_FILLS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, body=json.dumps(
            self._order_fills_request_full_fill_mock_response(order=order)
        ), callback=callback)

        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDER_FILLS_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=400, callback=callback)

        return url

    def configure_successful_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.private_rest_url(path_url=CONSTANTS.SET_POSITION_MODE_ENDPOINT)

        mock_api.post(url, body=json.dumps(
            self.set_position_mode_request_mock_response
        ), callback=callback)

        return url

    def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        url = web_utils.private_rest_url(path_url=CONSTANTS.SET_POSITION_MODE_ENDPOINT)
        mock_response = self.set_position_mode_request_mock_response
        mock_response["code"] = CONSTANTS.RET_CODE_PARAMS_ERROR
        mock_response["msg"] = "Some problem"

        mock_api.post(url, body=json.dumps(mock_response), callback=callback)

        return url, f"Error: {mock_response['code']} - {mock_response['msg']}"

    def configure_failed_set_leverage(
            self,
            leverage: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        url = web_utils.private_rest_url(path_url=CONSTANTS.SET_LEVERAGE_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_response = self.set_leverage_request_mock_response
        mock_response["code"] = CONSTANTS.RET_CODE_PARAMS_ERROR
        mock_response["msg"] = "Some problem"

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url, f"Error: {mock_response['code']} - {mock_response['msg']}"

    def configure_successful_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        url = web_utils.private_rest_url(path_url=CONSTANTS.SET_LEVERAGE_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.post(regex_url, body=json.dumps(
            self.set_leverage_request_mock_response
        ), callback=callback)

        return url

    def configure_all_symbols_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        all_urls = []

        url = (f"{web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT)}"
               f"?productType={CONSTANTS.USDT_PRODUCT_TYPE}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self.all_symbols_request_mock_response
        mock_api.get(regex_url, body=json.dumps(response))
        all_urls.append(url)

        url = (f"{web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT)}"
               f"?productType={CONSTANTS.USD_PRODUCT_TYPE}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._all_usd_symbols_request_mock_response
        mock_api.get(regex_url, body=json.dumps(response))
        all_urls.append(url)

        url = (f"{web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT)}"
               f"?productType={CONSTANTS.USDC_PRODUCT_TYPE}")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._all_usdc_symbols_request_mock_response
        mock_api.get(regex_url, body=json.dumps(response))
        all_urls.append(url)

        return all_urls

    def configure_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        return self.configure_all_symbols_response(mock_api=mock_api, callback=callback)

    def configure_erroneous_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        all_urls = []

        url = (f"{web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT)}"
               f"?productType={CONSTANTS.USDT_PRODUCT_TYPE}")
        response = self.trading_rules_request_erroneous_mock_response
        mock_api.get(url, body=json.dumps(response))
        all_urls.append(url)

        url = (f"{web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT)}"
               f"?productType={CONSTANTS.USD_PRODUCT_TYPE}")
        response = {
            "code": "00000",
            "data": [],
            "msg": "success",
            "requestTime": "0"
        }
        mock_api.get(url, body=json.dumps(response))
        all_urls.append(url)

        url = (f"{web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT)}"
               f"?productType={CONSTANTS.USDC_PRODUCT_TYPE}")
        mock_api.get(url, body=json.dumps(response))
        all_urls.append(url)

        return all_urls

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

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()

        linear_buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        linear_sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote_asset, linear_buy_collateral_token)
        self.assertEqual(self.quote_asset, linear_sell_collateral_token)

    def test_time_synchronizer_related_reqeust_error_detection(self):
        exception = self.exchange._formatted_error(
            CONSTANTS.RET_CODE_AUTH_TIMESTAMP_ERROR,
            "Request timestamp expired."
        )
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = self.exchange._formatted_error(
            CONSTANTS.RET_CODES_ORDER_NOT_EXISTS[0],
            "Failed to cancel order because it was not found."
        )
        self.assertFalse(
            self.exchange._is_request_exception_related_to_time_synchronizer(exception)
        )

    def test_user_stream_empty_position_event_removes_current_position(self):
        self.exchange._set_current_timestamp(1640780000)
        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders["OID1"]

        fake_position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal("0"),
            entry_price=order.price,
            amount=order.amount,
            leverage=Decimal("1")
        )
        self.exchange._perpetual_trading.set_position(self.exchange_trading_pair, fake_position)

        self.assertIn(fake_position, self.exchange._perpetual_trading._account_positions.values())

        position_event = {
            "action": "snapshot",
            "arg": {
                "channel": CONSTANTS.WS_POSITIONS_ENDPOINT,
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "instId": "default"
            },
            "data": [],
        }

        mock_queue = AsyncMock()
        event_messages = []
        event_messages.append(position_event)
        event_messages.append(asyncio.CancelledError)
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(0, len(self.exchange._perpetual_trading._account_positions))

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        rate_url = web_utils.public_rest_url(CONSTANTS.PUBLIC_FUNDING_RATE_ENDPOINT)
        mark_url = web_utils.public_rest_url(CONSTANTS.PUBLIC_SYMBOL_PRICE_ENDPOINT)
        rate_regex_url = re.compile(f"^{rate_url}".replace(".", r"\.").replace("?", r"\?"))
        mark_regex_url = re.compile(f"^{mark_url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self.funding_info_mock_response
        mock_api.get(rate_regex_url, body=json.dumps(resp))
        mock_api.get(mark_regex_url, body=json.dumps(resp))

        funding_info_event = self.funding_info_event_for_websocket_update()

        event_messages = [funding_info_event, asyncio.CancelledError]
        mock_queue_get.side_effect = event_messages

        try:
            self.async_run_with_timeout(
                self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        self.assertEqual(
            1,
            self.exchange._perpetual_trading.funding_info_stream.qsize()
        )

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(
        self,
        mock_api,
        mock_queue_get
    ):
        rate_url = web_utils.public_rest_url(CONSTANTS.PUBLIC_FUNDING_RATE_ENDPOINT)
        mark_url = web_utils.public_rest_url(CONSTANTS.PUBLIC_SYMBOL_PRICE_ENDPOINT)
        rate_regex_url = re.compile(f"^{rate_url}".replace(".", r"\.").replace("?", r"\?"))
        mark_regex_url = re.compile(f"^{mark_url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self.funding_info_mock_response
        mock_api.get(rate_regex_url, body=json.dumps(resp))
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
        self.assertEqual(
            self.target_funding_info_next_funding_utc_timestamp,
            funding_info.next_funding_utc_timestamp
        )
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    def test_product_type_associated_to_trading_pair(self):
        self.exchange._set_trading_pair_symbol_map(
            bidict({
                self.exchange_trading_pair: self.trading_pair,
                "ETHPERP": "ETH-USDC",
            })
        )

        product_type = self.async_run_with_timeout(
            self.exchange.product_type_associated_to_trading_pair(self.trading_pair))

        self.assertEqual(CONSTANTS.USDT_PRODUCT_TYPE, product_type)

        product_type = self.async_run_with_timeout(
            self.exchange.product_type_associated_to_trading_pair("ETH-USDC")
        )

        self.assertEqual(CONSTANTS.USDC_PRODUCT_TYPE, product_type)

        product_type = self.async_run_with_timeout(
            self.exchange.product_type_associated_to_trading_pair("XMR-ETH")
        )

        self.assertEqual(CONSTANTS.USD_PRODUCT_TYPE, product_type)

    @aioresponses()
    def test_update_trading_fees(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(
            bidict(
                {
                    self.exchange_trading_pair: self.trading_pair,
                    "BTCUSD": "BTC-USD",
                    "BTCPERP": "BTC-USDC",
                }
            )
        )

        urls = self.configure_all_symbols_response(mock_api=mock_api)
        url = urls[0]
        resp = self.all_symbols_request_mock_response

        self.async_run_with_timeout(self.exchange._update_trading_fees())

        fees_request = self._all_executed_requests(mock_api, url)[0]
        request_params = fees_request.kwargs["params"]
        self.assertEqual(CONSTANTS.USDT_PRODUCT_TYPE, request_params["productType"])

        expected_trading_fees = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal(resp["data"][0]["makerFeeRate"]),
            taker_percent_fee_decimal=Decimal(resp["data"][0]["takerFeeRate"]),
        )

        self.assertEqual(expected_trading_fees, self.exchange._trading_fees[self.trading_pair])

    def test_collateral_token_balance_updated_when_processing_order_creation_update(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._account_balances[self.quote_asset] = Decimal("10000")
        self.exchange._account_available_balances[self.quote_asset] = Decimal("10000")

        order = InFlightOrder(
            exchange_order_id="12345",
            client_order_id="67890",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("1000"),
            amount=Decimal("1"),
            position=PositionAction.OPEN,
            creation_timestamp=1664807277548,
            initial_state=OrderState.OPEN
        )

        mock_response = self.order_event_for_new_order_websocket_update(order)
        mock_response["data"][0]["leverage"] = "1"

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [mock_response, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("9000"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("10000"), self.exchange.get_balance(self.quote_asset))

    def test_collateral_token_balance_updated_when_processing_order_cancelation_update(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._account_balances[self.quote_asset] = Decimal("10000")
        self.exchange._account_available_balances[self.quote_asset] = Decimal("9000")

        order = InFlightOrder(
            exchange_order_id="12345",
            client_order_id="67890",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("1000"),
            amount=Decimal("1"),
            position=PositionAction.OPEN,
            creation_timestamp=1664807277548,
            initial_state=OrderState.CANCELED
        )

        mock_response = self.order_event_for_new_order_websocket_update(order)
        mock_response["data"][0]["leverage"] = "1"

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [mock_response, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10000"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("10000"), self.exchange.get_balance(self.quote_asset))

    def test_collateral_token_balance_updated_when_processing_order_creation_update_considering_leverage(
        self
    ):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._account_balances[self.quote_asset] = Decimal("10000")
        self.exchange._account_available_balances[self.quote_asset] = Decimal("10000")

        order = InFlightOrder(
            exchange_order_id="12345",
            client_order_id="67890",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("1000"),
            amount=Decimal("1"),
            position=PositionAction.OPEN,
            creation_timestamp=1664807277548,
            initial_state=OrderState.OPEN
        )

        mock_response = self.order_event_for_new_order_websocket_update(order)
        mock_response["data"][0]["leverage"] = "10"

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [mock_response, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("9900"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("10000"), self.exchange.get_balance(self.quote_asset))

    def test_collateral_token_balance_not_updated_for_order_creation_event_to_not_open_position(
        self
    ):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._account_balances[self.quote_asset] = Decimal("10000")
        self.exchange._account_available_balances[self.quote_asset] = Decimal("10000")

        order = InFlightOrder(
            exchange_order_id="12345",
            client_order_id="67890",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("1000"),
            amount=Decimal("1"),
            position=PositionAction.CLOSE,
            creation_timestamp=1664807277548,
            initial_state=OrderState.OPEN
        )

        mock_response = self.order_event_for_new_order_websocket_update(order)
        mock_response["data"][0]["leverage"] = "1"

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [mock_response, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10000"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("10000"), self.exchange.get_balance(self.quote_asset))

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

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": "00000",
            "data": {
                "orderId": self.expected_exchange_order_id,
                "clientOid": str(order.client_order_id)
            },
            "msg": "success",
            "requestTime": 1627293504612
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695823012595,
            "data": {
                "symbol": self.exchange_trading_pair,
                "size": str(order.amount),
                "orderId": str(order.exchange_order_id),
                "clientOid": str(order.client_order_id),
                "baseVolume": str(order.amount),
                "priceAvg": str(order.price),
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "price": str(order.price),
                "state": "filled",
                "side": order.trade_type.name.lower(),
                "force": "gtc",
                "totalProfits": "2112",
                "posSide": "long",
                "marginCoin": self.quote_asset,
                "presetStopSurplusPrice": "1910",
                "presetStopSurplusType": "fill_price",
                "presetStopSurplusExecutePrice": "1911",
                "presetStopLossPrice": "1890",
                "presetStopLossType": "fill_price",
                "presetStopLossExecutePrice": "1989",
                "quoteVolume": str(order.amount),
                "orderType": "limit",
                "leverage": "20",
                "marginMode": "cross",
                "reduceOnly": "yes",
                "enterPointSource": "api",
                "tradeSide": "buy_single",
                "posMode": "one_way_mode",
                "orderSource": "normal",
                "cancelReason": "",
                "cTime": "1627300098776",
                "uTime": "1627300098776"
            }
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"]["state"] = "cancelled"
        resp["data"]["priceAvg"] = "0"
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"]["state"] = "live"
        resp["data"]["priceAvg"] = "0"
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"]["state"] = "partially_filled"
        resp["data"]["priceAvg"] = str(self.expected_partial_fill_price)
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        fee_amount = str(self.expected_partial_fill_fee.flat_fees[0].amount)

        return {
            "code": "00000",
            "data": {
                "fillList": [
                    {
                        "tradeId": self.expected_fill_trade_id,
                        "symbol": self.exchange_trading_pair,
                        "orderId": order.exchange_order_id,
                        "price": str(self.expected_partial_fill_price),
                        "baseVolume": "10",
                        "feeDetail": [
                            {
                                "deduction": "no",
                                "feeCoin": self.quote_asset,
                                "totalDeductionFee": fee_amount,
                                "totalFee": fee_amount
                            }
                        ],
                        "side": "buy",
                        "quoteVolume": str(self.expected_partial_fill_amount),
                        "profit": "102",
                        "enterPointSource": "api",
                        "tradeSide": "close",
                        "posMode": "hedge_mode",
                        "tradeScope": "taker",
                        "cTime": "1627293509612"
                    }
                ],
                "endId": "123"
            },
            "msg": "success",
            "requestTime": 1627293504612
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        fee_amount = str(self.expected_fill_fee.flat_fees[0].amount)

        return {
            "code": "00000",
            "data": {
                "fillList": [
                    {
                        "tradeId": self.expected_fill_trade_id,
                        "symbol": self.exchange_trading_pair,
                        "orderId": order.exchange_order_id,
                        "price": str(order.price),
                        "baseVolume": "1",
                        "feeDetail": [
                            {
                                "deduction": "no",
                                "feeCoin": self.quote_asset,
                                "totalDeductionFee": fee_amount,
                                "totalFee": fee_amount
                            }
                        ],
                        "side": "buy",
                        "quoteVolume": str(order.amount),
                        "profit": "102",
                        "enterPointSource": "api",
                        "tradeSide": "close",
                        "posMode": "hedge_mode",
                        "tradeScope": "taker",
                        "cTime": "1627293509612"
                    }
                ],
                "endId": "123"
            },
            "msg": "success",
            "requestTime": 1627293504612
        }

    def _configure_balance_response(
            self,
            response: Dict[str, Any],
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:

        return_url = super()._configure_balance_response(
            response=response,
            mock_api=mock_api,
            callback=callback
        )

        url = self.balance_url + f"?productType={CONSTANTS.USD_PRODUCT_TYPE}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {
            "code": "00000",
            "data": [],
            "msg": "success",
            "requestTime": 1630901215622
        }
        mock_api.get(regex_url, body=json.dumps(response))

        url = self.balance_url + f"?productType={CONSTANTS.USDC_PRODUCT_TYPE}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps(response))

        return return_url

    def _simulate_trading_rules_initialized(self):
        rule = self.trading_rules_request_mock_response["data"][0]
        self.exchange._initialize_trading_pair_symbols_from_exchange_info([rule])
        collateral_token = rule["supportMarginCoins"][0]

        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_value=Decimal(rule.get("minTradeUSDT", "0")),
                max_order_size=Decimal(rule.get("maxOrderQty", "0")),
                min_order_size=Decimal(rule["minTradeNum"]),
                min_price_increment=Decimal(f"1e-{int(rule['pricePlace'])}"),
                min_base_amount_increment=Decimal(rule["sizeMultiplier"]),
                buy_order_collateral_token=collateral_token,
                sell_order_collateral_token=collateral_token,
            ),
        }

        return self.exchange._trading_rules
