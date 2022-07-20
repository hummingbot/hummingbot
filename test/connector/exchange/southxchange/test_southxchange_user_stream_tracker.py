# #!/usr/bin/env python
# import sys
# import asyncio
# import logging
# import unittest
# import conf

# from os.path import join, realpath
# from hummingbot.connector.exchange.southxchange.southxchange_user_stream_tracker import SouthxchangeUserStreamTracker
# from hummingbot.connector.exchange.southxchange.southxchange_auth import SouthXchangeAuth
# from hummingbot.core.utils.async_utils import safe_ensure_future
# from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL


# sys.path.insert(0, realpath(join(__file__, "../../../../../")))
# logging.basicConfig(level=METRICS_LOG_LEVEL)


# class TestSouthXchangeUserStreamTracker(unittest.TestCase):
#     api_key = conf.southxchange_api_key
#     api_secret = conf.southxchange_secret_key

#     @classmethod
#     def setUpClass(cls):
#         cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
#         cls.southxchange_auth = SouthXchangeAuth(cls.api_key, cls.api_secret)
#         cls.trading_pairs = ["BTC-USDT"]
#         cls.user_stream_tracker: SouthxchangeUserStreamTracker = SouthxchangeUserStreamTracker(
#             southxchange_auth=cls.southxchange_auth, trading_pairs=cls.trading_pairs)
#         cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

#     def test_user_stream(self):
#         # Wait process some msgs.
#         self.ev_loop.run_until_complete(asyncio.sleep(120.0))
#         print(self.user_stream_tracker.user_stream)


# def main():
#     logging.basicConfig(level=logging.INFO)
#     unittest.main()


# if __name__ == "__main__":
#     main()
import asyncio
import json
from typing import Any, Awaitable, Dict
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.southxchange import southxchange_constants as CONSTANTS
from hummingbot.connector.exchange.southxchange.southxchange_auth import SouthXchangeAuth
from hummingbot.connector.exchange.southxchange.southxchange_user_stream_tracker import SouthxchangeUserStreamTracker
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.exchange.southxchange.southxchange_exchange import SouthxchangeExchange
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
API_BASE_URL = "https://www.southxchange.com"

class SouthxchangeUserStreamTrackerTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "LTC2"
        cls.quote_asset = "USD2"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"
        cls.client_config_map = ClientConfigAdapter(ClientConfigMap())

        cls.exchange = SouthxchangeExchange(
            client_config_map=cls.client_config_map,
            southxchange_api_key=cls.api_key,
            southxchange_secret_key=cls.api_secret_key,
            trading_pairs=[cls.trading_pair])

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.mocking_assistant = NetworkMockingAssistant()
        self.listening_task = None
        self.api_factory = None
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._time_provider = TimeSynchronizer()
        self.tracker = SouthxchangeUserStreamTracker(
            connector=self.exchange,southxchange_auth=SouthXchangeAuth(api_key="testAPIKey", secret_key="testSecret",time_provider=self._time_provider),
            api_factory=self.api_factory,
            throttler=self.throttler,
        )

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _accountgroup_response(self) -> Dict[str, Any]:
        message = {"data": {"accountGroup": 12345679}}
        return message

    def _authentication_response(self, authenticated: bool) -> Dict[str, Any]:
        request = {"op": "auth", "args": ["testAPIKey", "testExpires", "testSignature"]}
        message = {"success": authenticated, "ret_msg": "", "conn_id": "testConnectionID", "request": request}

        return message

    @aioresponses()
    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_authenticates_and_subscribes_to_events(self, api_mock, ws_connect_mock):
        output_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.tracker.data_source.listen_for_user_stream(output_queue))
        resp = "token"
        # url = f"{API_BASE_URL}/{'api/v4/GetWebSocketToken'}"
        # regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))  
        api_mock.post(f"{API_BASE_URL}/{'api/v4/GetWebSocketToken'}", body=json.dumps(resp))

        # Create WS mock
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # # Add the authentication response for the websocket
        resp = self._authentication_response(authenticated=True)
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(resp))
        # Add a dummy message for the websocket to read and include in the "messages" queue
        resp = {"data": "dummyMessage"}
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(resp))
        ret = self.ev_loop.run_until_complete(output_queue.get())

        self.assertEqual(
            {
                "success": True,
                "ret_msg": "",
                "conn_id": "testConnectionID",
                "request": {"op": "auth", "args": ["testAPIKey", "testExpires", "testSignature"]},
            },
            ret,
        )

        ret = self.ev_loop.run_until_complete(output_queue.get())

        self.assertEqual(resp, ret)
