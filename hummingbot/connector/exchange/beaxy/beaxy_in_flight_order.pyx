import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.logger import HummingbotLogger

s_logger = None


cdef class BeaxyInFlightOrder(InFlightOrderBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(
        self,
        client_order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        order_type: OrderType,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        created_at: datetime,
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
            initial_state
        )
        self.created_at = created_at
        self.trade_id_set = set()

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

    def to_json(self) -> Dict[str, Any]:
        return dict(
            created_at=self.created_at.isoformat(),
            **super(BeaxyInFlightOrder, self).to_json()
        )

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        cdef:
            BeaxyInFlightOrder retval = BeaxyInFlightOrder(
                data['client_order_id'],
                data['exchange_order_id'],
                data['trading_pair'],
                getattr(OrderType, data['order_type']),
                getattr(TradeType, data['trade_type']),
                Decimal(data['price']),
                Decimal(data['amount']),
                datetime.fromisoformat(data['created_at']),
                data['last_state'],
            )
        retval.executed_amount_base = Decimal(data['executed_amount_base'])
        retval.executed_amount_quote = Decimal(data['executed_amount_quote'])
        retval.fee_asset = data['fee_asset']
        retval.fee_paid = Decimal(data['fee_paid'])
        retval.last_state = data['last_state']
        return retval

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from GET /trade_history end point)
        :param trade_update: the event message received for the order fill (or trade event)
        In the case of beaxy it is the same order update event
        :return: True if the order gets updated otherwise False
        """
        trade_id = trade_update["timestamp"]
        if (str(trade_update["order_id"]) != self.exchange_order_id
                or trade_id in self.trade_id_set
                or trade_update["trade_size"] is None
                or trade_update["trade_price"] is None
                or Decimal(trade_update["filled_size"]) <= self.executed_amount_base):
            return False

        self.trade_id_set.add(trade_id)
        trade_amount = Decimal(str(trade_update["trade_size"]))
        trade_price = Decimal(str(trade_update["trade_price"]))
        quote_amount = trade_amount * trade_price

        self.executed_amount_base += trade_amount
        self.executed_amount_quote += quote_amount

        if trade_update["commission"]:
            self.fee_paid += Decimal(str(trade_update["commission"]))
            self.fee_asset = trade_update["commission_currency"]

        return True
