import asyncio
import aiohttp
import unittest
import conf
from typing import List
from hummingbot.connector.exchange.wazirx.wazirx_auth import WazirxAuth
from hummingbot.connector.exchange.wazirx import wazirx_constants as CONSTANTS


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.wazirx_api_key
        secret_key = conf.wazirx_secret_key
        cls.auth = WazirxAuth(api_key, secret_key)

    async def con_rest_auth(self):
        params = {}
        params = self.auth.get_auth(params)
        headers = self.auth.get_headers()
        async with aiohttp.request('GET', f"{CONSTANTS.WAZIRX_API_BASE}/{CONSTANTS.FUND_DETAILS_PATH_URL}", headers=headers, data=params) as response:
            return response.status

    def test_auth(self):
        result: List[str] = self.ev_loop.run_until_complete(self.con_rest_auth())
        assert result == 200
