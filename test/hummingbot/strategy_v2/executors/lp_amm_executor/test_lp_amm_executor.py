import asyncio
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
        connector.resolve_trading_pair_from_pool = AsyncMock(
            return_value={"trading_pair": "SOL-USDC", "base_token": "SOL", "quote_token": "USDC"}
        )
        # A real dict, like the connector's own: order_id -> Decimal tx fee for a
        # confirmed AMM add/remove-liquidity call. Left as a MagicMock attribute (its
        # default), `.pop(order_id, Decimal("0"))` would return another MagicMock
        # instead of the given default, silently corrupting lp_position_state.tx_fee.
        connector._amm_lp_tx_fees = {}
        # Same reasoning as _amm_lp_tx_fees above: a real dict so `.pop(order_id, None)`
        # returns the given default instead of another MagicMock.
        connector._amm_lp_removed_amounts = {}
        # Same reasoning again: left as a MagicMock attribute, `.pop(order_id, False)`
        # would return another MagicMock (truthy) instead of False, making every close
        # look like a data-unavailable close.
        connector._amm_lp_data_unavailable = {}
        connector.order_failure_reason = MagicMock(return_value=None)

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
        self.assertEqual(executor.get_custom_info()["open_tx_hash"], "sig123")

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

    async def test_create_position_ambiguous_nft_holds(self):
        """Two new NFT positions appeared - cannot tell which is ours. The deposit
        already landed, so this must not resolve as FAILED (which the controller reads as
        "nothing deposited, safe to reopen") - it terminates as an involuntary POSITION_HOLD
        with a loud reconcile-by-hand log, same contract as close_retries_exhausted."""
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
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(executor._hold_reason, "open_nft_unresolved")
        self.assertTrue(executor._held_position_orders)
        self.assertEqual(executor.status, RunnableStatus.TERMINATED)

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

    async def test_close_position_forwards_slippage_pct(self):
        """Without this, the executor's configured max_slippage_pct (and its widened
        retry tolerance) has no effect on a withdrawal at all - Gateway falls back to
        its own default. See Greptile finding "Withdrawals ignore user limits"."""
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        executor.lp_position_state.base_amount = Decimal("1.0")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.EARLY_STOP
        executor._slippage_pct = Decimal("2.5")  # widened by a prior retry

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.0, quote=100.0,
            positions=[make_position_detail("nft1", 1.0, 100.0)],
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value="sig-close")

        await executor._close_position()

        _, kwargs = connector._amm_remove_liquidity.call_args
        self.assertEqual(kwargs["slippage_pct"], 2.5)

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

    async def test_create_position_refuses_pool_for_a_different_pair(self):
        """pool_address actually holds RAY-SOL, not the configured SOL-USDC pair:
        the executor must refuse to deposit rather than sending base/quote into
        the wrong tokens and booking them under the configured pair's symbols."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.resolve_trading_pair_from_pool = AsyncMock(
            return_value={"trading_pair": "RAY-SOL", "base_token": "RAY", "quote_token": "SOL"}
        )
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")

        await executor._create_position()

        connector._amm_add_liquidity.assert_not_awaited()
        self.assertFalse(executor.lp_position_state.position_opened)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.FAILED)

    async def test_create_position_uses_configured_pool_even_when_not_default(self):
        """The dex's default pool for this trading pair differs from the one
        configured: the executor must still deposit into the configured pool
        (passed explicitly to the connector) rather than failing or silently
        falling back to the dex's default."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_address = AsyncMock(return_value="some-other-pool")
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.0, quote=100.0,
            positions=[make_position_detail("nft1", 1.0, 100.0)],
        ))

        await executor._create_position()

        connector._amm_add_liquidity.assert_awaited_once()
        self.assertEqual(connector._amm_add_liquidity.await_args.kwargs["pool_address"], "pool123")
        self.assertTrue(executor.lp_position_state.position_opened)
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.ACTIVE)

    async def test_close_position_uses_configured_pool_even_when_not_default(self):
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = "nft1"
        executor._current_price = Decimal("100")
        executor.close_type = CloseType.EARLY_STOP

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_address = AsyncMock(return_value="some-other-pool")
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.0, quote=100.0,
            positions=[make_position_detail("nft1", 1.0, 100.0)],
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value="sig-close")

        await executor._close_position()

        connector._amm_remove_liquidity.assert_awaited_once()
        self.assertEqual(connector._amm_remove_liquidity.await_args.kwargs["pool_address"], "pool123")
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        self.assertFalse(executor.lp_position_state.position_opened)

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

    async def test_create_position_unresolved_add_holds_instead_of_failing(self):
        """Gateway could not prove the add transaction failed (TX_UNRESOLVED) - it may
        still land on-chain. Reporting FAILED would tell the controller nothing was
        deposited and it would be safe to reopen on top of a deposit that could still
        confirm - this must terminate as an involuntary POSITION_HOLD instead, same
        contract as open_nft_unresolved."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(return_value=None)
        connector.order_failure_reason = MagicMock(return_value="unresolved [code: TX_UNRESOLVED]")

        await executor._create_position()

        self.assertFalse(executor.lp_position_state.position_opened)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(executor._hold_reason, "open_unresolved")
        self.assertTrue(executor._held_position_orders)
        self.assertEqual(executor.status, RunnableStatus.TERMINATED)

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

    async def test_close_position_data_unavailable_skips_closeout_swap(self):
        """Gateway confirming the close but losing its response data must not be read
        as 'withdrew nothing': that would size a close-out swap for the executor's
        entire initial deposit instead of the real (unknown) shortfall. The amounts
        from the last position read should survive untouched and no swap should fire."""
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
        order_id = connector.create_market_order_id.return_value
        connector._amm_lp_data_unavailable[order_id] = True

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        self.assertTrue(executor.lp_position_state.close_data_unavailable)
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("1.0"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("100.0"))

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

    # ---- concurrent deposits into the same pool -----------------------------

    async def test_create_position_holds_pool_lock_across_the_deposit(self):
        """Two executors sharing a wallet and pool can each read the same LP
        balance before depositing, then each treat the whole post-deposit
        increase (including the other's minted tokens) as their own share -
        see Greptile finding "Executors claim each other's tokens". The fix
        serializes a deposit's snapshot -> add -> read against any other
        executor on the same (connector_name, pool_address): verify the lock
        is actually held for the whole span, not just acquired and dropped."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])

        lock = executor._get_pool_deposit_lock(executor.config.connector_name, executor.config.pool_address)
        add_liquidity_started = asyncio.Event()
        release_add_liquidity = asyncio.Event()

        async def amm_add_liquidity(**kwargs):
            add_liquidity_started.set()
            await release_add_liquidity.wait()
            return "sig123"

        connector._amm_add_liquidity = AsyncMock(side_effect=amm_add_liquidity)
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.0, quote=100.0, positions=None,
        ))

        create_task = asyncio.ensure_future(executor._create_position())
        await add_liquidity_started.wait()

        self.assertTrue(lock.locked())

        release_add_liquidity.set()
        await create_task

        self.assertFalse(lock.locked())
        self.assertTrue(executor.lp_position_state.position_opened)

    async def test_create_position_force_stopped_while_blocked_on_pool_lock_never_deposits(self):
        """RunnableBase.stop() never cancels the in-flight control_task, so a
        force_stop_with_position_hold() that lands while _create_position is parked
        on the pool-wide deposit lock must not let the deposit through once the lock
        frees - see Greptile finding "Stopped executor still deposits"."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")

        lock = executor._get_pool_deposit_lock(executor.config.connector_name, executor.config.pool_address)
        release_other_holder = asyncio.Event()

        async def hold_lock():
            async with lock:
                await release_other_holder.wait()

        holder_task = asyncio.ensure_future(hold_lock())
        while not lock.locked():
            await asyncio.sleep(0)

        create_task = asyncio.ensure_future(executor._create_position())
        # Let _create_position run up to (and queue on) the already-held lock.
        for _ in range(5):
            await asyncio.sleep(0)

        executor.force_stop_with_position_hold()
        self.assertEqual(executor.close_type, CloseType.FAILED)

        release_other_holder.set()
        await holder_task
        await create_task

        connector._amm_add_liquidity.assert_not_called()
        self.assertIsNone(executor.lp_position_state.active_open_order)

    async def test_create_position_confirms_after_force_stop_becomes_position_hold(self):
        """If the deposit was already in flight when the forced stop landed,
        force_stop_with_position_hold() recorded FAILED from the (then-empty) held
        orders before the transaction confirmed. Once it confirms, this must not be
        left as an unmanaged live position reported as FAILED."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])

        add_liquidity_started = asyncio.Event()
        release_add_liquidity = asyncio.Event()

        async def amm_add_liquidity(**kwargs):
            add_liquidity_started.set()
            await release_add_liquidity.wait()
            return "sig123"

        connector._amm_add_liquidity = AsyncMock(side_effect=amm_add_liquidity)

        create_task = asyncio.ensure_future(executor._create_position())
        await add_liquidity_started.wait()

        executor.force_stop_with_position_hold()
        self.assertEqual(executor.close_type, CloseType.FAILED)

        release_add_liquidity.set()
        await create_task

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(executor._hold_reason, "forced_stop")
        self.assertFalse(executor.lp_position_state.position_opened)
        markers = [o for o in executor._held_position_orders if o.get("lp_unclosed_position")]
        self.assertEqual(len(markers), 1)

    def test_pool_deposit_lock_is_shared_by_pool_not_by_executor(self):
        """Two different executors on the same (connector_name, pool_address) must
        contend for the same lock; a different pool gets its own."""
        executor_a = self.get_executor(self.get_default_config(id="test-amm-a"))
        executor_b = self.get_executor(self.get_default_config(id="test-amm-b"))
        executor_other_pool = self.get_executor(self.get_default_config(id="test-amm-c", pool_address="pool456"))

        self.assertIs(
            executor_a._get_pool_deposit_lock("solana-mainnet-beta", "pool123"),
            executor_b._get_pool_deposit_lock("solana-mainnet-beta", "pool123"),
        )
        self.assertIsNot(
            executor_a._get_pool_deposit_lock("solana-mainnet-beta", "pool123"),
            executor_other_pool._get_pool_deposit_lock("solana-mainnet-beta", "pool456"),
        )

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

    def test_early_stop_swapping_preserves_close_type(self):
        """A close-out swap already in flight settles on its own via
        _execute_closeout_swap/_handle_swap_failure. Overwriting close_type here
        would relabel that in-flight swap's outcome, and a normal fill would then
        complete without ever saving the settled result - see Greptile finding
        "Shutdown drops completed results"."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.close_type = CloseType.EARLY_STOP

        executor.early_stop(keep_position=True)

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.SWAPPING)
        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)
        self.assertEqual(executor._status, RunnableStatus.SHUTTING_DOWN)

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

    async def test_pool_matches_trading_pair_fails_open_on_lookup_error(self):
        executor = self.get_executor()
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.resolve_trading_pair_from_pool = AsyncMock(side_effect=Exception("rpc down"))
        self.assertTrue(await executor._pool_matches_trading_pair(connector))

    # ---- fungible-LP: scale to this executor's own share -------------------

    async def test_create_position_fungible_lp_scales_amounts_to_own_share(self):
        """The connector reports the WALLET'S WHOLE pool-wide balance for a
        fungible-LP position, which can include other liquidity sharing the same
        wallet and pool. base_amount/quote_amount must be scaled down to this
        deposit's own LP-token share, not left at the wallet-wide figure."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[
            make_position_info(price=100.0, base=10.0, quote=1000.0, positions=None, lp_token_amount=8.0),
        ])
        connector._amm_add_liquidity = AsyncMock(return_value="sig123")
        # own_lp_token_amount = 10 - 8 = 2 out of 10 total -> this deposit owns 20%
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=11.0, quote=1100.0, positions=None, lp_token_amount=10.0,
        ))

        await executor._create_position()

        self.assertEqual(executor.lp_position_state.own_lp_token_amount, Decimal("2"))
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("11.0") * Decimal("2") / Decimal("10"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("1100.0") * Decimal("2") / Decimal("10"))

    async def test_update_position_info_fungible_scales_amounts_to_own_share(self):
        """Same scaling applies on every refresh, not just at creation, so a
        close-out swap sized later from base_amount never trades a share this
        executor never deposited."""
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = None
        executor.lp_position_state.own_lp_token_amount = Decimal("1")  # owns 1 of 5 LP tokens

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=120.0, base=10.0, quote=1000.0, positions=None, lp_token_amount=5.0,
        ))

        await executor._update_position_info()

        self.assertEqual(executor.lp_position_state.base_amount, Decimal("2.0"))  # 10 * 1/5
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("200.0"))  # 1000 * 1/5

    # ---- NFT address recovery on retry --------------------------------------

    async def test_update_position_info_recovers_nft_address_on_retry(self):
        """A post-create position-info fetch that failed on every retry leaves the
        NFT address unresolved (open_data_unavailable=True). The next refresh must
        keep retrying the same before/after diff instead of treating the position
        as fungible-LP forever - a fungible read would adopt the wallet's WHOLE
        pool balance, and closing without the NFT address would remove 100% of an
        NFT-backed pool rather than just this deposit's own position."""
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = None
        executor.lp_position_state.open_data_unavailable = True
        executor._pending_nft_recovery = ({"existing-nft"}, Decimal("0"))

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=5.0, quote=500.0,
            positions=[
                make_position_detail("existing-nft", 4.0, 400.0),
                make_position_detail("new-nft", 1.0, 100.0),
            ],
        ))

        await executor._update_position_info()

        self.assertEqual(executor.lp_position_state.position_nft_address, "new-nft")
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("1.0"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("100.0"))
        self.assertFalse(executor.lp_position_state.open_data_unavailable)
        self.assertIsNone(executor._pending_nft_recovery)

    async def test_update_position_info_recovery_confirms_fungible_when_no_positions(self):
        """If the recovery retry's read comes back with no per-position breakdown at
        all, the pool is confirmed fungible-LP - stop looking for an NFT address
        instead of retrying forever."""
        executor = self.get_executor()
        executor.lp_position_state.position_opened = True
        executor.lp_position_state.position_nft_address = None
        executor.lp_position_state.open_data_unavailable = True
        executor._pending_nft_recovery = (set(), Decimal("8"))

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=10.0, quote=1000.0, positions=None, lp_token_amount=10.0,
        ))

        await executor._update_position_info()

        self.assertIsNone(executor.lp_position_state.position_nft_address)
        self.assertEqual(executor.lp_position_state.own_lp_token_amount, Decimal("2"))  # 10 - 8
        self.assertFalse(executor.lp_position_state.open_data_unavailable)
        self.assertIsNone(executor._pending_nft_recovery)
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("2.0"))  # scaled: 10 * 2/10

    # ---- forced stop while SWAPPING -----------------------------------------

    def test_collect_held_position_orders_swapping_forced_stop_records_marker(self):
        """A forced stop mid-SWAPPING finds the liquidity already withdrawn
        (position_opened=False) with the close-out swap unconfirmed - the withdrawn
        tokens must still be recorded as a held order, or the exposure falls out of
        tracking entirely (orchestrator records FAILED instead of POSITION_HOLD)."""
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.position_opened = False
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor._current_price = Decimal("100")

        held = executor._collect_held_position_orders()

        self.assertEqual(len(held), 1)
        self.assertTrue(held[0]["lp_net_trade"])
        self.assertEqual(executor._hold_reason, "forced_stop")

    # ---- swap settlement updates amounts and fee ----------------------------

    async def test_execute_closeout_swap_order_filled_updates_amounts_and_fee(self):
        """A filled close-out swap must apply its REALIZED fill to base_amount/
        quote_amount and tx_fee, so the executor's final value reflects what the
        swap actually settled at rather than the pre-swap balances re-priced at
        whatever the pool price has drifted to since."""
        from hummingbot.core.data_type.in_flight_order import OrderState

        executor = self.get_executor(self.get_default_config(swap_provider="jupiter/router"))
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.active_swap_order = TrackedOrder(order_id="swap-order-123")
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.tx_fee = Decimal("0.001")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        mock_order = MagicMock()
        mock_order.current_state = OrderState.FILLED
        mock_order.client_order_id = "swap-order-123"
        mock_order.trade_type = TradeType.SELL
        mock_order.executed_amount_base = Decimal("0.5")
        mock_order.executed_amount_quote = Decimal("49.0")
        mock_order.cumulative_fee_paid = MagicMock(return_value=Decimal("0.0002"))
        connector.get_order = MagicMock(return_value=mock_order)

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("1.0"))  # 1.5 - 0.5
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("149.0"))  # 100 + 49
        self.assertEqual(executor.lp_position_state.tx_fee, Decimal("0.0012"))  # 0.001 + 0.0002
        mock_order.cumulative_fee_paid.assert_called_once_with("SOL")

    async def test_closeout_swap_does_not_distort_fees_earned_quote(self):
        """Fees earned must be frozen at close confirmation, before any close-out
        swap trades base_amount/quote_amount - otherwise the swap's own execution
        price difference from current_price gets booked as LP fees (and, through
        filled_amount_quote, as pool volume that never happened)."""
        from hummingbot.core.data_type.in_flight_order import OrderState

        executor = self.get_executor(self.get_default_config(swap_provider="jupiter/router"))
        executor._pool_info = SimpleNamespace(fee_pct=1.0)
        executor._current_price = Decimal("25")

        # A fee-free position: deposited 1 base + 100 quote, now holds 2 base + 50
        # quote at price 25 - exactly on the no-fee curve (k=100).
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.initial_base_amount = Decimal("1")
        executor.lp_position_state.initial_quote_amount = Decimal("100")
        executor.lp_position_state.base_amount = Decimal("2")
        executor.lp_position_state.quote_amount = Decimal("50")
        # As _close_position/_handle_position_gone do before entering SWAPPING.
        executor.lp_position_state.realized_fees_earned_quote = (
            executor.lp_position_state.fees_earned_quote(Decimal("25"))
        )
        self.assertEqual(executor.lp_position_state.realized_fees_earned_quote, Decimal("0"))

        executor.lp_position_state.active_swap_order = TrackedOrder(order_id="swap-order-123")
        connector = self.strategy.connectors["solana-mainnet-beta"]
        mock_order = MagicMock()
        mock_order.current_state = OrderState.FILLED
        mock_order.client_order_id = "swap-order-123"
        mock_order.trade_type = TradeType.SELL
        mock_order.executed_amount_base = Decimal("1")
        mock_order.executed_amount_quote = Decimal("26")  # sold at 26, not the 25 mark price
        mock_order.cumulative_fee_paid = MagicMock(return_value=Decimal("0"))
        connector.get_order = MagicMock(return_value=mock_order)

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.base_amount, Decimal("1"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("76"))
        # Without the freeze, fees_earned_quote would recompute from the swapped
        # amounts against current_price (25) and report the swap's $1 price
        # difference as 1 quote of LP fees - and filled_amount_quote would turn
        # that into 100 quote of pool volume that never happened at a 1% fee rate.
        self.assertEqual(executor.lp_position_state.fees_earned_quote(Decimal("25")), Decimal("0"))
        self.assertEqual(executor.filled_amount_quote, Decimal("0"))

    async def test_handle_swap_failure_unresolved_holds_immediately(self):
        """An unresolved (ambiguous) swap result must never be retried: the first
        transaction may still land, and resubmitting could execute the swap twice.
        It goes straight to POSITION_HOLD instead of burning the normal retry
        budget, under its own hold_reason distinct from an ordinary close-out
        failure - the swap may still confirm and compete with a new deposit for
        the same funds, so the rebalancer's reopen-after-closeout-failure path
        (hold_reason == "closeout_swap_failed") must not match it. Regression for
        Greptile's 2026-11-26 19:35 PR #8580 finding."""
        executor = self.get_executor(self.get_default_config(swap_provider="jupiter/router"))
        executor.lp_position_state.state = LPAmmExecutorStates.SWAPPING
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor._current_price = Decimal("100")

        executor._handle_swap_failure(ValueError("pending [code: TX_UNRESOLVED]"))

        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(executor._hold_reason, "closeout_swap_unresolved")

    # ---- fungible-LP withdrawal reconciliation (no double-withdrawal) -------

    async def test_close_position_remove_liquidity_unresolved_reconciles_before_retry(self):
        """A remove-liquidity call that returns no signature (treated as a failure)
        may actually have landed on-chain. If the wallet's LP-token balance already
        dropped by the next attempt, that drop must be credited against
        own_lp_token_amount before re-deriving remove_percentage - otherwise the
        retry re-derives the fraction from the now-reduced balance and withdraws
        this executor's own share a second time."""
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
        # First attempt: wallet reports 8 LP tokens (this executor owns 3 of them),
        # but the remove call returns no signature - an ambiguous failure.
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=8.0, quote=800.0, positions=None, lp_token_amount=8.0,
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value=None)
        connector.order_failure_reason = MagicMock(return_value="unresolved [code: TX_UNRESOLVED]")

        await executor._close_position()

        self.assertEqual(executor._current_retries, 1)
        self.assertEqual(executor.lp_position_state.own_lp_token_amount, Decimal("3"))  # unchanged yet

        # Second attempt: the wallet balance already dropped from 8 to 5, proving the
        # first (ambiguously-failed) attempt actually removed this executor's 3 LP
        # tokens.
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=5.0, quote=500.0, positions=None, lp_token_amount=5.0,
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value="sig-close")
        executor._close_backoff_until = 0.0  # as if the backoff from attempt 1 had elapsed

        await executor._close_position()

        # own_lp_token_amount reconciled down to 0 before this attempt's percentage
        # was derived: nothing is left owed, so the remove call is skipped entirely
        # and the wallet's remaining 5 LP tokens (someone else's) are left untouched
        # instead of a naive fresh-fraction retry withdrawing 3/5 = 60% more of them.
        connector._amm_remove_liquidity.assert_not_awaited()
        self.assertEqual(executor.lp_position_state.own_lp_token_amount, Decimal("0"))
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)

    async def test_close_position_confirmed_failure_does_not_reconcile_unrelated_drop(self):
        """Unlike an unresolved failure, a confirmed (non-ambiguous) remove-liquidity
        failure proves this attempt's transaction did not land. A wallet-balance drop
        seen on the next attempt is then someone else's withdrawal from the same
        pool, not this executor's - reconciling it against own_lp_token_amount would
        zero it out and report the still-live position as gone."""
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
        # First attempt: wallet reports 8 LP tokens (this executor owns 3 of them),
        # and the remove call fails outright - a confirmed, non-ambiguous failure.
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=8.0, quote=800.0, positions=None, lp_token_amount=8.0,
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value=None)
        connector.order_failure_reason = MagicMock(return_value="slippage exceeded [code: SLIPPAGE_EXCEEDED]")

        await executor._close_position()

        self.assertEqual(executor._current_retries, 1)
        self.assertIsNone(executor._last_close_attempt_wallet_lp_tokens)
        self.assertEqual(executor.lp_position_state.own_lp_token_amount, Decimal("3"))  # unchanged

        # Second attempt: the wallet balance dropped from 8 to 5 - but another
        # executor withdrew its own 3 LP tokens in between, unrelated to the first
        # attempt's failure. own_lp_token_amount must not be reconciled against it.
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=5.0, quote=500.0, positions=None, lp_token_amount=5.0,
        ))
        connector._amm_remove_liquidity = AsyncMock(return_value="sig-close")
        executor._close_backoff_until = 0.0  # as if the backoff from attempt 1 had elapsed

        await executor._close_position()

        # own_lp_token_amount (3) still stood against the wallet's remaining 5 LP
        # tokens, so the remove call fires for this executor's real 60% share
        # instead of the position being wrongly declared gone.
        connector._amm_remove_liquidity.assert_awaited_once()
        self.assertAlmostEqual(
            connector._amm_remove_liquidity.await_args.kwargs["percentage"], 60.0, places=6
        )
        self.assertEqual(executor.lp_position_state.state, LPAmmExecutorStates.COMPLETE)

    # ---- tx_fee collected from the connector's AMM add/remove metadata ------

    async def test_create_position_collects_tx_fee_from_connector_metadata(self):
        executor = self.get_executor()
        executor.lp_position_state.state = LPAmmExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_user_positions = AsyncMock(return_value=[])

        async def fake_add_liquidity(*args, order_id, **kwargs):
            connector._amm_lp_tx_fees[order_id] = Decimal("0.0005")
            return "sig123"

        connector._amm_add_liquidity = AsyncMock(side_effect=fake_add_liquidity)
        connector.get_position_info_fresh = AsyncMock(return_value=make_position_info(
            price=100.0, base=1.0, quote=100.0,
            positions=[make_position_detail("nft1", 1.0, 100.0)],
        ))

        await executor._create_position()

        self.assertEqual(executor.lp_position_state.tx_fee, Decimal("0.0005"))
        self.assertNotIn("order-123", connector._amm_lp_tx_fees)

    async def test_close_position_collects_tx_fee_from_connector_metadata(self):
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

        async def fake_remove_liquidity(*args, order_id, **kwargs):
            connector._amm_lp_tx_fees[order_id] = Decimal("0.0003")
            return "sig-close"

        connector._amm_remove_liquidity = AsyncMock(side_effect=fake_remove_liquidity)

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.tx_fee, Decimal("0.0003"))


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
