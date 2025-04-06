"""Model for DepositPreauth transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class DepositPreauth(Transaction):
    """
    Represents a `DepositPreauth <https://xrpl.org/depositpreauth.html>`_
    transaction, which gives another account pre-approval to deliver payments to
    the sender of this transaction, if this account is using
    `Deposit Authorization <https://xrpl.org/depositauth.html>`_.
    """

    authorize: Optional[str] = None
    """
    Grant preauthorization to this address. You must provide this OR
    ``unauthorize`` but not both.
    """

    unauthorize: Optional[str] = None
    """
    Revoke preauthorization from this address. You must provide this OR
    ``authorize`` but not both.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.DEPOSIT_PREAUTH,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if self.authorize and self.unauthorize:
            errors["DepositPreauth"] = (
                "One of authorize and unauthorize must be set, not both."
            )

        if not self.authorize and not self.unauthorize:
            errors["DepositPreauth"] = "One of authorize and unauthorize must be set."

        return errors
