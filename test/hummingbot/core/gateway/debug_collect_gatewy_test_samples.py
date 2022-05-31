#!/usr/bin/env python

"""
Script for collecting the gateway http client fixture data.

This is included for record purpose only. If you need to collect another batch of fixture data, you'll need to modify
the ETH address and nonce numbers.
"""

import asyncio
from decimal import Decimal
from os.path import join, realpath
from test.mock.http_recorder import HttpRecorder

from bin import path_util  # noqa: F401
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    load_client_config_map_from_file,
    read_system_configs_from_yml,
)
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


async def main():
    client_config_map: ClientConfigAdapter = load_client_config_map_from_file()
    await read_system_configs_from_yml()
    client_config_map.gateway.gateway_api_port = 5000

    fixture_db_path: str = realpath(join(__file__, "../fixtures/gateway_http_client_fixture.db"))
    http_recorder: HttpRecorder = HttpRecorder(fixture_db_path)
    with http_recorder.patch_aiohttp_client():
        gateway_http_client: GatewayHttpClient = GatewayHttpClient()

        print("ping gateway:", await gateway_http_client.ping_gateway())
        print("gateway status:", await gateway_http_client.get_gateway_status())
        print("add wallet:",
              await gateway_http_client.add_wallet(
                  "ethereum",
                  "ropsten",
                  "0000000000000000000000000000000000000000000000000000000000000001"        # noqa: mock
              ))
        print("get wallets:", await gateway_http_client.get_wallets())
        print("get connectors:", await gateway_http_client.get_connectors())
        print("set configuration:", await gateway_http_client.update_config("telemetry.enabled", False))
        print("get configuration:", await gateway_http_client.get_configuration())
        print("get tokens:", await gateway_http_client.get_tokens("ethereum", "ropsten"))
        print("get network status:", await gateway_http_client.get_network_status("ethereum", "ropsten"))
        print("get price:",
              await gateway_http_client.get_price(
                  "ethereum",
                  "ropsten",
                  "uniswap",
                  "DAI",
                  "WETH",
                  Decimal(1000),
                  TradeType.BUY
              ))
        print("get balances:",
              await gateway_http_client.get_balances(
                  "ethereum",
                  "ropsten",
                  "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
                  ["WETH", "DAI"],
              ))
        print("get transaction status:",
              await gateway_http_client.get_transaction_status(
                  "ethereum",
                  "ropsten",
                  "0xa8d428627dc7f453be79a32129dc18ea29d1a715249a4a5762ca6273da5d96e3"      # noqa: mock
              ))
        print("get transaction status:",
              await gateway_http_client.get_transaction_status(
                  "ethereum",
                  "ropsten",
                  "0xa8d428627dc7f453be79a32129dc18ea29d1a715249a4a5762ca6273da5d96e1"      # noqa: mock
              ))
        print("get evm nonce:",
              await gateway_http_client.get_evm_nonce(
                  "ethereum",
                  "ropsten",
                  "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92"
              ))
        print("approve WETH:",
              await gateway_http_client.approve_token(
                  "ethereum",
                  "ropsten",
                  "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
                  "WETH",
                  "uniswap",
                  2
              ))
        print("approve DAI:",
              await gateway_http_client.approve_token(
                  "ethereum",
                  "ropsten",
                  "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
                  "DAI",
                  "uniswap",
                  3
              ))
        print("get WETH, DAI allowance:",
              await gateway_http_client.get_allowances(
                  "ethereum",
                  "ropsten",
                  "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
                  ["WETH", "DAI"],
                  "uniswap"
              ))
        print("buy DAI with WETH:",
              await gateway_http_client.amm_trade(
                  "ethereum",
                  "ropsten",
                  "uniswap",
                  "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
                  "DAI",
                  "WETH",
                  TradeType.BUY,
                  Decimal(1000),
                  Decimal("0.00266"),
                  4
              ))


if __name__ == "__main__":
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    try:
        ev_loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
