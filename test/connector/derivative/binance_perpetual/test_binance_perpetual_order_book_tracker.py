import asyncio
import logging
import unittest
from typing import Optional, List, Dict

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderBookEvent, OrderBookTradeEvent, TradeType
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_order_book_tracker import BinancePerpetualOrderBookTracker


class BinancePerpetualOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[BinancePerpetualOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "BTC-USDT",
        "ETH-USDT"
    ]

    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: BinancePerpetualOrderBookTracker = BinancePerpetualOrderBookTracker(
            trading_pairs=cls.trading_pairs, base_url="https://testnet.binancefuture.com", stream_url="wss://stream.binancefuture.com"
        )
        cls.order_book_tracker_task: asyncio.Task = safe_ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)

    def setUp(self) -> None:
        self.event_logger = EventLogger()
        for event_tag in self.events:
            for trading_pair, order_book in self.order_book_tracker.order_books.items():
                order_book.add_listener(event_tag, self.event_logger)

    @staticmethod
    async def run_parallel_async(*tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            await asyncio.sleep(1)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_order_book_trade_occurs(self):
        self.run_parallel(self.event_logger.wait_for(OrderBookTradeEvent))
        for ob_trade_event in self.event_logger.event_log:
            self.assertEqual(type(ob_trade_event), OrderBookTradeEvent)
            self.assertTrue(ob_trade_event.trading_pair in self.trading_pairs)
            self.assertEqual(type(ob_trade_event.timestamp), float)
            self.assertEqual(type(ob_trade_event.amount), float)
            self.assertEqual(type(ob_trade_event.price), float)
            self.assertEqual(type(ob_trade_event.type), TradeType)
            self.assertTrue(ob_trade_event.amount > 0)
            self.assertTrue(ob_trade_event.price > 0)

    def test_tracker_adv(self):
        self.ev_loop.run_until_complete(asyncio.sleep(10))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        btcusdt_book: OrderBook = order_books[self.trading_pairs[0]]
        ethusdt_book: OrderBook = order_books[self.trading_pairs[1]]

        print("BTC-USDT SNAPSHOT: ")
        print(btcusdt_book.snapshot)
        print("ETH-USDT SNAPSHOT: ")
        print(ethusdt_book.snapshot)

        self.assertGreaterEqual(btcusdt_book.get_price_for_volume(True, 10).result_price,
                                btcusdt_book.get_price(True))
        self.assertLessEqual(btcusdt_book.get_price_for_volume(False, 10).result_price,
                             btcusdt_book.get_price(False))
        self.assertGreaterEqual(ethusdt_book.get_price_for_volume(True, 10).result_price,
                                ethusdt_book.get_price(True))
        self.assertLessEqual(ethusdt_book.get_price_for_volume(False, 10).result_price,
                             ethusdt_book.get_price(False))


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
