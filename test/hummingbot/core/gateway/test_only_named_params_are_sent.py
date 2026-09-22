"""A request carries what the caller named, and nothing the model merely defaulted to.

`gateway_models.py` is generated from Gateway's spec, so a field's default there IS
Gateway's own default for an absent parameter. Echoing it back therefore says nothing
Gateway did not already assume — but it is not harmless, because a default is not
proof the route accepts the parameter at all. `approximateIfNoExactOut` defaults to
True on both router models and applies only to jupiter, dflow, okx and titan; Gateway
answers 400 when any other connector is sent it. Serializing model defaults meant every
uniswap quote and every uniswap swap left this client already rejected:

    Gateway error: approximateIfNoExactOut is not a uniswap parameter — it applies to
    jupiter, dflow, okx, titan. Remove it, or name a connector that takes it.

Verified against a live Gateway: the same quote succeeds with the parameter dropped and
400s with it present.
"""
import unittest
from decimal import Decimal

from hummingbot.core.gateway.gateway_http_client import _body, _query
from hummingbot.core.gateway.gateway_models import ClmmPoolInfoRequest, RouterExecuteSwapRequest, RouterQuoteSwapRequest


class TestOnlyNamedParamsAreSent(unittest.TestCase):

    def _router_quote(self) -> RouterQuoteSwapRequest:
        # The exact kwargs gateway_http_client.quote_swap builds a router quote from.
        return RouterQuoteSwapRequest(
            chainNetwork="ethereum-mainnet",
            connector="uniswap",
            baseToken="WETH",
            quoteToken="USDC",
            amount=Decimal("1"),
            side="SELL",
            slippagePct=None,
        )

    def test_quote_swap_does_not_send_an_unasked_for_approximation_flag(self):
        self.assertNotIn("approximateIfNoExactOut", _query(self._router_quote()))

    def test_execute_swap_does_not_send_an_unasked_for_approximation_flag(self):
        request = RouterExecuteSwapRequest(
            chainNetwork="ethereum-mainnet",
            connector="uniswap",
            baseToken="WETH",
            quoteToken="USDC",
            amount=Decimal("1"),
            side="SELL",
            slippagePct=None,
            walletAddress="0x0000000000000000000000000000000000000001",
        )
        self.assertNotIn("approximateIfNoExactOut", _body(request))

    def test_a_caller_that_asks_for_it_still_gets_it(self):
        # Dropping defaults must not make the parameter unreachable: a connector that
        # does take it has to be able to turn it off.
        request = self._router_quote().model_copy(update={"approximate_if_no_exact_out": False})
        request.__pydantic_fields_set__.add("approximate_if_no_exact_out")
        self.assertEqual("false", _query(request)["approximateIfNoExactOut"])

    def test_every_named_field_still_travels(self):
        # Dropping unset fields must not drop the ones the caller did name.
        self.assertEqual(
            {"chainNetwork", "connector", "baseToken", "quoteToken", "amount", "side"},
            set(_query(self._router_quote())),
        )

    def test_pool_info_leaves_the_bin_count_to_gateway(self):
        # pool_info names no bin_count, so the generated default of 0 must not be sent
        # as though the caller had asked for zero bins.
        query = _query(ClmmPoolInfoRequest(
            connector="meteora",
            chainNetwork="solana-mainnet-beta",
            poolAddress="pool",
        ))
        self.assertNotIn("binCount", query)


if __name__ == "__main__":
    unittest.main()
