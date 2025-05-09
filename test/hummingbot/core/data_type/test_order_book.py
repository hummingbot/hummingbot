#!/usr/bin/env python

import logging
import unittest
from hummingbot.core.data_type.order_book import OrderBook
import numpy as np


class OrderBookUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.order_book_dex = OrderBook(dex=True)
        cls.order_book_cex = OrderBook(dex=False)

    def test_truncate_overlap_entries_dex(self):
        bids_array = np.array([[1, 1, 1], [2, 1, 2], [3, 1, 3], [50, 0.01, 4]], dtype=np.float64)
        asks_array = np.array([[4, 1, 1], [5, 1, 2], [6, 1, 3], [7, 1, 4]], dtype=np.float64)
        self.order_book_dex.apply_numpy_snapshot(bids_array, asks_array)
        bids, asks = self.order_book_dex.snapshot
        best_bid = bids.iloc[0].tolist()
        best_ask = asks.iloc[0].tolist()
        self.assertEqual(best_bid, [3., 1., 3.])
        self.assertEqual(best_ask, [4., 1., 1.])

        new_ask = np.array([[2, 0.1, 5]])
        new_bid = np.array([[3.5, 1, 5]])
        self.order_book_dex.apply_numpy_diffs(new_bid, new_ask)
        bids, asks = self.order_book_dex.snapshot
        best_bid = bids.iloc[0].tolist()
        best_ask = asks.iloc[0].tolist()
        self.assertEqual(best_bid, [3.5, 1., 5.])
        self.assertEqual(best_ask, [4., 1., 1.])

    def test_truncate_overlap_entries_cex(self):
        bids_array = np.array([[1, 1, 1], [2, 1, 2], [3, 1, 3]], dtype=np.float64)
        asks_array = np.array([[4, 1, 1], [5, 1, 2], [6, 1, 3], [7, 1, 4]], dtype=np.float64)
        self.order_book_cex.apply_numpy_snapshot(bids_array, asks_array)
        bids, asks = self.order_book_cex.snapshot
        best_bid = bids.iloc[0].tolist()
        best_ask = asks.iloc[0].tolist()
        self.assertEqual(best_bid, [3., 1., 3.])
        self.assertEqual(best_ask, [4., 1., 1.])

        new_ask = np.array([[2, 0.1, 5]])
        new_bid = np.array([[50, 0.01, 6]])
        self.order_book_cex.apply_numpy_diffs(new_bid, new_ask)
        bids, asks = self.order_book_cex.snapshot
        best_bid = len(bids) and bids.iloc[0].tolist()
        best_ask = len(asks) and asks.iloc[0].tolist()
        self.assertEqual(best_bid, [50., 0.01, 6.])
        self.assertEqual(best_ask, 0)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
