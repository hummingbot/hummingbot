import unittest
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class GatewayHttpClientSwapRouteTest(IsolatedAsyncioWrapperTestCase):
    """The swap methods must hit Gateway's unified /trading/swap/* routes, keyed by the
    full 'chain-network' identifier and a 'connector/type' swap provider (not the legacy
    /connectors/{dex}/{type}/*-swap path)."""

    def setUp(self) -> None:
        super().setUp()
        self.client = GatewayHttpClient.get_instance()

    def test_to_chain_network_combines_short_network_with_chain(self):
        self.assertEqual("solana-mainnet-beta", self.client._to_chain_network("mainnet-beta", "solana"))

    def test_to_chain_network_leaves_full_network_untouched(self):
        self.assertEqual("solana-mainnet-beta", self.client._to_chain_network("solana-mainnet-beta", "solana"))
        self.assertEqual("solana-mainnet-beta", self.client._to_chain_network("solana-mainnet-beta", None))

    async def test_quote_swap_uses_unified_route_and_keys(self):
        with patch.object(self.client, "api_request", new=AsyncMock(return_value={"price": "1"})) as mock_req:
            await self.client.quote_swap(
                network="mainnet-beta", chain="solana", dex="jupiter", trading_type="router",
                base_asset="SOL", quote_asset="USDC", amount=Decimal("0.01"), side=TradeType.SELL,
            )
        method, path = mock_req.call_args.args[0], mock_req.call_args.args[1]
        payload = mock_req.call_args.args[2]
        self.assertEqual("get", method)
        self.assertEqual("trading/swap/quote", path)
        self.assertEqual("solana-mainnet-beta", payload["chainNetwork"])
        self.assertEqual("jupiter/router", payload["connector"])
        self.assertEqual("SOL", payload["baseToken"])
        self.assertEqual("USDC", payload["quoteToken"])
        self.assertEqual("SELL", payload["side"])
        self.assertNotIn("network", payload)  # legacy key must be gone

    async def test_execute_swap_uses_unified_route_and_keys(self):
        with patch.object(self.client, "api_request", new=AsyncMock(return_value={"signature": "sig"})) as mock_req:
            await self.client.execute_swap(
                network="mainnet-beta", chain="solana", dex="jupiter", trading_type="router",
                base_asset="SOL", quote_asset="USDC", amount=Decimal("0.02"), side=TradeType.SELL,
                wallet_address="WALLET",
            )
        method, path = mock_req.call_args.args[0], mock_req.call_args.args[1]
        payload = mock_req.call_args.args[2]
        self.assertEqual("post", method)
        self.assertEqual("trading/swap/execute", path)
        self.assertEqual("solana-mainnet-beta", payload["chainNetwork"])
        self.assertEqual("jupiter/router", payload["connector"])
        self.assertEqual("WALLET", payload["walletAddress"])
        self.assertNotIn("network", payload)


if __name__ == "__main__":
    unittest.main()
