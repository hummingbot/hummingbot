"""
Represents a TrustSet transaction on the XRP Ledger.
Creates or modifies a trust line linking two accounts.

`See TrustSet <https://xrpl.org/trustset.html>`_
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.flags import FlagInterface
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


class TrustSetFlag(int, Enum):
    """
    Transactions of the TrustSet type support additional values in the Flags field.
    This enum represents those options.
    """

    TF_SET_AUTH = 0x00010000
    """
    Authorize the other party to hold
    `currency issued by this account <https://xrpl.org/tokens.html>`_.
    (No effect unless using the `asfRequireAuth AccountSet flag
    <https://xrpl.org/accountset.html#accountset-flags>`_.) Cannot be unset.
    """

    TF_SET_NO_RIPPLE = 0x00020000
    """
    Enable the No Ripple flag, which blocks
    `rippling <https://xrpl.org/rippling.html>`_ between two trust
    lines of the same currency if this flag is enabled on both.
    """

    TF_CLEAR_NO_RIPPLE = 0x00040000
    """Disable the No Ripple flag, allowing rippling on this trust line."""

    TF_SET_FREEZE = 0x00100000
    """Freeze the trust line."""

    TF_CLEAR_FREEZE = 0x00200000
    """Unfreeze the trust line."""


class TrustSetFlagInterface(FlagInterface):
    """
    Transactions of the TrustSet type support additional values in the Flags field.
    This TypedDict represents those options.
    """

    TF_SET_AUTH: bool
    TF_SET_NO_RIPPLE: bool
    TF_CLEAR_NO_RIPPLE: bool
    TF_SET_FREEZE: bool
    TF_CLEAR_FREEZE: bool


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class TrustSet(Transaction):
    """
    Represents a TrustSet transaction on the XRP Ledger.
    Creates or modifies a trust line linking two accounts.

    `See TrustSet <https://xrpl.org/trustset.html>`_
    """

    limit_amount: IssuedCurrencyAmount = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    quality_in: Optional[int] = None

    quality_out: Optional[int] = None

    transaction_type: TransactionType = field(
        default=TransactionType.TRUST_SET,
        init=False,
    )
