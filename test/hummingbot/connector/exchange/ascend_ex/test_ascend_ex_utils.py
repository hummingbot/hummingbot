from unittest import TestCase
from unittest.mock import patch
from unittest import mock

from hummingbot.connector.exchange.ascend_ex import ascend_ex_utils as utils


class AscendExUtilsTests(TestCase):

    def _get_ms_timestamp(self):
        return 1633084102569

    @patch('hummingbot.connector.exchange.ascend_ex.ascend_ex_utils.get_tracking_nonce')
    def test_gen_client_order_id(self, nonce_provider_mock):
        nonce_provider_mock.return_value = int(1e15)
        self.assertEqual("HMBot-BBTCUSD1000000000000000", utils.gen_client_order_id(True, "BTC-USDT"))
        nonce_provider_mock.return_value = int(1e15) + 1
        self.assertEqual("HMBot-SETHUSD1000000000000001", utils.gen_client_order_id(False, "ETH-USDT"))

    def test_gen_exchange_order_id(self):
        with mock.patch('hummingbot.connector.exchange.ascend_ex.ascend_ex_utils.get_ms_timestamp') as get_ms_timestamp_mock:
            timestamp = self._get_ms_timestamp()
            get_ms_timestamp_mock.return_value = timestamp

            userUid = "abcdefghijklmnop1234"
            client_order_id = "abcdefghijklmnop5678"

            order_id = utils.gen_exchange_order_id(userUid = userUid, client_order_id = client_order_id)

            self.assertEqual('HMBot17c3b65d7a9jklmnop1234p5678', order_id[0])
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
        self.assertEqual(f"https://ascendex.com/{account_id}/api/pro/v1/websocket-for-hummingbot-liq-mining", url)

    def test_get_ws_url_private(self):
        account_id = "1234"

        url = utils.get_ws_url_private(account_id=account_id)
        self.assertEqual(f"wss://ascendex.com:443/{account_id}/api/pro/v1/websocket-for-hummingbot-liq-mining", url)

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_utils._time")
    def test_get_ms_timestamp(self, time_mock):
        time_mock.return_value = 1234567891.23456

        timestamp = utils.get_ms_timestamp()
        self.assertEqual(1234567891234, timestamp)
        # If requested two times at the same moment it should return the same value (writen this way to ensure
        # we are not using the nonce any more
        timestamp = utils.get_ms_timestamp()
        self.assertEqual(1234567891234, timestamp)

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
