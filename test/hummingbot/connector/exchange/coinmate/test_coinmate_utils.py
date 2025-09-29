import unittest

from hummingbot.connector.exchange.coinmate import coinmate_utils as utils


class CoinmateUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "EUR"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"

    def test_is_exchange_information_valid(self):
        # Valid exchange info - API returns list format
        valid_info = {
            "error": False,
            "data": [
                {"name": "BTC_EUR", "minAmount": 0.001},
                {"name": "ETH_EUR", "minAmount": 0.01}
            ]
        }
        self.assertTrue(utils.is_exchange_information_valid(valid_info))

        # Invalid exchange info - API error
        invalid_info_error = {"error": True, "errorMessage": "Some error"}
        self.assertFalse(utils.is_exchange_information_valid(invalid_info_error))

        # Invalid exchange info - no data key
        invalid_info_no_data = {"error": False}
        self.assertFalse(utils.is_exchange_information_valid(invalid_info_no_data))

        # Invalid exchange info - empty data list
        invalid_info_empty_data = {"error": False, "data": []}
        self.assertFalse(utils.is_exchange_information_valid(invalid_info_empty_data))

        # Invalid exchange info - not a dict
        self.assertFalse(utils.is_exchange_information_valid("not_a_dict"))
        self.assertFalse(utils.is_exchange_information_valid(None))

    def test_get_new_client_order_id(self):
        """Test client order ID generation"""
        buy_order_id = utils.get_new_client_order_id(True, self.trading_pair)
        sell_order_id = utils.get_new_client_order_id(False, self.trading_pair)

        # Test format
        self.assertTrue(buy_order_id.startswith("HBOT-B-"))
        self.assertTrue(sell_order_id.startswith("HBOT-S-"))

        # Test uniqueness
        another_buy_id = utils.get_new_client_order_id(True, self.trading_pair)
        self.assertNotEqual(buy_order_id, another_buy_id)

    def test_calculate_backoff_time(self):
        """Test exponential backoff calculation"""
        self.assertEqual(utils.calculate_backoff_time(0), 1.0)
        self.assertEqual(utils.calculate_backoff_time(1), 2.0)
        self.assertEqual(utils.calculate_backoff_time(2), 4.0)
        self.assertEqual(utils.calculate_backoff_time(3), 8.0)