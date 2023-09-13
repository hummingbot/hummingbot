import asyncio
from decimal import Decimal
from enum import Enum
from typing import List, Tuple, Union

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PriceType, TradeType
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SmartComponentStatus(Enum):
    NOT_STARTED = 1
    ACTIVE = 2
    TERMINATED = 3


class SmartComponentBase:
    def __init__(self, strategy: ScriptStrategyBase, connectors: List[str], update_interval: float = 0.5):
        self._strategy: ScriptStrategyBase = strategy
        self.update_interval = update_interval
        self.connectors = {connector_name: connector for connector_name, connector in strategy.connectors.items() if
                           connector_name in connectors}
        self._status: SmartComponentStatus = SmartComponentStatus.NOT_STARTED
        self._states: list = []

        self._create_buy_order_forwarder = SourceInfoEventForwarder(self.process_order_created_event)
        self._create_sell_order_forwarder = SourceInfoEventForwarder(self.process_order_created_event)
        self._fill_order_forwarder = SourceInfoEventForwarder(self.process_order_filled_event)
        self._complete_buy_order_forwarder = SourceInfoEventForwarder(self.process_order_completed_event)
        self._complete_sell_order_forwarder = SourceInfoEventForwarder(self.process_order_completed_event)
        self._cancel_order_forwarder = SourceInfoEventForwarder(self.process_order_canceled_event)
        self._failed_order_forwarder = SourceInfoEventForwarder(self.process_order_failed_event)

        self._event_pairs: List[Tuple[MarketEvent, SourceInfoEventForwarder]] = [
            (MarketEvent.OrderCancelled, self._cancel_order_forwarder),
            (MarketEvent.BuyOrderCreated, self._create_buy_order_forwarder),
            (MarketEvent.SellOrderCreated, self._create_sell_order_forwarder),
            (MarketEvent.OrderFilled, self._fill_order_forwarder),
            (MarketEvent.BuyOrderCompleted, self._complete_buy_order_forwarder),
            (MarketEvent.SellOrderCompleted, self._complete_sell_order_forwarder),
            (MarketEvent.OrderFailure, self._failed_order_forwarder),
        ]
        self.register_events()
        self.terminated = asyncio.Event()
        safe_ensure_future(self.control_loop())

    @property
    def status(self):
        return self._status

    def get_in_flight_order(self, connector_name: str, order_id: str):
        connector = self.connectors[connector_name]
        order = connector._order_tracker.fetch_order(client_order_id=order_id)
        return order

    async def control_loop(self):
        self.on_start()
        self._status = SmartComponentStatus.ACTIVE
        while not self.terminated.is_set():
            await self.control_task()
            await asyncio.sleep(self.update_interval)
        self._status = SmartComponentStatus.TERMINATED
        self.on_stop()

    def on_stop(self):
        pass

    def on_start(self):
        pass

    def terminate_control_loop(self):
        self.terminated.set()
        self.unregister_events()

    async def control_task(self):
        pass

    def register_events(self):
        """Start listening to events from the given market."""
        for connector in self.connectors.values():
            for event_pair in self._event_pairs:
                connector.add_listener(event_pair[0], event_pair[1])

    def unregister_events(self):
        """Stop listening to events from the given market."""
        for connector in self.connectors.values():
            for event_pair in self._event_pairs:
                connector.remove_listener(event_pair[0], event_pair[1])

    def place_order(self,
                    connector_name: str,
                    trading_pair: str,
                    order_type: OrderType,
                    side: TradeType,
                    amount: Decimal,
                    position_action: PositionAction = PositionAction.NIL,
                    price=Decimal("NaN"),
                    ):
        if side == TradeType.BUY:
            return self._strategy.buy(connector_name, trading_pair, amount, order_type, price, position_action)
        else:
            return self._strategy.sell(connector_name, trading_pair, amount, order_type, price, position_action)

    def get_price(self, connector_name: str, trading_pair: str, price_type: PriceType = PriceType.MidPrice):
        return self.connectors[connector_name].get_price_by_type(trading_pair, price_type)

    def get_order_book(self, connector_name: str, trading_pair: str):
        return self.connectors[connector_name].get_order_book(connector_name, trading_pair)

    def get_balance(self, connector_name: str, asset: str):
        return self.connectors[connector_name].get_balance(asset)

    def get_available_balance(self, connector_name: str, asset: str):
        return self.connectors[connector_name].get_available_balance(asset)

    def get_active_orders(self, connector_name: str):
        return self._strategy.get_active_orders(connector_name)

    def process_order_completed_event(self,
                                      event_tag: int,
                                      market: ConnectorBase,
                                      event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        pass

    def process_order_created_event(self,
                                    event_tag: int,
                                    market: ConnectorBase,
                                    event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        pass

    def process_order_canceled_event(self,
                                     event_tag: int,
                                     market: ConnectorBase,
                                     event: OrderCancelledEvent):
        pass

    def process_order_filled_event(self,
                                   event_tag: int,
                                   market: ConnectorBase,
                                   event: OrderFilledEvent):
        pass

    def process_order_failed_event(self,
                                   event_tag: int,
                                   market: ConnectorBase,
                                   event: MarketOrderFailureEvent):
        pass
