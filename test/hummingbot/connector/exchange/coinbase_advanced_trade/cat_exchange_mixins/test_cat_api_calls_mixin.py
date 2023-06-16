import asyncio
import unittest
from typing import Any, Dict
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange import CoinbaseAdvancedTradeExchange
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    CoinbaseAdvancedTradeAPICallsMixinProtocol,
)


class ExchangeAPI:
    def __init__(self):
        super().__init__()
        self._api_post_called: bool = False
        self._api_delete_called: bool = False
        self._api_get_called: bool = False

    async def _api_post(self, *args, **kwargs) -> dict:
        self._api_post_called = True
        return {}

    async def _api_delete(self, *args, **kwargs) -> dict:
        self._api_delete_called = True
        return {}

    async def _api_get(self, *args, **kwargs) -> dict:
        self._api_get_called = True
        return {}


class ExchangeAPIMock:
    def __init__(self):
        super().__init__()
        self._api_post = AsyncMock()
        self._api_delete = AsyncMock()
        self._api_get = AsyncMock()

    async def _api_post(self, *args, **kwargs) -> Dict[str, Any]:
        return await self._api_post()

    async def _api_delete(self, *args, **kwargs) -> Dict[str, Any]:
        return await self._api_delete()

    async def _api_get(self, *args, **kwargs) -> Dict[str, Any]:
        return await self._api_get()


class APICallsMixinSubclass(ExchangeAPI):
    def __init__(self):
        super().__init__()


class APICallsMixinSubclassMock(ExchangeAPIMock):
    def __init__(self):
        super().__init__()


class TestAPICallsMixin(unittest.TestCase):
    def setUp(self):
        self.mixin = APICallsMixinSubclass()
        self.mixin_mock = APICallsMixinSubclassMock()

    def test_api_post_calls_subclass_method(self):
        async def run_test():
            await self.mixin.api_post()
            self.assertTrue(self.mixin._api_post_called)

        asyncio.run(run_test())

    def test_api_delete_calls_subclass_method(self):
        async def run_test():
            await self.mixin.api_delete()
            self.assertTrue(self.mixin._api_delete_called)

        asyncio.run(run_test())

    def test_api_get_calls_subclass_method(self):
        async def run_test():
            await self.mixin.api_get()
            self.assertTrue(self.mixin._api_get_called)

        asyncio.run(run_test())

    def test_api_post_success(self):
        async def run_test():
            expected_response = {"success": True}
            self.mixin_mock._api_post.return_value = expected_response
            response = await self.mixin_mock.api_post()
            self.assertEqual(response, expected_response)

        asyncio.run(run_test())

    def test_api_delete_success(self):
        async def run_test():
            expected_response = {"success": True}
            self.mixin_mock._api_delete.return_value = expected_response
            response = await self.mixin_mock.api_delete()
            self.assertEqual(response, expected_response)

        asyncio.run(run_test())

    def test_api_get_success(self):
        async def run_test():
            expected_response = {"success": True}
            self.mixin_mock._api_get.return_value = expected_response
            response = await self.mixin_mock.api_get()
            self.assertEqual(response, expected_response)

        asyncio.run(run_test())

    def test_api_post_error(self):
        async def run_test():
            self.mixin_mock._api_post.side_effect = Exception("API Error")
            with self.assertRaises(Exception):
                await self.mixin_mock.api_post()

        asyncio.run(run_test())

    def test_api_delete_error(self):
        async def run_test():
            self.mixin_mock._api_delete.side_effect = Exception("API Error")
            with self.assertRaises(Exception):
                await self.mixin_mock.api_delete()

        asyncio.run(run_test())

    def test_api_get_error(self):
        async def run_test():
            self.mixin_mock._api_get.side_effect = Exception("API Error")
            with self.assertRaises(Exception):
                await self.mixin_mock.api_get()

        asyncio.run(run_test())

    def test_conforms_to_protocol(self):
        self.assertTrue(isinstance(APICallsMixinSubclass(), CoinbaseAdvancedTradeAPICallsMixinProtocol))

        self.assertTrue(isinstance(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeAPICallsMixinProtocol))


if __name__ == "__main__":
    unittest.main()
