"""Model for EnableAmendment pseudo-transaction type."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union

from xrpl.models.flags import FlagInterface
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.pseudo_transactions.pseudo_transaction import (
    PseudoTransaction,
)
from xrpl.models.transactions.types import PseudoTransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


class EnableAmendmentFlag(int, Enum):
    """
    The Flags value of the EnableAmendment pseudo-transaction indicates the status of
    the amendment at the time of the ledger including the pseudo-transaction.

    A Flags value of 0 (no flags) or an omitted Flags field indicates that the
    amendment has been enabled, and applies to all ledgers afterward.

    `See EnableAmendment Flags
    <https://xrpl.org/enableamendment.html#enableamendment-flags>`_
    """

    TF_GOT_MAJORITY = 0x00010000
    """
    Support for this amendment increased to at least 80% of trusted validators
    starting with this ledger version.
    """

    TF_LOST_MAJORITY = 0x00020000
    """
    Support for this amendment decreased to less than 80% of trusted validators
    starting with this ledger version.
    """


class EnableAmendmentFlagInterface(FlagInterface):
    """
    The Flags value of the EnableAmendment pseudo-transaction indicates the status of
    the amendment at the time of the ledger including the pseudo-transaction.

    A Flags value of 0 (no flags) or an omitted Flags field indicates that the
    amendment has been enabled, and applies to all ledgers afterward.

    `See EnableAmendment Flags
    <https://xrpl.org/enableamendment.html#enableamendment-flags>`_
    """

    TF_GOT_MAJORITY: bool
    TF_LOST_MAJORITY: bool


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class EnableAmendment(PseudoTransaction):
    """
    An EnableAmendment pseudo-transaction marks a change in status of an amendment to
    the XRP Ledger protocol, including:

    * A proposed amendment gained supermajority approval from validators.
    * A proposed amendment lost supermajority approval.
    * A proposed amendment has been enabled.
    """

    amendment: str = REQUIRED  # type: ignore
    """
    A unique identifier for the amendment. This is not intended to be a
    human-readable name. See `Amendments <https://xrpl.org/amendments.html>`_ for a
    list of known amendments. This field is required.

    :meta hide-value:
    """

    ledger_sequence: int = REQUIRED  # type: ignore
    """
    The ledger index where this pseudo-transaction appears. This distinguishes the
    pseudo-transaction from other occurrences of the same change.
    This field is required.

    :meta hide-value:
    """

    tf_got_majority: Optional[bool] = None
    """
    Support for this amendment increased to at least 80% of trusted validators
    starting with this ledger version.
    """

    tf_lost_majority: Optional[bool] = None
    """
    Support for this amendment decreased to less than 80% of trusted validators
    starting with this ledger version.
    """

    transaction_type: PseudoTransactionType = field(
        default=PseudoTransactionType.ENABLE_AMENDMENT,
        init=False,
    )

    flags: Union[int, List[int]] = 0
    """
    The Flags value of the EnableAmendment pseudo-transaction indicates the status
    of the amendment at the time of the ledger including the pseudo-transaction.
    A Flags value of 0 (no flags) or an omitted Flags field indicates that the
    amendment has been enabled, and applies to all ledgers afterward.
    """
