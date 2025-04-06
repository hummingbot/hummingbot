"""Model for MPTokenAuthorize transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from xrpl.models.flags import FlagInterface
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import require_kwargs_on_init


class MPTokenAuthorizeFlag(int, Enum):
    """
    Transactions of the MPTokenAuthorize type support additional values in the
    Flags field.
    This enum represents those options.
    """

    TF_MPT_UNAUTHORIZE = 0x00000001
    """
    If set and transaction is submitted by a holder, it indicates that the holder no
    longer wants to hold the MPToken, which will be deleted as a result. If the holder's
    MPToken has non-zero balance while trying to set this flag, the transaction will
    fail. On the other hand, if set and transaction is submitted by an issuer, it would
    mean that the issuer wants to unauthorize the holder (only applicable for
    allow-listing), which would unset the lsfMPTAuthorized flag on the MPToken.
    """


class MPTokenAuthorizeFlagInterface(FlagInterface):
    """
    Transactions of the MPTokenAuthorize type support additional values in the
    Flags field.
    This TypedDict represents those options.
    """

    TF_MPT_UNAUTHORIZE: bool


@require_kwargs_on_init
@dataclass(frozen=True)
class MPTokenAuthorize(Transaction):
    """
    The MPTokenAuthorize transaction is used to globally lock/unlock a MPTokenIssuance,
    or lock/unlock an individual's MPToken.
    """

    mptoken_issuance_id: str = REQUIRED  # type: ignore
    """Identifies the MPTokenIssuance"""

    holder: Optional[str] = None
    """
    An optional XRPL Address of an individual token holder balance to lock/unlock.
    If omitted, this transaction will apply to all any accounts holding MPTs.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.MPTOKEN_AUTHORIZE,
        init=False,
    )
