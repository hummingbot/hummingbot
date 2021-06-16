#!/usr/bin/env python
from os.path import join, realpath
import sys

import asyncio
import conf
import contextlib
import logging
import os
import time
from typing import List
import unittest

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    WalletEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderCancelledEvent,
    TradeType,
    TradeFee,
)
from hummingbot.connector.exchange.dolomite.dolomite_exchange import DolomiteExchange
from hummingbot.core.event.events import OrderType
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet

sys.path.insert(0, realpath(join(__file__, "../../../../../")))


class DolomiteExchangeUnitTest(unittest.TestCase):
    market_events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
    ]

    wallet_events: List[WalletEvent] = [WalletEvent.WrappedEth, WalletEvent.UnwrappedEth]

    wallet: Web3Wallet
    market: DolomiteExchange
    market_logger: EventLogger
    wallet_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.wallet = Web3Wallet(
            private_key=conf.dolomite_test_web3_private_key,
            backend_urls=conf.test_web3_provider_list,
            erc20_token_addresses=[conf.dolomite_test_web3_address],
            chain=EthereumChain.MAIN_NET,
        )
        cls.market: DolomiteExchange = DolomiteExchange(
            wallet=cls.wallet,
            ethereum_rpc_url=conf.test_web3_provider_list[0],
            order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
            isTestNet=True,
            trading_pairs=["WETH-DAI"],
        )
        print("Initializing Dolomite market... ")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.wallet)
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../dolomite_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        self.wallet_logger = EventLogger()
        for event_tag in self.market_events:
            self.market.add_listener(event_tag, self.market_logger)
        for event_tag in self.wallet_events:
            self.wallet.add_listener(event_tag, self.wallet_logger)

    def tearDown(self):
        for event_tag in self.market_events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None
        for event_tag in self.wallet_events:
            self.wallet.remove_listener(event_tag, self.wallet_logger)
        self.wallet_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = asyncio.ensure_future(asyncio.gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    # ====================================================

    def test_get_fee(self):
        limit_trade_fee: TradeFee = self.market.get_fee("WETH", "DAI", OrderType.LIMIT, TradeType.BUY, 10000, 1)
        self.assertLess(limit_trade_fee.percent, 0.01)
        self.assertEqual(len(limit_trade_fee.flat_fees), 0)
        market_trade_fee: TradeFee = self.market.get_fee("WETH", "DAI", OrderType.MARKET, TradeType.BUY, 0.1)
        self.assertGreater(market_trade_fee.percent, 0)
        self.assertEqual(len(market_trade_fee.flat_fees), 1)
        self.assertEqual(market_trade_fee.flat_fees[0][0], "DAI")

    def test_get_wallet_balances(self):
        balances = self.market.get_all_balances()
        self.assertGreaterEqual((balances["WETH"]), 0)
        self.assertGreaterEqual((balances["DAI"]), 0)

    def test_get_available_balances(self):
        balance = self.market.get_available_balance("WETH")
        self.assertGreaterEqual(balance, 0)

    def test_limit_orders(self):
        orders = self.market.limit_orders
        self.assertGreaterEqual(len(orders), 0)

    def test_cancel_order(self):
        trading_pair = "WETH-DAI"
        bid_price: float = self.market.get_price(trading_pair, True)
        amount = 0.5

        # Intentionally setting invalid price to prevent getting filled
        client_order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT, bid_price * 0.7)
        self.run_parallel(asyncio.sleep(1.0))
        self.market.cancel(trading_pair, client_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event

        self.run_parallel(asyncio.sleep(6.0))
        self.assertEqual(0, len(self.market.limit_orders))
        self.assertEqual(client_order_id, order_cancelled_event.order_id)

    def test_place_limit_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("WETH"), 0.4)
        self.assertGreater(self.market.get_balance("DAI"), 60)

        # Try to buy 0.2 WETH from the exchange, and watch for creation event.
        trading_pair = "WETH-DAI"
        bid_price: float = self.market.get_price(trading_pair, True)
        amount: float = 0.4
        buy_order_id: str = self.market.buy(trading_pair, amount, OrderType.LIMIT, bid_price * 0.7)
        [buy_order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(buy_order_id, buy_order_created_event.order_id)
        self.market.cancel(trading_pair, buy_order_id)
        [_] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

        # Try to sell 0.2 WETH to the exchange, and watch for creation event.
        ask_price: float = self.market.get_price(trading_pair, False)
        sell_order_id: str = self.market.sell(trading_pair, amount, OrderType.LIMIT, ask_price * 1.5)
        [sell_order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        self.assertEqual(sell_order_id, sell_order_created_event.order_id)
        self.market.cancel(trading_pair, sell_order_id)
        [_] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

    @unittest.skipUnless(
        any("test_place_market_buy_and_sell" in arg for arg in sys.argv),
        "test_place_market_buy_and_sell test requires manual action.",
    )
    def test_place_market_buy_and_sell(self):
        # Cannot trade between yourself on Dolomite. Testing this is... hard.
        # These orders use the same code as limit orders except for fee calculation
        # and setting a field in the http request to "MARKET" instead of "LIMIT".
        # Fee calculations for market orders is tested above
        pass


def main():
    logging.basicConfig(level=logging.ERROR)
    unittest.main()


if __name__ == "__main__":
    main()
