from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.lp_amm_executor.data_types import LPAmmExecutorConfig, LPAmmExecutorStates
from hummingbot.strategy_v2.executors.lp_amm_executor.lp_amm_executor import LPAmmExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


def make_position_detail(address: str, base: float, quote: float) -> SimpleNamespace:
    """A stand-in for connector.gateway.AMMPositionDetail."""
    return SimpleNamespace(
        position_address=address, base_token_amount=base, quote_token_amount=quote, lp_token_amount=1.0
    )


def make_position_info(
    price: float, base: float, quote: float, positions=None, lp_token_amount: float = 0.0,
) -> SimpleNamespace:
    """A stand-in for connector.gateway.AMMPositionInfo."""
    return SimpleNamespace(
        price=price, base_token_amount=base, quote_token_amount=quote, positions=positions,
        lp_token_amount=lp_token_amount,
    )


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
        connector.get_pool_address = AsyncMock(return_value="pool123")

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

    # ---- config.side (orchestrator compatibility) --------------------------

    def test_config_side_defaults_to_range(self):
        """config.side must exist: the orchestrator's PositionHold ledger reads
        executor_info.config.side unconditionally, even in a plain log line, and
        would raise AttributeError on a POSITION_HOLD close without it."""
        executor = self.get_executor()
        self.assertEqual(executor.config.side, TradeType.RANGE)

    # ---- pool-address mismatch ------------------------------------------

    async def test_create_position_pool_mismatch_rejected(self):
        """The connector would resolve a different pool for this trading pair than
        the one configured: refuse to deposit rather than risk funds there."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_address = AsyncMock(return_value="some-other-pool")
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")

        await executor._create_position()

        connector._amm_add_liquidity.assert_not_awaited()
        self.assertFalse(executor.lp_position_state.position_opened)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.FAILED)

    async def test_close_position_pool_mismatch_rejected(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.EARLY_STOP

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_address = AsyncMock(return_value="some-other-pool")
        connector._amm_remove_liquidity = AsyncMock(return_value="sig-close")

        await executor._close_position()

        connector._amm_remove_liquidity.assert_not_awaited()
        self.assertEqual(executor._current_retries, 1)
        self.assertTrue(executor.lp_position_state.position_opened)

    # ---- swallowed connector failures (None signature) ---------------------

    async def test_create_position_add_liquidity_returns_none_is_failure(self):
        """The real connector catches a transaction error and returns None instead
        of raising; treating that as a signature would book a deposit that never
        landed."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(return_value=None)

        await executor._create_position()

        self.assertFalse(executor.lp_position_state.position_opened)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.FAILED)

    async def test_close_position_remove_liquidity_returns_none_is_failure(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.EARLY_STOP

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.0, quote=100.0,
            positions=[make_position_detail("nft1", 1.0, 100.0)],
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value=None)

        await executor._close_position()

        self.assertTrue(executor.lp_position_state.position_opened)
        self.assertEqual(executor._current_retries, 1)

    # ---- SWAPPING / close-out swap (keep_position=False) -------------------

    async def test_close_position_early_stop_transitions_to_swapping(self):
        """A non-hold close with leftover single-sided exposure routes to
        SWAPPING instead of completing with the exposure unbalanced."""
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.EARLY_STOP

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.5, quote=100.0,
            positions=[make_position_detail("nft1", 1.5, 100.0)],
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value="sig-close")

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.SWAPPING)
        self.assertFalse(executor.lp_position_state.position_opened)

    async def test_execute_closeout_swap_sell_excess_base(self):
        """More base came out than went in: places a SELL for the excess."""
        executor = self.get_executor(self.get_default_config(swap_provider="jupiter/router"))
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("1.5")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.place_order = MagicMock(return_value="swap-order-123")

        await executor._execute_closeout_swap()

        connector.place_order.assert_called_once()
        call_kwargs = connector.place_order.call_args[1]
        self.assertFalse(call_kwargs["is_buy"])  # SELL excess base
        self.assertEqual(call_kwargs["amount"], Decimal("0.5"))
        self.assertEqual(call_kwargs["dex_name"], "jupiter/router")
        self.assertIsNotNone(executor.lp_position_state.active_swap_order)

    async def test_execute_closeout_swap_buy_back_base(self):
        """Less base came out than went in: places a BUY to restore it."""
        executor = self.get_executor(self.get_default_config(swap_provider="jupiter/router"))
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("0.5")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.place_order = MagicMock(return_value="swap-order-123")

        await executor._execute_closeout_swap()

        connector.place_order.assert_called_once()
        call_kwargs = connector.place_order.call_args[1]
        self.assertTrue(call_kwargs["is_buy"])  # BUY back the shortfall
        self.assertEqual(call_kwargs["amount"], Decimal("0.5"))
        self.assertIsNotNone(executor.lp_position_state.active_swap_order)

    async def test_execute_closeout_swap_order_filled_completes(self):
        """The placed swap order filling ends the executor as COMPLETE."""
        from hummingbot.core.data_type.in_flight_order import OrderState

        executor = self.get_executor(self.get_default_config(swap_provider="jupiter/router"))
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.active_swap_order = TrackedOrder(order_id="swap-order-123")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        mock_order = MagicMock()
        mock_order.current_state = OrderState.FILLED
        mock_order.client_order_id = "swap-order-123"
        connector.get_order = MagicMock(return_value=mock_order)

        await executor._execute_closeout_swap()

        self.assertIsNone(executor.lp_position_state.active_swap_order)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)

    async def test_execute_closeout_swap_no_swap_needed_completes(self):
        executor = self.get_executor(self.get_default_config(swap_provider="jupiter/router"))
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("1.0")  # balanced already

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)

    async def test_execute_closeout_swap_failure_retries_then_holds(self):
        """Each placement failure burns one of MAX_CLOSEOUT_SWAP_ATTEMPTS; on
        exhaustion the executor terminates POSITION_HOLD with the withdrawn
        tokens instead of reporting FAILED with hidden exposure."""
        executor = self.get_executor(self.get_default_config(swap_provider="jupiter/router"))
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor._current_price = Decimal("100")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.place_order = MagicMock(side_effect=Exception("swap failed"))

        for _ in range(executor.MAX_CLOSEOUT_SWAP_ATTEMPTS - 1):
            await executor._execute_closeout_swap()
            self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.SWAPPING)

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(executor._hold_reason, "closeout_swap_failed")
        self.assertEqual(len(executor._held_position_orders), 1)

    async def test_execute_closeout_swap_no_swap_provider_holds(self):
        """No swap_provider configured and no network default available: hold
        rather than silently skip the unbalanced exposure."""
        executor = self.get_executor()  # no swap_provider configured
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor._current_price = Decimal("100")

        with patch(
            "hummingbot.strategy_v2.executors.lp_amm_executor.lp_amm_executor.GatewayHttpClient"
        ) as mock_gateway_client:
            mock_gateway_client.get_instance.return_value.get_default_swap_provider = AsyncMock(return_value=None)
            for _ in range(executor.MAX_CLOSEOUT_SWAP_ATTEMPTS):
                await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)

    async def test_keep_position_true_skips_closeout_swap_entirely(self):
        """keep_position=True never routes through SWAPPING, even with leftover
        single-sided exposure: the net change is kept and recorded as a spot
        position instead of being swapped away."""
        executor = self.get_executor(self.get_default_config(keep_position=True))
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
        connector.place_order = MagicMock(side_effect=AssertionError("must not be called"))

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        connector.place_order.assert_not_called()
        held = executor.get_custom_info()["held_position_orders"]
        self.assertEqual(len(held), 1)
        self.assertTrue(held[0]["lp_net_trade"])

    # ---- NFT address recovery retries --------------------------------------

    async def test_create_position_retries_position_info_fetch(self):
        """A transient read failure right after a confirmed deposit is retried
        in-place instead of giving up on the first attempt."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")
        connector.get_position_info_fresh = AsyncMock(side_effect=[
            Exception("rpc hiccup"),
            make_position_info(
                price=100.0, base=1.0, quote=100.0, positions=[make_position_detail("nft1", 1.0, 100.0)],
            ),
        ])

        with patch("asyncio.sleep", new=AsyncMock()):
            await executor._create_position()

        self.assertEqual(connector.get_position_info_fresh.await_count, 2)
        self.assertTrue(executor.lp_position_state.position_opened)
        self.assertEqual(executor.lp_position_state.position_nft_address, "nft1")
        self.assertFalse(executor.lp_position_state.open_data_unavailable)

    async def test_create_position_gives_up_after_three_failed_fetches(self):
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")
        connector.get_position_info_fresh = AsyncMock(side_effect=Exception("rpc down"))

        with patch("asyncio.sleep", new=AsyncMock()):
            await executor._create_position()

        self.assertEqual(connector.get_position_info_fresh.await_count, 3)
        self.assertTrue(executor.lp_position_state.position_opened)
        self.assertIsNone(executor.lp_position_state.position_nft_address)
        self.assertTrue(executor.lp_position_state.open_data_unavailable)

    # ---- fungible-LP own-share isolation ------------------------------------

    async def test_create_position_fungible_lp_tracks_own_lp_tokens(self):
        """Isolate this deposit's own LP-token share from whatever the wallet
        already held in the pool, so closing later does not withdraw both."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[
            make_position_info(price=100.0, base=2.0, quote=200.0, positions=None, lp_token_amount=5.0),
        ])
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=3.0, quote=300.0, positions=None, lp_token_amount=8.0,
        ))

        await executor._create_position()

        self.assertTrue(executor.lp_position_state.position_opened)
        self.assertEqual(executor.lp_position_state.own_lp_token_amount, Decimal("3"))

    async def test_create_position_fungible_lp_snapshot_failure_leaves_amount_unresolved(self):
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(side_effect=Exception("rpc down"))
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=3.0, quote=300.0, positions=None, lp_token_amount=8.0,
        ))

        await executor._create_position()

        self.assertTrue(executor.lp_position_state.position_opened)
        self.assertIsNone(executor.lp_position_state.own_lp_token_amount)

    async def test_close_position_fungible_lp_removes_only_own_share(self):
        """Remove only this executor's own LP-token share, not the wallet's whole
        balance, when other liquidity shares the pool."""
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = None
        executor.lp_position_state.own_lp_token_amount = Decimal("3")
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.quote_amount = Decimal("150")
        executor.lp_position_state.initial_base_amount = Decimal("1.5")
        executor.lp_position_state.initial_quote_amount = Decimal("150")
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.EARLY_STOP

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=3.0, quote=300.0, positions=None, lp_token_amount=6.0,
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value="sig-close")

        await executor._close_position()

        connector._amm_remove_liquidity.assert_awaited_once()
        _, kwargs = connector._amm_remove_liquidity.call_args
        self.assertAlmostEqual(kwargs["percentage"], 50.0)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)

    async def test_close_position_fungible_lp_no_remaining_share_marks_gone(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = None
        executor.lp_position_state.own_lp_token_amount = Decimal("3")
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.EARLY_STOP

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=0.0, quote=0.0, positions=None, lp_token_amount=0.0,
        ))
        connector._amm_remove_liquidity = AsyncMock()

        await executor._close_position()

        connector._amm_remove_liquidity.assert_not_awaited()
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        self.assertFalse(executor.lp_position_state.position_opened)

    # ---- held-order accounting: dual-sided fee gain -------------------------

    def test_store_net_trade_both_sides_grew_records_gain_not_cost(self):
        """Fees earned on both tokens at once must show as a gain, not be inverted
        into a cost by taking abs(net_quote) in a BUY record."""
        executor = self.get_executor()
        executor.lp_position_state.base_amount = Decimal("1.01")
        executor.lp_position_state.quote_amount = Decimal("101")
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100")

        executor._store_net_trade_from_withdrawal(Decimal("100"))

        held = executor._held_position_orders
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]["executed_amount_base"], 0.0)
        self.assertEqual(held[0]["executed_amount_quote"], 0.0)
        # gained = 0.01 * 100 + 1 = 2 quote; recorded as a negative fee (a credit).
        self.assertAlmostEqual(held[0]["cumulative_fee_paid_quote"], -2.0)

    # ---- forced-stop held-order collection ----------------------------------

    def test_collect_held_position_orders_forced_stop_records_marker(self):
        """The orchestrator's shutdown-deadline path reads held orders directly,
        bypassing the normal close - a still-open position must still surface as
        one, or the forced stop reports FAILED and drops the live exposure."""
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        executor._current_price = Decimal("100")

        held = executor._collect_held_position_orders()

        self.assertEqual(len(held), 1)
        self.assertTrue(held[0]["lp_unclosed_position"])
        self.assertEqual(executor._hold_reason, "forced_stop")

    def test_collect_held_position_orders_no_position_returns_empty(self):
        executor = self.get_executor()
        self.assertEqual(executor._collect_held_position_orders(), [])

    # ---- connector validation ------------------------------------------

    def test_validate_and_normalize_connector_failure_stops(self):
        executor = self.get_executor()
        executor.stop = MagicMock()
        with patch(
            "hummingbot.strategy_v2.executors.lp_amm_executor.lp_amm_executor.validate_and_normalize_connector",
            return_value=(None, False),
        ):
            result = executor._validate_and_normalize_connector("bad-connector")
        self.assertIsNone(result)
        self.assertEqual(executor.close_type, CloseType.FAILED)
        executor.stop.assert_called_once()

    def test_validate_and_normalize_connector_success(self):
        executor = self.get_executor()
        executor.stop = MagicMock()
        with patch(
            "hummingbot.strategy_v2.executors.lp_amm_executor.lp_amm_executor.validate_and_normalize_connector",
            return_value=("solana-mainnet-beta", True),
        ):
            result = executor._validate_and_normalize_connector("solana-mainnet-beta")
        self.assertEqual(result, "solana-mainnet-beta")
        executor.stop.assert_not_called()

    async def test_validate_sufficient_balance_is_noop(self):
        executor = self.get_executor()
        await executor.validate_sufficient_balance()  # no exception, no-op

    # ---- control_task dispatch ------------------------------------------

    async def test_control_task_not_active_starts_opening(self):
        executor = self.get_executor()
        executor.update_pool_info = AsyncMock()
        executor._create_position = AsyncMock()

        await executor.control_task()

        executor.update_pool_info.assert_awaited_once()
        executor._create_position.assert_awaited_once()
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.OPENING)

    async def test_control_task_opening_calls_create_position(self):
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING
        executor.update_pool_info = AsyncMock()
        executor._create_position = AsyncMock()

        await executor.control_task()

        executor._create_position.assert_awaited_once()

    async def test_control_task_closing_calls_close_position(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.active_close_order = TrackedOrder(order_id="x")
        executor._update_position_info = AsyncMock()
        executor._close_position = AsyncMock()

        await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.CLOSING)
        executor._close_position.assert_awaited_once()

    async def test_control_task_active_checks_exit_triggers(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor._update_position_info = AsyncMock()
        executor._check_exit_triggers = MagicMock()

        await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.ACTIVE)
        executor._check_exit_triggers.assert_called_once()

    async def test_control_task_failed_stops_with_failed_close_type(self):
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.FAILED
        executor.update_pool_info = AsyncMock()
        executor.stop = MagicMock()

        await executor.control_task()

        self.assertEqual(executor.close_type, CloseType.FAILED)
        executor.stop.assert_called_once()

    async def test_control_task_complete_stops(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.state = LPAmmExecutorStates.COMPLETE
        executor._update_position_info = AsyncMock()
        executor.stop = MagicMock()

        await executor.control_task()

        executor.stop.assert_called_once()

    # ---- _is_position_refresh_due ---------------------------------------

    def test_is_position_refresh_due_variants(self):
        executor = self.get_executor()
        self.assertTrue(executor._is_position_refresh_due(100.0))

        executor._last_position_refresh_timestamp = 100.0
        self.assertFalse(executor._is_position_refresh_due(100.5))  # within interval
        self.assertTrue(executor._is_position_refresh_due(101.0))  # interval elapsed
        self.assertTrue(executor._is_position_refresh_due(50.0))  # clock went backwards

    # ---- _check_exit_triggers early returns ------------------------------

    def test_check_exit_triggers_no_price_does_nothing(self):
        executor = self.get_executor(self.get_default_config(max_duration_seconds=1.0))
        executor.lp_position_state.add_timestamp = 0.0
        executor._current_price = None
        executor._check_exit_triggers(1_000_000.0)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.NOT_ACTIVE)

    # ---- _update_position_info branches ----------------------------------

    async def test_update_position_info_noop_when_not_opened(self):
        executor = self.get_executor()
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock()
        await executor._update_position_info()
        connector.get_position_info_fresh.assert_not_awaited()

    async def test_update_position_info_no_connector(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.connectors = {}
        await executor._update_position_info()  # no crash

    async def test_update_position_info_closed_error_registers_miss(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(side_effect=Exception("Position closed on-chain"))
        await executor._update_position_info()
        self.assertEqual(executor._position_not_found_count, 1)

    async def test_update_position_info_transient_error_does_not_register_miss(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(side_effect=Exception("rpc timeout"))
        await executor._update_position_info()
        self.assertEqual(executor._position_not_found_count, 0)

    async def test_update_position_info_none_registers_miss(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=None)
        await executor._update_position_info()
        self.assertEqual(executor._position_not_found_count, 1)

    async def test_update_position_info_nft_detail_missing_registers_miss(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=0.0, quote=0.0, positions=[],
        ))
        await executor._update_position_info()
        self.assertEqual(executor._position_not_found_count, 1)

    async def test_update_position_info_fungible_updates_from_pool_wide_amounts(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = None
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=120.0, base=2.0, quote=200.0, positions=None,
        ))
        await executor._update_position_info()
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("2.0"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("200.0"))
        self.assertEqual(executor._position_not_found_count, 0)

    # ---- _register_position_miss / _handle_position_gone -----------------

    def test_register_position_miss_defaults_close_type_from_keep_position(self):
        executor = self.get_executor(self.get_default_config(keep_position=True))
        executor.lp_position_state.position_opened = True
        executor._current_price = Decimal("100")
        executor._position_not_found_count = 2

        executor._register_position_miss()

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)

    def test_handle_position_gone_records_held_order_on_position_hold(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.quote_amount = Decimal("100")
        executor.lp_position_state.initial_quote_amount = Decimal("100")
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.POSITION_HOLD

        executor._handle_position_gone()

        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertFalse(executor.lp_position_state.position_opened)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)

    # ---- _handle_close_failure retry exhaustion ---------------------------

    def test_handle_close_failure_exhausted_does_not_arm_backoff(self):
        executor = self.get_executor()
        executor._max_retries = 0
        before = executor._close_backoff_until

        executor._handle_close_failure(ValueError("boom"))

        self.assertEqual(executor._current_retries, 1)
        self.assertEqual(executor._close_backoff_until, before)

    # ---- evaluate_max_retries ---------------------------------------------

    def test_evaluate_max_retries_position_open_becomes_hold(self):
        executor = self.get_executor()
        executor.stop = MagicMock()
        executor.lp_position_state.position_opened = True
        executor._current_retries = executor._max_retries + 1

        executor.evaluate_max_retries()

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertTrue(executor._max_retries_reached)
        self.assertEqual(len(executor._held_position_orders), 1)
        executor.stop.assert_called_once()

    def test_evaluate_max_retries_no_position_becomes_failed(self):
        executor = self.get_executor()
        executor.stop = MagicMock()
        executor._current_retries = executor._max_retries + 1

        executor.evaluate_max_retries()

        self.assertEqual(executor.close_type, CloseType.FAILED)
        executor.stop.assert_called_once()

    def test_evaluate_max_retries_within_budget_is_noop(self):
        executor = self.get_executor()
        executor.stop = MagicMock()
        executor.evaluate_max_retries()
        executor.stop.assert_not_called()

    # ---- early_stop branches ----------------------------------------------

    def test_early_stop_active_transitions_to_closing(self):
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.ACTIVE
        executor.early_stop(keep_position=False)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.CLOSING)
        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)

    def test_early_stop_opening_defers_close(self):
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING
        executor.early_stop(keep_position=True)
        self.assertTrue(executor._close_after_open)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)

    def test_early_stop_not_active_completes_immediately(self):
        executor = self.get_executor()
        executor.early_stop(keep_position=False)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)

    # ---- _get_native_to_quote_rate ----------------------------------------

    def test_native_to_quote_rate_is_one_when_native_is_quote(self):
        executor = self.get_executor(self.get_default_config(trading_pair="USDC-SOL"))
        rate = executor._get_native_to_quote_rate()
        self.assertEqual(rate, Decimal("1"))

    # ---- filled_amount_base / filled_amount_quote -------------------------

    def test_filled_amount_base_reports_current_base(self):
        executor = self.get_executor()
        executor.lp_position_state.base_amount = Decimal("1.23")
        self.assertEqual(executor.filled_amount_base, Decimal("1.23"))

    def test_filled_amount_quote_zero_without_pool_info(self):
        executor = self.get_executor()
        self.assertEqual(executor.filled_amount_quote, Decimal("0"))

    def test_filled_amount_quote_zero_without_fee_pct(self):
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        executor._pool_info = SimpleNamespace(fee_pct=0)
        self.assertEqual(executor.filled_amount_quote, Decimal("0"))

    def test_filled_amount_quote_derived_from_fees(self):
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        executor._pool_info = SimpleNamespace(fee_pct=1.0)
        executor.lp_position_state.initial_base_amount = Decimal("1")
        executor.lp_position_state.initial_quote_amount = Decimal("100")
        executor.lp_position_state.base_amount = Decimal("1")
        executor.lp_position_state.quote_amount = Decimal("150")  # value grew beyond the no-fee curve

        volume = executor.filled_amount_quote

        self.assertGreater(volume, Decimal("0"))

    # ---- get_net_pnl_quote / get_net_pnl_pct / get_cum_fees_quote ----------

    def test_get_net_pnl_quote_zero_without_price(self):
        executor = self.get_executor()
        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))

    def test_get_net_pnl_quote_zero_when_failed_and_closed(self):
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        executor.lp_position_state.state = LPAmmExecutorStates.FAILED
        executor.lp_position_state.position_opened = False
        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))

    def test_get_net_pnl_quote_falls_back_to_current_value_without_add_price(self):
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        executor.lp_position_state.add_price = Decimal("0")
        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))

    def test_get_net_pnl_pct_zero_without_add_price(self):
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        executor.lp_position_state.base_amount = Decimal("2")
        executor.lp_position_state.add_price = Decimal("0")
        self.assertEqual(executor.get_net_pnl_pct(), Decimal("0"))

    def test_get_net_pnl_pct_nonzero(self):
        executor = self.get_executor()
        executor._current_price = Decimal("400")
        executor.lp_position_state.initial_base_amount = Decimal("1")
        executor.lp_position_state.initial_quote_amount = Decimal("100")
        executor.lp_position_state.base_amount = Decimal("0.5")
        executor.lp_position_state.quote_amount = Decimal("200")
        executor.lp_position_state.add_price = Decimal("100")

        self.assertNotEqual(executor.get_net_pnl_pct(), Decimal("0"))

    def test_get_cum_fees_quote_uses_tx_fee(self):
        executor = self.get_executor()
        executor.lp_position_state.tx_fee = Decimal("0.01")
        self.assertEqual(executor.get_cum_fees_quote(), Decimal("0.01"))  # SOL == native, rate 1 when quote=USDC too? see below

    # ---- update_pool_info ---------------------------------------------------

    async def test_update_pool_info_no_connector(self):
        executor = self.get_executor()
        executor.connectors = {}
        await executor.update_pool_info()  # no crash

    async def test_update_pool_info_success(self):
        executor = self.get_executor()
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_info_by_address = AsyncMock(
            return_value=SimpleNamespace(price=150.0, fee_pct=0.3)
        )
        await executor.update_pool_info()
        self.assertEqual(executor._current_price, Decimal("150.0"))
        self.assertIsNotNone(executor._pool_info)

    async def test_update_pool_info_error_is_swallowed(self):
        executor = self.get_executor()
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_info_by_address = AsyncMock(side_effect=Exception("rpc down"))
        await executor.update_pool_info()  # no crash
        self.assertIsNone(executor._pool_info)

    # ---- pool-address verification fail-open on lookup error --------------

    async def test_pool_address_matches_config_fails_open_on_lookup_error(self):
        executor = self.get_executor()
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_address = AsyncMock(side_effect=Exception("rpc down"))
        self.assertTrue(await executor._pool_address_matches_config(connector))


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
