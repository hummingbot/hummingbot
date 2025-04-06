"""Model for NFTokenCancelOffer transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from typing_extensions import Self

from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class NFTokenCancelOffer(Transaction):
    """
    The NFTokenCancelOffer transaction deletes existing NFTokenOffer objects.
    It is useful if you want to free up space on your account to lower your
    reserve requirement.

    The transaction can be executed by the account that originally created
    the NFTokenOffer, the account in the `Recipient` field of the NFTokenOffer
    (if present), or any account if the NFTokenOffer has an `Expiration` and
    the NFTokenOffer has already expired.
    """

    nftoken_offers: List[str] = REQUIRED  # type: ignore
    """
    An array of identifiers of NFTokenOffer objects that should be cancelled
    by this transaction.

    It is an error if an entry in this list points to an
    object that is not an NFTokenOffer object. It is not an
    error if an entry in this list points to an object that
    does not exist. This field is required.

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default=TransactionType.NFTOKEN_CANCEL_OFFER,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        return {
            key: value
            for key, value in {
                **super()._get_errors(),
                "nftoken_offers": self._get_nftoken_offers_error(),
            }.items()
            if value is not None
        }

    def _get_nftoken_offers_error(self: Self) -> Optional[str]:
        if len(self.nftoken_offers) < 1:
            return "Must specify at least one NFTokenOffer to cancel"
        return None
