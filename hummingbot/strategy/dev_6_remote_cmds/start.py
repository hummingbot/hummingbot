#!/usr/bin/env python

from hummingbot.strategy.dev_6_remote_cmds.dev_6_remote_cmds_config_map import dev_6_remote_cmds_config_map
from hummingbot.strategy.dev_6_remote_cmds import RemoteCmdsStrategy


def start(self):
    try:
        exchange = dev_6_remote_cmds_config_map.get("exchange").value.lower()
        trading_pair = dev_6_remote_cmds_config_map.get("trading_pair").value
        asset = dev_6_remote_cmds_config_map.get("asset").value

        self._initialize_markets([(exchange, [trading_pair])])

        exchange = self.markets[exchange]

        self.strategy = RemoteCmdsStrategy(exchange=exchange,
                                           trading_pair=trading_pair,
                                           asset=asset,
                                           )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
