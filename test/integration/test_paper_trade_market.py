#!/usr/bin/env python

import asyncio
import contextlib
import unittest
import os
from os.path import join, realpath
import time

from hummingbot.core.clock import (
    ClockMode,
    Clock
)
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketReceivedAssetEvent,
    MarketWithdrawAssetEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeFee,
    TradeType,
    MarketOrderFailureEvent
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.market.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.market.paper_trade.paper_trade_market import PaperTradeMarket, QueuedOrder
from hummingbot.market.paper_trade.symbol_pair import SymbolPair
from hummingbot.market.paper_trade.market_config import MarketConfig

from typing import List


class PaperTradePlaceOrdersTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]

    market: PaperTradeMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: PaperTradeMarket = PaperTradeMarket(
            order_book_tracker=BinanceOrderBookTracker(symbols=["ETHUSDT"]),
            config=MarketConfig.default_config()
        )
        print("Initializing PaperTrade place orders market... this will take about a minute.")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
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
        self.db_path: str = realpath(join(__file__, "../binance_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
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

    def testPlaceLimitOrders(self):
        """Tests that limit orders can be placed"""
        self.market.add_symbol_pair(SymbolPair("ETH", "USDT"))
        self.market.sell("ETHUSDT", 30, OrderType.LIMIT, 100)
        list_limit_orders: List[LimitOrder] = self.market.limit_orders
        first_limit_order: LimitOrder = list_limit_orders[0]
        self.assertEqual(first_limit_order.base_currency, "ETH", msg="Base currency is incorrect")
        self.assertEqual(first_limit_order.quote_currency, "USDT", msg="Quote currency is incorrect")
        self.assertFalse(first_limit_order.is_buy, msg="Limit order is not sell")
        self.assertEqual(first_limit_order.symbol, "ETHUSDT", msg="Symbol is incorrect")
        self.assertEqual(first_limit_order.price, 100, msg="Price is incorrect")
        self.assertEqual(first_limit_order.quantity, 30, msg="Quantity is incorrect")
        self.assertEqual(len(list_limit_orders), 1, msg="First limit order did not get added")

        self.market.add_symbol_pair(SymbolPair("BTC", "BNB"))
        self.market.buy("BTCBNB", 23, OrderType.LIMIT, 34)
        list_limit_orders: List[LimitOrder] = self.market.limit_orders
        second_limit_order: LimitOrder = list_limit_orders[0]
        self.assertEqual(second_limit_order.base_currency, "BTC", msg="Base currency is incorrect")
        self.assertEqual(second_limit_order.quote_currency, "BNB", msg="Quote currency is incorrect")
        self.assertTrue(second_limit_order.is_buy, msg="Limit order is not buy")
        self.assertEqual(second_limit_order.symbol, "BTCBNB", msg="Symbol is incorrect")
        self.assertEqual(second_limit_order.price, 34, msg="Price is incorrect")
        self.assertEqual(second_limit_order.quantity, 23, msg="Quantity is incorrect")
        self.assertEqual(len(list_limit_orders), 2, msg="Second limit order did not get added")

    def testPlaceMarketOrders(self):
        self.market.add_symbol_pair(SymbolPair("ETH", "USDT"))
        self.market.sell("ETHUSDT", 30, OrderType.MARKET)
        list_queued_orders: List[QueuedOrder] = self.market.queued_orders
        first_queued_order: QueuedOrder = list_queued_orders[0]
        self.assertFalse(first_queued_order.is_buy, msg="Market order is not sell")
        self.assertEqual(first_queued_order.symbol, "ETHUSDT", msg="Symbol is incorrect")
        self.assertEqual(first_queued_order.amount, 30, msg="Quantity is incorrect")
        self.assertEqual(len(list_queued_orders), 1, msg="First market order did not get added")

        # Figure out why this test is failing
        self.market.add_symbol_pair(SymbolPair("BTC", "BNB"))
        self.market.buy("BTCBNB", 30, OrderType.MARKET)
        list_queued_orders: List[QueuedOrder] = self.market.queued_orders
        second_queued_order: QueuedOrder = list_queued_orders[1]
        self.assertTrue(second_queued_order.is_buy, msg="Market order is not buy")
        self.assertEqual(second_queued_order.symbol, "BTCBNB", msg="Symbol is incorrect")
        self.assertEqual(second_queued_order.amount, 30, msg="Quantity is incorrect")
        self.assertEqual(second_queued_order.amount, 30, msg="Quantity is incorrect")
        self.assertEqual(len(list_queued_orders), 2, msg="Second market order did not get added")


class PaperTradeExecuteMarketOrdersTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]

    market: PaperTradeMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: PaperTradeMarket = PaperTradeMarket(
            order_book_tracker=BinanceOrderBookTracker(symbols=["ETHUSDT"]),
            config=MarketConfig.default_config()
        )
        print("Initializing PaperTrade execute orders market... this will take about a minute.")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
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
        self.db_path: str = realpath(join(__file__, "../binance_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)
        self.market.add_symbol_pair(SymbolPair("ETH", "USDT"))

    def tearDown(self):
        for event_tag in self.events:
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

    def testExecuteMarketOrders(self):
        self.market.set_balance("ETH", 20)
        self.market.set_balance("USDT", 100)
        self.market.sell("ETHUSDT", 10, OrderType.MARKET)
        self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        self.assertEquals(10, self.market.get_balance("ETH"), msg="Balance was not updated.")
        self.market.buy("ETHUSDT", 5, OrderType.MARKET)
        self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        self.assertEquals(15, self.market.get_balance("ETH"), msg="Balance was not updated.")

    def testExecuteLimitOrders(self):
        self.market.set_balance("ETH", 20)
        self.market.set_balance("USDT", 100)
        self.market.sell("ETHUSDT", 10, OrderType.LIMIT, 100)
        self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        self.assertEquals(10, self.market.get_balance("ETH"), msg="ETH Balance was not updated.")
        self.assertEquals(1100, self.market.get_balance("USDT"), msg="USDT Balance was not updated.")
        self.market.buy("ETHUSDT", 1, OrderType.LIMIT, 500)
        self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        self.assertEquals(11, self.market.get_balance("ETH"), msg="ETH Balance was not updated.")
        self.assertEquals(600, self.market.get_balance("USDT"), msg="USDT Balance was not updated.")
