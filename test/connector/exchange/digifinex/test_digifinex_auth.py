from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import asyncio
import unittest

import conf
from hummingbot.connector.exchange.digifinex.digifinex_auth import DigifinexAuth
from hummingbot.connector.exchange.digifinex.digifinex_websocket import DigifinexWebsocket


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.digifinex_api_key
        secret_key = conf.digifinex_secret_key
        cls.auth = DigifinexAuth(api_key, secret_key)
        cls.ws = DigifinexWebsocket(cls.auth)

    async def ws_auth(self):
        await self.ws.connect()
        await self.ws.subscribe("balance", ["USDT", "BTC", "ETH"])

        # no msg will arrive until balance changed after subscription
        # async for response in self.ws.on_message():
        #     if (response.get("method") == "subscribe"):
        #         return response

    def test_ws_auth(self):
        self.ev_loop.run_until_complete(self.ws_auth())
        # assert result["code"] == 0
