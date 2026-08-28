import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from controllers.generic.lp_rebalancer.lp_rebalancer import LPRebalancer, LPRebalancerConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider

CLOSE_PATH = "controllers.generic.lp_rebalancer.lp_rebalancer.GatewayHttpClient.get_instance"


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

    def setUp(self):
        self.now = 1000.0

    def _make_controller(self, positions=None, **config_overrides) -> LPRebalancer:
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
        market_data_provider.time.side_effect = lambda: self.now
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

        # Tests drive what the chain reports by assigning to _chain_positions.
        controller._chain_positions = positions
        self.fetch_count = 0

        async def fake_fetch():
            self.fetch_count += 1
            return controller._chain_positions

        controller._fetch_pool_positions = fake_fetch
        return controller

    @staticmethod
    def _gateway(close_result=None, close_error=None):
        gateway = MagicMock()
        gateway.clmm_close_position = AsyncMock(
            return_value=close_result if close_result is not None else {"signature": "SIG"},
            side_effect=close_error,
        )
        return gateway

    def _tick(self, controller, gateway=None):
        """Run one reconciliation pass, as update_processed_data would."""
        gateway = gateway or self._gateway()
        with patch(CLOSE_PATH, return_value=gateway):
            asyncio.run(controller._reconcile_startup_positions())
        return gateway

    # -- policy-independent behaviour --------------------------------------

    def test_no_existing_position_allows_trading(self):
        controller = self._make_controller(positions=[])
        self._tick(controller)
        self.assertTrue(controller._startup_reconciled)
        self.assertFalse(controller._startup_blocks_trading())

    def test_unreadable_chain_blocks_trading(self):
        """A failed read must not be mistaken for an empty wallet."""
        controller = self._make_controller(positions=None)
        self._tick(controller)
        self.assertFalse(controller._startup_reconciled)
        self.assertTrue(controller._startup_blocks_trading())

    def test_reconciliation_runs_once(self):
        controller = self._make_controller(positions=[])
        self._tick(controller)
        settled = self.fetch_count
        self._tick(controller)
        self.assertEqual(self.fetch_count, settled)

    def test_determine_executor_actions_creates_nothing_while_blocked(self):
        controller = self._make_controller(positions=[MockPosition()])
        self.assertTrue(controller._startup_blocks_trading())
        self.assertEqual(controller.determine_executor_actions(), [])

    def test_determine_executor_actions_resumes_after_reconciliation(self):
        """The gate must open again - it guards startup, not normal operation."""
        controller = self._make_controller(positions=[])
        self._tick(controller)
        self.assertFalse(controller._startup_blocks_trading())

        controller._pool_price = None
        self.assertEqual(controller.determine_executor_actions(), [])
        self.assertIsNotNone(controller._initial_base_balance)

    # -- policies ----------------------------------------------------------

    def test_default_policy_is_halt(self):
        """Ownership cannot be verified, so the default must not close anything."""
        config = LPRebalancerConfig(
            id="test",
            connector_name="solana-mainnet-beta",
            lp_provider="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="PoolAddress123",
        )
        self.assertEqual(config.startup_position_policy, "halt")

    def test_halt_policy_does_not_close_anything(self):
        controller = self._make_controller(positions=[MockPosition()])
        gateway = self._tick(controller)
        gateway.clmm_close_position.assert_not_awaited()
        self.assertIsNotNone(controller._startup_halted)
        self.assertTrue(controller._startup_blocks_trading())

    def test_ignore_policy_preserves_previous_behaviour(self):
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="ignore")
        gateway = self._tick(controller)
        gateway.clmm_close_position.assert_not_awaited()
        self.assertTrue(controller._startup_reconciled)
        self.assertFalse(controller._startup_blocks_trading())

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

    # -- recover -----------------------------------------------------------

    def test_recover_halts_when_several_positions_exist(self):
        """Several positions mean a shared wallet: closing could take someone else's."""
        controller = self._make_controller(
            positions=[MockPosition("AAA"), MockPosition("BBB")],
            startup_position_policy="recover")
        gateway = self._tick(controller)
        gateway.clmm_close_position.assert_not_awaited()
        self.assertIsNotNone(controller._startup_halted)
        self.assertTrue(controller._startup_blocks_trading())

    def test_recover_submits_close_then_waits(self):
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="recover")
        gateway = self._tick(controller)

        gateway.clmm_close_position.assert_awaited_once()
        kwargs = gateway.clmm_close_position.await_args.kwargs
        self.assertEqual(kwargs["position_address"], MockPosition().address)
        self.assertEqual(kwargs["dex"], "meteora")
        # Submitted, not yet confirmed: trading stays blocked.
        self.assertFalse(controller._startup_reconciled)
        self.assertTrue(controller._startup_blocks_trading())

    def test_recover_completes_once_the_position_clears(self):
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="recover")
        self._tick(controller)

        controller._chain_positions = []  # close settled
        self._tick(controller)

        self.assertTrue(controller._startup_reconciled)
        self.assertFalse(controller._startup_blocks_trading())
        self.assertTrue(controller._pending_balance_update)

    def test_recover_does_not_resubmit_while_close_is_in_flight(self):
        """An unsettled close is not a failed close.

        Reconciliation runs on the controller's update_interval, one second by
        default. Re-submitting on every tick would duplicate the close and burn
        every attempt within seconds of startup.
        """
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="recover")
        gateway = self._gateway()

        self._tick(controller, gateway)
        for _ in range(5):
            self.now += 1
            self._tick(controller, gateway)

        gateway.clmm_close_position.assert_awaited_once()
        self.assertEqual(controller._startup_recover_attempts, 0)
        self.assertIsNone(controller._startup_halted)

    def test_recover_resubmits_after_the_confirm_timeout(self):
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="recover",
            startup_close_confirm_timeout=60)
        gateway = self._gateway()

        self._tick(controller, gateway)
        self.now += 61
        self._tick(controller, gateway)

        self.assertEqual(gateway.clmm_close_position.await_count, 2)
        self.assertEqual(controller._startup_recover_attempts, 1)
        self.assertIsNone(controller._startup_halted)

    def test_recover_halts_after_max_attempts(self):
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="recover",
            startup_close_confirm_timeout=60, startup_recover_max_attempts=2)
        gateway = self._gateway()

        self._tick(controller, gateway)   # first submission
        self.now += 61
        self._tick(controller, gateway)   # attempt 1, re-submits
        self.now += 61
        self._tick(controller, gateway)   # attempt 2, gives up

        self.assertIsNotNone(controller._startup_halted)
        self.assertTrue(controller._startup_blocks_trading())

    def test_failed_submission_does_not_consume_an_attempt(self):
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="recover")
        gateway = self._gateway(close_error=RuntimeError("gateway down"))

        self._tick(controller, gateway)

        self.assertEqual(controller._startup_recover_attempts, 0)
        self.assertFalse(controller._startup_reconciled)
        self.assertIsNone(controller._startup_halted)
        # The failed attempt is still recorded, so the retry is paced.
        _, submitted = controller._startup_close_attempts[MockPosition().address]
        self.assertFalse(submitted)

    def test_repeated_submission_failures_are_paced_not_ticked(self):
        """A failing submission must not burn attempts at the tick rate.

        Recording only successful submissions would leave the previous attempt
        looking timed out, so every subsequent tick - one second apart - would
        consume an attempt and halt the controller within seconds while Gateway
        was briefly unavailable.
        """
        controller = self._make_controller(
            positions=[MockPosition()], startup_position_policy="recover",
            startup_close_confirm_timeout=60, startup_recover_max_attempts=3)
        gateway = self._gateway(close_error=RuntimeError("gateway down"))

        self._tick(controller, gateway)           # first attempt, submission fails
        for _ in range(10):                       # ten ticks, one second apart
            self.now += 1
            self._tick(controller, gateway)

        self.assertEqual(gateway.clmm_close_position.await_count, 1)
        self.assertEqual(controller._startup_recover_attempts, 0)
        self.assertIsNone(controller._startup_halted)

        self.now += 61                            # past the timeout: one retry
        self._tick(controller, gateway)
        self.assertEqual(gateway.clmm_close_position.await_count, 2)
        self.assertEqual(controller._startup_recover_attempts, 1)
        self.assertIsNone(controller._startup_halted)
