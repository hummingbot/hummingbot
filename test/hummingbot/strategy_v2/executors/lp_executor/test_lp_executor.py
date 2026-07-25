from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.event.events import RangePositionLiquidityAddedEvent, RangePositionLiquidityRemovedEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig, LPExecutorStates
from hummingbot.strategy_v2.executors.lp_executor.lp_executor import LPExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


def create_mock_remove_event(
    exchange_order_id: str = "sig789",
    trading_pair: str = "SOL-USDC",
    position_address: str = "pos123",
    base_amount: Decimal = Decimal("1.0"),
    quote_amount: Decimal = Decimal("100.0"),
    base_fee: Decimal = Decimal("0.01"),
    quote_fee: Decimal = Decimal("1.0"),
    mid_price: Decimal = Decimal("100"),
    lower_price: Decimal = Decimal("95"),
    upper_price: Decimal = Decimal("105"),
    tx_fee: Decimal = Decimal("0.0001"),
) -> RangePositionLiquidityRemovedEvent:
    """Create a mock RangePositionLiquidityRemovedEvent for testing."""
    trade_fee = TradeFeeBase.new_spot_fee(
        fee_schema={'percent_fee_token': 'SOL'},
        trade_type=None,
        flat_fees=[TokenAmount(amount=tx_fee, token='SOL')]
    )
    return RangePositionLiquidityRemovedEvent(
        timestamp=1234567890,
        order_id="order-123",
        exchange_order_id=exchange_order_id,
        trading_pair=trading_pair,
        token_id="0",
        trade_fee=trade_fee,
        creation_timestamp=1234567890,
        position_address=position_address,
        lower_price=lower_price,
        upper_price=upper_price,
        mid_price=mid_price,
        base_amount=base_amount,
        quote_amount=quote_amount,
        base_fee=base_fee,
        quote_fee=quote_fee,
        position_rent_refunded=Decimal("0.002"),
    )


def create_mock_add_event(
    exchange_order_id: str = "sig123",
    trading_pair: str = "SOL-USDC",
    position_address: str = "pos123",
    base_amount: Decimal = Decimal("5.0"),
    quote_amount: Decimal = Decimal("500.0"),
    mid_price: Decimal = Decimal("100"),
    lower_price: Decimal = Decimal("95"),
    upper_price: Decimal = Decimal("105"),
    position_rent: Decimal = Decimal("0.002"),
) -> RangePositionLiquidityAddedEvent:
    """Create a mock RangePositionLiquidityAddedEvent for testing."""
    trade_fee = TradeFeeBase.new_spot_fee(
        fee_schema={'percent_fee_token': 'SOL'},
        trade_type=None,
        flat_fees=[TokenAmount(amount=position_rent, token='SOL')]
    )
    return RangePositionLiquidityAddedEvent(
        timestamp=1234567890,
        order_id="order-123",
        exchange_order_id=exchange_order_id,
        trading_pair=trading_pair,
        lower_price=lower_price,
        upper_price=upper_price,
        amount=base_amount + quote_amount / mid_price,
        fee_tier="pool123",
        creation_timestamp=1234567890,
        trade_fee=trade_fee,
        position_address=position_address,
        mid_price=mid_price,
        base_amount=base_amount,
        quote_amount=quote_amount,
        position_rent=position_rent,
    )


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
            "solana-mainnet-beta": connector,
        }
        strategy.notify_hb_app_with_timestamp = MagicMock()
        return strategy

    def get_default_config(self) -> LPExecutorConfig:
        return LPExecutorConfig(
            id="test-lp-1",
            timestamp=1234567890,
            connector_name="solana-mainnet-beta",
            lp_provider="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="pool123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
            base_amount=Decimal("1.0"),
            quote_amount=Decimal("100"),
            side=TradeType.BUY,
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
        self.assertEqual(executor.config.connector_name, "solana-mainnet-beta")
        self.assertEqual(executor.config.trading_pair, "SOL-USDC")
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.NOT_ACTIVE)
        self.assertIsNone(executor._pool_info)

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

    @patch('hummingbot.strategy_v2.executors.lp_executor.lp_executor.GatewayHttpClient')
    async def test_on_start_resolves_swap_provider(self, mock_gateway_client):
        """Test on_start resolves swap_provider when keep_position=False and no swap_provider."""
        config = self.get_default_config()
        config_dict = config.model_dump()
        config_dict["keep_position"] = False
        config_dict["swap_provider"] = None
        new_config = LPExecutorConfig(**config_dict)

        executor = self.get_executor(new_config)

        # Mock gateway client to return a swap provider
        mock_instance = MagicMock()
        mock_instance.get_default_swap_provider = AsyncMock(return_value="jupiter/router")
        mock_gateway_client.get_instance.return_value = mock_instance

        with patch.object(executor.__class__.__bases__[0], 'on_start', new_callable=AsyncMock):
            await executor.on_start()

        mock_instance.get_default_swap_provider.assert_called_once_with(new_config.connector_name)
        self.assertEqual(executor.config.swap_provider, "jupiter/router")

    @patch('hummingbot.strategy_v2.executors.lp_executor.lp_executor.GatewayHttpClient')
    async def test_on_start_no_swap_provider_warning(self, mock_gateway_client):
        """Test on_start logs warning when no swap_provider available."""
        config = self.get_default_config()
        config_dict = config.model_dump()
        config_dict["keep_position"] = False
        config_dict["swap_provider"] = None
        new_config = LPExecutorConfig(**config_dict)

        executor = self.get_executor(new_config)

        # Mock gateway client to return None (no swap provider)
        mock_instance = MagicMock()
        mock_instance.get_default_swap_provider = AsyncMock(return_value=None)
        mock_gateway_client.get_instance.return_value = mock_instance

        with patch.object(executor.__class__.__bases__[0], 'on_start', new_callable=AsyncMock):
            await executor.on_start()

        mock_instance.get_default_swap_provider.assert_called_once_with(new_config.connector_name)
        # swap_provider should remain None
        self.assertIsNone(executor.config.swap_provider)

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
        """Test early_stop with keep_position=True transitions to CLOSING (always closes on-chain)"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.IN_RANGE

        executor.early_stop(keep_position=True)

        self.assertEqual(executor._status, RunnableStatus.SHUTTING_DOWN)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        # With new behavior, position is always closed on-chain
        # The spot position is captured after close completes
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)

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

    def test_pnl_zero_for_failed_executor_no_position(self):
        """Test P&L returns 0 when executor failed before creating a position.

        Failed executors that never created a position should report 0 P&L,
        not -100% (which would incorrectly suggest total loss of config amounts).
        """
        executor = self.get_executor()
        executor._current_price = Decimal("100")

        # Simulate failed state - no position was ever created
        executor.lp_position_state.state = LPExecutorStates.FAILED
        executor.lp_position_state.position_address = None

        # P&L should be 0, not -100%
        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))
        self.assertEqual(executor.get_net_pnl_pct(), Decimal("0"))

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
        # Pct ratio = 2 / 200 = 0.01 (1%)
        self.assertEqual(executor.get_net_pnl_pct(), Decimal("0.01"))

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

        self.assertEqual(info["side"], TradeType.BUY)
        self.assertEqual(info["state"], "NOT_ACTIVE")
        self.assertIsNone(info["position_address"])
        self.assertIsNone(info["current_price"])
        self.assertEqual(info["lower_price"], 0.0)
        self.assertEqual(info["upper_price"], 0.0)

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

        self.assertEqual(info["side"], TradeType.BUY)
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

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        await executor.update_pool_info()

        self.assertEqual(executor._pool_info, mock_pool_info)
        connector.get_pool_info_by_address.assert_called_once_with("pool123", dex_name="meteora", trading_type="clmm")

    async def test_update_pool_info_error(self):
        """Test update_pool_info handles errors gracefully"""
        executor = self.get_executor()
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_info_by_address = AsyncMock(side_effect=Exception("Network error"))

        await executor.update_pool_info()

        self.assertIsNone(executor._pool_info)

    async def test_update_pool_info_no_connector(self):
        """Test update_pool_info with missing connector"""
        executor = self.get_executor()
        executor.connectors = {}  # Clear executor's connectors

        await executor.update_pool_info()

        self.assertIsNone(executor._pool_info)

    def test_handle_create_failure_transitions_to_failed(self):
        """Test _handle_create_failure transitions to FAILED state (retry at connector level)"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING
        executor.lp_position_state.active_open_order = MagicMock()

        executor._handle_create_failure(Exception("Test error"))

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)
        self.assertIsNone(executor.lp_position_state.active_open_order)

    def test_handle_create_failure_closes_an_already_opened_position(self):
        """A throw after add_liquidity landed must close the position, not abandon it.

        FAILED stops the executor without ever calling _close_position, and the
        add-liquidity event that records the position is emitted after the code
        most likely to throw -- so the funds would survive only in a log line.
        """
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING
        executor.lp_position_state.active_open_order = MagicMock()
        executor.lp_position_state.position_address = "position-abc"

        executor._handle_create_failure(Exception("bad position_info field"))

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)
        self.assertEqual(executor.close_type, CloseType.FAILED)
        self.assertIsNone(executor.lp_position_state.active_open_order)
        self.assertTrue(self.is_partially_logged("ERROR", "position-abc"))

    async def test_recovery_close_records_no_hold_and_no_swap(self):
        """The recovery close is pure cleanup: CloseType.FAILED holds nothing."""
        executor = self.get_executor()
        executor._get_native_to_quote_rate = MagicMock(return_value=Decimal("1"))
        executor._current_price = Decimal("100")
        executor.lp_position_state.position_address = "position-abc"
        executor._handle_create_failure(Exception("bad position_info field"))

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._clmm_close_position = AsyncMock(return_value="sig-remove")
        connector._lp_orders_metadata = {
            "order-123": {
                "base_amount": Decimal("1.0"),
                "quote_amount": Decimal("100.0"),
                "base_fee": Decimal("0"),
                "quote_fee": Decimal("0"),
                "position_rent_refunded": Decimal("0.002"),
                "tx_fee": Decimal("0"),
            }
        }
        connector._trigger_remove_liquidity_event = MagicMock(
            return_value=create_mock_remove_event(
                base_amount=Decimal("1.0"), quote_amount=Decimal("100.0")
            )
        )

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)
        self.assertEqual(executor.close_type, CloseType.FAILED)
        self.assertEqual(executor._held_position_orders, [])

    def test_handle_close_failure_transitions_to_failed(self):
        """Test _handle_close_failure transitions to FAILED state (retry at connector level)"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.CLOSING
        executor.lp_position_state.active_close_order = MagicMock()

        executor._handle_close_failure(Exception("Test error"))

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)
        self.assertIsNone(executor.lp_position_state.active_close_order)

    async def test_control_task_not_active_starts_opening(self):
        """Test control_task transitions from NOT_ACTIVE to OPENING"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
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
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        with patch.object(executor, 'stop') as mock_stop:
            await executor.control_task()
            mock_stop.assert_called_once()

    async def test_control_task_out_of_range_upper_limit(self):
        """Test control_task closes when price exceeds upper_limit_price.

        With keep_position=True, close_type should be POSITION_HOLD.
        """
        config = self.get_default_config()
        config.upper_limit_price = Decimal("115")  # Close when price >= 115
        config.keep_position = True
        executor = self.get_executor(config)
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.OUT_OF_RANGE
        executor.lp_position_state.position_address = "pos123"

        # Mock position info with price above upper_limit_price
        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 120.0  # Above upper_limit_price (115)

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)
        # When keep_position=True (default), limit hit uses POSITION_HOLD
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)

    async def test_control_task_out_of_range_lower_limit(self):
        """Test control_task closes when price falls below lower_limit_price.

        With keep_position=True, close_type should be POSITION_HOLD.
        """
        config = self.get_default_config()
        config.lower_limit_price = Decimal("90")  # Close when price <= 90
        config.keep_position = True
        executor = self.get_executor(config)
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.OUT_OF_RANGE
        executor.lp_position_state.position_address = "pos123"

        # Mock position info with price below lower_limit_price
        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 85.0  # Below lower_limit_price (90)

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)
        # When keep_position=True (default), limit hit uses POSITION_HOLD
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)

    async def test_control_task_in_range_lower_limit(self):
        """A limit price crossed while the position is still IN_RANGE must close it.

        Regression for the QA scenario on a tight Meteora range: bin rounding at
        open made the on-chain position one bin wider than configured, so the
        price sat below lower_limit_price while the position was genuinely in
        range - and the old code only checked limits in OUT_OF_RANGE.
        """
        config = self.get_default_config()
        config.lower_limit_price = Decimal("98")  # Inside the [95, 105] range
        config.keep_position = True
        executor = self.get_executor(config)
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.IN_RANGE
        executor.lp_position_state.position_address = "pos123"

        # Price is within the position's bounds but at/below the lower limit
        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 96.0  # In range (95-105) but below lower_limit_price (98)

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)

    async def test_control_task_in_range_upper_limit(self):
        """An upper limit crossed while still IN_RANGE must close the position."""
        config = self.get_default_config()
        config.upper_limit_price = Decimal("102")  # Inside the [95, 105] range
        config.keep_position = False
        executor = self.get_executor(config)
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.IN_RANGE
        executor.lp_position_state.position_address = "pos123"

        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 103.0  # In range (95-105) but above upper_limit_price (102)

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)
        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)

    async def test_control_task_out_of_range_no_limit_no_close(self):
        """Test control_task does not close when out of range but no limit prices set"""
        config = self.get_default_config()
        # No upper_limit_price or lower_limit_price set
        executor = self.get_executor(config)
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.OUT_OF_RANGE
        executor.lp_position_state.position_address = "pos123"

        # Mock position info with price out of range
        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 120.0  # Out of range but no limit set

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor.control_task()

        # Should still be OUT_OF_RANGE, not CLOSING
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.OUT_OF_RANGE)

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

        connector = self.strategy.connectors["solana-mainnet-beta"]
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

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Position closed: pos123"))
        connector.create_market_order_id = MagicMock(return_value="order-123")
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._update_position_info()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_update_position_info_no_position_address(self):
        """Test _update_position_info returns early when no position"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = None

        connector = self.strategy.connectors["solana-mainnet-beta"]
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

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=None)

        await executor._update_position_info()
        # Should log warning but not crash

    async def test_update_position_info_not_found_error(self):
        """Test _update_position_info handles not found error"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Position not found: pos123"))

        await executor._update_position_info()
        # Should log error but not crash, state unchanged

    async def test_update_position_info_other_error(self):
        """Test _update_position_info handles other errors"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["solana-mainnet-beta"]
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

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor._update_position_info()

        self.assertEqual(executor._current_price, Decimal("99.5"))

    async def test_control_task_opening_state_retries(self):
        """Test control_task calls _create_position when OPENING (connector handles retry)"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.OPENING

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        with patch.object(executor, '_create_position', new_callable=AsyncMock) as mock_create:
            await executor.control_task()
            mock_create.assert_called_once()

    async def test_control_task_closing_state_retries(self):
        """Test control_task calls _close_position when CLOSING (connector handles retry)"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.CLOSING
        executor.lp_position_state.position_address = "pos123"

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        with patch.object(executor, '_close_position', new_callable=AsyncMock) as mock_close:
            await executor.control_task()
            mock_close.assert_called_once()

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
        connector = self.strategy.connectors["solana-mainnet-beta"]
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

        connector = self.strategy.connectors["solana-mainnet-beta"]
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
        connector._trigger_add_liquidity_event.assert_called_once()

    async def test_create_position_no_position_address(self):
        """Test _create_position handles missing position address"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector._clmm_add_liquidity = AsyncMock(return_value="sig123")
        connector._lp_orders_metadata = {"order-123": {}}  # No position_address

        await executor._create_position()

        # Should transition to FAILED state since no position address returned
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)
        self.assertIsNone(executor.lp_position_state.position_address)

    async def test_create_position_exception(self):
        """Test _create_position handles exception (connector handles retry internally)"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector._clmm_add_liquidity = AsyncMock(side_effect=Exception("Gateway error"))
        connector._lp_orders_metadata = {}

        await executor._create_position()

        # Should transition to FAILED state when connector raises exception
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    async def test_create_position_with_signature_in_metadata(self):
        """Test _create_position handles exception with signature in metadata"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector._clmm_add_liquidity = AsyncMock(side_effect=Exception("TRANSACTION_TIMEOUT"))
        connector._lp_orders_metadata = {"order-123": {"signature": "sig999"}}

        await executor._create_position()

        # Connector handles retry internally; when it raises, executor transitions to FAILED
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    async def test_create_position_fetches_position_info(self):
        """Test _create_position fetches position info and stores initial amounts"""
        executor = self.get_executor()

        connector = self.strategy.connectors["solana-mainnet-beta"]
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
        connector._trigger_add_liquidity_event = MagicMock(return_value=create_mock_add_event(
            base_amount=Decimal("0.95"), quote_amount=Decimal("105.0")
        ))

        await executor._create_position()

        self.assertEqual(executor.lp_position_state.base_amount, Decimal("0.95"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("105.0"))
        self.assertEqual(executor.lp_position_state.initial_base_amount, Decimal("0.95"))
        self.assertEqual(executor.lp_position_state.initial_quote_amount, Decimal("105.0"))
        self.assertEqual(executor.lp_position_state.add_mid_price, Decimal("100.0"))

    async def test_create_position_position_info_returns_none(self):
        """Test _create_position handles None position info response"""
        executor = self.get_executor()

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector._clmm_add_liquidity = AsyncMock(return_value="sig123")
        connector._lp_orders_metadata = {
            "order-123": {"position_address": "pos456", "position_rent": Decimal("0.002")}
        }
        connector.get_position_info = AsyncMock(return_value=None)
        connector._trigger_add_liquidity_event = MagicMock(return_value=create_mock_add_event())

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

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=None)
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)
        connector._trigger_remove_liquidity_event.assert_called_once()

    async def test_close_position_already_closed_exception(self):
        """Test _close_position handles position closed exception"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Position closed: pos123"))
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_close_position_not_found_exception(self):
        """Test _close_position handles position not found exception"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Position not found: pos123"))
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_close_position_other_exception_proceeds(self):
        """Test _close_position proceeds with close on other exceptions"""
        executor = self.get_executor()
        executor.lp_position_state.position_address = "pos123"

        connector = self.strategy.connectors["solana-mainnet-beta"]
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
        connector._trigger_remove_liquidity_event = MagicMock(return_value=create_mock_remove_event())

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
        connector = self.strategy.connectors["solana-mainnet-beta"]
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
        connector._trigger_remove_liquidity_event = MagicMock(return_value=create_mock_remove_event())

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)
        self.assertIsNone(executor.lp_position_state.position_address)
        self.assertEqual(executor.lp_position_state.base_amount, Decimal("1.0"))
        self.assertEqual(executor.lp_position_state.quote_amount, Decimal("100.0"))
        self.assertEqual(executor.lp_position_state.position_rent_refunded, Decimal("0.002"))
        self.assertEqual(executor.lp_position_state.tx_fee, Decimal("0.0001"))  # Close tx_fee added
        connector._trigger_remove_liquidity_event.assert_called_once()

    async def test_close_position_exception(self):
        """Test _close_position handles exception during close (connector handles retry)"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.CLOSING
        executor.lp_position_state.position_address = "pos123"

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._clmm_close_position = AsyncMock(side_effect=Exception("Gateway error"))
        connector._lp_orders_metadata = {}

        await executor._close_position()

        # Connector handles retry internally; when it raises, executor transitions to FAILED
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    async def test_close_position_exception_with_signature(self):
        """Test _close_position handles exception with signature in metadata"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.CLOSING
        executor.lp_position_state.position_address = "pos123"

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._clmm_close_position = AsyncMock(side_effect=Exception("TRANSACTION_TIMEOUT"))
        connector._lp_orders_metadata = {"order-123": {"signature": "sig999"}}

        await executor._close_position()

        # Connector handles retry internally; when it raises, executor transitions to FAILED
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

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

        connector = self.strategy.connectors["solana-mainnet-beta"]
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

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector._trigger_remove_liquidity_event = MagicMock()

        executor._emit_already_closed_event()

        # Should use Decimal("0") as price
        connector._trigger_remove_liquidity_event.assert_called_once()

    def test_get_net_pnl_pct_zero_initial_value(self):
        """Test get_net_pnl_pct handles zero initial value"""
        config = LPExecutorConfig(
            id="test-lp-1",
            timestamp=1234567890,
            connector_name="solana-mainnet-beta",
            lp_provider="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="pool123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
            base_amount=Decimal("0"),
            quote_amount=Decimal("0"),
            side=TradeType.BUY,
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
        # Pct ratio = 2 / 200 = 0.01 (1%)
        pct = executor.get_net_pnl_pct()
        self.assertEqual(pct, Decimal("0.01"))

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

        connector = self.strategy.connectors["solana-mainnet-beta"]
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

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        with patch.object(executor, '_create_position', new_callable=AsyncMock):
            await executor.control_task()

        connector.get_pool_info_by_address.assert_called_once()

    async def test_control_task_failed_state(self):
        """Test control_task handles FAILED state"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.FAILED

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        with patch.object(executor, 'stop') as mock_stop:
            await executor.control_task()
            self.assertEqual(executor.close_type, CloseType.FAILED)
            mock_stop.assert_called_once()

    @patch('hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS', {'solana-mainnet-beta'})
    def test_validate_connector_network_format_success(self):
        """Test connector validation succeeds with network format"""
        executor = self.get_executor()

        result = executor._validate_and_normalize_connector("solana-mainnet-beta")

        self.assertEqual(result, "solana-mainnet-beta")

    @patch('hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS', {'solana-mainnet-beta'})
    def test_validate_connector_network_not_found(self):
        """Test connector validation fails for unknown network"""
        config = LPExecutorConfig(
            id="test-lp-1",
            timestamp=1234567890,
            connector_name="unknown-network",
            lp_provider="unknown/clmm",
            trading_pair="SOL-USDC",
            pool_address="pool123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
            base_amount=Decimal("1.0"),
            quote_amount=Decimal("100"),
            side=TradeType.BUY,
        )
        executor = self.get_executor(config)
        executor.stop = MagicMock()

        result = executor._validate_and_normalize_connector("unknown-network")

        self.assertIsNone(result)
        self.assertEqual(executor.close_type, CloseType.FAILED)
        executor.stop.assert_called_once()

    async def test_on_start_connector_normalization(self):
        """Test on_start normalizes connector name"""
        config = LPExecutorConfig(
            id="test-lp-1",
            timestamp=1234567890,
            connector_name="solana-mainnet-beta",  # Network format
            lp_provider="meteora/clmm",  # DEX name
            trading_pair="SOL-USDC",
            pool_address="pool123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
            base_amount=Decimal("1.0"),
            quote_amount=Decimal("100"),
            side=TradeType.BUY,
        )
        executor = self.get_executor(config)

        with patch('hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS', {'solana-mainnet-beta'}):
            await executor.on_start()

        self.assertEqual(executor.config.connector_name, "solana-mainnet-beta")

    # Tests for SWAPPING state and close-out swap functionality

    async def test_control_task_swapping_state(self):
        """Test control_task calls _execute_closeout_swap when SWAPPING"""
        executor = self.get_executor()
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.SWAPPING

        mock_pool_info = MagicMock()
        mock_pool_info.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_pool_info_by_address = AsyncMock(return_value=mock_pool_info)

        with patch.object(executor, '_execute_closeout_swap', new_callable=AsyncMock) as mock_swap:
            await executor.control_task()
            mock_swap.assert_called_once()

    async def test_close_position_with_keep_position_false_needs_swap(self):
        """Test _close_position triggers swap when keep_position=False and base differs"""
        config = self.get_default_config()
        config_dict = config.model_dump()
        config_dict["keep_position"] = False
        config_dict["swap_provider"] = "jupiter/router"
        new_config = LPExecutorConfig(**config_dict)

        executor = self.get_executor(new_config)
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor.close_type = CloseType.EARLY_STOP  # set by early_stop(keep_position=False)

        # Position close returns more base than initial (IL scenario)
        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._clmm_close_position = AsyncMock(return_value="sig789")
        connector._lp_orders_metadata = {
            "order-123": {
                "base_amount": Decimal("1.5"),  # More base than initial
                "quote_amount": Decimal("50.0"),  # Less quote
                "base_fee": Decimal("0.01"),
                "quote_fee": Decimal("0.5"),
                "position_rent_refunded": Decimal("0.002"),
                "tx_fee": Decimal("0.0001")
            }
        }
        connector._trigger_remove_liquidity_event = MagicMock(return_value=create_mock_remove_event(
            base_amount=Decimal("1.5"), quote_amount=Decimal("50.0")
        ))

        await executor._close_position()

        # Should transition to SWAPPING since base_diff > 0.000001
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.SWAPPING)

    async def test_close_position_with_keep_position_false_no_swap_needed(self):
        """Test _close_position goes to COMPLETE when no swap needed"""
        config = self.get_default_config()
        config_dict = config.model_dump()
        config_dict["keep_position"] = False
        config_dict["swap_provider"] = "jupiter/router"
        new_config = LPExecutorConfig(**config_dict)

        executor = self.get_executor(new_config)
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor.close_type = CloseType.EARLY_STOP  # set by early_stop(keep_position=False)

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._clmm_close_position = AsyncMock(return_value="sig789")
        connector._lp_orders_metadata = {
            "order-123": {
                "base_amount": Decimal("1.0"),  # Same as initial
                "quote_amount": Decimal("100.0"),
                "base_fee": Decimal("0.0"),
                "quote_fee": Decimal("0.0"),
                "position_rent_refunded": Decimal("0.002"),
                "tx_fee": Decimal("0.0001")
            }
        }
        connector._trigger_remove_liquidity_event = MagicMock(return_value=create_mock_remove_event(
            base_amount=Decimal("1.0"), quote_amount=Decimal("100.0")
        ))

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_close_position_with_keep_position_false_quote_only_completes(self):
        """A quote-only withdrawal has no base to sell back, so no close-out swap is needed."""
        config = self.get_default_config()
        config_dict = config.model_dump()
        config_dict["keep_position"] = False
        config_dict["swap_provider"] = "jupiter/router"
        new_config = LPExecutorConfig(**config_dict)

        executor = self.get_executor(new_config)
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state.initial_base_amount = Decimal("0")
        executor.lp_position_state.initial_quote_amount = Decimal("100.0")
        executor.close_type = CloseType.EARLY_STOP  # set by early_stop(keep_position=False)

        mock_position = MagicMock()
        mock_position.price = 100.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)
        connector._clmm_close_position = AsyncMock(return_value="sig789")
        connector._lp_orders_metadata = {
            "order-123": {
                "base_amount": Decimal("0"),  # Price moved below range: all base converted to quote
                "quote_amount": Decimal("99.0"),
                "base_fee": Decimal("0"),
                "quote_fee": Decimal("0.5"),
                "position_rent_refunded": Decimal("0.002"),
                "tx_fee": Decimal("0.0001")
            }
        }
        connector._trigger_remove_liquidity_event = MagicMock(return_value=create_mock_remove_event(
            base_amount=Decimal("0"), quote_amount=Decimal("99.0"), base_fee=Decimal("0")
        ))

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_execute_closeout_swap_no_connector(self):
        """Test _execute_closeout_swap handles missing connector"""
        executor = self.get_executor()
        executor.config.swap_provider = "jupiter/router"
        executor.connectors = {}  # No connectors

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    async def test_execute_closeout_swap_no_swap_provider(self):
        """Test _execute_closeout_swap handles missing swap_provider"""
        executor = self.get_executor()
        executor.config.swap_provider = None

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    async def test_execute_closeout_swap_active_order_filled(self):
        """Test _execute_closeout_swap handles FILLED swap order"""
        from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
        from hummingbot.strategy_v2.executors.lp_executor.data_types import TrackedOrder

        executor = self.get_executor()
        executor.config.swap_provider = "jupiter/router"
        executor.lp_position_state.active_swap_order = TrackedOrder(order_id="swap-123")

        mock_order = MagicMock(spec=InFlightOrder)
        mock_order.client_order_id = "swap-123"
        mock_order.current_state = OrderState.FILLED

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_order = MagicMock(return_value=mock_order)

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)
        self.assertIsNone(executor.lp_position_state.active_swap_order)

    async def test_execute_closeout_swap_active_order_failed(self):
        """Test _execute_closeout_swap handles FAILED swap order"""
        from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
        from hummingbot.strategy_v2.executors.lp_executor.data_types import TrackedOrder

        executor = self.get_executor()
        executor.config.swap_provider = "jupiter/router"
        executor.lp_position_state.active_swap_order = TrackedOrder(order_id="swap-123")

        mock_order = MagicMock(spec=InFlightOrder)
        mock_order.client_order_id = "swap-123"
        mock_order.current_state = OrderState.FAILED

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_order = MagicMock(return_value=mock_order)

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    async def test_execute_closeout_swap_active_order_canceled(self):
        """Test _execute_closeout_swap handles CANCELED swap order"""
        from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
        from hummingbot.strategy_v2.executors.lp_executor.data_types import TrackedOrder

        executor = self.get_executor()
        executor.config.swap_provider = "jupiter/router"
        executor.lp_position_state.active_swap_order = TrackedOrder(order_id="swap-123")

        mock_order = MagicMock(spec=InFlightOrder)
        mock_order.client_order_id = "swap-123"
        mock_order.current_state = OrderState.CANCELED

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_order = MagicMock(return_value=mock_order)

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    async def test_execute_closeout_swap_active_order_not_found_multiple_times(self):
        """Test _execute_closeout_swap handles order not found after multiple checks"""
        from hummingbot.strategy_v2.executors.lp_executor.data_types import TrackedOrder

        executor = self.get_executor()
        executor.config.swap_provider = "jupiter/router"
        executor.lp_position_state.active_swap_order = TrackedOrder(order_id="swap-123")
        executor._swap_not_found_count = 2  # Already checked twice

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_order = MagicMock(return_value=None)

        await executor._execute_closeout_swap()

        # After 3 checks, assume completed
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)
        self.assertIsNone(executor.lp_position_state.active_swap_order)

    async def test_execute_closeout_swap_no_swap_needed(self):
        """Test _execute_closeout_swap completes when no swap needed"""
        executor = self.get_executor()
        executor.config.swap_provider = "jupiter/router"
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("1.0")  # Same
        executor.lp_position_state.base_fee = Decimal("0.0")

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_execute_closeout_swap_sell_excess_base(self):
        """Test _execute_closeout_swap sells excess base tokens"""
        executor = self.get_executor()
        executor.config.swap_provider = "jupiter/router"
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("1.5")  # More base than initial
        executor.lp_position_state.base_fee = Decimal("0.01")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.place_order = MagicMock(return_value="swap-order-123")

        await executor._execute_closeout_swap()

        # Should place a SELL order
        connector.place_order.assert_called_once()
        call_kwargs = connector.place_order.call_args[1]
        self.assertFalse(call_kwargs["is_buy"])  # SELL
        self.assertIsNotNone(executor.lp_position_state.active_swap_order)

    async def test_execute_closeout_swap_buy_back_base(self):
        """Test _execute_closeout_swap buys back base tokens"""
        executor = self.get_executor()
        executor.config.swap_provider = "jupiter/router"
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("0.5")  # Less base than initial
        executor.lp_position_state.base_fee = Decimal("0.01")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.place_order = MagicMock(return_value="swap-order-123")

        await executor._execute_closeout_swap()

        # Should place a BUY order
        connector.place_order.assert_called_once()
        call_kwargs = connector.place_order.call_args[1]
        self.assertTrue(call_kwargs["is_buy"])  # BUY
        self.assertIsNotNone(executor.lp_position_state.active_swap_order)

    async def test_execute_closeout_swap_is_quote_asset_agnostic(self):
        """The close-out swaps the net base change whatever the quote asset is.

        The rest of this suite runs on SOL-USDC (USDC quote); this covers the
        other common shape, a token quoted in SOL. The amount is pure base-side
        arithmetic, so it must not vary with the quote token.
        """
        config_dict = self.get_default_config().model_dump()
        config_dict["trading_pair"] = "BONK-SOL"
        executor = self.get_executor(LPExecutorConfig(**config_dict))
        executor.config.swap_provider = "jupiter/router"
        executor.lp_position_state.initial_base_amount = Decimal("1000")
        executor.lp_position_state.base_amount = Decimal("1400")
        executor.lp_position_state.base_fee = Decimal("25")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.place_order = MagicMock(return_value="swap-order-123")

        await executor._execute_closeout_swap()

        connector.place_order.assert_called_once()
        call_kwargs = connector.place_order.call_args[1]
        self.assertFalse(call_kwargs["is_buy"])  # SELL base for quote
        self.assertEqual(call_kwargs["trading_pair"], "BONK-SOL")
        # (base + base_fee) - initial_base: the net base the position handed back
        self.assertEqual(call_kwargs["amount"], Decimal("425"))

    async def test_execute_closeout_swap_exception(self):
        """Test _execute_closeout_swap handles exception when placing swap"""
        executor = self.get_executor()
        executor.config.swap_provider = "jupiter/router"
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.base_fee = Decimal("0.01")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.place_order = MagicMock(side_effect=Exception("Swap failed"))

        await executor._execute_closeout_swap()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    def test_force_stop_mid_swap_holds_withdrawn_balance(self):
        """A forced stop mid-SWAPPING converts the withdrawn tokens into a position hold.

        Liquidity is out of the pool but the close-out swap has not confirmed, so the
        base sits in the wallet as spot. The shutdown-deadline fallback must record the
        net trade versus the ADD — the same record the keep_position path would have
        stored at REMOVE — instead of terminating with nothing tracked.
        """
        executor = self.get_executor()
        executor.close_type = CloseType.EARLY_STOP
        executor._status = RunnableStatus.SHUTTING_DOWN
        executor._current_price = Decimal("100")
        executor._add_base_amount = Decimal("1.0")
        executor._add_quote_amount = Decimal("100.0")
        executor.lp_position_state.state = LPExecutorStates.SWAPPING
        executor.lp_position_state.position_address = None
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.base_fee = Decimal("0.01")
        executor.lp_position_state.quote_amount = Decimal("40.0")
        executor.lp_position_state.quote_fee = Decimal("0.5")

        executor.force_stop_with_position_hold()

        self.assertEqual(CloseType.POSITION_HOLD, executor.close_type)
        self.assertEqual(RunnableStatus.TERMINATED, executor.status)
        self.assertEqual(1, len(executor._held_position_orders))
        held = executor._held_position_orders[0]
        # net_base = (1.5 + 0.01) - 1.0 = +0.51; net_quote = 40.5 - 100 = -59.5 -> BUY
        self.assertEqual("BUY", held["trade_type"])
        self.assertAlmostEqual(0.51, held["executed_amount_base"])
        self.assertAlmostEqual(59.5, held["executed_amount_quote"])
        self.assertIn("held_position_orders", executor.get_custom_info())

    def test_force_stop_with_position_still_onchain_fails_loudly(self):
        """A position that never got its REMOVE cannot be held as spot orders.

        The forced stop must not fabricate a hold; it closes as FAILED and names the
        on-chain address so the position can be recovered.
        """
        executor = self.get_executor()
        executor.close_type = CloseType.EARLY_STOP
        executor._status = RunnableStatus.SHUTTING_DOWN
        executor.lp_position_state.state = LPExecutorStates.CLOSING
        executor.lp_position_state.position_address = "position-abc"

        executor.force_stop_with_position_hold()

        self.assertEqual(CloseType.FAILED, executor.close_type)
        self.assertEqual(RunnableStatus.TERMINATED, executor.status)
        self.assertEqual(0, len(executor._held_position_orders))
        self.assertTrue(self.is_partially_logged("ERROR", "still on-chain at position-abc"))

    # Tests for _store_lp_event_from_remove variations

    def test_store_lp_event_from_remove_tx_fee_only(self):
        """Test _store_lp_event_from_remove records tx_fee with no conversion"""
        executor = self.get_executor()
        # Set up ADD amounts (stored when position opened)
        executor._add_base_amount = Decimal("1.0")
        executor._add_quote_amount = Decimal("100.0")
        executor._add_tx_fee_quote = 0.001

        event = create_mock_remove_event(
            base_amount=Decimal("1.0"),  # Same as initial
            quote_amount=Decimal("100.0"),  # Same as initial
            base_fee=Decimal("0.0"),
            quote_fee=Decimal("0.0"),
            tx_fee=Decimal("0.001"),  # Only tx_fee
        )

        executor._store_lp_event_from_remove(event)

        # Should record with tx_fee but 0 amounts
        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertEqual(executor._held_position_orders[0]["executed_amount_base"], 0.0)
        self.assertGreater(executor._held_position_orders[0]["cumulative_fee_paid_quote"], 0)

    def test_store_lp_event_from_remove_buy_scenario(self):
        """Test _store_lp_event_from_remove records BUY when gained base, lost quote"""
        executor = self.get_executor()
        executor._add_base_amount = Decimal("1.0")
        executor._add_quote_amount = Decimal("100.0")
        executor._add_tx_fee_quote = 0.0

        event = create_mock_remove_event(
            base_amount=Decimal("1.5"),  # Gained 0.5 base
            quote_amount=Decimal("50.0"),  # Lost 50 quote
            base_fee=Decimal("0.01"),
            quote_fee=Decimal("0.5"),
        )

        executor._store_lp_event_from_remove(event)

        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertEqual(executor._held_position_orders[0]["trade_type"], "BUY")
        self.assertGreater(executor._held_position_orders[0]["executed_amount_base"], 0)

    def test_store_lp_event_from_remove_sell_scenario(self):
        """Test _store_lp_event_from_remove records SELL when lost base, gained quote"""
        executor = self.get_executor()
        executor._add_base_amount = Decimal("1.0")
        executor._add_quote_amount = Decimal("100.0")
        executor._add_tx_fee_quote = 0.0

        event = create_mock_remove_event(
            base_amount=Decimal("0.5"),  # Lost 0.5 base
            quote_amount=Decimal("150.0"),  # Gained 50 quote
            base_fee=Decimal("0.01"),
            quote_fee=Decimal("0.5"),
        )

        executor._store_lp_event_from_remove(event)

        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertEqual(executor._held_position_orders[0]["trade_type"], "SELL")
        self.assertGreater(executor._held_position_orders[0]["executed_amount_base"], 0)

    def test_store_lp_event_from_remove_base_only_change_positive(self):
        """Test _store_lp_event_from_remove handles positive base-only change (BUY)"""
        executor = self.get_executor()
        executor._add_base_amount = Decimal("1.0")
        executor._add_quote_amount = Decimal("100.0")
        executor._add_tx_fee_quote = 0.0

        event = create_mock_remove_event(
            base_amount=Decimal("1.5"),  # Gained 0.5 base
            quote_amount=Decimal("100.0"),  # Same quote
            base_fee=Decimal("0.0"),
            quote_fee=Decimal("0.0"),
        )

        executor._store_lp_event_from_remove(event)

        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertEqual(executor._held_position_orders[0]["trade_type"], "BUY")

    def test_store_lp_event_from_remove_base_only_change_negative(self):
        """Test _store_lp_event_from_remove handles negative base-only change (SELL)"""
        executor = self.get_executor()
        executor._add_base_amount = Decimal("1.0")
        executor._add_quote_amount = Decimal("100.0")
        executor._add_tx_fee_quote = 0.0

        event = create_mock_remove_event(
            base_amount=Decimal("0.5"),  # Lost 0.5 base
            quote_amount=Decimal("100.0"),  # Same quote
            base_fee=Decimal("0.0"),
            quote_fee=Decimal("0.0"),
        )

        executor._store_lp_event_from_remove(event)

        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertEqual(executor._held_position_orders[0]["trade_type"], "SELL")

    def test_store_lp_event_from_remove_quote_only_change(self):
        """Test _store_lp_event_from_remove handles quote-only change"""
        executor = self.get_executor()
        executor._add_base_amount = Decimal("1.0")
        executor._add_quote_amount = Decimal("100.0")
        executor._add_tx_fee_quote = 0.0

        event = create_mock_remove_event(
            base_amount=Decimal("1.0"),  # Same base
            quote_amount=Decimal("110.0"),  # Gained 10 quote (fees)
            base_fee=Decimal("0.0"),
            quote_fee=Decimal("10.0"),
        )

        executor._store_lp_event_from_remove(event)

        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertEqual(executor._held_position_orders[0]["executed_amount_base"], 0.0)

    # Tests for early_stop from OPENING state

    def test_early_stop_from_opening_state(self):
        """Test early_stop from OPENING state goes to FAILED with EARLY_STOP"""
        executor = self.get_executor()
        executor.lp_position_state.state = LPExecutorStates.OPENING

        executor.early_stop()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)
        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)

    # Tests for _calculate_net_base_difference

    def test_calculate_net_base_difference_positive(self):
        """Test _calculate_net_base_difference returns positive when gained base"""
        executor = self.get_executor()
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("1.4")
        executor.lp_position_state.base_fee = Decimal("0.1")

        # received = 1.4 + 0.1 = 1.5, initial = 1.0, diff = 0.5
        diff = executor._calculate_net_base_difference()
        self.assertEqual(diff, Decimal("0.5"))

    def test_calculate_net_base_difference_negative(self):
        """Test _calculate_net_base_difference returns negative when lost base"""
        executor = self.get_executor()
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("0.4")
        executor.lp_position_state.base_fee = Decimal("0.1")

        # received = 0.4 + 0.1 = 0.5, initial = 1.0, diff = -0.5
        diff = executor._calculate_net_base_difference()
        self.assertEqual(diff, Decimal("-0.5"))

    def test_calculate_net_base_difference_zero(self):
        """Test _calculate_net_base_difference returns zero when balanced"""
        executor = self.get_executor()
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("0.9")
        executor.lp_position_state.base_fee = Decimal("0.1")

        # received = 0.9 + 0.1 = 1.0, initial = 1.0, diff = 0
        diff = executor._calculate_net_base_difference()
        self.assertEqual(diff, Decimal("0"))

    # Test for filled_amount_base property

    def test_filled_amount_base_returns_position_base(self):
        """Test filled_amount_base returns current base amount"""
        executor = self.get_executor()
        executor.lp_position_state.base_amount = Decimal("2.5")

        self.assertEqual(executor.filled_amount_base, Decimal("2.5"))

    # ------------------------------------------------------------------
    # keep_position matrix
    #
    # config.keep_position defaults to True, while hummingbot-api's /stop
    # defaults keep_position=False and forwards it to early_stop(). The two
    # therefore diverge routinely, so every downstream gate must follow the
    # runtime decision (close_type) rather than the config.
    # ------------------------------------------------------------------

    async def _open_and_close(
        self,
        config_keep_position: bool,
        stop_keep_position: bool,
        deposited_base: Decimal = Decimal("5.0"),
        deposited_quote: Decimal = Decimal("500.0"),
        withdrawn_base: Decimal = Decimal("5.0"),
        withdrawn_quote: Decimal = Decimal("500.0"),
    ) -> LPExecutor:
        """Drive open -> early_stop(...) -> close and hand back the executor."""
        config_dict = self.get_default_config().model_dump()
        config_dict["keep_position"] = config_keep_position
        config_dict["swap_provider"] = "jupiter/router"
        config_dict["base_amount"] = deposited_base
        config_dict["quote_amount"] = deposited_quote
        executor = self.get_executor(LPExecutorConfig(**config_dict))
        executor._get_native_to_quote_rate = MagicMock(return_value=Decimal("1"))

        connector = self.strategy.connectors["solana-mainnet-beta"]

        position_info = MagicMock()
        position_info.base_token_amount = float(deposited_base)
        position_info.quote_token_amount = float(deposited_quote)
        position_info.lower_price = 95.0
        position_info.upper_price = 105.0
        position_info.base_fee_amount = 0.0
        position_info.quote_fee_amount = 0.0
        position_info.price = 100.0
        connector.get_position_info = AsyncMock(return_value=position_info)
        connector._clmm_add_liquidity = AsyncMock(return_value="sig-add")
        connector._lp_orders_metadata = {"order-123": {"position_address": "pos123"}}
        connector._trigger_add_liquidity_event = MagicMock(
            return_value=create_mock_add_event(
                base_amount=deposited_base, quote_amount=deposited_quote
            )
        )
        await executor._create_position()

        executor.early_stop(keep_position=stop_keep_position)

        connector._clmm_close_position = AsyncMock(return_value="sig-remove")
        connector._lp_orders_metadata = {
            "order-123": {
                "base_amount": withdrawn_base,
                "quote_amount": withdrawn_quote,
                "base_fee": Decimal("0"),
                "quote_fee": Decimal("0"),
                "position_rent_refunded": Decimal("0.002"),
                "tx_fee": Decimal("0"),
            }
        }
        connector._trigger_remove_liquidity_event = MagicMock(
            return_value=create_mock_remove_event(
                base_amount=withdrawn_base,
                quote_amount=withdrawn_quote,
                base_fee=Decimal("0"),
                quote_fee=Decimal("0"),
                tx_fee=Decimal("0"),
            )
        )
        await executor._close_position()
        return executor

    async def test_matrix_config_hold_stop_hold_records_only_the_net(self):
        """config=True, stop=True: the hold is the round trip's net, not the deposit."""
        executor = await self._open_and_close(
            config_keep_position=True, stop_keep_position=True,
            deposited_base=Decimal("5.0"), withdrawn_base=Decimal("5.5"),
            deposited_quote=Decimal("500.0"), withdrawn_quote=Decimal("450.0"),
        )

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)
        orders = [o for o in executor._held_position_orders if o["executed_amount_base"]]
        self.assertEqual(len(orders), 1)
        # Gained 0.5 base, spent 50 quote -> a BUY of the net only.
        self.assertEqual(orders[0]["trade_type"], "BUY")
        self.assertEqual(orders[0]["executed_amount_base"], 0.5)

    async def test_matrix_config_unwind_stop_unwind_holds_nothing_and_swaps_net(self):
        """config=False, stop=False: no hold recorded, close-out swaps the net."""
        executor = await self._open_and_close(
            config_keep_position=False, stop_keep_position=False,
            deposited_base=Decimal("5.0"), withdrawn_base=Decimal("5.5"),
        )

        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.SWAPPING)
        self.assertEqual(executor._held_position_orders, [])
        self.assertEqual(executor._calculate_net_base_difference(), Decimal("0.5"))

    async def test_matrix_config_unwind_stop_hold_records_only_the_net(self):
        """config=False, stop=True: the ADD must still be on record.

        Regression: _store_lp_event_from_add used to be gated on
        config.keep_position, so a runtime keep_position=True found no deposit
        to net against and booked the ENTIRE withdrawn balance as a BUY --
        a hold for base the executor never acquired.
        """
        executor = await self._open_and_close(
            config_keep_position=False, stop_keep_position=True,
            deposited_base=Decimal("5.0"), withdrawn_base=Decimal("5.5"),
            deposited_quote=Decimal("500.0"), withdrawn_quote=Decimal("450.0"),
        )

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        orders = [o for o in executor._held_position_orders if o["executed_amount_base"]]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["trade_type"], "BUY")
        self.assertEqual(orders[0]["executed_amount_base"], 0.5)
        # No close-out swap: the caller asked to keep the net position.
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)

    async def test_matrix_config_hold_stop_unwind_swaps_and_records_nothing(self):
        """config=True, stop=False: the runtime decision wins.

        Regression: the close-out swap was gated on config.keep_position, so
        the API's default stop (keep_position=False) against a default config
        (keep_position=True) silently skipped the unwind AND still wrote a
        hold -- a position the caller had asked to be flat out of.
        """
        executor = await self._open_and_close(
            config_keep_position=True, stop_keep_position=False,
            deposited_base=Decimal("5.0"), withdrawn_base=Decimal("5.5"),
        )

        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.SWAPPING)
        self.assertEqual(executor._held_position_orders, [])

    async def test_matrix_limit_auto_close_follows_config(self):
        """The limit-price auto-close has no caller, so config.keep_position decides.

        Every other gate keys off close_type; this is the one place the config
        is still the source of truth, because nothing else has spoken.
        """
        config = self.get_default_config()
        config.upper_limit_price = Decimal("115")
        config.keep_position = False
        executor = self.get_executor(config)
        executor._status = RunnableStatus.RUNNING
        executor.lp_position_state.state = LPExecutorStates.OUT_OF_RANGE
        executor.lp_position_state.position_address = "pos123"

        mock_position = MagicMock()
        mock_position.base_token_amount = 1.0
        mock_position.quote_token_amount = 100.0
        mock_position.base_fee_amount = 0.0
        mock_position.quote_fee_amount = 0.0
        mock_position.lower_price = 95.0
        mock_position.upper_price = 105.0
        mock_position.price = 120.0
        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(return_value=mock_position)

        await executor.control_task()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)
        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)

    async def test_balanced_round_trip_still_reports_an_order(self):
        """A no-op round trip must report a zero order, not an empty list.

        An empty held_position_orders is indistinguishable from "this executor
        does not report orders", and consumers then fall back to
        filled_amount_base -- the pool balance, not acquired base.
        """
        executor = await self._open_and_close(
            config_keep_position=True, stop_keep_position=True,
            deposited_base=Decimal("5.0"), withdrawn_base=Decimal("5.0"),
            deposited_quote=Decimal("500.0"), withdrawn_quote=Decimal("500.0"),
        )

        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertEqual(executor._held_position_orders[0]["executed_amount_base"], 0.0)

    async def test_already_closed_position_records_the_net_hold(self):
        """A position closed on-chain behind our back still books its net hold."""
        config_dict = self.get_default_config().model_dump()
        config_dict["keep_position"] = True
        executor = self.get_executor(LPExecutorConfig(**config_dict))
        executor._get_native_to_quote_rate = MagicMock(return_value=Decimal("1"))
        executor.close_type = CloseType.POSITION_HOLD
        executor._current_price = Decimal("100")
        executor.lp_position_state.position_address = "pos123"
        executor.lp_position_state.base_amount = Decimal("5.5")
        executor.lp_position_state.quote_amount = Decimal("450.0")
        # The deposit is on record from the open.
        executor._add_base_amount = Decimal("5.0")
        executor._add_quote_amount = Decimal("500.0")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_position_info = AsyncMock(side_effect=Exception("Position closed: pos123"))
        connector._trigger_remove_liquidity_event = MagicMock()

        await executor._close_position()

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.COMPLETE)
        orders = [o for o in executor._held_position_orders if o["executed_amount_base"]]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["trade_type"], "BUY")
        self.assertEqual(orders[0]["executed_amount_base"], 0.5)

    @patch('hummingbot.strategy_v2.executors.lp_executor.lp_executor.GatewayHttpClient')
    async def test_closeout_resolves_swap_provider_lazily(self, mock_gateway_client):
        """A keep_position=True config unwound at runtime still finds a provider.

        on_start only resolves one when the config already expects to unwind, so
        the close-out path has to resolve it itself.
        """
        config_dict = self.get_default_config().model_dump()
        config_dict["keep_position"] = True
        config_dict["swap_provider"] = None
        executor = self.get_executor(LPExecutorConfig(**config_dict))
        executor.lp_position_state.initial_base_amount = Decimal("1.0")
        executor.lp_position_state.base_amount = Decimal("1.5")
        executor.lp_position_state.base_fee = Decimal("0")

        mock_gateway = MagicMock()
        mock_gateway.get_default_swap_provider = AsyncMock(return_value="jupiter/router")
        mock_gateway_client.get_instance.return_value = mock_gateway

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.place_order = MagicMock(return_value="swap-order-123")

        await executor._execute_closeout_swap()

        self.assertEqual(executor.config.swap_provider, "jupiter/router")
        connector.place_order.assert_called_once()
        self.assertEqual(connector.place_order.call_args[1]["amount"], Decimal("0.5"))

    async def test_forced_stop_mid_swapping_holds_only_the_net(self):
        """A forced stop mid-close-out records the net, not the whole balance.

        The deposited base is already carried by whoever funded the slot, so
        booking the full withdrawn balance here would double-count it.
        """
        executor = await self._open_and_close(
            config_keep_position=False, stop_keep_position=False,
            deposited_base=Decimal("5.0"), withdrawn_base=Decimal("5.5"),
            deposited_quote=Decimal("500.0"), withdrawn_quote=Decimal("450.0"),
        )
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.SWAPPING)

        held = executor._collect_held_position_orders()

        orders = [o for o in held if o["executed_amount_base"]]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["trade_type"], "BUY")
        self.assertEqual(orders[0]["executed_amount_base"], 0.5)
