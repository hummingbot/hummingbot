import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.gateway.gateway import Gateway
from hummingbot.connector.gateway.gateway_base import GatewayBase, RetryAction, extract_error_code
from hummingbot.core.gateway.gateway_error import GatewayError
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class GatewayErrorShapeTest(unittest.TestCase):
    """GatewayError has to carry Gateway's structured fields AND keep rendering the
    exact string the flattened ValueError used to produce, since callers still
    string-match on 'Gateway error:' and '[code: X]'."""

    def test_attributes(self):
        err = GatewayError(
            "Insufficient balance for swap",
            status=400,
            code="INSUFFICIENT_BALANCE",
            error_type="SwapError",
            http_error="Bad Request",
        )
        self.assertEqual(400, err.status)
        self.assertEqual("INSUFFICIENT_BALANCE", err.code)
        self.assertEqual("Insufficient balance for swap", err.message)
        self.assertEqual("SwapError", err.error_type)
        self.assertEqual("Bad Request", err.http_error)

    def test_str_format_unchanged(self):
        err = GatewayError(
            "Insufficient balance for swap",
            status=400,
            code="INSUFFICIENT_BALANCE",
            error_type="SwapError",
            http_error="Bad Request",
        )
        self.assertEqual(
            "Gateway error: SwapError: Insufficient balance for swap (Bad Request) [code: INSUFFICIENT_BALANCE]",
            str(err),
        )

    def test_str_format_without_optional_fields(self):
        self.assertEqual("Gateway error: boom", str(GatewayError("boom", status=500)))

    def test_is_a_value_error(self):
        # Gateway failures have always been ValueErrors; existing handlers keep working.
        self.assertIsInstance(GatewayError("boom"), ValueError)


class GatewayErrorRaisedByApiRequestTest(IsolatedAsyncioWrapperTestCase):
    """api_request must raise the structured error, with the HTTP status attached."""

    def setUp(self) -> None:
        super().setUp()
        self.client = GatewayHttpClient.get_instance()

    def _mock_http_client(self, status: int, body: dict):
        response = MagicMock()
        response.status = status
        response.json = AsyncMock(return_value=body)
        http_client = MagicMock()
        http_client.get = AsyncMock(return_value=response)
        return http_client

    async def test_non_200_raises_gateway_error_with_status_and_code(self):
        http_client = self._mock_http_client(
            400,
            {
                "message": "Slippage exceeded",
                "code": "SLIPPAGE_EXCEEDED",
                "error": "Bad Request",
                "name": "SwapError",
            },
        )
        with patch.object(self.client, "_http_client", return_value=http_client):
            with self.assertRaises(GatewayError) as ctx:
                await self.client.api_request("get", "trading/swap/quote", {"chainNetwork": "solana-mainnet-beta"})
        self.assertEqual(400, ctx.exception.status)
        self.assertEqual("SLIPPAGE_EXCEEDED", ctx.exception.code)
        self.assertEqual("Slippage exceeded", ctx.exception.message)
        self.assertIn("[code: SLIPPAGE_EXCEEDED]", str(ctx.exception))

    async def test_404_keeps_status(self):
        http_client = self._mock_http_client(
            404, {"message": "Position not found or closed: pos123", "error": "Not Found"}
        )
        with patch.object(self.client, "_http_client", return_value=http_client):
            with self.assertRaises(GatewayError) as ctx:
                await self.client.api_request("get", "connectors/orca/clmm/position-info")
        self.assertEqual(404, ctx.exception.status)
        self.assertIsNone(ctx.exception.code)


class ExtractErrorCodeTest(unittest.TestCase):
    """The code must come off the exception, not out of its prose, when one is available."""

    def test_reads_attribute_not_string(self):
        err = GatewayError("nope", status=400, code="TRANSACTION_TIMEOUT")
        # The rendered message is frozen at construction, so a differing attribute
        # proves the attribute — not the "[code: ...]" prose — is what gets read.
        err.code = "SLIPPAGE_EXCEEDED"
        self.assertIn("[code: TRANSACTION_TIMEOUT]", str(err))
        self.assertEqual("SLIPPAGE_EXCEEDED", extract_error_code(err))

    def test_falls_back_to_string_for_plain_exceptions(self):
        # The connector synthesizes its own transaction errors with the code in prose.
        self.assertEqual(
            "TX_NOT_CONFIRMED",
            extract_error_code(Exception("Transaction sig not confirmed on-chain [code: TX_NOT_CONFIRMED]")),
        )

    def test_returns_none_without_a_code(self):
        self.assertIsNone(extract_error_code(Exception("something broke")))
        self.assertIsNone(extract_error_code(GatewayError("something broke", status=500)))


class ClassifyErrorUsesCodeAttributeTest(unittest.TestCase):
    """_classify_error must route on GatewayError.code."""

    def setUp(self) -> None:
        self.connector = MagicMock()
        self.connector.logger = MagicMock(return_value=MagicMock())

    def _classify(self, error, retries=0, max_retries=10):
        return GatewayBase._classify_error(self.connector, error, "execute swap", retries, max_retries)

    def test_non_retryable_code(self):
        err = GatewayError("Slippage exceeded", status=400, code="SLIPPAGE_EXCEEDED")
        self.assertEqual(RetryAction.FAIL_IMMEDIATE, self._classify(err))

    def test_retryable_code(self):
        err = GatewayError("Transaction pending", status=504, code="TRANSACTION_TIMEOUT")
        self.assertEqual(RetryAction.RETRY, self._classify(err))

    def test_retryable_code_out_of_retries(self):
        err = GatewayError("Too many requests", status=429, code="RATE_LIMITED")
        self.assertEqual(RetryAction.STOP, self._classify(err, retries=10, max_retries=10))

    def test_unknown_code_fails_immediately(self):
        err = GatewayError("Something odd", status=500, code="WHO_KNOWS")
        self.assertEqual(RetryAction.FAIL_IMMEDIATE, self._classify(err))


class ParseDexNameContractTest(unittest.TestCase):
    """An untyped swap provider must raise instead of silently becoming '<name>/router':
    Gateway rejects the guess with a 400, and the LP executor only reaches this while
    closing out a position."""

    def test_typed_provider_parses(self):
        self.assertEqual(("meteora", "clmm"), Gateway._parse_dex_name("meteora/clmm"))
        self.assertEqual(("jupiter", "router"), Gateway._parse_dex_name("jupiter/router"))

    def test_untyped_provider_raises(self):
        with self.assertRaises(ValueError) as ctx:
            Gateway._parse_dex_name("meteora")
        self.assertIn("meteora", str(ctx.exception))
        self.assertIn("name/type", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
