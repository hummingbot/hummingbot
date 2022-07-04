import asyncio
import unittest
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, patch

import ujson
from aioresponses.core import aioresponses

from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_api_user_stream_data_source import (
    FtxPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_auth import FtxPerpetualAuth

FTX_API_ENDPOINT = "wss://ftx.com/ws/"
FTX_USER_STREAM_ENDPOINT = "userDataStream"


class FtxPerpetualUserStreamDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"
        cls.subaccount_name = "TEST_SUBACCOUNT"

        cls.auth = FtxPerpetualAuth(
            api_key=cls.api_key,
            secret_key=cls.secret_key,
            subaccount_name=cls.subaccount_name
        )

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.async_task: Optional[asyncio.Task] = None

        self.data_source = FtxPerpetualAPIUserStreamDataSource(self.auth)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
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

    def _simulate_user_update_event(self):
        # Order Trade Update
        resp = {
            "channel": "fills",
            "data": {
                "fee": 10.0,
                "feeRate": "0.0014",
                "future": "COINALPHA-PERP",
                "id": 1,
                "liquidity": "taker",
                "market": "COINALPHA-PERP",
                "orderId": 2,
                "tradeId": 3,
                "price": 1000.00,
                "side": "buy",
                "size": 10.001,
                "time": "2022-01-01T00:40:58.358438+00:00",
                "type": "order"
            },
            "type": "update"
        }

        return ujson.dumps(resp)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_unsuccessful(self, mock_api, mock_ws):
        url = f"{FTX_API_ENDPOINT}"

        mock_api.post(url)

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.send.side_effect = lambda: None
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._simulate_user_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        try:
            self.async_run_with_timeout(msg_queue.get())
        except Exception:
            pass
