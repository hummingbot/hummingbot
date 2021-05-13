#!/usr/bin/env python

from os.path import join, realpath
import sys

import conf
from hummingbot.connector.exchange.beaxy.beaxy_auth import BeaxyAuth

from hummingbot.connector.exchange.beaxy.beaxy_user_stream_tracker import BeaxyUserStreamTracker

import asyncio
import logging
import unittest

sys.path.insert(0, realpath(join(__file__, "../../../../../")))

logging.basicConfig(level=logging.DEBUG)


class BeaxyUserStreamTrackerUnitTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        beaxy_auth = BeaxyAuth(conf.beaxy_api_key,
                               conf.beaxy_api_secret)
        cls.user_stream_tracker: BeaxyUserStreamTracker = BeaxyUserStreamTracker(beaxy_auth)
        cls.user_stream_tracker_task = asyncio.ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        print(self.user_stream_tracker.user_stream)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
