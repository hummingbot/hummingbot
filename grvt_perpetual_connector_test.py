import unittest
from grvt_perpetual_connector import GRVTPerpetualConnector

class TestGRVTPerpetualConnector(unittest.TestCase):

    def setUp(self):
        self.connector = GRVTPerpetualConnector(api_key='your_api_key', api_secret='your_api_secret')

    def test_place_order(self):
        response = self.connector.place_order(symbol="BTC-USD", side="BUY", price=50000.0, quantity=0.1)
        self.assertEqual(response['status'], 'success')

    def test_cancel_order(self):
        order_id = "12345"
        response = self.connector.cancel_order(order_id)
        self.assertEqual(response['status'], 'success')

    def test_get_balance(self):
        response = self.connector.get_balance()
        self.assertGreater(len(response['balances']), 0)

    def test_get_positions(self):
        response = self.connector.get_positions()
        self.assertGreater(len(response['positions']), 0)

    def test_websocket_connection(self):
        symbol = "BTC-USD"
        try:
            self.connector.start_websocket(symbol)
        except Exception as e:
            self.fail(f"WebSocket connection failed with error: {str(e)}")

if __name__ == "__main__":
    unittest.main()