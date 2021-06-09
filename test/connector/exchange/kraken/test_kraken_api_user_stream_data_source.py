#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from hummingbot.connector.exchange.kraken.kraken_api_user_stream_data_source import KrakenAPIUserStreamDataSource
from hummingbot.connector.exchange.kraken.kraken_auth import KrakenAuth
import asyncio
import logging
import unittest
import conf


class KrakenAPIOrderBookDataSourceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.kraken_auth = KrakenAuth(conf.kraken_api_key.strip(), conf.kraken_secret_key.strip())
        cls.user_stream_data_source: KrakenAPIUserStreamDataSource = KrakenAPIUserStreamDataSource(kraken_auth=cls.kraken_auth)

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def test_get_auth_token(self):
        self.token: str = self.run_async(self.user_stream_data_source.get_auth_token())
        self.assertIsInstance(self.token, str)
        self.run_async(self.user_stream_data_source.stop())


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
