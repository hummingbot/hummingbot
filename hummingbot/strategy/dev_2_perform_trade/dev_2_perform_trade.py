#!/usr/bin/env python

import logging
import math
import pandas as pd
import time

from decimal import Decimal
from typing import (
    List,
    Set
)

from hummingbot.connector.connector_base import OrderType
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import (
    OrderFilledEvent,
    PriceType,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase


pts_logger = None
s_decimal_zero = Decimal('0')


class PerformTradeStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global pts_logger
        if pts_logger is None:
            pts_logger = logging.getLogger(__name__)
        return pts_logger

    def __init__(self,
                 exchange: ExchangeBase,
                 trading_pair: str,
                 is_buy: bool,
                 spread: Decimal,
                 order_amount: Decimal,
                 price_type: PriceType,
                 hb_app_notification: bool = False,
                 ):

        super().__init__()
        self._exchange = exchange
        self._trading_pair = trading_pair
        self._is_buy = is_buy
        self._spread = spread / Decimal("100")
        self._order_amount = order_amount
        self._price_type = price_type
        self._hb_app_notification = hb_app_notification

        self.add_markets([self._exchange])

        base, quote = trading_pair.split("-")
        self._market_info: MarketTradingPairTuple = MarketTradingPairTuple(exchange, trading_pair, base, quote)

        self._ready = False
        self._current_price = s_decimal_zero
        self._last_own_trade_price = s_decimal_zero
        self._order_refresh_time: float = -1
        self._tracked_order_ids: Set = set()

    @property
    def active_orders(self) -> List[LimitOrder]:
        limit_orders: List[LimitOrder] = self.order_tracker.active_limit_orders
        return [o[1] for o in limit_orders]

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            HummingbotApplication.main_application()._notify(msg)

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Method that is called when an OrderFilledEvent is triggered.
        Updates the _last_own_trade_price when a OrderFilledEvent is triggered.
        """
        msg = f"({self._trading_pair}) {'BUY' if self._is_buy else 'SELL'} order ({event.amount} @ {event.price}) " \
              f"{self._market_info.base_asset} is filled."
        self.notify_hb_app(msg)
        if event.order_id in self._tracked_order_ids:
            self._last_own_trade_price = event.price

    def format_status(self) -> str:
        if not self._ready:
            return f"{self._exchange.name} connector is not ready..."

        lines = []

        lines.extend(["", f"  Market: {self._exchange.name} | {self._trading_pair}\n"])

        if len(self.active_orders) > 0:
            columns = ["Type", "Price", "Amount", "Spread(%)", "Age"]
            data = []
            mid_price = self._exchange.get_mid_price(self._trading_pair)
            for order in self.active_orders:
                spread = abs(order.price - mid_price) / mid_price
                data.append([
                    "BUY" if self._is_buy else "SELL",
                    float(order.price),
                    float(order.quantity),
                    f"{spread:.3%}",
                    pd.Timestamp(int(time.time()) - int(order.client_order_id[-16:]) / 1e6,
                                 unit='s').strftime('%H:%M:%S')
                ])

            df = pd.DataFrame(data=data, columns=columns)
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])

        else:
            lines.extend(["", "  No active orders."])

        return "\n".join(lines)

    def _recalculate_price_parameter(self) -> Decimal:
        """
        Method responsible for recalculating the order price.
        Order price is updated when the mid_price/last_price differs from the previous order price.
        """

        new_price = None
        if self._price_type == PriceType.MidPrice:
            new_price = self._exchange.get_mid_price(self._trading_pair)
        elif self._price_type == PriceType.LastTrade:
            new_price = Decimal(self._exchange.get_order_book(self._trading_pair).last_trade_price)
            if math.isnan(new_price):
                self.logger().info("Unable to get last traded price. Using MidPrice instead.")
                new_price = self._exchange.get_mid_price(self._trading_pair)
        elif self._price_type == PriceType.LastOwnTrade:
            if self._last_own_trade_price == s_decimal_zero:
                self.logger().info("No Filled Orders. Using MidPrice instead.")
                new_price = self._exchange.get_mid_price(self._trading_pair)
            new_price = self._last_own_trade_price

        if self._is_buy:
            new_price = (Decimal('1') - self._spread) * new_price
        else:
            new_price = (Decimal('1') + self._spread) * new_price
        return new_price

    def _cancel_active_order(self):
        """
        Cancel all active orders.
        Note: cancel_order() is inherited from StrategyPyBase
        """
        current_orders = [o for o in self.active_orders if o.trading_pair == self._trading_pair]

        for order in current_orders:
            self.cancel_order(market_trading_pair_tuple=self._market_info,
                              order_id=order.client_order_id)

    def _place_order(self, price: Decimal):
        """
        Places the order with the specified order price.
        Note: buy_with_specific_market() and sell_with_specific_market() are functions inherited from StrategyBase
        """
        self.logger().info(f"({self._exchange.name}) Creating a {'BUY' if self._is_buy else 'SELL'} order. "
                           f"Order: {self._order_amount}{self._market_info[2]} @ {price}{self._market_info[3]}")

        if self._is_buy:
            order_id = self.buy_with_specific_market(
                market_trading_pair_tuple=self._market_info,
                amount=self._order_amount,
                order_type=OrderType.LIMIT_MAKER,
                price=price,
            )
        else:
            order_id = self.sell_with_specific_market(
                market_trading_pair_tuple=self._market_info,
                amount=self._order_amount,
                order_type=OrderType.LIMIT_MAKER,
                price=price,
            )

        self._tracked_order_ids.add(order_id)
        self._order_refresh_time = self.current_timestamp + 60

    def tick(self, timestamp: float):
        """
        Clock tick entry point. This method is executed every second (on normal tick interval settings)
        : param timestamp: current tick timestamp
        """
        if not self._ready:
            self._ready = self._exchange.ready

            if not self._exchange.ready:
                # Message output using self.logger() will be displayed on Log panel(right) and saved on the strategy's log file.
                self.logger().warning(f"{self._exchange.name} connector is not ready. Please wait...")
                return
            else:
                self.logger().info(f"{self._exchange.name} is ready. Trading started.")

        if timestamp >= self._order_refresh_time:

            new_price = self._recalculate_price_parameter()

            if self._current_price == new_price:
                self.logger().info(f"Current {self._price_type} did not deviate from previous {self._price_type}: {self._current_price}")
                return

            self._cancel_active_order()
            self._place_order(price=new_price)
            self._current_price = new_price
