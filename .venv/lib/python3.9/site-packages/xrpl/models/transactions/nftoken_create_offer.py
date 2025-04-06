"""Model for NFTokenCreateOffer transaction type and related flag."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.models.amounts import Amount, get_amount_value
from xrpl.models.flags import FlagInterface
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


class NFTokenCreateOfferFlag(int, Enum):
    """Transaction Flags for an NFTokenCreateOffer Transaction."""

    TF_SELL_NFTOKEN = 0x00000001
    """
    If set, indicates that the offer is a sell offer.
    Otherwise, it is a buy offer.
    """


class NFTokenCreateOfferFlagInterface(FlagInterface):
    """Transaction Flags for an NFTokenCreateOffer Transaction."""

    TF_SELL_NFTOKEN: bool


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class NFTokenCreateOffer(Transaction):
    """
    The NFTokenCreateOffer transaction creates either an offer to buy an
    NFT the submitting account does not own, or an offer to sell an NFT
    the submitting account does own.
    """

    nftoken_id: str = REQUIRED  # type: ignore
    """
    Identifies the TokenID of the NFToken object that the
    offer references. This field is required.

    :meta hide-value:
    """

    amount: Amount = REQUIRED  # type: ignore
    """
    Indicates the amount expected or offered for the Token.

    The amount must be non-zero, except when this is a sell
    offer and the asset is XRP. This would indicate that the current
    owner of the token is giving it away free, either to anyone at all,
    or to the account identified by the Destination field. This field
    is required.

    :meta hide-value:
    """

    owner: Optional[str] = None
    """
    Indicates the AccountID of the account that owns the
    corresponding NFToken.

    If the offer is to buy a token, this field must be present
    and it must be different than Account (since an offer to
    buy a token one already holds is meaningless).

    If the offer is to sell a token, this field must not be
    present, as the owner is, implicitly, the same as Account
    (since an offer to sell a token one doesn't already hold
    is meaningless).
    """

    expiration: Optional[int] = None
    """
    Indicates the time after which the offer will no longer
    be valid. The value is the number of seconds since the
    Ripple Epoch.
    """

    destination: Optional[str] = None
    """
    If present, indicates that this offer may only be
    accepted by the specified account. Attempts by other
    accounts to accept this offer MUST fail.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.NFTOKEN_CREATE_OFFER,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        return {
            key: value
            for key, value in {
                **super()._get_errors(),
                "amount": self._get_amount_error(),
                "destination": self._get_destination_error(),
                "owner": self._get_owner_error(),
            }.items()
            if value is not None
        }

    def _get_amount_error(self: Self) -> Optional[str]:
        if (
            not self.has_flag(NFTokenCreateOfferFlag.TF_SELL_NFTOKEN)
            and get_amount_value(self.amount) <= 0
        ):
            return "Must be greater than 0 for a buy offer"
        return None

    def _get_destination_error(self: Self) -> Optional[str]:
        if self.destination == self.account:
            return "Must not be equal to the account"
        return None

    def _get_owner_error(self: Self) -> Optional[str]:
        if (
            not self.has_flag(NFTokenCreateOfferFlag.TF_SELL_NFTOKEN)
            and self.owner is None
        ):
            return "Must be present for buy offers"
        if (
            self.has_flag(NFTokenCreateOfferFlag.TF_SELL_NFTOKEN)
            and self.owner is not None
        ):
            return "Must not be present for sell offers"
        if self.owner == self.account:
            return "Must not be equal to the account"
        return None
