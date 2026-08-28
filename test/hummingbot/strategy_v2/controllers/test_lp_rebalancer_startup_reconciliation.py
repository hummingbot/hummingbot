import asyncio
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from controllers.generic.lp_rebalancer.lp_rebalancer import LPRebalancer, LPRebalancerConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider


class MockPosition:
    """Stand-in for CLMMPositionInfo, with only the fields the controller reads."""

    def __init__(self, address="PoSiTiOnAddress1234567890"):
        self.address = address
        self.lower_price = 100.0
        self.upper_price = 110.0
        self.base_token_amount = 1.5
        self.quote_token_amount = 400.0
        self.base_fee_amount = 0.001
        self.quote_fee_amount = 0.25


class TestLPRebalancerStartupReconciliation(TestCase):
    """Tests for startup handling of positions that already exist on-chain.

    The controller keeps no state across restarts, so a position opened by a
    previous process is invisible to it. Without reconciliation the next tick
    opens a second position and the first is never rebalanced, fee-harvested or
    closed - its capital is orphaned on-chain.
    """

    def _make_controller(self, positions=None, positions_after_close=None,
                         **config_overrides) -> LPRebalancer:
        config_kwargs = dict(
            id="test",
            connector_name="solana-mainnet-beta",
            lp_provider="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="PoolAddress123",
        )
        config_kwargs.update(config_overrides)
        config = LPRebalancerConfig(**config_kwargs)

        market_data_provider = MagicMock(spec=MarketDataProvider)
        connector = MagicMock()
        connector.network = "mainnet-beta"
        connector.address = "WalletAddress123"
        market_data_provider.get_connector.return_value = connector

        controller = LPRebalancer(
            config=config,
            market_data_provider=market_data_provider,
            actions_queue=AsyncMock(spec=asyncio.Queue),
        )
        controller.executors_info = []

        # First call returns the pre-close view; later calls return the
        # post-close view, so a recovery attempt can be observed end to end.
        self._fetch_calls = []
        views = [positions] if positions_after_close is None else [positions, positions_after_close]

        async def fake_fetch():
            self._fetch_calls.append(1)
            index = min(len(self._fetch_calls) - 1, len(views) - 1)
            return views[index]

        controller._fetch_pool_positions = fake_fetch
        return controller

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def test_no_existing_position_allows_trading(self):
        controller = self._make_controller(positions=[])
        self._run(controller._reconcile_startup_positions())
        self.assertTrue(controller._startup_reconciled)
        self.assertFalse(controller._startup_blocks_trading())

    def test_unreadable_chain_blocks_trading(self):
        """A failed read must not be mistaken for an empty wallet."""
        controller = self._make_controller(positions=None)
        self._run(controller._reconcile_startup_positions())
        self.assertFalse(controller._startup_reconciled)
        self.assertTrue(controller._startup_blocks_trading())

    def test_recover_closes_existing_position_then_allows_trading(self):
        controller = self._make_controller(
            positions=[MockPosition()], positions_after_close=[])
        gateway = MagicMock()
        gateway.clmm_close_position = AsyncMock(return_value={"signature": "SIG"})
        with patch(
            "controllers.generic.lp_rebalancer.lp_rebalancer.GatewayHttpClient.get_instance",
            return_value=gateway,
        ):
            self._run(controller._reconcile_startup_positions())

        gateway.clmm_close_position.assert_awaited_once()
        kwargs = gateway.clmm_close_position.await_args.kwargs
        self.assertEqual(kwargs["position_address"], MockPosition().address)
        self.assertEqual(kwargs["dex"], "meteora")
        self.assertTrue(controller._startup_reconciled)
        self.assertFalse(controller._startup_blocks_trading())
        self.assertTrue(controller._pending_balance_update)

    def test_recover_keeps_blocking_while_position_remains(self):
        """Closing is verified against the chain, not assumed from the response."""
        controller = self._make_controller(
            positions=[MockPosition()], positions_after_close=[MockPosition()])
        gateway = MagicMock()
        gateway.clmm_close_position = AsyncMock(return_value={"signature": "SIG"})
        with patch(
            "controllers.generic.lp_rebalancer.lp_rebalancer.GatewayHttpClient.get_instance",
            return_value=gateway,
        ):
            self._run(controller._reconcile_startup_positions())

        self.assertFalse(controller._startup_reconciled)
        self.assertTrue(controller._startup_blocks_trading())
        self.assertIsNone(controller._startup_halted)

    def test_recover_halts_after_max_attempts(self):
        controller = self._make_controller(
            positions=[MockPosition()], positions_after_close=[MockPosition()],
            startup_recover_max_attempts=2)
        gateway = MagicMock()
        gateway.clmm_close_position = AsyncMock(return_value={"signature": "SIG"})
        with patch(
            "controllers.generic.lp_rebalancer.lp_rebalancer.GatewayHttpClient.get_instance",
            return_value=gateway,
        ):
            self._run(controller._reconcile_startup_positions())
            self._run(controller._reconcile_startup_positions())

        self.assertIsNotNone(controller._startup_halted)
        self.assertTrue(controller._startup_blocks_trading())

    def test_failed_close_does_not_mark_reconciled(self):
        controller = self._make_controller(
            positions=[MockPosition()], positions_after_close=[MockPosition()])
        gateway = MagicMock()
        gateway.clmm_close_position = AsyncMock(side_effect=RuntimeError("boom"))
        with patch(
            "controllers.generic.lp_rebalancer.lp_rebalancer.GatewayHttpClient.get_instance",
            return_value=gateway,
        ):
            self._run(controller._reconcile_startup_positions())

        self.assertFalse(controller._startup_reconciled)
        self.assertTrue(controller._startup_blocks_trading())

    def test_halt_policy_does_not_close_anything(self):
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="halt")
        gateway = MagicMock()
        gateway.clmm_close_position = AsyncMock()
        with patch(
            "controllers.generic.lp_rebalancer.lp_rebalancer.GatewayHttpClient.get_instance",
            return_value=gateway,
        ):
            self._run(controller._reconcile_startup_positions())

        gateway.clmm_close_position.assert_not_awaited()
        self.assertIsNotNone(controller._startup_halted)
        self.assertTrue(controller._startup_blocks_trading())

    def test_ignore_policy_preserves_previous_behaviour(self):
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="ignore")
        self._run(controller._reconcile_startup_positions())
        self.assertTrue(controller._startup_reconciled)
        self.assertFalse(controller._startup_blocks_trading())

    def test_reconciliation_runs_once(self):
        controller = self._make_controller(positions=[])
        self._run(controller._reconcile_startup_positions())
        calls_after_first = len(self._fetch_calls)
        self._run(controller._reconcile_startup_positions())
        self.assertEqual(len(self._fetch_calls), calls_after_first)

    def test_determine_executor_actions_creates_nothing_while_blocked(self):
        controller = self._make_controller(positions=[MockPosition()])
        self.assertTrue(controller._startup_blocks_trading())
        self.assertEqual(controller.determine_executor_actions(), [])

    def test_determine_executor_actions_resumes_after_reconciliation(self):
        """The gate must open again - it guards startup, not normal operation."""
        controller = self._make_controller(positions=[])
        self._run(controller._reconcile_startup_positions())
        self.assertFalse(controller._startup_blocks_trading())

        # Past the gate the usual startup path runs: with no pool price known
        # yet the controller waits rather than opening, but it is no longer
        # short-circuited by reconciliation.
        controller._pool_price = None
        self.assertEqual(controller.determine_executor_actions(), [])
        self.assertIsNotNone(controller._initial_base_balance)

    def test_invalid_policy_is_rejected(self):
        with self.assertRaises(Exception) as ctx:
            LPRebalancerConfig(
                id="test",
                connector_name="solana-mainnet-beta",
                lp_provider="meteora/clmm",
                trading_pair="SOL-USDC",
                pool_address="PoolAddress123",
                startup_position_policy="bogus",
            )
        self.assertIn("startup_position_policy", str(ctx.exception))

    def test_defaults_are_safe(self):
        """The default must not be the capital-orphaning behaviour."""
        config = LPRebalancerConfig(
            id="test",
            connector_name="solana-mainnet-beta",
            lp_provider="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="PoolAddress123",
        )
        self.assertNotEqual(config.startup_position_policy, "ignore")
        self.assertGreaterEqual(config.startup_recover_max_attempts, 1)
        self.assertIsInstance(config.swap_buffer_pct, Decimal)
