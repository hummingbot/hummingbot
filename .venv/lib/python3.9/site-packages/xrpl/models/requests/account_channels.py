"""
This request returns information about an account's Payment Channels. This includes
only channels where the specified account is the channel's source, not the
destination. (A channel's "source" and "owner" are the same.)

All information retrieved is relative to a particular version of the ledger.

`See account_channels <https://xrpl.org/account_channels.html>`_
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AccountChannels(Request, LookupByLedgerRequest):
    """
    This request returns information about an account's Payment Channels. This includes
    only channels where the specified account is the channel's source, not the
    destination. (A channel's "source" and "owner" are the same.)

    All information retrieved is relative to a particular version of the ledger.

    `See account_channels <https://xrpl.org/account_channels.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.ACCOUNT_CHANNELS, init=False)
    account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    destination_account: Optional[str] = None
    limit: int = 200
    # marker data shape is actually undefined in the spec, up to the
    # implementation of an individual server
    marker: Optional[Any] = None
