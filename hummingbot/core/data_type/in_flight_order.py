import asyncio
import copy
import math

from async_timeout import timeout
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, NamedTuple, Optional, Tuple

from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.events import AddedToCostTradeFee, OrderType, PositionAction, TradeType

s_decimal_0 = Decimal("0")

GET_EX_ORDER_ID_TIMEOUT = 10  # seconds


class OrderState(Enum):
    PENDING_CREATE = 0
    OPEN = 1
    PENDING_CANCEL = 2
    CANCELLED = 3
    PARTIALLY_FILLED = 4
    FILLED = 5
    FAILED = 6


class OrderUpdate(NamedTuple):
    trading_pair: str
    update_timestamp: int  # milliseconds
    new_state: OrderState
    client_order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    trade_id: Optional[str] = None
    fill_price: Optional[Decimal] = None  # If None, defaults to order price
    executed_amount_base: Optional[Decimal] = None
    executed_amount_quote: Optional[Decimal] = None
    fee_asset: Optional[str] = None
    cumulative_fee_paid: Optional[Decimal] = None
    trade_fee_percent: Optional[Decimal] = None


class TradeUpdate(NamedTuple):
    trade_id: str
    client_order_id: str
    exchange_order_id: str
    trading_pair: str
    fill_timestamp: int
    fill_price: Decimal
    fill_base_amount: Decimal
    fill_quote_amount: Decimal
    fee_asset: str
    fee_paid: Optional[Decimal] = None
    trade_fee_percent: Optional[Decimal] = None


class InFlightOrder:
    def __init__(
        self,
        client_order_id: str,
        trading_pair: str,
        order_type: OrderType,
        trade_type: TradeType,
        amount: Decimal,
        price: Optional[Decimal] = None,
        exchange_order_id: Optional[str] = None,
        initial_state: OrderState = OrderState.PENDING_CREATE,
        leverage: int = 1,
        position: PositionAction = PositionAction.NIL,
        trade_fee_percent: Decimal = None,
        timestamp: int = -1,
    ) -> None:
        self.client_order_id = client_order_id
        self.trading_pair = trading_pair
        self.order_type = order_type
        self.trade_type = trade_type
        self.price = price
        self.amount = amount
        self.exchange_order_id = exchange_order_id
        self.current_state = initial_state
        self.leverage = leverage
        self.position = position
        self.trade_fee_percent = trade_fee_percent

        self.executed_amount_base = s_decimal_0
        self.executed_amount_quote = s_decimal_0
        self.fee_asset = None
        self.cumulative_fee_paid = s_decimal_0

        self.last_filled_price: Decimal = s_decimal_0
        self.last_filled_amount: Decimal = s_decimal_0  # in base asset
        self.last_fee_paid: Decimal = s_decimal_0
        self.last_update_timestamp: int = timestamp
        self.last_trade_id = -1

        self.order_fills: Dict[str, TradeUpdate] = {}  # Dict[trade_id, TradeUpdate]

        self.exchange_order_id_update_event = asyncio.Event()
        if self.exchange_order_id:
            self.exchange_order_id_update_event.set()

    @property
    def attributes(self) -> Tuple[Any]:
        return copy.deepcopy(
            (
                self.client_order_id,
                self.trading_pair,
                self.order_type,
                self.trade_type,
                self.price,
                self.amount,
                self.exchange_order_id,
                self.current_state,
                self.leverage,
                self.position,
                self.fee_asset,
                self.cumulative_fee_paid,
                self.executed_amount_base,
                self.executed_amount_quote,
                self.last_filled_price,
                self.last_filled_amount,
                self.last_fee_paid,
                self.last_update_timestamp,
            )
        )

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self.attributes == other.attributes

    @property
    def base_asset(self):
        return self.trading_pair.split("-")[0]

    @property
    def quote_asset(self):
        return self.trading_pair.split("-")[1]

    @property
    def is_pending_create(self) -> bool:
        return self.current_state == OrderState.PENDING_CREATE

    @property
    def is_pending_cancel_confirmation(self) -> bool:
        return self.current_state == OrderState.PENDING_CANCEL

    @property
    def is_open(self) -> bool:
        return self.current_state in {OrderState.PENDING_CREATE, OrderState.OPEN, OrderState.PARTIALLY_FILLED}

    @property
    def is_done(self) -> bool:
        return (
            self.current_state in {OrderState.CANCELLED, OrderState.FILLED, OrderState.FAILED}
            or math.isclose(self.executed_amount_base, self.amount)
            or self.executed_amount_base >= self.amount
        )

    @property
    def is_filled(self) -> bool:
        return (
            self.current_state == OrderState.FILLED
            or (self.amount != s_decimal_0
                and (math.isclose(self.executed_amount_base, self.amount)
                     or self.executed_amount_base >= self.amount)
                )
        )

    @property
    def is_failure(self) -> bool:
        return self.current_state == OrderState.FAILED

    @property
    def is_cancelled(self) -> bool:
        return self.current_state == OrderState.CANCELLED

    @property
    def average_executed_price(self) -> Optional[Decimal]:
        executed_value: Decimal = s_decimal_0
        total_base_amount: Decimal = s_decimal_0
        for order_fill in self.order_fills.values():
            executed_value += order_fill.fill_price * order_fill.fill_base_amount
            total_base_amount += order_fill.fill_base_amount
        if executed_value == s_decimal_0 or total_base_amount == s_decimal_0:
            return None
        return executed_value / total_base_amount

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "InFlightOrder":
        """
        Initialize an InFlightOrder using a JSON object
        :param data: JSON data
        :return: Formatted InFlightOrder
        """
        retval = InFlightOrder(
            client_order_id=data["client_order_id"],
            trading_pair=data["trading_pair"],
            order_type=getattr(OrderType, data["order_type"]),
            trade_type=getattr(TradeType, data["trade_type"]),
            amount=Decimal(data["amount"]),
            price=Decimal(data["price"]),
            exchange_order_id=data["exchange_order_id"],
            initial_state=OrderState(int(data["last_state"])),
            leverage=int(data["leverage"]),
            position=PositionAction(data["position"]),
        )
        retval.executed_amount_base = Decimal(data["executed_amount_base"])
        retval.executed_amount_quote = Decimal(data["executed_amount_quote"])
        retval.fee_asset = data["fee_asset"]
        retval.cumulative_fee_paid = Decimal(data["fee_paid"])
        return retval

    def to_json(self) -> Dict[str, Any]:
        """
        Returns this InFlightOrder as a JSON object.
        :return: JSON object
        """
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "trading_pair": self.trading_pair,
            "order_type": self.order_type.name,
            "trade_type": self.trade_type.name,
            "price": str(self.price),
            "amount": str(self.amount),
            "executed_amount_base": str(self.executed_amount_base),
            "executed_amount_quote": str(self.executed_amount_quote),
            "fee_asset": self.fee_asset,
            "fee_paid": str(self.cumulative_fee_paid),
            "last_state": str(self.current_state.value),
            "leverage": str(self.leverage),
            "position": self.position.value
        }

    def to_limit_order(self) -> LimitOrder:
        """
        Returns this InFlightOrder as a LimitOrder object.
        :return: LimitOrder object.
        """
        return LimitOrder(
            client_order_id=self.client_order_id,
            trading_pair=self.trading_pair,
            is_buy=self.trade_type is TradeType.BUY,
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            price=self.price,
            quantity=self.amount,
            filled_quantity=self.executed_amount_base
        )

    @property
    def latest_trade_fee(self) -> AddedToCostTradeFee:
        trade_fee: AddedToCostTradeFee = (
            AddedToCostTradeFee(percent=self.trade_fee_percent)
            if self.trade_fee_percent
            else AddedToCostTradeFee(flat_fees=[TokenAmount(self.fee_asset, self.last_fee_paid)])
        )
        return trade_fee

    def update_exchange_order_id(self, exchange_order_id: str):
        self.exchange_order_id = exchange_order_id
        self.exchange_order_id_update_event.set()

    async def get_exchange_order_id(self):
        if self.exchange_order_id is None:
            async with timeout(GET_EX_ORDER_ID_TIMEOUT):
                await self.exchange_order_id_update_event.wait()
        return self.exchange_order_id

    def update_with_order_update(self, order_update: OrderUpdate) -> bool:
        """
        Updates the in flight order with an order update (from REST API or WS API)
        return: True if the order gets updated otherwise False
        """
        if order_update.client_order_id != self.client_order_id and order_update.exchange_order_id != self.exchange_order_id:
            return False

        if self.exchange_order_id is None:
            self.update_exchange_order_id(order_update.exchange_order_id)

        updated = False
        prev_order_state: Tuple[Any] = self.attributes
        prev_executed_amount_base = copy.deepcopy(self.executed_amount_base)
        prev_cumulative_fee_paid = copy.deepcopy(self.cumulative_fee_paid)

        self.current_state = order_update.new_state
        if order_update.executed_amount_base:
            self.executed_amount_base = order_update.executed_amount_base
        if order_update.executed_amount_quote:
            self.executed_amount_quote = order_update.executed_amount_quote
        if order_update.cumulative_fee_paid:
            self.cumulative_fee_paid = order_update.cumulative_fee_paid
        if not self.fee_asset and order_update.fee_asset:
            self.fee_asset = order_update.fee_asset

        updated: bool = prev_order_state != self.attributes

        if updated:
            self.last_update_timestamp = order_update.update_timestamp
            if order_update.new_state in {OrderState.OPEN, OrderState.CANCELLED, OrderState.FAILED}:
                return True

            if self.executed_amount_base > prev_executed_amount_base:
                self.last_filled_price = order_update.fill_price or self.price
                self.last_filled_amount = (
                    order_update.executed_amount_base
                    if prev_executed_amount_base == s_decimal_0
                    else order_update.executed_amount_base - prev_executed_amount_base
                )
                self.last_fee_paid = (
                    order_update.cumulative_fee_paid
                    if prev_cumulative_fee_paid == s_decimal_0
                    else order_update.cumulative_fee_paid - prev_cumulative_fee_paid
                )
                # trade_id defaults to update timestamp if not provided
                trade_id: str = order_update.trade_id or order_update.update_timestamp
                self.last_trade_id = trade_id
                self.order_fills[trade_id] = TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=order_update.client_order_id,
                    exchange_order_id=order_update.exchange_order_id,
                    trading_pair=order_update.trading_pair,
                    fee_asset=order_update.fee_asset,
                    fee_paid=self.last_fee_paid,
                    fill_base_amount=self.last_filled_amount,
                    fill_quote_amount=self.last_filled_amount * (order_update.fill_price or self.price),
                    fill_price=(order_update.fill_price or self.price),
                    fill_timestamp=order_update.update_timestamp,
                )

            if self.is_filled:
                self.current_state = OrderState.FILLED

        return updated

    def update_with_trade_update(self, trade_update: TradeUpdate) -> bool:
        """
        Updates the in flight order with a trade update (from REST API or WS API)
        return: True if the order gets updated otherwise False
        """
        trade_id: str = trade_update.trade_id
        if self.exchange_order_id is None and trade_update.exchange_order_id:
            self.update_exchange_order_id(trade_update.exchange_order_id)

        if trade_id in self.order_fills or trade_update.exchange_order_id != self.exchange_order_id:
            return False

        self.executed_amount_base += trade_update.fill_base_amount
        self.executed_amount_quote += trade_update.fill_quote_amount

        if not self.fee_asset and trade_update.fee_asset:
            self.fee_asset = trade_update.fee_asset
        if trade_update.trade_fee_percent is not None:
            self.trade_fee_percent = trade_update.trade_fee_percent

        relevant_fee_amount: Decimal = (
            trade_update.fill_base_amount
            if trade_update.fee_asset == self.base_asset
            else trade_update.fill_quote_amount
        )
        fee_paid: Decimal = (
            trade_update.fee_paid if trade_update.fee_paid is not None else self.trade_fee_percent * relevant_fee_amount
        )
        self.cumulative_fee_paid += fee_paid

        self.last_trade_id = trade_id
        self.last_filled_price = trade_update.fill_price
        self.last_filled_amount = trade_update.fill_base_amount
        self.last_fee_paid = fee_paid
        self.last_update_timestamp = trade_update.fill_timestamp
        self.order_fills[trade_id] = trade_update

        if self.is_filled:
            self.current_state = OrderState.FILLED

        return True
