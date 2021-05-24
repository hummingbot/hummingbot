#!/usr/bin/env python

from hummingbot.strategy.dev_0_hello_world.dev_0_hello_world_config_map import dev_0_hello_world_config_map
from hummingbot.strategy.dev_0_hello_world import HelloWorldStrategy


def start(self):
    try:
        exchange = dev_0_hello_world_config_map.get("exchange").value.lower()
        trading_pair = dev_0_hello_world_config_map.get("trading_pair").value
        asset = dev_0_hello_world_config_map.get("asset").value

        self._initialize_markets([(exchange, [trading_pair])])

        exchange = self.markets[exchange]

        self.strategy = HelloWorldStrategy(exchange=exchange,
                                           trading_pair=trading_pair,
                                           asset=asset,
                                           )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
