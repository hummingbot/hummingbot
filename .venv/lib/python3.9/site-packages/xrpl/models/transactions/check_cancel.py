"""Model for CheckCancel transaction type."""

from dataclasses import dataclass, field

from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class CheckCancel(Transaction):
    """
    Represents a `CheckCancel <https://xrpl.org/checkcancel.html>`_ transaction,
    which cancels an unredeemed Check, removing it from the ledger
    without sending any money. The source or the destination of the check
    can cancel a Check at any time using this transaction type. If the
    Check has expired, any address can cancel it.
    """

    check_id: str = REQUIRED  # type: ignore
    """
    The ID of the `Check ledger object
    <https://xrpl.org/check.html>`_ to cancel, as a 64-character
    hexadecimal string. This field is required.

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default=TransactionType.CHECK_CANCEL,
        init=False,
    )
