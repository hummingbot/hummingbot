import asyncio
import json
import pandas as pd
import re
import unittest

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS
import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils as utils

from aioresponses.core import aioresponses
from typing import Any, Awaitable, List, Dict, Optional
from unittest.mock import patch, AsyncMock

from hummingbot.core.event.events import PositionMode
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative import BinancePerpetualDerivative
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


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

    @patch("hummingbot.connector.exchange.binance.binance_time.BinanceTime.start")
    def setUp(self, _) -> None:
        super().setUp()

        self.log_records = []

        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.resume_test_event = asyncio.Event()

        self.exchange = BinancePerpetualDerivative(
            binance_perpetual_api_key="testAPIKey",
            binance_perpetual_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant()
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        super().tearDown()

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
        url = utils.rest_url(
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
        url = utils.rest_url(
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
        url = utils.rest_url(
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
        url = utils.rest_url(
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
        url = utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        listen_key_response = {"listenKey": self.listen_key}
        mock_api.post(regex_url, body=json.dumps(listen_key_response))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.ev_loop.create_task(self.exchange._user_stream_tracker.start())

        self.assertEqual(len(self.exchange.account_positions), 0)

        account_update = self._get_account_update_ws_event_single_position_dict()
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(account_update))

        url = utils.rest_url(
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
        url = utils.rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        url = utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
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
        url = utils.rest_url(
            CONSTANTS.POSITION_INFORMATION_URL, domain=self.domain, api_version=CONSTANTS.API_VERSION_V2
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        positions = self._get_position_risk_api_endpoint_single_position_list()
        mock_api.get(regex_url, body=json.dumps(positions))

        task = self.ev_loop.create_task(self.exchange._update_positions())
        self.async_run_with_timeout(task)

        url = utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
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

        url = utils.rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
        post_position_mode_response = {"code": 200, "msg": "success"}
        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        mock_api.post(regex_url, body=json.dumps(post_position_mode_response))

        task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.HEDGE))
        self.async_run_with_timeout(task)

        self.assertEqual(PositionMode.HEDGE, self.exchange.position_mode)

    @aioresponses()
    def test_set_position_initial_mode_unchanged(self, mock_api):
        self.exchange._position_mode = PositionMode.ONEWAY
        url = utils.rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode

        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.ONEWAY))
        self.async_run_with_timeout(task)

        self.assertEqual(PositionMode.ONEWAY, self.exchange.position_mode)

    @aioresponses()
    def test_set_position_mode_diff_initial_mode_change_successful(self, mock_api):
        self.exchange._position_mode = PositionMode.ONEWAY
        url = utils.rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
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
        url = utils.rest_url(CONSTANTS.CHANGE_POSITION_MODE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        get_position_mode_response = {"dualSidePosition": False}  # True: Hedge Mode; False: One-way Mode
        post_position_mode_response = {"code": -4059, "msg": "No need to change position side."}

        mock_api.get(regex_url, body=json.dumps(get_position_mode_response))
        mock_api.post(regex_url, body=json.dumps(post_position_mode_response))

        task = self.ev_loop.create_task(self.exchange._set_position_mode(PositionMode.HEDGE))
        self.async_run_with_timeout(task)

        self.assertEqual(PositionMode.ONEWAY, self.exchange.position_mode)

    @patch("aiohttp.ClientSession.ws_connect")
    def test_funding_info_polling_loop_cancelled_when_connecting(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._funding_info_polling_loop())

    @patch("aiohttp.ClientSession.ws_connect")
    def test_funding_info_polling_loop_cancelled_when_listening(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        ws_connect_mock.return_value.receive_json.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._funding_info_polling_loop())

    @patch("aiohttp.ClientSession.ws_connect")
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative.BinancePerpetualDerivative._sleep")
    def test_funding_info_polling_loop_log_exception(self, mock_sleep, ws_connect_mock):
        mock_sleep.side_effect = lambda: (
            # Allows _funding_info_polling_loop task to yield control over thread
            self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        )
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        ws_connect_mock.return_value.receive_json.side_effect = lambda: (
            self._create_exception_and_unlock_test_with_event(Exception("TEST ERROR"))
        )

        self.test_task = self.ev_loop.create_task(self.exchange._funding_info_polling_loop())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error updating funding info. Retrying after 10 seconds... "))

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
