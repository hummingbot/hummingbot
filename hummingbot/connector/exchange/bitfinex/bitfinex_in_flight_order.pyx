from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
)

from hummingbot.core.event.events import (
    OrderType,
    TradeType,
)
from hummingbot.connector.exchange.bitfinex import (
    OrderStatus,
)
from hummingbot.connector.exchange.bitfinex.bitfinex_utils import split_trading_pair
from hummingbot.connector.in_flight_order_base import InFlightOrderBase


cdef class BitfinexInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = OrderStatus.ACTIVE):

        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            initial_state,
        )

    @property
    def is_open(self) -> bool:
        if self.last_state.startswith("PARTIALLY"):
            return True
        return self.last_state in {OrderStatus.ACTIVE}

    @property
    def is_done(self) -> bool:
        return self.last_state in {OrderStatus.EXECUTED, OrderStatus.CANCELED}

    @property
    def is_failure(self) -> bool:
        # This is the only known canceled state
        return self.last_state == OrderStatus.CANCELED

    @property
    def is_cancelled(self) -> bool:
        return self.last_state == OrderStatus.CANCELED

    @property
    def order_type_description(self) -> str:
        """
        :return: Order description string . One of ["limit buy" / "limit sell" / "market buy" / "market sell"]
        """
        order_type = "market" if self.order_type is OrderType.MARKET else "limit"
        side = "buy" if self.trade_type == TradeType.BUY else "sell"
        return f"{order_type} {side}"

    def set_status(self, order_status: str):
        statuses = list(filter(
            lambda s: order_status.startswith(s),
            [
                OrderStatus.ACTIVE,
                OrderStatus.CANCELED,
                OrderStatus.PARTIALLY,
                OrderStatus.EXECUTED,
            ]
        ))

        if (len(statuses) < 1):
            raise Exception(f"status not found for order_status {order_status}")

        self.last_state = statuses[0]

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        cdef:
            BitfinexInFlightOrder retval = BitfinexInFlightOrder(
                data["client_order_id"],
                data["exchange_order_id"],
                data["trading_pair"],
                getattr(OrderType, data["order_type"]),
                getattr(TradeType, data["trade_type"]),
                Decimal(data["price"]),
                Decimal(data["amount"]),
                data["last_state"]
            )
        retval.executed_amount_base = Decimal(data["executed_amount_base"])
        retval.executed_amount_quote = Decimal(data["executed_amount_quote"])
        retval.fee_asset = data["fee_asset"]
        retval.fee_paid = Decimal(data["fee_paid"])
        retval.last_state = data["last_state"]
        return retval

    @property
    def base_asset(self) -> str:
        return split_trading_pair(self.trading_pair)[0]

    @property
    def quote_asset(self) -> str:
        return split_trading_pair(self.trading_pair)[1]
