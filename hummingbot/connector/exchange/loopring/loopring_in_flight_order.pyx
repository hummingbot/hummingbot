from decimal import Decimal
from typing import Any, Dict, List

from hummingbot.connector.exchange.loopring.loopring_exchange cimport LoopringExchange
from hummingbot.connector.exchange.loopring.loopring_order_status import LoopringOrderStatus
from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.events import MarketEvent

cdef class LoopringInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 created_at: float,
                 initial_state: LoopringOrderStatus,
                 filled_size: Decimal,
                 filled_volume: Decimal,
                 filled_fee: Decimal):

        super().__init__(client_order_id=client_order_id,
                         exchange_order_id=exchange_order_id,
                         trading_pair=trading_pair,
                         order_type=order_type,
                         trade_type=trade_type,
                         price=price,
                         amount=amount,
                         initial_state=initial_state.name,
                         creation_timestamp=created_at)
        self.status = initial_state
        self.executed_amount_base = filled_size
        self.executed_amount_quote = filled_volume
        self.fee_paid = filled_fee

        self.fee_asset = self.base_asset if trade_type is TradeType.BUY else self.quote_asset

    @property
    def is_done(self) -> bool:
        return self.status >= LoopringOrderStatus.DONE

    @property
    def is_cancelled(self) -> bool:
        return self.status == LoopringOrderStatus.cancelled

    @property
    def is_failure(self) -> bool:
        return self.status >= LoopringOrderStatus.failed

    @property
    def is_expired(self) -> bool:
        return self.status == LoopringOrderStatus.expired

    @property
    def description(self):
        return f"{str(self.order_type).lower()} {str(self.trade_type).lower()}"

    def to_json(self):
        json_dict = super().to_json()
        json_dict.update({
            "last_state": self.status.name
        })
        return json_dict

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> LoopringInFlightOrder:
        order = super().from_json(data)
        order.status = LoopringOrderStatus[order.last_state]
        return order

    @classmethod
    def _instance_creation_parameters_from_json(cls, data: Dict[str, Any]) -> List[Any]:
        arguments: List[Any] = super()._instance_creation_parameters_from_json(data)
        arguments[8] = LoopringOrderStatus[arguments[8]]  # Order status has to be deserialized
        arguments.append(Decimal(0))  # Filled size
        arguments.append(Decimal(0))  # Filled volume
        arguments.append(Decimal(0))  # Filled fee
        return arguments

    @classmethod
    def from_loopring_order(cls,
                            side: TradeType,
                            client_order_id: str,
                            created_at: float,
                            hash: str,
                            trading_pair: str,
                            price: float,
                            amount: float) -> LoopringInFlightOrder:
        return LoopringInFlightOrder(
            client_order_id,
            hash,
            trading_pair,
            OrderType.LIMIT,
            side,
            Decimal(price),
            Decimal(amount),
            created_at,
            LoopringOrderStatus.waiting,
            Decimal(0),
            Decimal(0),
            Decimal(0),
        )

    def update(self, data: Dict[str, Any], connector: LoopringExchange) -> List[Any]:
        events: List[Any] = []

        base: str
        quote: str
        trading_pair: str = data["market"]
        base_id: int = connector.token_configuration.get_tokenid(self.base_asset)
        quote_id: int = connector.token_configuration.get_tokenid(self.quote_asset)
        fee_currency_id: int = connector.token_configuration.get_tokenid(self.fee_asset)

        new_status: LoopringOrderStatus = LoopringOrderStatus[data["status"]]
        new_executed_amount_base: Decimal = connector.token_configuration.unpad(data["filledSize"], base_id)
        new_executed_amount_quote: Decimal = connector.token_configuration.unpad(data["filledVolume"], quote_id)
        new_fee_paid: Decimal = connector.token_configuration.unpad(data["filledFee"], fee_currency_id)

        if new_executed_amount_base > self.executed_amount_base or new_executed_amount_quote > self.executed_amount_quote:
            diff_base: Decimal = new_executed_amount_base - self.executed_amount_base
            diff_quote: Decimal = new_executed_amount_quote - self.executed_amount_quote
            diff_fee: Decimal = new_fee_paid - self.fee_paid
            if diff_quote > Decimal(0):
                price: Decimal = diff_quote / diff_base
            else:
                price: Decimal = self.executed_amount_quote / self.executed_amount_base

            events.append((MarketEvent.OrderFilled, diff_base, price, diff_fee))

        if not self.is_done and new_status == LoopringOrderStatus.cancelled:
            events.append((MarketEvent.OrderCancelled, None, None, None))

        if not self.is_done and new_status == LoopringOrderStatus.expired:
            events.append((MarketEvent.OrderExpired, None, None, None))

        if not self.is_done and new_status == LoopringOrderStatus.failed:
            events.append((MarketEvent.OrderFailure, None, None, None))

        self.status = new_status
        self.last_state = str(new_status)
        self.executed_amount_base = new_executed_amount_base
        self.executed_amount_quote = new_executed_amount_quote
        self.fee_paid = new_fee_paid

        if self.exchange_order_id is None:
            self.update_exchange_order_id(data.get('hash', None))

        return events
