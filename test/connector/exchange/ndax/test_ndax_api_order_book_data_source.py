import asyncio
import unittest

from unittest.mock import patch, AsyncMock
from typing import (
    Any,
    Dict,
    List,
)

from hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source import NdaxAPIOrderBookDataSource
from hummingbot.core.data_type.order_book import OrderBook


class NdaxAPIOrderBookDataSourceUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.instrument_id = 1
        cls.data_source = NdaxAPIOrderBookDataSource([cls.trading_pair])

    def simulate_trading_pair_ids_initialized(self):
        self.data_source._trading_pair_id_map.update({self.trading_pair: self.instrument_id})

    def set_mock_response(self, mock_api, status, json_data):
        mock_api.return_value.__aenter__.return_value.status = status
        mock_api.return_value.__aenter__.return_value.json = AsyncMock(return_value=json_data)

    @patch("aiohttp.ClientSession.get")
    def test_init_trading_pair_ids(self, mock_api):

        mock_response: List[Any] = [{
            "Product1Symbol": self.base_asset,
            "Product2Symbol": self.quote_asset,
            "InstrumentId": self.instrument_id,
        }]

        self.set_mock_response(mock_api, 200, mock_response)

        self.ev_loop.run_until_complete(self.data_source.init_trading_pair_ids())
        self.assertEqual(1, self.data_source._trading_pair_id_map[self.trading_pair])

    @patch("aiohttp.ClientSession.get")
    def test_get_last_traded_prices(self, mock_api):

        self.simulate_trading_pair_ids_initialized()
        mock_response: Dict[Any] = {
            "LastTradedPx": 1.0
        }

        self.set_mock_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.get_last_traded_prices([self.trading_pair])))
        results: Dict[str, Any] = results[0]

        self.assertEqual(results[self.trading_pair], mock_response["LastTradedPx"])

    @patch("aiohttp.ClientSession.get")
    def test_fetch_trading_pairs(self, mock_api):

        self.simulate_trading_pair_ids_initialized()

        mock_response: List[Any] = [{
            "Product1Symbol": self.base_asset,
            "Product2Symbol": self.quote_asset,
        }]
        self.set_mock_response(mock_api, 200, mock_response)

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
