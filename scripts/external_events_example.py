import os
from decimal import Decimal

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, OrderType
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketOrderFailureEvent, SellOrderCreatedEvent
from hummingbot.remote_iface.mqtt import ExternalEventFactory, ExternalTopicFactory
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class ExternalEventsExampleConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    exchange: str = Field(default="kucoin_paper_trade")
    trading_pair: str = Field(default="BTC-USDT")

    def update_markets(self, markets: MarketDict) -> MarketDict:
        markets[self.exchange] = markets.get(self.exchange, set()) | {self.trading_pair}
        return markets


class ExternalEventsExample(StrategyV2Base):
    """
    Simple script that uses the external events plugin to create buy and sell
    market orders.
    """

    # ------ Using Factory Classes ------
    # hbot/{id}/external/events/*
    eevents = ExternalEventFactory.create_queue('*')
    # hbot/{id}/test/a
    etopic_queue = ExternalTopicFactory.create_queue('test/a')

    # ---- Using callback functions ----
    # ----------------------------------
    def __init__(self, *args, **kwargs):
        ExternalEventFactory.create_async('*', self.on_event)
        self.listener = ExternalTopicFactory.create_async('test/a', self.on_message)
        super().__init__(*args, **kwargs)

    def on_event(self, msg, name):
        self.logger().info(f'OnEvent Callback fired: {name} -> {msg}')

    def on_message(self, msg, topic):
        self.logger().info(f'Topic Message Callback fired: {topic} -> {msg}')

    async def on_stop(self):
        ExternalEventFactory.remove_listener('*', self.on_event)
        ExternalTopicFactory.remove_listener(self.listener)
    # ----------------------------------

    def on_tick(self):
        while len(self.eevents) > 0:
            event = self.eevents.popleft()
            self.logger().info(f'External Event in Queue: {event}')
            # event = (name, msg)
            if event[0] == 'order.market':
                if event[1].data['type'] in ('buy', 'Buy', 'BUY'):
                    self.execute_order(Decimal(event[1].data['amount']), True)
                elif event[1].data['type'] in ('sell', 'Sell', 'SELL'):
                    self.execute_order(Decimal(event[1].data['amount']), False)
        while len(self.etopic_queue) > 0:
            entry = self.etopic_queue.popleft()
            self.logger().info(f'Topic Message in Queue: {entry[0]} -> {entry[1]}')

    def execute_order(self, amount: Decimal, is_buy: bool):
        if is_buy:
            self.buy(self.config.exchange, self.config.trading_pair, amount, OrderType.MARKET)
        else:
            self.sell(self.config.exchange, self.config.trading_pair, amount, OrderType.MARKET)

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        """
        Method called when the connector notifies a buy order has been created
        """
        self.logger().info(f"The buy order {event.order_id} has been created")

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        """
        Method called when the connector notifies a sell order has been created
        """
        self.logger().info(f"The sell order {event.order_id} has been created")

    def did_fail_order(self, event: MarketOrderFailureEvent):
        """
        Method called when the connector notifies an order has failed
        """
        self.logger().info(f"The order {event.order_id} failed")
