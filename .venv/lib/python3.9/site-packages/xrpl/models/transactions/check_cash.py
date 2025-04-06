"""Model for CheckCash transaction type."""

from __future__ import annotations  # Requires Python 3.7+

from dataclasses import dataclass, field
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.models.amounts import Amount
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class CheckCash(Transaction):
    """
    Represents a `CheckCash transaction <https://xrpl.org/checkcash.html>`_,
    which redeems a Check object to receive up to the amount authorized by the
    corresponding CheckCreate transaction. Only the Destination address of a
    Check can cash it.
    """

    check_id: str = REQUIRED  # type: ignore
    """
    The ID of the `Check ledger object
    <https://xrpl.org/check.html>`_ to cash, as a 64-character
    hexadecimal string. This field is required.

    :meta hide-value:
    """

    amount: Optional[Amount] = None
    """
    Redeem the Check for exactly this amount, if possible. The currency must
    match that of the SendMax of the corresponding CheckCreate transaction.
    You must provide either this field or ``DeliverMin``.
    """

    deliver_min: Optional[Amount] = None
    """
    Redeem the Check for at least this amount and for as much as possible.
    The currency must match that of the ``SendMax`` of the corresponding
    CheckCreate transaction. You must provide either this field or ``Amount``.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.CHECK_CASH,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if not (self.amount is None) ^ (self.deliver_min is None):
            errors["CheckCash"] = (
                "either amount or deliver_min must be set but not both"
            )
        return errors
