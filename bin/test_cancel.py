#!/usr/bin/env python

import path_util        # noqa: F401
import asyncio
from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from decimal import Decimal
from hummingbot.connector.gateway_EVM_AMM import GatewayEVMAMM

# kovan values

# WETH
# 0xd0a1e359811322d97991e03f863a0c30c2cf029c

# DAI
# 0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa


async def main():
    await read_system_configs_from_yml()

    trading_pair = "WETH-DAI"

    gateway = GatewayEVMAMM(connector_name = "uniswap",
                            chain = "ethereum",
                            network = "kovan",
                            wallet_address = "0xFaA12FD102FE8623C9299c72B03E45107F2772B5",
                            trading_pairs = [trading_pair],
                            trading_required = True)

    await gateway.auto_approve()

    await gateway.update_balances()

    amount = Decimal("0.0001")

    price = await gateway.get_quote_price(trading_pair, True, amount)

    print(f"Price: {price}")

    result = gateway.place_order(True, "WETH-DAI", Decimal("0.0001"), price)
    print(result)
    print("waiting")
    await asyncio.sleep(100)
    print("complete")

if __name__ == "__main__":
    asyncio.run(main())
