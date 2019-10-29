from hummingbot.core.event.event_logger import EventLogger
from typing import (
    Dict,
    Optional,
    List
)
from hummingbot.core.event.events import (
    OrderBookEvent,
)
from hummingbot.core.data_type.order_book_tracker import (
    OrderBookTrackerDataSourceType
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.stablecoinswap.stablecoinswap_order_book_tracker import StablecoinswapOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from web3 import Web3, HTTPProvider
import sys
import conf
import asyncio
import logging
import unittest
import hummingbot.market.stablecoinswap.stablecoinswap_contracts as stablecoinswap_contracts
from os.path import join, realpath
sys.path.insert(0, realpath(join(__file__, "../../../")))


class StablecoinswapOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[StablecoinswapOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "DAI-USDC",
        "DAI-TUSD",
        "USDC-TUSD"
    ]
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.w3 = w3 = Web3(HTTPProvider(conf.test_web3_provider_list[0]))
        cls.oracle_cont = stablecoinswap_contracts.PriceOracle(w3)
        cls.stl_contract = stablecoinswap_contracts.Stablecoinswap(w3, cls.oracle_cont)
        cls.order_book_tracker: StablecoinswapOrderBookTracker = StablecoinswapOrderBookTracker(
            stl_contract = cls.stl_contract,
            data_source_type=OrderBookTrackerDataSourceType.BLOCKCHAIN,
            symbols=cls.trading_pairs
        )
        cls.order_book_tracker_task: asyncio.Task = safe_ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 2:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)

    async def run_parallel_async(self, *tasks, timeout=None):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        timer = 0
        while not future.done():
            if timeout and timer > timeout:
                raise Exception("Time out running parallel async task in tests.")
            timer += 1
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def setUp(self):
        self.event_logger = EventLogger()
        for event_tag in self.events:
            for trading_pair, order_book in self.order_book_tracker.order_books.items():
                order_book.add_listener(event_tag, self.event_logger)

    def test_tracker_integrity(self):
        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        # dai_usdc_book: OrderBook = order_books["DAI-USDC"]
        dai_tusd_book: OrderBook = order_books["DAI-TUSD"]
        # self.assertEqual(dai_usdc_book.get_price_for_volume(True, 10).result_price,
        #                         dai_usdc_book.get_price(True))
        # self.assertEqual(dai_usdc_book.get_price_for_volume(False, 10).result_price,
        #                      dai_usdc_book.get_price(False))
        self.assertEqual(dai_tusd_book.get_price_for_volume(True, 10).result_price,
                         dai_tusd_book.get_price(True))
        self.assertEqual(dai_tusd_book.get_price_for_volume(False, 10).result_price,
                         dai_tusd_book.get_price(False))


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
