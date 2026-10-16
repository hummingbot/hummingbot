import pickle
import unittest

import pandas as pd

from hummingbot.core.data_type.remote_api_order_book_data_source import RemoteAPIOrderBookDataSource


class RemoteAPIOrderBookDataSourceTests(unittest.TestCase):

    def test_load_order_book_tracker_data_accepts_expected_snapshot(self):
        bids_df = pd.DataFrame([[1.0, 2.0]], columns=["price", "amount"])
        asks_df = pd.DataFrame([[3.0, 4.0]], columns=["price", "amount"])
        payload = pickle.dumps({"BTC-USDT": (bids_df, asks_df)})

        result = RemoteAPIOrderBookDataSource._load_order_book_tracker_data(payload)

        self.assertEqual(["BTC-USDT"], list(result.keys()))
        result_bids_df, result_asks_df = result["BTC-USDT"]
        pd.testing.assert_frame_equal(bids_df, result_bids_df)
        pd.testing.assert_frame_equal(asks_df, result_asks_df)

    def test_load_order_book_tracker_data_rejects_unexpected_globals(self):
        class Exploit:
            def __reduce__(self):
                return eval, ("1 + 1",)

        with self.assertRaises(pickle.UnpicklingError):
            RemoteAPIOrderBookDataSource._load_order_book_tracker_data(pickle.dumps(Exploit()))

    def test_load_order_book_tracker_data_rejects_invalid_snapshot_shape(self):
        payload = pickle.dumps({"BTC-USDT": ("bids", "asks")})

        with self.assertRaises(ValueError):
            RemoteAPIOrderBookDataSource._load_order_book_tracker_data(payload)
