"""The order executor's slippage ramp, which applies to Gateway swaps and nothing else.

A CEX order has a price and a book and nothing to be tolerant about. A Gateway order is a
swap against a pool, and it had no slippage setting at any executor level: the request
omitted slippagePct, so every attempt used the connector's configured value and every
retry sent the identical request.

The reason a failure can be told apart at all is that the connector now remembers what
Gateway said. The order tracker records FAILED and nothing else.
"""
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from hummingbot.connector.gateway.gateway import Gateway
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.event.events import MarketOrderFailureEvent
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.executors.order_executor.order_executor import OrderExecutor
from hummingbot.strategy_v2.models.executors import TrackedOrder


def a_config(**overrides) -> OrderExecutorConfig:
    fields = dict(
        id="test-order",
        timestamp=1234567890,
        trading_pair="SOL-USDC",
        connector_name="solana-mainnet-beta",
        side=TradeType.SELL,
        amount=Decimal("1"),
        execution_strategy=ExecutionStrategy.MARKET,
    )
    fields.update(overrides)
    return OrderExecutorConfig(**fields)


class TestTheRampIsGatewayOnly(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self, connector, config=None) -> OrderExecutor:
        # ExecutorBase takes its connectors from the strategy at construction, so the
        # strategy hands over the one under test.
        self.strategy.connectors = {"solana-mainnet-beta": connector}
        executor = OrderExecutor(self.strategy, config or a_config(), update_interval=1.0)
        executor._order = TrackedOrder(order_id="order-1")
        return executor

    @staticmethod
    def _failure(order_id="order-1"):
        return MarketOrderFailureEvent(timestamp=1234567890, order_id=order_id, order_type=OrderType.MARKET)

    def test_a_gateway_slippage_failure_widens_the_next_attempt(self):
        connector = MagicMock(spec=Gateway)
        connector.order_failure_reason.return_value = (
            "Gateway error: Price slippage check failed. [code: SLIPPAGE_EXCEEDED]"
        )
        executor = self.an_executor(connector)

        executor.process_order_failed_event(None, MagicMock(), self._failure())

        self.assertEqual(executor._slippage_pct, Decimal("0.25"))

    def test_any_other_gateway_failure_retries_at_the_same_tolerance(self):
        connector = MagicMock(spec=Gateway)
        connector.order_failure_reason.return_value = "Gateway error: insufficient balance"
        executor = self.an_executor(connector)

        executor.process_order_failed_event(None, MagicMock(), self._failure())

        self.assertEqual(executor._slippage_pct, Decimal("0.05"))

    def test_a_cex_connector_never_moves_the_ramp(self):
        # A plain connector remembers no reason, so there is nothing to widen on — which
        # is the correct behaviour rather than an accident: a CEX order was not refused
        # for slippage.
        connector = MagicMock(spec=[])
        executor = self.an_executor(connector)

        executor.process_order_failed_event(None, MagicMock(), self._failure())

        self.assertEqual(executor._slippage_pct, Decimal("0.05"))

    def test_it_stops_widening_at_the_ceiling(self):
        connector = MagicMock(spec=Gateway)
        connector.order_failure_reason.return_value = "[code: SLIPPAGE_EXCEEDED]"
        executor = self.an_executor(connector)
        executor._slippage_pct = Decimal("5")

        executor.process_order_failed_event(None, MagicMock(), self._failure())

        self.assertEqual(executor._slippage_pct, Decimal("5"))

    def test_a_gateway_order_carries_the_tolerance_to_the_connector(self):
        connector = MagicMock(spec=Gateway)
        connector.place_order.return_value = "order-1"
        executor = self.an_executor(connector)

        executor.place_open_order()

        _, kwargs = connector.place_order.call_args
        self.assertEqual(kwargs["slippage_pct"], 0.05)
        self.assertEqual(kwargs["trading_pair"], "SOL-USDC")
        self.assertIs(kwargs["is_buy"], False)

    def test_a_cex_order_is_placed_through_the_strategy_as_before(self):
        connector = MagicMock(spec=[])
        executor = self.an_executor(connector)
        executor.place_order = MagicMock(return_value="order-1")

        executor.place_open_order()

        executor.place_order.assert_called_once()
        self.assertEqual(
            executor.place_order.call_args.kwargs["position_action"], PositionAction.OPEN
        )


class TestConfigValidation(IsolatedAsyncioWrapperTestCase):
    def test_a_start_above_the_ceiling_is_rejected(self):
        with self.assertRaises(ValueError):
            a_config(slippage_pct=Decimal("10"), max_slippage_pct=Decimal("5"))

    def test_a_multiplier_that_never_widens_is_rejected(self):
        with self.assertRaises(ValueError):
            a_config(slippage_multiplier=Decimal("1"))
