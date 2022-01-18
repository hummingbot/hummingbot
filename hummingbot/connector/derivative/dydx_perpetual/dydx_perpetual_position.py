from decimal import Decimal
from typing import Optional, Union

from hummingbot.connector.derivative.position import Position
from hummingbot.core.event.events import (
    PositionSide,
    TradeType
)
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_in_flight_order import DydxPerpetualInFlightOrder


class DydxPerpetualPosition(Position):
    def __init__(self,
                 trading_pair: str,
                 position_side: PositionSide,
                 unrealized_pnl: Decimal,
                 entry_price: Decimal,
                 amount: Decimal,
                 leverage: Decimal,
                 is_open: bool = True):
        amount = abs(amount)
        if position_side == PositionSide.SHORT:
            amount = -amount
        super().__init__(
            trading_pair,
            position_side,
            unrealized_pnl,
            entry_price,
            amount,
            leverage
        )
        self.is_open = is_open

    @property
    def leverage(self):
        return round(self._leverage, 2)

    @classmethod
    def from_dydx_fill(cls,
                       in_flight_order: DydxPerpetualInFlightOrder,
                       amount: Decimal,
                       price: Decimal,
                       balance: Decimal):
        position_side = PositionSide.LONG if in_flight_order.trade_type == TradeType.BUY else PositionSide.SHORT
        quote_amount = amount * price
        leverage = quote_amount / balance
        return DydxPerpetualPosition(
            in_flight_order.trading_pair,
            position_side,
            Decimal('0'),
            price,
            amount,
            leverage,
            True)

    def update_from_fill(self,
                         in_flight_order: DydxPerpetualInFlightOrder,
                         price: Decimal,
                         amount: Decimal,
                         balance: Decimal):
        if self.position_side == PositionSide.SHORT:
            if in_flight_order.trade_type == TradeType.BUY:
                self._amount += amount
            elif in_flight_order.trade_type == TradeType.SELL:
                total_quote: Decimal = (self.entry_price * self.amount) + (price * amount)
                self._amount -= amount
                self._entry_price: Decimal = total_quote / abs(self.amount)
        elif self.position_side == PositionSide.LONG:
            if in_flight_order.trade_type == TradeType.BUY:
                total_quote: Decimal = (self.entry_price * self.amount) + (price * amount)
                self._amount += amount
                self._entry_price: Decimal = total_quote / self.amount
            elif in_flight_order.trade_type == TradeType.SELL:
                self._amount -= amount

        new_total_quote: Decimal = self.entry_price * abs(self.amount)
        self._leverage = new_total_quote / balance

    def update_position(self,
                        position_side: Optional[str] = None,
                        unrealized_pnl: Optional[Union[Decimal, str]] = None,
                        entry_price: Optional[Union[Decimal, str]] = None,
                        amount: Optional[Union[Decimal, str]] = None,
                        status: Optional[str] = None):
        if unrealized_pnl is not None:
            unrealized_pnl = Decimal(unrealized_pnl)
        if entry_price is not None:
            entry_price = Decimal(entry_price)
        if amount is not None:
            amount = Decimal(amount)
        super().update_position(position_side, unrealized_pnl, entry_price, amount)
        if status == 'CLOSED':
            self.is_open = False

    def update_from_balance(self,
                            equity: Decimal):
        total_quote = self.entry_price * abs(self.amount)
        self._leverage = total_quote / equity
