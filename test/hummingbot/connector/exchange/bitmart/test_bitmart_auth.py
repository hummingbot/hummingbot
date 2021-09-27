import json
import hmac
import hashlib
from unittest import TestCase

from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth


class BitmartAuthTests(TestCase):

    @property
    def memo(self):
        return '001'

    @property
    def api_key(self):
        return 'test_api_key'

    @property
    def secret_key(self):
        return 'test_secret_key'

    def test_no_authentication_headers(self):
        auth = BitmartAuth(api_key=self.api_key, secret_key=self.secret_key, memo=self.memo)
        headers = auth.get_headers()

        self.assertEqual(1, len(headers))
        self.assertEqual('application/json', headers.get('Content-Type'))

    def test_keyed_authentication_headers(self):
        auth = BitmartAuth(api_key=self.api_key, secret_key=self.secret_key, memo=self.memo)
        headers = auth.get_headers(auth_type="KEYED")

        self.assertEqual(2, len(headers))
        self.assertEqual('application/json', headers.get("Content-Type"))
        self.assertEqual('test_api_key', headers.get('X-BM-KEY'))

    def test_signed_authentication_headers(self):
        auth = BitmartAuth(api_key=self.api_key, secret_key=self.secret_key, memo=self.memo)
        timestamp = '1589793795969'
        params = {'test_key': 'test_value'}
        headers = auth.get_headers(timestamp=timestamp, params=params, auth_type="SIGNED")

        params = json.dumps(params)
        raw_signature = f'{timestamp}#{self.memo}#{params}'
        expected_signature = hmac.new(self.secret_key.encode('utf-8'),
                                      raw_signature.encode('utf-8'),
                                      hashlib.sha256).hexdigest()

        self.assertEqual(4, len(headers))
        self.assertEqual('application/json', headers.get("Content-Type"))
        self.assertEqual('test_api_key', headers.get('X-BM-KEY'))
        self.assertEqual(expected_signature, headers.get('X-BM-SIGN'))
        self.assertEqual('1589793795969', headers.get('X-BM-TIMESTAMP'))

    def test_ws_auth_payload(self):
        auth = BitmartAuth(api_key=self.api_key, secret_key=self.secret_key, memo=self.memo)
        timestamp = '1589793795969'
        auth_info = auth.get_ws_auth_payload(timestamp=timestamp)

        raw_signature = f'{timestamp}#{self.memo}#bitmart.WebSocket'
        expected_signature = hmac.new(self.secret_key.encode('utf-8'),
                                      raw_signature.encode('utf-8'),
                                      hashlib.sha256).hexdigest()

        self.assertEqual(2, len(auth_info))
        self.assertEqual(3, len(auth_info.get('args')))
        self.assertEqual('login', auth_info.get('op'))
        self.assertEqual(['test_api_key', '1589793795969', expected_signature], auth_info.get('args'))
