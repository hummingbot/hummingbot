"""Model for AMMDeposit transaction type."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from typing_extensions import Self

from xrpl.models.amounts import Amount, IssuedCurrencyAmount
from xrpl.models.currencies import Currency
from xrpl.models.flags import FlagInterface
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


class AMMDepositFlag(int, Enum):
    """
    Transactions of the AMMDeposit type support additional values in the Flags field.
    This enum represents those options.
    """

    TF_LP_TOKEN = 0x00010000
    TF_SINGLE_ASSET = 0x00080000
    TF_TWO_ASSET = 0x00100000
    TF_ONE_ASSET_LP_TOKEN = 0x00200000
    TF_LIMIT_LP_TOKEN = 0x00400000
    TF_TWO_ASSET_IF_EMPTY = 0x00800000


class AMMDepositFlagInterface(FlagInterface):
    """
    Transactions of the AMMDeposit type support additional values in the Flags field.
    This TypedDict represents those options.
    """

    TF_LP_TOKEN: bool
    TF_SINGLE_ASSET: bool
    TF_TWO_ASSET: bool
    TF_ONE_ASSET_LP_TOKEN: bool
    TF_LIMIT_LP_TOKEN: bool
    TF_TWO_ASSET_IF_EMPTY: bool


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AMMDeposit(Transaction):
    """
    Deposit funds into an Automated Market Maker (AMM) instance
    and receive the AMM's liquidity provider tokens (LP Tokens) in exchange.

    You can deposit one or both of the assets in the AMM's pool.
    If successful, this transaction creates a trust line to the AMM Account (limit 0)
    to hold the LP Tokens.
    """

    asset: Currency = REQUIRED  # type: ignore
    """
    The definition for one of the assets in the AMM's pool. This field is required.
    """

    asset2: Currency = REQUIRED  # type: ignore
    """
    The definition for the other asset in the AMM's pool. This field is required.
    """

    amount: Optional[Amount] = None
    """
    The amount of one asset to deposit to the AMM.
    If present, this must match the type of one of the assets (tokens or XRP)
    in the AMM's pool.
    """

    amount2: Optional[Amount] = None
    """
    The amount of another asset to add to the AMM.
    If present, this must match the type of the other asset in the AMM's pool
    and cannot be the same asset as Amount.
    """

    e_price: Optional[Amount] = None
    """
    The maximum effective price, in the deposit asset, to pay
    for each LP Token received.
    """

    lp_token_out: Optional[IssuedCurrencyAmount] = None
    """
    How many of the AMM's LP Tokens to buy.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.AMM_DEPOSIT,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if self.amount2 is not None and self.amount is None:
            errors["AMMDeposit"] = "Must set `amount` with `amount2`"
        elif self.e_price is not None and self.amount is None:
            errors["AMMDeposit"] = "Must set `amount` with `e_price`"
        elif self.lp_token_out is None and self.amount is None:
            errors["AMMDeposit"] = "Must set at least `lp_token_out` or `amount`"
        return errors
