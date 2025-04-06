"""Model for Clawback transaction type and related flags."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Union

from typing_extensions import Self

from xrpl.models.amounts import (
    IssuedCurrencyAmount,
    MPTAmount,
    is_issued_currency,
    is_xrp,
)
from xrpl.models.amounts.amount import is_mpt
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Clawback(Transaction):
    """The clawback transaction claws back issued funds from token holders."""

    amount: Union[IssuedCurrencyAmount, MPTAmount] = REQUIRED  # type: ignore
    """
    The amount of currency to claw back. The issuer field is used for the token holder's
    address, from whom the tokens will be clawed back.

    :meta hide-value:
    """

    holder: Optional[str] = None
    """
    Indicates the AccountID that the issuer wants to clawback. This field is only valid
    for clawing back MPTs.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.CLAWBACK,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        # Amount transaction errors
        if is_xrp(self.amount):
            errors["amount"] = "``amount`` cannot be XRP."

        if is_issued_currency(self.amount):
            if self.holder is not None:
                errors["amount"] = "Cannot have Holder for currency."
            if self.account == self.amount.issuer:  # type:ignore
                errors["amount"] = "Holder's address is wrong."

        if is_mpt(self.amount):
            if self.holder is None:
                errors["amount"] = "Missing Holder."
            if self.account == self.holder:
                errors["amount"] = "Invalid Holder account."

        return errors
