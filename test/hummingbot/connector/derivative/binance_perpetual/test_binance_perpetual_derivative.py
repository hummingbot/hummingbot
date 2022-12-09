import asyncio
import functools
import json
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, PropertyMock, patch

import pandas as pd
from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source import (
    BinancePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative import BinancePerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent


class BinancePerpetualDerivativeUnitTest(unittest.TestCase):
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
        cls.domain = CONSTANTS.TESTNET_DOMAIN
        cls.listen_key = "TEST_LISTEN_KEY"

        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = BinancePerpetualDerivative(
            client_config_map=self.client_config_map,
            binance_perpetual_api_key="testAPIKey",
            binance_perpetual_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        self.exchange._set_current_timestamp(1640780000)
        self.exchange._binance_time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._client_order_tracker.logger().setLevel(1)
        self.exchange._client_order_tracker.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant()
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()
        BinancePerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.symbol: self.trading_pair})
        }

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        BinancePerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
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
        positions = [
            {
                "symbol": self.symbol,
                "positionAmt": "1",
                "entryPrice": "10",
                "markPrice": "11",
                "unRealizedProfit": "1",
                "liquidationPrice": "100",
                "leverage": "1",
                "maxNotionalValue": "9",
                "marginType": "cross",
                "isolatedMargin": "0",
                "isAutoAddMargin": "false",
                "positionSide": "BOTH",
                "notional": "11",
                "isolatedWallet": "0",
                "updateTime": int(self.start_timestamp),
            }
        ]
        return positions

    def _get_account_update_ws_event_single_position_dict(self) -> Dict[str, Any]:
        account_update = {
            "e": "ACCOUNT_UPDATE",
            "E": 1564745798939,
            "T": 1564745798938,
            "a": {
                "m": "POSITION",
                "B": [
                    {"a": "USDT", "wb": "122624.12345678", "cw": "100.12345678", "bc": "50.12345678"},
                ],
                "P": [
                    {
                        "s": self.symbol,
                        "pa": "1",
                        "ep": "10",
                        "cr": "200",
                        "up": "1",
                        "mt": "cross",
                        "iw": "0.00000000",
                        "ps": "BOTH",
                    },
                ],
            },
        }
        return account_update

    def _get_income_history_dict(self) -> List:
        income_history = [{
            "income": 1,
            "symbol": self.symbol,
            "time": self.start_timestamp,
        }]
        return income_history

    def _get_funding_info_dict(self) -> Dict[str, Any]:
        funding_info = {
            "indexPrice": 1000,
            "markPrice": 1001,
            "nextFundingTime": self.start_timestamp + 8 * 60 * 60,
            "lastFundingRate": 1010
        }
        return funding_info

    def _get_trading_pair_symbol_map(self) -> Dict[str, str]:
        trading_pair_symbol_map = {self.symbol: f"{self.base_asset}-{self.quote_asset}"}
        return trading_pair_symbol_map

    def _get_exchange_info_mock_response(
            self,
            margin_asset: str = "HBOT",
            min_order_size: float = 1,
            min_price_increment: float = 2,
            min_base_amount_increment: float = 3,
            min_notional_size: float = 4,
    ) -> Dict[str, Any]:
        mocked_exchange_info = {  # irrelevant fields removed
            "symbols": [
                {
                    "symbol": self.symbol,
                    "pair": self.symbol,
                    "contractType": "PERPETUAL",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "marginAsset": margin_asset,
                    "status": "TRADING",
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "maxPrice": "300",
                            "minPrice": "0.0001",
                            "tickSize": str(min_price_increment),
                        },
                        {
                            "filterType": "LOT_SIZE",
                            "maxQty": "10000000",
                            "minQty": str(min_order_size),
                            "stepSize": str(min_base_amount_increment),
                        },
                        {
                            "filterType": "MIN_NOTIONAL",
                            "notional": str(min_notional_size),
                        },
                    ],
                }
            ],
        }

        return mocked_exchange_info

    @aioresponses()
    def test_existing_account_position_detected_on_positions_update(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2
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
    def test_account_position_updated_on_positions_update(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 1)

        positions[0]["positionAmt"] = "2"
        req_mock.get(regex_url, body=json.dumps(positions))
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2)

    @aioresponses()
    def test_new_account_position_detected_on_positions_update(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps([]))

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
        url = web_utils.rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        positions = self._get_position_risk_api_endpoint_single_position_list()
        req_mock.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 1)

        positions[0]["positionAmt"] = "0"
        req_mock.get(regex_url, body=json.dumps(positions))
        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        self.assertEqual(len(self.exchange.account_positions), 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_new_account_position_detected_on_stream_event(self, mock_api, ws_connect_mock):
        url = web_utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        listen_key_response = {"listenKey": self.listen_key}
        mock_api.post(regex_url, body=json.dumps(listen_key_response))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 0)

        account_update = self._get_account_update_ws_event_single_position_dict()
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(account_update))

        url = web_utils.rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=json.dumps(positions))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(len(self.exchange.account_positions), 1)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_account_position_updated_on_stream_event(self, mock_api, ws_connect_mock):
        url = web_utils.rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        url = web_utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        listen_key_response = {"listenKey": self.listen_key}
        mock_api.post(regex_url, body=json.dumps(listen_key_response))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 1)

        account_update = self._get_account_update_ws_event_single_position_dict()
        account_update["a"]["P"][0]["pa"] = 2
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(account_update))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(pos.amount, 2)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_closed_account_position_removed_on_stream_event(self, mock_api, ws_connect_mock):
        url = web_utils.rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        url = web_utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        listen_key_response = {"listenKey": self.listen_key}
        mock_api.post(regex_url, body=json.dumps(listen_key_response))
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 1)

        account_update = self._get_account_update_ws_event_single_position_dict()
        account_update["a"]["P"][0]["pa"] = 0
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(account_update))

        self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(len(self.exchange.account_positions), 0)

    @aioresponses()
    def test_set_position_mode_initial_mode_is_none(self, mock_api):
        self.assertIsNone(self.exchange.position_mode)

        url = web_utils.rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
        post_position_mode_response = {"code": 200, "msg": "success"}
        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        mock_api.post(regex_url, body=json.dumps(post_position_mode_response))

        task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.HEDGE))
        self.async_run_with_timeout(task)

        self.assertEqual(PositionMode.HEDGE, self.exchange.position_mode)

    @aioresponses()
    def test_position_key(self, mock_api):
        self.assertIsNone(self.exchange.position_mode)

        # Exchange trading pair map not ready -> keep perpetual convention
        url = web_utils.rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        post_position_mode_response = {"code": 200, "msg": "success"}

        with patch.object(BinancePerpetualAPIOrderBookDataSource, "_trading_pair_symbol_map", new_callable=PropertyMock) as mock_pairs:
            mock_pairs.return_value = {}
            get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
            mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
            mock_api.post(regex_url, body=json.dumps(post_position_mode_response))
            task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.ONEWAY))
            self.async_run_with_timeout(task)

            self.assertEqual("COINALPHAHBOT", self.exchange.position_key("COINALPHAHBOT"))
            self.assertEqual("COINALPHAHBOT", self.exchange.position_key("COINALPHAHBOT", PositionSide.LONG))

            get_position_mode_response = {"dualSidePosition": True}  # True: Hedge Mode; False: One-way Mode
            mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
            mock_api.post(regex_url, body=json.dumps(post_position_mode_response))
            task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.HEDGE))
            self.async_run_with_timeout(task)

            self.assertEqual("COINALPHAHBOT:LONG", self.exchange.position_key("COINALPHAHBOT", PositionSide.LONG), )
            self.assertEqual("COINALPHAHBOT:SHORT", self.exchange.position_key("COINALPHAHBOT", PositionSide.SHORT), )

        # Perpetual pair not in exchange pairs
        with patch.object(BinancePerpetualAPIOrderBookDataSource, "_trading_pair_symbol_map", new_callable=PropertyMock) as mock_pairs:
            mock_pairs.return_value = {self.domain: bidict({"symbol": "trading-pair"})}
            get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
            mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
            mock_api.post(regex_url, body=json.dumps(post_position_mode_response))
            task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.ONEWAY))
            self.async_run_with_timeout(task)

            self.assertEqual("COINALPHAHBOT", self.exchange.position_key("COINALPHAHBOT"))
            self.assertEqual("COINALPHAHBOT", self.exchange.position_key("COINALPHAHBOT", PositionSide.LONG))

            get_position_mode_response = {"dualSidePosition": True}  # True: Hedge Mode; False: One-way Mode
            mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
            task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.HEDGE))
            self.async_run_with_timeout(task)

            self.assertEqual("COINALPHAHBOT:LONG", self.exchange.position_key("COINALPHAHBOT", PositionSide.LONG), )
            self.assertEqual("COINALPHAHBOT:SHORT", self.exchange.position_key("COINALPHAHBOT", PositionSide.SHORT), )

        # Perpetual orderbook trading pair map is ready
        with patch.object(BinancePerpetualAPIOrderBookDataSource, "_trading_pair_symbol_map", new_callable=PropertyMock) as mock_pairs:
            mock_pairs.return_value = {self.domain: bidict({self.symbol: self.trading_pair})}
            get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
            mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
            mock_api.post(regex_url, body=json.dumps(post_position_mode_response))
            task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.ONEWAY))
            self.async_run_with_timeout(task)

            self.assertEqual("COINALPHA-HBOT", self.exchange.position_key("COINALPHAHBOT"))
            self.assertEqual("COINALPHA-HBOT", self.exchange.position_key("COINALPHAHBOT", PositionSide.LONG))

            get_position_mode_response = {"dualSidePosition": True}  # True: Hedge Mode; False: One-way Mode
            mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
            mock_api.post(regex_url, body=json.dumps(post_position_mode_response))
            task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.HEDGE))
            self.async_run_with_timeout(task)
            self.assertEqual("COINALPHA-HBOT:LONG", self.exchange.position_key("COINALPHAHBOT", PositionSide.LONG), )
            self.assertEqual("COINALPHA-HBOT:SHORT", self.exchange.position_key("COINALPHAHBOT", PositionSide.SHORT), )

    @aioresponses()
    def test_set_position_initial_mode_unchanged(self, mock_api):
        self.exchange._position_mode = PositionMode.ONEWAY
        url = web_utils.rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode

        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.ONEWAY))
        self.async_run_with_timeout(task)

        self.assertEqual(PositionMode.ONEWAY, self.exchange.position_mode)

    @aioresponses()
    def test_set_position_mode_diff_initial_mode_change_successful(self, mock_api):
        self.exchange._position_mode = PositionMode.ONEWAY
        url = web_utils.rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
        post_position_mode_response = {"code": 200, "msg": "success"}

        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        mock_api.post(regex_url, body=json.dumps(post_position_mode_response))

        task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.HEDGE))
        self.async_run_with_timeout(task)

        self.assertEqual(PositionMode.HEDGE, self.exchange.position_mode)

    @aioresponses()
    def test_set_position_mode_diff_initial_mode_change_fail(self, mock_api):
        self.exchange._position_mode = PositionMode.ONEWAY
        url = web_utils.rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
        post_position_mode_response = {"code": -4059, "msg": "No need to change position side."}

        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        mock_api.post(regex_url, body=json.dumps(post_position_mode_response))

        task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.HEDGE))
        self.async_run_with_timeout(task)

        self.assertEqual(PositionMode.ONEWAY, self.exchange.position_mode)

    def test_format_trading_rules(self):
        margin_asset = self.quote_asset
        min_order_size = 1
        min_price_increment = 2
        min_base_amount_increment = 3
        min_notional_size = 4
        mocked_response = self._get_exchange_info_mock_response(
            margin_asset, min_order_size, min_price_increment, min_base_amount_increment, min_notional_size
        )

        trading_rules = self.exchange._format_trading_rules(mocked_response)

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[0]

        self.assertEqual(min_order_size, trading_rule.min_order_size)
        self.assertEqual(min_price_increment, trading_rule.min_price_increment)
        self.assertEqual(min_base_amount_increment, trading_rule.min_base_amount_increment)
        self.assertEqual(min_notional_size, trading_rule.min_notional_size)
        self.assertEqual(margin_asset, trading_rule.buy_order_collateral_token)
        self.assertEqual(margin_asset, trading_rule.sell_order_collateral_token)

    def test_get_collateral_token(self):
        margin_asset = self.quote_asset
        mocked_response = self._get_exchange_info_mock_response(margin_asset)
        trading_rules = self.exchange._format_trading_rules(mocked_response)
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]

        self.assertEqual(margin_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(margin_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    def test_buy_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": "HBOT",
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["o"]["N"], Decimal(partial_fill["o"]["n"]))], fill_event.trade_fee.flat_fees
        )

        complete_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "FILLED",
                "i": 8886774,
                "l": "0.9",
                "z": "1",
                "L": "10000",
                "N": "HBOT",
                "n": "30",
                "T": 1568879465651,
                "t": 2,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill["o"]["N"], Decimal(complete_fill["o"]["n"]))],
                         fill_event.trade_fee.flat_fees)

        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

    def test_sell_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "SELL",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["o"]["N"], Decimal(partial_fill["o"]["n"]))], fill_event.trade_fee.flat_fees
        )

        complete_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "SELL",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "FILLED",
                "i": 8886774,
                "l": "0.9",
                "z": "1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "30",
                "T": 1568879465651,
                "t": 2,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill["o"]["N"], Decimal(complete_fill["o"]["n"]))],
                         fill_event.trade_fee.flat_fees)

        self.assertEqual(1, len(self.sell_order_completed_logger.event_log))

    def test_order_fill_event_ignored_for_repeated_trade_id(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill["o"]["N"], Decimal(partial_fill["o"]["n"]))], fill_event.trade_fee.flat_fees
        )

        repeated_partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }
        }

        self.resume_test_event = asyncio.Event()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: repeated_partial_fill)

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

    def test_fee_is_zero_when_not_included_in_fill_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                # "N": "USDT", //Do not include fee asset
                # "n": "20", //Do not include fee amount
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

        task = self.ev_loop.create_task(self.exchange._process_user_stream_event(event_message=partial_fill))
        self.async_run_with_timeout(task)

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(0, len(fill_event.trade_fee.flat_fees))

    def test_order_event_with_cancelled_status_marks_order_as_cancelled(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": self.trading_pair,
                "c": order.client_order_id,
                "S": "BUY",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "1",
                "p": "10000",
                "ap": "0",
                "sp": "7103.04",
                "x": "TRADE",
                "X": "CANCELED",
                "i": 8886774,
                "l": "0.1",
                "z": "0.1",
                "L": "10000",
                "N": self.quote_asset,
                "n": "20",
                "T": 1568879465651,
                "t": 1,
                "b": "0",
                "a": "9.91",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "7476.89",
                "cr": "5.0",
                "rp": "0"
            }

        }

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

    def test_margin_call_event(self):

        margin_call = {
            "e": "MARGIN_CALL",
            "E": 1587727187525,
            "cw": "3.16812045",
            "p": [
                {
                    "s": "ETHUSDT",
                    "ps": "LONG",
                    "pa": "1.327",
                    "mt": "CROSSED",
                    "iw": "0",
                    "mp": "187.17127",
                    "up": "-1.166074",
                    "mm": "1.614445"
                }
            ]
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: margin_call)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(self._is_logged(
            "WARNING",
            "Margin Call: Your position risk is too high, and you are at risk of liquidation. "
            "Close your positions or add additional margin to your wallet."
        ))
        self.assertTrue(self._is_logged(
            "INFO",
            "Margin Required: 1.614445. Negative PnL assets: ETHUSDT: -1.166074, ."
        ))

    @aioresponses()
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative."
           "BinancePerpetualDerivative.current_timestamp")
    def test_update_order_fills_from_trades_successful(self, req_mock, mock_timestamp):
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        trades = [{"buyer": False,
                   "commission": "0",
                   "commissionAsset": self.quote_asset,
                   "id": 698759,
                   "maker": False,
                   "orderId": "8886774",
                   "price": "10000",
                   "qty": "0.5",
                   "quoteQty": "5000",
                   "realizedPnl": "0",
                   "side": "SELL",
                   "positionSide": "SHORT",
                   "symbol": "COINALPHAHBOT",
                   "time": 1000}]

        url = web_utils.rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(trades))

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        in_flight_orders = self.exchange._client_order_tracker.active_orders

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

        self.assertEqual(0.5, in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(5000, in_flight_orders["OID1"].executed_amount_quote)
        self.assertEqual(1, in_flight_orders["OID1"].last_update_timestamp)

        self.assertTrue("698759" in in_flight_orders["OID1"].order_fills.keys())

    @aioresponses()
    def test_update_order_fills_from_trades_failed(self, req_mock):
        self.exchange._set_current_timestamp(1640001112.0)
        self.exchange._last_poll_timestamp = 0

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        url = web_utils.rest_url(
            CONSTANTS.ACCOUNT_TRADE_LIST_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, exception=Exception())

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        in_flight_orders = self.exchange._client_order_tracker.active_orders

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

    @aioresponses()
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative."
           "BinancePerpetualDerivative.current_timestamp")
    def test_update_order_status_successful(self, req_mock, mock_timestamp):
        self.exchange._last_poll_timestamp = 0
        mock_timestamp.return_value = 1

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        order = {"avgPrice": "0.00000",
                 "clientOrderId": "OID1",
                 "cumQuote": "5000",
                 "executedQty": "0.5",
                 "orderId": 8886774,
                 "origQty": "1",
                 "origType": "LIMIT",
                 "price": "10000",
                 "reduceOnly": False,
                 "side": "SELL",
                 "positionSide": "LONG",
                 "status": "PARTIALLY_FILLED",
                 "closePosition": False,
                 "symbol": f"{self.base_asset}{self.quote_asset}",
                 "time": 1000,
                 "timeInForce": "GTC",
                 "type": "LIMIT",
                 "priceRate": "0.3",
                 "updateTime": 2000,
                 "workingType": "CONTRACT_PRICE",
                 "priceProtect": False}

        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url, body=json.dumps(order))

        self.async_run_with_timeout(self.exchange._update_order_status())

        in_flight_orders = self.exchange._client_order_tracker.active_orders

        self.assertTrue("OID1" in in_flight_orders)

        self.assertEqual("OID1", in_flight_orders["OID1"].client_order_id)
        self.assertEqual(f"{self.base_asset}-{self.quote_asset}", in_flight_orders["OID1"].trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_orders["OID1"].order_type)
        self.assertEqual(TradeType.SELL, in_flight_orders["OID1"].trade_type)
        self.assertEqual(10000, in_flight_orders["OID1"].price)
        self.assertEqual(1, in_flight_orders["OID1"].amount)
        self.assertEqual("8886774", in_flight_orders["OID1"].exchange_order_id)
        self.assertEqual(OrderState.PARTIALLY_FILLED, in_flight_orders["OID1"].current_state)
        self.assertEqual(1, in_flight_orders["OID1"].leverage)
        self.assertEqual(PositionAction.OPEN, in_flight_orders["OID1"].position)

        # Processing an order update should not impact trade fill information
        self.assertEqual(Decimal("0"), in_flight_orders["OID1"].executed_amount_base)
        self.assertEqual(Decimal("0"), in_flight_orders["OID1"].executed_amount_quote)

        self.assertEqual(2, in_flight_orders["OID1"].last_update_timestamp)

        self.assertEqual(0, len(in_flight_orders["OID1"].order_fills))

    @aioresponses()
    def test_set_leverage_successful(self, req_mock):
        trading_pair = f"{self.base_asset}-{self.quote_asset}"
        symbol = f"{self.base_asset}{self.quote_asset}"
        leverage = 21

        response = {
            "leverage": leverage,
            "maxNotionalValue": "1000000",
            "symbol": symbol
        }

        url = web_utils.rest_url(
            CONSTANTS.SET_LEVERAGE_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._set_leverage(trading_pair, leverage))

        self.assertTrue(self._is_logged("INFO",
                                        f"Leverage Successfully set to {leverage} for {trading_pair}."))

    @aioresponses()
    def test_set_leverage_failed(self, req_mock):
        trading_pair = f"{self.base_asset}-{self.quote_asset}"
        symbol = f"{self.base_asset}{self.quote_asset}"
        leverage = 21

        response = {"leverage": 0,
                    "maxNotionalValue": "1000000",
                    "symbol": symbol}

        url = web_utils.rest_url(
            CONSTANTS.SET_LEVERAGE_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._set_leverage(trading_pair, leverage))

        self.assertTrue(self._is_logged("ERROR",
                                        "Unable to set leverage."))

    @aioresponses()
    def test_fetch_funding_payment_successful(self, req_mock):
        income_history = self._get_income_history_dict()

        url = web_utils.rest_url(
            CONSTANTS.GET_INCOME_HISTORY_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url_income_history = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_income_history, body=json.dumps(income_history))

        funding_info = self._get_funding_info_dict()

        url = web_utils.rest_url(
            CONSTANTS.MARK_PRICE_URL, domain=self.domain
        )
        regex_url_funding_info = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_funding_info, body=json.dumps(funding_info))

        # Fetch from exchange with REST API - safe_ensure_future, not immediately
        self.async_run_with_timeout(self.exchange._fetch_funding_payment(self.trading_pair))

        req_mock.get(regex_url_income_history, body=json.dumps(income_history))

        # Fetch once received
        self.async_run_with_timeout(self.exchange._fetch_funding_payment(self.trading_pair))

        self.assertTrue(len(self.funding_payment_completed_logger.event_log) == 1)

        funding_info_logged = self.funding_payment_completed_logger.event_log[0]

        self.assertTrue(funding_info_logged.trading_pair == f"{self.base_asset}-{self.quote_asset}")

        self.assertEqual(funding_info_logged.funding_rate, funding_info["lastFundingRate"])
        self.assertEqual(funding_info_logged.amount, income_history[0]["income"])

    @aioresponses()
    def test_fetch_funding_payment_failed(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.GET_INCOME_HISTORY_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url_income_history = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.get(regex_url_income_history, exception=Exception)

        self.async_run_with_timeout(self.exchange._fetch_funding_payment(self.trading_pair))

        self.assertTrue(self._is_logged(
            "ERROR",
            f"Unexpected error occurred fetching funding payment for {self.trading_pair}. Error: "
        ))

    @aioresponses()
    def test_cancel_all_successful(self, mocked_api):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {"code": 200, "msg": "success"}
        mocked_api.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="8886775",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10101"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)
        self.assertTrue("OID2" in self.exchange._client_order_tracker._in_flight_orders)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(0, len(order_cancelled_events))
        self.assertEqual(2, len(cancellation_results))
        self.assertEqual("OID1", cancellation_results[0].order_id)
        self.assertEqual("OID2", cancellation_results[1].order_id)

    @aioresponses()
    def test_cancel_all_unknown_order(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {"code": -2011, "msg": "Unknown order sent."}
        req_mock.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        tracked_order = self.exchange._client_order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        self.assertEqual(1, len(cancellation_results))
        self.assertEqual("OID1", cancellation_results[0].order_id)

        self.assertTrue(self._is_logged(
            "DEBUG",
            "The order OID1 does not exist on Binance Perpetuals. "
            "No cancelation needed."
        ))

        self.assertTrue("OID1" in self.exchange._client_order_tracker._order_not_found_records)

    @aioresponses()
    def test_cancel_all_exception(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.delete(regex_url, exception=Exception())

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        tracked_order = self.exchange._client_order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        self.assertEqual(1, len(cancellation_results))
        self.assertEqual("OID1", cancellation_results[0].order_id)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Could not cancel order OID1 on Binance Perp. "
        ))

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)

    @aioresponses()
    def test_cancel_order_successful(self, mock_api):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        cancel_response = {
            "clientOrderId": "ODI1",
            "cumQty": "0",
            "cumQuote": "0",
            "executedQty": "0",
            "orderId": 283194212,
            "origQty": "11",
            "origType": "TRAILING_STOP_MARKET",
            "price": "0",
            "reduceOnly": False,
            "side": "BUY",
            "positionSide": "SHORT",
            "status": "CANCELED",
            "stopPrice": "9300",
            "closePosition": False,
            "symbol": "BTCUSDT",
            "timeInForce": "GTC",
            "type": "TRAILING_STOP_MARKET",
            "activatePrice": "9020",
            "priceRate": "0.3",
            "updateTime": 1571110484038,
            "workingType": "CONTRACT_PRICE",
            "priceProtect": False
        }
        mock_api.delete(regex_url, body=json.dumps(cancel_response))

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )
        tracked_order = self.exchange._client_order_tracker.fetch_order("OID1")
        tracked_order.current_state = OrderState.OPEN

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)

        canceled_order_id = self.async_run_with_timeout(self.exchange._execute_cancel(trading_pair=self.trading_pair,
                                                                                      client_order_id="OID1"))

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(1, len(order_cancelled_events))
        self.assertEqual("OID1", canceled_order_id)

    @aioresponses()
    def test_create_order_successful(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        create_response = {"updateTime": int(self.start_timestamp),
                           "status": "NEW",
                           "orderId": "8886774"}
        req_mock.post(regex_url, body=json.dumps(create_response))

        margin_asset = self.quote_asset
        mocked_response = self._get_exchange_info_mock_response(margin_asset)
        trading_rules = self.exchange._format_trading_rules(mocked_response)
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]

        self.async_run_with_timeout(self.exchange._create_order(trade_type=TradeType.BUY,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=Decimal("10000"),
                                                                order_type=OrderType.LIMIT,
                                                                position_action=PositionAction.OPEN,
                                                                price=Decimal("10000")))

        self.assertTrue("OID1" in self.exchange._client_order_tracker._in_flight_orders)

    @aioresponses()
    def test_create_order_exception(self, req_mock):
        url = web_utils.rest_url(
            CONSTANTS.ORDER_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        req_mock.post(regex_url, exception=Exception())

        margin_asset = self.quote_asset
        mocked_response = self._get_exchange_info_mock_response(margin_asset)
        trading_rules = self.exchange._format_trading_rules(mocked_response)
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]

        self.async_run_with_timeout(self.exchange._create_order(trade_type=TradeType.BUY,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=Decimal("10000"),
                                                                order_type=OrderType.LIMIT,
                                                                position_action=PositionAction.OPEN,
                                                                price=Decimal("1010")))

        self.assertTrue("OID1" not in self.exchange._client_order_tracker._in_flight_orders)

        # The order amount is quantizied
        self.assertTrue(self._is_logged(
            "NETWORK",
            f"Error submitting order to Binance Perpetuals for 9999 {self.trading_pair} "
            f"1010."
        ))

    def test_create_order_position_action_failure(self):
        margin_asset = self.quote_asset
        mocked_response = self._get_exchange_info_mock_response(margin_asset)
        trading_rules = self.exchange._format_trading_rules(mocked_response)
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]
        self.async_run_with_timeout(self.exchange._create_order(trade_type=TradeType.BUY,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=Decimal("10000"),
                                                                order_type=OrderType.LIMIT,
                                                                position_action="BAD POSITION ACTION",
                                                                price=Decimal("1010")))

        self.assertTrue("OID1" not in self.exchange._client_order_tracker._in_flight_orders)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Specify either OPEN_POSITION or CLOSE_POSITION position_action."
        ))

    def test_create_order_supported_order_type_failure(self):
        margin_asset = self.quote_asset
        mocked_response = self._get_exchange_info_mock_response(margin_asset)
        trading_rules = self.exchange._format_trading_rules(mocked_response)
        self.exchange._trading_rules[self.trading_pair] = trading_rules[0]
        self.async_run_with_timeout(self.exchange._create_order(trade_type=TradeType.BUY,
                                                                order_id="OID1",
                                                                trading_pair=self.trading_pair,
                                                                amount=Decimal("10000"),
                                                                order_type="STOP LIMIT",
                                                                position_action=PositionAction.OPEN,
                                                                price=Decimal("1010")))

        self.assertTrue("OID1" not in self.exchange._client_order_tracker._in_flight_orders)

        self.assertTrue(self._is_logged(
            "ERROR",
            "STOP LIMIT is not in the list of supported order types"
        ))

    def test_create_order_min_order_size_failure(self):
        margin_asset = self.quote_asset
        min_order_size = 3
        mocked_response = self._get_exchange_info_mock_response(margin_asset, min_order_size=min_order_size)
        trading_rules = self.exchange._format_trading_rules(mocked_response)
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

        self.assertTrue("OID1" not in self.exchange._client_order_tracker._in_flight_orders)

        self.assertTrue(self._is_logged(
            "WARNING",
            f"{trade_type.name.title()} order amount 0 is lower than the minimum order"
            f" size {min_order_size}. The order will not be created."
        ))

    def test_create_order_min_notional_size_failure(self):
        margin_asset = self.quote_asset
        min_notional_size = 10
        mocked_response = self._get_exchange_info_mock_response(margin_asset,
                                                                min_notional_size=min_notional_size,
                                                                min_base_amount_increment=0.5)
        trading_rules = self.exchange._format_trading_rules(mocked_response)
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

        self.assertTrue("OID1" not in self.exchange._client_order_tracker._in_flight_orders)

        self.assertTrue(self._is_logged(
            "WARNING",
            "Buy order notional 8.0 is lower than the "
            "minimum notional size 10. "
            "The order will not be created."
        ))

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
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"serverTime": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response))

        url = web_utils.rest_url(CONSTANTS.ACCOUNT_INFO_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "feeTier": 0,
            "canTrade": True,
            "canDeposit": True,
            "canWithdraw": True,
            "updateTime": 0,
            "totalInitialMargin": "0.00000000",
            "totalMaintMargin": "0.00000000",
            "totalWalletBalance": "23.72469206",
            "totalUnrealizedProfit": "0.00000000",
            "totalMarginBalance": "23.72469206",
            "totalPositionInitialMargin": "0.00000000",
            "totalOpenOrderInitialMargin": "0.00000000",
            "totalCrossWalletBalance": "23.72469206",
            "totalCrossUnPnl": "0.00000000",
            "availableBalance": "23.72469206",
            "maxWithdrawAmount": "23.72469206",
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": "23.72469206",
                    "unrealizedProfit": "0.00000000",
                    "marginBalance": "23.72469206",
                    "maintMargin": "0.00000000",
                    "initialMargin": "0.00000000",
                    "positionInitialMargin": "0.00000000",
                    "openOrderInitialMargin": "0.00000000",
                    "crossWalletBalance": "23.72469206",
                    "crossUnPnl": "0.00000000",
                    "availableBalance": "23.72469206",
                    "maxWithdrawAmount": "23.72469206",
                    "marginAvailable": True,
                    "updateTime": 1625474304765,
                },
                {
                    "asset": "BUSD",
                    "walletBalance": "103.12345678",
                    "unrealizedProfit": "0.00000000",
                    "marginBalance": "103.12345678",
                    "maintMargin": "0.00000000",
                    "initialMargin": "0.00000000",
                    "positionInitialMargin": "0.00000000",
                    "openOrderInitialMargin": "0.00000000",
                    "crossWalletBalance": "103.12345678",
                    "crossUnPnl": "0.00000000",
                    "availableBalance": "100.12345678",
                    "maxWithdrawAmount": "103.12345678",
                    "marginAvailable": True,
                    "updateTime": 1625474304765,
                }
            ],
            "positions": [{
                "symbol": "BTCUSDT",
                "initialMargin": "0",
                "maintMargin": "0",
                "unrealizedProfit": "0.00000000",
                "positionInitialMargin": "0",
                "openOrderInitialMargin": "0",
                "leverage": "100",
                "isolated": True,
                "entryPrice": "0.00000",
                "maxNotional": "250000",
                "bidNotional": "0",
                "askNotional": "0",
                "positionSide": "BOTH",
                "positionAmt": "0",
                "updateTime": 0,
            }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("23.72469206"), available_balances["USDT"])
        self.assertEqual(Decimal("100.12345678"), available_balances["BUSD"])
        self.assertEqual(Decimal("23.72469206"), total_balances["USDT"])
        self.assertEqual(Decimal("103.12345678"), total_balances["BUSD"])

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_account_info_request_includes_timestamp(self, mock_api, mock_seconds_counter):
        mock_seconds_counter.return_value = 1000

        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"serverTime": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response))

        url = web_utils.rest_url(CONSTANTS.ACCOUNT_INFO_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "feeTier": 0,
            "canTrade": True,
            "canDeposit": True,
            "canWithdraw": True,
            "updateTime": 0,
            "totalInitialMargin": "0.00000000",
            "totalMaintMargin": "0.00000000",
            "totalWalletBalance": "23.72469206",
            "totalUnrealizedProfit": "0.00000000",
            "totalMarginBalance": "23.72469206",
            "totalPositionInitialMargin": "0.00000000",
            "totalOpenOrderInitialMargin": "0.00000000",
            "totalCrossWalletBalance": "23.72469206",
            "totalCrossUnPnl": "0.00000000",
            "availableBalance": "23.72469206",
            "maxWithdrawAmount": "23.72469206",
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": "23.72469206",
                    "unrealizedProfit": "0.00000000",
                    "marginBalance": "23.72469206",
                    "maintMargin": "0.00000000",
                    "initialMargin": "0.00000000",
                    "positionInitialMargin": "0.00000000",
                    "openOrderInitialMargin": "0.00000000",
                    "crossWalletBalance": "23.72469206",
                    "crossUnPnl": "0.00000000",
                    "availableBalance": "23.72469206",
                    "maxWithdrawAmount": "23.72469206",
                    "marginAvailable": True,
                    "updateTime": 1625474304765,
                },
                {
                    "asset": "BUSD",
                    "walletBalance": "103.12345678",
                    "unrealizedProfit": "0.00000000",
                    "marginBalance": "103.12345678",
                    "maintMargin": "0.00000000",
                    "initialMargin": "0.00000000",
                    "positionInitialMargin": "0.00000000",
                    "openOrderInitialMargin": "0.00000000",
                    "crossWalletBalance": "103.12345678",
                    "crossUnPnl": "0.00000000",
                    "availableBalance": "100.12345678",
                    "maxWithdrawAmount": "103.12345678",
                    "marginAvailable": True,
                    "updateTime": 1625474304765,
                }
            ],
            "positions": [{
                "symbol": "BTCUSDT",
                "initialMargin": "0",
                "maintMargin": "0",
                "unrealizedProfit": "0.00000000",
                "positionInitialMargin": "0",
                "openOrderInitialMargin": "0",
                "leverage": "100",
                "isolated": True,
                "entryPrice": "0.00000",
                "maxNotional": "250000",
                "bidNotional": "0",
                "askNotional": "0",
                "positionSide": "BOTH",
                "positionAmt": "0",
                "updateTime": 0,
            }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        account_request = next(((key, value) for key, value in mock_api.requests.items()
                                if key[1].human_repr().startswith(url)))
        request_params = account_request[1][0].kwargs["params"]
        self.assertEqual(int(mock_seconds_counter.return_value * 1e3), request_params["timestamp"])

    def test_limit_orders(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )
        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="8886774",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            leverage=1,
            position=PositionAction.OPEN,
        )

        limit_orders = self.exchange.limit_orders

        self.assertEqual(len(limit_orders), 2)
        self.assertTrue(type(limit_orders) == list)
        self.assertTrue(type(limit_orders[0]) == LimitOrder)
