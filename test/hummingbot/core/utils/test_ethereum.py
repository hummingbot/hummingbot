"""
Unit tests for hummingbot.core.utils.ethereum
"""
from hummingbot.core.utils.ethereum import check_web3
from test.mock.mock_eth_node import MockEthNode
import asyncio
import unittest.mock


class EthereumTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.new_event_loop()

    def test_check_web3(self):
        mock_eth_node = MockEthNode()
        self.assertEqual(check_web3(mock_eth_node.url), False)

        mock_eth_node.start()
        self.assertEqual(check_web3(mock_eth_node.url), True)

    def check_transaction_exceptions(self):
        self.assertEqual(1, 1)

    def fetch_trading_pairs(self):
        self.assertEqual(1, 1)
