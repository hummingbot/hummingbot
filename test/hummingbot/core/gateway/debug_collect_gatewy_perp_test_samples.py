#!/usr/bin/env python

"""
Script for collecting the gateway http client fixture data.

This is included for record purpose only. If you need to collect another batch of fixture data, you'll need to modify
the ETH address and nonce numbers.
"""

import asyncio
from decimal import Decimal
from os.path import join, realpath

from bin import path_util  # noqa: F401
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    load_client_config_map_from_file,
    read_system_configs_from_yml,
)
from hummingbot.core.data_type.common import PositionSide
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


async def main():
    from test.mock.http_recorder import HttpRecorder
    client_config_map: ClientConfigAdapter = load_client_config_map_from_file()
    await read_system_configs_from_yml()

    fixture_db_path: str = realpath(join(__file__, "../fixtures/gateway_perp_http_client_fixture.db"))
    http_recorder: HttpRecorder = HttpRecorder(fixture_db_path)
    with http_recorder.patch_aiohttp_client():
        gateway_http_client: GatewayHttpClient = GatewayHttpClient.get_instance(client_config_map=client_config_map)

        print("ping gateway:", await gateway_http_client.ping_gateway())
        print("gateway status:", await gateway_http_client.get_gateway_status())
        print("add wallet:",
              await gateway_http_client.add_wallet(
                  "ethereum",
                  "optimism",
                  "0000000000000000000000000000000000000000000000000000000000000001"        # noqa: mock
              ))
        print("get wallets:", await gateway_http_client.get_wallets())
        print("get connectors:", await gateway_http_client.get_connectors())
        print("get market list:",
              await gateway_http_client.get_perp_markets(
                  "ethereum",
                  "optimism",
                  "perp",
              ))
        print("get market status:",
              await gateway_http_client.get_perp_market_status(
                  "ethereum",
                  "optimism",
                  "perp",
                  "AAVE",
                  "USD",
              ))
        print("get market price:",
              await gateway_http_client.get_perp_market_price(
                  "ethereum",
                  "optimism",
                  "perp",
                  "AAVE",
                  "USD",
                  Decimal("0.1"),
                  PositionSide.LONG,
              ))
        print("get USD balance:",
              await gateway_http_client.amm_perp_balance(
                  "ethereum",
                  "optimism",
                  "perp",
                  "0xefB7Be8631d154d4C0ad8676FEC0897B2894FE8F",
              ))
        print("open long position:",
              await gateway_http_client.amm_perp_open(
                  "ethereum",
                  "optimism",
                  "perp",
                  "0xefB7Be8631d154d4C0ad8676FEC0897B2894FE8F",
                  "AAVE",
                  "USD",
                  PositionSide.LONG,
                  Decimal("0.1"),
                  Decimal("63"),
              ))
        print("get active position:",
              await gateway_http_client.get_perp_position(
                  "ethereum",
                  "optimism",
                  "perp",
                  "0xefB7Be8631d154d4C0ad8676FEC0897B2894FE8F",
                  "AAVE",
                  "USD",
              ))
        print("close long position:",
              await gateway_http_client.amm_perp_close(
                  "ethereum",
                  "optimism",
                  "perp",
                  "0xefB7Be8631d154d4C0ad8676FEC0897B2894FE8F",
                  "AAVE",
                  "USD",
              ))


if __name__ == "__main__":
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    try:
        ev_loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
