import asyncio
import copy
import math
import typing
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, NamedTuple, Optional, Tuple

from async_timeout import timeout

from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import TradeFeeBase

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.exchange_base import ExchangeBase

s_decimal_0 = Decimal("0")

GET_EX_ORDER_ID_TIMEOUT = 10  # seconds


class OrderState(Enum):
    PENDING_CREATE = 0
    OPEN = 1
    PENDING_CANCEL = 2
    CANCELED = 3
    PARTIALLY_FILLED = 4
    FILLED = 5
    FAILED = 6
    PENDING_APPROVAL = 7
    APPROVED = 8
    CREATED = 9
    COMPLETED = 10


class OrderUpdate(NamedTuple):
    trading_pair: str
    update_timestamp: float  # seconds
    new_state: OrderState
    client_order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    misc_updates: Optional[Dict[str, Any]] = None


class TradeUpdate(NamedTuple):
    trade_id: str
    client_order_id: str
    exchange_order_id: str
    trading_pair: str
    fill_timestamp: float  # seconds
    fill_price: Decimal
    fill_base_amount: Decimal
    fill_quote_amount: Decimal
    fee: TradeFeeBase
    is_taker: bool = True  # CEXs deliver trade events from the taker's perspective

    @property
    def fee_asset(self):
        return self.fee.fee_asset

    @classmethod
    def from_json(cls, data: Dict[str, Any]):
        instance = TradeUpdate(
            trade_id=data["trade_id"],
            client_order_id=data["client_order_id"],
            exchange_order_id=data["exchange_order_id"],
            trading_pair=data["trading_pair"],
            fill_timestamp=data["fill_timestamp"],
            fill_price=Decimal(data["fill_price"]),
            fill_base_amount=Decimal(data["fill_base_amount"]),
            fill_quote_amount=Decimal(data["fill_quote_amount"]),
            fee=TradeFeeBase.from_json(data["fee"]),
        )

        return instance

    def to_json(self) -> Dict[str, Any]:
        json_dict = self._asdict()
        json_dict.update({
            "fill_price": str(self.fill_price),
            "fill_base_amount": str(self.fill_base_amount),
            "fill_quote_amount": str(self.fill_quote_amount),
            "fee": self.fee.to_json(),
        })
        return json_dict


class InFlightOrder:
    def __init__(
            self,
            client_order_id: str,
            trading_pair: str,
            order_type: OrderType,
            trade_type: TradeType,
            amount: Decimal,
            creation_timestamp: float,
            price: Optional[Decimal] = None,
            exchange_order_id: Optional[str] = None,
            initial_state: OrderState = OrderState.PENDING_CREATE,
            leverage: int = 1,
            position: PositionAction = PositionAction.NIL,
    ) -> None:
        self.client_order_id = client_order_id
        self.creation_timestamp = creation_timestamp
        self.trading_pair = trading_pair
        self.order_type = order_type
        self.trade_type = trade_type
        self.price = price
        self.amount = amount
        self.exchange_order_id = exchange_order_id
        self.current_state = initial_state
        self.leverage = leverage
        self.position = position

        self.executed_amount_base = s_decimal_0
        self.executed_amount_quote = s_decimal_0

        self.last_update_timestamp: float = creation_timestamp

        self.order_fills: Dict[str, TradeUpdate] = {}  # Dict[trade_id, TradeUpdate]

        self.exchange_order_id_update_event = asyncio.Event()
        if self.exchange_order_id:
            self.exchange_order_id_update_event.set()
        self.completely_filled_event = asyncio.Event()
        self.processed_by_exchange_event = asyncio.Event()
        self.check_processed_by_exchange_condition()

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
                self.executed_amount_base,
                self.executed_amount_quote,
                self.creation_timestamp,
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
        return self.current_state in {
            OrderState.PENDING_CREATE,
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.PENDING_CANCEL}

    @property
    def is_done(self) -> bool:
        return (
            self.current_state in {OrderState.CANCELED, OrderState.FILLED, OrderState.FAILED}
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
        return self.current_state == OrderState.CANCELED

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
        order = InFlightOrder(
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
            creation_timestamp=data.get("creation_timestamp", -1)
        )
        order.executed_amount_base = Decimal(data["executed_amount_base"])
        order.executed_amount_quote = Decimal(data["executed_amount_quote"])
        order.order_fills.update({key: TradeUpdate.from_json(value)
                                  for key, value
                                  in data.get("order_fills", {}).items()})
        order.last_update_timestamp = data.get("last_update_timestamp", order.creation_timestamp)

        order.check_filled_condition()
        order.check_processed_by_exchange_condition()

        return order

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
            "last_state": str(self.current_state.value),
            "leverage": str(self.leverage),
            "position": self.position.value,
            "creation_timestamp": self.creation_timestamp,
            "last_update_timestamp": self.last_update_timestamp,
            "order_fills": {key: fill.to_json() for key, fill in self.order_fills.items()}
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
            filled_quantity=self.executed_amount_base,
            creation_timestamp=int(self.creation_timestamp * 1e6)
        )

    def update_exchange_order_id(self, exchange_order_id: str):
        self.exchange_order_id = exchange_order_id
        self.exchange_order_id_update_event.set()

    async def get_exchange_order_id(self):
        if self.exchange_order_id is None:
            async with timeout(GET_EX_ORDER_ID_TIMEOUT):
                await self.exchange_order_id_update_event.wait()
        return self.exchange_order_id

    def cumulative_fee_paid(self, token: str, exchange: Optional['ExchangeBase'] = None) -> Decimal:
        """
        Returns the total amount of fee paid for each trade update, expressed in the specified token
        :param token: The token all partial fills' fees should be transformed to before summing them
        :param exchange: The exchange being used. If specified the logic will try to use the order book to get the rate
        :return: the cumulative fee paid for all partial fills in the specified token
        """
        total_fee_in_token = Decimal("0")
        for trade_update in self.order_fills.values():
            total_fee_in_token += trade_update.fee.fee_amount_in_token(
                trading_pair=self.trading_pair,
                price=trade_update.fill_price,
                order_amount=trade_update.fill_base_amount,
                token=token,
                exchange=exchange
            )
        return total_fee_in_token

    def update_with_order_update(self, order_update: OrderUpdate) -> bool:
        """
        Updates the in flight order with an order update (from REST API or WS API)
        return: True if the order gets updated otherwise False
        """
        if (order_update.client_order_id != self.client_order_id
                and order_update.exchange_order_id != self.exchange_order_id):
            return False

        prev_data = (self.exchange_order_id, self.current_state)

        if self.exchange_order_id is None and order_update.exchange_order_id is not None:
            self.update_exchange_order_id(order_update.exchange_order_id)

        self.current_state = order_update.new_state
        self.check_processed_by_exchange_condition()

        updated: bool = prev_data != (self.exchange_order_id, self.current_state)

        if updated:
            self.last_update_timestamp = order_update.update_timestamp

        return updated

    def update_with_trade_update(self, trade_update: TradeUpdate) -> bool:
        """
        Updates the in flight order with a trade update (from REST API or WS API)
        :return: True if the order gets updated otherwise False
        """
        trade_id: str = trade_update.trade_id

        if (trade_id in self.order_fills
                or (self.client_order_id != trade_update.client_order_id
                    and self.exchange_order_id != trade_update.exchange_order_id)):
            return False

        self.order_fills[trade_id] = trade_update

        self.executed_amount_base += trade_update.fill_base_amount
        self.executed_amount_quote += trade_update.fill_quote_amount

        self.last_update_timestamp = trade_update.fill_timestamp
        self.check_filled_condition()

        return True

    def check_filled_condition(self):
        if (abs(self.amount) - self.executed_amount_base).quantize(Decimal('1e-8')) <= 0:
            self.completely_filled_event.set()

    async def wait_until_completely_filled(self):
        await self.completely_filled_event.wait()

    def check_processed_by_exchange_condition(self):
        if self.current_state.value > OrderState.PENDING_CREATE.value:
            self.processed_by_exchange_event.set()

    async def wait_until_processed_by_exchange(self):
        await self.processed_by_exchange_event.wait()

    def build_order_created_message(self) -> str:
        return (
            f"Created {self.order_type.name.upper()} {self.trade_type.name.upper()} order "
            f"{self.client_order_id} for {self.amount} {self.trading_pair} "
            f"at {self.price}."
        )


class PerpetualDerivativeInFlightOrder(InFlightOrder):
    def build_order_created_message(self) -> str:
        return (
            f"Created {self.order_type.name.upper()} {self.trade_type.name.upper()} order "
            f"{self.client_order_id} for {self.amount} to {self.position.name.upper()} a {self.trading_pair} position "
            f"at {self.price}."
        )
