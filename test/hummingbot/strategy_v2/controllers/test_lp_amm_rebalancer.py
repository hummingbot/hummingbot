import asyncio
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

from controllers.generic.lp_amm_rebalancer.lp_amm_rebalancer import LPAmmRebalancer, LPAmmRebalancerConfig
from hummingbot.cli.strategy_configs import controller_updatable_fields
from hummingbot.core.data_type.common import MarketDict
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.executors.lp_amm_executor.data_types import LPAmmExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


def make_config(**overrides) -> LPAmmRebalancerConfig:
    defaults = dict(
        id="test",
        controller_name="lp_amm_rebalancer",
        trading_pair="SOL-USDC",
        pool_address="pool-address",
        base_amount=Decimal("1"),
        quote_amount=Decimal("100"),
    )
    defaults.update(overrides)
    return LPAmmRebalancerConfig(**defaults)


def make_executor_info(
    executor_id: str,
    status: RunnableStatus,
    close_type=None,
    custom_info: dict = None,
) -> ExecutorInfo:
    executor_config = LPAmmExecutorConfig(
        timestamp=1234,
        connector_name="solana-mainnet-beta",
        lp_provider="meteora/amm",
        trading_pair="SOL-USDC",
        pool_address="pool-address",
        base_amount=Decimal("1"),
        quote_amount=Decimal("100"),
    )
    return ExecutorInfo(
        id=executor_id,
        timestamp=1234,
        type="lp_amm_executor",
        status=status,
        config=executor_config,
        net_pnl_pct=Decimal("0"),
        net_pnl_quote=Decimal("0"),
        cum_fees_quote=Decimal("0"),
        filled_amount_quote=Decimal("0"),
        is_active=status != RunnableStatus.TERMINATED,
        is_trading=False,
        custom_info=custom_info or {},
        close_type=close_type,
    )


class TestLPAmmRebalancerConfig(TestCase):

    def test_position_refresh_interval_is_not_live_updatable(self):
        self.assertNotIn("position_refresh_interval", controller_updatable_fields(LPAmmRebalancerConfig))

    def test_update_markets_registers_connector_and_pair(self):
        config = make_config(connector_name="solana-mainnet-beta")
        markets = config.update_markets(MarketDict())
        self.assertIn("SOL-USDC", markets["solana-mainnet-beta"])


class TestLPAmmRebalancer(TestCase):

    def setUp(self):
        self.config = make_config()
        self.market_data_provider = MagicMock(spec=MarketDataProvider)
        self.market_data_provider.time.return_value = 1234.0
        self.actions_queue = AsyncMock(spec=asyncio.Queue)
        self.controller = LPAmmRebalancer(
            config=self.config,
            market_data_provider=self.market_data_provider,
            actions_queue=self.actions_queue,
        )

    def test_creates_executor_when_none_active(self):
        self.controller.executors_info = []
        actions = self.controller.determine_executor_actions()
        self.assertEqual(len(actions), 1)
        self.assertIsInstance(actions[0], CreateExecutorAction)
        self.assertEqual(actions[0].executor_config.base_amount, Decimal("1"))
        self.assertEqual(actions[0].executor_config.quote_amount, Decimal("100"))

    def test_no_action_while_executor_is_active(self):
        active = make_executor_info("exec-1", RunnableStatus.RUNNING)
        self.controller.executors_info = [active]
        actions = self.controller.determine_executor_actions()
        self.assertEqual(actions, [])
        self.assertEqual(self.controller._current_executor_id, "exec-1")

    def test_reopens_after_clean_close(self):
        terminated = make_executor_info(
            "exec-1",
            RunnableStatus.TERMINATED,
            close_type=CloseType.COMPLETED,
            custom_info={
                "base_amount": "1.1", "quote_amount": "95", "tx_fee_quote": "0.01",
                "initial_base_amount": "1", "initial_quote_amount": "100",
            },
        )
        self.controller._current_executor_id = "exec-1"
        self.controller.executors_info = [terminated]

        actions = self.controller.determine_executor_actions()

        self.assertEqual(len(actions), 1)
        self.assertIsInstance(actions[0], CreateExecutorAction)
        self.assertEqual(self.controller._position_hold_base, Decimal("0.1"))
        self.assertEqual(self.controller._position_hold_quote, Decimal("-5.01"))

    def test_does_not_reopen_when_reopen_after_close_is_false(self):
        self.controller.config.reopen_after_close = False
        terminated = make_executor_info(
            "exec-1",
            RunnableStatus.TERMINATED,
            close_type=CloseType.COMPLETED,
            custom_info={
                "base_amount": "1", "quote_amount": "100", "tx_fee_quote": "0",
                "initial_base_amount": "1", "initial_quote_amount": "100",
            },
        )
        self.controller._current_executor_id = "exec-1"
        self.controller.executors_info = [terminated]

        actions = self.controller.determine_executor_actions()

        self.assertEqual(actions, [])
        self.assertTrue(self.controller._stopped_after_close)

    def test_halts_on_orphaned_position(self):
        terminated = make_executor_info(
            "exec-1",
            RunnableStatus.TERMINATED,
            close_type=CloseType.POSITION_HOLD,
            custom_info={"hold_reason": "close_retries_exhausted", "position_nft_address": "nft-address"},
        )
        self.controller._current_executor_id = "exec-1"
        self.controller.executors_info = [terminated]

        actions = self.controller.determine_executor_actions()

        self.assertEqual(actions, [])
        self.assertEqual(self.controller._orphaned_position_address, "nft-address")

        # Halted even once the orphaned executor is no longer in executors_info.
        self.controller.executors_info = []
        self.assertEqual(self.controller.determine_executor_actions(), [])

    def test_position_hold_uses_quote_denominated_fee_not_native(self):
        """tx_fee is paid in the network's native token (e.g. SOL), not quote (e.g. USDC) -
        booking it against tx_fee's raw value would misprice the cost for any pair where the
        two differ. See Greptile finding "Fees use the wrong currency"."""
        terminated = make_executor_info(
            "exec-1",
            RunnableStatus.TERMINATED,
            close_type=CloseType.COMPLETED,
            custom_info={
                "base_amount": "1", "quote_amount": "99", "tx_fee": "0.01", "tx_fee_quote": "2.0",
                "initial_base_amount": "1", "initial_quote_amount": "100",
            },
        )
        self.controller._current_executor_id = "exec-1"
        self.controller.executors_info = [terminated]

        self.controller.determine_executor_actions()

        # quote_net = (99 - tx_fee_quote=2.0) - 100 = -3, NOT (99 - tx_fee=0.01) - 100 = -1.01
        self.assertEqual(self.controller._position_hold_quote, Decimal("-3"))

    def test_halts_on_unresolved_open_nft(self):
        """A confirmed deposit whose NFT address could not be isolated ends as POSITION_HOLD
        with hold_reason=open_nft_unresolved - funds are live on-chain but unmanaged, so this
        must halt new creation the same way close_retries_exhausted does, not be treated as a
        clean close that is safe to reopen on top of."""
        terminated = make_executor_info(
            "exec-1",
            RunnableStatus.TERMINATED,
            close_type=CloseType.POSITION_HOLD,
            custom_info={"hold_reason": "open_nft_unresolved"},
        )
        self.controller._current_executor_id = "exec-1"
        self.controller.executors_info = [terminated]

        actions = self.controller.determine_executor_actions()

        self.assertEqual(actions, [])
        self.assertEqual(self.controller._orphaned_position_address, self.config.pool_address)

        # Halted even once the orphaned executor is no longer in executors_info.
        self.controller.executors_info = []
        self.assertEqual(self.controller.determine_executor_actions(), [])

    def test_halts_on_unresolved_open_transaction(self):
        """The add transaction's outcome was unresolved (TX_UNRESOLVED) - it may still
        land on-chain. Must halt the same way open_nft_unresolved/close_retries_exhausted
        do, not be treated as a safe-to-reopen FAILED."""
        terminated = make_executor_info(
            "exec-1",
            RunnableStatus.TERMINATED,
            close_type=CloseType.POSITION_HOLD,
            custom_info={"hold_reason": "open_unresolved"},
        )
        self.controller._current_executor_id = "exec-1"
        self.controller.executors_info = [terminated]

        actions = self.controller.determine_executor_actions()

        self.assertEqual(actions, [])
        self.assertEqual(self.controller._orphaned_position_address, self.config.pool_address)

    def test_halts_on_failed_with_open_tx_hash(self):
        """A FAILED terminal that still carries an open_tx_hash means the add transaction
        was sent but its outcome is unproven - not the "nothing on-chain" FAILED case that
        is safe to reopen on top of."""
        terminated = make_executor_info(
            "exec-1",
            RunnableStatus.TERMINATED,
            close_type=CloseType.FAILED,
            custom_info={"open_tx_hash": "sig123"},
        )
        self.controller._current_executor_id = "exec-1"
        self.controller.executors_info = [terminated]

        actions = self.controller.determine_executor_actions()

        self.assertEqual(actions, [])
        self.assertEqual(self.controller._orphaned_position_address, self.config.pool_address)

    def test_failed_executor_with_nothing_on_chain_does_not_update_position_hold(self):
        terminated = make_executor_info(
            "exec-1",
            RunnableStatus.TERMINATED,
            close_type=CloseType.FAILED,
            custom_info={},
        )
        self.controller._current_executor_id = "exec-1"
        self.controller.executors_info = [terminated]

        actions = self.controller.determine_executor_actions()

        self.assertEqual(len(actions), 1)
        self.assertEqual(self.controller._position_hold_base, Decimal("0"))
        self.assertEqual(self.controller._position_hold_quote, Decimal("0"))
