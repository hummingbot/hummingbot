"""Types used by the parser."""

from typing import List

from typing_extensions import Literal, NotRequired, TypedDict


class Balance(TypedDict):
    """A account's balance model."""

    currency: str
    """The currency code."""

    value: str
    """The amount of the currency."""

    issuer: NotRequired[str]
    """The issuer of the currency. This value is optional."""


class AccountBalance(TypedDict):
    """A single account balance."""

    account: str
    """The affected account."""
    balance: Balance
    """The balance."""


class AccountBalances(TypedDict):
    """A model representing an account's balances."""

    account: str
    balances: List[Balance]


class CurrencyAmount(Balance):
    """A currency amount model. Has the same fields as `Balance`"""

    pass


class OfferChange(TypedDict):
    """A single offer change."""

    flags: int
    taker_gets: CurrencyAmount
    taker_pays: CurrencyAmount
    sequence: int
    status: Literal["created", "partially-filled", "filled", "cancelled"]
    maker_exchange_rate: str
    expiration_time: NotRequired[int]


class AccountOfferChange(TypedDict):
    """A model representing an account's offer change."""

    maker_account: str
    offer_change: OfferChange


class AccountOfferChanges(TypedDict):
    """A model representing an account's offer changes."""

    maker_account: str
    offer_changes: List[OfferChange]
