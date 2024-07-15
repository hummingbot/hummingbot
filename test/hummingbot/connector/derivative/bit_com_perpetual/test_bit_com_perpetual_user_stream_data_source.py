import asyncio
import json
import re
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bit_com_perpetual import bit_com_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_auth import BitComPerpetualAuth
from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_derivative import BitComPerpetualDerivative
from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_user_stream_data_source import (
    BitComPerpetualUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class TestBitComPerpetualAPIUserStreamDataSource(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"
        cls.user_id = "someUserId"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = BitComPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret_key)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BitComPerpetualDerivative(
            client_config_map=client_config_map,
            bit_com_perpetual_api_key="",
            bit_com_perpetual_api_secret="",
            trading_pairs=[])
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = BitComPerpetualUserStreamDataSource(
            self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 2):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    async def get_token(self):
        return "be4ffcc9-2b2b-4c3e-9d47-68bf062cf651"

    @aioresponses()
    def test_get_new_token_successful(self, mock_api):
        endpoint = CONSTANTS.USERSTREAM_AUTH_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = {
            "code": 0,
            "message": "",
            "data": {
                "token": "be4ffcc9-2b2b-4c3e-9d47-68bf062cf651"
            }
        }
        mock_api.get(regex_url, body=json.dumps(resp))

        date = self.async_run_with_timeout(
            self.data_source.get_token()
        )

        self.assertEqual("be4ffcc9-2b2b-4c3e-9d47-68bf062cf651", date)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_user_stream_data_source.BitComPerpetualUserStreamDataSource"
        ".get_token")
    def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, token_mock, ws_connect_mock):
        token_mock.return_value = "be4ffcc9-2b2b-4c3e-9d47-68bf062cf651"
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_orders = {
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
                    "instrument_id": "BTC-USD-PERPETUAL",
                    "is_liquidation": False,
                    "is_um": True,
                    "label": "",
                    "maker_fee_rate": "0.00010000",
                    "mmp": False,
                    "order_id": "1034087",
                    "order_type": "limit",
                    "pnl": "0.00000000",
                    "post_only": False,
                    "price": "36088.95000000",
                    "qty": "0.02000000",
                    "reduce_only": False,
                    "reject_post_only": False,
                    "reorder_index": 0,
                    "side": "buy",
                    "source": "web",
                    "status": "pending",
                    "stop_order_id": "",
                    "stop_price": "0.00000000",
                    "taker_fee_rate": "0.00010000",
                    "time_in_force": "gtc",
                    "updated_at": 1643101425539,
                    "user_id": "606122"
                }
            ]
        }
        result_subscribe_trades = {
            "channel": "user_trade",
            "timestamp": 1643101722258,
            "module": "linear",
            "data": [
                {
                    "created_at": 1643101722020,
                    "fee": "0.00000000",
                    "fee_rate": "0.00010000",
                    "index_price": "36214.05400000",
                    "instrument_id": "BTC-USD-PERPETUAL",
                    "is_block_trade": False,
                    "is_taker": True,
                    "label": "",
                    "order_id": "1034149",
                    "order_type": "limit",
                    "price": "36219.85000000",
                    "qty": "0.00100000",
                    "side": "buy",
                    "sigma": "0.00000000",
                    "trade_id": "1005590992",
                    "underlying_price": "",
                    "usd_price": ""
                }
            ]
        }
        result_subscribe_positions = {
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
                    "qty": "-0.03020000",
                    "qty_base": "-0.03020000",
                    "roi": "8.82942378",
                    "session_avg_price": "36055.02649047",
                    "session_funding": "-0.16699671",
                    "liq_price": "3587263.29572346",
                }
            ]
        }

        result_subscribe_balances = {
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
                        "currency": "ETH",
                        "equity": "1.9996000",
                        "liability": "0.00000000",
                        "index_price": "3119.01923077",
                        "cash_balance": "1.99960000",
                        "margin_balance": "1.99960000",
                        "available_balance": "1.99960000",
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
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_positions))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_balances))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_orders_subscription = {
            "type": "subscribe",
            "instruments": [self.ex_trading_pair],
            "channels": [CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
                         CONSTANTS.USER_POSITIONS_ENDPOINT_NAME,
                         CONSTANTS.USER_TRADES_ENDPOINT_NAME,
                         CONSTANTS.USER_BALANCES_ENDPOINT_NAME,
                         ],
            "pairs": [self.trading_pair],
            "categories": ["future"],
            "interval": "raw",
            "token": "be4ffcc9-2b2b-4c3e-9d47-68bf062cf651",
        }
        self.assertEqual(expected_orders_subscription, sent_subscription_messages[0])
        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private order changes channels..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_connection_failed(self, sleep_mock, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch.object(BitComPerpetualUserStreamDataSource, "get_token")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_iter_message_throws_exception(self, sleep_mock, mock_ws, get_token_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        get_token_mock.return_value = "be4ffcc9-2b2b-4c3e-9d47-68bf062cf651"
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
