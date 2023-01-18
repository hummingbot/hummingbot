import asyncio
import json
import re
from copy import deepcopy
from decimal import Decimal
from itertools import chain, product
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

import pandas as pd
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
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
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

    @property
    def all_symbols_request_mock_response(self):
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "name": self.exchange_trading_pair,
                    "alias": self.exchange_trading_pair,
                    "status": "Trading",
                    "base_currency": self.base_asset,
                    "quote_currency": self.quote_asset,
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                },
            ],
            "time_now": "1615801223.589808",
        }
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "symbol": self.exchange_trading_pair,
                    "bid_price": "7230",
                    "ask_price": "7230.5",
                    "last_price": str(self.expected_latest_price),
                    "last_tick_direction": "ZeroMinusTick",
                    "prev_price_24h": "7163.00",
                    "price_24h_pcnt": "0.009353",
                    "high_price_24h": "7267.50",
                    "low_price_24h": "7067.00",
                    "prev_price_1h": "7209.50",
                    "price_1h_pcnt": "0.002843",
                    "mark_price": "7230.31",
                    "index_price": "7230.14",
                    "open_interest": 117860186,
                    "open_value": "16157.26",
                    "total_turnover": "3412874.21",
                    "turnover_24h": "10864.63",
                    "total_volume": 28291403954,
                    "volume_24h": 78053288,
                    "funding_rate": "0.0001",
                    "predicted_funding_rate": "0.0001",
                    "next_funding_time": "2019-12-28T00:00:00Z",
                    "countdown_hour": 2,
                    "delivery_fee_rate": "0",
                    "predicted_delivery_price": "0.00",
                    "delivery_time": ""
                }
            ],
            "time_now": "1577484619.817968"
        }
        return mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "name": self.exchange_trading_pair,
                    "alias": self.exchange_trading_pair,
                    "status": "Trading",
                    "base_currency": self.base_asset,
                    "quote_currency": self.quote_asset,
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                },
                {
                    "name": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "alias": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "status": "Closed",
                    "base_currency": "INVALID",
                    "quote_currency": "PAIR",
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                },
            ],
            "time_now": "1615801223.589808"
        }
        return "INVALID-PAIR", mock_response

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1577444332.192859"
        }
        return mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "name": self.exchange_trading_pair,
                    "alias": self.exchange_trading_pair,
                    "status": "Trading",
                    "base_currency": self.base_asset,
                    "quote_currency": self.quote_asset,
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                },
            ],
            "time_now": "1615801223.589808",
        }
        return mock_response

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "335fd977-e5a5-4781-b6d0-c772d5bfb95b",
                "symbol": self.exchange_trading_pair,
                "side": "Buy",
                "order_type": "Limit",
                "price": 46000,
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "Created",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": get_new_client_order_id(
                    is_buy=True,
                    trading_pair=self.trading_pair,
                    hbot_order_id_prefix=CONSTANTS.HBOT_BROKER_ID,
                    max_id_len=CONSTANTS.MAX_ID_LEN,
                ),
                "created_at": "2019-11-30T11:03:43.452Z",
                "updated_at": "2019-11-30T11:03:43.455Z"
            },
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                self.base_asset: {
                    "equity": 15,
                    "available_balance": 10,
                    "used_margin": 0.00012529,
                    "order_margin": 0.00012529,
                    "position_margin": 0,
                    "occ_closing_fee": 0,
                    "occ_funding_fee": 0,
                    "wallet_balance": 15,
                    "realised_pnl": 0,
                    "unrealised_pnl": 2,
                    "cum_realised_pnl": 0,
                    "given_cash": 0,
                    "service_cash": 0
                },
                self.quote_asset: {
                    "equity": 2000,
                    "available_balance": 2000,
                    "used_margin": 49500,
                    "order_margin": 49500,
                    "position_margin": 0,
                    "occ_closing_fee": 0,
                    "occ_funding_fee": 0,
                    "wallet_balance": 2000,
                    "realised_pnl": 0,
                    "unrealised_pnl": 0,
                    "cum_realised_pnl": 0,
                    "given_cash": 0,
                    "service_cash": 0
                }
            },
            "time_now": "1578284274.816029",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        return mock_response

    @property
    def balance_request_mock_response_only_base(self):
        mock_response = self.balance_request_mock_response_for_base_and_quote
        del mock_response["result"][self.quote_asset]
        return mock_response

    @property
    def balance_event_websocket_update(self):
        mock_response = {
            "topic": "wallet",
            "data": [
                {
                    "available_balance": "10",
                    "wallet_balance": "15"
                }
            ]
        }
        return mock_response

    @property
    def non_linear_balance_event_websocket_update(self):
        mock_response = {
            "topic": "wallet",
            "data": [
                {
                    "user_id": 738713,
                    "coin": self.base_asset,
                    "available_balance": "10",
                    "wallet_balance": "15"
                },
                {
                    "user_id": 738713,
                    "coin": self.non_linear_quote_asset,
                    "available_balance": "20",
                    "wallet_balance": "25"
                },
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
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": {
                "symbol": self.exchange_trading_pair,
                "side": "Buy",
                "size": float(self.target_funding_payment_payment_amount / self.target_funding_payment_funding_rate),
                "funding_rate": float(self.target_funding_payment_funding_rate),
                "exec_fee": "0.0001",
                "exec_time": self.target_funding_payment_timestamp_str,
            },
            "ext_info": None,
            "time_now": "1577446900.717204",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1577446900724,
            "rate_limit": 120
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
        funding_info = mock_response["result"][0]
        funding_info["index_price"] = self.target_funding_info_index_price
        funding_info["mark_price"] = self.target_funding_info_mark_price
        funding_info["next_funding_time"] = self.target_funding_info_next_funding_utc_str
        funding_info["predicted_funding_rate"] = self.target_funding_info_rate
        return mock_response

    @property
    def get_predicted_funding_info(self):
        return {
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": {
                "predicted_funding_rate": 3,
                "predicted_funding_fee": 0
            },
            "ext_info": None,
            "time_now": "1577447415.583259",
            "rate_limit_status": 118,
            "rate_limit_reset_ms": 1577447415590,
            "rate_limit": 120
        }

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        trading_rules_resp = self.trading_rules_request_mock_response["result"][0]
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(str(trading_rules_resp["lot_size_filter"]["min_trading_qty"])),
            max_order_size=Decimal(str(trading_rules_resp["lot_size_filter"]["max_trading_qty"])),
            min_price_increment=Decimal(str(trading_rules_resp["price_filter"]["tick_size"])),
            min_base_amount_increment=Decimal(str(trading_rules_resp["lot_size_filter"]["qty_step"])),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["result"][0]
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

        request_data = request_call.kwargs["params"]
        if request_data is None:
            request_data = json.loads(request_call.kwargs["data"])

        self.assertIn("timestamp", request_data)
        self.assertIn("api_key", request_data)
        self.assertEqual(self.api_key, request_data["api_key"])
        self.assertIn("sign", request_data)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.trade_type.name.capitalize(), request_data["side"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(order.amount, request_data["qty"])
        self.assertEqual(CONSTANTS.DEFAULT_TIME_IN_FORCE, request_data["time_in_force"])
        self.assertEqual(order.position == PositionAction.CLOSE, request_data["close_on_trigger"])
        self.assertEqual(order.client_order_id, request_data["order_link_id"])
        self.assertEqual(order.position == PositionAction.CLOSE, request_data["reduce_only"])
        self.assertIn("position_idx", request_data)
        self.assertEqual(order.order_type.name.capitalize(), request_data["order_type"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(order.exchange_order_id, request_data["order_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["order_link_id"])
        self.assertEqual(order.exchange_order_id, request_params["order_id"])

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
            "ret_code": CONSTANTS.RET_CODE_ORDER_NOT_EXISTS,
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
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": None,
            "ext_info": None,
            "time_now": "1577477968.175013",
            "rate_limit_status": 74,
            "rate_limit_reset_ms": 1577477968183,
            "rate_limit": 75
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
            "ret_code": error_code,
            "ret_msg": error_msg,
            "ext_code": "",
            "result": None,
            "ext_info": None,
            "time_now": "1577477968.175013",
            "rate_limit_status": 74,
            "rate_limit_reset_ms": 1577477968183,
            "rate_limit": 75
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
            "ret_code": err_code,
            "ret_msg": err_msg,
            "ext_code": "",
            "result": leverage,
            "ext_info": None,
            "time_now": "1577477968.175013",
            "rate_limit_status": 74,
            "rate_limit_reset_ms": 1577477968183,
            "rate_limit": 75
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
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": leverage,
            "ext_info": None,
            "time_now": "1577477968.175013",
            "rate_limit_status": 74,
            "rate_limit_reset_ms": 1577477968183,
            "rate_limit": 75
        }

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "topic": "order",
            "data": [
                {
                    "order_id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "order_link_id": order.client_order_id or "",
                    "symbol": self.exchange_trading_pair,
                    "side": order.trade_type.name.capitalize(),
                    "order_type": order.order_type.name.capitalize(),
                    "price": str(order.price),
                    "qty": float(order.amount),
                    "time_in_force": "GoodTillCancel",
                    "create_type": "CreateByUser",
                    "cancel_type": "",
                    "order_status": "New",
                    "leaves_qty": 0,
                    "cum_exec_qty": 0,
                    "cum_exec_value": "0",
                    "cum_exec_fee": "0",
                    "timestamp": "2022-06-21T07:35:56.505Z",
                    "take_profit": "18500",
                    "tp_trigger_by": "LastPrice",
                    "stop_loss": "22000",
                    "sl_trigger_by": "LastPrice",
                    "trailing_stop": "0",
                    "last_exec_price": "21196.5",
                    "reduce_only": order.position == PositionAction.CLOSE,
                    "close_on_trigger": order.position == PositionAction.CLOSE,
                }
            ]
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "topic": "order",
            "data": [
                {
                    "order_id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "order_link_id": order.client_order_id or "",
                    "symbol": self.exchange_trading_pair,
                    "side": order.trade_type.name.capitalize(),
                    "order_type": order.order_type.name.capitalize(),
                    "price": str(order.price),
                    "qty": float(order.amount),
                    "time_in_force": "GoodTillCancel",
                    "create_type": "CreateByUser",
                    "cancel_type": "",
                    "order_status": "Cancelled",
                    "leaves_qty": 0,
                    "cum_exec_qty": 0,
                    "cum_exec_value": "0",
                    "cum_exec_fee": "0.00000567",
                    "timestamp": "2022-06-21T07:35:56.505Z",
                    "take_profit": "18500",
                    "tp_trigger_by": "LastPrice",
                    "stop_loss": "22000",
                    "sl_trigger_by": "LastPrice",
                    "trailing_stop": "0",
                    "last_exec_price": "21196.5",
                    "reduce_only": order.position == PositionAction.CLOSE,
                    "close_on_trigger": order.position == PositionAction.CLOSE,
                }
            ]
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "topic": "order",
            "data": [
                {
                    "order_id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "order_link_id": order.client_order_id or "",
                    "symbol": self.exchange_trading_pair,
                    "side": order.trade_type.name.capitalize(),
                    "order_type": order.order_type.name.capitalize(),
                    "price": str(order.price),
                    "qty": float(order.amount),
                    "time_in_force": "GoodTillCancel",
                    "create_type": "CreateByUser",
                    "cancel_type": "",
                    "order_status": "Filled",
                    "leaves_qty": 0,
                    "cum_exec_qty": float(order.amount),
                    "cum_exec_value": str(order.price),
                    "cum_exec_fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "timestamp": "2022-06-21T07:35:56.505Z",
                    "take_profit": "18500",
                    "tp_trigger_by": "LastPrice",
                    "stop_loss": "22000",
                    "sl_trigger_by": "LastPrice",
                    "trailing_stop": "0",
                    "last_exec_price": "21196.5",
                    "reduce_only": order.position == PositionAction.CLOSE,
                    "close_on_trigger": order.position == PositionAction.CLOSE,
                }
            ]
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "topic": "execution",
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "side": order.trade_type.name.capitalize(),
                    "order_id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "exec_id": self.expected_fill_trade_id,
                    "order_link_id": order.client_order_id or "",
                    "price": str(order.price),
                    "order_qty": float(order.amount),
                    "exec_type": "Trade",
                    "exec_qty": float(order.amount),
                    "exec_fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "leaves_qty": 0,
                    "is_maker": False,
                    "trade_time": "2020-01-14T14:07:23.629Z"
                }
            ]
        }

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        position_value = unrealized_pnl + order.amount * order.price * order.leverage
        return {
            "topic": "position",
            "data": [
                {
                    "user_id": 533285,
                    "symbol": self.exchange_trading_pair,
                    "size": float(order.amount),
                    "side": order.trade_type.name.capitalize(),
                    "position_value": str(position_value),
                    "entry_price": str(order.price),
                    "liq_price": "489",
                    "bust_price": "489",
                    "leverage": str(order.leverage),
                    "order_margin": "0",
                    "position_margin": "0.39929535",
                    "available_balance": "0.39753405",
                    "take_profit": "0",
                    "stop_loss": "0",
                    "realised_pnl": "0.00055631",
                    "trailing_stop": "0",
                    "trailing_active": "0",
                    "wallet_balance": "0.40053971",
                    "risk_id": 1,
                    "occ_closing_fee": "0.0002454",
                    "occ_funding_fee": "0",
                    "auto_add_margin": 1,
                    "cum_realised_pnl": "0.00055105",
                    "position_status": "Normal",
                    "position_seq": 0,
                    "Isolated": False,
                    "mode": 0,
                    "position_idx": 0,
                    "tp_sl_mode": "Partial",
                    "tp_order_num": 0,
                    "sl_order_num": 0,
                    "tp_free_size_x": 200,
                    "sl_free_size_x": 200
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
                        "next_funding_time": self.target_funding_info_next_funding_utc_str_ws_updated,
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
        self.assertEqual(Decimal("20"), self.exchange.available_balances[self.non_linear_quote_asset])
        self.assertEqual(Decimal("25"), self.exchange.get_balance(self.non_linear_quote_asset))

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
        results = response["result"]
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        duplicate["alias"] = f"{self.exchange_trading_pair}_12345"
        duplicate["lot_size_filter"]["min_trading_qty"] = duplicate["lot_size_filter"]["min_trading_qty"] + 1
        results.append(duplicate)
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
        results = response["result"]
        duplicate = deepcopy(results[0])
        duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        duplicate["alias"] = f"{self.exchange_trading_pair}_12345"
        duplicate["lot_size_filter"]["min_trading_qty"] = duplicate["lot_size_filter"]["min_trading_qty"] + 1
        results.insert(0, duplicate)
        mock_api.get(url, body=json.dumps(response))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(1, len(self.exchange.trading_rules))
        self.assertIn(self.trading_pair, self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_cannot_resolve(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url
        response = self.trading_rules_request_mock_response
        results = response["result"]
        first_duplicate = deepcopy(results[0])
        first_duplicate["name"] = f"{self.exchange_trading_pair}_12345"
        first_duplicate["alias"] = f"{self.exchange_trading_pair}_12345"
        first_duplicate["lot_size_filter"]["min_trading_qty"] = (
            first_duplicate["lot_size_filter"]["min_trading_qty"] + 1
        )
        second_duplicate = deepcopy(results[0])
        second_duplicate["name"] = f"{self.exchange_trading_pair}_67890"
        second_duplicate["alias"] = f"{self.exchange_trading_pair}_67890"
        second_duplicate["lot_size_filter"]["min_trading_qty"] = (
            second_duplicate["lot_size_filter"]["min_trading_qty"] + 2
        )
        results.pop(0)
        results.append(first_duplicate)
        results.append(second_duplicate)
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

        endpoint = CONSTANTS.GET_PREDICTED_FUNDING_RATE_PATH_URL
        url = web_utils.get_rest_url_for_endpoint(endpoint, self.trading_pair)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        funding_resp = self.get_predicted_funding_info
        mock_api.get(regex_url, body=json.dumps(funding_resp))

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

        endpoint = CONSTANTS.GET_PREDICTED_FUNDING_RATE_PATH_URL
        url = web_utils.get_rest_url_for_endpoint(endpoint, self.trading_pair)
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
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 533285,
                "order_id": order.exchange_order_id,
                "symbol": self.exchange_trading_pair,
                "side": order.trade_type.name.capitalize(),
                "order_type": order.order_type.name.capitalize(),
                "price": float(order.price),
                "qty": float(order.amount),
                "time_in_force": "GoodTillCancel",
                "order_status": "PendingCancel",
                "last_exec_time": 1655711524.37661,
                "last_exec_price": 0,
                "leaves_qty": float(order.amount),
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "EC_NoError",
                "order_link_id": "IPBTC00001",
                "created_at": "2022-06-20T07:52:04.376Z",
                "updated_at": "2022-06-20T07:54:35.339Z",
                "take_profit": "",
                "stop_loss": "",
                "tp_trigger_by": "",
                "sl_trigger_by": ""
            },
            "time_now": "1655711675.340162",
            "rate_limit_status": 99,
            "rate_limit_reset_ms": 1655711675338,
            "rate_limit": 100
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 533285,
                "position_idx": 0,
                "symbol": self.exchange_trading_pair,
                "side": order.trade_type.name.capitalize(),
                "order_type": order.order_type.name.capitalize(),
                "price": str(order.price),
                "qty": float(order.amount),
                "time_in_force": "GoodTillCancel",
                "order_status": "Filled",
                "ext_fields": {
                    "o_req_num": 1240101436
                },
                "last_exec_time": "1655716503.5852108",
                "leaves_qty": 0,
                "leaves_value": "0.01",
                "cum_exec_qty": float(order.amount),
                "cum_exec_value": float(order.price + 2),
                "cum_exec_fee": "0.01",
                "reject_reason": "EC_NoError",
                "cancel_type": "UNKNOWN",
                "order_link_id": order.client_order_id or "",
                "created_at": "2022-06-20T09:15:03.585128212Z",
                "updated_at": "2022-06-20T09:15:03.590398174Z",
                "order_id": order.exchange_order_id or "2b1d811c-8ff0-4ef0-92ed-b4ed5fd6de34",
                "take_profit": "23000.00",
                "stop_loss": "18000.00",
                "tp_trigger_by": "MarkPrice",
                "sl_trigger_by": "MarkPrice"
            },
            "time_now": "1655718311.123686",
            "rate_limit_status": 597,
            "rate_limit_reset_ms": 1655718311122,
            "rate_limit": 600
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["result"]["order_status"] = "Cancelled"
        resp["result"]["cum_exec_qty"] = 0
        resp["result"]["cum_exec_value"] = 0
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["result"]["order_status"] = "New"
        resp["result"]["cum_exec_qty"] = 0
        resp["result"]["cum_exec_value"] = 0
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["result"]["order_status"] = "PartiallyFilled"
        resp["result"]["cum_exec_qty"] = float(self.expected_partial_fill_amount)
        resp["result"]["cum_exec_value"] = float(self.expected_partial_fill_price)
        return resp

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "order_id": "Abandoned!!",
                "data": [
                    {
                        "closed_size": 0,
                        "cross_seq": 277136382,
                        "exec_fee": str(self.expected_fill_fee.flat_fees[0].amount),
                        "exec_id": self.expected_fill_trade_id,
                        "exec_price": str(self.expected_partial_fill_price),
                        "exec_qty": float(self.expected_partial_fill_amount),
                        "exec_time": "1571676941.70682",
                        "exec_type": "Trade",
                        "exec_value": "0.00012227",
                        "fee_rate": "0.00075",
                        "last_liquidity_ind": "RemovedLiquidity",
                        "leaves_qty": 0,
                        "nth_fill": 2,
                        "order_id": order.exchange_order_id,
                        "order_link_id": order.client_order_id,
                        "order_price": str(order.price),
                        "order_qty": float(order.amount),
                        "order_type": order.order_type.name.capitalize(),
                        "side": order.trade_type.name.capitalize(),
                        "symbol": self.exchange_trading_pair,
                        "user_id": 1,
                        "trade_time_ms": 1577480599000
                    }
                ]
            },
            "time_now": "1577483699.281488",
            "rate_limit_status": 118,
            "rate_limit_reset_ms": 1577483699244737,
            "rate_limit": 120
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "order_id": "Abandoned!!",
                "data": [
                    {
                        "closed_size": 0,
                        "cross_seq": 277136382,
                        "exec_fee": str(self.expected_fill_fee.flat_fees[0].amount),
                        "exec_id": self.expected_fill_trade_id,
                        "exec_price": str(order.price),
                        "exec_qty": float(order.amount),
                        "exec_time": "1571676941.70682",
                        "exec_type": "Trade",
                        "exec_value": "0.00012227",
                        "fee_rate": "0.00075",
                        "last_liquidity_ind": "RemovedLiquidity",
                        "leaves_qty": 0,
                        "nth_fill": 2,
                        "order_id": order.exchange_order_id,
                        "order_link_id": order.client_order_id,
                        "order_price": str(order.price),
                        "order_qty": float(order.amount),
                        "order_type": order.order_type.name.capitalize(),
                        "side": order.trade_type.name.capitalize(),
                        "symbol": self.exchange_trading_pair,
                        "user_id": 1,
                        "trade_time_ms": 1577480599000
                    }
                ]
            },
            "time_now": "1577483699.281488",
            "rate_limit_status": 118,
            "rate_limit_reset_ms": 1577483699244737,
            "rate_limit": 120
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
