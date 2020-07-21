# import asyncio
# import json
import unittest
# from typing import List

# import websockets

import conf
#from hummingbot.market.bitfinex import BITFINEX_WS_AUTH_URI
from hummingbot.market.okex.okex_auth import OKExAuth

import requests

class TestAuth(unittest.TestCase):
    def setUp(self):

        # cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        okex_api_key = conf.okex_api_key
        okex_secret_key = conf.okex_secret_key
        okex_passphrase = conf.okex_passphrase

        assert okex_api_key
        assert okex_secret_key
        assert okex_passphrase

        self.auth = OKExAuth(okex_api_key, okex_secret_key, okex_passphrase)

    def test_auth(self):
        print("I run")
        headers = self.auth.add_auth_to_params('get', "api/spot/v3/accounts", {})
        print(dict(headers))
        r = requests.get("https://www.okex.com/api/spot/v3/accounts", headers=headers)
        print(r.text)
        # print(dict(headers))

        assert False

        # result: List[str] = self.ev_loop.run_until_complete(self.con_auth())
        # assert "serverId" in result

    async def con_auth(self):
        # async with websockets.connect(BITFINEX_WS_AUTH_URI) as ws:
        #     ws: websockets.WebSocketClientProtocol = ws
        #     payload = self.auth.generate_auth_payload()
        #     await ws.send(json.dumps(payload))
        #     msg = await asyncio.wait_for(ws.recv(), timeout=30)  # response
        #     return msg
        pass
