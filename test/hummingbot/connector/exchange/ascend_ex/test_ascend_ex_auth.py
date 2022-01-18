import hashlib
import hmac
import mock

from unittest import TestCase

from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth


class AscendExAuthTests(TestCase):

    @property
    def api_key(self):
        return 'test_api_key'

    @property
    def secret_key(self):
        return 'test_secret_key'

    def _get_ms_timestamp(self):
        return str(1633084102569)

    def test_no_authentication_headers(self):
        auth = AscendExAuth(api_key=self.api_key, secret_key=self.secret_key)
        headers = auth.get_headers()

        self.assertEqual(2, len(headers))
        self.assertEqual('application/json', headers.get('Content-Type'))

    def test_authentication_headers(self):

        with mock.patch('hummingbot.connector.exchange.ascend_ex.ascend_ex_auth.get_ms_timestamp') as get_ms_timestamp_mock:
            timestamp = self._get_ms_timestamp()
            get_ms_timestamp_mock.return_value = timestamp
            path_url = "test.com"

            auth = AscendExAuth(api_key=self.api_key, secret_key=self.secret_key)

            headers = auth.get_auth_headers(path_url=path_url)

            message = timestamp + path_url
            expected_signature = hmac.new(self.secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()

            self.assertEqual(3, len(headers))
            self.assertEqual(timestamp, headers.get('x-auth-timestamp'))
            self.assertEqual(self.api_key, headers.get('x-auth-key'))
            self.assertEqual(expected_signature, headers.get('x-auth-signature'))
