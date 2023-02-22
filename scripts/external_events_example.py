from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketOrderFailureEvent, SellOrderCreatedEvent
from hummingbot.remote_iface.mqtt import (
    EEventListenerFactory,
    EEventQueueFactory,
    ETopicListenerFactory,
    ETopicQueueFactory,
)
from hummingbot.strategy.script_strategy_base import Decimal, OrderType, ScriptStrategyBase


class ExternalEventsExample(ScriptStrategyBase):
    """
    Simple script that uses the external events plugin to create buy and sell
    market orders.
    """
    #: Define markets
    markets = {"kucoin_paper_trade": {"BTC-USDT"}}

    # ------ Using Factory Classes ------
    # -----------------------------------
    # hbot/{id}/external/events/*
    eevents = EEventQueueFactory.create('*')
    # hbot/{id}/external/events/tv/s1/signal
    # eevents = EEventsQueueFactory.create('tv.s1.signal')

    # Examples of using ETopicQUeueFactory to listen to MQTT topics for
    # messages and puts them in a FIFO
    # hbot/{id}/test/a
    # etopic_queue = ETopicQueueFactory.create('test.a')
    etopic_queue = ETopicQueueFactory.create('test/a')

    # this/is/without/prefix/a
    # etopic_queue = ETopicQueueFactory.create(
    #     'this/is/without/prefix/a',
    #     use_bot_prefix=False
    # )
    # -----------------------------------

    # ---- Using callback functions ----
    # ----------------------------------
    def __init__(self, *args, **kwargs):
        EEventListenerFactory.create('*', self.on_event)
        self.listener = ETopicListenerFactory.create('test/a', self.on_message)
        super().__init__(*args, **kwargs)

    def on_event(self, msg, name):
        self.logger().info(f'OnEvent Callback fired: {name} -> {msg}')

    def on_message(self, msg, topic):
        self.logger().info(f'Topic Message Callback fired: {topic} -> {msg}')

    def on_stop(self):
        EEventListenerFactory.remove('*', self.on_event)
        ETopicListenerFactory.remove(self.listener)
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
            self.buy("kucoin_paper_trade", "BTC-USDT", amount, OrderType.MARKET)
        else:
            self.sell("kucoin_paper_trade", "BTC-USDT", amount, OrderType.MARKET)

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
