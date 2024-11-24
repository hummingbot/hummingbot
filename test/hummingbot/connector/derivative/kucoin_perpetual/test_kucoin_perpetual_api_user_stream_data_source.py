import asyncio
import re
import unittest
from typing import Any, Awaitable, Dict, Optional
from unittest.mock import AsyncMock, patch

import ujson
from aioresponses.core import aioresponses

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.kucoin_perpetual import (
    kucoin_perpetual_constants as CONSTANTS,
    kucoin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_api_user_stream_data_source import (
    KucoinPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_auth import KucoinPerpetualAuth
from hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_derivative import KucoinPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class KucoinPerpetualAPIUserStreamDataSourceUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"
        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()
        client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.emulated_time = 1640001112.223
        self.auth = KucoinPerpetualAuth(
            api_key="TEST_API_KEY",
            passphrase="TEST_PASSPHRASE",
            secret_key="TEST_SECRET",
            time_provider=self)
        self.connector = KucoinPerpetualDerivative(
            client_config_map,
            kucoin_perpetual_api_key="",
            kucoin_perpetual_secret_key="",
            kucoin_perpetual_passphrase="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        self.data_source = KucoinPerpetualAPIUserStreamDataSource(
            trading_pairs=[self.trading_pair], connector=self.connector, auth=self.auth, api_factory=self.connector._web_assistants_factory, domain=self.domain
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mock_done_event = asyncio.Event()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _mock_responses_done_callback(self, *_, **__):
        self.mock_done_event.set()

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _successful_get_server_time(self) -> str:
        resp = {
            "code": "200000",
            "msg": "success",
            "data": 1546837113087,
        }
        return ujson.dumps(resp)

    def _all_symbols_request_mock_response(self):
        mock_response = {
            "code": "200000",
            "data": [
                {
                    "symbol": "COINALPHAHBOT",
                    "rootSymbol": "COINALPHA",
                    "type": "FFWCSX",
                    "firstOpenDate": 1585555200000,
                    "expireDate": None,
                    "settleDate": None,
                    "baseCurrency": "COINALPHA",
                    "quoteCurrency": "HBOT",
                    "settleCurrency": "HBOT",
                    "maxOrderQty": 1000000,
                    "maxPrice": 1000000.0,
                    "lotSize": 1,
                    "tickSize": 1.0,
                    "indexPriceTickSize": 0.01,
                    "multiplier": 0.001,
                    "initialMargin": 0.01,
                    "maintainMargin": 0.005,
                    "maxRiskLimit": 2000000,
                    "minRiskLimit": 2000000,
                    "riskStep": 1000000,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                    "takerFixFee": 0.0,
                    "makerFixFee": 0.0,
                    "settlementFee": None,
                    "isDeleverage": True,
                    "isQuanto": True,
                    "isInverse": False,
                    "markMethod": "FairPrice",
                    "fairMethod": "FundingRate",
                    "settlementSymbol": "",
                    "status": "Open",
                    "fundingFeeRate": 0.0001,
                    "predictedFundingFeeRate": 0.0001,
                    "openInterest": "5191275",
                    "turnoverOf24h": 2361994501.712677,
                    "volumeOf24h": 56067.116,
                    "markPrice": 44514.03,
                    "indexPrice": 44510.78,
                    "lastTradePrice": 44493.0,
                    "nextFundingRateTime": 21031525,
                    "maxLeverage": 100,
                    "sourceExchanges": [
                        "htx",
                        "Okex",
                        "Binance",
                        "Kucoin",
                        "Poloniex",
                    ],
                    "lowPrice": 38040,
                    "highPrice": 44948,
                    "priceChgPct": 0.1702,
                    "priceChg": 6476
                }
            ]
        }
        return ujson.dumps(mock_response)

    def _successful_get_connection_token_response(self) -> str:
        resp = {
            "code": "200000",
            "data": {
                "token": self.listen_key,
                "instanceServers": [
                    {
                        "endpoint": "wss://someEndpoint",
                        "encrypt": True,
                        "protocol": "websocket",
                        "pingInterval": 18000,
                        "pingTimeout": 10000,
                    }
                ]
            }
        }
        return ujson.dumps(resp)

    def _error_response(self) -> Dict[str, Any]:
        resp = {"code": "400100", "msg": "Invalid Parameter."}

        return resp

    def _simulate_user_update_event(self):
        # Order Trade Update
        resp = {
            "type": "message",
            "topic": "/contractMarket/tradeOrders:HBOTALPHAM",
            "subject": "symbolOrderChange",
            "channelType": "private",
            "data": {
                "orderId": "5cdfc138b21023a909e5ad55",  # Order ID
                "symbol": "HBOTALPHAM",  # Symbol
                "type": "match",  # Message Type: "open", "match", "filled", "canceled", "update"
                "status": "open",  # Order Status: "match", "open", "done"
                "matchSize": "",  # Match Size (when the type is "match")
                "matchPrice": "",  # Match Price (when the type is "match")
                "orderType": "limit",  # Order Type, "market" indicates market order, "limit" indicates limit order
                "side": "buy",  # Trading direction,include buy and sell
                "price": "3600",  # Order Price
                "size": "20000",  # Order Size
                "remainSize": "20001",  # Remaining Size for Trading
                "filledSize": "20000",  # Filled Size
                "canceledSize": "0",  # In the update message, the Size of order reduced
                "tradeId": "5ce24c16b210233c36eexxxx",  # Trade ID (when the type is "match")
                "clientOid": "5ce24c16b210233c36ee321d",  # clientOid
                "orderTime": 1545914149935808589,  # Order Time
                "oldSize ": "15000",  # Size Before Update (when the type is "update")
                "liquidity": "maker",  # Trading direction, buy or sell in taker
                "ts": 1545914149935808589  # Timestamp
            }
        }
        return ujson.dumps(resp)

    def time(self):
        # Implemented to emulate a TimeSynchronizer
        return self.emulated_time

    def test_last_recv_time(self):
        # Initial last_recv_time
        self.assertEqual(0, self.data_source.last_recv_time)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_log_exception(self, mock_api, mock_ws):
        url = web_utils.wss_private_url(self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_connection_token_response())

        mock_ws.side_effect = Exception("TEST ERROR.")

        msg_queue = asyncio.Queue()
        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.exceptions.TimeoutError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Unexpected error while listening to user stream {url}. Retrying after 5 seconds...",
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_create_websocket_connection_failed(self, mock_api, mock_ws):
        url = web_utils.wss_private_url(self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_connection_token_response())

        mock_ws.side_effect = Exception("TEST ERROR.")

        msg_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        try:
            self.async_run_with_timeout(msg_queue.get())
        except asyncio.exceptions.TimeoutError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Unexpected error while listening to user stream {url}. Retrying after 5 seconds...",
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_iter_message_throws_exception(self, mock_api, _, mock_ws):
        url = web_utils.wss_private_url(self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"listenKey": self.listen_key}
        mock_api.post(regex_url, body=ujson.dumps(mock_response))

        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        mock_ws.return_value.closed = False
        mock_ws.return_value.close.side_effect = Exception

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        try:
            self.async_run_with_timeout(msg_queue.get())
        except Exception:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Unexpected error while listening to user stream {url}. Retrying after 5 seconds...",
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_successful(self, mock_api, mock_ws):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.PRIVATE_WS_DATA_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_connection_token_response())

        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.SERVER_TIME_PATH_URL)
        mock_api.get(url, body=self._successful_get_server_time())
        mock_api.get(url, body=self._successful_get_server_time())

        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)
        mock_api.get(url, body=self._all_symbols_request_mock_response())
        mock_api.get(url, body=self._all_symbols_request_mock_response())

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._simulate_user_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        msg = self.async_run_with_timeout(msg_queue.get())
        self.assertTrue(msg, self._simulate_user_update_event)
        mock_ws.return_value.ping.assert_called()

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_api, mock_ws):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.PRIVATE_WS_DATA_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_connection_token_response())

        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.SERVER_TIME_PATH_URL)
        mock_api.get(url, body=self._successful_get_server_time())
        mock_api.get(url, body=self._successful_get_server_time())

        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT)
        mock_api.get(url, body=self._all_symbols_request_mock_response())
        mock_api.get(url, body=self._all_symbols_request_mock_response())

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())
