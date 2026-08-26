"""An order executor's Gateway swap has to be findable and its tolerance visible.

GW-40 gave OrderExecutorConfig the three slippage fields and they work — a MARKET BUY and
SELL both went out at slippage_pct 0.05 and landed. But custom_info reported neither the
live tolerance nor the transaction, so:

- a widening left no trace. lp_executor exposes its live slippage_pct for exactly this
  reason: a value above the configured start is the only evidence that earlier attempts
  failed and this one is paying to get through.
- the trade could not be linked to the chain. order_id is internal
  (buy-SOL-USDC-1787271213996599) and appears nowhere on chain, so confirming what two
  real swaps did meant querying the wallet's recent signatures and matching by timestamp.

The hash is also what a swap record has to be keyed on, which is why GW-42 could not be
fixed before this.
"""
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from hummingbot.core.data_type.common import PositionAction, TradeType
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.executors.order_executor.order_executor import OrderExecutor

SIGNATURE = "5xLmQ5s5xZ9jTqk3Y8bNvW2pR7cH4dF6gJ1kM3nP9qS8tU4vX6yZ2aB5cD7eF9gH1jK3lM5nP7qR9sT"


def a_config(**overrides) -> OrderExecutorConfig:
    fields = dict(
        id="test-observability",
        timestamp=1234567890,
        connector_name="solana-mainnet-beta",
        trading_pair="SOL-USDC",
        side=TradeType.BUY,
        amount=Decimal("0.01"),
        execution_strategy=ExecutionStrategy.MARKET,
        position_action=PositionAction.OPEN,
    )
    fields.update(overrides)
    return OrderExecutorConfig(**fields)


class TestCustomInfo(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self, config=None, exchange_order_id=SIGNATURE,
                    swap_provider="jupiter/router", wallet="82Sgg", with_order=True):
        executor = OrderExecutor(self.strategy, config or a_config(), update_interval=1.0)
        connector = MagicMock(swap_provider=swap_provider, address=wallet)
        executor.connectors = {"solana-mainnet-beta": connector}
        if with_order:
            order = MagicMock()
            order.order = MagicMock(exchange_order_id=exchange_order_id)
            order.order_id = "buy-SOL-USDC-1787271213996599"
            order.last_update_timestamp = 1234567890
            # A real filled swap: the amounts the two live 2026-08-21 SOL-USDC legs moved.
            order.executed_amount_base = Decimal("0.01")
            order.average_executed_price = Decimal("87.8444")
            executor._order = order
        else:
            executor._order = None
        return executor

    def test_the_transaction_hash_is_reported(self):
        info = self.an_executor().get_custom_info()

        self.assertEqual(info["transaction_hash"], SIGNATURE)

    def test_the_internal_order_id_is_not_the_transaction(self):
        """They were being conflated, and only one of them exists on chain."""
        info = self.an_executor().get_custom_info()

        self.assertNotEqual(info["transaction_hash"], info["order_id"])

    def test_no_order_yet_means_no_hash_rather_than_an_error(self):
        info = self.an_executor(with_order=False).get_custom_info()

        self.assertIsNone(info["transaction_hash"])

    def test_the_live_tolerance_is_reported_not_the_configured_one(self):
        """The whole point: after a widening these two differ, and the live one is the
        fact that explains what the swap paid."""
        executor = self.an_executor()
        executor._slippage_pct = Decimal("1.25")

        info = executor.get_custom_info()

        self.assertEqual(info["slippage_pct"], Decimal("1.25"))
        self.assertNotEqual(info["slippage_pct"], executor.config.slippage_pct)

    def test_the_ceiling_is_reported_so_a_reader_knows_how_far_it_could_go(self):
        info = self.an_executor().get_custom_info()

        self.assertEqual(info["max_slippage_pct"], Decimal("5"))

    def test_it_names_the_dex_that_executed_the_swap(self):
        """connector_name is the NETWORK. The DEX comes from that network's configured
        swapProvider, resolved inside the connector, so nothing else can observe it."""
        info = self.an_executor().get_custom_info()

        self.assertEqual(info["swap_provider"], "jupiter/router")
        self.assertNotEqual(info["swap_provider"], info["side"])

    def test_it_names_the_wallet_that_paid(self):
        info = self.an_executor().get_custom_info()

        self.assertEqual(info["wallet_address"], "82Sgg")

    def test_a_non_gateway_connector_reports_neither_rather_than_inventing_them(self):
        """A CEX connector has no swap provider and no wallet address; None says so."""
        executor = self.an_executor()
        executor.connectors = {"solana-mainnet-beta": object()}

        info = executor.get_custom_info()

        self.assertIsNone(info["swap_provider"])
        self.assertIsNone(info["wallet_address"])
