from decimal import Decimal
from typing import Protocol

from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


class ExecutorProtocol(Protocol):
    """
    Protocol defining the methods required by executor mixins.
    """
    close_type: CloseType
    _status: RunnableStatus

    @property
    def status(self) -> RunnableStatus:
        ...

    @property
    def is_closed(self):
        ...

    @property
    def net_pnl_quote(self) -> Decimal:
        ...

    @property
    def net_pnl_pct(self) -> Decimal:
        ...

    @property
    def cum_fees_quote(self) -> Decimal:
        ...

    def stop(self) -> None:
        ...

    def get_in_flight_order(self, connector_name: str, order_id: str) -> InFlightOrder:
        ...

    def place_order(
            self,
            connector_name: str,
            trading_pair: str,
            order_type: OrderType,
            side: TradeType,
            amount: Decimal,
            position_action: PositionAction = PositionAction.NIL,
            price=Decimal("NaN"),
            **kwargs,
    ) -> str:
        ...

    def get_trading_rules(self, connector_name: str, trading_pair: str) -> TradingRule:
        ...

    def adjust_order_candidates(self, exchange: str, order_candidates: list[OrderCandidate]) -> list[OrderCandidate]:
        ...
