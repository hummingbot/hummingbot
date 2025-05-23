import asyncio
import functools
import json
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pandas as pd
from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_api_order_book_data_source import (
    BitmartPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative import BitmartPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent


class BitmartPerpetualDerivativeUnitTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = CONSTANTS.DOMAIN

        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = BitmartPerpetualDerivative(
            client_config_map=self.client_config_map,
            bitmart_perpetual_api_key="testAPIKey",
            bitmart_perpetual_api_secret="testSecret",
            bitmart_perpetual_memo="testMemo",
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        if hasattr(self.exchange, "_time_synchronizer"):
            self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
            self.exchange._time_synchronizer.logger().setLevel(1)
            self.exchange._time_synchronizer.logger().addHandler(self)

        BitmartPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.symbol: self.trading_pair})
        }

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant()
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL,
                                        domain=CONSTANTS.DOMAIN)
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.EXCHANGE_INFO_URL,
            domain=CONSTANTS.DOMAIN
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL,
                                        domain=CONSTANTS.DOMAIN)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL,
                                        domain=CONSTANTS.DOMAIN)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.ASSETS_DETAIL,
                                         domain=CONSTANTS.DOMAIN)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.EXCHANGE_INFO_URL,
            domain=CONSTANTS.DOMAIN
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.private_rest_url(
            path_url=CONSTANTS.GET_INCOME_HISTORY_URL,
            domain=CONSTANTS.DOMAIN
        )
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        BitmartPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.funding_payment_completed_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.FundingPaymentCompleted, self.funding_payment_completed_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def _get_position_risk_api_endpoint_single_position_list(self) -> List[Dict[str, Any]]:
        positions = {
            "code": 1000,
            "message": "Ok",
            "data": [
                {
                    "symbol": self.symbol,
                    "leverage": "5",
                    "timestamp": self.start_timestamp,
                    "current_fee": "5.00409471",
                    "open_timestamp": 1662714817820,
                    "current_value": "16680.3157",
                    "mark_value": "16673.27053207877",
                    "mark_price": "93000.50",
                    "position_value": "18584.272343943943943944339",
                    "position_cross": "3798.397624451826977945",
                    "maintenance_margin": "4798.397624451826977945",
                    "margin_type": "Isolated",
                    "close_vol": "100",
                    "close_avg_price": "20700.7",
                    "open_avg_price": "20200",
                    "entry_price": "20201",
                    "current_amount": "1",
                    "unrealized_value": "1903.956643943943943944339",
                    "realized_value": "55.049173071454605573",
                    "position_type": 1
                }
            ],
            "trace": "ae96cae5-1f09-4ea5-971e-4474a6724bc8"
        }
        return positions

    def _get_wrong_symbol_position_risk_api_endpoint_single_position_list(self) -> List[Dict[str, Any]]:
        positions = {
            "code": 1000,
            "message": "Ok",
            "data": [
                {
                    "symbol": f"{self.symbol}_20250108",
                    "leverage": "5",
                    "timestamp": self.start_timestamp,
                    "current_fee": "5.00409471",
                    "open_timestamp": 1662714817820,
                    "current_value": "16680.3157",
                    "mark_value": "16673.27053207877",
                    "mark_price": "93000.50",
                    "position_value": "18584.272343943943943944339",
                    "position_cross": "3798.397624451826977945",
                    "maintenance_margin": "4798.397624451826977945",
                    "margin_type": "Isolated",
                    "close_vol": "100",
                    "close_avg_price": "20700.7",
                    "open_avg_price": "20200",
                    "entry_price": "20201",
                    "current_amount": "899",
                    "unrealized_value": "1903.956643943943943944339",
                    "realized_value": "55.049173071454605573",
                    "position_type": 2
                }
            ],
            "trace": "ae96cae5-1f09-4ea5-971e-4474a6724bc8"
        }
        return positions

    def _get_account_update_ws_event_single_position_dict(self) -> Dict[str, Any]:
        account_update = {
            "group": "futures/position",
            "data": [
                {
                    "symbol": self.symbol,
                    "hold_volume": "2000",
                    "position_type": 1,
                    "open_type": 1,
                    "frozen_volume": "0",
                    "close_volume": "0",
                    "hold_avg_price": "19406.2092",
                    "close_avg_price": "0",
                    "open_avg_price": "19406.2092",
                    "liquidate_price": "15621.998406",
                    "create_time": 1662692862255,
                    "update_time": 1662692862255
                }
            ]
        }
        return account_update

    def _get_wrong_symbol_account_update_ws_event_single_position_dict(self) -> Dict[str, Any]:
        account_update = {
            "group": "futures/position",
            "data": [
                {
                    "symbol": f"{self.symbol}_20250108",
                    "hold_volume": "2000",
                    "position_type": 1,
                    "open_type": 1,
                    "frozen_volume": "0",
                    "close_volume": "0",
                    "hold_avg_price": "19406.2092",
                    "close_avg_price": "0",
                    "open_avg_price": "19406.2092",
                    "liquidate_price": "15621.998406",
                    "create_time": 1662692862255,
                    "update_time": 1662692862255
                }
            ]
        }
        return account_update

    @staticmethod
    def _get_position_mode_mock_response(position_mode: str = "hedge_mode"):
        position_mode_resp = {
            "code": 1000,
            "message": "Ok",
            "data": {
                "position_mode": position_mode
            },
            "trace": "b15f261868b540889e57f826e0420621.97.17443984622695574"
        }
        return position_mode_resp

    def _get_income_history_dict(self) -> List:
        income_history = {
            "code": 1000,
            "message": "Ok",
            "data": [
                {
                    "symbol": "",
                    "type": "Transfer",
                    "amount": "-0.37500000",
                    "asset": "USDT",
                    "time": "1570608000000",
                    "tran_id": "9689322392"
                },
                {
                    "symbol": self.symbol,
                    "type": "Funding Fee",
                    "amount": "-0.01000000",
                    "asset": "USDT",
                    "time": "1570636800000",
                    "tran_id": "9689322392"
                }
            ],
            "trace": "80ba1f07-1b6f-46ad-81dd-78ac7e9bbccd"
        }
        return income_history

    def _get_funding_info_dict(self) -> Dict[str, Any]:
        funding_info = {
            "code": 1000,
            "message": "Ok",
            "data": {
                "timestamp": 1662518172178,
                "symbol": self.symbol,
                "rate_value": "0.000164",
                "expected_rate": "0.000164",
                "funding_time": 1709971200000,
                "funding_upper_limit": "0.0375",
                "funding_lower_limit": "-0.0375"
            },
            "trace": "13f7fda9-9543-4e11-a0ba-cbe117989988"
        }
        return funding_info

    def _get_trading_pair_symbol_map(self) -> Dict[str, str]:
        trading_pair_symbol_map = {self.symbol: f"{self.base_asset}-{self.quote_asset}"}
        return trading_pair_symbol_map

    def _get_exchange_info_mock_response(self,
                                         contract_size: int = 10,
                                         min_volume: int = 1,
                                         vol_precision: float = 0.1,
                                         price_precision: float = 0.01,
                                         last_price: float = 10.0) -> Dict[str, Any]:
        mocked_exchange_info = {
            "code": 1000,
            "message": "Ok",
            "trace": "9b92a999-9463-4c96-91a4-93ad1cad0d72",
            "data": {
                "symbols": [
                    {
                        "symbol": self.symbol,
                        "product_type": 1,
                        "open_timestamp": 1594080000123,
                        "expire_timestamp": 0,
                        "settle_timestamp": 0,
                        "base_currency": self.base_asset,
                        "quote_currency": self.quote_asset,
                        "last_price": str(last_price),
                        "volume_24h": "18969368",
                        "turnover_24h": "458933659.7858",
                        "index_price": "23945.25191635",
                        "index_name": "BTCUSDT",
                        "contract_size": str(contract_size),
                        "min_leverage": "1",
                        "max_leverage": "100",
                        "price_precision": str(price_precision),
                        "vol_precision": str(vol_precision),
                        "max_volume": "500000",
                        "market_max_volume": "500000",
                        "min_volume": str(min_volume),
                        "funding_rate": "0.0001",
                        "expected_funding_rate": "0.00011",
                        "open_interest": "4134180870",
                        "open_interest_value": "94100888927.0433258",
                        "high_24h": "23900",
                        "low_24h": "23100",
                        "change_24h": "0.004",
                        "funding_interval_hours": 8
                    }
                ]
            }
        }
        return mocked_exchange_info

    def _get_exchange_info_with_unknown_pair_mock_response(self,
                                                           contract_size: int = 10,
                                                           min_volume: int = 1,
                                                           vol_precision: float = 0.1,
                                                           price_precision: float = 0.01,
                                                           last_price: float = 10.0) -> Dict[str, Any]:
        mocked_exchange_info = {
            "code": 1000,
            "message": "Ok",
            "trace": "9b92a999-9463-4c96-91a4-93ad1cad0d72",
            "data": {
                "symbols": [
                    {
                        "symbol": "UNKNOWN",
                        "product_type": 1,
                        "open_timestamp": 1594080000123,
                        "expire_timestamp": 0,
                        "settle_timestamp": 0,
                        "base_currency": "UNKNOWN",
                        "quote_currency": self.quote_asset,
                        "last_price": str(last_price),
                        "volume_24h": "18969368",
                        "turnover_24h": "458933659.7858",
                        "index_price": "23945.25191635",
                        "index_name": "UNKNOWNUSDT",
                        "contract_size": str(contract_size),
                        "min_leverage": "1",
                        "max_leverage": "100",
                        "price_precision": str(price_precision),
                        "vol_precision": str(vol_precision),
                        "max_volume": "500000",
                        "market_max_volume": "500000",
                        "min_volume": str(min_volume),
                        "funding_rate": "0.0001",
                        "expected_funding_rate": "0.00011",
                        "open_interest": "4134180870",
                        "open_interest_value": "94100888927.0433258",
                        "high_24h": "23900",
                        "low_24h": "23100",
                        "change_24h": "0.004",
                        "funding_interval_hours": 8
                    },
                    {
                        "symbol": self.symbol,
                        "product_type": 1,
                        "open_timestamp": 1594080000123,
                        "expire_timestamp": 0,
                        "settle_timestamp": 0,
                        "base_currency": self.base_asset,
                        "quote_currency": self.quote_asset,
                        "last_price": str(last_price),
                        "volume_24h": "18969368",
                        "turnover_24h": "458933659.7858",
                        "index_price": "23945.25191635",
                        "index_name": "BTCUSDT",
                        "contract_size": str(contract_size),
                        "min_leverage": "1",
                        "max_leverage": "100",
                        "price_precision": str(price_precision),
                        "vol_precision": str(vol_precision),
                        "max_volume": "500000",
                        "market_max_volume": "500000",
                        "min_volume": str(min_volume),
                        "funding_rate": "0.0001",
                        "expected_funding_rate": "0.00011",
                        "open_interest": "4134180870",
                        "open_interest_value": "94100888927.0433258",
                        "high_24h": "23900",
                        "low_24h": "23100",
                        "change_24h": "0.004",
                        "funding_interval_hours": 8
                    }
                ]
            }
        }
        return mocked_exchange_info

    def _get_exchange_info_error_mock_response(self,
                                               contract_size: int = 10,
                                               min_volume: int = 1,
                                               vol_precision: float = 0.1,
                                               price_precision: float = 0.01,
                                               last_price: float = 10.0) -> Dict[str, Any]:
        mocked_exchange_info = {
            "code": 1000,
            "message": "Ok",
            "trace": "9b92a999-9463-4c96-91a4-93ad1cad0d72",
            "data": {
                "symbols": [
                    {
                        "symbol": self.symbol,
                        "product_type": 1,
                        "open_timestamp": 1594080000123,
                        "expire_timestamp": 0,
                        "settle_timestamp": 0,
                        "base_currency": self.base_asset,
                        "last_price": str(last_price),
                        "volume_24h": "18969368",
                        "turnover_24h": "458933659.7858",
                        "index_price": "23945.25191635",
                        "index_name": "BTCUSDT",
                        "contract_size": str(contract_size),
                        "min_leverage": "1",
                        "max_leverage": "100",
                        "price_precision": str(price_precision),
                        "vol_precision": str(vol_precision),
                        "max_volume": "500000",
                        "market_max_volume": "500000",
                        "min_volume": str(min_volume),
                        "funding_rate": "0.0001",
                        "expected_funding_rate": "0.00011",
                        "open_interest": "4134180870",
                        "open_interest_value": "94100888927.0433258",
                        "high_24h": "23900",
                        "low_24h": "23100",
                        "change_24h": "0.004",
                        "funding_interval_hours": 8
                    }
                ]
            }
        }
        return mocked_exchange_info

    @aioresponses()
    def test_existing_account_position_detected_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.trading_pair.replace("-", ""), self.symbol)

    @aioresponses()
    def test_wrong_symbol_position_detected_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()

        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_wrong_symbol_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 0)

    @aioresponses()
    def test_account_position_updated_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 1)

        positions["data"][0]["current_amount"] = "2"
        req_mock.get(regex_url, body=json.dumps(positions))
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2)

    @aioresponses()
    def test_new_account_position_detected_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps({"data": []}))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 0)

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)

    @aioresponses()
    def test_closed_account_position_removed_on_positions_update(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)

        positions["data"][0]["current_amount"] = "0"
        req_mock.get(regex_url, body=json.dumps(positions))
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 0)

    @aioresponses()
    @patch("hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative.BitmartPerpetualDerivative.get_price_by_type")
    def test_new_account_position_detected_on_stream_event(self, mock_api, mock_price):
        self._simulate_trading_rules_initialized()

        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 0)

        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=json.dumps(positions))

        account_update = self._get_account_update_ws_event_single_position_dict()
        self.async_run_with_timeout(self.exchange._process_user_stream_event(account_update))

        self.assertEqual(len(self.exchange.account_positions), 1)

    @aioresponses()
    @patch("hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative.BitmartPerpetualDerivative.get_price_by_type")
    def test_account_position_updated_on_stream_event(self, mock_api, mock_price):

        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 1)

        account_update = self._get_account_update_ws_event_single_position_dict()

        mock_price.return_value = Decimal("18452.2")
        self.async_run_with_timeout(self.exchange._process_user_stream_event(account_update))

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2000)

    @aioresponses()
    @patch("hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative.BitmartPerpetualDerivative.get_price_by_type")
    def test_closed_account_position_removed_on_stream_event(self, mock_api, mock_price):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 1)

        account_update = self._get_account_update_ws_event_single_position_dict()
        account_update["data"][0]["hold_volume"] = "0.0"
        mock_price.return_value = Decimal("18452.2")

        self.async_run_with_timeout(self.exchange._process_user_stream_event(account_update))

        self.assertEqual(len(self.exchange.account_positions), 0)

    @aioresponses()
    def test_wrong_symbol_new_account_position_detected_on_stream_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 0)

        url = web_utils.private_rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=json.dumps(positions))

        account_update = self._get_wrong_symbol_account_update_ws_event_single_position_dict()
        self.async_run_with_timeout(self.exchange._process_user_stream_event(account_update))

        self.assertEqual(len(self.exchange.account_positions), 0)

    def test_supported_position_modes(self):
        linear_connector = self.exchange
        expected_result = [PositionMode.ONEWAY, PositionMode.HEDGE]
        self.assertEqual(expected_result, linear_connector.supported_position_modes())

    def test_format_trading_rules(self):
        contract_size = 1.0
        min_volume = 2.0
        vol_precision = 3.0
        price_precision = 1.0
        last_price = 6.0
        mocked_response = self._get_exchange_info_mock_response(contract_size, min_volume, vol_precision,
                                                                price_precision, last_price)
        self._simulate_trading_rules_initialized()
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[0]
        min_order_size = min_volume * contract_size
        self.assertEqual(min_order_size, trading_rule.min_order_size)
        self.assertEqual(price_precision, trading_rule.min_price_increment)
        self.assertEqual(vol_precision, trading_rule.min_base_amount_increment)
        self.assertEqual(min_order_size * last_price, trading_rule.min_notional_size)
        self.assertEqual(self.quote_asset, trading_rule.buy_order_collateral_token)
        self.assertEqual(self.quote_asset, trading_rule.sell_order_collateral_token)

    def test_format_trading_rules_exception(self):
        mocked_response = self._get_exchange_info_error_mock_response()
        self._simulate_trading_rules_initialized()

        self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))
        self.assertTrue(self._is_logged(
            "ERROR",
            f"Error parsing the trading pair rule {mocked_response['data']['symbols'][0]}. Error: 'quote_currency'. Skipping..."
        ))

    def test_get_collateral_token(self):
        margin_asset = self.quote_asset
        self._simulate_trading_rules_initialized()

        self.assertEqual(margin_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(margin_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    def _get_order_channel_mock_response(self,
                                         order_id="OID1",
                                         exchange_order_id="8886774",
                                         price="10000",
                                         deal_size="0",
                                         state=2,
                                         amount=Decimal("1"),
                                         fee="-0.00027",
                                         fill_qty="0",
                                         last_trade_id=1234):
        mocked_response = {
            "group": "futures/order",
            "data": [
                {
                    "action": 3,
                    "order": {
                        "order_id": exchange_order_id,
                        "client_order_id": order_id,
                        "price": price,
                        "size": amount,
                        "symbol": self.symbol,
                        "state": state,
                        "side": 1,
                        "type": "limit",
                        "leverage": "5",
                        "open_type": "isolated",
                        "deal_avg_price": price,
                        "deal_size": deal_size,
                        "create_time": 1662368173000,
                        "update_time": 1662368173000,
                        "plan_order_id": "220901412155341",
                        "last_trade": {
                            "lastTradeID": last_trade_id,
                            "fillQty": fill_qty,
                            "fillPrice": price,
                            "fee": fee,
                            "feeCcy": "USDT"
                        },
                        "trigger_price": "-",
                        "trigger_price_type": "-",
                        "execution_price": "-",
                        "activation_price_type": "-",
                        "activation_price": "-",
                        "callback_rate": "-"
                    }
                }
            ]
        }
        return mocked_response

    def test_buy_order_fill_event_takes_fee_from_update_event(self):
        self._simulate_trading_rules_initialized()
        order_id = "test_id"
        exchange_order_id = "ex_test_id"
        price = "10.0"
        amount = "5.0"
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
            leverage=5,
            position_action=PositionAction.OPEN,
        )

        partial_fill = self._get_order_channel_mock_response(order_id=order_id,
                                                             exchange_order_id=exchange_order_id,
                                                             amount=amount,
                                                             state=2,
                                                             deal_size="2",
                                                             fill_qty="20",
                                                             last_trade_id=1234)
        self.async_run_with_timeout(self.exchange._process_user_stream_event(partial_fill))
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        fee = TokenAmount(token=partial_fill["data"][0]["order"]["last_trade"]["feeCcy"],
                          amount=Decimal(partial_fill["data"][0]["order"]["last_trade"]["fee"]))
        self.assertEqual([fee], fill_event.trade_fee.flat_fees)

        complete_fill = self._get_order_channel_mock_response(order_id=order_id,
                                                              exchange_order_id=exchange_order_id,
                                                              amount=amount,
                                                              state=4,
                                                              deal_size="5",
                                                              fill_qty="3",
                                                              last_trade_id=1235)
        self.async_run_with_timeout(self.exchange._process_user_stream_event(complete_fill))

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        fee = TokenAmount(token=partial_fill["data"][0]["order"]["last_trade"]["feeCcy"],
                          amount=Decimal(partial_fill["data"][0]["order"]["last_trade"]["fee"]))
        self.assertEqual([fee], fill_event.trade_fee.flat_fees)
        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    def test_sell_order_fill_event_takes_fee_from_update_event(self):
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        partial_fill = self._get_order_channel_mock_response(amount="5",
                                                             deal_size="2",
                                                             fill_qty="2",
                                                             last_trade_id=1234)
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        fee = TokenAmount(token=partial_fill["data"][0]["order"]["last_trade"]["feeCcy"],
                          amount=Decimal(partial_fill["data"][0]["order"]["last_trade"]["fee"]))
        self.assertEqual([fee], fill_event.trade_fee.flat_fees)

        complete_fill = self._get_order_channel_mock_response(amount="5",
                                                              state=4,
                                                              deal_size="5",
                                                              fill_qty="3",
                                                              last_trade_id=1235)

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        fee = TokenAmount(token=partial_fill["data"][0]["order"]["last_trade"]["feeCcy"],
                          amount=Decimal(partial_fill["data"][0]["order"]["last_trade"]["fee"]))
        self.assertEqual([fee], fill_event.trade_fee.flat_fees)

        self.assertEqual(1, len(self.sell_order_completed_logger.event_log))

    def test_order_fill_event_ignored_for_repeated_trade_id(self):
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        partial_fill = self._get_order_channel_mock_response(amount="5",
                                                             state=2,
                                                             deal_size="2",
                                                             fill_qty="2",
                                                             last_trade_id=1234)

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        fee = TokenAmount(token=partial_fill["data"][0]["order"]["last_trade"]["feeCcy"],
                          amount=Decimal(partial_fill["data"][0]["order"]["last_trade"]["fee"]))
        self.assertEqual([fee], fill_event.trade_fee.flat_fees)

        repeated_partial_fill = self._get_order_channel_mock_response(amount="5",
                                                                      state=2,
                                                                      deal_size="2",
                                                                      fill_qty="2",
                                                                      last_trade_id=1234)

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: repeated_partial_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

    def test_fee_is_zero_when_not_included_in_fill_event(self):
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        partial_fill = self._get_order_channel_mock_response(deal_size="2", amount="5", fill_qty="2")
        del partial_fill["data"][0]["order"]["last_trade"]["fee"]
        del partial_fill["data"][0]["order"]["last_trade"]["feeCcy"]

        task = self.ev_loop.create_task(self.exchange._process_user_stream_event(event_message=partial_fill))
        self.async_run_with_timeout(task)

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(0, len(fill_event.trade_fee.flat_fees))

    def test_order_event_with_cancelled_status_marks_order_as_cancelled(self):
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = self._get_order_channel_mock_response(amount="5",
                                                             state=4,
                                                             deal_size="2",
                                                             fill_qty="2",
                                                             last_trade_id=1234)

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))

        self.assertTrue(self._is_logged(
            "INFO",
            f"Successfully canceled order {order.client_order_id}."
        ))

    def test_user_stream_event_listener_raises_cancelled_error(self):
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = asyncio.CancelledError

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.test_task)

    @aioresponses()
    @patch("hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative."
           "BitmartPerpetualDerivative.current_timestamp")
    def test_update_order_fills_from_trades_successful(self, req_mock, mock_timestamp):
        self._simulate_trading_rules_initialized()
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1
        price = 10000.0
        amount = 100.0
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal(str(price)),
            amount=Decimal(str(amount)),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        trades = {
            "code": 1000,
            "message": "Ok",
            "data": [
                {
                    "order_id": "8886774",
                    "trade_id": "698759",
                    "symbol": self.symbol,
                    "side": 1,
                    "price": str(price),
                    "vol": str(amount / self.exchange._contract_sizes[self.trading_pair]),
                    "exec_type": "Maker",
                    "profit": False,
                    "realised_profit": "-0.00832",
                    "paid_fees": "0",
                    "create_time": 1663663818589
                }
            ],
            "trace": "638d5048-ad21-4a4b-9365-d0756fbfc7ba"
        }

        url = web_utils.private_rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(trades))

        self.async_run_with_timeout(self.exchange._update_trade_history())

        in_flight_orders = self.exchange._order_tracker.active_orders

        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(price, in_flight_orders["OID1"].price)
        self.assertEqual(amount, in_flight_orders["OID1"].amount)
        self.assertEqual("8886774", in_flight_orders["OID1"].exchange_order_id)
        self.assertEqual(OrderState.PENDING_CREATE, in_flight_orders["OID1"].current_state)
        self.assertEqual(1, in_flight_orders["OID1"].leverage)
        self.assertEqual(PositionAction.OPEN, in_flight_orders["OID1"].position)

        self.assertEqual(amount, in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(Decimal(str(amount * price)), in_flight_orders["OID1"].executed_amount_quote)
        self.assertEqual(1663663818.589, in_flight_orders["OID1"].last_update_timestamp)

        self.assertTrue("698759" in in_flight_orders["OID1"].order_fills.keys())

    @aioresponses()
    def test_update_order_fills_from_trades_failed(self, req_mock):
        self.exchange._set_current_timestamp(1640001112.0)
        self.exchange._last_poll_timestamp = 0
        self._simulate_trading_rules_initialized()
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        url = web_utils.private_rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, exception=Exception())

        self.async_run_with_timeout(self.exchange._update_trade_history())

        in_flight_orders = self.exchange._order_tracker.active_orders

        # Nothing has changed
        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(10000, in_flight_orders["OID1"].price)
        self.assertEqual(1, in_flight_orders["OID1"].amount)
        self.assertEqual("8886774", in_flight_orders["OID1"].exchange_order_id)
        self.assertEqual(OrderState.PENDING_CREATE, in_flight_orders["OID1"].current_state)
        self.assertEqual(1, in_flight_orders["OID1"].leverage)
        self.assertEqual(PositionAction.OPEN, in_flight_orders["OID1"].position)

        self.assertEqual(0, in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(0, in_flight_orders["OID1"].executed_amount_quote)
        self.assertEqual(1640001112.0, in_flight_orders["OID1"].last_update_timestamp)

        # Error was logged
        self.assertTrue(self._is_logged("NETWORK",
                                        f"Error fetching trades update for the order {self.trading_pair}: ."))

    def _get_order_detail_response_mock(self):
        mocked_response = {
            "code": 1000,
            "message": "Ok",
            "data": {
                "order_id": "8886774",
                "client_order_id": "OID1",
                "price": "10000",
                "size": "4",
                "symbol": self.symbol,
                "state": 2,
                "side": 4,
                "type": "limit",
                "leverage": "1",
                "open_type": "isolated",
                "deal_avg_price": "10000",
                "deal_size": "1",
                "create_time": 1662368173000,
                "update_time": 1662368173000
            },
            "trace": "638d5048-ad21-4a4b-9365-d0756fbfc7ba"
        }
        return mocked_response

    @aioresponses()
    @patch("hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative."
           "BitmartPerpetualDerivative.current_timestamp")
    def test_update_order_status_successful(self, req_mock, mock_timestamp):
        self._simulate_trading_rules_initialized()
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("5"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        order = self._get_order_detail_response_mock()

        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_DETAILS, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(order))

        self.async_run_with_timeout(self.exchange._update_order_status())

        in_flight_orders = self.exchange._order_tracker.active_orders

        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(10000, in_flight_orders["OID1"].price)
        self.assertEqual(5, in_flight_orders["OID1"].amount)
        self.assertEqual("8886774", in_flight_orders["OID1"].exchange_order_id)
        self.assertEqual(OrderState.PARTIALLY_FILLED, in_flight_orders["OID1"].current_state)
        self.assertEqual(1, in_flight_orders["OID1"].leverage)
        self.assertEqual(PositionAction.OPEN, in_flight_orders["OID1"].position)

        # Processing an order update should not impact trade fill information
        self.assertEqual(Decimal("0"), in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(Decimal("0"), in_flight_orders["OID1"].executed_amount_quote)

        self.assertEqual(1662368173, in_flight_orders["OID1"].last_update_timestamp)

        self.assertEqual(0, len(in_flight_orders["OID1"].order_fills))

    @aioresponses()
    @patch("hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative."
           "BitmartPerpetualDerivative.current_timestamp")
    def test_request_order_status_successful(self, req_mock, mock_timestamp):
        self._simulate_trading_rules_initialized()
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        tracked_order = self.exchange._order_tracker.fetch_order("OID1")

        order = self._get_order_detail_response_mock()

        url = web_utils.private_rest_url(
            CONSTANTS.ORDER_DETAILS, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(order))

        order_update = self.async_run_with_timeout(self.exchange._request_order_status(tracked_order))

        in_flight_orders = self.exchange._order_tracker.active_orders
        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual(order_update.client_order_id, in_flight_orders["OID1"].client_order_id)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order_update.new_state)
        self.assertEqual(0, len(in_flight_orders["OID1"].order_fills))

    @aioresponses()
    def test_set_position_mode_successful(self, mock_api):
        position_mode = "hedge_mode"
        trading_pair = "any"
        response = self._get_position_mode_mock_response(position_mode)

        url = web_utils.private_rest_url(path_url=CONSTANTS.SET_POSITION_MODE_URL,
                                         domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=json.dumps(response))

        success, msg = self.async_run_with_timeout(
            self.exchange._trading_pair_position_mode_set(mode=PositionMode.HEDGE,
                                                          trading_pair=trading_pair))
        self.assertEqual(success, True)
        self.assertEqual(msg, '')

    @aioresponses()
    def test_set_position_mode_once(self, mock_api):
        position_mode = "hedge_mode"
        trading_pairs = ["BTC-USDT", "ETH-USDT"]

        response = self._get_position_mode_mock_response(position_mode)
        url = web_utils.private_rest_url(path_url=CONSTANTS.SET_POSITION_MODE_URL,
                                         domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=json.dumps(response))

        success, msg = self.async_run_with_timeout(
            self.exchange._trading_pair_position_mode_set(mode=PositionMode.HEDGE,
                                                          trading_pair=trading_pairs[0]))
        self.assertEqual(success, True)
        self.assertEqual(msg, '')

        success, msg = self.async_run_with_timeout(
            self.exchange._trading_pair_position_mode_set(mode=PositionMode.HEDGE,
                                                          trading_pair=trading_pairs[1])
        )
        self.assertEqual(success, True)
        self.assertEqual(msg, "Position Mode already set.")

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        mode = PositionMode.HEDGE
        trading_pair = "any"
        response = {
            "trace": "1e17720eff0f4ff9b15278e1f42685b4.87.17444004177653908",
            "code": 30002,
            "data": {},
            "message": "some error"
        }

        url = web_utils.private_rest_url(path_url=CONSTANTS.SET_POSITION_MODE_URL,
                                         domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=json.dumps(response))

        success, msg = self.async_run_with_timeout(
            self.exchange._trading_pair_position_mode_set(mode=PositionMode.HEDGE,
                                                          trading_pair=trading_pair))
        self.assertEqual(success, False)
        self.assertEqual(msg, 'Unable to set position mode: Code 30002 - some error')
        self._is_logged("network", f"Error switching {trading_pair} mode to {mode}: {msg}")

    @aioresponses()
    def test_set_leverage_successful(self, req_mock):
        self._simulate_trading_rules_initialized()
        leverage = 21

        response = {
            "code": 1000,
            "message": "Ok",
            "data": {
                "symbol": self.symbol,
                "leverage": "21",
                "open_type": "isolated",
                "max_value": "100"
            },
            "trace": "13f7fda9-9543-4e11-a0ba-cbe117989988"
        }

        url = web_utils.private_rest_url(
            CONSTANTS.SET_LEVERAGE_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url, body=json.dumps(response))

        success, msg = self.async_run_with_timeout(self.exchange._set_trading_pair_leverage(self.trading_pair, leverage))
        self.assertEqual(success, True)
        self.assertEqual(msg, '')

    @aioresponses()
    def test_set_leverage_failed(self, req_mock):
        self._simulate_trading_rules_initialized()
        leverage = 21

        response = {
            "code": 40040,
            "message": "Invalid Leverage",
            "trace": "d73d949bbd8645f6a40c8fc7f5ae6738.67.17364673745684111"
        }

        url = web_utils.private_rest_url(
            CONSTANTS.SET_LEVERAGE_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url, body=json.dumps(response))

        success, message = self.async_run_with_timeout(self.exchange._set_trading_pair_leverage(self.trading_pair, leverage))
        self.assertEqual(success, False)
        self.assertEqual(message, 'Unable to set leverage')

    @aioresponses()
    def test_fetch_funding_payment_successful(self, req_mock):
        self._simulate_trading_rules_initialized()
        income_history = self._get_income_history_dict()

        url = web_utils.private_rest_url(
            CONSTANTS.GET_INCOME_HISTORY_URL, domain=self.domain
        )
        regex_url_income_history = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_income_history, body=json.dumps(income_history))

        funding_info = self._get_funding_info_dict()

        url = web_utils.public_rest_url(
            CONSTANTS.FUNDING_INFO_URL, domain=self.domain
        )
        regex_url_funding_info = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_funding_info, body=json.dumps(funding_info))

        # Fetch from exchange with REST API - safe_ensure_future, not immediately
        self.async_run_with_timeout(self.exchange._update_funding_payment(self.trading_pair, True))

        req_mock.get(regex_url_income_history, body=json.dumps(income_history))

        # Fetch once received
        self.async_run_with_timeout(self.exchange._update_funding_payment(self.trading_pair, True))

        self.assertTrue(len(self.funding_payment_completed_logger.event_log) == 1)

        funding_info_logged = self.funding_payment_completed_logger.event_log[0]

        self.assertTrue(funding_info_logged.trading_pair == f"{self.base_asset}-{self.quote_asset}")

        self.assertEqual(funding_info_logged.funding_rate, Decimal(funding_info["data"]["rate_value"]))
        self.assertEqual(funding_info_logged.amount, Decimal(income_history["data"][1]["amount"]))

    @aioresponses()
    def test_fetch_funding_payment_failed(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.GET_INCOME_HISTORY_URL, domain=self.domain
        )
        regex_url_income_history = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_income_history, exception=Exception)

        self.async_run_with_timeout(self.exchange._update_funding_payment(self.trading_pair, False))

        self.assertTrue(self._is_logged(
            "NETWORK",
            f"Unexpected error while fetching last fee payment for {self.trading_pair}.",
        ))

    @aioresponses()
    def test_cancel_all_successful(self, mocked_api):
        url = web_utils.private_rest_url(
            CONSTANTS.CANCEL_ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = self._get_cancel_order_successful_response_mock()
        mocked_api.post(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="8886775",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10101"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)
        self.assertTrue("OID2" in self.exchange._order_tracker._in_flight_orders)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(0, len(order_cancelled_events))
        self.assertEqual(2, len(cancellation_results))

    @aioresponses()
    def test_cancel_all_unknown_order(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.CANCEL_ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = self._get_cancel_order_successful_response_mock()
        cancel_response["code"] = CONSTANTS.UNKNOWN_ORDER_ERROR_CODE
        cancel_response["msg"] = CONSTANTS.UNKNOWN_ORDER_MESSAGE
        req_mock.post(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        tracked_order = self.exchange._order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        self.assertEqual(1, len(cancellation_results))
        self.assertEqual("OID1", cancellation_results[0].order_id)

        self.assertTrue(self._is_logged(
            "DEBUG",
            "The order OID1 does not exist on Bitmart Perpetual. "
            "No cancelation needed."
        ))

        self.assertTrue("OID1" in self.exchange._order_tracker._order_not_found_records)

    @aioresponses()
    def test_cancel_all_exception(self, req_mock):
        url = web_utils.private_rest_url(
            CONSTANTS.CANCEL_ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.delete(regex_url, exception=Exception())

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        tracked_order = self.exchange._order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        self.assertEqual(1, len(cancellation_results))
        self.assertEqual("OID1", cancellation_results[0].order_id)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Failed to cancel order OID1",
        ))

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

    @staticmethod
    def _get_cancel_order_successful_response_mock():
        mocked_response = {
            "code": 1000,
            "trace": "0cc6f4c4-8b8c-4253-8e90-8d3195aa109c",
            "message": "Ok",
            "data": {}
        }
        return mocked_response

    @aioresponses()
    def test_cancel_order_successful(self, mock_api):
        self._simulate_trading_rules_initialized()

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        tracked_order = self.exchange._order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN
        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

        url = web_utils.private_rest_url(
            CONSTANTS.CANCEL_ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = self._get_cancel_order_successful_response_mock()
        mock_api.post(regex_url, body=json.dumps(cancel_response))
        canceled_order_id = self.async_run_with_timeout(self.exchange._execute_cancel(trading_pair=self.trading_pair,
                                                                                      order_id="OID1"))

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual("OID1", canceled_order_id)
        self.assertEqual(1, len(order_cancelled_events))

    @aioresponses()
    def test_cancel_order_failed(self, mock_api):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.CANCEL_ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = self._get_cancel_order_successful_response_mock()
        cancel_response["code"] = 1001
        mock_api.post(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        tracked_order = self.exchange._order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

        self.async_run_with_timeout(self.exchange._execute_cancel(trading_pair=self.trading_pair, order_id="OID1"))

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(0, len(order_cancelled_events))

    @aioresponses()
    def test_create_order_successful(self, req_mock):
        url = web_utils.private_rest_url(
            CONSTANTS.SUBMIT_ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        create_response = self._get_submit_order_mock_response()
        req_mock.post(regex_url, body=json.dumps(create_response))
        self._simulate_trading_rules_initialized()

        self.async_run_with_timeout(self.exchange._create_order(trade_type=TradeType.BUY,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=Decimal("10000"),
                                                                order_type=OrderType.LIMIT,
                                                                position_action=PositionAction.OPEN,
                                                                price=Decimal("10000")))

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

    @staticmethod
    def _get_submit_order_mock_response():
        mocked_response = {
            "code": 1000,
            "message": "Ok",
            "data": {
                "order_id": 123456789,
                "price": "25637.2"
            },
            "trace": "13f7fda9-9543-4e11-a0ba-cbe117989988"
        }
        return mocked_response

    @aioresponses()
    def test_create_limit_maker_successful(self, req_mock):
        self._simulate_trading_rules_initialized()
        url = web_utils.private_rest_url(
            CONSTANTS.SUBMIT_ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        create_response = self._get_submit_order_mock_response()
        req_mock.post(regex_url, body=json.dumps(create_response))

        self.async_run_with_timeout(self.exchange._create_order(trade_type=TradeType.BUY,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=Decimal("10000"),
                                                                order_type=OrderType.LIMIT_MAKER,
                                                                position_action=PositionAction.OPEN,
                                                                price=Decimal("25637.2")))

        self.assertTrue("OID1" in self.exchange._order_tracker._in_flight_orders)

    @aioresponses()
    def test_create_order_exception(self, req_mock):
        url = web_utils.private_rest_url(
            CONSTANTS.SUBMIT_ORDER_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        req_mock.post(regex_url, exception=Exception())
        self._simulate_trading_rules_initialized()
        self.async_run_with_timeout(self.exchange._create_order(trade_type=TradeType.BUY,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=Decimal("10000"),
                                                                order_type=OrderType.LIMIT,
                                                                position_action=PositionAction.OPEN,
                                                                price=Decimal("1010")))

        self.assertTrue("OID1" not in self.exchange._order_tracker._in_flight_orders)

        # The order amount is quantizied
        # "Error submitting buy LIMIT order to Bitmart_perpetual for 9999 COINALPHA-HBOT 1010."
        self.assertTrue(self._is_logged(
            "NETWORK",
            f"Error submitting {TradeType.BUY.name.lower()} {OrderType.LIMIT.name.upper()} order to {self.exchange.name_cap} for "
            f"{Decimal('9999')} {self.trading_pair} {Decimal('1010')}.",
        ))

    def test_create_order_min_order_size_failure(self):
        self._simulate_trading_rules_initialized()
        min_order_size = 3
        mocked_response = self._get_exchange_info_mock_response(contract_size=1, min_volume=min_order_size)
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]
        trade_type = TradeType.BUY
        amount = Decimal("2")

        self.async_run_with_timeout(self.exchange._create_order(trade_type=trade_type,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=amount,
                                                                order_type=OrderType.LIMIT,
                                                                position_action=PositionAction.OPEN,
                                                                price=Decimal("1010")))

        self.assertTrue("OID1" not in self.exchange._order_tracker._in_flight_orders)

        self.assertTrue(self._is_logged(
            "WARNING",
            f"{trade_type.name.title()} order amount {amount} is lower than the minimum order "
            f"size {trading_rules[0].min_order_size}. The order will not be created, increase the "
            f"amount to be higher than the minimum order size."
        ))

    def test_create_order_min_notional_size_failure(self):
        min_notional_size = 10
        self._simulate_trading_rules_initialized()
        mocked_response = self._get_exchange_info_mock_response(contract_size=1,
                                                                min_volume=min_notional_size,
                                                                vol_precision=0.5)
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]
        trade_type = TradeType.BUY
        amount = Decimal("2")
        price = Decimal("4")

        self.async_run_with_timeout(self.exchange._create_order(trade_type=trade_type,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=amount,
                                                                order_type=OrderType.LIMIT,
                                                                position_action=PositionAction.OPEN,
                                                                price=price))

        self.assertTrue("OID1" not in self.exchange._order_tracker._in_flight_orders)

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        ))
        orders.append(InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="EOID2",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.CANCELED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID3",
            exchange_order_id="EOID3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID4",
            exchange_order_id="EOID4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        self.assertNotIn("OID2", self.exchange.in_flight_orders)
        self.assertNotIn("OID3", self.exchange.in_flight_orders)
        self.assertNotIn("OID4", self.exchange.in_flight_orders)

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 4

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action="OPEN",
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.BROKER_ID,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
            position_action="OPEN",
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.BROKER_ID,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = web_utils.private_rest_url(CONSTANTS.ASSETS_DETAIL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "code": 1000,
            "message": "Ok",
            "data": [
                {
                    "currency": "USDT",
                    "position_deposit": "100",
                    "frozen_balance": "100",
                    "available_balance": "100",
                    "equity": "100",
                    "unrealized": "100"
                },
                {
                    "currency": "BTC",
                    "available_balance": "0.1",
                    "frozen_balance": "0",
                    "unrealized": "0",
                    "equity": "0.1",
                    "position_deposit": "0"
                },
                {
                    "currency": "ETH",
                    "available_balance": "3.5",
                    "frozen_balance": "0",
                    "unrealized": "0",
                    "equity": "7",
                    "position_deposit": "0"
                }
            ],
            "trace": "13f7fda9-9543-4e11-a0ba-cbe117989988"
        }

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("100"), available_balances["USDT"])
        self.assertEqual(Decimal("0.1"), available_balances["BTC"])
        self.assertEqual(Decimal("3.5"), available_balances["ETH"])
        self.assertEqual(Decimal("7"), total_balances["ETH"])

    def test_limit_orders(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )
        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position_action=PositionAction.OPEN,
        )

        limit_orders = self.exchange.limit_orders

        self.assertEqual(len(limit_orders), 2)
        self.assertIsInstance(limit_orders, list)
        self.assertIsInstance(limit_orders[0], LimitOrder)

    def _simulate_trading_rules_initialized(self):
        contract_size = 10
        mocked_response = self._get_exchange_info_mock_response(contract_size=contract_size)
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(1)),
                min_price_increment=Decimal(str(2)),
                min_base_amount_increment=Decimal(str(3)),
                min_notional_size=Decimal(str(4)),
            )
        }
        self.exchange._contract_sizes[self.trading_pair] = contract_size
        return self.exchange._trading_rules

    @aioresponses()
    def test_exchange_info_contains_trading_pair_not_initialized_and_ignores_it(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain)
        mocked_response = self._get_exchange_info_mock_response()
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        mock_api.get(url, body=json.dumps(mocked_response))
        last_traded_prices = self.async_run_with_timeout(self.exchange.get_last_traded_prices())
        self.assertEqual(1, len(mocked_response["data"]["symbols"]))
        self.assertEqual(1, len(last_traded_prices))

        unknown_trading_pair_response = self._get_exchange_info_with_unknown_pair_mock_response()
        mock_api.get(url, body=json.dumps(unknown_trading_pair_response))
        last_traded_prices_with_unknown_pair = self.async_run_with_timeout(self.exchange.get_last_traded_prices())
        self.assertEqual(2, len(unknown_trading_pair_response["data"]["symbols"]))
        self.assertEqual(1, len(last_traded_prices_with_unknown_pair))
