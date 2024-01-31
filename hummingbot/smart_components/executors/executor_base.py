from decimal import Decimal
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
from hummingbot.smart_components.smart_component_base import SmartComponentBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class ExecutorBase(SmartComponentBase):
    """
    Base class for all executors. Executors are responsible for executing orders based on the strategy.
    """

    def __init__(self, strategy: ScriptStrategyBase, connectors: List[str], update_interval: float = 0.5):
        """
        Initializes the executor with the given strategy, connectors and update interval.

        :param strategy: The strategy to be used by the executor.
        :param connectors: The connectors to be used by the executor.
        :param update_interval: The update interval for the executor.
        """
        super().__init__(update_interval)
        self._strategy: ScriptStrategyBase = strategy
        self.connectors = {connector_name: connector for connector_name, connector in strategy.connectors.items() if
                           connector_name in connectors}

        # Event forwarders for different order events
        self._create_buy_order_forwarder = SourceInfoEventForwarder(self.process_order_created_event)
        self._create_sell_order_forwarder = SourceInfoEventForwarder(self.process_order_created_event)
        self._fill_order_forwarder = SourceInfoEventForwarder(self.process_order_filled_event)
        self._complete_buy_order_forwarder = SourceInfoEventForwarder(self.process_order_completed_event)
        self._complete_sell_order_forwarder = SourceInfoEventForwarder(self.process_order_completed_event)
        self._cancel_order_forwarder = SourceInfoEventForwarder(self.process_order_canceled_event)
        self._failed_order_forwarder = SourceInfoEventForwarder(self.process_order_failed_event)

        # Pairs of market events and their corresponding event forwarders
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

    @property
    def status(self):
        """
        Returns the status of the executor.
        """
        return self._status

    @staticmethod
    def is_perpetual_connector(connector_name: str):
        """
        Returns whether the specified connector is a perpetual connector.

        :param connector_name: The name of the connector.
        :return: True if the connector is a perpetual connector, False otherwise.
        """
        return "perpetual" in connector_name.lower()

    def start(self):
        """
        Starts the executor and registers the events.
        """
        super().start()
        self.register_events()

    def stop(self):
        """
        Stops the executor and unregisters the events.
        """
        super().stop()
        self.unregister_events()

    def get_in_flight_order(self, connector_name: str, order_id: str):
        """
        Retrieves an in-flight order from the specified connector using the order ID.

        :param connector_name: The name of the connector.
        :param order_id: The ID of the order.
        :return: The in-flight order.
        """
        connector = self.connectors[connector_name]
        order = connector._order_tracker.fetch_order(client_order_id=order_id)
        return order

    def register_events(self):
        """
        Registers the events with the connectors.
        """
        for connector in self.connectors.values():
            for event_pair in self._event_pairs:
                connector.add_listener(event_pair[0], event_pair[1])

    def unregister_events(self):
        """
        Unregisters the events from the connectors.
        """
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
        """
        Places an order with the specified parameters.

        :param connector_name: The name of the connector.
        :param trading_pair: The trading pair for the order.
        :param order_type: The type of the order.
        :param side: The side of the order (buy or sell).
        :param amount: The amount for the order.
        :param position_action: The position action for the order.
        :param price: The price for the order.
        :return: The result of the order placement.
        """
        if side == TradeType.BUY:
            return self._strategy.buy(connector_name, trading_pair, amount, order_type, price, position_action)
        else:
            return self._strategy.sell(connector_name, trading_pair, amount, order_type, price, position_action)

    def get_price(self, connector_name: str, trading_pair: str, price_type: PriceType = PriceType.MidPrice):
        """
        Retrieves the price for the specified trading pair from the specified connector.

        :param connector_name: The name of the connector.
        :param trading_pair: The trading pair.
        :param price_type: The type of the price.
        :return: The price.
        """
        return self.connectors[connector_name].get_price_by_type(trading_pair, price_type)

    def get_order_book(self, connector_name: str, trading_pair: str):
        """
        Retrieves the order book for the specified trading pair from the specified connector.

        :param connector_name: The name of the connector.
        :param trading_pair: The trading pair.
        :return: The order book.
        """
        return self.connectors[connector_name].get_order_book(connector_name, trading_pair)

    def get_balance(self, connector_name: str, asset: str):
        """
        Retrieves the balance of the specified asset from the specified connector.

        :param connector_name: The name of the connector.
        :param asset: The asset.
        :return: The balance.
        """
        return self.connectors[connector_name].get_balance(asset)

    def get_available_balance(self, connector_name: str, asset: str):
        """
        Retrieves the available balance of the specified asset from the specified connector.

        :param connector_name: The name of the connector.
        :param asset: The asset.
        :return: The available balance.
        """
        return self.connectors[connector_name].get_available_balance(asset)

    def get_active_orders(self, connector_name: str):
        """
        Retrieves the active orders from the specified connector.

        :param connector_name: The name of the connector.
        :return: The active orders.
        """
        return self._strategy.get_active_orders(connector_name)

    def process_order_completed_event(self,
                                      event_tag: int,
                                      market: ConnectorBase,
                                      event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        """
        Processes the order completed event. This method should be overridden by subclasses.

        :param event_tag: The event tag.
        :param market: The market where the event occurred.
        :param event: The event.
        """
        pass

    def process_order_created_event(self,
                                    event_tag: int,
                                    market: ConnectorBase,
                                    event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        """
        Processes the order created event. This method should be overridden by subclasses.

        :param event_tag: The event tag.
        :param market: The market where the event occurred.
        :param event: The event.
        """
        pass

    def process_order_canceled_event(self,
                                     event_tag: int,
                                     market: ConnectorBase,
                                     event: OrderCancelledEvent):
        """
        Processes the order canceled event. This method should be overridden by subclasses.

        :param event_tag: The event tag.
        :param market: The market where the event occurred.
        :param event: The event.
        """
        pass

    def process_order_filled_event(self,
                                   event_tag: int,
                                   market: ConnectorBase,
                                   event: OrderFilledEvent):
        """
        Processes the order filled event. This method should be overridden by subclasses.

        :param event_tag: The event tag.
        :param market: The market where the event occurred.
        :param event: The event.
        """
        pass

    def process_order_failed_event(self,
                                   event_tag: int,
                                   market: ConnectorBase,
                                   event: MarketOrderFailureEvent):
        """
        Processes the order failed event. This method should be overridden by subclasses.

        :param event_tag: The event tag.
        :param market: The market where the event occurred.
        :param event: The event.
        """
        pass
