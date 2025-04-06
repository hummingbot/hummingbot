"""Model for a XChainCommit transaction type."""

from dataclasses import dataclass, field
from typing import Optional, Union

from xrpl.models.amounts import Amount
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init
from xrpl.models.xchain_bridge import XChainBridge


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class XChainCommit(Transaction):
    """
    Represents a XChainCommit transaction.
    The `XChainCommit` transaction is the second step in a cross-chain
    transfer. It puts assets into trust on the locking chain so that they can
    be wrapped on the issuing chain, or burns wrapped assets on the issuing
    chain so that they can be returned on the locking chain.
    """

    xchain_bridge: XChainBridge = REQUIRED  # type: ignore
    """
    The bridge to use to transfer funds. This field is required.

    :meta hide-value:
    """

    xchain_claim_id: Union[int, str] = REQUIRED  # type: ignore
    """
    The unique integer ID for a cross-chain transfer. This must be acquired on
    the destination chain (via a ``XChainCreateClaimID`` transaction) and
    checked from a validated ledger before submitting this transaction. If an
    incorrect sequence number is specified, the funds will be lost. This field
    is required.

    :meta hide-value:
    """

    amount: Amount = REQUIRED  # type: ignore
    """
    The asset to commit, and the quantity. This must match the door account's
    ``LockingChainIssue`` (if on the locking chain) or the door account's
    ``IssuingChainIssue`` (if on the issuing chain). This field is required.

    :meta hide-value:
    """

    other_chain_destination: Optional[str] = None
    """
    The destination account on the destination chain. If this is not specified,
    the account that submitted the ``XChainCreateClaimID`` transaction on the
    destination chain will need to submit a ``XChainClaim`` transaction to
    claim the funds.

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default=TransactionType.XCHAIN_COMMIT,
        init=False,
    )
