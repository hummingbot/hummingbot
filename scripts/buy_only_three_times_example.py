from decimal import Decimal

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.event.events import BuyOrderCreatedEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class BuyOnlyThreeTimes(ScriptStrategyBase):
    """
    This example places shows how to add a logic to only place three buy orders in the market,
    use an event to increase the counter and stop the strategy once the task is done.
    """
    markets = {"kucoin_paper_trade": {"ETH-USDT"}}
    orders_to_place = 3
    orders_created = 0
    distance_from_mid_price = 0.0001

    def on_tick(self):
        if self.orders_created < self.orders_to_place:
            mid_price = self.connectors["kucoin_paper_trade"].get_mid_price("ETH-USDT")
            self.buy(
                connector_name="kucoin_paper_trade",
                trading_pair="ETH-USDT",
                amount=Decimal(0.05),
                price=mid_price * Decimal(1 - self.distance_from_mid_price),
                order_type=OrderType.LIMIT,
            )

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        self.orders_created += 1
        if self.orders_created == self.orders_to_place:
            self.logger().info("All orders created")
            HummingbotApplication().main_application().stop()
