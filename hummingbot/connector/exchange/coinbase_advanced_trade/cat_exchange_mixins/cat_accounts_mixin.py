from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Iterable, Set

from _decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_api_calls_mixin import (
    _APICallsMixinSuperCalls,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utils import AccountInfo, Accounts


class _AccountsMixinAbstract(ABC):
    @abstractmethod
    def get_balances_keys(self) -> Set[str]:
        pass

    @abstractmethod
    def update_balance(self, asset: str, balance: Decimal):
        pass

    @abstractmethod
    def update_available_balance(self, asset: str, balance: Decimal):
        pass

    @abstractmethod
    def remove_balances(self, assets: Iterable[str]):
        pass


class _AccountsMixin(_APICallsMixinSuperCalls,
                     _AccountsMixinAbstract,
                     ABC):
    __slots__ = (
        "_asset_uuid_map",
    )

    def __init__(self):
        self._asset_uuid_map: Dict[str, str] = {}

    @property
    def asset_uuid_map(self) -> Dict[str, str]:
        return self._asset_uuid_map

    async def _list_one_accounts_page(self, cursor: str) -> Accounts:
        """
        List one page of accounts with maximum of 250 accounts per page.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
        """
        params = {"limit": 250}
        if cursor != "0":
            params["cursor"] = cursor

        return await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_LIST_EP,
            params=params,
            is_auth_required=True,
        )

    async def _list_trading_accounts(self) -> AsyncGenerator[AccountInfo, None]:
        has_next_page = True
        cursor = "0"

        while has_next_page:
            page: Accounts = await self._list_one_accounts_page(cursor)
            has_next_page = page["has_next"]
            cursor = page["cursor"]
            for account in page["accounts"]:
                self._asset_uuid_map[account["currency"]] = account["uuid"]
                yield account

    async def _update_balances(self):
        local_asset_names = set(self.get_balances_keys())
        remote_asset_names = set()

        async for account in self._list_trading_accounts():
            asset_name: str = account["currency"]
            self.update_balance(asset_name, Decimal(account["hold"]["value"]))
            self.update_available_balance(asset_name, Decimal(account["available_balance"]["value"]))
            remote_asset_names.add(asset_name)

        # Request removal of non-valid assets
        self.remove_balances(local_asset_names.difference(remote_asset_names))
