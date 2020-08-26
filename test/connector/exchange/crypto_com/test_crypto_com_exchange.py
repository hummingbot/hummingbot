from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import asyncio
import conf
import logging

from typing import (
    List,
)
import unittest

from hummingbot.core.event.events import (
    MarketEvent,
)

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.crypto_com.crypto_com_exchange import CryptoComExchange

logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.crypto_com_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.crypto_com_secret_key


class CryptoComExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]

    def test_public_api_request(self):
        asyncio.get_event_loop().run_until_complete(self._test_public_api_request())

    async def _test_public_api_request(self):
        cryto_com = CryptoComExchange({}, {}, API_KEY, API_SECRET)
        response = await cryto_com._api_request("get", "public/get-instruments")
        print(response)
        self.assertGreater(len(response), 0)

    def test_private_api_request(self):
        asyncio.get_event_loop().run_until_complete(self._test_private_api_request())

    async def _test_private_api_request(self):
        cryto_com = CryptoComExchange({}, {}, API_KEY, API_SECRET)
        response = await cryto_com._api_request("post", "private/get-account-summary", {"currency": "USDT"},
                                                is_auth_required=True)
        print(response)
        self.assertGreater(len(response), 0)
        response = await cryto_com._api_request("post", "private/get-account-summary", {},
                                                is_auth_required=True)
        print(response)
        self.assertGreater(len(response), 0)

    def test_update_trading_rules(self):
        asyncio.get_event_loop().run_until_complete(self._test_update_trading_rules())

    async def _test_update_trading_rules(self):
        crypto_com = CryptoComExchange({}, {}, API_KEY, API_SECRET)
        await crypto_com._update_trading_rules()
        print(crypto_com._trading_rules)
        self.assertGreater(len(crypto_com._trading_rules), 0)
