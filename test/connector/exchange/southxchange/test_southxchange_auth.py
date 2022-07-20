import hashlib
import hmac
import json
from typing import Dict, Any
from unittest import TestCase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.exchange.southxchange.southxchange_auth import SouthXchangeAuth


class SouthXchangeAuthTests(TestCase):

    @property
    def api_key(self):
        return 'test_api_key'

    @property
    def secret_key(self):
        return 'test_secret_key'

    def _get_ms_timestamp(self):
        return str(1633084102569)

    def test_authentication_headers(self):
        path_url = "test.com"
        _time_provider = TimeSynchronizer()
        auth = SouthXchangeAuth(api_key=self.api_key, secret_key=self.secret_key, time_provider=_time_provider)

        auth_result = auth.get_auth_headers(path_url=path_url)
        auth_header = auth_result['header']
        auth_data = auth_result['data']

        request_params: Dict[str, Any] = {}
        request_params['nonce'] = str(auth_data.get('nonce'))
        request_params['key'] = self.api_key
        userSignature = hmac.new(
            self.secret_key.encode('utf-8'),
            json.dumps(request_params).encode('utf8'),
            hashlib.sha512
        ).hexdigest()
        self.assertEqual(2, len(auth_header))
        self.assertEqual(userSignature, auth_header.get('Hash'))
        self.assertEqual('application/json', auth_header.get('Content-Type'))
