"""Model for a XChainAccountCreateCommit transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from typing_extensions import Self

from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init
from xrpl.models.xchain_bridge import XChainBridge


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class XChainAccountCreateCommit(Transaction):
    """
    Represents a XChainAccountCreateCommit transaction on the XRP Ledger.
    The XChainAccountCreateCommit transaction creates a new account on one of
    the chains a bridge connects, which serves as the bridge entrance for that
    chain.
    """

    xchain_bridge: XChainBridge = REQUIRED  # type: ignore
    """
    The bridge to create accounts for. This field is required.

    :meta hide-value:
    """

    signature_reward: str = REQUIRED  # type: ignore
    """
    The amount, in XRP, to be used to reward the witness servers for providing
    signatures. This must match the amount on the ``Bridge`` ledger object. This
    field is required.

    :meta hide-value:
    """

    destination: str = REQUIRED  # type: ignore
    """
    The destination account on the destination chain. This field is required.

    :meta hide-value:
    """

    amount: str = REQUIRED  # type: ignore
    """
    The amount, in XRP, to use for account creation. This must be greater than
    or equal to the ``MinAccountCreateAmount`` specified in the ``Bridge``
    ledger object. This field is required.

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default=TransactionType.XCHAIN_ACCOUNT_CREATE_COMMIT,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        if self.signature_reward != REQUIRED and not self.signature_reward.isnumeric():
            errors["signature_reward"] = "`signature_reward` must be numeric."

        if self.amount != REQUIRED and not self.amount.isnumeric():
            errors["amount"] = "`amount` must be numeric."

        return errors
