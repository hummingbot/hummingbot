import unittest

from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_utils import (
    DEFAULT_FEES,
    KEYS,
)


class TestEvedexPerpetualUtils(unittest.TestCase):

    def test_default_fees_exist(self):
        self.assertIsNotNone(DEFAULT_FEES)

    def test_keys_exist(self):
        self.assertIsNotNone(KEYS)


if __name__ == "__main__":
    unittest.main()
