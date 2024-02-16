from decimal import Decimal

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.event.events import BuyOrderCreatedEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class BuyOnlyThreeTimesExample(ScriptStrategyBase):
    """
    This example places shows how to add a logic to only place three buy orders in the market,
    use an event to increase the counter and stop the strategy once the task is done.
    """
    order_amount_xrp = Decimal(5)
    orders_submitted = 0
    orders_created = 0
    orders_to_create = 3
    base = "SOLO"
    quote = "XRP"
    markets = {
        "xrpl_xrpl_mainnet": {f"{base}-{quote}"}
    }

    def on_tick(self):
        if self.orders_submitted < self.orders_to_create:
            price = self.connectors["xrpl_xrpl_mainnet"].get_mid_price(f"{self.base}-{self.quote}") * Decimal(0.99)
            amount = self.order_amount_xrp / price
            self.buy(
                connector_name="xrpl_xrpl_mainnet",
                trading_pair="SOLO-XRP",
                amount=amount,
                order_type=OrderType.LIMIT,
                price=price
            )
            self.orders_submitted += 1

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        trading_pair = f"{self.base}-{self.quote}"
        if event.trading_pair == trading_pair:
            self.orders_created += 1
            if self.orders_created == self.orders_to_create:
                self.logger().info("All order created !")
                HummingbotApplication.main_application().stop()
