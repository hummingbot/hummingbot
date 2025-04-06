"""Model for a XChainClaim transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Union

from typing_extensions import Self

from xrpl.models.amounts import Amount
from xrpl.models.amounts.amount import is_issued_currency, is_mpt, is_xrp
from xrpl.models.currencies import XRP
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init
from xrpl.models.xchain_bridge import XChainBridge


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class XChainClaim(Transaction):
    """
    Represents a XChainClaim transaction.
    The ``XChainClaim`` transaction completes a cross-chain transfer of value.
    It allows a user to claim the value on the destination chain - the
    equivalent of the value locked on the source chain.
    """

    xchain_bridge: XChainBridge = REQUIRED  # type: ignore
    """
    The bridge to use for the transfer. This field is required.

    :meta hide-value:
    """

    xchain_claim_id: Union[int, str] = REQUIRED  # type: ignore
    """
    The unique integer ID for the cross-chain transfer that was referenced in
    the corresponding ``XChainCommit`` transaction. This field is required.

    :meta hide-value:
    """

    destination: str = REQUIRED  # type: ignore
    """
    The destination account on the destination chain. It must exist or the
    transaction will fail. However, if the transaction fails in this case, the
    sequence number and collected signatures won't be destroyed, and the
    transaction can be rerun with a different destination. This field is
    required.

    :meta hide-value:
    """

    destination_tag: Optional[int] = None
    """
    An integer destination tag.

    :meta hide-value:
    """

    amount: Amount = REQUIRED  # type: ignore
    """
    The amount to claim on the destination chain. This must match the amount
    attested to on the attestations associated with this ``XChainClaimID``.
    This field is required.

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default=TransactionType.XCHAIN_CLAIM,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        bridge = self.xchain_bridge

        amount = self.amount
        if is_xrp(amount):
            currency = XRP()
        elif is_issued_currency(amount):
            currency = amount.to_currency()  # type: ignore
        elif is_mpt(amount):
            currency = amount.mpt_issuance_id  # type: ignore
        else:
            errors["amount"] = "currency can't be derived."

        if (
            currency != bridge.locking_chain_issue
            and currency != bridge.issuing_chain_issue
        ):
            errors["amount"] = (
                "amount must match either locking chain issue or issuing chain issue."
            )

        return errors
