from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import asyncio
import conf
import logging
from decimal import Decimal
import unittest

from hummingbot.core.event.events import (
    OrderType,
    TradeType,
)

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.crypto_com.crypto_com_exchange import CryptoComExchange

logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.crypto_com_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.crypto_com_secret_key


class CryptoComExchangeUnitTest(unittest.TestCase):
    trading_pair = "BTC-USDT"

    def setUp(self) -> None:
        self.crypto_com = CryptoComExchange({}, {}, API_KEY, API_SECRET)

    def test_public_api_request(self):
        asyncio.get_event_loop().run_until_complete(self._test_public_api_request())

    async def _test_public_api_request(self):
        # response = await self.crypto_com._api_request("get", "public/get-instruments")
        # print(response)
        response = await self.crypto_com._api_request("get", "public/get-ticker?instrument_name=BTC_USDT")
        print(response)
        self.assertGreater(len(response), 0)

    def test_private_api_request(self):
        asyncio.get_event_loop().run_until_complete(self._test_private_api_request())

    async def _test_private_api_request(self):
        response = await self.crypto_com._api_request("post", "private/get-account-summary", {"currency": "USDT"},
                                                      is_auth_required=True)
        print(response)
        self.assertGreater(len(response), 0)
        response = await self.crypto_com._api_request("post", "private/get-account-summary", {},
                                                      is_auth_required=True)
        print(response)
        self.assertGreater(len(response), 0)

    def test_update_trading_rules(self):
        asyncio.get_event_loop().run_until_complete(self._test_update_trading_rules())

    async def _test_update_trading_rules(self):
        await self.crypto_com._update_trading_rules()
        print(self.crypto_com._trading_rules)
        self.assertGreater(len(self.crypto_com._trading_rules), 0)

    def test_create_orders(self):
        asyncio.get_event_loop().run_until_complete(self._test_create_orders())

    async def _test_create_orders(self):
        await self.crypto_com._update_trading_rules()
        await self.crypto_com.create_order(TradeType.BUY, "HBOT-0001", self.trading_pair, Decimal("0.001"),
                                           OrderType.LIMIT_MAKER, Decimal("10000"))
        await asyncio.sleep(2)
        print(self.crypto_com._in_flight_orders)
        self.assertGreater(len(self.crypto_com._in_flight_orders), 0)
        await self.crypto_com._update_order_status()
        await self.crypto_com.cancel()

    def test_update_balances(self):
        asyncio.get_event_loop().run_until_complete(self._test_update_balances())

    async def _test_update_balances(self):
        await self.crypto_com._update_balances()
        self.assertTrue(len(self.crypto_com._account_balances) > 0)
        self.assertTrue(len(self.crypto_com._account_available_balances) > 0)
