"""Model for MPTokenIssuanceDestroy transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field

from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True)
class MPTokenIssuanceDestroy(Transaction):
    """
    The MPTokenIssuanceDestroy transaction is used to remove an MPTokenIssuance object
    from the directory node in which it is being held, effectively removing the token
    from the ledger. If this operation succeeds, the corresponding
    MPTokenIssuance is removed and the owner’s reserve requirement is reduced by one.
    This operation must fail if there are any holders who have non-zero balances.
    """

    mptoken_issuance_id: str = REQUIRED  # type: ignore
    """Identifies the MPTokenIssuance object to be removed by the transaction."""

    transaction_type: TransactionType = field(
        default=TransactionType.MPTOKEN_ISSUANCE_DESTROY,
        init=False,
    )
