#!/usr/bin/env python

import sys, os; sys.path.insert(0, os.path.realpath(os.path.join(__file__, "../../")))
import logging; logging.basicConfig(level=logging.INFO)

import argparse
import asyncio
from eth_account import Account
import getpass
import json
import pandas as pd
import time
from typing import (
    Dict,
    List
)

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.market.ddex.ddex_market import DDEXMarket
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet


class CmdlineParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__()
        self.add_argument("key_file", type=str, help="Encrypted key file for the test wallet.")
        self.add_argument("eth_node", type=str, help="Ethereum node URL.")


async def main():
    cmd_args = CmdlineParser().parse_args()
    with open(cmd_args.key_file, "r") as fd:
        encrypted_json: Dict[str, any] = json.load(fd)

    wallet: Web3Wallet = Web3Wallet(
        Account.decrypt(encrypted_json, getpass.getpass("Wallet password: ")),
        [cmd_args.eth_node],
        [],
        EthereumChain.MAIN_NET
    )
    market: DDEXMarket = DDEXMarket(
        wallet,
        cmd_args.eth_node
    )
    clock: Clock = Clock(ClockMode.REALTIME)
    clock.add_iterator(wallet)
    clock.add_iterator(market)

    with clock:
        orders: List[Dict[str, any]] = await market.list_orders()
        order_data: pd.DataFrame = pd.DataFrame(
            [(o["createdAt"], o["id"], o["marketId"]) for o in orders],
            columns=["Created", "OrderID", "TradingPair"]
        )
        order_data.Created = order_data.Created.astype("datetime64[ms]").astype("datetime64[ns, UTC]")
        order_data = order_data.set_index("Created")

        while True:
            try:
                sample_ids: List[str] = list(order_data.sample(10).OrderID)
                tasks: List[asyncio.Future] = [market.get_order(order_id) for order_id in sample_ids]
                response_data: List[Dict[str, any]] = await safe_gather(*tasks)

                mismatches: int = 0
                for expected_id, response in zip(sample_ids, response_data):
                    returned_order_id = response["id"]
                    if returned_order_id != expected_id:
                        print(f"    - Error: requested for {expected_id} but got {returned_order_id} back.")
                        mismatches += 1

                if mismatches < 1:
                    print(f"[{str(pd.Timestamp.utcnow())}] All fetches passed.")
                else:
                    print(f"[{str(pd.Timestamp.utcnow())}] {mismatches} out of 10 requests failed.")

                now: float = time.time()
                next_tick: float = now // 1 + 1
                await asyncio.sleep(next_tick - now)
            except asyncio.CancelledError:
                raise


if __name__ == "__main__":
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    try:
        ev_loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Done!")
