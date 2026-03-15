import time
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, PropertyMock, patch

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketEvent, OrderFilledEvent, SellOrderCreatedEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class ExtendedMockPaperExchange(MockPaperExchange):

    def __init__(self, client_config_map: "ClientConfigAdapter"):
        super().__init__(client_config_map)

        self._order_tracker = ClientOrderTracker(self)
        self._trading_rules = {}

    @property
    def in_flight_orders(self) -> dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    def get_in_flight_order(self, client_order_id: str) -> InFlightOrder | None:
        return self._order_tracker.fetch_tracked_order(client_order_id)

    @property
    def trading_rules(self) -> dict[str, TradingRule]:
        return self._trading_rules

    def set_trading_rules(self, trading_rules: dict[str, TradingRule]):
        self._trading_rules = trading_rules


class MockStrategyV2Config(StrategyV2ConfigBase):
    """
    Configuration for test strategy.

    :ivar markets: Dictionary mapping connector names to sets of trading pairs
    """
    markets: dict[str, set[str]]

    class Config:
        title = "test_strategy"


class MockStrategyV2(StrategyV2Base):
    """
    A minimal strategy implementation for testing purposes.
    """

    @classmethod
    def init_markets(cls, config: MockStrategyV2Config):
        """Initialize markets from config."""
        cls.markets = config.markets

    def create_actions_proposal(self) -> list[CreateExecutorAction]:
        return MagicMock(return_value=[MagicMock(spec=CreateExecutorAction)])

    def stop_actions_proposal(self) -> list[ExecutorAction]:
        return MagicMock(return_value=[MagicMock(spec=ExecutorAction)])

    def update_actions_proposal(self) -> list[ExecutorAction]:
        return MagicMock(return_value=[MagicMock(spec=ExecutorAction)])


class ExecutorIntegrationTestBase(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    level = 1

    def create_executor_config(self, *args, **kwargs) -> ExecutorConfigBase:
        NotImplementedError()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Store original class state
        cls._original_markets = getattr(MockStrategyV2, 'markets', None)

    @classmethod
    def tearDownClass(cls):
        # Restore original class state
        if hasattr(cls, '_original_markets'):
            MockStrategyV2.markets = cls._original_markets
        super().tearDownClass()

    def setUp(self) -> None:
        self._patches = []
        super().setUp()
        self.clock_tick_size = 1
        self.start = pd.Timestamp("2019-01-01", tz="UTC")
        self.start_timestamp = self.start.timestamp()
        self.end = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
        self.end_timestamp = self.end.timestamp()
        self.clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)

        self.trading_pair = "ETH-USDT"
        self.base_asset = "ETH"
        self.quote_asset = "USDT"
        self.initial_price = Decimal("100")

        self.connector = self.create_exchange()
        self.market_info = MarketTradingPairTuple(self.connector, self.trading_pair, *self.trading_pair.split("-"))

        self.base_asset, self.quote_asset = self.trading_pair.split("-")
        self.initial_price = Decimal("100")

        self.strategy = self.create_strategy()
        self.executor = None

        self.clock.add_iterator(self.connector)
        self.clock.add_iterator(self.strategy)
        self.strategy.start(self.clock, self.start_timestamp)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.set_loggers([self.strategy.logger()])

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()

    async def asyncTearDown(self) -> None:
        await super().asyncTearDown()

    def tearDown(self) -> None:
        try:
            # Remove clock iterators first to prevent any late callbacks
            if hasattr(self, 'clock'):
                for iterator in self.clock.child_iterators:
                    self.clock.remove_iterator(iterator)

            # Stop executor first since it depends on everything else
            if hasattr(self, 'executor') and self.executor is not None:
                self.executor.stop()
                # Clear executor state explicitly
                self.executor._trailing_stop_pnl_trigger = None
                self.executor._open_order = None
                self.executor._close_order = None
                self.executor._realized_orders = []
                self.executor._failed_orders = []
                self.executor._canceled_orders = []
                self.executor._total_executed_amount_backup = Decimal("0")
                self.executor._current_retries = 0

            # Remove event listeners
            if hasattr(self, 'connector') and hasattr(self, '_event_listeners'):
                for event_tag, listener in self._event_listeners:
                    self.connector.remove_listener(event_tag, listener)
                self._event_listeners.clear()

            # Clear order tracker
            if hasattr(self, 'connector'):
                self.connector._order_tracker.active_orders.clear()
                # Reset order book
                self.connector.new_empty_order_book(self.trading_pair)
                self.connector.set_balanced_order_book(
                    trading_pair=self.trading_pair,
                    mid_price=float(self.initial_price),  # Start fresh at initial price
                    min_price=float(self.initial_price * Decimal("0.95")),
                    max_price=float(self.initial_price * Decimal("1.05")),
                    price_step_size=0.1,
                    volume_step_size=1.0,
                )
            # Stop strategy and clear mocks
            if hasattr(self, 'strategy'):
                self.strategy.stop(self.clock)
                if hasattr(self.strategy, 'executor_orchestrator'):
                    self.strategy.executor_orchestrator.reset_mock()
                if hasattr(self.strategy, 'market_data_provider'):
                    self.strategy.market_data_provider.reset_mock()

            # Always reset markets class variable
            if hasattr(MockStrategyV2, 'markets'):
                MockStrategyV2.markets = {}

            # Stop all patches
            if hasattr(self, '_patches'):
                for p in self._patches:
                    p.stop()
                self._patches.clear()
            if hasattr(self, '_mocks'):
                self._mocks.clear()

            for iterator in self.clock.child_iterators:
                self.clock.remove_iterator(iterator)

        finally:
            super().tearDown()

    def create_exchange(self):
        connector = ExtendedMockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap()),
        )
        connector._network_status = NetworkStatus.CONNECTED
        connector.new_empty_order_book(self.trading_pair)
        connector.set_balanced_order_book(
            trading_pair=self.trading_pair,
            mid_price=float(self.initial_price),
            min_price=float(self.initial_price * Decimal("0.95")),
            max_price=float(self.initial_price * Decimal("1.05")),
            price_step_size=0.1,
            volume_step_size=1.0,
        )
        connector.set_balance(self.base_asset, Decimal("10"))
        connector.set_balance(self.quote_asset, Decimal("10000"))
        connector.set_quantization_param(
            QuantizationParams(
                self.trading_pair,
                price_decimals=6,
                order_size_decimals=6,
                price_precision=6,
                order_size_precision=6,
            ),
        )
        connector.set_trading_rules({
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal("0.01"),
                min_price_increment=Decimal("0.0001"),
                min_base_amount_increment=Decimal("0.01"),
            )
        })
        return connector

    def create_strategy(self):
        # Create patches
        patches = [
            patch("asyncio.create_task"),
            patch("hummingbot.strategy.strategy_v2_base.StrategyV2Base.listen_to_executor_actions"),
            patch("hummingbot.strategy.strategy_v2_base.ExecutorOrchestrator"),
            patch("hummingbot.strategy.strategy_v2_base.MarketDataProvider"),
        ]

        # Start patches and store mocks
        self._patches = []
        self._mocks = []
        for p in patches:
            mock = p.start()
            self._patches.append(p)
            self._mocks.append(mock)

        mock_orch = self._mocks[2]  # Now we can access the mock
        type(mock_orch).ready = PropertyMock(return_value=True)

        strategy = MockStrategyV2(
            connectors={"mock_paper_exchange": self.connector},
            config=MockStrategyV2Config(
                markets={"mock_paper_exchange": {self.trading_pair}},
                candles_config=[],
            ),
        )
        return strategy

    def advance_clock(self, ticks: int = 1) -> None:
        for _ in range(ticks):
            self.clock.backtest_til(self.clock.current_timestamp + self.clock_tick_size)

    async def place_and_fill_order(self):
        self.clock.backtest_til(self.start_timestamp + 1)
        await self.executor.control_task()

        market_info = MarketTradingPairTuple(self.connector, self.trading_pair, self.base_asset, self.quote_asset)
        self.connector.add_listener(MarketEvent.BuyOrderCreated,
                                    SourceInfoEventForwarder(self.executor.process_order_created_event))
        self.connector.add_listener(MarketEvent.OrderFilled,
                                    SourceInfoEventForwarder(self.executor.process_order_filled_event))

        if active_orders := self.strategy.get_active_orders("mock_paper_exchange"):
            executor_order = [o for o in active_orders if o.client_order_id == self.executor.open_order.order_id][0]
            self.simulate_order_created(market_info, executor_order)
            self.advance_clock()
            await self.executor.control_task()
            self.simulate_order_filled(market_info, executor_order)
            self.advance_clock()
            await self.executor.control_task()

    async def run_executor_until_ready(self) -> None:
        self.clock.backtest_til(self.start_timestamp + 1)
        await self.executor.control_task()

        market_info = MarketTradingPairTuple(self.connector, self.trading_pair, self.base_asset, self.quote_asset)
        self.connector.add_listener(MarketEvent.BuyOrderCreated,
                                    SourceInfoEventForwarder(self.executor.process_order_created_event))
        self.connector.add_listener(MarketEvent.OrderFilled,
                                    SourceInfoEventForwarder(self.executor.process_order_filled_event))

        if active_orders := self.strategy.get_active_orders("mock_paper_exchange"):
            executor_order = [o for o in active_orders if o.client_order_id == self.executor.open_order.order_id][0]
            self.simulate_order_created(market_info, executor_order)
            self.advance_clock()
            await self.executor.control_task()
            self.simulate_order_filled(market_info, executor_order)
            self.advance_clock()
            await self.executor.control_task()

    def simulate_price_change(self, new_price: Decimal) -> None:
        price_step = 1
        self.connector.set_balanced_order_book(
            trading_pair=self.trading_pair,
            mid_price=float(new_price),
            min_price=float(new_price - 10 * price_step),
            max_price=float(new_price + 10 * price_step),
            price_step_size=price_step,
            volume_step_size=10,
        )

    def simulate_side_price_change(self, new_price: Decimal, taker_side: TradeType) -> None:
        # Set the order book so that the best bid/best ask matches the new price
        price_step = 1
        mid_price_offset = - price_step if taker_side is TradeType.SELL else price_step
        mid_price = new_price + mid_price_offset / Decimal("2")

        self.connector.set_balanced_order_book(
            trading_pair=self.trading_pair,
            mid_price=float(mid_price),
            min_price=float(mid_price - 10 * price_step),
            max_price=float(mid_price + 10 * price_step),
            price_step_size=price_step,
            volume_step_size=10,
        )

    @staticmethod
    def simulate_order_created(market_info: MarketTradingPairTuple, order: LimitOrder | MarketOrder):
        in_flight_order = InFlightOrder(
            client_order_id=order.client_order_id,
            exchange_order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY if order.is_buy else TradeType.SELL,
            amount=order.quantity,
            price=order.price,
            creation_timestamp=time.time(),
        )
        market_info.market._order_tracker.start_tracking_order(in_flight_order)
        event_tag = MarketEvent.BuyOrderCreated if order.is_buy else MarketEvent.SellOrderCreated
        event_class = BuyOrderCreatedEvent if order.is_buy else SellOrderCreatedEvent
        event = event_class(
            timestamp=time.time(),
            type=OrderType.LIMIT,
            trading_pair=order.trading_pair,
            amount=order.quantity,
            price=order.price,
            order_id=order.client_order_id,
            creation_timestamp=time.time()
        )
        market_info.market.trigger_event(event_tag, event)

    @staticmethod
    def simulate_order_filled(market_info: MarketTradingPairTuple, order: LimitOrder | MarketOrder):
        in_flight_order = market_info.market.in_flight_orders.get(order.client_order_id)
        in_flight_order.executed_amount_base = order.quantity
        in_flight_order.executed_amount_quote = order.quantity * order.price
        fill_event = OrderFilledEvent(
            timestamp=time.time(),
            order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            trade_type=TradeType.BUY if order.is_buy else TradeType.SELL,
            order_type=OrderType.LIMIT,
            price=order.price,
            amount=order.quantity,
            trade_fee=AddedToCostTradeFee(flat_fees=[]),
        )
        market_info.market.trigger_event(MarketEvent.OrderFilled, fill_event)
