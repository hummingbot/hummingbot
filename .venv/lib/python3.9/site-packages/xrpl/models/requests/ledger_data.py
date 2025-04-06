"""
The ledger_data method retrieves contents of
the specified ledger. You can iterate through
several calls to retrieve the entire contents
of a single ledger version.
`See ledger data <https://xrpl.org/ledger_data.html>`_
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from xrpl.models.requests.ledger_entry import LedgerEntryType
from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class LedgerData(Request, LookupByLedgerRequest):
    """
    The ledger_data method retrieves contents of
    the specified ledger. You can iterate through
    several calls to retrieve the entire contents
    of a single ledger version.
    `See ledger data <https://xrpl.org/ledger_data.html>`_
    """

    method: RequestMethod = field(default=RequestMethod.LEDGER_DATA, init=False)
    binary: bool = False
    limit: Optional[int] = None
    # marker data shape is actually undefined in the spec, up to the
    # implementation of an individual server
    marker: Optional[Any] = None
    type: Optional[LedgerEntryType] = None
