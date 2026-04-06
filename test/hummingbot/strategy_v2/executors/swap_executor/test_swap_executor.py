from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.connector.gateway.gateway import Gateway
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
)
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.swap_executor.data_types import SwapExecutorConfig, SwapExecutorStates
from hummingbot.strategy_v2.executors.swap_executor.swap_executor import SwapExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


class TestSwapExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
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

        # Create mock Gateway connector (network-based)
        connector = MagicMock(spec=Gateway)
        connector.place_order = MagicMock(return_value="OID-SWAP-1")
        connector.get_order = MagicMock(return_value=None)
        connector.get_quote_price = AsyncMock(return_value=Decimal("100"))

        strategy.connectors = {
            "solana-mainnet-beta": connector,
        }
        return strategy

    def get_swap_executor_from_config(self, config: SwapExecutorConfig):
        executor = SwapExecutor(self.strategy, config, self.update_interval)
        self.set_loggers(loggers=[executor.logger()])
        return executor

    def test_executor_initialization(self):
        """Test executor initialization."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        self.assertEqual(executor._state, SwapExecutorStates.NOT_STARTED)
        self.assertEqual(executor._executed_amount, Decimal("0"))
        self.assertEqual(executor._executed_price, Decimal("0"))
        self.assertEqual(executor._tx_fee, Decimal("0"))

    def test_get_connector(self):
        """Test connector retrieval."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        connector = executor._get_connector()
        self.assertIsNotNone(connector)

    def test_get_connector_not_found(self):
        """Test connector retrieval when not found."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="nonexistent-network",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        connector = executor._get_connector()
        self.assertIsNone(connector)

    @patch.object(SwapExecutor, "_execute_swap", new_callable=AsyncMock)
    async def test_control_task_not_started(self, mock_execute_swap):
        """Test control task transitions from NOT_STARTED to EXECUTING."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        await executor.control_task()

        self.assertEqual(executor._state, SwapExecutorStates.EXECUTING)
        mock_execute_swap.assert_called_once()

    @patch.object(SwapExecutor, "_check_order_status", new_callable=AsyncMock)
    async def test_control_task_executing_with_order(self, mock_check_order_status):
        """Test control task monitors order when EXECUTING."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._state = SwapExecutorStates.EXECUTING
        executor._order_id = "OID-123"

        await executor.control_task()

        mock_check_order_status.assert_called_once()

    async def test_control_task_completed(self):
        """Test control task handles COMPLETED state with POSITION_HOLD."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._state = SwapExecutorStates.COMPLETED
        executor._executed_amount = Decimal("1.0")
        executor._executed_price = Decimal("100.0")
        executor._order_id = "swap-order-123"
        executor._exchange_order_id = "exchange-swap-123"
        executor.stop = MagicMock()

        await executor.control_task()

        # Swaps complete with POSITION_HOLD to enable position tracking
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        executor.stop.assert_called_once()
        # Verify held position was stored
        self.assertEqual(len(executor._held_position_orders), 1)
        held_order = executor._held_position_orders[0]
        self.assertEqual(held_order["trade_type"], "BUY")
        self.assertEqual(held_order["executed_amount_base"], 1.0)
        # Verify client_order_id for PositionHold deduplication
        self.assertIsNotNone(held_order.get("client_order_id"))
        self.assertEqual(held_order["client_order_id"], held_order["order_id"])

    async def test_control_task_failed(self):
        """Test control task handles FAILED state."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._state = SwapExecutorStates.FAILED
        executor.stop = MagicMock()

        await executor.control_task()

        self.assertEqual(executor.close_type, CloseType.FAILED)
        executor.stop.assert_called_once()

    @patch("hummingbot.strategy_v2.executors.swap_executor.swap_executor.GatewayHttpClient")
    async def test_execute_swap_no_connector(self, mock_gateway_client):
        """Test execute_swap fails when connector not found."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="nonexistent-network",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        await executor._execute_swap()

        self.assertEqual(executor._state, SwapExecutorStates.FAILED)

    @patch("hummingbot.strategy_v2.executors.swap_executor.swap_executor.GatewayHttpClient")
    async def test_execute_swap_success(self, mock_gateway_client):
        """Test successful swap execution."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        mock_gateway = MagicMock()
        mock_gateway_client.get_instance.return_value = mock_gateway

        await executor._execute_swap()

        self.assertEqual(executor._order_id, "OID-SWAP-1")
        self.assertEqual(executor._selected_provider, "jupiter/router")

    @patch("hummingbot.strategy_v2.executors.swap_executor.swap_executor.GatewayHttpClient")
    async def test_execute_swap_with_multiple_providers(self, mock_gateway_client):
        """Test swap execution with multiple providers."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
            additional_swap_providers=["raydium/clmm"],
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        mock_gateway = MagicMock()
        mock_gateway.quote_swap = AsyncMock(return_value={
            "price": "100",
            "amountIn": "1",
            "amountOut": "100",
        })
        mock_gateway.get_pool = AsyncMock(return_value={"address": "0xpool123"})
        mock_gateway_client.get_instance.return_value = mock_gateway

        await executor._execute_swap()

        self.assertEqual(executor._order_id, "OID-SWAP-1")

    @patch("hummingbot.strategy_v2.executors.swap_executor.swap_executor.GatewayHttpClient")
    async def test_execute_swap_no_valid_quotes(self, mock_gateway_client):
        """Test swap execution fails when no valid quotes."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
            additional_swap_providers=["raydium/clmm"],
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        mock_gateway = MagicMock()
        mock_gateway.quote_swap = AsyncMock(side_effect=Exception("API Error"))
        mock_gateway.get_pool = AsyncMock(return_value={"address": "0xpool123"})
        mock_gateway_client.get_instance.return_value = mock_gateway

        await executor._execute_swap()

        self.assertEqual(executor._state, SwapExecutorStates.FAILED)

    async def test_check_order_status_order_filled(self):
        """Test order status check when order is filled."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._order_id = "OID-123"

        # Create a filled order
        order = MagicMock()
        order.current_state = OrderState.FILLED
        order.exchange_order_id = "TX-HASH-123"
        order.executed_amount_base = Decimal("1.0")
        order.amount = Decimal("1.0")
        order.average_executed_price = Decimal("100")
        order.price = Decimal("100")
        order.fee_paid = Decimal("0.001")

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_order.return_value = order

        await executor._check_order_status()

        self.assertEqual(executor._state, SwapExecutorStates.COMPLETED)
        self.assertEqual(executor._exchange_order_id, "TX-HASH-123")
        self.assertEqual(executor._executed_amount, Decimal("1.0"))
        self.assertEqual(executor._executed_price, Decimal("100"))
        self.assertEqual(executor._tx_fee, Decimal("0.001"))

    async def test_check_order_status_order_failed(self):
        """Test order status check when order fails."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._order_id = "OID-123"

        order = MagicMock()
        order.current_state = OrderState.FAILED

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_order.return_value = order

        await executor._check_order_status()

        self.assertEqual(executor._state, SwapExecutorStates.FAILED)

    async def test_check_order_status_order_canceled(self):
        """Test order status check when order is canceled."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._order_id = "OID-123"

        order = MagicMock()
        order.current_state = OrderState.CANCELED

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_order.return_value = order

        await executor._check_order_status()

        self.assertEqual(executor._state, SwapExecutorStates.FAILED)

    async def test_check_order_status_no_order(self):
        """Test order status check when order not found."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._order_id = "OID-123"

        connector = self.strategy.connectors["solana-mainnet-beta"]
        connector.get_order.return_value = None

        # Should not crash
        await executor._check_order_status()

    def test_process_order_filled_event(self):
        """Test processing order filled event."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._order_id = "OID-123"

        # Create a mock trade_fee with flat_fees
        trade_fee = MagicMock()
        trade_fee.flat_fees = [TokenAmount(amount=Decimal("0.001"), token="SOL")]

        event = OrderFilledEvent(
            timestamp=123,
            order_id="OID-123",
            trading_pair="SOL-USDC",
            trade_type=TradeType.BUY,
            order_type=None,
            price=Decimal("100"),
            amount=Decimal("1.0"),
            trade_fee=trade_fee,
            exchange_trade_id="TX-123",
        )

        connector = self.strategy.connectors["solana-mainnet-beta"]
        executor.process_order_filled_event(1, connector, event)

        self.assertEqual(executor._exchange_order_id, "TX-123")
        self.assertEqual(executor._executed_amount, Decimal("1.0"))
        self.assertEqual(executor._executed_price, Decimal("100"))
        self.assertEqual(executor._tx_fee, Decimal("0.001"))

    def test_process_order_filled_event_wrong_order(self):
        """Test processing order filled event for wrong order ID."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._order_id = "OID-123"

        event = OrderFilledEvent(
            timestamp=123,
            order_id="DIFFERENT-ORDER",
            trading_pair="SOL-USDC",
            trade_type=TradeType.BUY,
            order_type=None,
            price=Decimal("100"),
            amount=Decimal("1.0"),
            trade_fee=None,
            exchange_trade_id="TX-123",
        )

        connector = self.strategy.connectors["solana-mainnet-beta"]
        executor.process_order_filled_event(1, connector, event)

        # Should not update anything
        self.assertEqual(executor._executed_amount, Decimal("0"))

    def test_process_order_completed_event_buy(self):
        """Test processing buy order completed event."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._order_id = "OID-123"
        executor._state = SwapExecutorStates.EXECUTING

        event = BuyOrderCompletedEvent(
            timestamp=123,
            order_id="OID-123",
            base_asset="SOL",
            quote_asset="USDC",
            base_asset_amount=Decimal("1.0"),
            quote_asset_amount=Decimal("100"),
            order_type=None,
            exchange_order_id="TX-123",
        )

        connector = self.strategy.connectors["solana-mainnet-beta"]
        executor.process_order_completed_event(1, connector, event)

        self.assertEqual(executor._state, SwapExecutorStates.COMPLETED)

    def test_process_order_completed_event_sell(self):
        """Test processing sell order completed event."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.SELL,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._order_id = "OID-123"
        executor._state = SwapExecutorStates.EXECUTING

        event = SellOrderCompletedEvent(
            timestamp=123,
            order_id="OID-123",
            base_asset="SOL",
            quote_asset="USDC",
            base_asset_amount=Decimal("1.0"),
            quote_asset_amount=Decimal("100"),
            order_type=None,
            exchange_order_id="TX-123",
        )

        connector = self.strategy.connectors["solana-mainnet-beta"]
        executor.process_order_completed_event(1, connector, event)

        self.assertEqual(executor._state, SwapExecutorStates.COMPLETED)

    def test_process_order_failed_event(self):
        """Test processing order failed event."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._order_id = "OID-123"
        executor._state = SwapExecutorStates.EXECUTING

        event = MarketOrderFailureEvent(
            timestamp=123,
            order_id="OID-123",
            order_type=None,
        )

        connector = self.strategy.connectors["solana-mainnet-beta"]
        executor.process_order_failed_event(1, connector, event)

        self.assertEqual(executor._state, SwapExecutorStates.FAILED)

    def test_early_stop(self):
        """Test early stop functionality."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._state = SwapExecutorStates.EXECUTING
        executor.stop = MagicMock()

        executor.early_stop()

        self.assertEqual(executor.close_type, CloseType.EARLY_STOP)
        self.assertEqual(executor._state, SwapExecutorStates.FAILED)
        executor.stop.assert_called_once()

    def test_early_stop_already_completed(self):
        """Test early stop when already completed does nothing."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._state = SwapExecutorStates.COMPLETED
        executor.stop = MagicMock()

        executor.early_stop()

        # Should not call stop when already completed
        executor.stop.assert_not_called()

    def test_filled_amount_quote(self):
        """Test filled amount quote calculation."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._executed_amount = Decimal("2.0")
        executor._executed_price = Decimal("50")

        self.assertEqual(executor.filled_amount_quote, Decimal("100"))

    def test_get_net_pnl_quote(self):
        """Test net PnL calculation (always 0 for swaps)."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))

    def test_get_net_pnl_pct(self):
        """Test net PnL percentage (always 0 for swaps)."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        self.assertEqual(executor.get_net_pnl_pct(), Decimal("0"))

    def test_get_cum_fees_quote(self):
        """Test cumulative fees calculation."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._tx_fee = Decimal("0.005")

        self.assertEqual(executor.get_cum_fees_quote(), Decimal("0.005"))

    async def test_validate_sufficient_balance(self):
        """Test validate sufficient balance (pass-through for Gateway)."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        # Should not raise
        await executor.validate_sufficient_balance()

    def test_get_custom_info(self):
        """Test custom info retrieval."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._state = SwapExecutorStates.EXECUTING
        executor._order_id = "OID-123"
        executor._exchange_order_id = "TX-123"
        executor._executed_amount = Decimal("1.0")
        executor._executed_price = Decimal("100")
        executor._tx_fee = Decimal("0.001")
        executor._selected_provider = "jupiter/router"

        custom_info = executor.get_custom_info()

        self.assertEqual(custom_info["state"], "EXECUTING")
        self.assertEqual(custom_info["connector_name"], "solana-mainnet-beta")
        self.assertEqual(custom_info["side"], "BUY")
        self.assertEqual(custom_info["amount"], 1.0)
        self.assertEqual(custom_info["executed_amount"], 1.0)
        self.assertEqual(custom_info["executed_price"], 100.0)
        self.assertEqual(custom_info["tx_fee"], 0.001)
        self.assertEqual(custom_info["order_id"], "OID-123")
        self.assertEqual(custom_info["tx_hash"], "TX-123")
        self.assertEqual(custom_info["swap_provider"], "jupiter/router")

    def test_select_best_quote_buy(self):
        """Test best quote selection for BUY (lower price is better)."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        quotes = [
            {"provider": "jupiter", "quote": {"price": "100"}, "pool_address": None},
            {"provider": "raydium", "quote": {"price": "95"}, "pool_address": None},
            {"provider": "orca", "quote": {"price": "105"}, "pool_address": None},
        ]

        best = executor._select_best_quote(quotes)
        self.assertEqual(best["provider"], "raydium")

    def test_select_best_quote_sell(self):
        """Test best quote selection for SELL (higher price is better)."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.SELL,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        quotes = [
            {"provider": "jupiter", "quote": {"price": "100"}, "pool_address": None},
            {"provider": "raydium", "quote": {"price": "95"}, "pool_address": None},
            {"provider": "orca", "quote": {"price": "105"}, "pool_address": None},
        ]

        best = executor._select_best_quote(quotes)
        self.assertEqual(best["provider"], "orca")

    def test_select_best_quote_empty(self):
        """Test best quote selection with empty list."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        best = executor._select_best_quote([])
        self.assertIsNone(best)

    @patch("hummingbot.strategy_v2.executors.swap_executor.swap_executor.GatewayHttpClient")
    async def test_fetch_quotes(self, mock_gateway_client):
        """Test fetching quotes from multiple providers."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        mock_gateway = MagicMock()
        mock_gateway.quote_swap = AsyncMock(return_value={
            "price": "100",
            "amountIn": "1",
            "amountOut": "100",
        })
        mock_gateway.get_pool = AsyncMock(return_value={"address": "0xpool123"})

        quotes = await executor._fetch_quotes(
            mock_gateway,
            "SOL",
            "USDC",
            Decimal("1.0"),
            ["jupiter/router", "raydium/clmm"]
        )

        self.assertEqual(len(quotes), 2)

    @patch("hummingbot.strategy_v2.executors.swap_executor.swap_executor.GatewayHttpClient")
    async def test_get_pool_address_for_provider_router(self, mock_gateway_client):
        """Test pool address lookup for router provider (returns None)."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        mock_gateway = MagicMock()

        pool_address = await executor._get_pool_address_for_provider(mock_gateway, "jupiter/router")
        self.assertIsNone(pool_address)

    @patch("hummingbot.strategy_v2.executors.swap_executor.swap_executor.GatewayHttpClient")
    async def test_get_pool_address_for_provider_clmm(self, mock_gateway_client):
        """Test pool address lookup for CLMM provider."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        mock_gateway = MagicMock()
        mock_gateway.get_pool = AsyncMock(return_value={"address": "0xpool123"})

        pool_address = await executor._get_pool_address_for_provider(mock_gateway, "raydium/clmm")
        self.assertEqual(pool_address, "0xpool123")

    # Connector validation tests

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_CONNECTORS", {"jupiter/router", "orca/router"})
    async def test_on_start_normalizes_connector_auto_append_router(self):
        """Test on_start auto-appends /router to swap_provider."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter",  # No /router suffix
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        await executor.on_start()

        # Swap provider should be normalized to include /router
        self.assertEqual(executor.config.swap_provider, "jupiter/router")

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_CONNECTORS", {"jupiter/router", "orca/router"})
    async def test_on_start_keeps_existing_router_suffix(self):
        """Test on_start keeps existing /router suffix on swap_provider."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="jupiter/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)

        await executor.on_start()

        self.assertEqual(executor.config.swap_provider, "jupiter/router")

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_CONNECTORS", {"meteora/clmm"})
    async def test_on_start_fails_wrong_connector_type(self):
        """Test on_start fails when swap_provider has CLMM type (not router)."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="meteora/clmm",  # CLMM instead of router
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        await executor.on_start()

        self.assertEqual(executor.close_type, CloseType.FAILED)

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_CONNECTORS", {"orca/router"})
    async def test_on_start_fails_connector_not_found(self):
        """Test on_start fails when swap_provider is not found in Gateway."""
        config = SwapExecutorConfig(
            id="test-swap",
            timestamp=123,
            connector_name="solana-mainnet-beta",
            swap_provider="nonexistent/router",
            trading_pair="SOL-USDC",
            side=TradeType.BUY,
            amount=Decimal("1.0"),
        )
        executor = self.get_swap_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        await executor.on_start()

        self.assertEqual(executor.close_type, CloseType.FAILED)
