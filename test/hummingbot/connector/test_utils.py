import time
import unittest
from unittest.mock import patch

from hummingbot.connector.utils import get_new_client_order_id


class UtilsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = "HBOT"
        cls.quote = "COINALPHA"
        cls.trading_pair = f"{cls.base}-{cls.quote}"

    @patch("hummingbot.core.utils.tracking_nonce._time")
    def test_get_new_client_order_id(self, mocked_time):
        t = int(time.time() * 1e3)
        mocked_time.return_value = t
        host_prefix = "hbot"

        id0 = get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair)
        id1 = get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair, hbot_order_id_prefix=host_prefix)

        self.assertFalse(id0.startswith(host_prefix))
        self.assertTrue(id1.startswith(host_prefix))

        id2 = get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair, max_id_len=len(id0) - 2)

        self.assertEqual(len(id0) - 2, len(id2))
