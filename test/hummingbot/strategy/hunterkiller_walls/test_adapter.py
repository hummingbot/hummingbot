"""Run inside Hummingbot 2.17. Real config/order types, fixture market only."""
from collections import deque
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from pydantic import ValidationError
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, DeductedFromReturnsTradeFee, TokenAmount
from hummingbot.core.event.events import OrderFilledEvent

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from hk_strategy_core import LongPlan
from hk_wall_grid import HKWallGrid, HKWallGridConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hk_strategy_core import Timeline, parse_snapshot
from test_core import fixture, T


class FixtureConnector:
    def __init__(self):
        self.budget_checker = SimpleNamespace(adjust_candidates=lambda proposal, **kwargs: proposal)

    def get_price_by_type(self, pair, kind):
        return Decimal("100")

    def get_price(self, pair, is_buy):
        return Decimal("100.01") if is_buy else Decimal("99.99")

    def quantize_order_price(self, pair, price):
        return price.quantize(Decimal("0.01"))

    def quantize_order_amount(self, pair, amount):
        return amount.quantize(Decimal("0.000001"))


class TestHummingbotAdapter(unittest.TestCase):
    def test_native_config_is_paper_only_and_redacts_the_key(self):
        config = HKWallGridConfig(api_key="fixture-only")
        self.assertNotIn("fixture-only", repr(config))
        self.assertEqual(config.update_markets({}), {"binance_paper_trade": {"BTC-USDT"}})
        with self.assertRaises(ValidationError):
            HKWallGridConfig(exchange="binance")
        with self.assertRaises(ValidationError):
            HKWallGridConfig(trading_pair="ETH-USDT")

    def test_native_candidates_stay_passive_and_within_inventory(self):
        state = SimpleNamespace(config=HKWallGridConfig(), _inventory=Decimal("0.25"),
                                _plan=LongPlan(98, 103, 1),
                                connectors={"binance_paper_trade": FixtureConnector()})
        quotes = HKWallGrid.create_proposal(state, 100)
        self.assertEqual(len(quotes), 4)
        buys = [q for q in quotes if q.order_side == TradeType.BUY]
        sells = [q for q in quotes if q.order_side == TradeType.SELL]
        self.assertTrue(all(q.is_maker and q.order_type == OrderType.LIMIT for q in quotes))
        self.assertTrue(all(q.price < 100 for q in buys))
        self.assertTrue(all(q.price > 100 for q in sells))
        self.assertLessEqual(sum(q.amount for q in sells), Decimal("0.25"))

    def test_actual_fill_event_counts_only_own_orders_once(self):
        state = SimpleNamespace(_owned=deque(["owned"]), _fills=deque(maxlen=8192), _inventory=Decimal("0"))
        event = OrderFilledEvent(1, "owned", "BTC-USDT", TradeType.BUY, OrderType.LIMIT,
                                 Decimal("100"), Decimal("0.1"), AddedToCostTradeFee(),
                                 exchange_trade_id="fixture-fill")
        HKWallGrid.did_fill_order(state, event)
        HKWallGrid.did_fill_order(state, event)
        self.assertEqual(state._inventory, Decimal("0.1"))
        foreign = OrderFilledEvent(2, "foreign", "BTC-USDT", TradeType.BUY, OrderType.LIMIT,
                                   Decimal("100"), Decimal("1"), AddedToCostTradeFee(),
                                   exchange_trade_id="foreign-fill")
        HKWallGrid.did_fill_order(state, foreign)
        self.assertEqual(state._inventory, Decimal("0.1"))

    def test_base_fees_and_rounding_cannot_sell_foreign_inventory(self):
        state = SimpleNamespace(_owned=deque(["owned"]), _fills=deque(maxlen=8192), _inventory=Decimal("0"))
        event = OrderFilledEvent(1, "owned", "BTC-USDT", TradeType.BUY, OrderType.LIMIT,
                                 Decimal("100"), Decimal("0.1"),
                                 DeductedFromReturnsTradeFee(percent=Decimal("0.001"),
                                    flat_fees=[TokenAmount("BTC", Decimal("0.00001"))]),
                                 exchange_trade_id="fixture-fee")
        HKWallGrid.did_fill_order(state, event)
        self.assertEqual(state._inventory, Decimal("0.09989"))
        state.config = HKWallGridConfig()
        state._plan = LongPlan(98, 103, 1)
        state._inventory = Decimal("0.333333")
        state.connectors = {"binance_paper_trade": FixtureConnector()}
        quotes = HKWallGrid.create_proposal(state, 100)
        self.assertLessEqual(sum(q.amount for q in quotes if q.order_side == TradeType.SELL), state._inventory)
        self.assertLessEqual(sum(q.amount * q.price for q in quotes if q.order_side == TradeType.BUY),
                             Decimal("100") - state._inventory * 100)

    def test_stop_intent_survives_cancellation_and_price_reentry(self):
        calls = []
        state = SimpleNamespace(current_timestamp=1000, _feed=SimpleNamespace(next_poll=2000,
            timeline=SimpleNamespace(at=lambda now: object())), _refresh_task=None,
            config=HKWallGridConfig(), connectors={"binance_paper_trade": SimpleNamespace(
                get_price_by_type=lambda *a: Decimal("100"))}, _flatten_order=None, _closing=True,
            _inventory=Decimal("0.1"), _active_orders=lambda: [], _flatten=lambda orders: calls.append("close"))
        HKWallGrid.on_tick(state)
        self.assertEqual(calls, ["close"])
        self.assertTrue(state._closing)


class TestHummingbotLifecycle(unittest.IsolatedAsyncioTestCase):
    def make_strategy(self, inventory="0"):
        # Only native framework lifecycle setup is isolated. All script state,
        # input selection, quote generation and callbacks execute unchanged.
        with patch.object(StrategyV2Base, "__init__", return_value=None):
            strategy = HKWallGrid({}, HKWallGridConfig())
        self.tick = patch.object(HKWallGrid, "current_timestamp", new_callable=PropertyMock, return_value=T)
        self.clock = self.tick.start()
        self.addCleanup(self.tick.stop)
        strategy.connectors = {"binance_paper_trade": FixtureConnector()}
        timeline = Timeline()
        timeline.append(T, parse_snapshot(fixture(), T, "BTCUSDT"))
        strategy._feed = SimpleNamespace(next_poll=T + 60, timeline=timeline, last_error=None, poll=Mock())
        strategy.get_active_orders = Mock(return_value=[])
        strategy.buy = Mock(side_effect=["buy1", "buy2", "buy3", "buy4"])
        strategy.sell = Mock(side_effect=["sell1", "sell2", "sell3", "sell4"])
        strategy.cancel = Mock()
        strategy._inventory = Decimal(inventory)
        if strategy._inventory:
            strategy._plan = LongPlan(98, 103, T)
            strategy._plan_started_at = T
        return strategy

    async def test_tick_quotes_once_then_cancels_before_replacement(self):
        strategy = self.make_strategy()
        strategy.on_tick()
        first_count = strategy.buy.call_count
        self.assertGreater(first_count, 0)
        self.assertLessEqual(first_count, 2)
        strategy.on_tick()
        self.assertEqual(strategy.buy.call_count, first_count)
        strategy.get_active_orders.return_value = [SimpleNamespace(client_order_id="buy1")]
        self.clock.return_value = T + 31
        strategy.on_tick()
        strategy.cancel.assert_called_once_with("binance_paper_trade", "BTC-USDT", "buy1")
        self.assertEqual(strategy.buy.call_count, first_count)

    async def test_tick_quotes_asks_only_from_own_inventory(self):
        strategy = self.make_strategy("0.25")
        strategy.on_tick()
        self.assertGreater(strategy.sell.call_count, 0)
        sold = sum(call.args[2] for call in strategy.sell.call_args_list)
        self.assertLessEqual(sold, Decimal("0.25"))
        self.assertNotIn("api_key", strategy.format_status())

    async def test_feed_gap_cancels_then_closes_and_does_not_reopen(self):
        strategy = self.make_strategy("0.1")
        strategy._owned.append("owned")
        strategy._feed.timeline.clear()
        strategy.get_active_orders.return_value = [SimpleNamespace(client_order_id="owned")]
        strategy.on_tick()
        self.assertTrue(strategy._closing)
        strategy.sell.assert_not_called()
        strategy.get_active_orders.return_value = []
        strategy.on_tick()
        self.assertEqual(strategy.sell.call_args.args[3], OrderType.MARKET)
        event = OrderFilledEvent(T, "sell1", "BTC-USDT", TradeType.SELL, OrderType.MARKET,
                                 Decimal("100"), Decimal("0.1"), AddedToCostTradeFee(), exchange_trade_id="close1")
        strategy.did_fill_order(event)
        strategy.did_complete_sell_order(SimpleNamespace(order_id="sell1"))
        strategy.on_tick()
        self.assertEqual(strategy._inventory, 0)
        self.assertIsNone(strategy._plan)
        strategy.buy.assert_not_called()

    async def test_holding_limit_closes_the_paper_inventory(self):
        strategy = self.make_strategy("0.1")
        strategy._plan_started_at = T - 86400
        strategy.on_tick()
        self.assertTrue(strategy._closing)
        self.assertEqual(strategy.sell.call_args.args[3], OrderType.MARKET)

    async def test_failed_close_obeys_backoff(self):
        strategy = self.make_strategy("0.1")
        strategy._closing = True
        strategy.on_tick()
        strategy.did_fail_order(SimpleNamespace(order_id="sell1"))
        strategy.on_tick()
        self.assertEqual(strategy.sell.call_count, 1)
        self.clock.return_value = T + 61
        strategy.on_tick()
        self.assertEqual(strategy.sell.call_count, 2)

    async def test_refresh_runs_once_off_the_tick_thread(self):
        strategy = self.make_strategy()
        strategy._feed.next_poll = T - 1
        strategy.on_tick()
        await strategy._refresh_task
        strategy._feed.poll.assert_called_once_with(T)

    async def test_stop_cancels_own_quotes_and_pending_refresh(self):
        import asyncio
        strategy = self.make_strategy()
        strategy._owned.append("owned")
        strategy.get_active_orders.return_value = [SimpleNamespace(client_order_id="owned")]
        pending = asyncio.get_running_loop().create_future()
        strategy._refresh_task = pending
        with patch.object(StrategyV2Base, "on_stop", new_callable=AsyncMock) as stop:
            await strategy.on_stop()
            stop.assert_awaited_once()
        self.assertTrue(pending.cancelled())
        strategy.cancel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
