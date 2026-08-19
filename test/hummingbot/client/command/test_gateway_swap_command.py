import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.command.gateway_swap_command import GatewaySwapCommand
from hummingbot.connector.gateway.gateway import Gateway

# Exactly the keys ChainQuoteSwapResponseSchema returns (gateway src/schemas/chain-schema.ts).
# Fastify serializes strictly to that schema, so nothing else can ever appear here.
UNIFIED_QUOTE_RESPONSE = {
    "tokenIn": "So11111111111111111111111111111111111111112",
    "tokenOut": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "amountIn": 1.0,
    "amountOut": 148.5,
    "price": 148.5,
    "priceImpactPct": 0.02,
    "minAmountOut": 147.0,
    "maxAmountIn": 1.0,
    "routePath": "SOL -> USDC",
    "slippagePct": 1.0,
}


class GatewaySwapCommandQuoteTest(IsolatedAsyncioWrapperTestCase):
    """Pins the `gateway swap` quote path against Gateway's unified swap route."""

    def setUp(self) -> None:
        super().setUp()
        self.notify = MagicMock()
        self.gateway_instance = MagicMock()
        self.gateway_instance.get_default_wallet = AsyncMock(return_value=("WALLET", None))
        self.gateway_instance.quote_swap = AsyncMock(return_value=dict(UNIFIED_QUOTE_RESPONSE))

        self.command = type("TestCommand", (GatewaySwapCommand,), {
            "notify": self.notify,
            "app": MagicMock(to_stop_config=False, prompt=AsyncMock()),
            "logger": MagicMock(return_value=MagicMock()),
            "_get_gateway_instance": MagicMock(return_value=self.gateway_instance),
            "ev_loop": None,
        })()

        self.swap_connector = MagicMock()
        self.swap_connector.swap_provider = "jupiter/router"
        self.swap_connector.start_network = AsyncMock()
        self.swap_connector.stop_network = AsyncMock()
        self.swap_connector.buy = MagicMock(return_value="order-1")
        self.swap_connector.sell = MagicMock(return_value="order-1")

    def _patch_gateway_class(self):
        mock_cls = MagicMock(return_value=self.swap_connector)
        # Keep the real parser: its raise-on-untyped-provider behaviour is under test.
        mock_cls._parse_dex_name = Gateway._parse_dex_name
        return patch("hummingbot.client.command.gateway_swap_command.Gateway", mock_cls)

    async def _run_swap(self, confirm: bool = False):
        with self._patch_gateway_class(), \
                patch("hummingbot.client.command.gateway_swap_command.GatewayCommandUtils") as mock_utils:
            mock_utils.enter_interactive_mode = AsyncMock()
            mock_utils.exit_interactive_mode = AsyncMock()
            mock_utils.prompt_for_confirmation = AsyncMock(return_value=confirm)
            mock_utils.monitor_transaction_with_timeout = AsyncMock(
                return_value={"success": True, "tx_hash": "sig"}
            )
            await self.command._gateway_swap("solana-mainnet-beta", "SOL-USDC", "BUY", "1")
            return mock_utils

    async def test_quote_swap_not_called_with_pool_address(self):
        """quote_swap has no pool_address parameter — passing one was a TypeError on
        every invocation, and the unified route resolves the pool itself."""
        await self._run_swap()
        self.gateway_instance.quote_swap.assert_awaited_once()
        kwargs = self.gateway_instance.quote_swap.await_args.kwargs
        self.assertNotIn("pool_address", kwargs)
        self.assertEqual("solana", kwargs["chain"])
        self.assertEqual("mainnet-beta", kwargs["network"])
        self.assertEqual("jupiter", kwargs["dex"])
        self.assertEqual("router", kwargs["trading_type"])

    async def test_displays_only_fields_the_schema_returns(self):
        await self._run_swap()
        messages = [call.args[0] for call in self.notify.call_args_list if call.args]
        self.assertTrue(any("Price Impact: 0.02%" == m for m in messages))
        self.assertTrue(any("Route: SOL -> USDC" == m for m in messages))
        self.assertTrue(any("Amount Out: 148.5" in m for m in messages))
        # Nothing may be rendered from keys the unified response cannot carry
        joined = "\n".join(messages)
        self.assertNotIn("Transaction Fee", joined)
        self.assertNotIn("WARNINGS", joined)

    async def test_execute_passes_no_quote_id(self):
        """The unified route caches no quote, so there is no quoteId to hand the
        connector — passing one would send it down the dead execute_quote path."""
        await self._run_swap(confirm=True)
        self.swap_connector.buy.assert_called_once()
        self.assertNotIn("quote_id", self.swap_connector.buy.call_args.kwargs)
        self.assertNotIn("quote_response", self.swap_connector.buy.call_args.kwargs)

    async def test_untyped_swap_provider_is_reported(self):
        self.swap_connector.swap_provider = "meteora"
        await self._run_swap()
        joined = "\n".join(call.args[0] for call in self.notify.call_args_list if call.args)
        self.assertIn("name/type", joined)
        self.gateway_instance.quote_swap.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
