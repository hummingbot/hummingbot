from decimal import Decimal
from typing import Optional

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.connector.in_flight_order_base import InFlightOrderBase


cdef class BeaxyInFlightOrder(InFlightOrderBase):
    def __init__(
        self,
        client_order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        order_type: OrderType,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        creation_timestamp: float,
        initial_state: str = 'new',
    ):
        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            creation_timestamp,
            initial_state,
        )

    @property
    def is_done(self) -> bool:
        return self.last_state in {'closed', 'completely_filled', 'canceled', 'cancelled', 'rejected', 'replaced', 'expired', 'pending_cancel', 'suspended', 'pending_replace'}

    @property
    def is_failure(self) -> bool:
        # This is the only known canceled state
        return self.last_state in {'canceled', 'cancelled', 'pending_cancel', 'rejected', 'expired', 'suspended'}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {'cancelled', 'canceled'}

    @property
    def order_type_description(self) -> str:
        """
        :return: Order description string . One of ['limit buy' / 'limit sell' / 'market buy' / 'market sell']
        """
        order_type = 'market' if self.order_type is OrderType.MARKET else 'limit'
        side = 'buy' if self.trade_type == TradeType.BUY else 'sell'
        return f'{order_type} {side}'
