from hummingbot.logger import HummingbotLogger
import logging

from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
    Set
)

from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.connector.in_flight_order_base import InFlightOrderBase

s_decimal_0 = Decimal(0)

_eifo_logger: Optional[HummingbotLogger] = None

cdef class EterbaseInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 cost: Optional[Decimal],
                 initial_state: str = "open",
                 fill_ids: Set[str] = set()):
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
        self.fill_ids = fill_ids
        self.cost = cost
        self.executed_cost_quote = s_decimal_0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _eifo_logger
        if _eifo_logger is None:
            _eifo_logger = logging.getLogger(__name__)
        return _eifo_logger

    @property
    def is_done(self) -> bool:
        return self.last_state in {"FILLED",
                                   "USER_REQUESTED_CANCEL",
                                   "ADMINISTRATIVE_CANCEL",
                                   "NOT_ENOUGH_LIQUIDITY",
                                   "EXPIRED",
                                   "ONE_CANCELS_OTHER",
                                   "4"}

    @property
    def is_failure(self) -> bool:
        # This is the only known canceled state
        return self.last_state in {"NOT_ENOUGH_LIQUIDITY"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state == {"USER_REQUESTED_CANCEL", "ADMINISTRATIVE_CANCEL", "ONE_CANCELS_OTHER"}

    @property
    def order_type_description(self) -> str:
        """
        :return: Order description string . One of ["limit buy" / "limit sell" / "market buy" / "market sell"]
        """
        order_type = "limit_maker" if self.order_type is OrderType.LIMIT_MAKER else "limit"
        side = "buy" if self.trade_type == TradeType.BUY else "sell"
        return f"{order_type} {side}"

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        cdef:
            EterbaseInFlightOrder retval = EterbaseInFlightOrder(
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

        if ("cost" in data):
            retval.cost = data["cost"]
        return retval

    def __repr__(self) -> str:
        return super().__repr__() + \
            f".EterbaseExtension(" \
            f"fill_ids='{self.fill_ids}', " \
            f"cost='{self.cost}')"
