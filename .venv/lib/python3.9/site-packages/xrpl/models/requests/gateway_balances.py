"""
This request calculates the total balances issued by a given account, optionally
excluding amounts held by operational addresses.

`See gateway_balances <https://xrpl.org/gateway_balances.html>`_
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union

from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class GatewayBalances(Request, LookupByLedgerRequest):
    """
    This request calculates the total balances issued by a given account, optionally
    excluding amounts held by operational addresses.

    `See gateway_balances <https://xrpl.org/gateway_balances.html>`_
    """

    account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    method: RequestMethod = field(default=RequestMethod.GATEWAY_BALANCES, init=False)
    strict: bool = False
    hotwallet: Optional[Union[str, List[str]]] = None
