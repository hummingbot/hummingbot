import unittest

from hummingbot.client.data_type.currency_amount import CurrencyAmount


class CurrencyAmountTestCase(unittest.TestCase):

    def test_currency_amount_properties(self):
        amount = CurrencyAmount()
        amount.token = "ETH"
        amount.amount = 1.23
        self.assertEqual(amount.token, "ETH")
        self.assertEqual(amount.amount, 1.23)


if __name__ == '__main__':
    unittest.main()
