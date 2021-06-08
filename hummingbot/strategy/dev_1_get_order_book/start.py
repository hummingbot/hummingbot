#!/usr/bin/env python

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.dev_1_get_order_book import GetOrderBookStrategy
from hummingbot.strategy.dev_1_get_order_book.dev_1_get_order_book_config_map import dev_1_get_order_book_config_map


def start(self):
    try:
        exchange: str = dev_1_get_order_book_config_map.get("exchange").value.lower()
        trading_pair: str = dev_1_get_order_book_config_map.get("trading_pair").value

        self._initialize_markets([(exchange, [trading_pair])])

        exchange: ExchangeBase = self.markets[exchange]

        self.strategy = GetOrderBookStrategy(exchange=exchange,
                                             trading_pair=trading_pair,
                                             )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
