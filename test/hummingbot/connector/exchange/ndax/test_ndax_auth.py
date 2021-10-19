import hashlib
import hmac
from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth


class NdaxAuthTests(TestCase):

    @property
    def uid(self):
        return '001'

    @property
    def api_key(self):
        return 'test_api_key'

    @property
    def secret_key(self):
        return 'test_secret_key'

    def test_no_authentication_headers(self):
        auth = NdaxAuth(uid=self.uid, api_key=self.api_key, secret_key=self.secret_key, account_name="hbot")
        headers = auth.get_headers()

        self.assertEqual(1, len(headers))
        self.assertEqual('application/json', headers.get('Content-Type'))

    def test_authentication_headers(self):
        auth = NdaxAuth(uid=self.uid, api_key=self.api_key, secret_key=self.secret_key, account_name="hbot")
        nonce = '1234567890'

        with patch('hummingbot.connector.exchange.ndax.ndax_auth.get_tracking_nonce_low_res') as generate_nonce_mock:
            generate_nonce_mock.return_value = nonce
            headers = auth.get_auth_headers()

        raw_signature = nonce + self.uid + self.api_key
        expected_signature = hmac.new(self.secret_key.encode('utf-8'),
                                      raw_signature.encode('utf-8'),
                                      hashlib.sha256).hexdigest()

        self.assertEqual(5, len(headers))
        self.assertEqual('application/json', headers.get("Content-Type"))
        self.assertEqual('001', headers.get('UserId'))
        self.assertEqual('test_api_key', headers.get('APIKey'))
        self.assertEqual('1234567890', headers.get('Nonce'))
        self.assertEqual(expected_signature, headers.get('Signature'))

    def test_ws_auth_payload(self):
        auth = NdaxAuth(uid=self.uid, api_key=self.api_key, secret_key=self.secret_key, account_name="hbot")
        nonce = '1234567890'

        with patch('hummingbot.connector.exchange.ndax.ndax_auth.get_tracking_nonce_low_res') as generate_nonce_mock:
            generate_nonce_mock.return_value = nonce
            auth_info = auth.get_ws_auth_payload()

        raw_signature = nonce + self.uid + self.api_key
        expected_signature = hmac.new(self.secret_key.encode('utf-8'),
                                      raw_signature.encode('utf-8'),
                                      hashlib.sha256).hexdigest()

        self.assertEqual(4, len(auth_info))
        self.assertEqual('001', auth_info.get('UserId'))
        self.assertEqual('test_api_key', auth_info.get('APIKey'))
        self.assertEqual('1234567890', auth_info.get('Nonce'))
        self.assertEqual(expected_signature, auth_info.get('Signature'))
