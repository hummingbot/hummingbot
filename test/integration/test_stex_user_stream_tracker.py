from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.connector.exchange.stex.stex_user_stream_tracker import StexUserStreamTracker
from hummingbot.connector.exchange.stex.stex_auth import StexAuth
from hummingbot.core.utils.async_utils import safe_ensure_future
import asyncio
import logging
import unittest
import conf


class StexUserStreamTrackerUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.stex_auth = StexAuth(conf.stex_access_token)
        cls.user_stream_tracker: StexUserStreamTracker = StexUserStreamTracker(stex_auth=cls.stex_auth)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def test_user_stream(self):
        self.ev_loop.run_until_complete(asyncio.sleep(20.0))
        print(self.user_stream_tracker.user_stream)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
