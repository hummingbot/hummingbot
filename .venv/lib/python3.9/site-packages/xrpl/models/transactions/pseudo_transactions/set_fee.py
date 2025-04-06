"""Model for SetFee pseudo-transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from xrpl.models.transactions.pseudo_transactions.pseudo_transaction import (
    PseudoTransaction,
)
from xrpl.models.transactions.types import PseudoTransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class SetFee(PseudoTransaction):
    """
    A SetFee pseudo-transaction marks a change in `transaction cost
    <https://xrpl.org/transaction-cost.html>`_ or `reserve requirements
    <https://xrpl.org/reserves.html>`_ as a result of `Fee Voting
    <https://xrpl.org/fee-voting.html>`_.

    The parameters are different depending on if this is before or after the
    `XRPFees Amendment<https://xrpl.org/known-amendments.html#xrpfees>`_

    Before the XRPFees Amendment which was proposed in rippled 1.10.0
    base_fee, reference_fee_units, reserve_base, and reserve_increment
    were required fields.

    After the XRPFees Amendment, base_fee_drops, reserve_base_drops,
    and reserve_increment_drops are required fields.

    No SetFee Pseudo Transaction should contain fields from BOTH before
    and after the XRPFees amendment.
    """

    # Required BEFORE the XRPFees Amendment

    base_fee: Optional[str] = None
    """
    The charge, in drops of XRP, for the reference transaction, as hex. (This is the
    transaction cost before scaling for load.) This field is required.

    :meta hide-value:
    """

    reference_fee_units: Optional[int] = None
    """
    The cost, in fee units, of the reference transaction. This field is required.

    :meta hide-value:
    """

    reserve_base: Optional[int] = None
    """
    The base reserve, in drops. This field is required.

    :meta hide-value:
    """

    reserve_increment: Optional[int] = None
    """
    The incremental reserve, in drops. This field is required.

    :meta hide-value:
    """

    # Required AFTER the XRPFees Amendment

    base_fee_drops: Optional[str] = None
    """
    The charge, in drops of XRP, for the reference transaction, as hex. (This is the
    transaction cost before scaling for load.) This field is required.

    :meta hide-value:
    """

    reserve_base_drops: Optional[str] = None
    """
    The base reserve, in drops. This field is required.

    :meta hide-value:
    """

    reserve_increment_drops: Optional[str] = None
    """
    The incremental reserve, in drops. This field is required.

    :meta hide-value:
    """

    transaction_type: PseudoTransactionType = field(
        default=PseudoTransactionType.SET_FEE,
        init=False,
    )
