#!/usr/bin/env python

import sys, os; sys.path.insert(0, os.path.realpath(os.path.join(__file__, "../../")))
import logging; logging.basicConfig(level=logging.INFO)

import asyncio
import time

from hummingbot.cli.config.config_helpers import get_erc20_token_addresses
from wings.wallet.web3_wallet import Web3Wallet
from wings.clock import Clock, ClockMode
from wings.market.ddex_market import DDEXMarket
from wings.ethereum_chain import EthereumChain
from wings.order_book_tracker import OrderBookTrackerDataSourceType

token_addresses = get_erc20_token_addresses(["WETH", "DAI"])
zrx_addr = "0x74622073a4821dbfd046E9AA2ccF691341A076e1"
pkey = "7BB21B1C4C9C0A474BCD08C1BA3C31ACEA8B6840AC72A67EDD38CB32899CBF87"
server = "http://aws-mainnet-1.mainnet-rpc-headless.mainnet:8545"
clock = Clock(ClockMode.REALTIME)
wallet = Web3Wallet(pkey, [server], token_addresses, chain=EthereumChain.MAIN_NET)
market = DDEXMarket(wallet,
                    server,
                    order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                    symbols=["WETH-DAI"])
clock.add_iterator(wallet)
clock.add_iterator(market)


async def main():
    begin = time.time() // 1
    while True:
        now = time.time() // 1
        await clock.run_til(now + 1)

        elapsed = clock.current_timestamp - begin
        if elapsed == 10:
            print(await market.get_order("0xcfcf8234d40069903d4592e7ad08a59612058e1cb66db38e681756140ddee3fe"))

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
