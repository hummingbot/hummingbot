from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)
import asyncio
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.connector.in_flight_order_base import InFlightOrderBase

NEW_LOCAL_STATUS = "NewLocal"


class AscendExInFlightOrder(InFlightOrderBase):

    @staticmethod
    def is_open_status(status: str) -> bool:
        # PendingNew is for stop orders
        return status in {"New", "PendingNew", "PartiallyFilled"}

    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = NEW_LOCAL_STATUS):
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
        self.trade_id_set = set()
        self.cancelled_event = asyncio.Event()

    @property
    def is_locally_new(self) -> bool:
        return self.last_state == NEW_LOCAL_STATUS

    @property
    def is_open(self) -> bool:
        return AscendExInFlightOrder.is_open_status(self.last_state)

    @property
    def is_done(self) -> bool:
        return self.last_state in {"Filled", "Canceled", "Rejected"}

    @property
    def is_filled(self) -> bool:
        return self.last_state == "Filled"

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"Rejected"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"Canceled"}

    def update_status(self, new_status: str):
        if new_status not in {"New", "PendingNew", "Filled", "PartiallyFilled", "Canceled", "Rejected"}:
            raise Exception(f"Invalid order status: {new_status}")
        self.last_state = new_status

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        retval = AscendExInFlightOrder(
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
