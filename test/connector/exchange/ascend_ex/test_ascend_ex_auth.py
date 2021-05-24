#!/usr/bin/env python
import sys
import asyncio
import unittest
import aiohttp
import ujson
import websockets
import conf
import logging
from os.path import join, realpath
from typing import Dict, Any
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.ascend_ex.ascend_ex_constants import REST_URL
from hummingbot.connector.exchange.ascend_ex.ascend_ex_utils import get_ws_url_private

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class TestAscendExAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.ascend_ex_api_key
        secret_key = conf.ascend_ex_secret_key
        cls.auth = AscendExAuth(api_key, secret_key)

    async def rest_auth(self) -> Dict[Any, Any]:
        headers = {
            **self.auth.get_headers(),
            **self.auth.get_auth_headers("info"),
        }
        response = await aiohttp.ClientSession().get(f"{REST_URL}/info", headers=headers)
        return await response.json()

    async def ws_auth(self) -> Dict[Any, Any]:
        info = await self.rest_auth()
        accountGroup = info.get("data").get("accountGroup")
        headers = self.auth.get_auth_headers("stream")
        ws = await websockets.connect(f"{get_ws_url_private(accountGroup)}/stream", extra_headers=headers)

        raw_msg = await asyncio.wait_for(ws.recv(), 5000)
        msg = ujson.loads(raw_msg)

        return msg

    def test_rest_auth(self):
        result = self.ev_loop.run_until_complete(self.rest_auth())
        assert result["code"] == 0

    def test_ws_auth(self):
        result = self.ev_loop.run_until_complete(self.ws_auth())
        assert result["m"] == "connected"
        assert result["type"] == "auth"
