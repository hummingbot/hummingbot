import unittest
from decibel_perp_connector import DecibelPerpConnector

class TestDecibelPerpConnector(unittest.TestCase):
    def setUp(self):
        self.connector = DecibelPerpConnector(api_key='test_api_key', api_secret='test_api_secret')

    def test_place_limit_order(self):
        response = self.connector.place_limit_order('BTCUSD', 'buy', 1.0, 50000)
        self.assertIsNotNone(response)
        self.assertEqual(response.get('status'), 'success')

    def test_place_market_order(self):
        response = self.connector.place_market_order('BTCUSD', 'buy', 1.0)
        self.assertIsNotNone(response)
        self.assertEqual(response.get('status'), 'success')

    def test_cancel_order(self):
        # Assuming order_id 1234 exists
        response = self.connector.cancel_order(1234)
        self.assertIsNotNone(response)
        self.assertEqual(response.get('status'), 'success')

    def test_get_balance(self):
        balance = self.connector.get_balance()
        self.assertIsNotNone(balance)
        self.assertIn('total', balance)

if __name__ == '__main__':
    unittest.main()