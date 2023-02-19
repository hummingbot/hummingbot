from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketOrderFailureEvent, SellOrderCreatedEvent
from hummingbot.remote_iface.mqtt import EEventsQueueFactory
from hummingbot.strategy.script_strategy_base import Decimal, OrderType, ScriptStrategyBase


class ExternalEventsExample(ScriptStrategyBase):
    """
    Simple script that uses the external events plugin to create buy and sell
    market orders.
    """
    #: Define markets
    markets = {"kucoin_paper_trade": {"BTC-USDT"}}
    eevents = EEventsQueueFactory.create('*')
    # eevents = EEventsQueueFactory.create('tv.s1.signal')

    def on_tick(self):
        while len(self.eevents) > 0:
            event = self.eevents.popleft()
            self.logger().info(f'External Event in Queue: {event}')
            if event[0] == 'order.market':
                if event[1].data['type'] in ('buy', 'Buy', 'BUY'):
                    self.execute_order(Decimal(event[1].data['amount']), True)
                elif event[1].data['type'] in ('sell', 'Sell', 'SELL'):
                    self.execute_order(Decimal(event[1].data['amount']), False)

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
