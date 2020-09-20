import asyncio
import unittest
import conf

from hummingbot.connector.exchange.bitfinex.bitfinex_auth import BitfinexAuth
from hummingbot.connector.exchange.bitfinex.bitfinex_user_stream_tracker import \
    BitfinexUserStreamTracker


class BitfinexUserStreamTrackerUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.bitfinex_auth = BitfinexAuth(conf.bitfinex_api_key,
                                         conf.bitfinex_secret_key)
        cls.trading_pair = ["ETHUSD"]   # Using V3 convention since OrderBook is built using V3
        cls.user_stream_tracker: BitfinexUserStreamTracker = BitfinexUserStreamTracker(
            bitfinex_auth=cls.bitfinex_auth, trading_pairs=cls.trading_pair)
        cls.user_stream_tracker_task: asyncio.Task = asyncio.ensure_future(
            cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        assert self.user_stream_tracker.user_stream.qsize() > 0
