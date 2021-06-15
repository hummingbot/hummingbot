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
from hummingbot.connector.exchange.eterbase.eterbase_order_book_message import EterbaseOrderBookMessage
from hummingbot.connector.exchange.eterbase.eterbase_exchange import EterbaseExchange, EterbaseAuth
from hummingbot.connector.exchange.eterbase.eterbase_user_stream_tracker import EterbaseUserStreamTracker
from hummingbot.core.event.events import OrderType


class EterbaseUserStreamTrackerUnitTest(unittest.TestCase):
    user_stream_tracker: Optional[EterbaseUserStreamTracker] = None

    market: EterbaseExchange
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.eterbase_auth = EterbaseAuth(conf.eterbase_api_key,
                                         conf.eterbase_secret_key)
        cls.trading_pairs = ["ETHEUR"]
        cls.user_stream_tracker: EterbaseUserStreamTracker = EterbaseUserStreamTracker(
            eterbase_auth=cls.eterbase_auth, eterbase_account=conf.eterbase_account, trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: EterbaseExchange = EterbaseExchange(
            conf.eterbase_api_key,
            conf.eterbase_secret_key,
            conf.eterbase_account,
            trading_pairs=cls.trading_pairs
        )
        print("Initializing Eterbase market... this will take about a minute.")
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
#        bid_price: Decimal = current_bid_price  + Decimal("0.05") * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

        client_order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)

        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        [open_message] = self.run_parallel(self.user_stream_tracker.user_stream.get())

        self.assertTrue(isinstance(open_message, EterbaseOrderBookMessage))
        self.assertEqual(open_message.trading_pair, trading_pair)
        self.assertEqual(open_message.content["type"], "o_placed")
        self.assertEqual(open_message.content["side"], 1)
        self.assertEqual(open_message.content["marketId"], 51)
        self.assertGreaterEqual(Decimal(open_message.content["limitPrice"]), quantize_bid_price)
        self.assertEqual(Decimal(open_message.content["qty"]), quantized_amount)

        self.run_parallel(asyncio.sleep(5.0))
        self.market.cancel(trading_pair, client_order_id)

        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        [done_message] = self.run_parallel(self.user_stream_tracker.user_stream.get())

        self.assertEqual(done_message.trading_pair, trading_pair)
        self.assertEqual(done_message.content["type"], "o_closed")
        self.assertEqual(done_message.content["side"], 1)
        self.assertEqual(done_message.content["marketId"], 51)
        self.assertGreaterEqual(Decimal(done_message.content["price"]), quantize_bid_price)
        self.assertEqual(Decimal(done_message.content["qty"]), quantized_amount)
        self.assertEqual(done_message.content["closeReason"], "USER_REQUESTED_CANCEL")

#    @unittest.skip
    def test_limit_order_filled(self):
        """
        This test should be run after the developer has implemented the limit buy in the corresponding market class
        """
        market_id = 51

        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.1"))
        trading_pair = self.trading_pairs[0]
        amount: Decimal = Decimal("0.02")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        bid_price: Decimal = current_bid_price * Decimal("1.05")
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

        self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)

        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        [message_0, message_1, message_2] = self.run_parallel(self.user_stream_tracker.user_stream.get(),
                                                              self.user_stream_tracker.user_stream.get(),
                                                              self.user_stream_tracker.user_stream.get())

        self.assertTrue(isinstance(message_0, EterbaseOrderBookMessage))
        self.assertTrue(isinstance(message_1, EterbaseOrderBookMessage))
        self.assertTrue(isinstance(message_2, EterbaseOrderBookMessage))

        if message_1.content["type"] == "o_closed":
            done_message = message_1
        elif message_1.content["type"] == "o_fill":
            match_message = message_1
        elif message_1.content["type"] == "o_placed":
            placed_message = message_1

        if message_2.content["type"] == "o_closed":
            done_message = message_2
        elif message_2.content["type"] == "o_fill":
            match_message = message_2
        elif message_2.content["type"] == "o_placed":
            placed_message = message_2

        if message_0.content["type"] == "o_closed":
            done_message = message_0
        elif message_0.content["type"] == "o_fill":
            match_message = message_0
        elif message_0.content["type"] == "o_placed":
            placed_message = message_0

        self.assertEqual(placed_message.trading_pair, trading_pair)
        self.assertEqual(placed_message.content["type"], "o_placed")
        self.assertEqual(placed_message.content["marketId"], market_id)
        self.assertLessEqual(Decimal(placed_message.content["limitPrice"]), quantize_bid_price)
        self.assertLessEqual(Decimal(placed_message.content["qty"]), quantized_amount)

        self.assertEqual(match_message.trading_pair, trading_pair)
        self.assertEqual(match_message.content["type"], "o_fill")
        self.assertEqual(match_message.content["marketId"], market_id)
        self.assertLessEqual(Decimal(match_message.content["price"]), quantize_bid_price)
        self.assertEqual(Decimal(match_message.content["remainingQty"]), Decimal(0.0))
        self.assertEqual(Decimal(match_message.content["qty"]), quantized_amount)

        self.assertEqual(done_message.trading_pair, trading_pair)
        self.assertEqual(done_message.content["type"], "o_closed")
        self.assertEqual(done_message.content["marketId"], market_id)
        self.assertLessEqual(Decimal(done_message.content["price"]), quantize_bid_price)
        self.assertEqual(done_message.content["closeReason"], "FILLED")

    @unittest.skip
    def test_user_stream_manually(self):
        """
        This test should be run before market functions like buy and sell are implemented.
        Developer needs to manually trigger those actions in order for the messages to show up in the user stream.
        """
        self.ev_loop.run_until_complete(asyncio.sleep(30.0))
        print(self.user_stream_tracker.user_stream)


def main():
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()


if __name__ == "__main__":
    main()
