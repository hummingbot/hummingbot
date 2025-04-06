"""
The `nft_history` method retreives a list of transactions that involved the
specified NFToken.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class NFTHistory(Request, LookupByLedgerRequest):
    """
    The `nft_history` method retreives a list of transactions that involved the
    specified NFToken.
    """

    method: RequestMethod = field(default=RequestMethod.NFT_HISTORY, init=False)
    nft_id: str = REQUIRED  # type: ignore
    """
    The unique identifier of an NFToken.
    The request returns past transactions of this NFToken. This value is required.

    :meta hide-value:
    """

    ledger_index_min: Optional[int] = None
    ledger_index_max: Optional[int] = None
    binary: bool = False
    forward: bool = False
    limit: Optional[int] = None
    # marker data shape is actually undefined in the spec, up to the
    # implementation of an individual server
    marker: Optional[Any] = None
