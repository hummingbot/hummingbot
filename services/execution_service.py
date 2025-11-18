from decimal import Decimal
from typing import Any, Optional

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.core.data_type.common import PositionAction
from services.models import ExecutionRiskLimits, OrderIntent


class ExecutionService:
    """
    Thin wrapper around connector order placement that performs minimal risk checks before submitting trades.
    """

    def __init__(self, connector: Any, risk_limits: Optional[ExecutionRiskLimits] = None):
        self._connector = connector
        self._risk_limits = risk_limits or ExecutionRiskLimits()

    async def place_order(self, intent: OrderIntent):
        self._check_limits(intent)
        price = intent.price if intent.price is not None else s_decimal_NaN
        if intent.side.lower() == "buy":
            self._connector.buy(
                trading_pair=intent.trading_pair,
                amount=intent.amount,
                order_type=intent.order_type,
                price=price,
                position_action=intent.position_action,
            )
        else:
            self._connector.sell(
                trading_pair=intent.trading_pair,
                amount=intent.amount,
                order_type=intent.order_type,
                price=price,
                position_action=intent.position_action,
            )

    def _check_limits(self, intent: OrderIntent):
        if self._risk_limits.reduce_only and intent.position_action != PositionAction.CLOSE:
            raise ValueError("Reduce-only mode is active; refusing to open new positions.")
        max_notional = self._risk_limits.max_notional
        if max_notional is not None and max_notional > Decimal("0"):
            raw_price: Optional[Decimal] = intent.price
            if raw_price is None or raw_price <= Decimal("0"):
                mid_price = self._connector.get_mid_price(intent.trading_pair)
                if mid_price is None or mid_price <= 0:
                    raise ValueError("Unable to determine price for risk checks.")
                raw_price = Decimal(str(mid_price))
            reference_price = raw_price
            notional = reference_price * intent.amount
            if notional > max_notional:
                raise ValueError(f"Order notional {notional} exceeds max allowed {max_notional}.")
