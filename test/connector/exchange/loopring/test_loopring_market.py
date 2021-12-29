
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
from decimal import Decimal

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    # WalletEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderCancelledEvent,
    TradeType,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.connector.exchange.loopring.loopring_exchange import LoopringExchange
from hummingbot.connector.exchange_base import OrderType
# from hummingbot.connector.exchange.loopring.loopring_auth import LoopringAuth

sys.path.insert(0, realpath(join(__file__, "../../../../../")))


class LoopringExchangeUnitTest(unittest.TestCase):
    market_events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
    ]

    market: LoopringExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: LoopringExchange = LoopringExchange(
            conf.loopring_accountid,
            conf.loopring_exchangeid,
            conf.loopring_private_key,
            conf.loopring_api_key,
            trading_pairs=["ETH-USDT"],
        )
        print("Initializing Loopring market... ")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
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
        self.db_path: str = realpath(join(__file__, "../loopring_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.market_events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.market_events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

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
        limit_trade_fee: AddedToCostTradeFee = self.market.get_fee(
            "ETH", "USDT", OrderType.LIMIT, TradeType.SELL, 10000, 1
        )
        self.assertLess(limit_trade_fee.percent, 0.01)

    def test_get_balances(self):
        balances = self.market.get_all_balances()
        self.assertGreaterEqual((balances["ETH"]), 0)
        self.assertGreaterEqual((balances["USDT"]), 0)

    def test_get_available_balances(self):
        balance = self.market.get_available_balance("ETH")
        self.assertGreaterEqual(balance, 0)

    def test_limit_orders(self):
        orders = self.market.limit_orders
        self.assertGreaterEqual(len(orders), 0)

    def test_cancel_order(self):
        self.assertGreater(self.market.get_balance("USDT"), 20)
        trading_pair = "ETH-USDT"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal("0.05")

        # Intentionally setting price far away from best ask
        client_order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT, bid_price * Decimal("0.5"))
        self.run_parallel(asyncio.sleep(1.0))
        self.market.cancel(trading_pair, client_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event

        self.run_parallel(asyncio.sleep(6.0))
        self.assertEqual(0, len(self.market.limit_orders))
        self.assertEqual(client_order_id, order_cancelled_event.order_id)

    def test_place_limit_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("USDT"), 20)

        # Try to buy 0.05 ETH from the exchange, and watch for creation event.
        trading_pair = "ETH-USDT"
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("0.05")
        buy_order_id: str = self.market.buy(trading_pair, amount, OrderType.LIMIT, ask_price * Decimal("1.5"))
        [buy_order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(buy_order_id, buy_order_created_event.order_id)

        # Try to sell 0.05 ETH to the exchange, and watch for creation event.
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        sell_order_id: str = self.market.sell(trading_pair, amount, OrderType.LIMIT, bid_price * Decimal("0.5"))
        [sell_order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        self.assertEqual(sell_order_id, sell_order_created_event.order_id)

    def test_place_market_buy_and_sell(self):
        # Market orders not supported on Loopring
        pass


def main():
    logging.basicConfig(level=logging.ERROR)
    unittest.main()


if __name__ == "__main__":
    main()
