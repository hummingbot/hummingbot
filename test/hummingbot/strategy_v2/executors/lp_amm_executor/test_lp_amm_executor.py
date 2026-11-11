from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.lp_amm_executor.data_types import LPAmmExecutorConfig, LPAmmExecutorStates
from hummingbot.strategy_v2.executors.lp_amm_executor.lp_amm_executor import LPAmmExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


def make_position_detail(address: str, base: float, quote: float) -> SimpleNamespace:
    """A stand-in for connector.gateway.AMMPositionDetail."""
    return SimpleNamespace(
        position_address=address, base_token_amount=base, quote_token_amount=quote, lp_token_amount=1.0
    )


def make_position_info(price: float, base: float, quote: float, positions=None) -> SimpleNamespace:
    """A stand-in for connector.gateway.AMMPositionInfo."""
    return SimpleNamespace(price=price, base_token_amount=base, quote_token_amount=quote, positions=positions)


class TestLPAmmExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self) -> None:
        super().setUp()
        self.strategy = self.create_mock_strategy()
        self.update_interval = 0.5

    @staticmethod
    def create_mock_strategy():
        strategy = MagicMock(spec=StrategyV2Base)
        type(strategy).current_timestamp = PropertyMock(return_value=1_000_000.0)

        connector = MagicMock()
        connector.create_market_order_id.return_value = "order-123"
        connector._native_currency = "SOL"

        strategy.connectors = {"solana-mainnet-beta": connector}
        strategy.notify_hb_app_with_timestamp = MagicMock()
        return strategy

    def get_default_config(self, **overrides) -> LPAmmExecutorConfig:
        kwargs = dict(
            id="test-amm-1",
            timestamp=1234567890,
            connector_name="solana-mainnet-beta",
            lp_provider="meteora/amm",
            trading_pair="SOL-USDC",
            pool_address="pool123",
            base_amount=Decimal("1.0"),
            quote_amount=Decimal("100"),
        )
        kwargs.update(overrides)
        return LPAmmExecutorConfig(**kwargs)

    def get_executor(self, config: LPAmmExecutorConfig = None) -> LPAmmExecutor:
        if config is None:
            config = self.get_default_config()
        executor = LPAmmExecutor(self.strategy, config, self.update_interval)
        self.set_loggers(loggers=[executor.logger()])
        return executor

    def test_executor_initialization(self):
        executor = self.get_executor()
        self.assertEqual(executor.config.pool_address, "pool123")
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.NOT_ACTIVE)
        self.assertIsNone(executor._pool_info)
        self.assertEqual(executor.lp_dex_name, "meteora")
        self.assertEqual(executor.lp_trading_type, "amm")

    # ---- open ----------------------------------------------------------

    async def test_create_position_nft_backed_success(self):
        """A new NFT position appears after add_liquidity: adopt it and go ACTIVE."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.0, quote=100.0,
            positions=[make_position_detail("nft1", 1.0, 100.0)],
        ))

        await executor._create_position()

        self.assertTrue(executor.lp_position_state.position_opened)
        self.assertEqual(executor.lp_position_state.position_nft_address, "nft1")
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("1.0"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("100.0"))
        self.assertEqual(executor.lp_position_state.initial_base_amount, Decimal("1.0"))
        self.assertEqual(executor.lp_position_state.add_price, Decimal("100.0"))
        self.assertEqual(executor.lp_position_state.add_timestamp, 1_000_000.0)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.ACTIVE)

    async def test_create_position_fungible_lp_success(self):
        """No per-position breakdown: the pool address alone identifies the holding."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.0, quote=100.0, positions=None,
        ))

        await executor._create_position()

        self.assertTrue(executor.lp_position_state.position_opened)
        self.assertIsNone(executor.lp_position_state.position_nft_address)
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("1.0"))
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.ACTIVE)

    async def test_create_position_ambiguous_nft_fails(self):
        """Two new NFT positions appeared - cannot tell which is ours. The deposit
        already landed, so this is FAILED (not retried) with a loud reconcile-by-hand log,
        same limitation LPExecutor accepts for its own unresolvable case."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=2.0, quote=200.0,
            positions=[make_position_detail("nft1", 1.0, 100.0), make_position_detail("nft2", 1.0, 100.0)],
        ))

        await executor._create_position()

        self.assertFalse(executor.lp_position_state.position_opened)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.FAILED)

    async def test_create_position_slippage_widens_and_retries(self):
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(
            side_effect=Exception("Gateway rejected: [code: SLIPPAGE_EXCEEDED]")
        )

        await executor._create_position()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.OPENING)
        self.assertEqual(executor._current_retries, 1)
        self.assertGreater(executor._slippage_pct, executor.config.slippage_pct)
        self.assertFalse(executor.lp_position_state.position_opened)

    async def test_create_position_no_connector(self):
        executor = self.get_executor()
        executor.connectors = {}
        await executor._create_position()
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.FAILED)

    # ---- monitor --------------------------------------------------------

    async def test_update_position_info_nft_backed(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=110.0, base=0.95, quote=105.0,
            positions=[make_position_detail("nft1", 0.95, 105.0)],
        ))

        await executor._update_position_info()

        self.assertEqual(executor._current_price, Decimal("110.0"))
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("0.95"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("105.0"))

    # ---- close ------------------------------------------------------------

    async def test_close_position_nft_backed_success(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        executor.lp_position_state.base_amount = Decimal("1.0")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.EARLY_STOP

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.0, quote=100.0,
            positions=[make_position_detail("nft1", 1.0, 100.0)],
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value="sig-close")

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        self.assertFalse(executor.lp_position_state.position_opened)
        self.assertIsNone(executor.lp_position_state.position_nft_address)
        connector._amm_remove_liquidity.assert_awaited_once()
        _, kwargs = connector._amm_remove_liquidity.call_args
        self.assertEqual(kwargs["position_address"], "nft1")
        self.assertEqual(kwargs["percentage"], 100.0)

    async def test_close_position_keep_position_records_held_order(self):
        """Volume/POSITION_HOLD accounting: a POSITION_HOLD close records the net
        token change as a held order, tagged lp_net_trade so the orchestrator does
        not double-count it against filled_amount_quote."""
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.POSITION_HOLD

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.5, quote=100.0,
            positions=[make_position_detail("nft1", 1.5, 100.0)],
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value="sig-close")

        await executor._close_position()

        held = executor.get_custom_info()["held_position_orders"]
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]["trade_type"], "BUY")  # net_base = 1.5 - 1.0 = 0.5 > 0
        self.assertAlmostEqual(held[0]["executed_amount_base"], 0.5)
        self.assertTrue(held[0]["lp_net_trade"])

    async def test_close_position_already_closed_after_three_misses(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.EARLY_STOP

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=0.0, quote=0.0, positions=[],  # nft1 no longer listed
        ))
        connector._amm_remove_liquidity = AsyncMock()

        for _ in range(2):
            await executor._close_position()
            self.assertNotEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)

        await executor._close_position()
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        connector._amm_remove_liquidity.assert_not_awaited()

    async def test_close_position_no_connector(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.connectors = {}
        await executor._close_position()
        # No crash; stays non-terminal and the failure handler counted the attempt.
        self.assertEqual(executor._current_retries, 1)

    # ---- exit triggers (IL / fee-APR) --------------------------------------

    def test_max_duration_trigger_closes(self):
        executor = self.get_executor(self.get_default_config(max_duration_seconds=3600.0))
        executor.lp_position_state.state = LPAmmExecutorStates.ACTIVE
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.add_timestamp = 1_000_000.0 - 3700.0
        executor._current_price = Decimal("100")

        executor._check_exit_triggers(1_000_000.0)

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.CLOSING)
        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)

    def test_max_duration_trigger_does_not_fire_early(self):
        executor = self.get_executor(self.get_default_config(max_duration_seconds=3600.0))
        executor.lp_position_state.state = LPAmmExecutorStates.ACTIVE
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.add_timestamp = 1_000_000.0 - 1800.0
        executor._current_price = Decimal("100")

        executor._check_exit_triggers(1_000_000.0)

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.ACTIVE)

    def test_min_fee_apr_trigger_closes_when_no_fees_earned(self):
        executor = self.get_executor(self.get_default_config(
            min_fee_apr_pct=Decimal("5"), min_fee_apr_window_seconds=3600.0,
        ))
        executor.lp_position_state.state = LPAmmExecutorStates.ACTIVE
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.initial_base_amount = Decimal("1")
        executor.lp_position_state.initial_quote_amount = Decimal("100")
        executor.lp_position_state.base_amount = Decimal("1")
        executor.lp_position_state.quote_amount = Decimal("100")  # no fees earned at all
        executor.lp_position_state.add_price = Decimal("100")
        executor.lp_position_state.add_timestamp = 1_000_000.0 - 7200.0
        executor._current_price = Decimal("100")

        executor._check_exit_triggers(1_000_000.0)

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.CLOSING)
        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)

    def test_min_fee_apr_trigger_ignored_within_window(self):
        """An APR extrapolated from a few minutes of fees is noise, not a measurement."""
        executor = self.get_executor(self.get_default_config(
            min_fee_apr_pct=Decimal("5"), min_fee_apr_window_seconds=3600.0,
        ))
        executor.lp_position_state.state = LPAmmExecutorStates.ACTIVE
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.initial_base_amount = Decimal("1")
        executor.lp_position_state.initial_quote_amount = Decimal("100")
        executor.lp_position_state.base_amount = Decimal("1")
        executor.lp_position_state.quote_amount = Decimal("100")
        executor.lp_position_state.add_price = Decimal("100")
        executor.lp_position_state.add_timestamp = 1_000_000.0 - 1800.0  # within the window
        executor._current_price = Decimal("100")

        executor._check_exit_triggers(1_000_000.0)

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.ACTIVE)

    def test_fee_apr_above_threshold_does_not_close(self):
        executor = self.get_executor(self.get_default_config(
            min_fee_apr_pct=Decimal("0.5"), min_fee_apr_window_seconds=3600.0,
        ))
        executor.lp_position_state.state = LPAmmExecutorStates.ACTIVE
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.initial_base_amount = Decimal("1")
        executor.lp_position_state.initial_quote_amount = Decimal("100")
        # Reserves grew from fees to 1.01/101 at an unchanged price -> fees_earned=2, 1% APR/yr.
        executor.lp_position_state.base_amount = Decimal("1.01")
        executor.lp_position_state.quote_amount = Decimal("101")
        executor.lp_position_state.add_price = Decimal("100")
        executor.lp_position_state.add_timestamp = 0.0
        executor._current_price = Decimal("100")

        one_year_later = 365 * 86400.0
        executor._check_exit_triggers(one_year_later)

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.ACTIVE)

    def test_keep_position_config_drives_close_type(self):
        executor = self.get_executor(self.get_default_config(
            max_duration_seconds=3600.0, keep_position=True,
        ))
        executor.lp_position_state.state = LPAmmExecutorStates.ACTIVE
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.add_timestamp = 1_000_000.0 - 3700.0
        executor._current_price = Decimal("100")

        executor._check_exit_triggers(1_000_000.0)

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)

    # ---- custom info / pnl -------------------------------------------------

    def test_get_custom_info_reports_il_and_fee_apr(self):
        executor = self.get_executor()
        executor.lp_position_state.initial_base_amount = Decimal("1")
        executor.lp_position_state.initial_quote_amount = Decimal("100")
        executor.lp_position_state.base_amount = Decimal("0.5")
        executor.lp_position_state.quote_amount = Decimal("200")
        executor.lp_position_state.add_price = Decimal("100")
        executor.lp_position_state.add_timestamp = 1_000_000.0 - 3600.0
        executor._current_price = Decimal("400")

        info = executor.get_custom_info()

        self.assertEqual(info["impermanent_loss_quote"], 100.0)
        self.assertEqual(info["fees_earned_quote"], 0.0)
        self.assertIsNotNone(info["fee_apr_pct"])


class TestLPAmmExecutorOrchestratorRegistration(TestCase):
    """FEAT-017 acceptance: registration + the volume/POSITION_HOLD carve-out."""

    def test_registered_in_executor_config_base_type(self):
        from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
        type_args = ExecutorConfigBase.model_fields["type"].annotation.__args__
        self.assertIn("lp_amm_executor", type_args)

    def test_registered_in_executor_mapping(self):
        from hummingbot.strategy_v2.executors.executor_orchestrator import ExecutorOrchestrator
        from hummingbot.strategy_v2.executors.lp_amm_executor.lp_amm_executor import LPAmmExecutor
        self.assertIs(ExecutorOrchestrator._executor_mapping["lp_amm_executor"], LPAmmExecutor)

    def test_registered_in_any_executor_config_union(self):
        from hummingbot.strategy_v2.executors.lp_amm_executor.data_types import LPAmmExecutorConfig
        from hummingbot.strategy_v2.models.executors_info import AnyExecutorConfig
        self.assertIn(LPAmmExecutorConfig, AnyExecutorConfig.__args__)

    def test_volume_counted_for_position_hold_lp_amm_executor(self):
        """Held LP inventory does not carry the executor's accumulated swap volume for
        most executors, but lp_amm_executor gets lp_executor's carve-out: its deposit
        is capital, not a trade, so filled_amount_quote is still added even on a hold."""
        from hummingbot.strategy_v2.executors.executor_orchestrator import ExecutorOrchestrator
        from hummingbot.strategy_v2.executors.lp_amm_executor.data_types import LPAmmExecutorConfig
        from hummingbot.strategy_v2.models.executors_info import ExecutorInfo

        orchestrator = ExecutorOrchestrator.__new__(ExecutorOrchestrator)
        orchestrator.cached_performance = {}

        config = LPAmmExecutorConfig(
            id="test-amm-1", timestamp=1234567890, connector_name="solana-mainnet-beta",
            lp_provider="meteora/amm", trading_pair="SOL-USDC", pool_address="pool123",
            base_amount=Decimal("1.0"), quote_amount=Decimal("100"),
        )
        executor_info = ExecutorInfo(
            id=config.id, timestamp=config.timestamp, type="lp_amm_executor",
            status=RunnableStatus.TERMINATED, close_type=CloseType.POSITION_HOLD,
            close_timestamp=1.0, config=config, net_pnl_pct=Decimal("0"), net_pnl_quote=Decimal("0"),
            cum_fees_quote=Decimal("0"), filled_amount_quote=Decimal("42"), is_active=False,
            is_trading=False, custom_info={}, controller_id="main",
        )

        orchestrator._update_cached_performance("main", executor_info)

        self.assertEqual(orchestrator.cached_performance["main"].volume_traded, Decimal("42"))
