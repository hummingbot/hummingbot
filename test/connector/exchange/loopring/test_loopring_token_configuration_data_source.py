#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from hummingbot.connector.exchange.loopring.loopring_api_token_configuration_data_source import LoopringAPITokenConfigurationDataSource
# from hummingbot.connector.exchange.loopring.loopring_auth import LoopringAuth
from decimal import Decimal
import asyncio
# import conf
import json
import logging
import unittest


class LoopringAPITokenConfigurationUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.loopring_token_configuration_data_source = LoopringAPITokenConfigurationDataSource()
        asyncio.get_event_loop().run_until_complete(cls.loopring_token_configuration_data_source._configure())

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def test_configs(self):
        logging.info("Token configurations from loopring.io")
        for token in self.loopring_token_configuration_data_source.get_tokens():
            logging.info(json.dumps(self.loopring_token_configuration_data_source.get_config(token), indent=4))

    def test_conversion(self):
        logging.info("Symbol : int : int [both ints should match]")
        for token in self.loopring_token_configuration_data_source.get_tokens():
            logging.info(f"{self.loopring_token_configuration_data_source.get_symbol(token)} : "
                         f"{self.loopring_token_configuration_data_source.get_tokenid(self.loopring_token_configuration_data_source.get_symbol(token))} : {token}")

    def test_padding(self):
        logging.info('Convert "3.1412" into the padded format for each token [{symbol} : {padded} : {unpadded}]')
        for token in self.loopring_token_configuration_data_source.get_tokens():
            logging.info(f"{self.loopring_token_configuration_data_source.get_symbol(token)} : {self.loopring_token_configuration_data_source.pad(Decimal('3.1412'), token)}"
                         f" :  {self.loopring_token_configuration_data_source.unpad(self.loopring_token_configuration_data_source.pad(Decimal('3.1412'), token), token)}")

        logging.info('Verify padding and unpadding of ETH [all three values should represent the samve value, {padded} {unpadded} {padded}]')
        value = '12153289800000001277952'
        eth_id = self.loopring_token_configuration_data_source.get_tokenid('ETH')
        unpaded: Decimal = self.loopring_token_configuration_data_source.unpad(value, eth_id)
        repaded: str = self.loopring_token_configuration_data_source.pad(unpaded, eth_id)
        assert(value == repaded)
        logging.info(f"{value} {unpaded} {repaded}")


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
