"""Model for a XChainCreateClaimID transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from typing_extensions import Self

from xrpl.core.addresscodec import is_valid_classic_address
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init
from xrpl.models.xchain_bridge import XChainBridge


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class XChainCreateClaimID(Transaction):
    """
    Represents a XChainCreateClaimID transaction.
    The XChainCreateClaimID transaction creates a new cross-chain claim ID that
    is used for a cross-chain transfer. A cross-chain claim ID represents one
    cross-chain transfer of value.
    """

    xchain_bridge: XChainBridge = REQUIRED  # type: ignore
    """
    The bridge to create the claim ID for. This field is required.

    :meta hide-value:
    """

    signature_reward: str = REQUIRED  # type: ignore
    """
    The amount, in XRP, to reward the witness servers for providing signatures.
    This must match the amount on the ``Bridge`` ledger object. This field is
    required.

    :meta hide-value:
    """

    other_chain_source: str = REQUIRED  # type: ignore
    """
    The account that must send the corresponding ``XChainCommit`` transaction
    on the source chain. This field is required.

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default=TransactionType.XCHAIN_CREATE_CLAIM_ID,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        if self.signature_reward != REQUIRED and not self.signature_reward.isnumeric():
            errors["signature_reward"] = "`signature_reward` must be numeric."

        if self.other_chain_source != REQUIRED and not is_valid_classic_address(
            self.other_chain_source
        ):
            errors["other_chain_source"] = (
                "`other_chain_source` must be a valid XRPL address."
            )

        return errors
