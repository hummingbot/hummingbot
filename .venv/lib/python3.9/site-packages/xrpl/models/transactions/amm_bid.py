"""Model for AMMBid transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from typing_extensions import Final, Self

from xrpl.models.amounts.issued_currency_amount import IssuedCurrencyAmount
from xrpl.models.auth_account import AuthAccount
from xrpl.models.currencies import Currency
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init

_MAX_AUTH_ACCOUNTS: Final[int] = 4


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AMMBid(Transaction):
    """
    Bid on an Automated Market Maker's (AMM's) auction slot.

    If you win, you can trade against the AMM at a discounted fee until you are outbid
    or 24 hours have passed.
    If you are outbid before 24 hours have passed, you are refunded part of the cost
    of your bid based on how much time remains.
    You bid using the AMM's LP Tokens; the amount of a winning bid is returned
    to the AMM, decreasing the outstanding balance of LP Tokens.
    """

    asset: Currency = REQUIRED  # type: ignore
    """
    The definition for one of the assets in the AMM's pool. This field is required.
    """

    asset2: Currency = REQUIRED  # type: ignore
    """
    The definition for the other asset in the AMM's pool. This field is required.
    """

    bid_min: Optional[IssuedCurrencyAmount] = None
    """
    Pay at least this LPToken amount for the slot.
    Setting this value higher makes it harder for others to outbid you.
    If omitted, pay the minimum necessary to win the bid.
    """

    bid_max: Optional[IssuedCurrencyAmount] = None
    """
    Pay at most this LPToken amount for the slot.
    If the cost to win the bid is higher than this amount, the transaction fails.
    If omitted, pay as much as necessary to win the bid.
    """

    auth_accounts: Optional[List[AuthAccount]] = None
    """
    A list of up to 4 additional accounts that you allow to trade at the discounted fee.
    This cannot include the address of the transaction sender.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.AMM_BID,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        return {
            key: value
            for key, value in {
                **super()._get_errors(),
                "auth_accounts": self._get_auth_accounts_error(),
            }.items()
            if value is not None
        }

    def _get_auth_accounts_error(self: Self) -> Optional[str]:
        if (
            self.auth_accounts is not None
            and len(self.auth_accounts) > _MAX_AUTH_ACCOUNTS
        ):
            return f"Length must not be greater than {_MAX_AUTH_ACCOUNTS}"
        return None
