"""Tests for SpotFeed — mocked HTTP."""
import time
import unittest
from unittest.mock import MagicMock, patch

from controllers.generic.binary_options.spot_feed import SpotFeed


def _pyth_response(entries):
    """Build a fake Pyth Hermes response. entries: [(feed_id_no_prefix, price_int, expo)]"""
    parsed = []
    for fid, price, expo in entries:
        parsed.append({"id": fid, "price": {"price": str(price), "expo": str(expo)}})
    return {"parsed": parsed}


def _binance_response(price):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"price": str(price)}
    return resp


def _ok_resp(json_data):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = json_data
    return resp


class TestSpotFeed(unittest.TestCase):
    def setUp(self):
        self.feed = SpotFeed()
        self.feed.update_addresses({
            "BTC": "0xabc123",
            "ETH": "0xdef456",
        })

    @patch("controllers.generic.binary_options.spot_feed.requests.get")
    def test_get_prices_cache_hit(self, mock_get):
        now = time.time()
        self.feed._cache = {"BTC": (now, 60000.0), "ETH": (now, 3000.0)}
        result = self.feed.get_prices(now + 1.0)
        mock_get.assert_not_called()
        self.assertEqual(result, {"BTC": 60000.0, "ETH": 3000.0})

    @patch("controllers.generic.binary_options.spot_feed.requests.get")
    def test_get_prices_fetches_when_stale(self, mock_get):
        mock_get.return_value = _ok_resp(_pyth_response([
            ("abc123", 6000000, -2),
            ("def456", 300000, -2),
        ]))
        now = time.time()
        result = self.feed.get_prices(now)
        mock_get.assert_called_once()
        self.assertAlmostEqual(result["BTC"], 60000.0)
        self.assertAlmostEqual(result["ETH"], 3000.0)

    @patch("controllers.generic.binary_options.spot_feed.requests.get")
    def test_fetch_pyth_success(self, mock_get):
        mock_get.return_value = _ok_resp(_pyth_response([("abc123", 5000000000, -5)]))
        result = self.feed._fetch_pyth(["BTC"])
        self.assertAlmostEqual(result["BTC"], 50000.0)
        self.assertEqual(self.feed._pyth_consecutive_failures, 0)

    @patch("controllers.generic.binary_options.spot_feed.requests.get")
    def test_fetch_pyth_cb_trips(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        self.feed._fetch_pyth(["BTC"])
        self.assertEqual(self.feed._pyth_consecutive_failures, 1)
        self.assertFalse(self.feed._pyth_cb_tripped)
        self.feed._fetch_pyth(["BTC"])
        self.assertEqual(self.feed._pyth_consecutive_failures, 2)
        self.assertTrue(self.feed._pyth_cb_tripped)

    @patch("controllers.generic.binary_options.spot_feed.requests.get")
    def test_fetch_pyth_cb_recovers(self, mock_get):
        self.feed._pyth_cb_tripped = True
        self.feed._pyth_cb_ticks_skipped = 0
        # Should skip for 10 ticks
        for _ in range(9):
            result = self.feed._fetch_pyth(["BTC"])
            self.assertEqual(result, {})
        # 10th tick: recovery attempt
        mock_get.return_value = _ok_resp(_pyth_response([("abc123", 6000000, -2)]))
        result = self.feed._fetch_pyth(["BTC"])
        self.assertFalse(self.feed._pyth_cb_tripped)
        self.assertAlmostEqual(result["BTC"], 60000.0)

    @patch("controllers.generic.binary_options.spot_feed.requests.get")
    def test_fetch_binance_success(self, mock_get):
        mock_get.return_value = _binance_response(61000.5)
        result = self.feed._fetch_binance("BTC")
        self.assertAlmostEqual(result, 61000.5)

    @patch("controllers.generic.binary_options.spot_feed.requests.get")
    def test_fetch_binance_unknown_symbol(self, mock_get):
        resp = MagicMock()
        resp.status_code = 400
        mock_get.return_value = resp
        result = self.feed._fetch_binance("FAKECOIN")
        self.assertIsNone(result)
        self.assertIn("FAKECOIN", self.feed._binance_unknown_symbols)
        # Second call skips HTTP
        mock_get.reset_mock()
        result = self.feed._fetch_binance("FAKECOIN")
        self.assertIsNone(result)
        mock_get.assert_not_called()

    @patch("controllers.generic.binary_options.spot_feed.requests.get")
    def test_fallback_pyth_to_binance(self, mock_get):
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "pyth" in url:
                raise Exception("pyth down")
            return _binance_response(62000.0)
        mock_get.side_effect = side_effect

        now = time.time()
        result = self.feed.get_prices(now)
        self.assertIn("BTC", self.feed._binance_routed)
        self.assertIn("ETH", self.feed._binance_routed)
        self.assertAlmostEqual(result.get("BTC"), 62000.0)

    def test_update_addresses(self):
        self.feed._binance_routed.add("SOL")
        self.feed.update_addresses({"SOL": "0xsol789"})
        self.assertIn("SOL", self.feed._pyth_addresses)
        self.assertNotIn("SOL", self.feed._binance_routed)

    def test_is_stale(self):
        self.assertTrue(self.feed.is_stale)  # empty cache
        self.feed._cache = {"BTC": (time.time() - 10.0, 60000.0)}
        self.assertTrue(self.feed.is_stale)
        self.feed._cache = {"BTC": (time.time(), 60000.0)}
        self.assertFalse(self.feed.is_stale)


if __name__ == "__main__":
    unittest.main()
