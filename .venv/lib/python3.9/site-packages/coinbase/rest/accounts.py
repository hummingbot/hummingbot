from typing import Any, Dict, Optional

from coinbase.constants import API_PREFIX
from coinbase.rest.types.accounts_types import GetAccountResponse, ListAccountsResponse


def get_accounts(
    self,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    retail_portfolio_id: Optional[str] = None,
    **kwargs,
) -> ListAccountsResponse:
    """
    **List Accounts**
    _________________
    [GET] https://api.coinbase.com/api/v3/brokerage/accounts

    __________

    **Description:**

    Get a list of authenticated accounts for the current user.

    __________

    **Read more on the official documentation:** `List Accounts <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getaccounts>`_

    """
    endpoint = f"{API_PREFIX}/accounts"
    params = {
        "limit": limit,
        "cursor": cursor,
        "retail_portfolio_id": retail_portfolio_id,
    }

    return ListAccountsResponse(self.get(endpoint, params=params, **kwargs))


def get_account(self, account_uuid: str, **kwargs) -> GetAccountResponse:
    """

    **Get Account**
    _______________
    [GET] https://api.coinbase.com/api/v3/brokerage/accounts/{account_uuid}

    __________

    **Description:**

    Get a list of information about an account, given an account UUID.

    __________

    **Read more on the official documentation:** `Get Account <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getaccount>`_
    """
    endpoint = f"{API_PREFIX}/accounts/{account_uuid}"

    return GetAccountResponse(self.get(endpoint, **kwargs))
