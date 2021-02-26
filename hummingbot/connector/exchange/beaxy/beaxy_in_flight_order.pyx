# -*- coding: utf-8 -*-

from decimal import Decimal
from typing import Any, Dict, Optional
from datetime import datetime

from hummingbot.core.event.events import OrderType, TradeType
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
