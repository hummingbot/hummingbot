import unittest
from grvt_perpetual.grvt_rest_api import GRVTRestAPI

class TestGRVTPerpetualConnector(unittest.TestCase):
    def setUp(self):
        self.config = {'api_key': 'your_api_key'}
        self.api = GRVTRestAPI(self.config)

    def test_place_order(self):
        order = {'symbol': 'BTCUSDT', 'price': 40000, 'quantity': 1, 'side': 'buy'}
        response = self.api.place_order(order)
        self.assertIn('order_id', response)

    def test_get_balance(self):
        response = self.api.get_balance()
        self.assertIn('balance', response)

if __name__ == '__main__':
    unittest.main()