#!/usr/bin/env python

# this script is to test the cancel functionality of GatewayEVMAMM and gateway

import path_util        # noqa: F401
import asyncio
from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from decimal import Decimal
from hummingbot.connector.gateway_EVM_AMM import GatewayEVMAMM

# development values used
# uniswap-ethereum-kovan

# my wallet already had a balance of WETH and DAI

# WETH
# 0xd0a1e359811322d97991e03f863a0c30c2cf029c

# DAI
# 0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa

# I set gateway/conf/ethereum.yml 'manualGasPrice' to '1'
# I set gateway/conf/ethereum-gas-station.yml 'enabled' to 'false'
# Run gateway from source, then run this script
# In the python logs you can see the in flight order and most likely it
# will print in the cancelling state.
# In the gateway logs you should see the transaction hash and nonce of the
# trade and the cancel of the trade.


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

    order_result = gateway.place_order(True, "WETH-DAI", amount, price + Decimal("1000"))
    print(order_result)
    await asyncio.sleep(3)

    # while True:
    #     await gateway.update_order_status(gateway.amm_orders)
    #     print(f"{gateway._in_flight_orders}")
    #     await asyncio.sleep(2)

    # cancel logic
    await gateway.update_order_status(gateway.amm_orders)

    # await asyncio.sleep(10)
    cancel_result = await gateway.cancel_outdated_orders(0)
    print(cancel_result)

    print("waiting")
    await asyncio.sleep(3)
    await gateway.update_order_status(gateway.amm_orders)
    print(f"{gateway._in_flight_orders}")
    # print("complete")

if __name__ == "__main__":
    asyncio.run(main())
