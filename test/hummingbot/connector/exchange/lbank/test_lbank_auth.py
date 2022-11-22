import asyncio
import hashlib
import hmac
import json
from base64 import b64encode
from typing import Any, Awaitable, Dict, OrderedDict
from unittest import TestCase
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class LbankAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.rsa_api_key = "justSomeRandomlyGeneratedApiKey"

        # A randomly generated RSA key.
        self.rsa_secret_key = """MIIBOgIBAAJBAO71SQVEwgssrzRgHs5yzUtpHA6McKyorRWKQweNs3dbR69eq+az
                                hXl6BOeysdW41WIFz61sXCwW4tLDzUk6gCUCAwEAAQJAKEDprBmJFpjQauJGTkDI
                                lIuATnMaB/viLF6+K+eS8+f5NE79oXPwb+XGivRve90kiN5bh+HmhTvFCzS/Qeto
                                AQIhAPtQg78Ow7nEoiNIJyg7MYbJkV+tEElbupn3jcmD1ADVAiEA82nLqynk/hNO
                                0+D1xtBnY/mX8/AYNwIF+I4vGAW1qhECIBFHded7AmYRaPx4B4kymLMlxMMJSSdi
                                ETBo3uzODZOJAiEAxbQSVq2qbqtkBTfcqGSw9UTOpLVIFbWw/9cMbSiGCuECID/6
                                49TAwxBJUU4zkbbGgJY9lX+l0jESa2bTWhvcRyaE"""

        self.hmac_api_key = "justAnotherRandomlyGeneratedApiKey"
        self.hmac_secret_key = "anotherSecretKey"

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.rsa_auth = LbankAuth(api_key=self.rsa_api_key, secret_key=self.rsa_secret_key, auth_method="RSA")
        self.hmac_auth = LbankAuth(api_key=self.hmac_api_key, secret_key=self.hmac_secret_key, auth_method="HmacSHA256")

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _rsa_sign(self, data: Dict[str, Any], expected_rand_str: str, expected_timestamp: str) -> str:
        new_data = {}
        new_data.update(data)
        new_data.update(
            {
                "api_key": self.rsa_api_key,
                "echostr": expected_rand_str,
                "signature_method": "RSA",
                "timestamp": expected_timestamp,
            }
        )
        payload: str = hashlib.md5(urlencode(dict(sorted(new_data.items()))).encode("utf-8")).hexdigest().upper()
        key = RSA.importKey(LbankAuth.RSA_KEY_FORMAT.format(self.rsa_secret_key))
        signer = PKCS1_v1_5.new(key)
        digest = SHA256.new()
        digest.update(payload.encode("utf-8"))
        sig = b64encode(signer.sign(digest))
        return sig.decode("utf-8")

    def _hmac_sign(self, data: Dict[str, Any], expected_rand_str: str, expected_timestamp: str):
        new_data = OrderedDict()
        new_data.update(data)
        new_data.update(
            {
                "api_key": self.hmac_api_key,
                "echostr": expected_rand_str,
                "signature_method": "HmacSHA256",
                "timestamp": expected_timestamp,
            }
        )
        payload: str = hashlib.md5(urlencode(dict(sorted(new_data.items()))).encode("utf-8")).hexdigest().upper()
        secret_bytes = bytes(self.hmac_secret_key, encoding="utf-8")
        payload_bytes = bytes(payload, encoding="utf-8")
        signature = hmac.new(secret_bytes, payload_bytes, digestmod=hashlib.sha256).hexdigest().lower()
        return signature

    @patch("hummingbot.connector.exchange.lbank.lbank_auth.LbankAuth._time")
    @patch("hummingbot.connector.exchange.lbank.lbank_auth.LbankAuth._generate_rand_str")
    def test_rsa_authentication(self, mock_rand, mock_time):

        mock_rand.return_value = "A" * 35
        mock_time.return_value = 1

        body = {"test_param": "test_value"}
        request = RESTRequest(
            method=RESTMethod.POST, url="https://test.url/api/endpoint", data=json.dumps(body), is_auth_required=True,
        )

        signed_request: RESTRequest = self.async_run_with_timeout(self.rsa_auth.rest_authenticate(request))

        expected_signature: str = self._rsa_sign(body, mock_rand.return_value, mock_time.return_value)

        self.assertIn("echostr", signed_request.headers)
        self.assertEqual(mock_rand.return_value, signed_request.headers["echostr"])
        self.assertIn("signature_method", signed_request.headers)
        self.assertEqual(self.rsa_auth.auth_method, signed_request.headers["signature_method"])
        self.assertIn("timestamp", signed_request.headers)
        self.assertEqual(str(mock_time.return_value), signed_request.headers["timestamp"])
        self.assertIn("Content-Type", signed_request.headers)
        self.assertEqual("application/x-www-form-urlencoded", signed_request.headers["Content-Type"])
        self.assertIn("sign", signed_request.data)
        self.assertEqual(expected_signature, signed_request.data["sign"])

    @patch("hummingbot.connector.exchange.lbank.lbank_auth.LbankAuth._time")
    @patch("hummingbot.connector.exchange.lbank.lbank_auth.LbankAuth._generate_rand_str")
    def test_hmac_authentication(self, mock_rand, mock_time):

        mock_rand.return_value = "A" * 35
        mock_time.return_value = 1

        body = {"test_param": "test_value"}
        request = RESTRequest(
            method=RESTMethod.POST, url="https://test.url/api/endpoint", data=json.dumps(body), is_auth_required=True,
        )

        signed_request: RESTRequest = self.async_run_with_timeout(self.hmac_auth.rest_authenticate(request))

        expected_signature = self._hmac_sign(body, mock_rand.return_value, mock_time.return_value)

        self.assertIn("echostr", signed_request.headers)
        self.assertEqual(mock_rand.return_value, signed_request.headers["echostr"])
        self.assertIn("signature_method", signed_request.headers)
        self.assertEqual(self.hmac_auth.auth_method, signed_request.headers["signature_method"])
        self.assertIn("timestamp", signed_request.headers)
        self.assertEqual(str(mock_time.return_value), signed_request.headers["timestamp"])
        self.assertIn("Content-Type", signed_request.headers)
        self.assertEqual("application/x-www-form-urlencoded", signed_request.headers["Content-Type"])
        self.assertIn("sign", signed_request.data)
        self.assertEqual(expected_signature, signed_request.data["sign"])
