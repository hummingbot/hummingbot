from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_api_calls_mixin import (
    CoinbaseAdvancedTradeAPICallsMixin,
)


class TestCoinbaseAdvancedTradeAPICallsMixin(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        # Create a mock object that simulates the behavior of a class that uses the mixin
        self.mock_api = AsyncMock()
        self.mixin = CoinbaseAdvancedTradeAPICallsMixin()

    async def test_api_post(self):
        self.mixin._api_post = self.mock_api
        await self.mixin.api_post("test", arg1="value1")
        self.mock_api.assert_called_once_with("test", arg1="value1", return_err=True)

    async def test_api_delete(self):
        self.mixin._api_delete = self.mock_api
        await self.mixin.api_delete("test", arg1="value1")
        self.mock_api.assert_called_once_with("test", arg1="value1", return_err=True)

    async def test_api_get(self):
        self.mixin._api_get = self.mock_api
        await self.mixin.api_get("test", arg1="value1")
        self.mock_api.assert_called_once_with("test", arg1="value1", return_err=True)

    async def test_inheritance(self):
        class APIImplementation:
            async def _api_post(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

            async def _api_delete(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

            async def _api_get(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        class SubClass(CoinbaseAdvancedTradeAPICallsMixin, APIImplementation):
            pass

        test_obj = SubClass()
        self.assertTrue(hasattr(test_obj, "api_post"))
        self.assertTrue(hasattr(test_obj, "api_delete"))
        self.assertTrue(hasattr(test_obj, "api_get"))

        # Mock the methods in the base class
        with patch.object(APIImplementation, "_api_post", new_callable=AsyncMock) as mock_post, \
                patch.object(APIImplementation, "_api_delete", new_callable=AsyncMock) as mock_delete, \
                patch.object(APIImplementation, "_api_get", new_callable=AsyncMock) as mock_get:
            await test_obj.api_post("test", arg1="value1")
            mock_post.assert_called_once_with("test", arg1="value1", return_err=True)

            await test_obj.api_delete("test", arg1="value1")
            mock_delete.assert_called_once_with("test", arg1="value1", return_err=True)

            await test_obj.api_get("test", arg1="value1")
            mock_get.assert_called_once_with("test", arg1="value1", return_err=True)

    async def test_inheritance_override(self):
        class APIImplementation:
            async def _api_post(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

            async def _api_delete(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

            async def _api_get(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        class SubClass(
            CoinbaseAdvancedTradeAPICallsMixin,
            APIImplementation,
        ):
            async def _api_get(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        test_obj = SubClass()
        self.assertTrue(hasattr(test_obj, "api_post"))
        self.assertTrue(hasattr(test_obj, "api_delete"))
        self.assertTrue(hasattr(test_obj, "api_get"))

        # Mock the methods in the base class
        with patch.object(APIImplementation, "_api_post", new_callable=AsyncMock) as mock_post, \
                patch.object(APIImplementation, "_api_delete", new_callable=AsyncMock) as mock_delete:
            # Patching the _api_get method in the subclass
            with patch.object(SubClass, "_api_get", new_callable=AsyncMock) as mock_get:
                await test_obj.api_post("test", arg1="value1")
                mock_post.assert_called_once_with("test", arg1="value1", return_err=True)

                await test_obj.api_delete("test", arg1="value1")
                mock_delete.assert_called_once_with("test", arg1="value1", return_err=True)

                await test_obj.api_get("test", arg1="value1")
                mock_get.assert_called_once_with("test", arg1="value1", return_err=True)

    async def test_daisy_chaining(self):
        class TestClass1:
            async def _api_post(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        class TestClass2(CoinbaseAdvancedTradeAPICallsMixin, TestClass1):
            pass

        test_obj = TestClass2()
        self.assertTrue(hasattr(test_obj, "api_post"))

    async def test_daisy_chaining_with_kwargs(self):
        class BaseClass:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def base_method(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

            async def overwritten_in_mixin(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

            async def overwritten_in_subclass(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        class OtherMixin:
            def __init__(self, **kwargs):
                if super().__class__ is not object:
                    super().__init__(**kwargs)

            async def overwritten_in_mixin(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        class SubClass(CoinbaseAdvancedTradeAPICallsMixin, OtherMixin, BaseClass):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)

            async def overwritten_in_subclass(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        test_obj = SubClass(test="test")
        # Mock the methods in the base class
        with patch.object(BaseClass, "base_method", new_callable=AsyncMock) as mock_method:
            with patch.object(OtherMixin, "overwritten_in_mixin", new_callable=AsyncMock) as mock_mixin:
                with patch.object(SubClass, "overwritten_in_subclass", new_callable=AsyncMock) as mock_subbclass:
                    await test_obj.overwritten_in_subclass()
                    await test_obj.overwritten_in_mixin()
                    await test_obj.base_method()
                    mock_method.assert_called_once_with()
                    mock_mixin.assert_called_once_with()
                    mock_subbclass.assert_called_once_with()
                    self.assertEqual(test_obj.kwargs, {"test": "test"})
