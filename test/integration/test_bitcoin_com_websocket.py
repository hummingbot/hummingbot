#!/usr/bin/env python
import asyncio
import sys
import logging
import unittest
import conf

from os.path import join, realpath
from hummingbot.market.bitcoin_com.bitcoin_com_websocket import BitcoinComWebsocket
from hummingbot.market.bitcoin_com.bitcoin_com_auth import BitcoinComAuth

sys.path.insert(0, realpath(join(__file__, "../../../")))


class BitcoinComWebsocketUnitTest(unittest.TestCase):
    auth = BitcoinComAuth(conf.bitcoin_com_api_key, conf.bitcoin_com_secret_key)
    ws = BitcoinComWebsocket()
    # balances = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    async def wait_til_ready(cls):
        while True:
            await cls.ws.connect()

            if cls.ws._client.open is True:
                print("Websocket connection established.")
                return

            await asyncio.sleep(1)

    def test_open(self):
        """
        Tests if websocket connection is opened succesfully
        """
        self.assertTrue(self.ws._client.open)

    # def test_authenticated(self):
    #     """
    #     Tests if websocket connection is authenticated
    #     """
    #     self.assertTrue(self.connectionAuthenticated)

    # def test_received_trading_balances(self):
    #     """
    #     Tests if it received balances
    #     """
    #     print(self.balances)
    #     self.assertGreater(len(list(self.balances)))


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
