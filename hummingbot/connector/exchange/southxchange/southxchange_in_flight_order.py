from decimal import Decimal
from hummingbot.connector.exchange.southxchange.southxchange_utils import get_exchange_trading_pair_from_currencies
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


class SouthXchangeInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "Pending"):
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
    def is_done(self) -> bool:
        return self.last_state in {"Executed", "CanceledNotExecuted", "CanceledPartiallyExecuted"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"AmountBelowMinimum", "NotEnoughBalance", "PartiallyExecutedButNotEnoughBalance"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CanceledPartiallyExecuted", "CanceledNotExecuted", ""}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        retval = SouthXchangeInFlightOrder(
            "",
            data["Code"],
            get_exchange_trading_pair_from_currencies(data["ListingCurrency"], data["ReferenceCurrency"]),
            OrderType.MARKET,
            getattr(TradeType, str(data["Type"]).upper()),
            Decimal(data["LimitPrice"]),
            Decimal(data["Amount"]),
            data["Status"]
        )
        retval.last_state = data["Status"]
        return retval
