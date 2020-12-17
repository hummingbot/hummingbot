import copy
import json
import time
from typing import (Any, Dict, List, Tuple)
from decimal import Decimal
from hummingbot.connector.exchange.dydx.dydx_order_status import DydxOrderStatus
from hummingbot.connector.exchange.dydx.dydx_fill_report import DydxFillReport
from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase
from hummingbot.connector.exchange.dydx.dydx_exchange cimport DydxExchange
from hummingbot.core.event.events import (OrderFilledEvent, TradeType, OrderType, TradeFee, MarketEvent)


cdef class DydxInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 market: DydxExchange,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: DydxOrderStatus,
                 filled_size: Decimal,
                 filled_volume: Decimal,
                 filled_fee: Decimal,
                 created_at: int,):

        super().__init__(client_order_id=client_order_id,
                         exchange_order_id=exchange_order_id,
                         trading_pair=trading_pair,
                         order_type=order_type,
                         trade_type=trade_type,
                         price=price,
                         amount=amount,
                         initial_state = str(initial_state))
        self.market = market
        self.status = initial_state
        self.created_at = created_at
        self._last_executed_amount_from_order_status = Decimal(0)
        self.executed_amount_base = filled_size
        self.executed_amount_quote = filled_volume
        self.fee_paid = filled_fee
        self.fills = set()
        self._queued_events = []
        self._queued_fill_events = []
        self._completion_sent = False
        self._cancel_before_eoid_set = False

        (base, quote) = self.market.split_trading_pair(trading_pair)
        self.fee_asset = base if trade_type is TradeType.BUY else quote
        self.reserved_asset = quote if trade_type is TradeType.BUY else base

    @property
    def is_done(self) -> bool:
        return self.status >= DydxOrderStatus.done

    @property
    def is_cancelled(self) -> bool:
        return self.status in [DydxOrderStatus.CANCELED, DydxOrderStatus.expired]

    @property
    def is_failure(self) -> bool:
        return self.status >= DydxOrderStatus.failed

    @property
    def description(self):
        return f"{str(self.order_type).lower()} {str(self.trade_type).lower()}"

    @property
    def amount_remaining(self):
        return self.amount - self.executed_amount_base

    @property
    def reserved_balance(self):
        if self.trade_type is TradeType.SELL:
            return self.amount_remaining
        else:
            return self.amount_remaining * self.price

    @property
    def cancel_before_eoid_set(self):
        return self._cancel_before_eoid_set

    def to_json(self):
        return json.dumps({
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "trading_pair": self.trading_pair,
            "order_type": self.order_type.name,
            "trade_type": self.trade_type.name,
            "price": str(self.price),
            "amount": str(self.amount),
            "status": self.status.name,
            "executed_amount_base": str(self.executed_amount_base),
            "executed_amount_quote": str(self.executed_amount_quote),
            "fee_paid": str(self.fee_paid),
            "created_at": self.created_at,
            "fills": [f.as_dict() for f in self.fills],
            "_last_executed_amount_from_order_status": str(self._last_executed_amount_from_order_status),
        })

    @classmethod
    def from_json(cls, market, data: Dict[str, Any]) -> DydxInFlightOrder:
        order = DydxInFlightOrder(
            market,
            data["client_order_id"],
            data["exchange_order_id"],
            data["trading_pair"],
            OrderType[data["order_type"]],
            TradeType[data["trade_type"]],
            Decimal(data["price"]),
            Decimal(data["amount"]),
            DydxOrderStatus[data["status"]],
            Decimal(data["executed_amount_base"]),
            Decimal(data["executed_amount_quote"]),
            Decimal(data["fee_paid"]),
            data["created_at"]
        )
        for fill in data["fills"]:
            order.fills.add(DydxFillReport(fill['id'], Decimal(fill['amount']), Decimal(fill['price']), Decimal(fill['fee'])))
        order._last_executed_amount_from_order_status = Decimal(data['_last_executed_amount_from_order_status'])

        return order

    @classmethod
    def from_dydx_order(cls,
                        market: DydxExchange,
                        side: TradeType,
                        client_order_id: str,
                        order_type: OrderType,
                        created_at: int,
                        hash: str,
                        trading_pair: str,
                        price: Decimal,
                        amount: Decimal) -> DydxInFlightOrder:
        return DydxInFlightOrder(
            market,
            client_order_id,
            hash,
            trading_pair,
            order_type,
            side,
            price,
            amount,
            DydxOrderStatus.PENDING,
            Decimal(0),
            Decimal(0),
            Decimal(0),
            created_at
        )

    def fills_covered(self) -> bool:
        return self.executed_amount_base == self._last_executed_amount_from_order_status

    def _enqueue_completion_event(self):
        if (not self._completion_sent and
                self.status is DydxOrderStatus.FILLED and
                self.executed_amount_base == self.amount and
                self.executed_amount_base == self._last_executed_amount_from_order_status):
            self._queued_events.append((MarketEvent.BuyOrderCompleted if self.trade_type is TradeType.BUY else MarketEvent.SellOrderCompleted,
                                        self.executed_amount_base,
                                        self.executed_amount_quote,
                                        self.fee_paid))
            self._completion_sent = True

    def register_fill(self, id: str, amount: Decimal, price: Decimal, fee: Decimal):
        fill_ids = [fill.as_dict()["id"] for fill in self.fills]
        if id not in fill_ids:
            report = DydxFillReport(id, amount, price, fee)
            self.fills.add(report)
            self.executed_amount_base += report.amount
            self.executed_amount_quote += report.value
            self.fee_paid += fee * (report.amount if self.trade_type is TradeType.BUY else report.value)

            # enqueue the relevent events caused by this fill report
            self._queued_fill_events.append((MarketEvent.OrderFilled, amount, price, fee))
            self._enqueue_completion_event()

    def get_issuable_events(self) -> List[Any]:
        # We can always issue our fill events
        events: List[Any] = self._queued_fill_events.copy()
        self._queued_fill_events.clear()

        if self.executed_amount_base >= self._last_executed_amount_from_order_status:
            # We have all the fill reports up to our observed order status, so we can issue all
            # order status update related events.
            events.extend(self._queued_events)
            self._queued_events.clear()

        return events

    def cancel_attempted_before_eoid_set(self):
        self._cancel_before_eoid_set = True

    def update(self, data: Dict[str, Any]) -> List[Any]:
        base: str
        quote: str
        trading_pair: str = data["market"]
        (base, quote) = self.market.split_trading_pair(trading_pair)
        base_id: int = self.market.token_configuration.get_tokenid(base)

        new_status: DydxOrderStatus = DydxOrderStatus[data["status"]]
        new_executed_amount_base: Decimal = self.market.token_configuration.unpad(data["filledAmount"], base_id)

        if not self.is_done and new_status == DydxOrderStatus.CANCELED:
            reason = data.get('cancelReason')
            if reason is None and reason == "EXPIRED":
                self._queued_events.append((MarketEvent.OrderExpired, None, None, None))
                new_status = DydxOrderStatus.expired
            elif reason is None and reason in ["UNDERCOLLATERALIZED", "FAILED"]:
                self._queued_events.append((MarketEvent.OrderFailure, None, None, None))
                new_status = DydxOrderStatus.failed
            else:
                self._queued_events.append((MarketEvent.OrderCancelled, None, None, None))

        self.status = new_status
        self.last_state = str(new_status)
        self._last_executed_amount_from_order_status = new_executed_amount_base

        # check and enqueue our completion event if it is time to do so
        self._enqueue_completion_event()

        if self.exchange_order_id is None:
            self.update_exchange_order_id(data.get('hash', None))
