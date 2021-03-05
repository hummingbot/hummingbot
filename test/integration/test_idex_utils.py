import asyncio
import aiohttp
import unittest

from typing import List
from unittest.mock import patch

from hummingbot.connector.exchange.idex.idex_utils import validate_idex_contract_blockchain, IDEX_BLOCKCHAINS

class TestUtils (unittest.TestCase):

    def test_validate_idex_contract_blockchain(self):
        blockchain_value = "ETH"
        self.assertNotEqual(validate_idex_contract_blockchain("ETH"), f'Value ETH must be one of: {IDEX_BLOCKCHAINS}')
        self.assertNotEqual(validate_idex_contract_blockchain("BSC"), f'Value BSC must be one of: {IDEX_BLOCKCHAINS}')
        self.assertEqual(validate_idex_contract_blockchain("BAL"), f'Value BAL must be one of: {IDEX_BLOCKCHAINS}')
