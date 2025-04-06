"""Model for AMMCreate transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from typing_extensions import Final, Self

from xrpl.models.amounts import Amount
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init

AMM_MAX_TRADING_FEE: Final[int] = 1000


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AMMCreate(Transaction):
    """
    Create a new Automated Market Maker (AMM) instance for trading a pair of
    assets (fungible tokens or XRP).

    Creates both an AMM object and a special AccountRoot object to represent the AMM.
    Also transfers ownership of the starting balance of both assets from the sender to
    the created AccountRoot and issues an initial balance of liquidity provider
    tokens (LP Tokens) from the AMM account to the sender.

    Caution: When you create the AMM, you should fund it with (approximately)
    equal-value amounts of each asset.
    Otherwise, other users can profit at your expense by trading with
    this AMM (performing arbitrage).
    The currency risk that liquidity providers take on increases with the
    volatility (potential for imbalance) of the asset pair.
    The higher the trading fee, the more it offsets this risk,
    so it's best to set the trading fee based on the volatility of the asset pair.
    """

    amount: Amount = REQUIRED  # type: ignore
    """
    The first of the two assets to fund this AMM with. This must be a positive amount.
    This field is required.
    """

    amount2: Amount = REQUIRED  # type: ignore
    """
    The second of the two assets to fund this AMM with. This must be a positive amount.
    This field is required.
    """

    trading_fee: int = REQUIRED  # type: ignore
    """
    The fee to charge for trades against this AMM instance, in units of 1/100,000;
    a value of 1 is equivalent to 0.001%.
    The maximum value is 1000, indicating a 1% fee.
    The minimum value is 0.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.AMM_CREATE,
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
