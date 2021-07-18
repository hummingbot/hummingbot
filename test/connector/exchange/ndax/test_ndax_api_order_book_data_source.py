import asyncio
import unittest


from hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source import NdaxAPIOrderBookDataSource
from hummingbot.core.data_type.order_book import OrderBook


class NdaxAPIOrderBookDataSourceUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.ev_loop = asyncio.get_event_loop()
        cls.trading_pair = "BTC-CAD"
        cls.data_source = NdaxAPIOrderBookDataSource([cls.trading_pair])
        cls.ev_loop.run_until_complete(cls.wait_til_data_source_ready())

    @classmethod
    async def wait_til_data_source_ready(cls):
        while True:
            if len(cls.data_source._trading_pair_id_map) > 0:
                print("Initialized data source.")
                return
            await asyncio.sleep(1)

    # def test_init_trading_pair_ids(self):
    #     self.ev_loop.run_until_complete(self.data_source.init_trading_pair_ids())
    #     self.assertEqual(1, self.data_source._trading_pair_id_map[self.trading_pair])

    def test_get_last_traded_prices(self):
        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.get_last_traded_prices([self.trading_pair])))
        results = results[0]
        self.assertGreaterEqual(results[self.trading_pair], 0.0)

    def test_fetch_trading_pairs(self):
        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.fetch_trading_pairs()))
        result = results[0]
        self.assertTrue(self.trading_pair in result)

    def test_get_order_book_data(self):
        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.get_order_book_data(self.trading_pair)))
        result = results[0]
        self.assertTrue("data" in result)
        self.assertGreaterEqual(len(result["data"]), 0)

    def test_get_new_order_book(self):
        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.get_new_order_book(self.trading_pair)))
        result: OrderBook = results[0]

        self.assertTrue(type(result) == OrderBook)
        self.assertNotEqual(result.snapshot_uid, 0)

    def test_listen_for_snapshots(self):
        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue), timeout=2.0)
            )

        self.assertGreater(msg_queue.qsize(), 0)

    def test_listen_for_order_book_diffs(self):
        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue), timeout=2.0))

        self.assertGreater(msg_queue.qsize(), 0)
