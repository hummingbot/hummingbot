import asyncio
import unittest
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.market.binance_perpetual.binance_perpetual_user_stream_tracker import BinancePerpetualUserStreamTracker
from .assets.test_keys import Keys

import logging

logging.basicConfig(level=logging.DEBUG)

API_KEY = Keys.get_binance_futures_api_key()


class BinancePerpetualUserStreamTrackerUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.user_stream_tracker: BinancePerpetualUserStreamTracker = BinancePerpetualUserStreamTracker(
            data_source_type=UserStreamTrackerDataSourceType.EXCHANGE_API,
            api_key=API_KEY
        )
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        self.ev_loop.run_until_complete((asyncio.sleep(120)))
        print(self.user_stream_tracker.user_stream)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
