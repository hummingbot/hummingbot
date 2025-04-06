"""Model for SetRegularKey transaction type."""

from dataclasses import dataclass, field
from typing import Optional

from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class SetRegularKey(Transaction):
    """
    Represents a `SetRegularKey <https://xrpl.org/setregularkey.html>`_
    transaction, which assigns, changes, or removes a secondary "regular" key pair
    associated with an account.
    """

    regular_key: Optional[str] = None
    """
    The classic address derived from the key pair to authorize for this
    account. If omitted, removes any existing regular key pair from the
    account. Must not match the account's master key pair.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.SET_REGULAR_KEY,
        init=False,
    )
