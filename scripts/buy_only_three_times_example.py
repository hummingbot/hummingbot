from decimal import Decimal

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.event.events import BuyOrderCreatedEvent
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class BuyOnlyThreeTimesExample(ScriptStrategyBase):
    """
    This example places shows how to add a logic to only place three buy orders in the market,
    use an event to increase the counter and stop the strategy once the task is done.
    """
    order_amount_usd = Decimal(100)
    orders_created = 0
    orders_to_create = 3
    base = "ETH"
    quote = "USDT"
    markets = {
        "kucoin_paper_trade": {f"{base}-{quote}"}
    }

    def on_tick(self):
        if self.orders_created < self.orders_to_create:
            conversion_rate = RateOracle.get_instance().get_pair_rate(f"{self.base}-USD")
            amount = self.order_amount_usd / conversion_rate
            price = self.connectors["kucoin_paper_trade"].get_mid_price(f"{self.base}-{self.quote}") * Decimal(0.99)
            self.buy(
                connector_name="kucoin_paper_trade",
                trading_pair="ETH-USDT",
                amount=amount,
                order_type=OrderType.LIMIT,
                price=price
            )

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        trading_pair = f"{self.base}-{self.quote}"
        if event.trading_pair == trading_pair:
            self.orders_created += 1
            if self.orders_created == self.orders_to_create:
                self.logger().info("All order created !")
                HummingbotApplication.main_application().stop()
