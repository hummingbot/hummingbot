import hashlib
import hmac
from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth


class AscendExAuthTests(TestCase):
    @property
    def api_key(self):
        return "test_api_key"

    @property
    def secret_key(self):
        return "test_secret_key"

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_auth.AscendExAuth._time")
    def test_authentication_headers(self, time_mock):
        time_mock.return_value = 1640001112.223

        timestamp = "1640001112223"
        path_url = "test.com"

        auth = AscendExAuth(api_key=self.api_key, secret_key=self.secret_key)

        headers = auth.get_auth_headers(path_url=path_url)

        message = timestamp + path_url
        expected_signature = hmac.new(
            self.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        self.assertEqual(3, len(headers))
        self.assertEqual(timestamp, headers.get("x-auth-timestamp"))
        self.assertEqual(self.api_key, headers.get("x-auth-key"))
        self.assertEqual(expected_signature, headers.get("x-auth-signature"))
