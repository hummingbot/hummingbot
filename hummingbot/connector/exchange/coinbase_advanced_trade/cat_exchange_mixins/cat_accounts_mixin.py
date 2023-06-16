from typing import AsyncGenerator, Dict, Iterable, Set

from _decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeAccount,
    CoinbaseAdvancedTradeListAccountsResponse,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    CoinbaseAdvancedTradeAccountsMixinProtocol,
    CoinbaseAdvancedTradeAPICallsMixinProtocol,
)


class _BalanceProtocol(CoinbaseAdvancedTradeAccountsMixinProtocol):
    async def _list_trading_accounts(self) -> AsyncGenerator[CoinbaseAdvancedTradeAccount, None]:
        ...


class CoinbaseAdvancedTradeAccountsMixin:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._asset_uuid_map: Dict[str, str] = {}

    @property
    def asset_uuid_map(self) -> Dict[str, str]:
        return self._asset_uuid_map

    def get_balances_keys(self: CoinbaseAdvancedTradeAccountsMixinProtocol) -> Set[str]:
        return set(self._account_balances.keys())

    def remove_balances(self: CoinbaseAdvancedTradeAccountsMixinProtocol, assets: Iterable[str]):
        for asset in assets:
            self._account_balances.pop(asset, None)
            self._account_available_balances.pop(asset, None)

    def update_balance(self: CoinbaseAdvancedTradeAccountsMixinProtocol, asset: str, balance: Decimal):
        self._account_balances[asset] = balance

    def update_available_balance(self: CoinbaseAdvancedTradeAccountsMixinProtocol, asset: str, balance: Decimal):
        self._account_available_balances[asset] = balance

    async def _list_one_page_of_accounts(self: CoinbaseAdvancedTradeAPICallsMixinProtocol,
                                         cursor: str) -> CoinbaseAdvancedTradeListAccountsResponse:
        """
        List one page of accounts with maximum of 250 accounts per page.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
        """
        params = {"limit": 250}
        if cursor != "0":
            params["cursor"] = cursor

        return CoinbaseAdvancedTradeListAccountsResponse(**(await self.api_get(
            path_url=CONSTANTS.ACCOUNTS_LIST_EP,
            params=params,
            is_auth_required=True,
        )))

    async def _list_trading_accounts(self) -> AsyncGenerator[CoinbaseAdvancedTradeAccount, None]:
        has_next_page = True
        cursor = "0"

        while has_next_page:
            page: CoinbaseAdvancedTradeListAccountsResponse = await self._list_one_page_of_accounts(cursor)
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
