"""Model for MPTokenIssuanceCreate transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.constants import HEX_REGEX
from xrpl.models.flags import FlagInterface
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import require_kwargs_on_init


class MPTokenIssuanceCreateFlag(int, Enum):
    """
    Transactions of the MPTokenIssuanceCreate type support additional values in the
    Flags field.
    This enum represents those options.
    """

    TF_MPT_CAN_LOCK = 0x00000002
    TF_MPT_REQUIRE_AUTH = 0x00000004
    TF_MPT_CAN_ESCROW = 0x00000008
    TF_MPT_CAN_TRADE = 0x00000010
    TF_MPT_CAN_TRANSFER = 0x00000020
    TF_MPT_CAN_CLAWBACK = 0x00000040


class MPTokenIssuanceCreateFlagInterface(FlagInterface):
    """
    Transactions of the MPTokenIssuanceCreate type support additional values in the
    Flags field.
    This TypedDict represents those options.
    """

    TF_MPT_CAN_LOCK: bool
    TF_MPT_REQUIRE_AUTH: bool
    TF_MPT_CAN_ESCROW: bool
    TF_MPT_CAN_TRADE: bool
    TF_MPT_CAN_TRANSFER: bool
    TF_MPT_CAN_CLAWBACK: bool


@require_kwargs_on_init
@dataclass(frozen=True)
class MPTokenIssuanceCreate(Transaction):
    """
    The MPTokenIssuanceCreate transaction creates a MPTokenIssuance object
    and adds it to the relevant directory node of the creator account.
    This transaction is the only opportunity an issuer has to specify any token fields
    that are defined as immutable (e.g., MPT Flags). If the transaction is successful,
    the newly created token will be owned by the account (the creator account) which
    executed the transaction.
    """

    asset_scale: Optional[int] = None
    """
    An asset scale is the difference, in orders of magnitude, between a standard unit
    and a corresponding fractional unit. More formally, the asset scale is a
    non-negative integer (0, 1, 2, …) such that one standard unit equals 10^(-scale) of
    a corresponding fractional unit. If the fractional unit equals the standard unit,
    then the asset scale is 0.
    Note that this value is optional, and will default to 0 if not supplied.
    """

    maximum_amount: Optional[str] = None
    """
    Specifies the hex-encoded maximum asset amount of this token that should ever be
    issued. It is a non-negative integer that can store a range of up to 63 bits. If
    not set, the max amount will default to the largest unsigned 63-bit integer
    (0x7FFFFFFFFFFFFFFF)
    """

    transfer_fee: Optional[int] = None
    """
    Specifies the fee to charged by the issuer for secondary sales of the Token,
    if such sales are allowed. Valid values for this field are between 0 and 50,000
    inclusive, allowing transfer rates of between 0.000% and 50.000% in increments of
    0.001. The field must NOT be present if the `tfMPTCanTransfer` flag is not set.
    """

    mptoken_metadata: Optional[str] = None
    """
    Specifies the hex-encoded maximum asset amount of this token that should ever be
    issued. It is a non-negative integer that can store a range of up to 63 bits. If
    not set, the max amount will default to the largest unsigned 63-bit integer
    (0x7FFFFFFFFFFFFFFF)
    """

    transaction_type: TransactionType = field(
        default=TransactionType.MPTOKEN_ISSUANCE_CREATE,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        if self.mptoken_metadata is not None:
            if len(self.mptoken_metadata) == 0:
                errors["mptoken_metadata"] = "Field must not be empty string."
            elif bool(HEX_REGEX.fullmatch(self.mptoken_metadata)) is False:
                errors["mptoken_metadata"] = "Field must be in hex format."

        return errors
