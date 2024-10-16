from unittest import TestCase

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS, chainflip_lp_utils as utils


class ChainflipLpUtilsTests(TestCase):
    def setUp(self):
        super().setUp()

    def test_chain_as_str(self):
        data = utils.chains_as_str("ETH")
        self.assertEqual(data, ",".join(CONSTANTS.SAME_CHAINS["ETH"]))
