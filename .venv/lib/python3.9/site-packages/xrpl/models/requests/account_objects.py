"""
This request returns the raw ledger format for all objects owned by an account.

For a higher-level view of an account's trust lines and balances, see
AccountLinesRequest instead.

`See account_objects <https://xrpl.org/account_objects.html>`_
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from xrpl.models.requests.request import LookupByLedgerRequest, Request, RequestMethod
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


class AccountObjectType(str, Enum):
    """Represents the object types that an AccountObjectsRequest can ask for."""

    AMM = "amm"
    BRIDGE = "bridge"
    CHECK = "check"
    DEPOSIT_PREAUTH = "deposit_preauth"
    DID = "did"
    ESCROW = "escrow"
    MPT_ISSUANCE = "mpt_issuance"
    MPTOKEN = "mptoken"
    NFT_OFFER = "nft_offer"
    OFFER = "offer"
    ORACLE = "oracle"
    PAYMENT_CHANNEL = "payment_channel"
    SIGNER_LIST = "signer_list"
    STATE = "state"
    TICKET = "ticket"
    XCHAIN_OWNED_CREATE_ACCOUNT_CLAIM_ID = "xchain_owned_create_account_claim_id"
    XCHAIN_OWNED_CLAIM_ID = "xchain_owned_claim_id"


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AccountObjects(Request, LookupByLedgerRequest):
    """
    This request returns the raw ledger format for all objects owned by an account.

    For a higher-level view of an account's trust lines and balances, see
    AccountLinesRequest instead.

    `See account_objects <https://xrpl.org/account_objects.html>`_
    """

    account: str = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    method: RequestMethod = field(default=RequestMethod.ACCOUNT_OBJECTS, init=False)
    type: Optional[AccountObjectType] = None
    deletion_blockers_only: bool = False
    limit: Optional[int] = None
    # marker data shape is actually undefined in the spec, up to the
    # implementation of an individual server
    marker: Optional[Any] = None
