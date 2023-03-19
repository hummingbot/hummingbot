import asyncio
import json
import logging
import re
from copy import deepcopy
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

import pandas as pd
from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_derivative import BitComPerpetualDerivative
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class BitComPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    _logger = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"
        cls.user_id = "someUserId"
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"  # linear
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(
            CONSTANTS.TICKER_PRICE_CHANGE_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def order_creation_url(self):
        url = web_utils.public_rest_url(
            CONSTANTS.CREATE_ORDER_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.public_rest_url(CONSTANTS.ACCOUNT_INFO_URL)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(
            CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        pass

    @property
    def balance_request_mock_response_only_base(self):
        pass

    @property
    def all_symbols_request_mock_response(self):
        mock_response = {
            "code": 0,
            "message": "",
            "data": [
                {
                    "instrument_id": self.exchange_trading_pair,
                    "created_at": 1640944328750,
                    "updated_at": 1640944328750,
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "strike_price": "",
                    "expiration_at": 4102444800000,
                    "option_type": "",
                    "category": "future",
                    "min_price": "0.00050000",
                    "max_price": "1000000.00000000",
                    "price_step": "0.01000000",
                    "min_size": "0.00010000",
                    "size_step": "0.00010000",
                    "delivery_fee_rate": "",
                    "contract_size": "",
                    "contract_size_currency": "BTC",
                    "active": True,
                    "status": "online",
                    "groups": [
                        1,
                        10,
                        100,
                        10000
                    ],
                    "group_steps": [
                        "0.01000000",
                        "0.10000000",
                        "1.00000000",
                        "100.00000000"
                    ],
                    "display_at": 1640944328422,
                    "is_display": True
                }
            ]
        }
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        mock_response = {
            "code": 0,
            "message": "",
            "data": {
                "time": self.target_funding_info_next_funding_utc_timestamp,
                "instrument_id": self.exchange_trading_pair,
                "best_bid": "35310.40000000",
                "best_ask": "35311.15000000",
                "best_bid_qty": "4.46000000",
                "best_ask_qty": "3.10000000",
                "ask_sigma": "",
                "bid_sigma": "",
                "last_price": str(self.expected_latest_price),
                "last_qty": "5.85000000",
                "open24h": "35064.40000000",
                "high24h": "36480.60000000",
                "low24h": "34688.50000000",
                "price_change24h": "0.00700426",
                "volume24h": "2329.37000000",
                "volume_usd24h": "82236990.06700000",
                "open_interest": "94.21840000",
                "funding_rate": "0.00000000",
                "funding_rate8h": "0.00017589",
                "underlying_price": "0.00000000",
                "mark_price": "35310.69417074",
                "index_price": "1",
                "min_sell": "34781.03000000",
                "max_buy": "35840.36000000"
            }
        }

        return mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        mock_response = {
            "code": 0,
            "message": "",
            "data": [
                {
                    "instrument_id": f"{self.base_asset}_{self.quote_asset}",
                    "created_at": 1640944328750,
                    "updated_at": 1640944328750,
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "strike_price": "",
                    "expiration_at": 4102444800000,
                    "option_type": "",
                    "category": "future",
                    "min_price": "0.00050000",
                    "max_price": "1000000.00000000",
                    "price_step": "0.01000000",
                    "min_size": "0.00010000",
                    "size_step": "0.00010000",
                    "delivery_fee_rate": "",
                    "contract_size": "",
                    "contract_size_currency": "BTC",
                    "active": True,
                    "status": "online",
                    "groups": [
                        1,
                        10,
                        100,
                        10000
                    ],
                    "group_steps": [
                        "0.01000000",
                        "0.10000000",
                        "1.00000000",
                        "100.00000000"
                    ],
                    "display_at": 1640944328422,
                    "is_display": True
                }
            ]
        }
        return "INVALID-PAIR", mock_response

    def empty_funding_payment_mock_response(self):
        pass

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, *args, **kwargs):
        pass

    @property
    def network_status_request_successful_mock_response(self):
        mock_response = {
            "code": 0,
            "message": "",
            "data": 1587884283175
        }
        return mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = {
            "code": 0,
            "message": "",
            "data": [
                {
                    "instrument_id": self.exchange_trading_pair,
                    "created_at": 1640944328750,
                    "updated_at": 1640944328750,
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "strike_price": "",
                    "expiration_at": 4102444800000,
                    "option_type": "",
                    "category": "future",
                    "size_step": "0.00010000",
                    "delivery_fee_rate": "",
                    "contract_size": "",
                    "contract_size_currency": "BTC",
                    "active": True,
                    "status": "online",
                    "groups": [
                        1,
                        10,
                        100,
                        10000
                    ],
                    "group_steps": [
                        "0.01000000",
                        "0.10000000",
                        "1.00000000",
                        "100.00000000"
                    ],
                    "display_at": 1640944328422,
                    "is_display": True
                }
            ]
        }
        return mock_response

    @property
    def order_creation_request_successful_mock_response(self):
        mock_response = {
            "code": 0,
            "message": "",
            "data": {
                "order_id": self.expected_exchange_order_id,
                "created_at": 1589523803017,
                "updated_at": 1589523803017,
                "user_id": "51140",
                "instrument_id": self.exchange_trading_pair,
                "order_type": "limit",
                "side": "buy",
                "price": "50000.00000000",
                "qty": "3.00000000",
                "time_in_force": "gtc",
                "avg_price": "0.00000000",
                "filled_qty": "0.00000000",
                "status": "open",
                "is_liquidation": False,
                "auto_price": "0.00000000",
                "auto_price_type": "",
                "taker_fee_rate": "0.00050000",
                "maker_fee_rate": "0.00020000",
                "label": get_new_client_order_id(
                    is_buy=True,
                    trading_pair=self.trading_pair,
                    hbot_order_id_prefix=CONSTANTS.BROKER_ID,
                    max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
                ),
                "stop_price": "0.00000000",
                "reduce_only": False,
                "post_only": False,
                "reject_post_only": False,
                "mmp": False,
                "source": "api",
                "hidden": False
            }
        }
        return mock_response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        mock_response = {
            "code": 0,
            "message": "",
            "data": {
                "user_id": 481554,
                "created_at": 1649923879505,
                "total_collateral": "3170125.05978108",
                "total_margin_balance": "3170125.05978108",
                "total_available": "3169721.64891398",
                "total_initial_margin": "403.41086710",
                "total_maintenance_margin": "303.16627631",
                "total_initial_margin_ratio": "0.00012725",
                "total_maintenance_margin_ratio": "0.00009563",
                "total_liability": "0.00000000",
                "total_unsettled_amount": "-0.84400340",
                "total_future_value": "1.26000000",
                "total_option_value": "0.00000000",
                "spot_orders_hc_loss": "0.00000000",
                "total_position_pnl": "1225.53245820",
                "details": [
                    {
                        "currency": "BTC",
                        "equity": "78.13359310",
                        "liability": "0.00000000",
                        "index_price": "41311.20615385",
                        "cash_balance": "78.13360190",
                        "margin_balance": "78.13359310",
                        "available_balance": "78.12382795",
                        "initial_margin": "0.00976516",
                        "spot_margin": "0.00000000",
                        "maintenance_margin": "0.00733859",
                        "potential_liability": "0.00000000",
                        "interest": "0.00000000",
                        "interest_rate": "0.07000000",
                        "pnl": "0.02966586",
                        "total_delta": "0.48532539",
                        "session_rpl": "0.00001552",
                        "session_upl": "-0.00003595",
                        "option_value": "0.00000000",
                        "option_pnl": "0.00000000",
                        "option_session_rpl": "0.00000000",
                        "option_session_upl": "0.00000000",
                        "option_delta": "0.00000000",
                        "option_gamma": "0.00000000",
                        "option_vega": "0.00000000",
                        "option_theta": "0.00000000",
                        "future_value": "1.23000000",
                        "future_pnl": "0.02966586",
                        "future_session_rpl": "0.00001552",
                        "future_session_upl": "-0.00003595",
                        "future_session_funding": "0.00001552",
                        "future_delta": "0.48532539",
                        "future_available_balance": "76.72788921",
                        "option_available_balance": "76.72788921",
                        "unsettled_amount": "-0.00002043",
                        "usdt_index_price": "41311.20615385"
                    },
                    {
                        "currency": self.quote_asset,
                        "equity": "2000",
                        "liability": "0.00000000",
                        "index_price": "3119.01923077",
                        "cash_balance": "1.99960000",
                        "margin_balance": "1.99960000",
                        "available_balance": "2000",
                        "initial_margin": "0.00000000",
                        "spot_margin": "0.00000000",
                        "maintenance_margin": "0.00000000",
                        "potential_liability": "0.00000000",
                        "interest": "0.00000000",
                        "interest_rate": "0.07000000",
                        "pnl": "0.00000000",
                        "total_delta": "0.00000000",
                        "session_rpl": "0.00000000",
                        "session_upl": "0.00000000",
                        "option_value": "0.00000000",
                        "option_pnl": "0.00000000",
                        "option_session_rpl": "0.00000000",
                        "option_session_upl": "0.00000000",
                        "option_delta": "0.00000000",
                        "option_gamma": "0.00000000",
                        "option_vega": "0.00000000",
                        "option_theta": "0.00000000",
                        "future_value": "0.03000000",
                        "future_pnl": "0.00000000",
                        "future_session_rpl": "0.00000000",
                        "future_session_upl": "0.00000000",
                        "future_session_funding": "0.00000000",
                        "future_delta": "0.00000000",
                        "future_available_balance": "1.99960000",
                        "option_available_balance": "1.99960000",
                        "unsettled_amount": "0.00000000",
                        "usdt_index_price": "3119.01923077"
                    }
                ],
                "usdt_total_collateral": "3170125.05978108",
                "usdt_total_margin_balance": "3170125.05978108",
                "usdt_total_available": "3169721.64891398",
                "usdt_total_initial_margin": "403.41086710",
                "usdt_total_maintenance_margin": "303.16627631",
                "usdt_total_initial_margin_ratio": "0.00012725",
                "usdt_total_maintenance_margin_ratio": "0.00009563",
                "usdt_total_liability": "0.00000000",
                "usdt_total_unsettled_amount": "-0.84400340"
            }
        }
        return mock_response

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("2000"), total_balances[self.quote_asset])

    def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        pass

    def configure_successful_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        pass

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        self.exchange.set_position_mode(PositionMode.HEDGE)
        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message="Position mode PositionMode.HEDGE is not supported. Mode not set."
            )
        )

    def funding_info_event_for_websocket_update(self):
        return {
            "channel": "ticker",
            "timestamp": 1643099422727,
            "module": "linear",
            "data": {
                "ask_sigma": "",
                "best_ask": "36295.00000000",
                "best_ask_qty": "1.00000000",
                "best_bid": "36242.30000000",
                "best_bid_qty": "7.01000000",
                "bid_sigma": "",
                "funding_rate": "0.00203429",
                "funding_rate8h": "0.00009707",
                "high24h": "37377.00000000",
                "instrument_id": "BTC-USD-PERPETUAL",
                "last_price": "36242.30000000",
                "last_qty": "0.42000000",
                "low24h": "33117.95000000",
                "mark_price": "36261.48392714",
                "max_buy": "36805.41000000",
                "min_sell": "35717.56000000",
                "open24h": "34998.65000000",
                "open_interest": "87.69310000",
                "price_change24h": "0.03553423",
                "time": 1643099422727,
                "volume24h": "4422.94140000"
            }
        }

    def is_cancel_request_executed_synchronously_by_server(self):
        return False

    @aioresponses()
    def test_set_position_mode_success(self, mock_api):
        self.exchange.set_position_mode(PositionMode.ONEWAY)
        self.async_run_with_timeout(asyncio.sleep(0.5))
        self.assertTrue(
            self.is_logged(
                log_level="DEBUG",
                message=f"Position mode switched to {PositionMode.ONEWAY}.",
            )
        )

    @property
    def balance_event_websocket_update(self):
        mock_response = {
            "channel": "um_account",
            "timestamp": 1632439007081,
            "module": "um",
            "data": {
                "user_id": 481554,
                "created_at": 1649923879505,
                "total_collateral": "3170125.05978108",
                "total_margin_balance": "3170125.05978108",
                "total_available": "3169721.64891398",
                "total_initial_margin": "403.41086710",
                "total_maintenance_margin": "303.16627631",
                "total_initial_margin_ratio": "0.00012725",
                "total_maintenance_margin_ratio": "0.00009563",
                "total_liability": "0.00000000",
                "total_unsettled_amount": "-0.84400340",
                "spot_orders_hc_loss": "0.00000000",
                "total_position_pnl": "1225.53245820",
                "details": [
                    {
                        "currency": "BTC",
                        "equity": "78.13359310",
                        "liability": "0.00000000",
                        "index_price": "41311.20615385",
                        "cash_balance": "78.13360190",
                        "margin_balance": "78.13359310",
                        "available_balance": "78.12382795",
                        "initial_margin": "0.00976516",
                        "spot_margin": "0.00000000",
                        "maintenance_margin": "0.00733859",
                        "potential_liability": "0.00000000",
                        "interest": "0.00000000",
                        "interest_rate": "0.07000000",
                        "pnl": "0.02966586",
                        "total_delta": "0.48532539",
                        "session_rpl": "0.00001552",
                        "session_upl": "-0.00003595",
                        "option_value": "0.00000000",
                        "option_pnl": "0.00000000",
                        "option_session_rpl": "0.00000000",
                        "option_session_upl": "0.00000000",
                        "option_delta": "0.00000000",
                        "option_gamma": "0.00000000",
                        "option_vega": "0.00000000",
                        "option_theta": "0.00000000",
                        "future_pnl": "0.02966586",
                        "future_session_rpl": "0.00001552",
                        "future_session_upl": "-0.00003595",
                        "future_session_funding": "0.00001552",
                        "future_delta": "0.48532539",
                        "future_available_balance": "76.72788921",
                        "option_available_balance": "76.72788921",
                        "unsettled_amount": "-0.00002043",
                        "usdt_index_price": "41311.20615385"
                    },
                    {
                        "currency": "USD",
                        "equity": "15",
                        "liability": "0.00000000",
                        "index_price": "3119.01923077",
                        "cash_balance": "1.99960000",
                        "margin_balance": "1.99960000",
                        "available_balance": "10",
                        "initial_margin": "0.00000000",
                        "spot_margin": "0.00000000",
                        "maintenance_margin": "0.00000000",
                        "potential_liability": "0.00000000",
                        "interest": "0.00000000",
                        "interest_rate": "0.07000000",
                        "pnl": "0.00000000",
                        "total_delta": "0.00000000",
                        "session_rpl": "0.00000000",
                        "session_upl": "0.00000000",
                        "option_value": "0.00000000",
                        "option_pnl": "0.00000000",
                        "option_session_rpl": "0.00000000",
                        "option_session_upl": "0.00000000",
                        "option_delta": "0.00000000",
                        "option_gamma": "0.00000000",
                        "option_vega": "0.00000000",
                        "option_theta": "0.00000000",
                        "future_pnl": "0.00000000",
                        "future_session_rpl": "0.00000000",
                        "future_session_upl": "0.00000000",
                        "future_session_funding": "0.00000000",
                        "future_delta": "0.00000000",
                        "future_available_balance": "1.99960000",
                        "option_available_balance": "1.99960000",
                        "unsettled_amount": "0.00000000",
                        "usdt_index_price": "3119.01923077"
                    }
                ],
                "usdt_total_collateral": "3170125.05978108",
                "usdt_total_margin_balance": "3170125.05978108",
                "usdt_total_available": "3169721.64891398",
                "usdt_total_initial_margin": "403.41086710",
                "usdt_total_maintenance_margin": "303.16627631",
                "usdt_total_initial_margin_ratio": "0.00012725",
                "usdt_total_maintenance_margin_ratio": "0.00009563",
                "usdt_total_liability": "0.00000000",
                "usdt_total_unsettled_amount": "-0.84400340"
            }
        }
        return mock_response

    @property
    def position_event_websocket_update(self):
        mock_response = {
            "channel": "position",
            "timestamp": 1643101230232,
            "module": "linear",
            "data": [
                {
                    "avg_price": "42474.49668874",
                    "category": "future",
                    "expiration_at": 4102444800000,
                    "index_price": "36076.66600000",
                    "initial_margin": "21.81149685",
                    "instrument_id": "BTC-USD-PERPETUAL",
                    "leverage": "50.00000000",
                    "maintenance_margin": "16.36076260",
                    "mark_price": "36097.57784846",
                    "position_pnl": "192.58294898",
                    "position_session_rpl": "-0.16699671",
                    "position_session_upl": "-1.28505101",
                    "qty": "1",
                    "qty_base": "1",
                    "roi": "8.82942378",
                    "session_avg_price": "36055.02649047",
                    "session_funding": "-0.16699671",
                    "liq_price": "3587263.29572346",
                }
            ]
        }

        return mock_response

    @property
    def position_event_websocket_update_zero(self):
        mock_response = {
            "channel": "position",
            "timestamp": 1643101230232,
            "module": "linear",
            "data": [
                {
                    "avg_price": "42474.49668874",
                    "category": "future",
                    "expiration_at": 4102444800000,
                    "index_price": "36076.66600000",
                    "initial_margin": "21.81149685",
                    "instrument_id": "BTC-USD-PERPETUAL",
                    "leverage": "50.00000000",
                    "maintenance_margin": "16.36076260",
                    "mark_price": "36097.57784846",
                    "position_pnl": "192.58294898",
                    "position_session_rpl": "-0.16699671",
                    "position_session_upl": "-1.28505101",
                    "qty": "0",
                    "qty_base": "1",
                    "roi": "8.82942378",
                    "session_avg_price": "36055.02649047",
                    "session_funding": "-0.16699671",
                    "liq_price": "3587263.29572346",
                }
            ]
        }

        return mock_response

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def funding_payment_mock_response(self):
        raise NotImplementedError

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
        funding_info = mock_response["data"]
        funding_info["mark_price"] = self.target_funding_info_mark_price
        funding_info["index_price"] = self.target_funding_info_index_price
        funding_info["funding_rate"] = self.target_funding_info_rate
        return mock_response

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        rule = self.trading_rules_request_mock_response["data"][0]
        collateral_token = rule["quote_currency"]

        return TradingRule(self.trading_pair,
                           min_order_size=Decimal(rule.get("min_size")),
                           min_price_increment=Decimal(rule.get("price_step")),
                           min_base_amount_increment=Decimal(rule.get("size_step")),
                           buy_order_collateral_token=collateral_token,
                           sell_order_collateral_token=collateral_token,
                           )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

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

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}-PERPETUAL"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = BitComPerpetualDerivative(
            client_config_map,
            self.api_key,
            self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        # exchange._last_trade_history_timestamp = self.latest_trade_hist_timestamp
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        request_headers = request_call.kwargs["headers"]
        self.assertIn("X-Bit-Access-Key", request_headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(self.exchange_trading_pair, request_data["instrument_id"])
        self.assertEqual(order.amount, abs(Decimal(str(request_data["qty"]))))
        self.assertEqual(order.client_order_id, request_data["label"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertIsNone(request_params)

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]
        self.assertIsNone(request_data)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["instrument_id"])
        self.assertEqual(order.exchange_order_id, request_params["order_id"])

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        """
        :return: the URL configured for the cancelation
        """
        url = web_utils.public_rest_url(
            CONSTANTS.CANCEL_ORDER_URL
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
        url = web_utils.public_rest_url(
            CONSTANTS.CANCEL_ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.post(regex_url, status=400, callback=callback)
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
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )

        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )
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
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ORDER_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL,
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.public_rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_failed_set_leverage(
            self,
            leverage: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> Tuple[str, str]:
        endpoint = CONSTANTS.SET_LEVERAGE_URL
        url = web_utils.public_rest_url(
            endpoint
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        err_msg = "Unable to set leverage"
        mock_response = {
            "code": 0,
            "message": "",
            "data": {
                "pair": "BTC-USD",
                "leverage_ratio": "60.00000000"
            }
        }
        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)
        return url, err_msg

    def configure_successful_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ):
        endpoint = CONSTANTS.SET_LEVERAGE_URL
        url = web_utils.public_rest_url(
            endpoint
        )
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "code": 0,
            "message": "",
            "data": {
                "pair": "BTC-USD",
                "leverage_ratio": str(leverage)
            }
        }

        mock_api.post(regex_url, body=json.dumps(mock_response), callback=callback)

        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "channel": "order",
            "timestamp": 1643101425658,
            "module": "linear",
            "data": [
                {
                    "auto_price": "0.00000000",
                    "auto_price_type": "",
                    "avg_price": "0.00000000",
                    "cash_flow": "0.00000000",
                    "created_at": 1643101425539,
                    "fee": "0.00000000",
                    "filled_qty": "0.00000000",
                    "hidden": False,
                    "initial_margin": "",
                    "instrument_id": self.exchange_trading_pair,
                    "is_liquidation": False,
                    "is_um": True,
                    "label": order.client_order_id or "",
                    "maker_fee_rate": "0.00010000",
                    "mmp": False,
                    "order_id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "order_type": "limit",
                    "pnl": "0.00000000",
                    "post_only": False,
                    "price": order.price,
                    "qty": float(order.amount),
                    "reduce_only": False,
                    "reject_post_only": False,
                    "reorder_index": 0,
                    "side": "buy",
                    "source": "web",
                    "status": "open",
                    "stop_order_id": "",
                    "stop_price": "0.00000000",
                    "taker_fee_rate": "0.00010000",
                    "time_in_force": "gtc",
                    "updated_at": 1643101425539,
                    "user_id": "606122"
                }
            ]
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "channel": "order",
            "timestamp": 1643101425658,
            "module": "linear",
            "data": [
                {
                    "auto_price": "0.00000000",
                    "auto_price_type": "",
                    "avg_price": "0.00000000",
                    "cash_flow": "0.00000000",
                    "created_at": 1643101425539,
                    "fee": "0.00000000",
                    "filled_qty": "0.00000000",
                    "hidden": False,
                    "initial_margin": "",
                    "instrument_id": self.exchange_trading_pair,
                    "is_liquidation": False,
                    "is_um": True,
                    "label": order.client_order_id or "",
                    "maker_fee_rate": "0.00010000",
                    "mmp": False,
                    "order_id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "order_type": "limit",
                    "pnl": "0.00000000",
                    "post_only": False,
                    "price": order.price,
                    "qty": float(order.amount),
                    "reduce_only": False,
                    "reject_post_only": False,
                    "reorder_index": 0,
                    "side": "buy",
                    "source": "web",
                    "status": "cancelled",
                    "stop_order_id": "",
                    "stop_price": "0.00000000",
                    "taker_fee_rate": "0.00010000",
                    "time_in_force": "gtc",
                    "updated_at": 1643101425539,
                    "user_id": "606122"
                }
            ]
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()

        return {
            "channel": "order",
            "timestamp": 1643101425658,
            "module": "linear",
            "data": [
                {
                    "auto_price": "0.00000000",
                    "auto_price_type": "",
                    "avg_price": "0.00000000",
                    "cash_flow": "0.00000000",
                    "created_at": 1643101425539,
                    "fee": "0.00000000",
                    "filled_qty": "0.00000000",
                    "hidden": False,
                    "initial_margin": "",
                    "instrument_id": self.exchange_trading_pair,
                    "is_liquidation": False,
                    "is_um": True,
                    "label": order.client_order_id or "",
                    "maker_fee_rate": "0.00010000",
                    "mmp": False,
                    "order_id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "order_type": "limit",
                    "pnl": "0.00000000",
                    "post_only": False,
                    "price": order.price,
                    "qty": float(order.amount),
                    "reduce_only": False,
                    "reject_post_only": False,
                    "reorder_index": 0,
                    "side": "buy",
                    "source": "web",
                    "status": "filled",
                    "stop_order_id": "",
                    "stop_price": "0.00000000",
                    "taker_fee_rate": "0.00010000",
                    "time_in_force": "gtc",
                    "updated_at": 1643101425539,
                    "user_id": "606122"
                }
            ]
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            "channel": "user_trade",
            "timestamp": 1643101722258,
            "module": "linear",
            "data": [
                {
                    "created_at": 1643101722020,
                    "fee": Decimal(self.expected_fill_fee.flat_fees[0].amount),
                    "fee_rate": "0.00010000",
                    "index_price": "36214.05400000",
                    "instrument_id": self.exchange_trading_pair,
                    "is_block_trade": False,
                    "is_taker": True,
                    "label": order.client_order_id or "",
                    "order_id": order.exchange_order_id or "1640b725-75e9-407d-bea9-aae4fc666d33",
                    "order_type": "limit",
                    "price": str(order.price),
                    "qty": Decimal(order.amount),
                    "side": "buy",
                    "sigma": "0.00000000",
                    "trade_id": self.expected_fill_trade_id,
                    "underlying_price": "",
                    "usd_price": ""
                }
            ]
        }

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        pass

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

    def test_user_stream_update_for_new_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["11"]

        order_event = self.order_event_for_new_order_websocket_update(order=order)

        mock_queue = AsyncMock()
        event_messages = [order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        event = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, event.timestamp)
        self.assertEqual(order.order_type, event.type)
        self.assertEqual(order.trading_pair, event.trading_pair)
        self.assertEqual(order.amount, event.amount)
        self.assertTrue(order.is_open)

    def test_user_stream_balance_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = BitComPerpetualDerivative(
            client_config_map=client_config_map,
            bit_com_perpetual_api_key=self.api_key,
            bit_com_perpetual_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        connector._set_current_timestamp(1640780000)

        balance_event = self.balance_event_websocket_update

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [balance_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.quote_asset))

    def test_user_stream_position_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = BitComPerpetualDerivative(
            client_config_map=client_config_map,
            bit_com_perpetual_api_key=self.api_key,
            bit_com_perpetual_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        connector._set_current_timestamp(1640780000)

        position_event = self.position_event_websocket_update

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [position_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        self._simulate_trading_rules_initialized()
        self.exchange.account_positions[self.trading_pair] = Position(

            trading_pair=self.trading_pair,
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal('1'),
            entry_price=Decimal('1'),
            amount=Decimal('1'),
            leverage=Decimal('1'),
        )
        amount_precision = Decimal(self.exchange.trading_rules[self.trading_pair].min_base_amount_increment)
        try:
            asyncio.get_event_loop().run_until_complete(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, Decimal(1e6) * amount_precision)

    def test_user_stream_remove_position_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = BitComPerpetualDerivative(
            client_config_map=client_config_map,
            bit_com_perpetual_api_key=self.api_key,
            bit_com_perpetual_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        connector._set_current_timestamp(1640780000)

        position_event = self.position_event_websocket_update_zero
        self._simulate_trading_rules_initialized()
        self.exchange.account_positions[self.trading_pair] = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.SHORT,
            unrealized_pnl=Decimal('1'),
            entry_price=Decimal('1'),
            amount=Decimal('1'),
            leverage=Decimal('1'),
        )
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [position_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            asyncio.get_event_loop().run_until_complete(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass
        self.assertEqual(len(self.exchange.account_positions), 0)

    def test_supported_position_modes(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        linear_connector = BitComPerpetualDerivative(
            client_config_map=client_config_map,
            bit_com_perpetual_api_key=self.api_key,
            bit_com_perpetual_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
        )

        expected_result = [PositionMode.ONEWAY]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()
        buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)
        self.assertEqual(self.quote_asset, buy_collateral_token)
        self.assertEqual(self.quote_asset, sell_collateral_token)

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
            self.target_funding_info_next_funding_utc_timestamp + CONSTANTS.FUNDING_RATE_INTERNAL_MIL_SECOND,
            funding_info.next_funding_utc_timestamp
        )
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    @aioresponses()
    def test_resolving_trading_pair_symbol_duplicates_on_trading_rules_update_first_is_good(self, mock_api):
        self.exchange._set_current_timestamp(1000)

        url = self.trading_rules_url

        response = self.trading_rules_request_mock_response
        results = response["data"]
        duplicate = deepcopy(results[0])
        duplicate["instrument_id"] = f"{self.exchange_trading_pair}_12345"
        duplicate["min_size"] = str(float(duplicate["min_size"]) + 1)
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
        results = response["data"]
        duplicate = deepcopy(results[0])
        duplicate["instrument_id"] = f"{self.exchange_trading_pair}_12345"
        duplicate["min_size"] = str(float(duplicate["min_size"]) + 1)
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
        results = response["data"]
        first_duplicate = deepcopy(results[0])
        first_duplicate["instrument_id"] = f"{self.exchange_trading_pair}_12345"
        first_duplicate["min_size"] = (
            str(float(first_duplicate["min_size"]) + 1)
        )
        second_duplicate = deepcopy(results[0])
        second_duplicate["instrument_id"] = f"{self.exchange_trading_pair}_67890"
        second_duplicate["min_size"] = (
            str(float(second_duplicate["min_size"]) + 2)
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

    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_api):
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
        order = self.exchange.in_flight_orders["11"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        url = self.configure_erroneous_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(cancel_request)
        self.validate_order_cancelation_request(
            order=order,
            request_call=cancel_request)

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
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
        self.assertEqual(leverage, fill_event.leverage)
        self.assertEqual(PositionAction.OPEN.value, fill_event.position)

        buy_event = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * fill_event.price, buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
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

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "message": "",
            "data": {
                "num_cancelled": 1
            }
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "code": 0,
            "message": "",
            "data": [{
                "order_id": order.exchange_order_id,
                "created_at": 1589202185000,
                "updated_at": 1589460149000,
                "user_id": "51140",
                "instrument_id": self.exchange_trading_pair,
                "order_type": "limit",
                "side": "buy",
                "price": str(order.price),
                "qty": float(order.amount),
                "time_in_force": "gtc",
                "avg_price": str(order.price),
                "filled_qty": float(order.amount),
                "status": "filled",
                "fee": "0.00000000",
                "is_liquidation": False,
                "auto_price": "0.00000000",
                "auto_price_type": "",
                "pnl": "0.00000000",
                "cash_flow": "0.00000000",
                "initial_margin": "",
                "taker_fee_rate": "0.00050000",
                "maker_fee_rate": "0.00020000",
                "label": order.client_order_id or "2b1d811c-8ff0-4ef0-92ed-b4ed5fd6de34",
                "stop_price": "0.00000000",
                "reduce_only": False,
                "post_only": False,
                "reject_post_only": False,
                "mmp": False,
                "reorder_index": 1,
                "source": "api",
                "hidden": False,
                "is_um": True
            }]
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"][0]["status"] = "cancelled"
        resp["data"][0]["filled_qty"] = "0"
        resp["data"][0]["avg_price"] = "0"
        return resp

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"][0]["status"] = "open"
        resp["data"][0]["avg_price"] = "0"
        return resp

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"][0]["status"] = "open"
        resp["data"][0]["avg_price"] = str(order.price)
        return resp

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        pass

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        resp = self._order_status_request_completely_filled_mock_response(order)
        resp["data"][0]["status"] = "open"
        resp["data"][0]["avg_price"] = str(order.price)
        resp["data"][0]["filled_qty"] = float(order.amount) / 2
        return resp

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
        return {
            "code": 0,
            "message": "",
            "data": [{
                "trade_id": self.expected_fill_trade_id,
                "order_id": order.exchange_order_id,
                "instrument_id": self.exchange_trading_pair,
                "qty": str(Decimal(order.amount)),
                "price": str(order.price),
                "sigma": "0.00000000",
                "underlying_price": "",
                "index_price": "50012.81000000",
                "usd_price": "",
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "fee_rate": "0.00050000",
                "side": "buy",
                "created_at": 1589521371000,
                "is_taker": True,
                "order_type": "limit",
                "label": order.client_order_id,
            }]
        }

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }
