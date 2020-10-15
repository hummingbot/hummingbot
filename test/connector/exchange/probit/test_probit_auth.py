from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import asyncio
import unittest
from typing import List

import conf
from hummingbot.connector.exchange.probit.probit_auth import ProbitAuth
from hummingbot.connector.exchange.probit.probit_websocket import ProbitWebsocket


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.probit_api_key
        secret_key = conf.probit_secret_key
        cls.auth = ProbitAuth(api_key, secret_key)
        cls.ws = ProbitWebsocket(cls.auth)

    async def con_auth(self):
        await self.ws.connect()
        await self.ws.subscribe("balance")

        async for response in self.ws.on_message():
            if (response.get("channel") == "balance"):
                return response

    def test_auth(self):
        result: List[str] = self.ev_loop.run_until_complete(self.con_auth())
        assert result["data"] != None
        print(result["data"])


if __name__ == '__main__':
    unittest.main()
