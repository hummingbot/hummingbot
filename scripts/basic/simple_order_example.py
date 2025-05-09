import logging
from decimal import Decimal

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy.strategy_py_base import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)


class SimpleOrder(ScriptStrategyBase):
    """
    This example script places an order on a Hummingbot exchange connector. The user can select the
    order type (market or limit), side (buy or sell) and the spread (for limit orders only).
    The bot uses the Rate Oracle to convert the order amount in USD to the base amount for the exchange and trading pair.
    The script uses event handlers to notify the user when the order is created and completed, and then stops the bot.
    """

    # Key Parameters
    order_amount_usd = Decimal(25)
    exchange = "kraken"
    base = "SOL"
    quote = "USDT"
    side = "buy"
    order_type = "market"   # market or limit
    spread = Decimal(0.01)  # for limit orders only

    # Other Parameters
    order_created = False
    markets = {
        exchange: {f"{base}-{quote}"}
    }

    def on_tick(self):
        if self.order_created is False:
            conversion_rate = RateOracle.get_instance().get_pair_rate(f"{self.base}-USDT")
            amount = self.order_amount_usd / conversion_rate
            price = self.connectors[self.exchange].get_mid_price(f"{self.base}-{self.quote}")

            # applies spread to price if order type is limit
            order_type = OrderType.MARKET if self.order_type == "market" else OrderType.LIMIT_MAKER
            if order_type == OrderType.LIMIT_MAKER and self.side == "buy":
                price = price * (1 - self.spread)
            else:
                if order_type == OrderType.LIMIT_MAKER and self.side == "sell":
                    price = price * (1 + self.spread)

            # places order
            if self.side == "sell":
                self.sell(
                    connector_name=self.exchange,
                    trading_pair=f"{self.base}-{self.quote}",
                    amount=amount,
                    order_type=order_type,
                    price=price
                )
            else:
                self.buy(
                    connector_name=self.exchange,
                    trading_pair=f"{self.base}-{self.quote}",
                    amount=amount,
                    order_type=order_type,
                    price=price
                )
            self.order_created = True

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"{event.trade_type.name} {event.amount} of {event.trading_pair} {self.exchange} at {event.price}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
        HummingbotApplication.main_application().stop()

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        msg = (f"Order {event.order_id} to buy {event.base_asset_amount} of {event.base_asset} is completed.")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        msg = (f"Order {event.order_id} to sell {event.base_asset_amount} of {event.base_asset} is completed.")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        msg = (f"Created BUY order {event.order_id}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        msg = (f"Created SELL order {event.order_id}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
