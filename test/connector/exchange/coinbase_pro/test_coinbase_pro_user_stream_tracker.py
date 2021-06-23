#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import logging
import time
import asyncio
import contextlib
from decimal import Decimal
from typing import Optional
import unittest
import conf
from hummingbot.core.clock import (
    Clock,
    ClockMode
)

from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book_message import CoinbaseProOrderBookMessage
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_exchange import CoinbaseProExchange, CoinbaseProAuth
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_user_stream_tracker import CoinbaseProUserStreamTracker
from hummingbot.core.event.events import OrderType


class CoinbaseProUserStreamTrackerUnitTest(unittest.TestCase):
    user_stream_tracker: Optional[CoinbaseProUserStreamTracker] = None

    market: CoinbaseProExchange
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.coinbase_pro_auth = CoinbaseProAuth(conf.coinbase_pro_api_key,
                                                conf.coinbase_pro_secret_key,
                                                conf.coinbase_pro_passphrase)
        cls.trading_pairs = ["ETH-USDC"]
        cls.user_stream_tracker: CoinbaseProUserStreamTracker = CoinbaseProUserStreamTracker(
            coinbase_pro_auth=cls.coinbase_pro_auth, trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: CoinbaseProExchange = CoinbaseProExchange(
            conf.coinbase_pro_api_key,
            conf.coinbase_pro_secret_key,
            conf.coinbase_pro_passphrase,
            trading_pairs=cls.trading_pairs
        )
        print("Initializing Coinbase Pro market... this will take about a minute.")
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

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

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_limit_order_cancelled(self):
        """
        This test should be run after the developer has implemented the limit buy and cancel
        in the corresponding market class
        """
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.1"))
        trading_pair = self.trading_pairs[0]
        amount: Decimal = Decimal("0.02")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        bid_price: Decimal = current_bid_price * Decimal("0.8")
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

        client_order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)

        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        [open_message] = self.run_parallel(self.user_stream_tracker.user_stream.get())

        # print(open_message)
        self.assertTrue(isinstance(open_message, CoinbaseProOrderBookMessage))
        self.assertEqual(open_message.trading_pair, trading_pair)
        self.assertEqual(open_message.content["type"], "open")
        self.assertEqual(open_message.content["side"], "buy")
        self.assertEqual(open_message.content["product_id"], trading_pair)
        self.assertEqual(Decimal(open_message.content["price"]), quantize_bid_price)
        self.assertEqual(Decimal(open_message.content["remaining_size"]), quantized_amount)

        self.run_parallel(asyncio.sleep(5.0))
        self.market.cancel(trading_pair, client_order_id)

        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        [done_message] = self.run_parallel(self.user_stream_tracker.user_stream.get())

        # print(done_message)
        self.assertEqual(done_message.trading_pair, trading_pair)
        self.assertEqual(done_message.content["type"], "done")
        self.assertEqual(done_message.content["side"], "buy")
        self.assertEqual(done_message.content["product_id"], trading_pair)
        self.assertEqual(Decimal(done_message.content["price"]), quantize_bid_price)
        self.assertEqual(Decimal(done_message.content["remaining_size"]), quantized_amount)
        self.assertEqual(done_message.content["reason"], "canceled")

    @unittest.skip
    def test_limit_order_filled(self):
        """
        This test should be run after the developer has implemented the limit buy in the corresponding market class
        """
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.1"))
        trading_pair = self.trading_pairs[0]
        amount: Decimal = Decimal("0.02")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        bid_price: Decimal = current_bid_price * Decimal("1.05")
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

        self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)

        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        [message_1, message_2] = self.run_parallel(self.user_stream_tracker.user_stream.get(),
                                                   self.user_stream_tracker.user_stream.get())
        self.assertTrue(isinstance(message_1, CoinbaseProOrderBookMessage))
        self.assertTrue(isinstance(message_2, CoinbaseProOrderBookMessage))
        if message_1.content["type"] == "done":
            done_message = message_1
            match_message = message_2
        else:
            done_message = message_2
            match_message = message_1

        # print(done_message)
        self.assertEqual(done_message.trading_pair, trading_pair)
        self.assertEqual(done_message.content["type"], "done")
        self.assertEqual(done_message.content["side"], "buy")
        self.assertEqual(done_message.content["product_id"], trading_pair)
        self.assertEqual(Decimal(done_message.content["price"]), quantize_bid_price)
        self.assertEqual(Decimal(done_message.content["remaining_size"]), Decimal(0.0))
        self.assertEqual(done_message.content["reason"], "filled")

        # print(match_message)
        self.assertEqual(match_message.trading_pair, trading_pair)
        self.assertEqual(match_message.content["type"], "match")
        self.assertEqual(match_message.content["side"], "sell")
        self.assertEqual(match_message.content["product_id"], trading_pair)
        self.assertLessEqual(Decimal(match_message.content["price"]), quantize_bid_price)
        self.assertEqual(Decimal(match_message.content["size"]), quantized_amount)

    @unittest.skip
    def test_user_stream_manually(self):
        """
        This test should be run before market functions like buy and sell are implemented.
        Developer needs to manually trigger those actions in order for the messages to show up in the user stream.
        """
        self.ev_loop.run_until_complete(asyncio.sleep(30.0))
        print(self.user_stream_tracker.user_stream)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
