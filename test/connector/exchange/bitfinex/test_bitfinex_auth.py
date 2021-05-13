import asyncio
import json
import unittest
from typing import List

import websockets

import conf
from hummingbot.connector.exchange.bitfinex import BITFINEX_WS_AUTH_URI
from hummingbot.connector.exchange.bitfinex.bitfinex_auth import BitfinexAuth


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

        api_key = conf.bitfinex_api_key
        secret_key = conf.bitfinex_secret_key
        cls.auth = BitfinexAuth(api_key, secret_key)

    async def con_auth(self):
        async with websockets.connect(BITFINEX_WS_AUTH_URI) as ws:
            ws: websockets.WebSocketClientProtocol = ws
            payload = self.auth.generate_auth_payload('AUTH{nonce}'.format(nonce=self.auth.get_nonce()))
            await ws.send(json.dumps(payload))
            msg = await asyncio.wait_for(ws.recv(), timeout=30)  # response
            return msg

    def test_auth(self):
        result: List[str] = self.ev_loop.run_until_complete(self.con_auth())
        assert "serverId" in result
