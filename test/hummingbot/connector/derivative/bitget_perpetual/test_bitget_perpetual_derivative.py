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
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase, TradeFeeSchema


class BitgetPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.passphrase = "somePassphrase"
        cls.quote_asset = "USDT"  # linear
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT
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
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return regex_url

    @property
    def order_creation_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.GET_WALLET_BALANCE_PATH_URL)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.GET_FUNDING_FEES_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def all_symbols_request_mock_response(self):
        mock_response = {
            "code": "00000",
            "data": [{
                "baseCoin": self.base_asset,
                "buyLimitPriceRatio": "0.01",
                "feeRateUpRatio": "0.005",
                "makerFeeRate": "0.0002",
                "minTradeNum": "0.001",
                "openCostUpRatio": "0.01",
                "priceEndStep": "5",
                "pricePlace": "1",
                "quoteCoin": self.quote_asset,
                "sellLimitPriceRatio": "0.01",
                "supportMarginCoins": [
                    self.quote_asset
                ],
                "symbol": self.exchange_trading_pair,
                "takerFeeRate": "0.0006",
                "volumePlace": "3",
                "sizeMultiplier": "5"
            }],
            "msg": "success",
            "requestTime": 1627114525850
        }
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = {
            "code": "00000",
            "msg": "success",
            "data": {
                "symbol": self.exchange_trading_pair,
                "last": "23990.5",
                "bestAsk": "23991",
                "bestBid": "23989.5",
                "high24h": "24131.5",
                "low24h": "23660.5",
                "timestamp": "1660705778888",
                "priceChangePercent": "0.00442",
                "baseVolume": "156243.358",
                "quoteVolume": "3735854069.908",
                "usdtVolume": "3735854069.908",
                "openUtc": "23841.5",
                "chgUtc": "0.00625"
            }
        }
        return mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        mock_response = self.all_symbols_request_mock_response
        return None, mock_response

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = {"flag": True, "requestTime": 1662584739780}
        return mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = {
            "code": "00000",
            "data": [{
                "baseCoin": self.base_asset,
                "quoteCoin": self.quote_asset,
                "symbol": self.exchange_trading_pair,
            }],
            "msg": "success",
            "requestTime": 1627114525850
        }
        return mock_response

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {
            "code": "00000",
            "data": {
                "orderId": "1627293504612",
                "clientOid": "BITGET#1627293504612"
            },
            "msg": "success",
            "requestTime": 1627293504612
        }
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        mock_response = {
            "code": "00000",
            "data": [
                {
                    "marginCoin": self.quote_asset,
                    "locked": "0",
                    "available": "2000",
                    "crossMaxAvailable": "2000",
                    "fixedMaxAvailable": "2000",
                    "maxTransferOut": "10572.92904289",
                    "equity": "2000",
                    "usdtEquity": "10582.902657719473",
                    "btcEquity": "0.204885807029"
                },
                {
                    "marginCoin": self.base_asset,
                    "locked": "5",
                    "available": "10",
                    "crossMaxAvailable": "10",
                    "fixedMaxAvailable": "10",
                    "maxTransferOut": "10572.92904289",
                    "equity": "15",
                    "usdtEquity": "10582.902657719473",
                    "btcEquity": "0.204885807029"
                }
            ],
            "msg": "success",
            "requestTime": 1630901215622
        }
        return mock_response

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "code": "00000",
            "data": [
                {
                    "marginCoin": self.base_asset,
                    "locked": "5",
                    "available": "10",
                    "crossMaxAvailable": "10",
                    "fixedMaxAvailable": "10",
                    "maxTransferOut": "10572.92904289",
                    "equity": "15",
                    "usdtEquity": "10582.902657719473",
                    "btcEquity": "0.204885807029"
                }
            ],
            "msg": "success",
            "requestTime": 1630901215622
        }

    @property
    def balance_event_websocket_update(self):
        mock_response = {
            "arg": {
                "channel": CONSTANTS.WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME,
                "instType": "umcbl",
                "instId": "default"
            },
            "data": [
                {
                    "marginCoin": self.base_asset,
                    "available": "100",
                    "locked": "5",
                    "maxOpenPosAvailable": "10",
                    "equity": "15",
                }
            ]
        }
        return mock_response

    @property
    def expected_latest_price(self):
        return 23990.5

    @property
    def empty_funding_payment_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "data": {
                "result": [],
                "endId": "885353495773458432",
                "nextFlag": False,
                "preFlag": False
            }
        }

    @property
    def funding_payment_mock_response(self):
        return {
            "code": "00000",
            "msg": "success",
            "data": {
                "result": [
                    {
                        "id": "892962903462432768",
                        "symbol": self.exchange_symbol_for_tokens(base_token=self.base_asset,
                                                                  quote_token=self.quote_asset),
                        "marginCoin": self.quote_asset,
                        "amount": str(self.target_funding_payment_payment_amount),
                        "fee": "0",
                        "feeByCoupon": "",
                        "feeCoin": self.quote_asset,
                        "business": "contract_settle_fee",
                        "cTime": "1657110053000"
                    }
                ],
                "endId": "885353495773458432",
                "nextFlag": False,
                "preFlag": False
            }
        }

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return list(CONSTANTS.POSITION_MODE_MAP.keys())

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
        funding_info = {"data": {}}
        funding_info["data"]["amount"] = self.target_funding_info_index_price
        funding_info["data"]["markPrice"] = self.target_funding_info_mark_price
        funding_info["data"]["fundingTime"] = self.target_funding_info_next_funding_utc_str
        funding_info["data"]["fundingRate"] = self.target_funding_info_rate
        return funding_info

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        trading_rules_resp = self.trading_rules_request_mock_response["data"][0]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(str(trading_rules_resp["minTradeNum"])),
            min_price_increment=(Decimal(str(trading_rules_resp["priceEndStep"]))
                                 * Decimal(f"1e-{trading_rules_resp['pricePlace']}")),
            min_base_amount_increment=Decimal(str(trading_rules_resp["sizeMultiplier"])),
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
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

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}_UMCBL"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = BitgetPerpetualDerivative(
            client_config_map=client_config_map,
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
        if order.position in [PositionAction.OPEN, PositionAction.NIL]:
            contract = "long" if order.trade_type == TradeType.BUY else "short"
        else:
            contract = "short" if order.trade_type == TradeType.BUY else "long"
        pos_action = order.position.name.lower() if order.position.name.lower() in ["open", "close"] else "open"
        self.assertEqual(f"{pos_action}_{contract}", request_data["side"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(order.amount, Decimal(request_data["size"]))
        self.assertEqual(CONSTANTS.DEFAULT_TIME_IN_FORCE, request_data["timeInForceValue"])
        self.assertEqual(order.client_order_id, request_data["clientOid"])

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
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL
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
            endpoint=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {
            "code": "43026",
            "msg": "Could not find order",
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
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL
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
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL
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
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL
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
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL
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
            endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL
        )
        regex_url = re.compile(url + r"\?.*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_cancelled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
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
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.USER_TRADE_RECORDS_PATH_URL
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
            endpoint=CONSTANTS.USER_TRADE_RECORDS_PATH_URL
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
            endpoint=CONSTANTS.USER_TRADE_RECORDS_PATH_URL
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
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.SET_POSITION_MODE_URL)
        response = {
            "code": "00000",
            "data": {
                "symbol": self.exchange_trading_pair,
                "marginCoin": "USDT",
                "longLeverage": 25,
                "shortLeverage": 20,
                "marginMode": "crossed"
            },
            "msg": "success",
            "requestTime": 1627293445916
        }
        mock_api.post(url, body=json.dumps(response), callback=callback)

        return url

    def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.SET_POSITION_MODE_URL)
        regex_url = re.compile(f"^{url}")

        error_code = CONSTANTS.RET_CODE_PARAMS_ERROR
        error_msg = "Some problem"
        mock_response = {
            "code": error_code,
            "data": {
                "symbol": self.exchange_trading_pair,
                "marginCoin": "USDT",
                "longLeverage": 25,
                "shortLeverage": 20,
                "marginMode": "crossed"
            },
            "msg": error_msg,
            "requestTime": 1627293445916
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
            endpoint=CONSTANTS.SET_LEVERAGE_PATH_URL
        )
        regex_url = re.compile(f"^{url}")

        err_code = CONSTANTS.RET_CODE_PARAMS_ERROR
        err_msg = "Some problem"
        mock_response = {
            "code": err_code,
            "data": {
                "symbol": self.exchange_trading_pair,
                "marginCoin": "USDT",
                "longLeverage": 25,
                "shortLeverage": 20,
                "marginMode": "crossed"
            },
            "msg": err_msg,
            "requestTime": 1627293049406
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
            endpoint=CONSTANTS.SET_LEVERAGE_PATH_URL
        )
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "code": "00000",
            "data": {
                "symbol": self.exchange_trading_pair,
                "marginCoin": "USDT",
                "longLeverage": 25,
                "shortLeverage": 20,
                "marginMode": "crossed"
            },
            "msg": "success",
            "requestTime": 1627293049406
        }

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "arg": {
                "channel": CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME,
                "instType": "umcbl",
                "instId": "default"
            },
            "data": [{
                "instId": "default",
                "ordId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                "clOrdId": order.client_order_id or "",
                "px": str(order.price),
                "sz": str(order.amount),
                "notionalUsd": "100",
                "ordType": order.order_type.name.capitalize(),
                "force": "post_only",
                "side": order.trade_type.name.capitalize(),
                "posSide": "long",
                "tdMode": "cross",
                "tgtCcy": self.base_asset,
                "fillPx": "0",
                "tradeId": "0",
                "fillSz": "0",
                "fillTime": "1627293049406",
                "fillFee": "0",
                "fillFeeCcy": "USDT",
                "execType": "maker",
                "accFillSz": "0",
                "fillNotionalUsd": "0",
                "avgPx": "0",
                "status": "new",
                "lever": "1",
                "orderFee": [
                    {"feeCcy": "USDT",
                     "fee": "0.001"},
                ],
                "pnl": "0.1",
                "uTime": "1627293049406",
                "cTime": "1627293049406",
            }],
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "arg": {
                "channel": CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME,
                "instType": "umcbl",
                "instId": "default"
            },
            "data": [{
                "instId": "default",
                "ordId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                "clOrdId": order.client_order_id or "",
                "px": str(order.price),
                "sz": str(order.amount),
                "notionalUsd": "100",
                "ordType": order.order_type.name.capitalize(),
                "force": "post_only",
                "side": order.trade_type.name.capitalize(),
                "posSide": "long",
                "tdMode": "cross",
                "tgtCcy": self.base_asset,
                "fillPx": str(order.price),
                "tradeId": "0",
                "fillSz": "10",
                "fillTime": "1627293049406",
                "fillFee": "0",
                "fillFeeCcy": self.quote_asset,
                "execType": "maker",
                "accFillSz": "10",
                "fillNotionalUsd": "10",
                "avgPx": str(order.price),
                "status": "cancelled",
                "lever": "1",
                "orderFee": [
                    {"feeCcy": "USDT",
                     "fee": "0.001"},
                ],
                "pnl": "0.1",
                "uTime": "1627293049416",
                "cTime": "1627293049416",
            }],
        }

    def order_event_for_partially_canceled_websocket_update(self, order: InFlightOrder):
        return self.order_event_for_canceled_order_websocket_update(order=order)

    def order_event_for_partially_filled_websocket_update(self, order: InFlightOrder):
        return {
            "arg": {
                "channel": CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME,
                "instType": "umcbl",
                "instId": "default"
            },
            "data": [{
                "instId": "default",
                "ordId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                "clOrdId": order.client_order_id or "",
                "px": str(order.price),
                "sz": str(order.amount),
                "notionalUsd": "100",
                "ordType": order.order_type.name.capitalize(),
                "force": "post_only",
                "side": order.trade_type.name.capitalize(),
                "posSide": "long",
                "tdMode": "cross",
                "tgtCcy": self.base_asset,
                "fillPx": str(self.expected_partial_fill_price),
                "tradeId": "xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6",
                "fillSz": str(self.expected_partial_fill_amount),
                "fillTime": "1627293049409",
                "fillFee": "10",
                "fillFeeCcy": self.quote_asset,
                "execType": "maker",
                "accFillSz": str(self.expected_partial_fill_amount),
                "fillNotionalUsd": "10",
                "avgPx": str(self.expected_partial_fill_price),
                "status": "partial-fill",
                "lever": "1",
                "orderFee": [
                    {"feeCcy": self.quote_asset,
                     "fee": str(self.expected_partial_fill_fee.flat_fees[0].amount)},
                ],
                "pnl": "0.1",
                "uTime": "1627293049409",
                "cTime": "1627293049409",
            }],
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "arg": {
                "channel": "orders",
                "instType": "umcbl",
                "instId": "default"
            },
            "data": [{
                "instId": "default",
                "ordId": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                "clOrdId": order.client_order_id or "",
                "px": str(order.price),
                "sz": str(order.amount),
                "notionalUsd": "100",
                "ordType": order.order_type.name.capitalize(),
                "force": "post_only",
                "side": order.trade_type.name.capitalize(),
                "posSide": "short",
                "tdMode": "cross",
                "tgtCcy": self.base_asset,
                "fillPx": str(order.price),
                "tradeId": "0",
                "fillSz": str(order.amount),
                "fillTime": "1627293049406",
                "fillFee": str(self.expected_fill_fee.flat_fees[0].amount),
                "fillFeeCcy": self.quote_asset,
                "execType": "maker",
                "accFillSz": str(order.amount),
                "fillNotionalUsd": "0",
                "avgPx": str(order.price),
                "status": "full-fill",
                "lever": "1",
                "orderFee": [
                    {"feeCcy": self.quote_asset,
                     "fee": str(self.expected_fill_fee.flat_fees[0].amount)},
                ],
                "pnl": "0.1",
                "uTime": "1627293049406",
                "cTime": "1627293049406",
            }],
        }

    def trade_event_for_partial_fill_websocket_update(self, order: InFlightOrder):
        return self.order_event_for_partially_filled_websocket_update(order)

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return self.order_event_for_full_fill_websocket_update(order)

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return {
            "action": "snapshot",
            "arg": {
                "channel": "positions",
                "instType": "umcbl",
                "instId": "default"
            },
            "data": [{
                "instId": self.exchange_symbol_for_tokens(base_token=self.base_asset, quote_token=self.quote_asset),
                "posId": order.exchange_order_id or "960836851453296640",
                "instName": self.exchange_trading_pair,
                "marginCoin": self.quote_asset,
                "margin": str(order.amount),
                "marginMode": "fixed",
                "holdSide": "short",
                "holdMode": "double_hold",
                "total": str(order.amount),
                "available": str(order.amount),
                "locked": "0",
                "averageOpenPrice": str(order.price),
                "leverage": str(order.leverage),
                "achievedProfits": "0",
                "upl": str(unrealized_pnl),
                "uplRate": "1627293049406",
                "liqPx": "0",
                "keepMarginRate": "",
                "fixedMarginRate": "",
                "marginRate": "0",
                "uTime": "1627293049406",
                "cTime": "1627293049406",
                "markPrice": "1317.43",
            }],
        }

    def funding_info_event_for_websocket_update(self):
        return {
            "arg": {
                "channel": "ticker",
                "instType": "UMCBL",
                "instId": f"{self.base_asset}{self.quote_asset}"
            },
            "data": [{
                "instId": f"{self.base_asset}{self.quote_asset}",
                "indexPrice": "0",
                "markPrice": "0",
                "nextSettleTime": "0",
                "capitalRate": "0",
            }],
        }

    def configure_all_symbols_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        all_urls = []

        url = (f"{web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)}"
               f"?productType={CONSTANTS.USDT_PRODUCT_TYPE.lower()}")
        response = self.all_symbols_request_mock_response
        mock_api.get(url, body=json.dumps(response))
        all_urls.append(url)

        url = (f"{web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)}"
               f"?productType={CONSTANTS.USD_PRODUCT_TYPE.lower()}")
        response = self._all_usd_symbols_request_mock_response()
        mock_api.get(url, body=json.dumps(response))
        all_urls.append(url)

        url = (f"{web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)}"
               f"?productType={CONSTANTS.USDC_PRODUCT_TYPE.lower()}")
        response = self._all_usdc_symbols_request_mock_response()
        mock_api.get(url, body=json.dumps(response))
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

        url = (f"{web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)}"
               f"?productType={CONSTANTS.USDT_PRODUCT_TYPE.lower()}")
        response = self.trading_rules_request_erroneous_mock_response
        mock_api.get(url, body=json.dumps(response))
        all_urls.append(url)

        url = (f"{web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)}"
               f"?productType={CONSTANTS.USD_PRODUCT_TYPE.lower()}")
        response = {
            "code": "00000",
            "data": [],
            "msg": "success",
            "requestTime": "0"
        }
        mock_api.get(url, body=json.dumps(response))
        all_urls.append(url)

        url = (f"{web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)}"
               f"?productType={CONSTANTS.USDC_PRODUCT_TYPE.lower()}")
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

    def test_get_buy_and_sell_collateral_tokens_without_trading_rules(self):
        self.exchange._set_trading_pair_symbol_map(None)

        collateral_token = self.exchange.get_buy_collateral_token(trading_pair="BTC-USDT")
        self.assertEqual("USDT", collateral_token)
        collateral_token = self.exchange.get_sell_collateral_token(trading_pair="BTC-USDT")
        self.assertEqual("USDT", collateral_token)

        collateral_token = self.exchange.get_buy_collateral_token(trading_pair="BTC-USDC")
        self.assertEqual("USDC", collateral_token)
        collateral_token = self.exchange.get_sell_collateral_token(trading_pair="BTC-USDC")
        self.assertEqual("USDC", collateral_token)

        collateral_token = self.exchange.get_buy_collateral_token(trading_pair="BTC-USD")
        self.assertEqual("BTC", collateral_token)
        collateral_token = self.exchange.get_sell_collateral_token(trading_pair="BTC-USD")
        self.assertEqual("BTC", collateral_token)

    def test_time_synchronizer_related_reqeust_error_detection(self):
        error_code_str = self.exchange._format_ret_code_for_print(ret_code=CONSTANTS.RET_CODE_AUTH_TIMESTAMP_ERROR)
        exception = IOError(f"{error_code_str} - Request timestamp expired.")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        error_code_str = self.exchange._format_ret_code_for_print(ret_code=CONSTANTS.RET_CODE_ORDER_NOT_EXISTS)
        exception = IOError(f"{error_code_str} - Failed to cancel order because it was not found.")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

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
                "channel": CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME,
                "instType": "umcbl",
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
        rate_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL)}".replace(".",
                                                                                                        r"\.").replace(
                "?", r"\?")
        )
        interest_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.OPEN_INTEREST_PATH_URL)}".replace(".", r"\.").replace("?",
                                                                                                                    r"\?")
        )
        mark_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.MARK_PRICE_PATH_URL)}".replace(".", r"\.").replace("?",
                                                                                                                 r"\?")
        )
        settlement_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.FUNDING_SETTLEMENT_TIME_PATH_URL)}".replace(".",
                                                                                                          r"\.").replace(
                "?", r"\?")
        )
        resp = self.funding_info_mock_response
        mock_api.get(rate_regex_url, body=json.dumps(resp))
        mock_api.get(interest_regex_url, body=json.dumps(resp))
        mock_api.get(mark_regex_url, body=json.dumps(resp))
        mock_api.get(settlement_regex_url, body=json.dumps(resp))

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
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        rate_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL)}".replace(".",
                                                                                                        r"\.").replace(
                "?", r"\?")
        )
        interest_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.OPEN_INTEREST_PATH_URL)}".replace(".", r"\.").replace("?",
                                                                                                                    r"\?")
        )
        mark_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.MARK_PRICE_PATH_URL)}".replace(".", r"\.").replace("?",
                                                                                                                 r"\?")
        )
        settlement_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.FUNDING_SETTLEMENT_TIME_PATH_URL)}".replace(".",
                                                                                                          r"\.").replace(
                "?", r"\?")
        )
        resp = self.funding_info_mock_response
        mock_api.get(rate_regex_url, body=json.dumps(resp))
        mock_api.get(interest_regex_url, body=json.dumps(resp))
        mock_api.get(mark_regex_url, body=json.dumps(resp))
        mock_api.get(settlement_regex_url, body=json.dumps(resp))

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

    def test_exchange_symbol_associated_to_pair_without_product_type(self):
        self.exchange._set_trading_pair_symbol_map(
            bidict({
                self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset): self.trading_pair,
                "BTCUSD_DMCBL": "BTC-USD",
                "ETHPERP_CMCBL": "ETH-USDC",
            }))

        trading_pair = self.async_run_with_timeout(
            self.exchange.trading_pair_associated_to_exchange_instrument_id(
                instrument_id=f"{self.base_asset}{self.quote_asset}"))
        self.assertEqual(self.trading_pair, trading_pair)

        trading_pair = self.async_run_with_timeout(
            self.exchange.trading_pair_associated_to_exchange_instrument_id(
                instrument_id="BTCUSD"))
        self.assertEqual("BTC-USD", trading_pair)

        trading_pair = self.async_run_with_timeout(
            self.exchange.trading_pair_associated_to_exchange_instrument_id(
                instrument_id="ETHPERP"))
        self.assertEqual("ETH-USDC", trading_pair)

        with self.assertRaises(ValueError) as context:
            self.async_run_with_timeout(
                self.exchange.trading_pair_associated_to_exchange_instrument_id(
                    instrument_id="XMRPERP"))
        self.assertEqual("No trading pair associated to instrument ID XMRPERP", str(context.exception))

    @aioresponses()
    def test_update_trading_fees(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(
            bidict(
                {
                    self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset): self.trading_pair,
                    "BTCUSD_DMCBL": "BTC-USD",
                    "BTCPERP_CMCBL": "BTC-USDC",
                }
            )
        )

        urls = self.configure_all_symbols_response(mock_api=mock_api)
        url = urls[0]
        resp = self.all_symbols_request_mock_response

        self.async_run_with_timeout(self.exchange._update_trading_fees())

        fees_request = self._all_executed_requests(mock_api, url)[0]
        request_params = fees_request.kwargs["params"]
        self.assertEqual(CONSTANTS.USDT_PRODUCT_TYPE.lower(), request_params["productType"])

        expected_trading_fees = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal(resp["data"][0]["makerFeeRate"]),
            taker_percent_fee_decimal=Decimal(resp["data"][0]["takerFeeRate"]),
        )

        self.assertEqual(expected_trading_fees, self.exchange._trading_fees[self.trading_pair])

    def test_collateral_token_balance_updated_when_processing_order_creation_update(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._account_balances[self.quote_asset] = Decimal(10_000)
        self.exchange._account_available_balances[self.quote_asset] = Decimal(10_000)

        order_creation_event = {
            "action": "snapshot",
            "arg": {
                "instType": "umcbl",
                "channel": "orders",
                "instId": "default"
            },
            "data": [
                {
                    "accFillSz": "0",
                    "cTime": 1664807277548,
                    "clOrdId": "960836851453296644",
                    "force": "normal",
                    "instId": self.exchange_trading_pair,
                    "lever": "1",
                    "notionalUsd": "13.199",
                    "ordId": "960836851386187777",
                    "ordType": "limit",
                    "orderFee": [{"feeCcy": "USDT", "fee": "0"}],
                    "posSide": "long",
                    "px": "1000",
                    "side": "buy",
                    "status": "new",
                    "sz": "1",
                    "tdMode": "cross",
                    "tgtCcy": "USDT",
                    "uTime": 1664807277548}
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [order_creation_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal(9_000), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal(10_000), self.exchange.get_balance(self.quote_asset))

    def test_collateral_token_balance_updated_when_processing_order_cancelation_update(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._account_balances[self.quote_asset] = Decimal(10_000)
        self.exchange._account_available_balances[self.quote_asset] = Decimal(9_000)

        order_creation_event = {
            "action": "snapshot",
            "arg": {
                "instType": "umcbl",
                "channel": "orders",
                "instId": "default"
            },
            "data": [
                {
                    "accFillSz": "0",
                    "cTime": 1664807277548,
                    "clOrdId": "960836851453296644",
                    "force": "normal",
                    "instId": self.exchange_trading_pair,
                    "lever": "1",
                    "notionalUsd": "13.199",
                    "ordId": "960836851386187777",
                    "ordType": "limit",
                    "orderFee": [{"feeCcy": "USDT", "fee": "0"}],
                    "posSide": "long",
                    "px": "1000",
                    "side": "buy",
                    "status": "canceled",
                    "sz": "1",
                    "tdMode": "cross",
                    "tgtCcy": "USDT",
                    "uTime": 1664807277548}
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [order_creation_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal(10_000), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal(10_000), self.exchange.get_balance(self.quote_asset))

    def test_collateral_token_balance_updated_when_processing_order_creation_update_considering_leverage(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._account_balances[self.quote_asset] = Decimal(10_000)
        self.exchange._account_available_balances[self.quote_asset] = Decimal(10_000)

        order_creation_event = {
            "action": "snapshot",
            "arg": {
                "instType": "umcbl",
                "channel": "orders",
                "instId": "default"
            },
            "data": [
                {
                    "accFillSz": "0",
                    "cTime": 1664807277548,
                    "clOrdId": "960836851453296644",
                    "force": "normal",
                    "instId": self.exchange_trading_pair,
                    "lever": "10",
                    "notionalUsd": "13.199",
                    "ordId": "960836851386187777",
                    "ordType": "limit",
                    "orderFee": [{"feeCcy": "USDT", "fee": "0"}],
                    "posSide": "long",
                    "px": "1000",
                    "side": "buy",
                    "status": "new",
                    "sz": "1",
                    "tdMode": "cross",
                    "tgtCcy": "USDT",
                    "uTime": 1664807277548}
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [order_creation_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal(9_900), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal(10_000), self.exchange.get_balance(self.quote_asset))

    def test_collateral_token_balance_not_updated_for_order_creation_event_to_not_open_position(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._account_balances[self.quote_asset] = Decimal(10_000)
        self.exchange._account_available_balances[self.quote_asset] = Decimal(10_000)

        order_creation_event = {
            "action": "snapshot",
            "arg": {
                "instType": "umcbl",
                "channel": "orders",
                "instId": "default"
            },
            "data": [
                {
                    "accFillSz": "0",
                    "cTime": 1664807277548,
                    "clOrdId": "960836851453296644",
                    "force": "normal",
                    "instId": self.exchange_trading_pair,
                    "lever": "1",
                    "notionalUsd": "13.199",
                    "ordId": "960836851386187777",
                    "ordType": "limit",
                    "orderFee": [{"feeCcy": "USDT", "fee": "0"}],
                    "posSide": "long",
                    "px": "1000",
                    "side": "sell",
                    "status": "new",
                    "sz": "1",
                    "tdMode": "cross",
                    "tgtCcy": "USDT",
                    "uTime": 1664807277548}
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [order_creation_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal(10_000), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal(10_000), self.exchange.get_balance(self.quote_asset))

    @aioresponses()
    def test_update_balances_for_tokens_in_several_product_type_markets(self, mock_api):
        self.exchange._trading_pairs = []
        url = self.balance_url + f"?productType={CONSTANTS.USDT_PRODUCT_TYPE.lower()}"
        response = self.balance_request_mock_response_for_base_and_quote
        mock_api.get(url, body=json.dumps(response))

        url = self.balance_url + f"?productType={CONSTANTS.USD_PRODUCT_TYPE.lower()}"
        response = {
            "code": "00000",
            "data": [
                {
                    "marginCoin": self.base_asset,
                    "locked": "5",
                    "available": "50",
                    "crossMaxAvailable": "50",
                    "fixedMaxAvailable": "50",
                    "maxTransferOut": "10572.92904289",
                    "equity": "70",
                    "usdtEquity": "10582.902657719473",
                    "btcEquity": "0.204885807029"
                }
            ],
            "msg": "success",
            "requestTime": 1630901215622
        }
        mock_api.get(url, body=json.dumps(response))

        url = self.balance_url + f"?productType={CONSTANTS.USDC_PRODUCT_TYPE.lower()}"
        response = {
            "code": "00000",
            "data": [],
            "msg": "success",
            "requestTime": 1630901215622
        }
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("60"), available_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("85"), total_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), total_balances[self.quote_asset])

        response = self.balance_request_mock_response_only_base

        self._configure_balance_response(response=response, mock_api=mock_api)
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn(self.quote_asset, available_balances)
        self.assertNotIn(self.quote_asset, total_balances)
        self.assertEqual(Decimal("10"), available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), total_balances[self.base_asset])

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

    def _expected_valid_trading_pairs(self):
        return [self.trading_pair, "BTC-USD", "BTC-USDC"]

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
            "data": {
                "symbol": self.exchange_trading_pair,
                "size": float(order.amount),
                "orderId": str(order.exchange_order_id),
                "clientOid": str(order.client_order_id),
                "filledQty": float(order.amount),
                "priceAvg": float(order.price),
                "fee": float(self.expected_fill_fee.flat_fees[0].amount),
                "price": str(order.price),
                "state": "filled",
                "side": "open_long",
                "timeInForce": "normal",
                "totalProfits": "10",
                "posSide": "long",
                "marginCoin": self.quote_asset,
                "presetTakeProfitPrice": 69582.5,
                "presetStopLossPrice": 21432.5,
                "filledAmount": float(order.amount),
                "orderType": "limit",
                "cTime": 1627028708807,
                "uTime": 1627028717807
            },
            "msg": "success",
            "requestTime": 1627300098776
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"]["state"] = "canceled"
        resp["data"]["filledQty"] = 0
        resp["data"]["priceAvg"] = 0
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"]["state"] = "new"
        resp["data"]["filledQty"] = 0
        resp["data"]["priceAvg"] = 0
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"]["state"] = "partially_filled"
        resp["data"]["filledQty"] = float(self.expected_partial_fill_amount)
        resp["data"]["priceAvg"] = float(self.expected_partial_fill_price)
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "code": "00000",
            "data": [
                {
                    "tradeId": self.expected_fill_trade_id,
                    "symbol": self.exchange_trading_pair,
                    "orderId": order.exchange_order_id,
                    "price": str(self.expected_partial_fill_price),
                    "sizeQty": float(self.expected_partial_fill_amount),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "side": "close_long",
                    "cTime": "1627027632241"
                }
            ],
            "msg": "success",
            "requestTime": 1627386245672
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "code": "00000",
            "data": [
                {
                    "tradeId": self.expected_fill_trade_id,
                    "symbol": self.exchange_trading_pair,
                    "orderId": order.exchange_order_id,
                    "price": str(order.price),
                    "sizeQty": float(order.amount),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "side": "close_short",
                    "cTime": "1627027632241"
                }
            ],
            "msg": "success",
            "requestTime": 1627386245672
        }

    def _all_usd_symbols_request_mock_response(self):
        return {
            "code": "00000",
            "data": [
                {
                    "baseCoin": "BTC",
                    "buyLimitPriceRatio": "0.01",
                    "feeRateUpRatio": "0.005",
                    "makerFeeRate": "0.0002",
                    "minTradeNum": "0.001",
                    "openCostUpRatio": "0.01",
                    "priceEndStep": "5",
                    "pricePlace": "1",
                    "quoteCoin": "USD",
                    "sellLimitPriceRatio": "0.01",
                    "sizeMultiplier": "0.001",
                    "supportMarginCoins": ["BTC", "ETH", "USDC", "XRP", "BGB"],
                    "symbol": "BTCUSD_DMCBL",
                    "takerFeeRate": "0.0006",
                    "volumePlace": "3"},
            ],
            "msg": "success",
            "requestTime": "0"
        }

    def _all_usdc_symbols_request_mock_response(self):
        return {
            "code": "00000",
            "data": [
                {
                    "baseCoin": "BTC",
                    "buyLimitPriceRatio": "0.02",
                    "feeRateUpRatio": "0.005",
                    "makerFeeRate": "0.0002",
                    "minTradeNum": "0.0001",
                    "openCostUpRatio": "0.01",
                    "priceEndStep": "5",
                    "pricePlace": "1",
                    "quoteCoin": "USD",
                    "sellLimitPriceRatio": "0.02",
                    "sizeMultiplier": "0.0001",
                    "supportMarginCoins": ["USDC"],
                    "symbol": "BTCPERP_CMCBL",
                    "takerFeeRate": "0.0006",
                    "volumePlace": "4"
                },
            ],
            "msg": "success",
            "requestTime": "0"
        }

    def _configure_balance_response(
            self,
            response: Dict[str, Any],
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:

        return_url = super()._configure_balance_response(response=response, mock_api=mock_api, callback=callback)

        url = self.balance_url + f"?productType={CONSTANTS.USD_PRODUCT_TYPE.lower()}"
        response = {
            "code": "00000",
            "data": [],
            "msg": "success",
            "requestTime": 1630901215622
        }
        mock_api.get(url, body=json.dumps(response))

        url = self.balance_url + f"?productType={CONSTANTS.USDC_PRODUCT_TYPE.lower()}"
        mock_api.get(url, body=json.dumps(response))

        return return_url

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            ),
        }
