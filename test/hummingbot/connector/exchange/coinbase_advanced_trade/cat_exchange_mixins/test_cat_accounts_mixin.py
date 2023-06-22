import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Iterable, Set
from unittest.mock import AsyncMock, MagicMock, patch

from _decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeAccount,
    CoinbaseAdvancedTradeListAccountsResponse,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_accounts_mixin import (
    CoinbaseAdvancedTradeAccountsMixin,
)


# Create a helper function to create an AccountInfo object
def create_account_info(uuid: str = "123"):
    return {
        "uuid": uuid,
        "name": "BTC Wallet",
        "currency": "BTC",
        "available_balance": {
            "value": Decimal(5),
            "currency": "BTC"
        },
        "default": False,
        "active": True,
        "created_at": "2021-05-31T09:59:59Z",
        "updated_at": "2021-05-31T09:59:59Z",
        "deleted_at": "2021-05-31T09:59:59Z",
        "type": "ACCOUNT_TYPE_CRYPTO",
        "ready": True,
        "hold": {
            "value": Decimal(1),
            "currency": "BTC"
        }
    }


# Create a helper function to create an Accounts object
def create_accounts():
    return {
        "accounts": [create_account_info(),
                     create_account_info(uuid="456")],
        "has_next": True,
        "cursor": "789100",
        "size": 1
    }


def create_last_accounts_page():
    return {
        "accounts": [create_account_info(),
                     create_account_info(uuid="456")],
        "has_next": False,
        "cursor": "789100",
        "size": 1
    }


# Create a subclass of CoinbaseAdvancedTradeAccountsMixin simulating Exchange inheritance
class ExchangeAPI:
    def __init__(self):
        self.api_get_called: bool = False

    async def api_get(self, *args, **kwargs) -> Dict[str, Any]:
        self.api_get_called = True
        await asyncio.sleep(0)
        return create_accounts()


class ExchangeMixinSubclass(CoinbaseAdvancedTradeAccountsMixin, ExchangeAPI):
    def __init__(self):
        super().__init__()
        self.remove_balances_called: bool = False
        self.update_available_balance_called: bool = False
        self.update_balance_called: bool = False
        self.get_balances_keys_called: bool = False

    def get_balances_keys(self) -> Set[str]:
        self.get_balances_keys_called = True
        return set()

    def update_balance(self, asset: str, balance: Decimal):
        self.update_balance_called = True

    def update_available_balance(self, asset: str, balance: Decimal):
        self.update_available_balance_called = True

    def remove_balances(self, assets: Iterable[str]):
        self.remove_balances_called = True


async def overwritten_method(*args, **kwargs) -> Dict[str, Any]:
    return {}


class TestAccountsMixin(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        self.accounts_mixin = CoinbaseAdvancedTradeAccountsMixin()
        self.accounts = create_accounts()
        self.exchange_with_accounts_mixin = ExchangeMixinSubclass()

    # Helper function to create an asynchronous generator
    @staticmethod
    async def async_gen(seq):
        for item in seq:
            yield item

    def test_asset_uuid_map(self):
        self.assertEqual(self.accounts_mixin.asset_uuid_map, {})

    async def test_list_one_page_of_accounts(self):
        self.accounts_mixin.api_get = AsyncMock(return_value=self.accounts)
        accounts = await self.accounts_mixin._list_one_page_of_accounts("0")
        self.accounts_mixin.api_get.assert_called_once_with(
            path_url="api/v3" + CONSTANTS.ACCOUNTS_LIST_EP,
            data={},
            params={"limit": 250},
            is_auth_required=True,
            limit_id="accounts"
        )
        self.assertEqual(True, accounts.has_next, f"Expected has_next to be True, got {accounts.has_next}")
        self.assertEqual("789100", accounts.cursor, f"Expected cursor to be 789100, got {accounts.cursor}")
        self.assertEqual(accounts.accounts,
                         tuple([CoinbaseAdvancedTradeAccount(**a) for a in self.accounts["accounts"]]))

    async def test_list_one_page_of_accounts_in_exchange(self):
        accounts = await self.exchange_with_accounts_mixin._list_one_page_of_accounts("0")
        self.assertEqual(accounts, CoinbaseAdvancedTradeListAccountsResponse(**create_accounts()), )
        self.assertEqual(self.exchange_with_accounts_mixin.api_get_called, True)

    async def test_list_trading_accounts(self):
        self.accounts_mixin._list_one_page_of_accounts = AsyncMock(
            return_value=CoinbaseAdvancedTradeListAccountsResponse(**self.accounts))
        self.accounts_mixin._list_one_page_of_accounts.side_effect = [
            CoinbaseAdvancedTradeListAccountsResponse(**create_last_accounts_page())]
        trading_accounts = [account async for account in self.accounts_mixin._list_trading_accounts()]
        self.assertEqual(2, len(trading_accounts))
        self.accounts_mixin._list_one_page_of_accounts.assert_called_once()
        self.assertEqual(trading_accounts, [CoinbaseAdvancedTradeAccount(**a) for a in self.accounts["accounts"]])
        self.assertEqual(self.accounts_mixin.asset_uuid_map, {"BTC": "456"})

    async def test_list_trading_accounts_in_exchange(self):
        self.exchange_with_accounts_mixin._list_one_page_of_accounts = AsyncMock(
            return_value=CoinbaseAdvancedTradeListAccountsResponse(**self.accounts))
        self.exchange_with_accounts_mixin._list_one_page_of_accounts.side_effect = [
            CoinbaseAdvancedTradeListAccountsResponse(**create_last_accounts_page())]
        trading_accounts = [account async for account in self.exchange_with_accounts_mixin._list_trading_accounts()]

        self.assertEqual(trading_accounts, [CoinbaseAdvancedTradeAccount(**a) for a in self.accounts["accounts"]])
        self.assertEqual(self.exchange_with_accounts_mixin.asset_uuid_map, {"BTC": "456"})

    async def test_update_balances(self):
        self.accounts_mixin._list_trading_accounts = MagicMock(
            return_value=self.async_gen([CoinbaseAdvancedTradeAccount(**a) for a in self.accounts["accounts"]]))
        self.accounts_mixin.get_balances_keys = MagicMock(return_value=set())
        self.accounts_mixin.update_balance = MagicMock()
        self.accounts_mixin.update_available_balance = MagicMock()
        self.accounts_mixin.remove_balances = MagicMock()

        await self.accounts_mixin._update_balances()

        self.accounts_mixin._list_trading_accounts.assert_called_once()
        self.accounts_mixin.get_balances_keys.assert_called_once()
        self.accounts_mixin.update_balance.assert_called_with("BTC", Decimal(1))
        self.accounts_mixin.update_available_balance.assert_called_with("BTC", Decimal(5))
        self.accounts_mixin.remove_balances.assert_called_once_with(set())

    async def test_update_balances_in_exchange(self):
        self.exchange_with_accounts_mixin._list_trading_accounts = MagicMock(
            return_value=self.async_gen([CoinbaseAdvancedTradeAccount(**a) for a in self.accounts["accounts"]]))
        await self.exchange_with_accounts_mixin._update_balances()

        self.assertEqual(self.exchange_with_accounts_mixin.get_balances_keys_called, True)
        self.assertEqual(self.exchange_with_accounts_mixin.update_balance_called, True)
        self.assertEqual(self.exchange_with_accounts_mixin.update_available_balance_called, True)
        self.assertEqual(self.exchange_with_accounts_mixin.remove_balances_called, True)

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

        class SubClass(CoinbaseAdvancedTradeAccountsMixin, OtherMixin, BaseClass):
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


if __name__ == "__main__":
    unittest.main()
