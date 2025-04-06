"""Model for AMMVote transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.models.currencies import Currency
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.amm_create import AMM_MAX_TRADING_FEE
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AMMVote(Transaction):
    """
    Vote on the trading fee for an Automated Market Maker (AMM) instance.

    Up to 8 accounts can vote in proportion to the amount of the AMM's LP Tokens
    they hold.
    Each new vote re-calculates the AMM's trading fee based on a weighted average
    of the votes.
    """

    asset: Currency = REQUIRED  # type: ignore
    """
    The definition for one of the assets in the AMM's pool. This field is required.
    """

    asset2: Currency = REQUIRED  # type: ignore
    """
    The definition for the other asset in the AMM's pool. This field is required.
    """

    trading_fee: int = REQUIRED  # type: ignore
    """
    The proposed fee to vote for, in units of 1/100,000; a value of 1 is equivalent
    to 0.001%.
    The maximum value is 1000, indicating a 1% fee. This field is required.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.AMM_VOTE,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        return {
            key: value
            for key, value in {
                **super()._get_errors(),
                "trading_fee": self._get_trading_fee_error(),
            }.items()
            if value is not None
        }

    def _get_trading_fee_error(self: Self) -> Optional[str]:
        if self.trading_fee < 0 or self.trading_fee > AMM_MAX_TRADING_FEE:
            return f"Must be between 0 and {AMM_MAX_TRADING_FEE}"
        return None
