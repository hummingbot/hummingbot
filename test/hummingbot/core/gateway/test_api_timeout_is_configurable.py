"""The Gateway request timeout comes from config, not from a literal.

An EVM router quote is an RPC fan-out across candidate pools, and it is slow. Two
pancakeswap BSC quotes, timed against the RPC Gateway is configured with, took 27.9s
and 31.4s -- straddling the 30s this client used to hardcode, so the same quote
succeeded or timed out depending on how the RPC felt. A caller on a slow chain now has
a knob instead of a patch.
"""
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.config.client_config_map import GatewayConfigMap
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class TestApiTimeoutIsConfigurable(unittest.IsolatedAsyncioTestCase):

    def test_default_is_sixty_seconds(self):
        self.assertEqual(Decimal("60"), GatewayConfigMap().gateway_api_timeout)

    def test_a_timeout_of_zero_is_rejected(self):
        # A zero total would fail every request instantly rather than disabling the cap.
        with self.assertRaises(Exception):
            GatewayConfigMap(gateway_api_timeout=Decimal("0"))

    def test_an_existing_config_without_the_key_still_loads(self):
        # conf_client.yml files written before this field existed must keep working.
        cfg = GatewayConfigMap(gateway_api_host="localhost", gateway_api_port="15888", gateway_use_ssl=False)
        self.assertEqual(Decimal("60"), cfg.gateway_api_timeout)

    async def test_the_configured_value_reaches_the_request(self):
        client = GatewayHttpClient.get_instance()
        client._gateway_config = GatewayConfigMap(gateway_api_timeout=Decimal("123"))

        session = MagicMock()
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={})
        session.get = AsyncMock(return_value=response)

        with patch.object(GatewayHttpClient, "_http_client", return_value=session):
            await client.api_request("get", "config/chains", {"a": "b"})

        self.assertEqual(123, session.get.await_args.kwargs["timeout"].total)


if __name__ == "__main__":
    unittest.main()
