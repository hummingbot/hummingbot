import asyncio
import logging

from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import Decimal, OrderType, ScriptStrategyBase


class DCAExample(ScriptStrategyBase):
    """
    This example shows how to set up a simple strategy to buy a token on fixed (dollar) amount on a regular basis
    """
    #: Define markets to instruct Hummingbot to create connectors on the exchanges and markets you need
    markets = {"uniswap_ethereum_goerli": {"WETH-UNI"}}
    #: The last time the strategy places a buy order
    last_ordered_ts = 0.
    #: Buying interval (in seconds)
    buy_interval = 10.
    #: Buying amount (in dollars - USDT)
    buy_quote_amount = Decimal("0.001")
    create_timestamp = 0
    on_going_task = False

    def on_tick(self):

        if self.create_timestamp <= self.current_timestamp and not self.on_going_task:
            self.on_going_task = True
            safe_ensure_future(self.async_task())


    async def async_task(self):
        cancels = await self.cancel_all_orders()
        if not all([result.success for result in cancels[0]]):
            self.logger().warning("There was an error when trying to cancel an order, retrying...")
            self.on_going_task = False
            return
        price = await self.connectors["uniswap_ethereum_goerli"].get_quote_price("WETH-UNI", True, self.buy_quote_amount, True)
        self.logger().info(f"Price: {price}")
        self.buy("uniswap_ethereum_goerli", "WETH-UNI", self.buy_quote_amount, OrderType.LIMIT, price)
        self.last_ordered_ts = self.current_timestamp


    async def cancel_all_orders(self):
        tasks = [exchange.cancel_all(timeout_seconds=5) for exchange in self.connectors.values()]
        cancels = await asyncio.gather(*tasks)
        return cancels
        
    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        """
        Method called when the connector notifies a buy order has been created
        """
        self.logger().info(logging.INFO, f"The buy order {event.order_id} has been created")

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        """
        Method called when the connector notifies a sell order has been created
        """
        self.logger().info(logging.INFO, f"The sell order {event.order_id} has been created")

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Method called when the connector notifies that an order has been partially or totally filled (a trade happened)
        """
        self.logger().info(logging.INFO, f"The order {event.order_id} has been filled")

    def did_fail_order(self, event: MarketOrderFailureEvent):
        """
        Method called when the connector notifies an order has failed
        """
        self.logger().info(logging.INFO, f"The order {event.order_id} failed")

    def did_cancel_order(self, event: OrderCancelledEvent):
        """
        Method called when the connector notifies an order has been cancelled
        """
        self.logger().info(f"The order {event.order_id} has been cancelled")

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        """
        Method called when the connector notifies a buy order has been completed (fully filled)
        """
        self.logger().info(f"The buy order {event.order_id} has been completed")

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        """
        Method called when the connector notifies a sell order has been completed (fully filled)
        """
        self.logger().info(f"The sell order {event.order_id} has been completed")
