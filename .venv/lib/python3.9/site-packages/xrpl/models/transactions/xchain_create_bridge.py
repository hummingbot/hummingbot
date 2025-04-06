"""Model for a XChainCreateBridge transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.models.currencies import XRP
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init
from xrpl.models.xchain_bridge import XChainBridge


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class XChainCreateBridge(Transaction):
    """
    Represents a XChainCreateBridge transaction.
    The XChainCreateBridge transaction creates a new `Bridge` ledger object and
    defines a new cross-chain bridge entrance on the chain that the transaction
    is submitted on. It includes information about door accounts and assets for
    the bridge.
    """

    xchain_bridge: XChainBridge = REQUIRED  # type: ignore
    """
    The bridge (door accounts and assets) to create. This field is required.

    :meta hide-value:
    """

    signature_reward: str = REQUIRED  # type: ignore
    """
    The total amount to pay the witness servers for their signatures. This
    amount will be split among the signers. This field is required.

    :meta hide-value:
    """

    min_account_create_amount: Optional[str] = None
    """
    The minimum amount, in XRP, required for a ``XChainAccountCreateCommit``
    transaction. If this isn't present, the ``XChainAccountCreateCommit``
    transaction will fail. This field can only be present on XRP-XRP bridges.

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default=TransactionType.XCHAIN_CREATE_BRIDGE,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        bridge = self.xchain_bridge

        if bridge.locking_chain_door == bridge.issuing_chain_door:
            errors["xchain_bridge"] = (
                "Cannot have the same door accounts on the locking and issuing chain."
            )

        if self.account not in [bridge.locking_chain_door, bridge.issuing_chain_door]:
            errors["account"] = (
                "account must be either locking chain door or issuing chain door."
            )

        if (bridge.locking_chain_issue == XRP()) != (
            bridge.issuing_chain_issue == XRP()
        ):
            errors["issue"] = "Bridge must be XRP-XRP or IOU-IOU."

        if (
            self.min_account_create_amount is not None
            and bridge.locking_chain_issue != XRP()
        ):
            errors["min_account_create_amount"] = (
                "Cannot have MinAccountCreateAmount if bridge is IOU-IOU."
            )

        if self.signature_reward != REQUIRED and not self.signature_reward.isnumeric():
            errors["signature_reward"] = "signature_reward must be numeric."

        if (
            self.min_account_create_amount is not None
            and not self.min_account_create_amount.isnumeric()
        ):
            errors["min_account_create_amount_value"] = (
                "min_account_create_amount must be numeric."
            )

        return errors
