import hashlib
import hmac
import time

from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth


class BybitPerpetualAuthTests(TestCase):

    @property
    def api_key(self):
        return 'test_api_key'

    @property
    def secret_key(self):
        return 'test_secret_key'

    def _get_timestamp(self):
        return str(int(time.time() * 1e3))

    def _get_expiration_timestamp(self):
        return str(int(time.time() + 1 * 1e3))

    def test_no_authentication_headers(self):
        auth = BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)
        headers = auth.get_headers()

        self.assertEqual(1, len(headers))
        self.assertEqual('application/json', headers.get('Content-Type'))

    def test_authentication_headers(self):
        auth = BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)

        timestamp = self._get_timestamp()
        headers = {}

        with patch.object(auth, 'get_timestamp') as get_timestamp_mock:
            get_timestamp_mock.return_value = timestamp
            headers = auth.extend_params_with_authentication_info(headers)

        raw_signature = "api_key=" + self.api_key + "&timestamp=" + timestamp
        expected_signature = hmac.new(self.secret_key.encode('utf-8'),
                                      raw_signature.encode('utf-8'),
                                      hashlib.sha256).hexdigest()

        self.assertEqual(3, len(headers))
        self.assertEqual(timestamp, headers.get('timestamp'))
        self.assertEqual(self.api_key, headers.get('api_key'))
        self.assertEqual(expected_signature, headers.get('sign'))

    def test_ws_auth_payload(self):
        auth = BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)

        expires = self._get_expiration_timestamp()

        with patch.object(auth, 'get_expiration_timestamp') as get_expires_ts_mock:
            get_expires_ts_mock.return_value = expires
            payload = auth.get_ws_auth_payload()

        raw_signature = 'GET/realtime' + expires
        expected_signature = hmac.new(self.secret_key.encode('utf-8'),
                                      raw_signature.encode('utf-8'),
                                      hashlib.sha256).hexdigest()

        self.assertEqual(3, len(payload))
        self.assertEqual(self.api_key, payload[0])
        self.assertEqual(expires, payload[1])
        self.assertEqual(expected_signature, payload[2])

    def test_get_header_without_referer(self):
        auth = BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)
        expected_header = {
            "Content-Type": "application/json"
        }

        header = auth.get_headers()
        self.assertTrue(header, expected_header)

    def test_get_header_with_referer(self):
        auth = BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)
        expected_header = {
            "Content-Type": "application/json",
            "Referer": CONSTANTS.HBOT_BROKER_ID
        }

        header = auth.get_headers(referer_header_required=True)
        self.assertTrue(header, expected_header)
