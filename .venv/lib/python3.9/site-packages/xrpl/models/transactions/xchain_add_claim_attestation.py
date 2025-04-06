"""Model for a XChainAddClaimAttestation transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from typing_extensions import Literal

from xrpl.models.amounts import Amount
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init
from xrpl.models.xchain_bridge import XChainBridge


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class XChainAddClaimAttestation(Transaction):
    """
    Represents a XChainAddClaimAttestation transaction.
    The ``XChainAddClaimAttestation`` transaction provides proof from a witness
    server, attesting to an ``XChainCommit`` transaction.
    """

    xchain_bridge: XChainBridge = REQUIRED  # type: ignore
    """
    The bridge to use to transfer funds. This field is required.

    :meta hide-value:
    """

    public_key: str = REQUIRED  # type: ignore
    """
    The public key used to verify the signature. This field is required.

    :meta hide-value:
    """

    signature: str = REQUIRED  # type: ignore
    """
    The signature attesting to the event on the other chain. This field is
    required.

    :meta hide-value:
    """

    other_chain_source: str = REQUIRED  # type: ignore
    """
    The account on the source chain that submitted the ``XChainCommit``
    transaction that triggered the event associated with the attestation. This
    field is required.

    :meta hide-value:
    """

    amount: Amount = REQUIRED  # type: ignore
    """
    The amount committed by the ``XChainCommit`` transaction on the source
    chain. This field is required.

    :meta hide-value:
    """

    attestation_reward_account: str = REQUIRED  # type: ignore
    """
    The account that should receive this signer's share of the
    ``SignatureReward``. This field is required.

    :meta hide-value:
    """

    attestation_signer_account: str = REQUIRED  # type: ignore
    """
    The account on the door account's signer list that is signing the
    transaction. This field is required.

    :meta hide-value:
    """

    was_locking_chain_send: Union[Literal[0], Literal[1]] = REQUIRED  # type: ignore
    """
    A boolean representing the chain where the event occurred. This field is
    required.

    :meta hide-value:
    """

    xchain_claim_id: Union[str, int] = REQUIRED  # type: ignore
    """
    The ``XChainClaimID`` associated with the transfer, which was included in
    the ``XChainCommit`` transaction. This field is required.

    :meta hide-value:
    """

    destination: Optional[str] = None
    """
    The destination account for the funds on the destination chain (taken from
    the ``XChainCommit`` transaction).

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default=TransactionType.XCHAIN_ADD_CLAIM_ATTESTATION,
        init=False,
    )
