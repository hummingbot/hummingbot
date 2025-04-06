"""Model for a PaymentChannelFund transaction type."""

from dataclasses import dataclass, field
from typing import Optional

from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class PaymentChannelFund(Transaction):
    """
    Represents a `PaymentChannelFund <https://xrpl.org/paymentchannelfund.html>`_
    transaction, adds additional XRP to an open `payment channel
    <https://xrpl.org/payment-channels.html>`_, and optionally updates the
    expiration time of the channel. Only the source address
    of the channel can use this transaction.
    """

    channel: str = REQUIRED  # type: ignore
    """
    The unique ID of the payment channel, as a 64-character hexadecimal
    string. This field is required.

    :meta hide-value:
    """

    amount: str = REQUIRED  # type: ignore
    """
    The amount of XRP, in drops, to add to the channel. This field is
    required.

    :meta hide-value:
    """

    expiration: Optional[int] = None
    """
    A new mutable expiration time to set for the channel, in seconds since the
    Ripple Epoch. This must be later than the existing expiration time of the
    channel or later than the current time plus the settle delay of the channel.
    This is separate from the immutable ``cancel_after`` time.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.PAYMENT_CHANNEL_FUND,
        init=False,
    )
