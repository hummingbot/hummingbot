#!/usr/bin/env python
import sys
import asyncio
import unittest
import aiohttp
import conf
import logging
from async_timeout import timeout
from os.path import join, realpath
from typing import Dict, Any
from hummingbot.connector.exchange.coinzoom.coinzoom_auth import CoinzoomAuth
from hummingbot.connector.exchange.coinzoom.coinzoom_websocket import CoinzoomWebsocket
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.coinzoom.coinzoom_constants import Constants

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.coinzoom_api_key
        secret_key = conf.coinzoom_secret_key
        api_username = conf.coinzoom_username
        cls.auth = CoinzoomAuth(api_key, secret_key, api_username)

    async def rest_auth(self) -> Dict[Any, Any]:
        endpoint = Constants.ENDPOINT['USER_BALANCES']
        headers = self.auth.get_headers()
        response = await aiohttp.ClientSession().get(f"{Constants.REST_URL}/{endpoint}", headers=headers)
        return await response.json()

    async def ws_auth(self) -> Dict[Any, Any]:
        ws = CoinzoomWebsocket(self.auth)
        await ws.connect()
        user_ws_streams = {Constants.WS_SUB["USER_ORDERS_TRADES"]: {}}
        async with timeout(30):
            await ws.subscribe(user_ws_streams)
            async for response in ws.on_message():
                if ws.is_subscribed:
                    return True
        return False

    def test_rest_auth(self):
        result = self.ev_loop.run_until_complete(self.rest_auth())
        if len(result) == 0 or "currency" not in result[0].keys():
            print(f"Unexpected response for API call: {result}")
        assert "currency" in result[0].keys()

    def test_ws_auth(self):
        subscribed = self.ev_loop.run_until_complete(self.ws_auth())
        assert subscribed is True
