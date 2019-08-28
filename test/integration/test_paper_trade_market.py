#!/usr/bin/env python
from os.path import join, realpath
import sys;

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.event.event_reporter import EventReporter

sys.path.insert(0, realpath(join(__file__, "../../../")))
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
    MarketOrderFailureEvent,
    OrderBookTradeEvent, OrderBookEvent)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.market.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.market.paper_trade.paper_trade_market import PaperTradeMarket, QueuedOrder
from hummingbot.market.paper_trade.trading_pair import TradingPair
from hummingbot.market.paper_trade.market_config import MarketConfig
import pandas as pd
from typing import List, Tuple, Iterator
import logging; logging.basicConfig(level=logging.INFO)


class OrderBookUtils:
    @classmethod
    def ob_rows_data_frame(cls, ob_rows):
        data = []
        try:
            for ob_row in ob_rows:
                data.append([
                    ob_row.price, ob_row.amount
                ])
            df = pd.DataFrame(data=data, columns=[
                "price", "amount"])
            df.index = df.price
            return df
        except Exception as e:
            print(f"Error formatting market stats. {e}")

    @classmethod
    def get_compare_df(cls, row_it_1: Iterator[OrderBookRow], row_it_2: Iterator[OrderBookRow],
                       n_rows: int = 20000, diffs_only: bool = False) -> pd.DataFrame:
        rows_1 = list(row_it_1)
        rows_2 = list(row_it_2)
        book_1: pd.DataFrame = cls.ob_rows_data_frame(rows_1)
        book_2: pd.DataFrame = cls.ob_rows_data_frame(rows_2)
        book_1.index = book_1.price
        book_2.index = book_2.price
        compare_df: pd.DataFrame = pd.concat([book_1.iloc[0:n_rows], book_2.iloc[0:n_rows]],
                                             axis="columns", keys=["pre", "post"])
        compare_df = compare_df.fillna(0.0)
        compare_df['diff'] = compare_df['pre'].amount - compare_df['post'].amount
        if not diffs_only:
            return compare_df
        else:
            return compare_df[(compare_df["pre"]["amount"] - compare_df["post"]["amount"]).abs() > 1e-8]


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
            order_book_tracker=BinanceOrderBookTracker(symbols=["ETHUSDT", "BTCUSDT"]),
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

        self.market.buy("BTCUSDT", 23, OrderType.LIMIT, 34)
        list_limit_orders: List[LimitOrder] = self.market.limit_orders
        second_limit_order: LimitOrder = list_limit_orders[0]
        self.assertEqual(second_limit_order.base_currency, "BTC", msg="Base currency is incorrect")
        self.assertEqual(second_limit_order.quote_currency, "USDT", msg="Quote currency is incorrect")
        self.assertTrue(second_limit_order.is_buy, msg="Limit order is not buy")
        self.assertEqual(second_limit_order.symbol, "BTCUSDT", msg="Symbol is incorrect")
        self.assertEqual(second_limit_order.price, 34, msg="Price is incorrect")
        self.assertEqual(second_limit_order.quantity, 23, msg="Quantity is incorrect")
        self.assertEqual(len(list_limit_orders), 2, msg="Second limit order did not get added")

    def testPlaceMarketOrders(self):
        self.market.sell("ETHUSDT", 30, OrderType.MARKET)
        list_queued_orders: List[QueuedOrder] = self.market.queued_orders
        first_queued_order: QueuedOrder = list_queued_orders[0]
        self.assertFalse(first_queued_order.is_buy, msg="Market order is not sell")
        self.assertEqual(first_queued_order.trading_pair, "ETHUSDT", msg="Symbol is incorrect")
        self.assertEqual(first_queued_order.amount, 30, msg="Quantity is incorrect")
        self.assertEqual(len(list_queued_orders), 1, msg="First market order did not get added")

        # Figure out why this test is failing
        self.market.buy("BTCUSDT", 30, OrderType.MARKET)
        list_queued_orders: List[QueuedOrder] = self.market.queued_orders
        second_queued_order: QueuedOrder = list_queued_orders[1]
        self.assertTrue(second_queued_order.is_buy, msg="Market order is not buy")
        self.assertEqual(second_queued_order.trading_pair, "BTCUSDT", msg="Symbol is incorrect")
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
            order_book_tracker=BinanceOrderBookTracker(symbols=["ETHUSDT", "BTCUSDT"]),
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

        for trading_pair, orderbook in self.market.order_books.items():
            orderbook.clear_traded_order_book()
            orderbook.clear_traded_order_book()

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

    def test_market_order_simulation(self):
        self.market.set_balance("ETH", 20)
        self.market.set_balance("USDT", 100)
        self.market.sell("ETHUSDT", 10, OrderType.MARKET)
        self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

        # Get diff between composite bid entries and original bid entries
        d2 = OrderBookUtils.get_compare_df(
            self.market.order_books['ETHUSDT'].original_bid_entries(),
            self.market.order_books['ETHUSDT'].bid_entries(), diffs_only=True).sort_index().round(10)
        filled_bids = OrderBookUtils.ob_rows_data_frame(
            list(self.market.order_books['ETHUSDT'].traded_order_book.bid_entries())).sort_index().round(10)

        # assert filled orders matches diff
        diff_bid = d2["diff"] - filled_bids["amount"]

        self.assertFalse(diff_bid.to_numpy().any())

        self.assertEquals(10, self.market.get_balance("ETH"), msg="Balance was not updated.")
        self.market.buy("ETHUSDT", 5, OrderType.MARKET)
        self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

        # Get diff between composite bid entries and original bid entries
        d2 = OrderBookUtils.get_compare_df(
            self.market.order_books['ETHUSDT'].original_ask_entries(),
            self.market.order_books['ETHUSDT'].ask_entries(), diffs_only=True).sort_index().round(10)
        filled_asks = OrderBookUtils.ob_rows_data_frame(
            list(self.market.order_books['ETHUSDT'].traded_order_book.ask_entries())).sort_index().round(10)

        # assert filled orders matches diff
        diff_ask = d2["diff"] - filled_asks["amount"]

        self.assertFalse(diff_ask.to_numpy().any())
        self.assertEquals(15, self.market.get_balance("ETH"), msg="Balance was not updated.")

    def test_limit_order_crossed(self):
        self.market.set_balance("ETH", 20)
        self.market.set_balance("USDT", 1000)
        self.market.sell("ETHUSDT", 10, OrderType.LIMIT, 100)

        self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        #self.assertEquals(10, self.market.get_balance("ETH"), msg="ETH Balance was not updated.")
        #self.assertEquals(1100, self.market.get_balance("USDT"), msg="USDT Balance was not updated.")
        self.market.buy("ETHUSDT", 1, OrderType.LIMIT, 500)
        self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        #self.assertEquals(11, self.market.get_balance("ETH"), msg="ETH Balance was not updated.")
        #self.assertEquals(600, self.market.get_balance("USDT"), msg="USDT Balance was not updated.")

    def test_bid_limit_order_trade_match(self):
        self.market.set_balance("ETH", 200)
        self.market.set_balance("USDT", 2000)
        best_bid_price = self.market.order_books['ETHUSDT'].get_price(True)

        self.market.buy("ETHUSDT", 1, OrderType.LIMIT, best_bid_price)

        placed_bid_orders: List[LimitOrder] = [o for o in self.market.limit_orders if o.is_buy]

        self.assertEqual(1, len(placed_bid_orders))

        async def delay_trigger_event1():
            await asyncio.sleep(1)
            trade_event = OrderBookTradeEvent(
                symbol="ETHUSDT", timestamp=time.time(), type=TradeType.SELL, price=best_bid_price, amount=1)
            self.market.order_books['ETHUSDT'].apply_trade(trade_event)
        asyncio.ensure_future(delay_trigger_event1())
        self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

        placed_bid_orders: List[LimitOrder] = [o for o in self.market.limit_orders if o.is_buy]

        self.assertEqual(0, len(placed_bid_orders))

        print(self.market_logger.event_log)

    def test_ask_limit_order_trade_match(self):
        self.market.set_balance("ETH", 200)
        self.market.set_balance("USDT", 2000)

        best_ask_price = self.market.order_books['ETHUSDT'].get_price(False)

        self.market.sell("ETHUSDT", 1, OrderType.LIMIT, best_ask_price)

        placed_ask_orders: List[LimitOrder] = [o for o in self.market.limit_orders if not o.is_buy]

        self.assertEqual(1, len(placed_ask_orders))

        async def delay_trigger_event2():
            await asyncio.sleep(1)
            trade_event = OrderBookTradeEvent(
                symbol="ETHUSDT", timestamp=time.time(), type=TradeType.BUY, price=best_ask_price, amount=1)
            self.market.order_books['ETHUSDT'].apply_trade(trade_event)

        asyncio.ensure_future(delay_trigger_event2())
        print(self.market_logger.event_log)
        self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

        placed_ask_orders: List[LimitOrder] = [o for o in self.market.limit_orders if not o.is_buy]

        self.assertEqual(0, len(placed_ask_orders))
        print(self.market_logger.event_log)
