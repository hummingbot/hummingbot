#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))
import asyncio
import logging
import unittest

import hummingbot.connector.exchange.idex.idex_resolve

from hummingbot.connector.exchange.idex.idex_user_stream_tracker import IdexUserStreamTracker
from hummingbot.connector.exchange.idex.idex_auth import IdexAuth
from hummingbot.core.utils.async_utils import safe_ensure_future

import conf


"""
To run this integration test before the idex connector is initialized you must set environment variables for API key,
API secret and ETH Wallet. Example in bash (these are not real api key and address, substitute your own):

export IDEX_API_KEY='d88c5070-42ea-435f-ba26-8cb82064a972'
export IDEX_API_SECRET_KEY='pLrUpy53o8enXTAHkOqsH8pLpQVMQ47p'
export IDEX_WALLET_PRIVATE_KEY='ad10037142dc378b3f004bbb4803e24984b8d92969ec9407efb56a0135661576'
export IDEX_CONTRACT_BLOCKCHAIN='ETH'
"""


BASE_URL = 'https://api-sandbox-eth.idex.io/'  # rest url for sandbox (rinkeby) ETH chain

# load config from Hummingbot's central debug conf
# Values can be overridden by env variables (in uppercase). Example: export IDEX_WALLET_PRIVATE_KEY="1234567"
IDEX_API_KEY = getattr(conf, 'idex_api_key') or ''
IDEX_API_SECRET_KEY = getattr(conf, 'idex_api_secret_key') or ''
IDEX_WALLET_PRIVATE_KEY = getattr(conf, 'idex_wallet_private_key') or ''
IDEX_CONTRACT_BLOCKCHAIN = getattr(conf, 'idex_contract_blockchain') or 'ETH'
IDEX_USE_SANDBOX = True if getattr(conf, 'idex_use_sandbox') is None else getattr(conf, 'idex_use_sandbox')

# force resolution of api base url for conf values provided to this test
hummingbot.connector.exchange.idex.idex_resolve._IS_IDEX_SANDBOX = IDEX_USE_SANDBOX
hummingbot.connector.exchange.idex.idex_resolve._IDEX_BLOCKCHAIN = IDEX_CONTRACT_BLOCKCHAIN


class IdexUserStreamTrackerUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.idex_auth = IdexAuth(IDEX_API_KEY, IDEX_API_SECRET_KEY, IDEX_WALLET_PRIVATE_KEY)

        cls.user_stream_tracker: IdexUserStreamTracker = IdexUserStreamTracker(idex_auth=cls.idex_auth, trading_pairs=['DIL-ETH'])
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
