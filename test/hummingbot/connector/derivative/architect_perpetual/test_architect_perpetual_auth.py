import base64
import hashlib
import hmac
import unittest

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class _FixedTime:
    def __init__(self, t: float):
        self._t = t

    def time(self) -> float:
        return self._t


class ArchitectPerpetualAuthTests(unittest.TestCase):

    def test_rest_authenticate_adds_headers(self):
        api_key = "k"
        api_secret = "s"
        tp = _FixedTime(1700000000.0)
        auth = ArchitectPerpetualAuth(api_key, api_secret, time_provider=tp)

        req = RESTRequest(method=RESTMethod.POST, url="https://example.com/api/v1/order?x=1", data={"a": 1})
        req = self.async_run(auth.rest_authenticate(req))

        self.assertIn("X-ARCH-API-KEY", req.headers)
        self.assertIn("X-ARCH-TS", req.headers)
        self.assertIn("X-ARCH-SIGN", req.headers)
        self.assertEqual(api_key, req.headers["X-ARCH-API-KEY"])
        self.assertEqual(str(int(1700000000.0 * 1e3)), req.headers["X-ARCH-TS"])

        ts = req.headers["X-ARCH-TS"]
        prehash = f"{ts}POST/api/v1/order?x=1{{\"a\":1}}"
        expected = base64.b64encode(hmac.new(api_secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()
        self.assertEqual(expected, req.headers["X-ARCH-SIGN"])

    @staticmethod
    def async_run(coro):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError()
        except Exception:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
