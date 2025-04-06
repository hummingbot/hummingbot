"""
The `nfts_by_issuer` method retrieves all of the NFTokens
issued by an account
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True)
class NFTsByIssuer(Request, LookupByLedgerRequest):
    """
    The `nfts_by_issuer` method retrieves all of the NFTokens
    issued by an account
    """

    method: RequestMethod = field(default=RequestMethod.NFTS_BY_ISSUER, init=False)
    issuer: str = REQUIRED  # type: ignore
    """
    The unique identifier for an account that issues NFTokens
    The request returns NFTokens issued by this account. This field is required

    :meta hide-value:
    """

    marker: Optional[Any] = None
    nft_taxon: Optional[int] = None
    limit: Optional[int] = None
