import time
import unittest
from unittest.mock import patch

from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.utils import tracking_nonce


class UtilsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = "HBOT"
        cls.quote = "COINALPHA"
        cls.trading_pair = f"{cls.base}-{cls.quote}"

    @patch("hummingbot.core.utils.tracking_nonce._time")
    def test_get_new_client_order_id(self, mocked_time):
        t = time.time()
        target_nonce_0 = f"{int(t)}00"
        target_nonce_1 = f"{int(t)}01"
        target_nonce_2 = f"{int(t)}02"
        mocked_time.return_value = t
        tracking_nonce.nonce_multiplier_power = 2
        host_prefix = "hbot"

        id0 = get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair)
        id1 = get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair, hbot_order_id_prefix=host_prefix)

        self.assertFalse(id0.startswith(host_prefix))
        self.assertTrue(id1.startswith(host_prefix))
        self.assertTrue(id0.endswith(target_nonce_0))
        self.assertTrue(id1.endswith(target_nonce_1))

        id2 = get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair, max_id_len=len(id0) - 2)

        self.assertTrue(id2.endswith(target_nonce_2[2:]))
        self.assertEqual(id0[:-len(target_nonce_0)], id2[:-len(target_nonce_2[2:])])

        with self.assertRaises(NotImplementedError):
            get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair, max_id_len=len(id0) - 10)
