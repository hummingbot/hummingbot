"""
This request retrieves a list of currencies that an account can send or receive,
based on its trust lines.

This is not a thoroughly confirmed list, but it can be used to populate user
interfaces.

`See account_currencies <https://xrpl.org/account_currencies.html>`_
"""

from dataclasses import dataclass, field

from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AccountCurrencies(Request, LookupByLedgerRequest):
    """
    This request retrieves a list of currencies that an account can send or receive,
    based on its trust lines.

    This is not a thoroughly confirmed list, but it can be used to populate user
    interfaces.

    `See account_currencies <https://xrpl.org/account_currencies.html>`_
    """

    account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """
    method: RequestMethod = field(default=RequestMethod.ACCOUNT_CURRENCIES, init=False)
    strict: bool = False
