"""
Unit tests for hummingbot.core.utils.ethereum
"""

import asyncio
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.ethereum import check_web3, check_transaction_exceptions, fetch_trading_pairs
from test.mock.mock_eth_node import MockEthNodeRequestHandler
from test.mock.mock_token_list import MockTokenListRequestHandler
from test.mock.mock_server import MockServer
import unittest.mock


class EthereumTest(unittest.TestCase):
    def test_check_web3(self):
        """
        Unit tests for hummingbot.core.utils.ethereum.check_web3
        """

        # create a MockEthNode but do not start it, check_web3 should fail to contact it
        mock_eth_node = MockServer(MockEthNodeRequestHandler)
        self.assertEqual(check_web3(mock_eth_node.url), False)

        # start the node, the check should pass
        mock_eth_node.start()
        self.assertEqual(check_web3(mock_eth_node.url), True)

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

    def test_fetch_trading_pairs(self):
        """
        Unit tests for hummingbot.core.utils.ethereum.fetch_trading_pairs
        """

        # Set url to localhost to mock it
        mock_server = MockServer(MockTokenListRequestHandler)
        global_config_map['ethereum_token_list_url'].value = mock_server.url

        # the server hasn't started to the function call should fail
        self.assertRaises(Exception, fetch_trading_pairs())

        # turn on the server to get data
        mock_server.start()
        trading_pairs = asyncio.get_event_loop().run_until_complete(fetch_trading_pairs())

        # the order of the elements isn't guaranteed so compare both to sets to compare
        self.assertEqual(set(trading_pairs), set(['DAI-BTC', 'DAI-ETH', 'BTC-DAI', 'BTC-ETH', 'ETH-DAI', 'ETH-BTC']))
