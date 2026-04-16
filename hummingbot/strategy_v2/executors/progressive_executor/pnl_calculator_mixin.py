import math
from decimal import Decimal

from hummingbot.core.data_type.common import TradeType

from .protocols import ProgressiveOrderPNLProtocol, ProgressiveOrderProtocol

_60 = Decimal("60")
_24 = Decimal("24")
_365 = Decimal("365")


class PNLCalculatorMixin:
    """
    Provides methods and properties for calculating profit and loss (PNL) metrics.
    """

    @staticmethod
    def _realized_pnl(pop: ProgressiveOrderProtocol, side: int) -> Decimal:
        return sum(
            (o.executed_amount_base * side * (o.average_executed_price - pop.entry_price) for o in pop.realized_orders),
            start=Decimal("0"),
        )

    @staticmethod
    def _unrealized_pnl(pop: ProgressiveOrderProtocol, side: int) -> Decimal:
        return pop.unrealized_filled_amount * side * (pop.close_price - pop.entry_price)

    @property
    def trade_pnl_pct(self: ProgressiveOrderProtocol) -> Decimal:
        if self.open_filled_amount == Decimal("0"):
            return Decimal("0")
        side: int = 1 if self.side == TradeType.BUY else -1
        realized: Decimal = PNLCalculatorMixin._realized_pnl(self, side)
        unrealized: Decimal = PNLCalculatorMixin._unrealized_pnl(self, side)
        return (realized + unrealized) / (self.entry_price * self.open_filled_amount)

    @property
    def trade_pnl_quote(self: ProgressiveOrderPNLProtocol) -> Decimal:
        return self.trade_pnl_pct * self.open_filled_amount * self.entry_price

    def get_net_pnl_quote(self: ProgressiveOrderPNLProtocol) -> Decimal:
        return self.trade_pnl_quote - self.cum_fees_quote

    def get_cum_fees_quote(self: ProgressiveOrderPNLProtocol) -> Decimal:
        orders = [self.open_order, self.close_order, *self.realized_orders]
        return sum((order.cum_fees_quote for order in orders if order), start=Decimal("0"))

    def get_net_pnl_pct(self: ProgressiveOrderPNLProtocol) -> Decimal:
        return (
            self.get_net_pnl_quote() / self.open_filled_amount_quote
            if self.open_filled_amount_quote != Decimal("0")
            else Decimal("0")
        )

    def get_target_pnl_yield(self: ProgressiveOrderPNLProtocol) -> Decimal:
        time_lapsed: Decimal = Decimal(self.current_timestamp - self.config.timestamp)
        pnl: Decimal = self.config.triple_barrier_config.apr_yield * time_lapsed / (_60 * _60 * _24 * _365)
        return Decimal("0") if math.isnan(pnl) else pnl
