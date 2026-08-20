import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class GatewayHttpClientLPRouteTest(IsolatedAsyncioWrapperTestCase):
    """The LP methods must hit Gateway's unified /trading/{clmm,amm}/* routes, keyed by a
    'connector' name plus the full 'chain-network' identifier (not the legacy
    /connectors/{dex}/{type}/* path), and must send every field those routes declare
    required.

    Payload keys below are asserted against ~/gateway's unified route schemas
    (src/trading/trading-clmm-routes/*, src/trading/trading-amm-routes/*,
    src/trading/clmm/*)."""

    def setUp(self) -> None:
        super().setUp()
        self.client = GatewayHttpClient.get_instance()

    def _capture(self):
        return patch.object(self.client, "api_request", new=AsyncMock(return_value={"signature": "sig"}))

    def _sent(self, mock_req):
        """(method, path, payload) of the single captured request."""
        args = mock_req.call_args.args
        payload = args[2] if len(args) > 2 else mock_req.call_args.kwargs["params"]
        return args[0], args[1], payload

    # ------------------------------------------------------------------ routing

    def test_lp_route_rejects_a_trading_type_with_no_unified_route(self):
        with self.assertRaises(ValueError):
            self.client._lp_route("router", "open")

    # ------------------------------------------------------------------ CLMM

    async def test_clmm_open_position_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.clmm_open_position(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                pool_address="POOL", lower_price=1.0, upper_price=2.0, dex="meteora",
                base_token_amount=1.5, quote_token_amount=3.0, slippage_pct=1.0,
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("post", method)
        self.assertEqual("trading/clmm/open", path)
        self.assertEqual("meteora", payload["connector"])
        self.assertEqual("solana-mainnet-beta", payload["chainNetwork"])
        self.assertEqual("WALLET", payload["walletAddress"])
        self.assertEqual("POOL", payload["poolAddress"])
        self.assertEqual(1.0, payload["lowerPrice"])
        self.assertEqual(2.0, payload["upperPrice"])
        self.assertEqual(1.5, payload["baseTokenAmount"])
        self.assertEqual(3.0, payload["quoteTokenAmount"])
        self.assertNotIn("network", payload)  # legacy key must be gone

    async def test_clmm_open_position_single_sided_omits_the_other_amount(self):
        # The unified route makes both amounts optional (at least one required), so a
        # single-sided open sends only the funded side rather than a fabricated zero.
        with self._capture() as mock_req:
            await self.client.clmm_open_position(
                network="solana-mainnet-beta", wallet_address="WALLET", pool_address="POOL",
                lower_price=1.0, upper_price=2.0, dex="raydium", quote_token_amount=10.0,
            )
        _, _, payload = self._sent(mock_req)
        self.assertEqual(10.0, payload["quoteTokenAmount"])
        self.assertNotIn("baseTokenAmount", payload)

    async def test_clmm_add_liquidity_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.clmm_add_liquidity(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                position_address="POS", dex="orca", base_token_amount=2.0,
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("post", method)
        self.assertEqual("trading/clmm/add", path)
        self.assertEqual("orca", payload["connector"])
        self.assertEqual("solana-mainnet-beta", payload["chainNetwork"])
        self.assertEqual("POS", payload["positionAddress"])
        self.assertEqual(2.0, payload["baseTokenAmount"])
        self.assertNotIn("quoteTokenAmount", payload)
        self.assertNotIn("network", payload)

    async def test_clmm_remove_liquidity_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.clmm_remove_liquidity(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                position_address="POS", percentage=50.0, dex="meteora",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("post", method)
        self.assertEqual("trading/clmm/remove", path)
        self.assertEqual("POS", payload["positionAddress"])
        self.assertEqual(50.0, payload["percentageToRemove"])
        self.assertNotIn("network", payload)

    async def test_clmm_close_position_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.clmm_close_position(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                position_address="POS", dex="meteora",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("post", method)
        self.assertEqual("trading/clmm/close", path)
        self.assertEqual("POS", payload["positionAddress"])
        self.assertNotIn("network", payload)

    async def test_clmm_collect_fees_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.clmm_collect_fees(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                position_address="POS", dex="meteora",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("post", method)
        self.assertEqual("trading/clmm/collect-fees", path)
        self.assertEqual("POS", payload["positionAddress"])
        self.assertNotIn("network", payload)

    async def test_clmm_position_info_uses_unified_route_and_sends_no_wallet(self):
        # The unified position-info route is keyed by the position address alone.
        with self._capture() as mock_req:
            await self.client.clmm_position_info(
                network="mainnet-beta", chain="solana", position_address="POS", dex="meteora",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("get", method)
        self.assertEqual("trading/clmm/position-info", path)
        self.assertEqual("POS", payload["positionAddress"])
        self.assertNotIn("walletAddress", payload)
        self.assertNotIn("network", payload)

    async def test_clmm_positions_owned_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.clmm_positions_owned(
                network="mainnet-beta", chain="solana", wallet_address="WALLET", dex="meteora",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("get", method)
        self.assertEqual("trading/clmm/positions-owned", path)
        self.assertEqual("WALLET", payload["walletAddress"])
        self.assertNotIn("network", payload)

    async def test_clmm_quote_position_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.clmm_quote_position(
                network="mainnet-beta", chain="solana", pool_address="POOL",
                lower_price=1.0, upper_price=2.0, dex="meteora", base_token_amount=1.0,
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("get", method)
        self.assertEqual("trading/clmm/quote-liquidity", path)
        self.assertEqual("POOL", payload["poolAddress"])
        self.assertNotIn("quoteTokenAmount", payload)
        self.assertNotIn("network", payload)

    async def test_pool_info_routes_per_trading_type(self):
        with self._capture() as mock_req:
            await self.client.pool_info(
                network="mainnet-beta", chain="solana", pool_address="POOL", dex="meteora",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("get", method)
        self.assertEqual("trading/clmm/pool-info", path)
        self.assertEqual("POOL", payload["poolAddress"])
        self.assertNotIn("network", payload)

        with self._capture() as mock_req:
            await self.client.pool_info(
                network="mainnet-beta", chain="solana", pool_address="POOL", dex="meteora",
                trading_type="amm",
            )
        _, path, _ = self._sent(mock_req)
        self.assertEqual("trading/amm/pool-info", path)

    # ------------------------------------------------------------------ AMM

    async def test_amm_add_liquidity_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.amm_add_liquidity(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                pool_address="POOL", base_token_amount=1.0, quote_token_amount=2.0,
                dex="meteora", position_address="POS",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("post", method)
        self.assertEqual("trading/amm/add", path)
        self.assertEqual("meteora", payload["connector"])
        self.assertEqual("solana-mainnet-beta", payload["chainNetwork"])
        self.assertEqual("POOL", payload["poolAddress"])
        self.assertEqual(1.0, payload["baseTokenAmount"])
        self.assertEqual(2.0, payload["quoteTokenAmount"])
        self.assertEqual("POS", payload["positionAddress"])
        self.assertNotIn("network", payload)

    async def test_amm_remove_liquidity_sends_the_position_address(self):
        # Meteora DAMM v2 positions are NFTs and a wallet may hold several per pool, so
        # the removal has to name one; omitting it 400s on Meteora's schema.
        with self._capture() as mock_req:
            await self.client.amm_remove_liquidity(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                pool_address="POOL", percentage=100.0, dex="meteora", position_address="POS",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("post", method)
        self.assertEqual("trading/amm/remove", path)
        self.assertEqual("POOL", payload["poolAddress"])
        self.assertEqual("POS", payload["positionAddress"])
        self.assertEqual(100.0, payload["percentageToRemove"])
        self.assertNotIn("network", payload)

    async def test_amm_remove_liquidity_omits_position_address_when_not_given(self):
        # Fungible-LP AMMs address a holding by pool alone.
        with self._capture() as mock_req:
            await self.client.amm_remove_liquidity(
                network="solana-mainnet-beta", wallet_address="WALLET", pool_address="POOL",
                percentage=100.0, dex="raydium",
            )
        _, _, payload = self._sent(mock_req)
        self.assertNotIn("positionAddress", payload)

    async def test_amm_position_info_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.amm_position_info(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                pool_address="POOL", dex="meteora",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("get", method)
        self.assertEqual("trading/amm/position-info", path)
        self.assertEqual("POOL", payload["poolAddress"])
        self.assertEqual("WALLET", payload["walletAddress"])
        self.assertNotIn("network", payload)

    async def test_amm_quote_liquidity_uses_unified_route_and_keys(self):
        with self._capture() as mock_req:
            await self.client.amm_quote_liquidity(
                network="mainnet-beta", chain="solana", pool_address="POOL",
                base_token_amount=1.0, quote_token_amount=2.0, dex="raydium",
            )
        method, path, payload = self._sent(mock_req)
        self.assertEqual("get", method)
        self.assertEqual("trading/amm/quote-liquidity", path)
        self.assertEqual("POOL", payload["poolAddress"])
        self.assertNotIn("network", payload)


class GatewayRequestSerializationTest(IsolatedAsyncioWrapperTestCase):
    """The wire types the request models are serialized to.

    The methods above build their payloads from the models generated off Gateway's
    OpenAPI spec, so the field *names* are checked against the spec by construction.
    What is not checked by construction is how the values are rendered, and the models
    hold amounts as Decimal — a type neither json.dumps nor a query string accepts as
    it stands. These pin the two conversions:

    - a JSON body carries numbers as numbers. `model_dump(mode="json")` would render
      Decimal as a string, and Gateway declares these fields `type: number`.
    - a query string carries everything as text, which is what a URL can hold.

    Both drop fields left as None rather than sending null, because Gateway applies its
    own default for an absent parameter.
    """

    def setUp(self) -> None:
        super().setUp()
        self.client = GatewayHttpClient.get_instance()

    def _capture(self):
        return patch.object(self.client, "api_request", new=AsyncMock(return_value={"signature": "sig"}))

    def _sent(self, mock_req):
        args = mock_req.call_args.args
        return args[2] if len(args) > 2 else mock_req.call_args.kwargs["params"]

    async def test_a_body_carries_amounts_as_json_numbers(self):
        with self._capture() as mock_req:
            await self.client.amm_add_liquidity(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                pool_address="POOL", base_token_amount=0.1, quote_token_amount=2.0,
                dex="meteora", slippage_pct=1.0,
            )
        payload = self._sent(mock_req)
        for key in ("baseTokenAmount", "quoteTokenAmount", "slippagePct"):
            # assertEqual would not catch this: Decimal("0.1") == 0.1 is True, and a
            # Decimal reaches aiohttp as an unserializable object rather than a number.
            self.assertIsInstance(payload[key], float, f"{key} must be a JSON number")
        self.assertEqual(0.1, payload["baseTokenAmount"], "float -> Decimal -> float must round-trip")

    async def test_a_query_carries_everything_as_text(self):
        with self._capture() as mock_req:
            await self.client.clmm_quote_position(
                network="mainnet-beta", chain="solana", pool_address="POOL",
                lower_price=1.5, upper_price=2.5, dex="meteora", base_token_amount=0.1,
            )
        params = self._sent(mock_req)
        self.assertTrue(all(isinstance(v, str) for v in params.values()), params)
        self.assertEqual("0.1", params["baseTokenAmount"])
        self.assertEqual("1.5", params["lowerPrice"])

    async def test_omitted_optionals_are_absent_rather_than_null(self):
        with self._capture() as mock_req:
            await self.client.clmm_open_position(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                pool_address="POOL", lower_price=1.0, upper_price=2.0, dex="meteora",
                base_token_amount=1.5,
            )
        payload = self._sent(mock_req)
        self.assertNotIn("quoteTokenAmount", payload)
        self.assertNotIn("slippagePct", payload)
        self.assertNotIn(None, payload.values())

    async def test_connector_specific_params_survive_the_model(self):
        # strategyType is named by the connector, not by the route, so it is merged after
        # the model rather than validated against it.
        with self._capture() as mock_req:
            await self.client.clmm_open_position(
                network="mainnet-beta", chain="solana", wallet_address="WALLET",
                pool_address="POOL", lower_price=1.0, upper_price=2.0, dex="meteora",
                base_token_amount=1.5, extra_params={"strategyType": 0},
            )
        self.assertEqual(0, self._sent(mock_req)["strategyType"])

    async def test_an_unknown_trading_type_is_rejected_before_the_request(self):
        """A wrong type used to reach Gateway as a 404; the model map names the options."""
        with self.assertRaises(ValueError) as ctx:
            await self.client.quote_swap(
                network="mainnet-beta", chain="solana", base_asset="SOL",
                quote_asset="USDC", amount=1, side=TradeType.SELL,
                dex="meteora", trading_type="nonsense",
            )
        self.assertIn("nonsense", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
