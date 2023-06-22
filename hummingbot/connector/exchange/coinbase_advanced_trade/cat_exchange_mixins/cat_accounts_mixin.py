from typing import AsyncGenerator, Dict, Iterable, Set

from _decimal import Decimal

from ..cat_data_types.cat_api_v3_endpoints import CoinbaseAdvancedTradeAPIEndpoint as _APIEndpoint
from ..cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeAccount as _Account,
    CoinbaseAdvancedTradeListAccountsResponse as _ListAccountsResponse,
)
from .cat_exchange_protocols import (
    CoinbaseAdvancedTradeAccountsMixinProtocol as _AccountsPtcl,
    CoinbaseAdvancedTradeAPICallsMixinProtocol as _APICallsPtcl,
)


class _BalanceProtocol(_AccountsPtcl):
    async def _list_trading_accounts(self) -> AsyncGenerator[_Account, None]:
        ...


class CoinbaseAdvancedTradeAccountsMixin:
    def __init__(self, **kwargs):
        if super().__class__ is not object:
            super().__init__(**kwargs)
        self._asset_uuid_map: Dict[str, str] = {}

    @property
    def asset_uuid_map(self) -> Dict[str, str]:
        return self._asset_uuid_map

    def get_balances_keys(self: _AccountsPtcl) -> Set[str]:
        return set(self._account_balances.keys())

    def remove_balances(self: _AccountsPtcl, assets: Iterable[str]):
        for asset in assets:
            self._account_balances.pop(asset, None)
            self._account_available_balances.pop(asset, None)

    def update_balance(self: _AccountsPtcl, asset: str, balance: Decimal):
        self._account_balances[asset] = balance

    def update_available_balance(self: _AccountsPtcl, asset: str, balance: Decimal):
        self._account_available_balances[asset] = balance

    async def _list_one_page_of_accounts(self: _APICallsPtcl, cursor: str) -> _ListAccountsResponse:
        """
        List one page of accounts with maximum of 250 accounts per page.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
        """
        params = {"limit": 250}
        if cursor != "0":
            params["cursor"] = cursor
        resp: _ListAccountsResponse = await _APIEndpoint(self, "ListAccounts", **params).execute()
        return resp
        # return CoinbaseAdvancedTradeListAccountsResponse(**(await self.api_get(
        #     path_url=CONSTANTS.ACCOUNTS_LIST_EP,
        #     params=params,
        #     is_auth_required=True,
        # )))

    async def _list_trading_accounts(self) -> AsyncGenerator[_Account, None]:
        has_next_page = True
        cursor = "0"

        while has_next_page:
            page: _ListAccountsResponse = await self._list_one_page_of_accounts(cursor)
            has_next_page = page.has_next
            cursor = page.cursor
            for account in page.accounts:
                self._asset_uuid_map[account.currency] = account.uuid
                yield account

    async def _update_balances(self: _BalanceProtocol):
        local_asset_names = set(self.get_balances_keys())
        remote_asset_names = set()

        async for account in self._list_trading_accounts():  # type: ignore # Known Pycharm issue
            asset_name: str = account.currency
            self.update_balance(asset_name, Decimal(account.hold.value))
            self.update_available_balance(asset_name, Decimal(account.available_balance.value))
            remote_asset_names.add(asset_name)

        # Request removal of non-valid assets
        self.remove_balances(local_asset_names.difference(remote_asset_names))
