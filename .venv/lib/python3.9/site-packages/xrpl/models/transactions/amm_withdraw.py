"""Model for AMMWithdraw transaction type."""

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


class AMMWithdrawFlag(int, Enum):
    """
    Transactions of the AMMWithdraw type support additional values in the Flags field.
    This enum represents those options.
    """

    TF_LP_TOKEN = 0x00010000
    TF_WITHDRAW_ALL = 0x00020000
    TF_ONE_ASSET_WITHDRAW_ALL = 0x00040000
    TF_SINGLE_ASSET = 0x00080000
    TF_TWO_ASSET = 0x00100000
    TF_ONE_ASSET_LP_TOKEN = 0x00200000
    TF_LIMIT_LP_TOKEN = 0x00400000


class AMMWithdrawFlagInterface(FlagInterface):
    """
    Transactions of the AMMWithdraw type support additional values in the Flags field.
    This TypedDict represents those options.
    """

    TF_LP_TOKEN: bool
    TF_WITHDRAW_ALL: bool
    TF_ONE_ASSET_WITHDRAW_ALL: bool
    TF_SINGLE_ASSET: bool
    TF_TWO_ASSET: bool
    TF_ONE_ASSET_LP_TOKEN: bool
    TF_LIMIT_LP_TOKEN: bool


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class AMMWithdraw(Transaction):
    """
    Withdraw assets from an Automated Market Maker (AMM) instance by returning the
    AMM's liquidity provider tokens (LP Tokens).
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
    The amount of one asset to withdraw from the AMM.
    This must match the type of one of the assets (tokens or XRP) in the AMM's pool.
    """

    amount2: Optional[Amount] = None
    """
    The amount of another asset to withdraw from the AMM.
    If present, this must match the type of the other asset in the AMM's pool
    and cannot be the same type as Amount.
    """

    e_price: Optional[Amount] = None
    """
    The minimum effective price, in LP Token returned, to pay per unit of the asset
    to withdraw.
    """

    lp_token_in: Optional[IssuedCurrencyAmount] = None
    """
    How many of the AMM's LP Tokens to redeem.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.AMM_WITHDRAW,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()
        if self.amount2 is not None and self.amount is None:
            errors["AMMWithdraw"] = "Must set `amount` with `amount2`"
        elif self.e_price is not None and self.amount is None:
            errors["AMMWithdraw"] = "Must set `amount` with `e_price`"
        return errors
