"""
This request retrieves a list of offers made by a given account that are
outstanding as of a particular ledger version.

`See account_offers <https://xrpl.org/account_offers.html>`_
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AccountOffers(Request, LookupByLedgerRequest):
    """
    This request retrieves a list of offers made by a given account that are
    outstanding as of a particular ledger version.

    `See account_offers <https://xrpl.org/account_offers.html>`_
    """

    account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    method: RequestMethod = field(default=RequestMethod.ACCOUNT_OFFERS, init=False)
    limit: Optional[int] = None
    # marker data shape is actually undefined in the spec, up to the
    # implementation of an individual server
    marker: Optional[Any] = None
    strict: bool = False
