"""Model for a XChainModifyBridge transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.models.currencies import XRP
from xrpl.models.flags import FlagInterface
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init
from xrpl.models.xchain_bridge import XChainBridge


class XChainModifyBridgeFlag(int, Enum):
    """
    Transactions of the XChainModifyBridge type support additional values in the Flags
    field. This enum represents those options.
    """

    TF_CLEAR_ACCOUNT_CREATE_AMOUNT = 0x00010000


class XChainModifyBridgeFlagInterface(FlagInterface):
    """
    Transactions of the XChainModifyBridge type support additional values in the Flags
    field. This TypedDict represents those options.
    """

    TF_CLEAR_ACCOUNT_CREATE_AMOUNT: bool


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class XChainModifyBridge(Transaction):
    """
    Represents a XChainModifyBridge transaction.
    The XChainModifyBridge transaction allows bridge managers to modify the
    parameters of the bridge.
    """

    xchain_bridge: XChainBridge = REQUIRED  # type: ignore
    """
    The bridge to modify. This field is required.

    :meta hide-value:
    """

    signature_reward: Optional[str] = None
    """
    The signature reward split between the witnesses for submitting
    attestations.

    :meta hide-value:
    """

    min_account_create_amount: Optional[str] = None
    """
    The minimum amount, in XRP, required for a ``XChainAccountCreateCommit``
    transaction. If this is not present, the ``XChainAccountCreateCommit``
    transaction will fail. This field can only be present on XRP-XRP bridges.

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default=TransactionType.XCHAIN_MODIFY_BRIDGE,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        bridge = self.xchain_bridge

        if (
            self.signature_reward is None
            and self.min_account_create_amount is None
            and not self.has_flag(XChainModifyBridgeFlag.TF_CLEAR_ACCOUNT_CREATE_AMOUNT)
        ):
            errors["xchain_modify_bridge"] = (
                "Must either change signature_reward, change "
                + "min_account_create_amount, or clear min_account_create_amount."
            )

        if self.account not in [bridge.locking_chain_door, bridge.issuing_chain_door]:
            errors["account"] = (
                "account must be either locking chain door or issuing chain door."
            )

        if self.signature_reward is not None and not self.signature_reward.isnumeric():
            errors["signature_reward"] = "`signature_reward` must be numeric."

        if (
            self.min_account_create_amount is not None
            and bridge.locking_chain_issue != XRP()
        ):
            errors["min_account_create_amount"] = (
                "Cannot have MinAccountCreateAmount if bridge is IOU-IOU."
            )

        if (
            self.min_account_create_amount is not None
            and not self.min_account_create_amount.isnumeric()
        ):
            errors["min_account_create_amount_value"] = (
                "`min_account_create_amount` must be numeric."
            )

        return errors
