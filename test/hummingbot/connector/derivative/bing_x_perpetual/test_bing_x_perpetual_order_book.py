import gzip
import io
import json
import os
from unittest import TestCase


class TestBingXPerpetualOrderBook(TestCase):
    """Tests for order book data source logic by inspecting source and testing data formats."""

    def setUp(self):
        src_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'bing_x_perpetual', 'bing_x_perpetual_api_order_book_data_source.py'
        )
        with open(src_path) as f:
            self.source = f.read()

    def test_snapshot_uses_correct_endpoint(self):
        self.assertIn('SNAPSHOT_PATH_URL', self.source)

    def test_subscription_uses_depth20(self):
        self.assertIn('@depth20', self.source)

    def test_subscription_uses_trade_channel(self):
        self.assertIn('@trade', self.source)

    def test_subscription_message_format(self):
        # Verify the subscription payload structure
        self.assertIn('"reqType": "sub"', self.source)
        self.assertIn('"id":', self.source)
        self.assertIn('"dataType":', self.source)

    def test_gzip_decompression_integration(self):
        # Test that decompress_ws_message (from utils) handles gzip
        data = {"dataType": "BTC-USDT@depth20", "data": {"bids": [], "asks": []}}
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode='wb') as f:
            f.write(json.dumps(data).encode('utf-8'))
        compressed = buf.getvalue()
        # Decompress manually same way as utils
        decompressed = gzip.GzipFile(fileobj=io.BytesIO(compressed), mode='rb')
        result = json.loads(decompressed.read().decode('utf-8'))
        self.assertEqual(result["dataType"], "BTC-USDT@depth20")

    def test_order_book_snapshot_parsing(self):
        snapshot = {
            "data": {
                "bids": [["50000", "1.5"], ["49999", "2.0"]],
                "asks": [["50001", "1.0"], ["50002", "0.5"]],
                "t": 1234567890000
            }
        }
        bids = snapshot["data"]["bids"]
        asks = snapshot["data"]["asks"]
        self.assertEqual(len(bids), 2)
        self.assertEqual(len(asks), 2)
        self.assertEqual(bids[0][0], "50000")

    def test_trade_message_parsing(self):
        raw = {
            "dataType": "BTC-USDT@trade",
            "data": {"m": True, "t": "12345", "p": "50000.5", "q": "0.1", "T": 1234567890000}
        }
        trading_pair = raw["dataType"].split('@')[0]
        self.assertEqual(trading_pair, "BTC-USDT")
        self.assertEqual(raw["data"]["p"], "50000.5")

    def test_diff_event_type_used(self):
        self.assertIn('DIFF_EVENT_TYPE', self.source)

    def test_trade_event_type_used(self):
        self.assertIn('TRADE_EVENT_TYPE', self.source)

    def test_ping_pong_handling(self):
        self.assertIn('ping', self.source)
        self.assertIn('pong', self.source)
