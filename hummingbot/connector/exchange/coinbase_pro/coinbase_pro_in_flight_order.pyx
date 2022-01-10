from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import OrderType, TradeType


cdef class CoinbaseProInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "open"):
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
        self.fee_asset = self.quote_asset

    @property
    def is_done(self) -> bool:
        return self.last_state in {"filled", "canceled", "done"}

    @property
    def is_failure(self) -> bool:
        # This is the only known canceled state
        return self.last_state == "canceled"

    @property
    def is_cancelled(self) -> bool:
        return self.last_state == "canceled"

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
            CoinbaseProInFlightOrder retval = CoinbaseProInFlightOrder(
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

    def fee_rate_from_trade_update(self, trade_update: Dict[str, Any]) -> Decimal:
        maker_fee_rate = Decimal(str(trade_update.get("maker_fee_rate", "0")))
        taker_fee_rate = Decimal(str(trade_update.get("taker_fee_rate", "0")))
        fee_rate = max(maker_fee_rate, taker_fee_rate)
        return fee_rate

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from GET /trade_history end point)
        return: True if the order gets updated otherwise False
        """
        trade_id = trade_update["trade_id"]
        if (self.exchange_order_id not in [trade_update["maker_order_id"], trade_update["taker_order_id"]]
                or trade_id in self.trade_id_set):
            return False
        self.trade_id_set.add(trade_id)
        trade_amount = Decimal(str(trade_update["size"]))
        trade_price = Decimal(str(trade_update["price"]))
        quote_amount = trade_amount * trade_price

        self.executed_amount_base += trade_amount
        self.executed_amount_quote += quote_amount
        fee_rate = self.fee_rate_from_trade_update(trade_update)
        self.fee_paid += quote_amount * fee_rate

        return True
