import base64
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_auth import KalshiPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


def _pem(key, private_format: serialization.PrivateFormat) -> str:
    # Keys are generated at runtime: committing a PEM literal trips the detect-private-key pre-commit hook.
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=private_format,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


class KalshiPerpetualAuthTests(IsolatedAsyncioWrapperTestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "a952bcbe-ec3b-4b5b-b8f9-11dae589608c"
        cls.rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        # Kalshi hands out PKCS#1 ("RSA PRIVATE KEY") PEM files.
        cls.pkcs1_pem = _pem(cls.rsa_key, serialization.PrivateFormat.TraditionalOpenSSL)

    def setUp(self) -> None:
        super().setUp()
        self.emulated_time = 1703123456.789
        self.expected_timestamp = "1703123456789"
        self.time_provider = MagicMock()
        self.time_provider.time.return_value = self.emulated_time
        self.auth = KalshiPerpetualAuth(api_key=self.api_key, private_key=self.pkcs1_pem, time_provider=self.time_provider)

    def _assert_valid_signature(self, signature: str, message: str):
        try:
            self.rsa_key.public_key().verify(
                base64.b64decode(signature),
                message.encode("utf-8"),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                hashes.SHA256(),
            )
        except InvalidSignature:
            self.fail(f"Signature does not verify for message {message!r}")

    async def test_rest_authenticate(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://external-api.kalshi.com/trade-api/v2/margin/portfolio/balance",
            params={"limit": 100},
            is_auth_required=True,
        )

        signed_request = await self.auth.rest_authenticate(request)

        self.assertEqual(self.api_key, signed_request.headers["KALSHI-ACCESS-KEY"])
        self.assertEqual(self.expected_timestamp, signed_request.headers["KALSHI-ACCESS-TIMESTAMP"])
        self._assert_valid_signature(
            signed_request.headers["KALSHI-ACCESS-SIGNATURE"],
            f"{self.expected_timestamp}GET/trade-api/v2/margin/portfolio/balance",
        )
        self.assertEqual({"limit": 100}, signed_request.params)

    async def test_rest_authenticate_signs_path_without_query_string(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://external-api.kalshi.com/trade-api/v2/margin/orders?cursor=abc&limit=5",
            is_auth_required=True,
        )

        signed_request = await self.auth.rest_authenticate(request)

        self._assert_valid_signature(
            signed_request.headers["KALSHI-ACCESS-SIGNATURE"],
            f"{self.expected_timestamp}GET/trade-api/v2/margin/orders",
        )

    async def test_rest_authenticate_post_keeps_body_and_existing_headers(self):
        body = json.dumps({"ticker": "KXBTCPERP", "side": "bid"})
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://external-api.kalshi.com/trade-api/v2/margin/orders",
            data=body,
            headers={"Content-Type": "application/json"},
            is_auth_required=True,
        )

        signed_request = await self.auth.rest_authenticate(request)

        self.assertEqual("application/json", signed_request.headers["Content-Type"])
        self.assertEqual(body, signed_request.data)
        self._assert_valid_signature(
            signed_request.headers["KALSHI-ACCESS-SIGNATURE"],
            f"{self.expected_timestamp}POST/trade-api/v2/margin/orders",
        )

    def test_header_for_authentication_for_websocket_handshake(self):
        headers = self.auth.header_for_authentication(method="GET", path="/trade-api/ws/v2/margin")

        self.assertEqual(
            {"KALSHI-ACCESS-KEY", "KALSHI-ACCESS-SIGNATURE", "KALSHI-ACCESS-TIMESTAMP"}, set(headers.keys())
        )
        self.assertEqual(self.expected_timestamp, headers["KALSHI-ACCESS-TIMESTAMP"])
        self._assert_valid_signature(
            headers["KALSHI-ACCESS-SIGNATURE"], f"{self.expected_timestamp}GET/trade-api/ws/v2/margin"
        )

    def test_header_for_authentication_uppercases_method(self):
        headers = self.auth.header_for_authentication(method="delete", path="/trade-api/v2/margin/orders/123")

        self._assert_valid_signature(
            headers["KALSHI-ACCESS-SIGNATURE"], f"{self.expected_timestamp}DELETE/trade-api/v2/margin/orders/123"
        )

    def test_generate_signature_is_rsa_pss_sha256_base64(self):
        message = f"{self.expected_timestamp}GET/trade-api/v2/margin/portfolio/balance"

        first = self.auth._generate_signature(message)
        second = self.auth._generate_signature(message)

        # PSS is randomized: signatures differ, yet both verify. 2048-bit RSA gives a 256-byte signature.
        self.assertNotEqual(first, second)
        self.assertEqual(256, len(base64.b64decode(first)))
        self._assert_valid_signature(first, message)
        self._assert_valid_signature(second, message)

    async def test_ws_authenticate_is_pass_through(self):
        request = WSJSONRequest(payload={"id": 1, "cmd": "subscribe"}, is_auth_required=True)

        signed_request = await self.auth.ws_authenticate(request)

        self.assertIs(request, signed_request)

    def test_load_private_key_accepts_pkcs8(self):
        pkcs8_pem = _pem(self.rsa_key, serialization.PrivateFormat.PKCS8)

        auth = KalshiPerpetualAuth(api_key=self.api_key, private_key=pkcs8_pem, time_provider=self.time_provider)

        self.assertEqual(self.rsa_key.private_numbers(), auth._private_key.private_numbers())

    def test_load_private_key_accepts_escaped_newlines(self):
        escaped_pem = self.pkcs1_pem.strip().replace("\n", "\\n")

        auth = KalshiPerpetualAuth(api_key=self.api_key, private_key=escaped_pem, time_provider=self.time_provider)

        self.assertEqual(self.rsa_key.private_numbers(), auth._private_key.private_numbers())

    def test_load_private_key_accepts_line_breaks_replaced_by_spaces(self):
        lines = self.pkcs1_pem.strip().splitlines()
        # Single-line prompts can turn the body's line breaks into spaces; the header/footer keep their own spaces.
        flattened_pem = f"{lines[0]} {' '.join(lines[1:-1])} {lines[-1]}"

        auth = KalshiPerpetualAuth(api_key=self.api_key, private_key=flattened_pem, time_provider=self.time_provider)

        self.assertEqual(self.rsa_key.private_numbers(), auth._private_key.private_numbers())

    def test_load_private_key_rejects_non_pem_input(self):
        with self.assertRaises(ValueError):
            KalshiPerpetualAuth(api_key=self.api_key, private_key="not-a-key", time_provider=self.time_provider)

    def test_load_private_key_rejects_non_rsa_key(self):
        ec_pem = _pem(ec.generate_private_key(ec.SECP256R1()), serialization.PrivateFormat.PKCS8)

        with self.assertRaises(TypeError):
            KalshiPerpetualAuth(api_key=self.api_key, private_key=ec_pem, time_provider=self.time_provider)
