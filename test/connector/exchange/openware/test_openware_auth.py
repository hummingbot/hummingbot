#!/usr/bin/env python
import sys
import asyncio
import unittest
import aiohttp
import conf
import traceback
import logging
from async_timeout import timeout
from os.path import join, realpath
from typing import Any, Tuple
from hummingbot.connector.exchange.openware.openware_auth import OpenwareAuth
from hummingbot.connector.exchange.openware.openware_websocket import OpenwareWebsocket
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.openware.openware_constants import Constants
from hummingbot.connector.exchange.openware.openware_http_utils import aiohttp_response_with_errors

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.openware_api_key
        secret_key = conf.openware_secret_key
        cls.auth = OpenwareAuth(api_key, secret_key)

    async def rest_auth(self) -> Tuple[Any, Any]:
        endpoint = Constants.ENDPOINT['USER_BALANCES']
        headers = self.auth.get_headers()
        http_client = aiohttp.ClientSession()
        http_status, response, request_errors = await aiohttp_response_with_errors(http_client.request(method='GET', url=f"{Constants.REST_URL}/{endpoint}", headers=headers))
        await http_client.close()
        return response, request_errors

    async def ws_auth(self) -> bool:
        ws = OpenwareWebsocket(self.auth)
        await ws.connect()
        async with timeout(60):
            await ws.subscribe(Constants.WS_SUB["USER_ORDERS_TRADES"])
            async for response in ws.on_message():
                if ws.is_subscribed:
                    return True
        return False

    def test_rest_auth(self):
        result, errors = self.ev_loop.run_until_complete(self.rest_auth())
        if errors:
            reason = result.get('errors', result.get('error', result)) if isinstance(result, dict) else result
            print(f"\nUnable to connect: {reason}")
        assert errors is False
        if len(result) == 0 or "currency" not in result[0].keys():
            print(f"\nUnexpected response for API call: {result}")
        assert "currency" in result[0].keys()

    def test_ws_auth(self):
        try:
            subscribed = self.ev_loop.run_until_complete(self.ws_auth())
            no_errors = True
        except Exception as ex:
            traceback.print_exc()
            no_errors = False
            print(ex)
        assert no_errors is True
        assert subscribed is True
