"""Model for EscrowFinish transaction type."""

from __future__ import annotations  # Requires Python 3.7+

from dataclasses import dataclass, field
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class EscrowFinish(Transaction):
    """
    Represents an `EscrowFinish <https://xrpl.org/escrowfinish.html>`_
    transaction, delivers XRP from a held payment to the recipient.
    """

    owner: str = REQUIRED  # type: ignore
    """
    The source account that funded the Escrow. This field is required.

    :meta hide-value:
    """

    offer_sequence: int = REQUIRED  # type: ignore
    """
    Transaction sequence (or Ticket number) of the EscrowCreate transaction
    that created the Escrow. This field is required.

    :meta hide-value:
    """

    condition: Optional[str] = None
    """
    The previously-supplied `PREIMAGE-SHA-256 crypto-condition
    <https://tools.ietf.org/html/draft-thomas-crypto-conditions-04#section-8.1.>`_
    of the Escrow, if any, as hexadecimal.
    """

    fulfillment: Optional[str] = None
    """
    The `PREIMAGE-SHA-256 crypto-condition fulfillment
    <https://tools.ietf.org/html/draft-thomas-crypto-conditions-04#section-8.1.4.>`_
    matching the Escrow's condition, if any, as hexadecimal.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.ESCROW_FINISH,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if self.condition and not self.fulfillment:
            errors["fulfillment"] = (
                "If condition is specified, fulfillment must also be specified."
            )
        if self.fulfillment and not self.condition:
            errors["condition"] = (
                "If fulfillment is specified, condition must also be specified."
            )

        return errors
