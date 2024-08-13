from decimal import Decimal
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Union

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
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
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo
from hummingbot.strategy_v2.runnable_base import RunnableBase


class ExecutorBase(RunnableBase):
    """
    Base class for all executors. Executors are responsible for executing orders based on the strategy.
    """

    def __init__(self, strategy: ScriptStrategyBase, connectors: List[str], config: ExecutorConfigBase, update_interval: float = 0.5):
        """
        Initializes the executor with the given strategy, connectors and update interval.

        :param strategy: The strategy to be used by the executor.
        :param connectors: The connectors to be used by the executor.
        :param update_interval: The update interval for the executor.
        """
        super().__init__(update_interval)
        self.config = config
        self.close_type: Optional[CloseType] = None
        self.close_timestamp: Optional[float] = None
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

    @property
    def status(self):
        """
        Returns the status of the executor.
        """
        return self._status

    @property
    def is_trading(self):
        """
        Returns whether the executor is trading.
        """
        return self.is_active and self.net_pnl_quote != 0

    @property
    def filled_amount_quote(self):
        """
        Returns the filled amount in quote currency.
        """
        return Decimal("0")

    @property
    def is_active(self):
        """
        Returns whether the executor is open or trading.
        """
        return self._status in [RunnableStatus.RUNNING, RunnableStatus.NOT_STARTED]

    @property
    def is_closed(self):
        """
        Returns whether the executor is closed.
        """
        return self._status == RunnableStatus.TERMINATED

    @property
    def executor_info(self) -> ExecutorInfo:
        """
        Returns the executor info.
        """
        return ExecutorInfo(
            id=self.config.id,
            timestamp=self.config.timestamp,
            type=self.config.type,
            status=self.status,
            close_type=self.close_type,
            close_timestamp=self.close_timestamp,
            config=self.config,
            net_pnl_pct=self.net_pnl_pct,
            net_pnl_quote=self.net_pnl_quote,
            cum_fees_quote=self.cum_fees_quote,
            filled_amount_quote=self.filled_amount_quote,
            is_active=self.is_active,
            is_trading=self.is_trading,
            custom_info=self.get_custom_info(),
            controller_id=self.config.controller_id,
        )

    def get_custom_info(self) -> Dict:
        """
        Returns the custom info of the executor. Returns an empty dictionary by default, and can be reimplemented
        by subclasses.
        """
        return {}

    @staticmethod
    def is_perpetual_connector(connector_name: str):
        """
        Returns whether the specified connector is a perpetual connector.

        :param connector_name: The name of the connector.
        :return: True if the connector is a perpetual connector, False otherwise.
        """
        return "perpetual" in connector_name.lower()

    @staticmethod
    @lru_cache(maxsize=10)
    def is_amm_connector(exchange: str) -> bool:
        return exchange in sorted(
            AllConnectorSettings.get_gateway_amm_connector_names()
        )

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
        self.close_timestamp = self._strategy.current_timestamp
        super().stop()
        self.unregister_events()

    def on_start(self):
        """
        Called when the executor is started.
        """
        self.validate_sufficient_balance()

    def on_stop(self):
        """
        Called when the executor is stopped.
        """
        pass

    def early_stop(self):
        """
        This method allows strategy to stop the executor early.
        """
        raise NotImplementedError

    def validate_sufficient_balance(self):
        """
        Validates that the executor has sufficient balance to place orders.
        """
        raise NotImplementedError

    @property
    def net_pnl_quote(self) -> Decimal:
        """
        Returns the net profit or loss in quote currency.
        """
        return self.get_net_pnl_quote()

    @property
    def net_pnl_pct(self) -> Decimal:
        """
        Returns the net profit or loss in percentage.
        """
        return self.get_net_pnl_pct()

    @property
    def cum_fees_quote(self) -> Decimal:
        """
        Returns the cumulative fees in quote currency.
        """
        return self.get_cum_fees_quote()

    def get_net_pnl_quote(self) -> Decimal:
        """
        Returns the net profit or loss in quote currency.
        """
        raise NotImplementedError

    def get_net_pnl_pct(self) -> Decimal:
        """
        Returns the net profit or loss in percentage.
        """
        raise NotImplementedError

    def get_cum_fees_quote(self) -> Decimal:
        """
        Returns the cumulative fees in quote currency.
        """
        raise NotImplementedError

    def get_in_flight_order(self, connector_name: str, order_id: str):
        """
        Retrieves an in-flight order from the specified connector using the order ID.

        :param connector_name: The name of the connector.
        :param order_id: The ID of the order.
        :return: The in-flight order.
        """
        return self.connectors[connector_name]._order_tracker.fetch_order(client_order_id=order_id)

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

    def adjust_order_candidates(self, exchange: str, order_candidates: List[OrderCandidate]) -> List[OrderCandidate]:
        """
        Adjusts the order candidates based on the budget checker of the specified exchange.
        """
        return self.connectors[exchange].budget_checker.adjust_candidates(order_candidates)

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

    def get_trading_rules(self, connector_name: str, trading_pair: str) -> TradingRule:
        """
        Retrieves the trading rules for the specified trading pair from the specified connector.

        :param connector_name: The name of the connector.
        :param trading_pair: The trading pair.
        :return: The trading rules.
        """
        return self.connectors[connector_name].trading_rules[trading_pair]

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
