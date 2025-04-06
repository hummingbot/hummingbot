from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.models.base import RunnableStatus


class TestExecutorBase(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self):
        self.strategy = self.create_mock_strategy
        self.config = ExecutorConfigBase(id="test", type="test", timestamp=1234567890)
        self.component = ExecutorBase(strategy=self.strategy, connectors=["connector1"], config=self.config,
                                      update_interval=0.5)

    @property
    def create_mock_strategy(self):
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=ScriptStrategyBase)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        connector = MagicMock(spec=ExchangePyBase)
        connector.get_price_by_type.return_value = Decimal("1000.0")
        connector.get_order_book.return_value = OrderBook()
        connector.get_balance.return_value = Decimal("0.0")
        connector.get_available_balance.return_value = Decimal("0.0")
        connector._order_tracker = MagicMock(spec=ClientOrderTracker)
        connector._order_tracker.fetch_order.return_value = None
        strategy.connectors = {
            "connector1": connector,
        }
        return strategy

    def test_process_order_completed_event(self):
        event_tag = 1
        market = MagicMock()
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=Decimal("1.0"),
            quote_asset_amount=Decimal("1.0") * Decimal("1000.0"),
            order_type=OrderType.LIMIT,
            exchange_order_id="ED140"
        )
        self.component.process_order_completed_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_completed_event(event_tag, market, event))

    def test_process_order_created_event(self):
        event_tag = 1
        market = MagicMock()
        event = BuyOrderCreatedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            trading_pair="ETH-USDT",
            amount=Decimal("1.0"),
            type=OrderType.LIMIT,
            price=Decimal("1000.0"),
            exchange_order_id="ED140",
            creation_timestamp=1234567890
        )
        self.component.process_order_created_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_created_event(event_tag, market, event))

    def test_process_order_canceled_event(self):
        event_tag = 1
        market = MagicMock()
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            exchange_order_id="ED140",
        )
        self.component.process_order_canceled_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_canceled_event(event_tag, market, event))

    def test_process_order_filled_event(self):
        event_tag = 1
        market = MagicMock()
        event = OrderFilledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            exchange_order_id="ED140",
            trading_pair="ETH-USDT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("1000.0"),
            amount=Decimal("1.0"),
            trade_fee=AddedToCostTradeFee(percent=Decimal("0.001")),
        )
        self.component.process_order_filled_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_filled_event(event_tag, market, event))

    def test_process_order_failed_event(self):
        event_tag = 1
        market = MagicMock()
        event = MarketOrderFailureEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            order_type=OrderType.LIMIT,
        )
        self.component.process_order_failed_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_failed_event(event_tag, market, event))

    def test_place_buy_order(self):
        buy_order_id = self.component.place_order(
            connector_name="connector1",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            side=TradeType.BUY,
            price=Decimal("1000.0"),
            amount=Decimal("1.0"),
        )
        self.assertEqual(buy_order_id, "OID-BUY-1")

    def test_place_sell_order(self):
        sell_order_id = self.component.place_order(
            connector_name="connector1",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            side=TradeType.SELL,
            price=Decimal("1000.0"),
            amount=Decimal("1.0"),
        )
        self.assertEqual(sell_order_id, "OID-SELL-1")

    async def test_executor_starts_and_stops(self):
        self.assertEqual(RunnableStatus.NOT_STARTED, self.component.status)
        self.component.start()
        self.assertEqual(RunnableStatus.RUNNING, self.component.status)
        self.component.stop()
        self.assertEqual(RunnableStatus.TERMINATED, self.component.status)

    @patch.object(ExecutorBase, "get_net_pnl_pct")
    @patch.object(ExecutorBase, "get_net_pnl_quote")
    @patch.object(ExecutorBase, "get_cum_fees_quote")
    async def test_executor_info(self, net_pnl_pct_mock, net_pnl_quote_mock, cum_fees_quote_mock):
        net_pnl_pct_mock.return_value = Decimal("0.01")
        net_pnl_quote_mock.return_value = Decimal("1.0")
        cum_fees_quote_mock.return_value = Decimal("0.1")
        executor_info = self.component.executor_info
        self.assertEqual(executor_info.id, "test")

    def test_get_price_by_type(self):
        price = self.component.get_price("connector1", "EHT-USDT", PriceType.MidPrice)
        self.assertEqual(price, Decimal("1000.0"))

    def test_get_order_book(self):
        order_book = self.component.get_order_book("connector1", "ETH-USDT")
        self.assertEqual(order_book.last_diff_uid, 0)

    def test_get_total_and_available_balance(self):
        balance = self.component.get_balance("connector1", "ETH")
        self.assertEqual(balance, Decimal("0.0"))
        available_balance = self.component.get_available_balance("connector1", "ETH")
        self.assertEqual(available_balance, Decimal("0.0"))

    def test_get_in_flight_order(self):
        in_flight_orders = self.component.get_in_flight_order("connector1", "OID-BUY-1")
        self.assertEqual(in_flight_orders, None)
