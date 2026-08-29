import asyncio
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

from controllers.generic.lp_rebalancer.lp_rebalancer import LPRebalancer, LPRebalancerConfig
from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider


class TestLPRebalancerAutoswapDustFloor(TestCase):
    """Autoswap must ignore deficits too small for a router to execute.

    Wallet balances rarely land exactly on total_amount_quote - fees, gas and
    rounding leave them a fraction short - and any positive deficit used to
    trigger a swap. A deficit of a few millionths of a token cannot be routed,
    so the order fails, and because the controller retries on the next tick it
    fails again indefinitely without ever opening a position.
    """

    def _make_controller(self, base_balance="10", quote_balance="1000",
                         **config_overrides) -> LPRebalancer:
        config_kwargs = dict(
            id="test",
            connector_name="solana-mainnet-beta",
            lp_provider="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="PoolAddress123",
            autoswap=True,
            total_amount_quote=Decimal("575"),
        )
        config_kwargs.update(config_overrides)
        config = LPRebalancerConfig(**config_kwargs)

        market_data_provider = MagicMock(spec=MarketDataProvider)
        market_data_provider.time.return_value = 1000.0
        balances = {"SOL": Decimal(base_balance), "USDC": Decimal(quote_balance)}
        market_data_provider.get_balance.side_effect = \
            lambda _conn, token: balances.get(token, Decimal("0"))
        connector = MagicMock()
        connector.native_currency = "SOL"
        connector.get_native_currency_buffer.return_value = Decimal("0")
        market_data_provider.get_connector.return_value = connector

        controller = LPRebalancer(
            config=config,
            market_data_provider=market_data_provider,
            actions_queue=AsyncMock(spec=asyncio.Queue),
        )
        controller.executors_info = []
        controller._pool_price = Decimal("100")
        return controller

    # -- the outage ---------------------------------------------------------

    def test_dust_quote_deficit_produces_no_swap(self):
        """The observed failure: 574.999944 USDC against a 575 target.

        A shortfall of 0.000056 asked the router to sell 0.000001 SOL. Nothing
        can route that, so the swap failed on every tick for hours while the
        strategy held its full capital and never opened a position.
        """
        controller = self._make_controller(
            base_balance="0.388", quote_balance="574.999944",
            side=TradeType.BUY, position_offset_pct=Decimal("0.01"))
        swap = controller._check_autoswap_needed(TradeType.BUY, Decimal("100"))
        self.assertIsNone(swap)

    def test_dust_base_deficit_produces_no_swap(self):
        controller = self._make_controller(
            base_balance="5.749999", quote_balance="0",
            side=TradeType.SELL, position_offset_pct=Decimal("0.01"))
        swap = controller._check_autoswap_needed(TradeType.SELL, Decimal("100"))
        self.assertIsNone(swap)

    # -- real deficits still swap -------------------------------------------

    def test_real_quote_deficit_still_swaps(self):
        controller = self._make_controller(
            base_balance="10", quote_balance="100",
            side=TradeType.BUY, position_offset_pct=Decimal("0.01"))
        swap = controller._check_autoswap_needed(TradeType.BUY, Decimal("100"))
        self.assertIsNotNone(swap)
        self.assertEqual(swap.side, TradeType.SELL)

    def test_floor_of_zero_restores_previous_behaviour(self):
        """Opt back in to attempting any deficit, however small."""
        controller = self._make_controller(
            base_balance="0.388", quote_balance="574.999944",
            side=TradeType.BUY, position_offset_pct=Decimal("0.01"),
            min_autoswap_quote=Decimal("0"))
        swap = controller._check_autoswap_needed(TradeType.BUY, Decimal("100"))
        self.assertIsNotNone(swap)

    # -- sizing absorbs what the swap declined to fix ------------------------

    def test_sub_floor_shortfall_is_absorbed_by_sizing(self):
        """Skipping the dust swap must not just move the failure downstream."""
        controller = self._make_controller(quote_balance="574.999944")
        base, quote = controller._fit_amounts_to_balance(
            Decimal("0"), Decimal("575"), Decimal("100"))
        self.assertEqual(quote, Decimal("574.999944"))
        self.assertEqual(base, Decimal("0"))

    def test_real_shortfall_is_not_absorbed(self):
        """A genuine funding gap must still surface, not silently shrink."""
        controller = self._make_controller(quote_balance="400")
        _, quote = controller._fit_amounts_to_balance(
            Decimal("0"), Decimal("575"), Decimal("100"))
        self.assertEqual(quote, Decimal("575"))

    def test_funded_request_is_untouched(self):
        controller = self._make_controller(base_balance="10", quote_balance="1000")
        base, quote = controller._fit_amounts_to_balance(
            Decimal("2"), Decimal("300"), Decimal("100"))
        self.assertEqual((base, quote), (Decimal("2"), Decimal("300")))

    def test_unreadable_balance_leaves_amounts_alone(self):
        controller = self._make_controller()
        controller.market_data_provider.get_balance.side_effect = RuntimeError("rpc down")
        base, quote = controller._fit_amounts_to_balance(
            Decimal("2"), Decimal("300"), Decimal("100"))
        self.assertEqual((base, quote), (Decimal("2"), Decimal("300")))

    def test_default_floor_is_one_quote_unit(self):
        config = LPRebalancerConfig(
            id="test",
            connector_name="solana-mainnet-beta",
            lp_provider="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="PoolAddress123",
        )
        self.assertEqual(config.min_autoswap_quote, Decimal("1"))
