"""
Unit tests for hummingbot.core.utils.ethereum
"""

import asyncio
from hummingbot.core.utils.ethereum import check_web3, check_transaction_exceptions, fetch_trading_pairs
import unittest.mock


class EthereumTest(unittest.TestCase):
    @unittest.mock.patch('hummingbot.core.utils.ethereum.is_connected_to_web3')
    def test_check_web3(self, is_connected_to_web3_mock):
        """
        Unit tests for hummingbot.core.utils.ethereum.check_web3
        """

        # unable to connect to web3
        is_connected_to_web3_mock.return_value = False
        self.assertEqual(check_web3('doesnt-exist'), False)

        # connect to web3
        is_connected_to_web3_mock.return_value = True
        self.assertEqual(check_web3('ethereum.node'), True)

    def test_check_transaction_exceptions(self):
        """
        Unit tests for hummingbot.core.utils.ethereum.transaction_exceptions
        """

        # create transactions data that should result in no warnings
        transaction = {
            "allowances": {"WBTC": 1000},
            "balances": {"ETH": 1000},
            "base": "ETH",
            "quote": "WBTC",
            "amount": 1000,
            "side": 100,
            "gas_limit": 22000,
            "gas_price": 90,
            "gas_cost": 90,
            "price": 100
        }
        self.assertEqual(check_transaction_exceptions(transaction), [])

        # ETH balance less than gas_cost
        invalid_transaction_1 = transaction.copy()
        invalid_transaction_1["balances"] = {"ETH": 10}
        self.assertRegexpMatches(check_transaction_exceptions(invalid_transaction_1)[0], r"^Insufficient ETH balance to cover gas")

        # Gas limit set too low, gas_limit is less than 21000
        invalid_transaction_2 = transaction.copy()
        invalid_transaction_2["gas_limit"] = 10000
        self.assertRegexpMatches(check_transaction_exceptions(invalid_transaction_2)[0], r"^Gas limit")

        # Insufficient token allowance, allowance of quote less than amount
        invalid_transaction_3 = transaction.copy()
        invalid_transaction_3["allowances"] = {"WBTC": 500}
        self.assertRegexpMatches(check_transaction_exceptions(invalid_transaction_3)[0], r"^Insufficient")

    @unittest.mock.patch('hummingbot.core.utils.ethereum.get_token_list')
    def test_fetch_trading_pairs(self, get_token_list_mock):
        """
        Unit tests for hummingbot.core.utils.ethereum.fetch_trading_pairs
        """
        # patch get_token_list to avoid a server call
        get_token_list_mock.return_value = {'tokens': [{"symbol": "ETH"}, {"symbol": "DAI"}, {"symbol": "BTC"}]}

        trading_pairs = asyncio.get_event_loop().run_until_complete(fetch_trading_pairs())

        # the order of the elements isn't guaranteed so compare both to sets to compare
        self.assertEqual(set(trading_pairs), set(['DAI-BTC', 'DAI-ETH', 'BTC-DAI', 'BTC-ETH', 'ETH-DAI', 'ETH-BTC']))
