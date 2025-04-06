"""
The ripple_path_find method is a simplified version of the
path_find method that provides a single response with a payment
path you can use right away. It is available in both the WebSocket
and JSON-RPC APIs. However, the results tend to become outdated as
time passes. Instead of making multiple calls to stay updated, you
should instead use the path_find method to subscribe to continued
updates where possible.

Although the rippled server tries to find the cheapest path or
combination of paths for making a payment, it is not guaranteed that
the paths returned by this method are, in fact, the best paths.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from xrpl.models.amounts import Amount
from xrpl.models.currencies import Currency
from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class RipplePathFind(Request, LookupByLedgerRequest):
    """
    The ripple_path_find method is a simplified version of the
    path_find method that provides a single response with a payment
    path you can use right away. It is available in both the WebSocket
    and JSON-RPC APIs. However, the results tend to become outdated as
    time passes. Instead of making multiple calls to stay updated, you
    should instead use the path_find method to subscribe to continued
    updates where possible.

    Although the rippled server tries to find the cheapest path or
    combination of paths for making a payment, it is not guaranteed that
    the paths returned by this method are, in fact, the best paths.
    """

    source_account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    destination_account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    destination_amount: Amount = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    method: RequestMethod = field(default=RequestMethod.RIPPLE_PATH_FIND, init=False)
    send_max: Optional[Amount] = None
    source_currencies: Optional[List[Currency]] = None
