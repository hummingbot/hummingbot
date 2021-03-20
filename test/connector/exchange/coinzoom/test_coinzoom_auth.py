#!/usr/bin/env python
import sys
import asyncio
import unittest
import aiohttp
import conf
import logging
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
        cls.auth = CoinzoomAuth(api_key, secret_key)

    async def rest_auth(self) -> Dict[Any, Any]:
        endpoint = Constants.ENDPOINT['USER_BALANCES']
        headers = self.auth.get_headers("GET", f"{Constants.REST_URL_AUTH}/{endpoint}", None)
        response = await aiohttp.ClientSession().get(f"{Constants.REST_URL}/{endpoint}", headers=headers)
        return await response.json()

    async def ws_auth(self) -> Dict[Any, Any]:
        ws = CoinzoomWebsocket(self.auth)
        await ws.connect()
        await ws.subscribe(Constants.WS_SUB["USER_ORDERS_TRADES"], None, {})
        async for response in ws.on_message():
            return response

    def test_rest_auth(self):
        result = self.ev_loop.run_until_complete(self.rest_auth())
        if len(result) == 0 or "currency" not in result[0].keys():
            print(f"Unexpected response for API call: {result}")
        assert "currency" in result[0].keys()

    def test_ws_auth(self):
        try:
            response = self.ev_loop.run_until_complete(self.ws_auth())
            no_errors = True
        except Exception:
            no_errors = False
        assert no_errors is True
        if 'result' not in response:
            print(f"Unexpected response for API call: {response}")
        assert response['result'] is True
