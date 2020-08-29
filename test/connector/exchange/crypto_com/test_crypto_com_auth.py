import asyncio
import unittest
from typing import List

import conf
from hummingbot.connector.exchange.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.connector.exchange.crypto_com.crypto_com_websocket import CryptoComWebsocket


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.crypto_com_api_key
        secret_key = conf.crypto_com_secret_key
        cls.auth = CryptoComAuth(api_key, secret_key)
        cls.ws = CryptoComWebsocket(cls.auth)

    async def con_auth(self):
        await self.ws.connect()
        await self.ws.subscribe(["user.balance"])

        async for response in self.ws.on_message():
            if (response.get("method") == "subscribe"):
                return response

    def test_auth(self):
        result: List[str] = self.ev_loop.run_until_complete(self.con_auth())
        assert result["code"] == 0
