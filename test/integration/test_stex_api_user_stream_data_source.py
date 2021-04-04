from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))
from hummingbot.connector.exchange.stex.stex_api_user_stream_data_source import StexAPIUserStreamDataSource
from hummingbot.connector.exchange.stex.stex_auth import StexAuth
import asyncio
import logging
import unittest
import conf


class StexAPIOrderBookDataSourceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.stex_auth = StexAuth(conf.stex_access_token)
        cls.user_stream_data_source: StexAPIUserStreamDataSource = StexAPIUserStreamDataSource(stex_auth=cls.stex_auth)

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def test_get_auth_token(self):
        self.token: str = self.run_async(self.user_stream_data_source.get_access_token())
        self.assertIsInstance(self.token, str)
        self.run_async(self.user_stream_data_source.stop())


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
