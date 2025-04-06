"""Model for CheckCreate transaction type."""

from dataclasses import dataclass, field
from typing import Optional

from xrpl.models.amounts import Amount
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class CheckCreate(Transaction):
    """
    Represents a `CheckCreate <https://xrpl.org/checkcreate.html>`_ transaction,
    which creates a Check object. A Check object is a deferred payment
    that can be cashed by its intended destination. The sender of this
    transaction is the sender of the Check.
    """

    destination: str = REQUIRED  # type: ignore
    """
    The address of the `account
    <https://xrpl.org/accounts.html>`_ that can cash the Check. This field is
    required.

    :meta hide-value:
    """

    send_max: Amount = REQUIRED  # type: ignore
    """
    Maximum amount of source token the Check is allowed to debit the
    sender, including transfer fees on non-XRP tokens. The Check can only
    credit the destination with the same token (from the same issuer, for
    non-XRP tokens). This field is required.

    :meta hide-value:
    """

    destination_tag: Optional[int] = None
    """
    An arbitrary `destination tag
    <https://xrpl.org/source-and-destination-tags.html>`_ that
    identifies the reason for the Check, or a hosted recipient to pay.
    """

    expiration: Optional[int] = None
    """
    Time after which the Check is no longer valid, in seconds since the
    Ripple Epoch.
    """

    invoice_id: Optional[str] = None
    """
    Arbitrary 256-bit hash representing a specific reason or identifier for
    this Check.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.CHECK_CREATE,
        init=False,
    )
