from decimal import Decimal
from typing import List, Optional
import warnings

from hummingbot.client.config.trade_fee_schema_loader import TradeFeeSchemaLoader
from hummingbot.core.data_type.trade_fee import (
    TradeFeeBase,
    TokenAmount,
    TradeFeeSchema
)
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType


def build_trade_fee(
    exchange: str,
    is_maker: bool,
    base_currency: str,
    quote_currency: str,
    order_type: OrderType,
    order_side: TradeType,
    amount: Decimal,
    price: Decimal = Decimal("NaN"),
    extra_flat_fees: Optional[List[TokenAmount]] = None,
) -> TradeFeeBase:
    """
    WARNING: Do not use this method for order sizing. Use the `BudgetChecker` instead.

    Uses the exchange's `TradeFeeSchema` to build a `TradeFee`, given the trade parameters.
    """
    trade_fee_schema: TradeFeeSchema = TradeFeeSchemaLoader.configured_schema_for_exchange(exchange_name=exchange)
    fee_percent: Decimal = (
        trade_fee_schema.maker_percent_fee_decimal
        if is_maker
        else trade_fee_schema.taker_percent_fee_decimal
    )
    fixed_fees: List[TokenAmount] = (
        trade_fee_schema.maker_fixed_fees
        if is_maker
        else trade_fee_schema.taker_fixed_fees
    ).copy()
    if extra_flat_fees is not None and len(extra_flat_fees) > 0:
        fixed_fees = fixed_fees + extra_flat_fees
    trade_fee: TradeFeeBase = TradeFeeBase.new_spot_fee(
        fee_schema=trade_fee_schema,
        trade_type=order_side,
        percent=fee_percent,
        percent_token=trade_fee_schema.percent_fee_token,
        flat_fees=fixed_fees
    )
    return trade_fee


def build_perpetual_trade_fee(
    exchange: str,
    is_maker: bool,
    position_action: PositionAction,
    base_currency: str,
    quote_currency: str,
    order_type: OrderType,
    order_side: TradeType,
    amount: Decimal,
    price: Decimal = Decimal("NaN"),
) -> TradeFeeBase:
    """
    WARNING: Do not use this method for order sizing. Use the `BudgetChecker` instead.

    Uses the exchange's `TradeFeeSchema` to build a `TradeFee`, given the trade parameters.
    """
    trade_fee_schema = TradeFeeSchemaLoader.configured_schema_for_exchange(exchange_name=exchange)
    percent = trade_fee_schema.maker_percent_fee_decimal if is_maker else trade_fee_schema.taker_percent_fee_decimal
    fixed_fees = trade_fee_schema.maker_fixed_fees if is_maker else trade_fee_schema.taker_fixed_fees
    trade_fee = TradeFeeBase.new_perpetual_fee(
        fee_schema=trade_fee_schema,
        position_action=position_action,
        percent=percent,
        percent_token=trade_fee_schema.percent_fee_token,
        flat_fees=fixed_fees)
    return trade_fee


def estimate_fee(exchange: str, is_maker: bool) -> TradeFeeBase:
    """
    WARNING: This method is deprecated and remains only for backward compatibility.
    Use `build_trade_fee` and `build_perpetual_trade_fee` instead.

    Estimate the fee of a transaction on any blockchain.
    exchange is the name of the exchange to query.
    is_maker if true look at fee from maker side, otherwise from taker side.
    """
    warnings.warn(
        "The 'estimate_fee' method is deprecated, use 'build_trade_fee' and 'build_perpetual_trade_fee' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    trade_fee = build_trade_fee(
        exchange,
        is_maker,
        base_currency="",
        quote_currency="",
        order_type=OrderType.LIMIT,
        order_side=TradeType.BUY,
        amount=Decimal("0"),
        price=Decimal("0"),
    )
    return trade_fee
