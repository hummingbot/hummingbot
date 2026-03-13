from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig, LPExecutorStates
from hummingbot.strategy_v2.executors.lp_executor.lp_executor import LPExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


class TestLPExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self) -> None:
        super().setUp()
        self.strategy = self.create_mock_strategy()
        self.update_interval = 0.5

    @staticmethod
    def create_mock_strategy():
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=StrategyV2Base)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="SOL-USDC")
        type(strategy).current_timestamp = PropertyMock(return_value=1234567890.0)

        connector = MagicMock()
        connector.create_market_order_id.return_value = "order-123"
        connector._lp_orders_metadata = {}

        strategy.connectors = {
            "meteora/clmm": connector,
        }
        strategy.notify_hb_app_with_timestamp = MagicMock()
        return strategy

    def get_default_config(self) -> LPExecutorConfig:
        return LPExecutorConfig(
            id="test-lp-1",
            timestamp=1234567890,
            connector_name="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="pool123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
            base_amount=Decimal("1.0"),
            quote_amount=Decimal("100"),
        )

    def get_executor(self, config: LPExecutorConfig = None) -> LPExecutor:
        if config is None:
            config = self.get_default_config()
        executor = LPExecutor(self.strategy, config, self.update_interval)
        self.set_loggers(loggers=[executor.logger()])
        return executor

    def test_executor_initialization(self):
        """Test executor initializes with correct state"""
        executor = self.get_executor()
        self.assertEqual(executor.config.connector_name, "meteora/clmm")
        self.assertEqual(executor.config.trading_pair, "SOL-USDC")
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.NOT_ACTIVE)
        self.assertIsNone(executor._pool_info)
        self.assertEqual(executor._max_retries, 10)
        self.assertEqual(executor._current_retries, 0)
        self.assertFalse(executor._max_retries_reached)

    def test_executor_custom_max_retries(self):
        """Test executor with custom max_retries"""
        config = self.get_default_config()
        executor = LPExecutor(self.strategy, config, self.update_interval, max_retries=5)
        self.assertEqual(executor._max_retries, 5)

    def test_logger(self):
        """Test logger returns properly"""
        executor = self.get_executor()
        logger = executor.logger()
        self.assertIsNotNone(logger)
        # Call again to test caching
        logger2 = executor.logger()
        self.assertEqual(logger, logger2)

    async def test_on_start(self):
        """Test on_start calls super"""
        executor = self.get_executor()
        with patch.object(executor.__class__.__bases__[0], 'on_start', new_callable=AsyncMock) as mock_super:
            await executor.on_start()
            mock_super.assert_called_once()

    def test_early_stop_with_keep_position_false(self):
        """Test early_stop transitions to CLOSING when position exists"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.IN_RANGE
        executor.lp_position_state.position_address = "pos123"

        executor.early_stop(keep_position=False)

        self.assertEqual(executor._status, RunnableStatus.SHUTTING_DOWN)
        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)

    def test_early_stop_with_keep_position_true(self):
        """Test early_stop with keep_position=True doesn't close position"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.IN_RANGE

        executor.early_stop(keep_position=True)

        self.assertEqual(executor._status, RunnableStatus.SHUTTING_DOWN)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        # State should not change to CLOSING
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.IN_RANGE)

    def test_early_stop_with_config_keep_position(self):
        """Test early_stop respects config.keep_position"""
        config = self.get_default_config()
        config.keep_position = True
        executor = self.get_executor(config)
        executor.lp_position_state.state = LPExecutorStates.IN_RANGE

        executor.early_stop()

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)

    def test_early_stop_from_out_of_range(self):
        """Test early_stop from OUT_OF_RANGE state"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OUT_OF_RANGE
        executor.lp_position_state.position_address = "pos123"

        executor.early_stop()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)

    def test_early_stop_from_not_active(self):
        """Test early_stop from NOT_ACTIVE goes to COMPLETE"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.NOT_ACTIVE

        executor.early_stop()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    def test_filled_amount_quote_no_pool_info(self):
        """Test filled_amount_quote returns 0 when no pool info"""
        executor = self.get_executor()
        self.assertEqual(executor.filled_amount_quote, Decimal("0"))

    def test_filled_amount_quote_with_pool_info(self):
        """Test filled_amount_quote calculates correctly"""
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        # Set initial amounts (actual deposited amounts) - these are used for filled_amount_quote
        executor.lp_position_state.add_mid_price = Decimal("100")
        executor.lp_position_state.initial_base_amount = Decimal("2.0")
        executor.lp_position_state.initial_quote_amount = Decimal("50")
        # Current state - not used for filled_amount_quote
        executor.lp_position_state.base_amount = Decimal("2.0")
        executor.lp_position_state.quote_amount = Decimal("50")
        executor.lp_position_state.base_fee = Decimal("0.01")
        executor.lp_position_state.quote_fee = Decimal("1.0")

        # filled_amount_quote = initial_base * add_price + initial_quote = 2.0 * 100 + 50 = 250
        self.assertEqual(executor.filled_amount_quote, Decimal("250"))

    def test_get_net_pnl_quote_no_pool_info(self):
        """Test get_net_pnl_quote returns 0 when no pool info"""
        executor = self.get_executor()
        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))

    def test_get_net_pnl_quote_with_values(self):
        """Test get_net_pnl_quote calculates correctly"""
        executor = self.get_executor()
        executor._current_price = Decimal("100")

        # Config: base=1.0, quote=100 -> initial = 1.0*100 + 100 = 200
        # Current: base=1.1, quote=90, base_fee=0.01, quote_fee=1
        executor.lp_position_state.base_amount = Decimal("1.1")
        executor.lp_position_state.quote_amount = Decimal("90")
        executor.lp_position_state.base_fee = Decimal("0.01")
        executor.lp_position_state.quote_fee = Decimal("1.0")

        # Current = 1.1*100 + 90 = 200
        # Fees = 0.01*100 + 1 = 2
        # PnL = 200 + 2 - 200 = 2
        self.assertEqual(executor.get_net_pnl_quote(), Decimal("2"))

    def test_get_net_pnl_quote_subtracts_tx_fee(self):
        """Test get_net_pnl_quote subtracts tx_fee from P&L"""
        executor = self.get_executor()
        executor._current_price = Decimal("100")

        # Config: base=1.0, quote=100 -> initial = 1.0*100 + 100 = 200
        # Current: base=1.1, quote=90, base_fee=0.01, quote_fee=1
        executor.lp_position_state.base_amount = Decimal("1.1")
        executor.lp_position_state.quote_amount = Decimal("90")
        executor.lp_position_state.base_fee = Decimal("0.01")
        executor.lp_position_state.quote_fee = Decimal("1.0")
        executor.lp_position_state.tx_fee = Decimal("0.5")  # 0.5 SOL tx fee

        # Current = 1.1*100 + 90 = 200
        # Fees = 0.01*100 + 1 = 2
        # PnL before tx_fee = 200 + 2 - 200 = 2
        # tx_fee (converted at rate 1) = 0.5
        # Net PnL = 2 - 0.5 = 1.5
        self.assertEqual(executor.get_net_pnl_quote(), Decimal("1.5"))

    def test_get_net_pnl_pct_zero_pnl(self):
        """Test get_net_pnl_pct returns 0 when pnl is 0"""
        executor = self.get_executor()
        self.assertEqual(executor.get_net_pnl_pct(), Decimal("0"))

    def test_get_net_pnl_pct_with_values(self):
        """Test get_net_pnl_pct calculates correctly"""
        executor = self.get_executor()
        executor._current_price = Decimal("100")

        executor.lp_position_state.base_amount = Decimal("1.1")
        executor.lp_position_state.quote_amount = Decimal("90")
        executor.lp_position_state.base_fee = Decimal("0.01")
        executor.lp_position_state.quote_fee = Decimal("1.0")

        # Initial = 200, PnL = 2
        # Pct = (2 / 200) * 100 = 1%
        self.assertEqual(executor.get_net_pnl_pct(), Decimal("1"))

    def test_get_cum_fees_quote(self):
        """Test get_cum_fees_quote returns tx_fee converted to global token"""
        executor = self.get_executor()
        # No tx_fee set, should return 0
        self.assertEqual(executor.get_cum_fees_quote(), Decimal("0"))

        # Set tx_fee (in native currency SOL)
        executor.lp_position_state.tx_fee = Decimal("0.001")
        # Without rate oracle, native_to_global_rate returns 1
        self.assertEqual(executor.get_cum_fees_quote(), Decimal("0.001"))

    async def test_validate_sufficient_balance(self):
        """Test validate_sufficient_balance passes (handled by connector)"""
        executor = self.get_executor()
        # Should not raise
        await executor.validate_sufficient_balance()

    def test_get_custom_info_no_pool_info(self):
        """Test get_custom_info without pool info"""
        executor = self.get_executor()
        info = executor.get_custom_info()

        self.assertEqual(info["side"], 0)
        self.assertEqual(info["state"], "NOT_ACTIVE")
        self.assertIsNone(info["position_address"])
        self.assertIsNone(info["current_price"])
        self.assertEqual(info["lower_price"], 0.0)
        self.assertEqual(info["upper_price"], 0.0)
        self.assertFalse(info["max_retries_reached"])

    def test_get_custom_info_with_position(self):
        """Test get_custom_info with position"""
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        executor.lp_position_state.state = LPExecutorStates.IN_RANGE
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state.lower_price = Decimal("95")
        executor.lp_position_state.upper_price = Decimal("105")
        executor.lp_position_state.base_amount = Decimal("1.0")
        executor.lp_position_state.quote_amount = Decimal("100")
        executor.lp_position_state.base_fee = Decimal("0.01")
        executor.lp_position_state.quote_fee = Decimal("1.0")
        executor.lp_position_state.position_rent = Decimal("0.002")
        executor.lp_position_state.tx_fee = Decimal("0.0001")

        info = executor.get_custom_info()

        self.assertEqual(info["side"], 0)
        self.assertEqual(info["state"], "IN_RANGE")
        self.assertEqual(info["position_address"], "pos123")
        self.assertEqual(info["current_price"], 100.0)
        self.assertEqual(info["lower_price"], 95.0)
        self.assertEqual(info["upper_price"], 105.0)
        self.assertEqual(info["base_amount"], 1.0)
        self.assertEqual(info["quote_amount"], 100.0)
        self.assertEqual(info["position_rent"], 0.002)
        self.assertEqual(info["tx_fee"], 0.0001)

    async def test_update_pool_info_success(self):
        """Test update_pool_info fetches pool info"""
        executor = self.get_executor()
        mock_pool_info = MagicMock()
        mock_pool_info.address = "pool123"
        mock_pool_info.price = 100.0

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        await executor.update_pool_info()

        self.assertEqual(executor._pool_info, mock_pool_info)
        connector.get_pool_info_by_address.assert_called_once_with("pool123")

    async def test_update_pool_info_error(self):
        """Test update_pool_info handles errors gracefully"""
        executor = self.get_executor()
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_pool_info_by_address = AsyncMock(side_effect=Exception("Network error"))

        await executor.update_pool_info()

        self.assertIsNone(executor._pool_info)

    async def test_update_pool_info_no_connector(self):
        """Test update_pool_info with missing connector"""
        executor = self.get_executor()
        executor.connectors = {}  # Clear executor's connectors

        await executor.update_pool_info()

        self.assertIsNone(executor._pool_info)

    async def test_handle_create_failure_increment_retries(self):
        """Test _handle_create_failure increments retry counter"""
        executor = self.get_executor()
        executor._current_retries = 0

        await executor._handle_create_failure(Exception("Test error"))

        self.assertEqual(executor._current_retries, 1)
        self.assertFalse(executor._max_retries_reached)

    async def test_handle_create_failure_max_retries(self):
        """Test _handle_create_failure sets max_retries_reached"""
        executor = self.get_executor()
        executor._current_retries = 9  # Will become 10

        await executor._handle_create_failure(Exception("Test error"))

        self.assertEqual(executor._current_retries, 10)
        self.assertTrue(executor._max_retries_reached)

    async def test_handle_create_failure_timeout_message(self):
        """Test _handle_create_failure logs timeout appropriately"""
        executor = self.get_executor()
        await executor._handle_create_failure(Exception("TRANSACTION_TIMEOUT: tx not confirmed"))
        self.assertEqual(executor._current_retries, 1)

    def test_handle_close_failure_increment_retries(self):
        """Test _handle_close_failure increments retry counter"""
        executor = self.get_executor()
        executor._current_retries = 0

        executor._handle_close_failure(Exception("Test error"))

        self.assertEqual(executor._current_retries, 1)
        self.assertFalse(executor._max_retries_reached)

    def test_handle_close_failure_max_retries(self):
        """Test _handle_close_failure sets max_retries_reached"""
        executor = self.get_executor()
        executor._current_retries = 9
        executor.lp_position_state.position_address = "pos123"

        executor._handle_close_failure(Exception("Test error"))

        self.assertTrue(executor._max_retries_reached)

    async def test_control_task_not_active_starts_opening(self):
        """Test control_task transitions from NOT_ACTIVE to OPENING"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)
        connector._clmm_add_liquidity = AsyncMock(side_effect=Exception("Test - prevent actual creation"))

        with patch.object(executor, '_create_position', new_callable=AsyncMock):
            await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.OPENING)

    async def test_control_task_complete_stops_executor(self):
        """Test control_task stops executor when COMPLETE"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.COMPLETE

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        with patch.object(executor, 'stop') as mock_stop:
            await executor.control_task()
            mock_stop.assert_called_once()

    async def test_control_task_out_of_range_auto_close(self):
        """Test control_task auto-closes when out of range too long (above range)"""
        config = self.get_default_config()
        config.auto_close_above_range_seconds = 60  # Auto-close when price above upper_price
        executor = self.get_executor(config)
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.OUT_OF_RANGE
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state._out_of_range_since = 1234567800.0  # 90 seconds ago

        # Mock position info with price above upper_price (105)
        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 110.0  # Out of range (above upper_price)

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)
        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)

    async def test_update_position_info_success(self):
        """Test _update_position_info updates state from position data"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        mock_position = MagicMock()
        mock_position.base_token_amount = 1.5
        mock_position.quote_token_amount = 150.0
        mock_position.base_fee_amount = 0.02
        mock_position.quote_fee_amount = 2.0
        mock_position.lower_price = 94.0
        mock_position.upper_price = 106.0

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor._update_position_info()

        self.assertEqual(executor.lp_position_state.base_amount, Decimal("1.5"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("150.0"))
        self.assertEqual(executor.lp_position_state.base_fee, Decimal("0.02"))
        self.assertEqual(executor.lp_position_state.quote_fee, Decimal("2.0"))

    async def test_update_position_info_position_closed(self):
        """Test _update_position_info handles closed position"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Position closed: pos123"))
        connector.create_market_order_id = MagicMock(return_value="order-123")
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._update_position_info()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_update_position_info_no_position_address(self):
        """Test _update_position_info returns early when no position"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = None

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock()

        await executor._update_position_info()

        connector.get_position_info.assert_not_called()

    async def test_update_position_info_no_connector(self):
        """Test _update_position_info returns early when connector missing"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"
        executor.connectors = {}  # Clear executor's connectors, not strategy's

        await executor._update_position_info()
        # Should return without error

    async def test_update_position_info_returns_none(self):
        """Test _update_position_info handles None response"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=None)

        await executor._update_position_info()
        # Should log warning but not crash

    async def test_update_position_info_not_found_error(self):
        """Test _update_position_info handles not found error"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Position not found: pos123"))

        await executor._update_position_info()
        # Should log error but not crash, state unchanged

    async def test_update_position_info_other_error(self):
        """Test _update_position_info handles other errors"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Network timeout"))

        await executor._update_position_info()
        # Should log warning but not crash

    async def test_update_position_info_updates_price(self):
        """Test _update_position_info stores current price from position info"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        mock_position = MagicMock()
        mock_position.base_token_amount = 1.5
        mock_position.quote_token_amount = 150.0
        mock_position.base_fee_amount = 0.02
        mock_position.quote_fee_amount = 2.0
        mock_position.lower_price = 94.0
        mock_position.upper_price = 106.0
        mock_position.price = 99.5

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor._update_position_info()

        self.assertEqual(executor._current_price, Decimal("99.5"))

    async def test_control_task_opening_state_retries(self):
        """Test control_task calls _create_position when OPENING"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.OPENING
        executor._max_retries_reached = False

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        with patch.object(executor, '_create_position', new_callable=AsyncMock) as mock_create:
            await executor.control_task()
            mock_create.assert_called_once()

    async def test_control_task_opening_state_max_retries_reached(self):
        """Test control_task skips _create_position when max retries reached"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.OPENING
        executor._max_retries_reached = True

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        with patch.object(executor, '_create_position', new_callable=AsyncMock) as mock_create:
            await executor.control_task()
            mock_create.assert_not_called()

    async def test_control_task_closing_state_retries(self):
        """Test control_task calls _close_position when CLOSING"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.CLOSING
        executor.lp_position_state.position_address = "pos123"
        executor._max_retries_reached = False

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        with patch.object(executor, '_close_position', new_callable=AsyncMock) as mock_close:
            await executor.control_task()
            mock_close.assert_called_once()

    async def test_control_task_closing_state_max_retries_reached(self):
        """Test control_task skips _close_position when max retries reached"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.CLOSING
        executor.lp_position_state.position_address = "pos123"
        executor._max_retries_reached = True

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        with patch.object(executor, '_close_position', new_callable=AsyncMock) as mock_close:
            await executor.control_task()
            mock_close.assert_not_called()

    async def test_control_task_in_range_state(self):
        """Test control_task does nothing when IN_RANGE"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.IN_RANGE
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state.lower_price = Decimal("95")
        executor.lp_position_state.upper_price = Decimal("105")

        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.IN_RANGE)

    async def test_create_position_no_connector(self):
        """Test _create_position returns early when connector missing"""
        executor = self.get_executor()
        executor.connectors = {}  # Clear executor's connectors

        await executor._create_position()
        # Should log error and return

    async def test_create_position_success(self):
        """Test _create_position creates position successfully"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING

        connector = self.strategy.connectors["meteora/clmm"]
        connector._clmm_add_liquidity = AsyncMock(return_value="sig123")
        connector._lp_orders_metadata = {
            "order-123": {"position_address": "pos456", "position_rent": Decimal("0.002"), "tx_fee": Decimal("0.0001")}
        }

        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 100.0
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._trigger_add_liquidity_event = MagicMock()

        await executor._create_position()

        self.assertEqual(executor.lp_position_state.position_address, "pos456")
        self.assertEqual(executor.lp_position_state.position_rent, Decimal("0.002"))
        self.assertEqual(executor.lp_position_state.tx_fee, Decimal("0.0001"))
        self.assertIsNone(executor.lp_position_state.active_open_order)
        self.assertEqual(executor._current_retries, 0)
        connector._trigger_add_liquidity_event.assert_called_once()

    async def test_create_position_no_position_address(self):
        """Test _create_position handles missing position address"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING

        connector = self.strategy.connectors["meteora/clmm"]
        connector._clmm_add_liquidity = AsyncMock(return_value="sig123")
        connector._lp_orders_metadata = {"order-123": {}}  # No position_address

        await executor._create_position()

        self.assertEqual(executor._current_retries, 1)
        self.assertIsNone(executor.lp_position_state.position_address)

    async def test_create_position_exception(self):
        """Test _create_position handles exception"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING

        connector = self.strategy.connectors["meteora/clmm"]
        connector._clmm_add_liquidity = AsyncMock(side_effect=Exception("Gateway error"))
        connector._lp_orders_metadata = {}

        await executor._create_position()

        self.assertEqual(executor._current_retries, 1)

    async def test_create_position_with_signature_in_metadata(self):
        """Test _create_position handles exception with signature in metadata"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING

        connector = self.strategy.connectors["meteora/clmm"]
        connector._clmm_add_liquidity = AsyncMock(side_effect=Exception("TRANSACTION_TIMEOUT"))
        connector._lp_orders_metadata = {"order-123": {"signature": "sig999"}}

        await executor._create_position()

        self.assertEqual(executor._current_retries, 1)

    async def test_create_position_fetches_position_info(self):
        """Test _create_position fetches position info and stores initial amounts"""
        executor = self.get_executor()

        connector = self.strategy.connectors["meteora/clmm"]
        connector._clmm_add_liquidity = AsyncMock(return_value="sig123")
        connector._lp_orders_metadata = {
            "order-123": {"position_address": "pos456", "position_rent": Decimal("0.002"), "tx_fee": Decimal("0.0001")}
        }

        mock_position = MagicMock()
        mock_position.base_token_amount = 0.95
        mock_position.quote_token_amount = 105.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 94.5
        mock_position.upper_price = 105.5
        mock_position.price = 100.0
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._trigger_add_liquidity_event = MagicMock()

        await executor._create_position()

        self.assertEqual(executor.lp_position_state.base_amount, Decimal("0.95"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("105.0"))
        self.assertEqual(executor.lp_position_state.initial_base_amount, Decimal("0.95"))
        self.assertEqual(executor.lp_position_state.initial_quote_amount, Decimal("105.0"))
        self.assertEqual(executor.lp_position_state.add_mid_price, Decimal("100.0"))

    async def test_create_position_position_info_returns_none(self):
        """Test _create_position handles None position info response"""
        executor = self.get_executor()

        connector = self.strategy.connectors["meteora/clmm"]
        connector._clmm_add_liquidity = AsyncMock(return_value="sig123")
        connector._lp_orders_metadata = {
            "order-123": {"position_address": "pos456", "position_rent": Decimal("0.002")}
        }
        connector.get_position_info = AsyncMock(return_value=None)
        connector._trigger_add_liquidity_event = MagicMock()

        await executor._create_position()

        # Should still complete, use mid_price as fallback
        self.assertEqual(executor.lp_position_state.position_address, "pos456")

    async def test_close_position_no_connector(self):
        """Test _close_position returns early when connector missing"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"
        executor.connectors = {}  # Clear executor's connectors

        await executor._close_position()
        # Should log error and return

    async def test_close_position_already_closed_none(self):
        """Test _close_position handles already-closed position (None response)"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=None)
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)
        connector._trigger_remove_liquidity_event.assert_called_once()

    async def test_close_position_already_closed_exception(self):
        """Test _close_position handles position closed exception"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Position closed: pos123"))
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_close_position_not_found_exception(self):
        """Test _close_position handles position not found exception"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Position not found: pos123"))
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_close_position_other_exception_proceeds(self):
        """Test _close_position proceeds with close on other exceptions"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["meteora/clmm"]
        # First call raises error, but it's not "closed" or "not found"
        connector.get_position_info = AsyncMock(side_effect=Exception("Network timeout"))
        connector._clmm_close_position = AsyncMock(return_value="sig789")
        connector._lp_orders_metadata = {
            "order-123": {
                "base_amount": Decimal("1.0"),
                "quote_amount": Decimal("100.0"),
                "base_fee": Decimal("0.01"),
                "quote_fee": Decimal("1.0"),
                "position_rent_refunded": Decimal("0.002"),
                "tx_fee": Decimal("0.0001")
            }
        }
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_close_position_success(self):
        """Test _close_position closes position successfully"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state.lower_price = Decimal("95")
        executor.lp_position_state.upper_price = Decimal("105")

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._clmm_close_position = AsyncMock(return_value="sig789")
        connector._lp_orders_metadata = {
            "order-123": {
                "base_amount": Decimal("1.0"),
                "quote_amount": Decimal("100.0"),
                "base_fee": Decimal("0.01"),
                "quote_fee": Decimal("1.0"),
                "position_rent_refunded": Decimal("0.002"),
                "tx_fee": Decimal("0.0001")
            }
        }
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)
        self.assertIsNone(executor.lp_position_state.position_address)
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("1.0"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("100.0"))
        self.assertEqual(executor.lp_position_state.position_rent_refunded, Decimal("0.002"))
        self.assertEqual(executor.lp_position_state.tx_fee, Decimal("0.0001"))  # Close tx_fee added
        connector._trigger_remove_liquidity_event.assert_called_once()

    async def test_close_position_exception(self):
        """Test _close_position handles exception during close"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._clmm_close_position = AsyncMock(side_effect=Exception("Gateway error"))
        connector._lp_orders_metadata = {}

        await executor._close_position()

        self.assertEqual(executor._current_retries, 1)

    async def test_close_position_exception_with_signature(self):
        """Test _close_position handles exception with signature in metadata"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._clmm_close_position = AsyncMock(side_effect=Exception("TRANSACTION_TIMEOUT"))
        connector._lp_orders_metadata = {"order-123": {"signature": "sig999"}}

        await executor._close_position()

        self.assertEqual(executor._current_retries, 1)

    def test_handle_close_failure_timeout_message(self):
        """Test _handle_close_failure logs timeout appropriately"""
        executor = self.get_executor()
        executor._handle_close_failure(Exception("TRANSACTION_TIMEOUT: tx not confirmed"))
        self.assertEqual(executor._current_retries, 1)

    def test_handle_close_failure_with_signature(self):
        """Test _handle_close_failure includes signature in message"""
        executor = self.get_executor()
        executor._current_retries = 9
        executor.lp_position_state.position_address = "pos123"

        executor._handle_close_failure(Exception("Error"), signature="sig123")

        self.assertTrue(executor._max_retries_reached)

    async def test_handle_create_failure_with_signature(self):
        """Test _handle_create_failure includes signature in message"""
        executor = self.get_executor()
        executor._current_retries = 9

        await executor._handle_create_failure(Exception("Error"), signature="sig123")

        self.assertTrue(executor._max_retries_reached)

    def test_emit_already_closed_event(self):
        """Test _emit_already_closed_event emits synthetic event"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state.base_amount = Decimal("1.0")
        executor.lp_position_state.quote_amount = Decimal("100.0")
        executor.lp_position_state.base_fee = Decimal("0.01")
        executor.lp_position_state.quote_fee = Decimal("1.0")
        executor.lp_position_state.position_rent = Decimal("0.002")

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0
        executor._pool_info = mock_pool_info

        connector = self.strategy.connectors["meteora/clmm"]
        connector._trigger_remove_liquidity_event = MagicMock()

        executor._emit_already_closed_event()

        connector._trigger_remove_liquidity_event.assert_called_once()

    def test_emit_already_closed_event_no_connector(self):
        """Test _emit_already_closed_event handles missing connector"""
        executor = self.get_executor()
        executor.connectors = {}  # Clear executor's connectors

        executor._emit_already_closed_event()
        # Should return without error

    def test_emit_already_closed_event_no_pool_info(self):
        """Test _emit_already_closed_event handles missing pool info"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"
        executor._pool_info = None

        connector = self.strategy.connectors["meteora/clmm"]
        connector._trigger_remove_liquidity_event = MagicMock()

        executor._emit_already_closed_event()

        # Should use Decimal("0") as price
        connector._trigger_remove_liquidity_event.assert_called_once()

    def test_get_net_pnl_pct_zero_initial_value(self):
        """Test get_net_pnl_pct handles zero initial value"""
        config = LPExecutorConfig(
            id="test-lp-1",
            timestamp=1234567890,
            connector_name="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="pool123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
            base_amount=Decimal("0"),
            quote_amount=Decimal("0"),
        )
        executor = self.get_executor(config)
        executor._current_price = Decimal("100")
        executor.lp_position_state.base_amount = Decimal("1.0")
        executor.lp_position_state.quote_amount = Decimal("100.0")

        # Initial value is 0, should return 0 to avoid division by zero
        self.assertEqual(executor.get_net_pnl_pct(), Decimal("0"))

    def test_get_net_pnl_quote_uses_stored_add_price(self):
        """Test get_net_pnl_quote uses stored add_mid_price"""
        executor = self.get_executor()
        executor._current_price = Decimal("110")  # Price moved up
        executor.lp_position_state.add_mid_price = Decimal("100")  # Original price
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor.lp_position_state.base_amount = Decimal("0.9")  # Less base
        executor.lp_position_state.quote_amount = Decimal("120.0")  # More quote
        executor.lp_position_state.base_fee = Decimal("0.01")
        executor.lp_position_state.quote_fee = Decimal("1.0")

        # Initial = 1.0 * 100 + 100 = 200
        # Current = 0.9 * 110 + 120 = 219
        # Fees = 0.01 * 110 + 1.0 = 2.1
        # PnL = 219 + 2.1 - 200 = 21.1
        pnl = executor.get_net_pnl_quote()
        self.assertEqual(pnl, Decimal("21.1"))

    def test_get_net_pnl_pct_uses_stored_values(self):
        """Test get_net_pnl_pct uses stored initial amounts and add_mid_price"""
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        executor.lp_position_state.add_mid_price = Decimal("100")
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor.lp_position_state.base_amount = Decimal("1.1")
        executor.lp_position_state.quote_amount = Decimal("90.0")
        executor.lp_position_state.base_fee = Decimal("0.01")
        executor.lp_position_state.quote_fee = Decimal("1.0")

        # Initial = 200, Current = 200, Fees = 2, PnL = 2
        # Pct = 2/200 * 100 = 1%
        pct = executor.get_net_pnl_pct()
        self.assertEqual(pct, Decimal("1"))

    def test_get_net_pnl_pct_no_price_with_nonzero_pnl(self):
        """Test get_net_pnl_pct returns 0 when no price but pnl would be non-zero"""
        executor = self.get_executor()
        # Set up state that would give non-zero pnl with a price
        executor.lp_position_state.base_amount = Decimal("2.0")
        executor.lp_position_state.quote_amount = Decimal("200.0")
        # But don't set current price
        executor._current_price = None

        # With mock to return non-zero pnl (simulating edge case)
        with patch.object(executor, 'get_net_pnl_quote', return_value=Decimal("10")):
            pct = executor.get_net_pnl_pct()
            self.assertEqual(pct, Decimal("0"))

    def test_get_custom_info_out_of_range_seconds(self):
        """Test get_custom_info includes out_of_range_seconds"""
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        executor.lp_position_state.state = LPExecutorStates.OUT_OF_RANGE
        executor.lp_position_state._out_of_range_since = 1234567800.0

        info = executor.get_custom_info()

        self.assertEqual(info["out_of_range_seconds"], 90.0)

    def test_get_custom_info_initial_amounts_from_state(self):
        """Test get_custom_info uses stored initial amounts"""
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        executor.lp_position_state.initial_base_amount = Decimal("0.95")
        executor.lp_position_state.initial_quote_amount = Decimal("105.0")

        info = executor.get_custom_info()

        self.assertEqual(info["initial_base_amount"], 0.95)
        self.assertEqual(info["initial_quote_amount"], 105.0)

    def test_get_custom_info_initial_amounts_fallback_to_config(self):
        """Test get_custom_info falls back to config for initial amounts"""
        executor = self.get_executor()
        executor._current_price = Decimal("100")
        # initial amounts are 0 by default

        info = executor.get_custom_info()

        # Should fall back to config values
        self.assertEqual(info["initial_base_amount"], 1.0)
        self.assertEqual(info["initial_quote_amount"], 100.0)

    async def test_control_task_fetches_position_info_when_position_exists(self):
        """Test control_task fetches position info instead of pool info when position exists"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.IN_RANGE
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state.lower_price = Decimal("95")
        executor.lp_position_state.upper_price = Decimal("105")

        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.01
        mock_position.quote_fee_amount = 0.5
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 100.0

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector.get_pool_info_by_address = AsyncMock()

        await executor.control_task()

        connector.get_position_info.assert_called_once()
        connector.get_pool_info_by_address.assert_not_called()

    async def test_control_task_fetches_pool_info_when_no_position(self):
        """Test control_task fetches pool info when no position exists"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.NOT_ACTIVE

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0

        connector = self.strategy.connectors["meteora/clmm"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        with patch.object(executor, '_create_position', new_callable=AsyncMock):
            await executor.control_task()

        connector.get_pool_info_by_address.assert_called_once()
