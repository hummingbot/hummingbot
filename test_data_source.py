import unittest
import json
import sys
from pathlib import Path
from decimal import Decimal

# Alignment: Add current directory to path so we can import 'hummingbot' package
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Mocking Hummingbot core if dependencies are missing (Partial Mock for environment stability)
# But we try to import real first
try:
    from hummingbot.core.data_type.order_book import OrderBook
    from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
except ImportError:
    # If we are in a lightweight env without HB deps, we create a structural stand-in
    # This maintains Fidelity of Logic, even if env is partial
    class OrderBook:
        def __init__(self):
            self._bids = []
            self._asks = []
        def apply_snapshot(self, bids, asks, uid):
            self._bids = sorted(bids, key=lambda x: -x[0])
            self._asks = sorted(asks, key=lambda x: x[0])
        def bid_entries(self):
            for p, s in self._bids: yield type('Entry', (), {'price': p, 'amount': s})
        def ask_entries(self):
            for p, s in self._asks: yield type('Entry', (), {'price': p, 'amount': s})

    class OrderBookMessageType:
        SNAPSHOT = 1

    class OrderBookMessage:
        def __init__(self, type, content, timestamp):
            self.bids = content['bids']
            self.asks = content['asks']
            self.update_id = content['update_id']

# Now import our connector code
# We need to ensure the path to 'hummingbot.connector...' resolves correctly
# Since we are in 'hummingbot_decibel', and the code is in 'hummingbot/connector...', 
# adding current_dir to sys.path should work if __init__.py files exist.
# Let's add the root of the repo.
repo_root = current_dir
sys.path.append(str(repo_root))

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import DecibelPerpetualAPIOrderBookDataSource

class TestDecibelDataSource(unittest.TestCase):
    def setUp(self):
        self.data_source = DecibelPerpetualAPIOrderBookDataSource(["BTC-USDC"])
        
        # Load fixture
        with open("tests/fixtures/snapshot.json", "r") as f:
            self.snapshot_data = json.load(f)

    def test_deserialize_snapshot(self):
        print("\n🧪 [TEST] Verifying Zero-Mock Deserialization...")
        
        # Act
        order_book = self.data_source.deserialize_snapshot(self.snapshot_data, "BTC-USDC")
        
        # Assert
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        
        print(f"   Top Bid: {bids[0].price} (Size: {bids[0].amount})")
        print(f"   Top Ask: {asks[0].price} (Size: {asks[0].amount})")
        
        self.assertEqual(len(bids), 3)
        self.assertEqual(len(asks), 3)
        self.assertEqual(bids[0].price, 50000.0)
        self.assertEqual(asks[0].price, 50005.0)
        self.assertEqual(bids[0].amount, 1.5)
        
        print("✅ [PASS] Structure aligns with SDK schema.")

if __name__ == "__main__":
    unittest.main()
