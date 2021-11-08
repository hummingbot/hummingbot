from unittest import TestCase
from unittest.mock import patch
from unittest import mock

from hummingbot.connector.exchange.ascend_ex import ascend_ex_utils as utils


class AscendExUtilsTests(TestCase):

    def _get_ms_timestamp(self):
        return 1633084102569

    @patch('hummingbot.connector.exchange.ascend_ex.ascend_ex_utils.uuid32')
    def test_gen_client_order_id(self, uuid_mock):
        uuid_mock.return_value = "A" * 32
        self.assertEqual(f"HMBot-BBTCUSD{uuid_mock.return_value}", utils.gen_client_order_id(True, "BTC-USDT"))
        uuid_mock.return_value = "A" * 31 + "B"
        self.assertEqual(f"HMBot-SETHUSD{uuid_mock.return_value}", utils.gen_client_order_id(False, "ETH-USDT"))

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_utils.get_ms_timestamp")
    @patch('hummingbot.connector.exchange.ascend_ex.ascend_ex_utils.uuid32')
    def test_gen_exchange_order_id(self, uuid_mock, get_ms_timestamp_mock):
        uuid_mock.return_value = "A" * 32

        timestamp = self._get_ms_timestamp()
        get_ms_timestamp_mock.return_value = timestamp

        userUid = "U0123456789"  # "U" + 10 digits
        client_order_id = f"HMBot-BBTCUSD{uuid_mock.return_value}"

        order_id = utils.gen_exchange_order_id(userUid = userUid, client_order_id = client_order_id)

        self.assertEqual('HMBot17c3b65d7a9U0123456789AAAAA', order_id[0])
        self.assertEqual(1633084102569, order_id[1])

    def test_convert_to_exchange_trading_pair(self):
        trading_pair = "BTC-USDT"
        self.assertEqual("BTC/USDT", utils.convert_to_exchange_trading_pair(trading_pair))

    def test_convert_from_exchange_trading_pair(self):
        trading_pair = "BTC/USDT"
        self.assertEqual("BTC-USDT", utils.convert_from_exchange_trading_pair(trading_pair))

    def test_rest_api_url_private(self):
        account_id = "1234"

        url = utils.get_rest_url_private(account_id=account_id)
        self.assertEqual(f"https://ascendex.com/{account_id}/api/pro/v1", url)

    def test_get_ws_url_private(self):
        account_id = "1234"

        url = utils.get_ws_url_private(account_id=account_id)
        self.assertEqual(f"wss://ascendex.com/{account_id}/api/pro/v1", url)

    def test_get_ms_timestamp(self):
        with mock.patch('hummingbot.connector.exchange.ascend_ex.ascend_ex_utils.get_tracking_nonce_low_res') as get_tracking_nonce_low_res_mock:
            get_tracking_nonce_low_res_mock.return_value = 123456789

            timestamp = utils.get_ms_timestamp()
            self.assertEqual(123456789, timestamp)

    def test_uuid32(self):
        with mock.patch('hummingbot.connector.exchange.ascend_ex.ascend_ex_utils.random.choice') as random_choice_mock:
            random_choice_mock.return_value = 'a'

            uuid32 = utils.uuid32()
            self.assertEqual("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", uuid32)

    def test_derive_order_id(self):
        user_uid = "abcdefghijklmnop1234"
        cl_order_id = "abcdefghijklmnop5678"
        ts = 123456789

        order_id = utils.derive_order_id(user_uid, cl_order_id, ts)

        self.assertEqual("HMBot75bcd15jklmnop1234p5678", order_id)
