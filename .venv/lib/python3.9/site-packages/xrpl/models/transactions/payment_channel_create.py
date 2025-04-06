"""Model for PaymentChannelCreate transaction type."""

from dataclasses import dataclass, field
from typing import Optional

from xrpl.models.amounts import Amount
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class PaymentChannelCreate(Transaction):
    """
    Represents a `PaymentChannelCreate
    <https://xrpl.org/paymentchannelcreate.html>`_ transaction, which creates a
    `payment channel <https://xrpl.org/payment-channels.html>`_ and funds it with
    XRP. The sender of this transaction is the "source address" of the payment
    channel.
    """

    amount: Amount = REQUIRED  # type: ignore
    """
    The amount of XRP, in drops, to set aside in this channel. This field is
    required.

    :meta hide-value:
    """

    destination: str = REQUIRED  # type: ignore
    """
    The account that can receive XRP from this channel, also known as the
    "destination address" of the channel. Cannot be the same as the sender.
    This field is required.

    :meta hide-value:
    """

    settle_delay: int = REQUIRED  # type: ignore
    """
    The amount of time, in seconds, the source address must wait between
    requesting to close the channel and fully closing it. This field is
    required.

    :meta hide-value:
    """

    public_key: str = REQUIRED  # type: ignore
    """
    The public key of the key pair that the source will use to authorize
    claims against this  channel, as hexadecimal. This can be any valid
    secp256k1 or Ed25519 public key. This field is required.

    :meta hide-value:
    """

    cancel_after: Optional[int] = None
    """
    An immutable expiration time for the channel, in seconds since the Ripple
    Epoch. The channel can be closed sooner than this but cannot remain open
    later than this time.
    """

    destination_tag: Optional[int] = None
    """
    An arbitrary `destination tag
    <https://xrpl.org/source-and-destination-tags.html>`_ that
    identifies the reason for the Payment Channel, or a hosted recipient to pay.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.PAYMENT_CHANNEL_CREATE,
        init=False,
    )
