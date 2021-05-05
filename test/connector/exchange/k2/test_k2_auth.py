import aiohttp
import asyncio
import conf
import logging
import sys
import unittest
import ujson
import websockets

import hummingbot.connector.exchange.k2.k2_constants as CONSTANTS

from os.path import join, realpath
from typing import (
    Any,
    Dict,
)

from hummingbot.connector.exchange.k2.k2_auth import K2Auth
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class K2AuthUnitTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.k2_api_key
        secret_key = conf.k2_secret_key
        cls.auth: K2Auth = K2Auth(api_key, secret_key)

    async def rest_auth(self) -> Dict[str, Any]:
        http_client = aiohttp.ClientSession()
        headers = self.auth.generate_auth_dict(path_url=CONSTANTS.GET_DETAILED_BALANCES)
        resp = await http_client.post(url=CONSTANTS.REST_URL + CONSTANTS.GET_DETAILED_BALANCES,
                                      headers=headers)

        await http_client.close()
        return resp

    async def ws_auth(self) -> Dict[Any, Any]:
        ws = await websockets.connect(CONSTANTS.WSS_URL)

        auth_payload = await self.auth.get_ws_auth_payload()

        await ws.send(ujson.dumps(auth_payload, escape_forward_slashes=False))
        resp = await ws.recv()
        await ws.close()

        return ujson.loads(resp)

    def test_rest_auth(self):
        result = self.ev_loop.run_until_complete(self.rest_auth())
        assert not isinstance(result, Exception)

    def test_ws_auth(self):
        result = self.ev_loop.run_until_complete(self.ws_auth())
        self.assertTrue(result["success"])


if __name__ == "__main__":
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()
