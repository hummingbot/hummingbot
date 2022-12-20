import asyncio
from decimal import Decimal

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.event.events import BuyOrderCreatedEvent
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.utils.async_utils import safe_ensure_future



class BuyOnlyThreeTimesExample(ScriptStrategyBase):
    """
    This example places shows how to add a logic to only place three buy orders in the market,
    use an event to increase the counter and stop the strategy once the task is done.
    """
    order_amount = Decimal("0.001")
    orders_created = 0
    orders_to_create = 3
    base = "WETH"
    quote = "UNI"
    markets = {
        "uniswap_ethereum_goerli": {f"{base}-{quote}"}
    }
    on_going_task = False

    def on_tick(self):
        if self.orders_created < self.orders_to_create and not self.on_going_task:
            self.on_going_task = True
            safe_ensure_future(self.async_task())
            self.logger().info(f"Order NUmber: {self.orders_created}")
            

    
    async def async_task(self):
        cancels = await self.cancel_all_orders()
        if not all([result.success for result in cancels[0]]):
            self.logger().warning("There was an error when trying to cancel an order, retrying...")
            self.on_going_task = False
            return
        price = await self.connectors["uniswap_ethereum_goerli"].get_quote_price("WETH-UNI", True, self.order_amount, True)
        self.logger().info(f"Price: {price}")
        self.buy(
                connector_name="uniswap_ethereum_goerli",
                trading_pair="WETH-UNI",
                amount=self.order_amount,
                order_type=OrderType.MARKET,
                price=price
            )


    
    async def cancel_all_orders(self):
        tasks = [exchange.cancel_all(timeout_seconds=5) for exchange in self.connectors.values()]
        cancels = await asyncio.gather(*tasks)
        return cancels

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        trading_pair = f"{self.base}-{self.quote}"
        if event.trading_pair == trading_pair:
            self.orders_created += 1
            if self.orders_created == self.orders_to_create:
                self.logger().info("All order created !")
                HummingbotApplication.main_application().stop()
