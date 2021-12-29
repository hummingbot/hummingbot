from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.core.clock import Clock
from hummingbot.core.clock_mode import ClockMode
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    PositionMode,
    PositionSide,
    PriceType,
    SellOrderCompletedEvent,
    TradeType,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TradeFeeSchema
from hummingbot.strategy.data_types import Proposal, PriceSize
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.perpetual_market_making import PerpetualMarketMakingStrategy
from hummingbot.strategy.strategy_base import StrategyBase
from test.mock.mock_paper_exchange import MockPaperExchange
from test.mock.mock_perp_connector import MockPerpConnector


class PerpetualMarketMakingTests(TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()

    level = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.trading_pair: str = "COINALPHA-HBOT"
        cls.base_asset, cls.quote_asset = cls.trading_pair.split("-")
        cls.initial_mid_price: int = 100
        cls.clock_tick_size: int = 1
        cls.stop_loss_spread = Decimal("0.2")
        cls.stop_loss_slippage_buffer = Decimal("0.1")
        cls.long_profit_taking_spread = Decimal("0.5")
        cls.short_profit_taking_spread = Decimal("0.4")
        cls.trade_fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.01"),
            taker_percent_fee_decimal=Decimal("0.01"),
        )

    def setUp(self):
        super().setUp()
        self.log_records = []
        self.market: MockPerpConnector = MockPerpConnector(self.trade_fee_schema)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair,
                price_precision=6,
                price_decimals=2,
                order_size_precision=6,
                order_size_decimals=2,
            )
        )
        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.market, self.trading_pair, self.base_asset, self.quote_asset
        )
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.initial_mid_price,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)
        self.market.set_balance("COINALPHA", 1000)
        self.market.set_balance("HBOT", 50000)

        new_strategy = PerpetualMarketMakingStrategy()
        new_strategy.init_params(
            market_info=self.market_info,
            leverage=10,
            position_mode=PositionMode.ONEWAY.name.title(),
            bid_spread=Decimal("0.5"),
            ask_spread=Decimal("0.4"),
            order_amount=Decimal("100"),
            long_profit_taking_spread=self.long_profit_taking_spread,
            short_profit_taking_spread=self.short_profit_taking_spread,
            stop_loss_spread=self.stop_loss_spread,
            time_between_stop_loss_orders=10.0,
            stop_loss_slippage_buffer=self.stop_loss_slippage_buffer,
        )

        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)

        self.clock.add_iterator(self.market)
        self._configure_strategy(new_strategy)
        self.clock.backtest_til(self.start_timestamp)

        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    def tearDown(self) -> None:
        self.strategy.stop(self.clock)
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage().startswith(message)
                   for record in self.log_records)

    def _configure_strategy(self, strategy: StrategyBase):
        self.strategy = strategy
        self.strategy.logger().setLevel(1)
        self.strategy.logger().addHandler(self)
        self.clock.add_iterator(self.strategy)
        self.strategy.start(self.clock, self.start_timestamp)

    @staticmethod
    def simulate_limit_order_fill(market: MockPaperExchange, limit_order: LimitOrder):
        quote_currency_traded: Decimal = limit_order.price * limit_order.quantity
        base_currency_traded: Decimal = limit_order.quantity
        quote_currency: str = limit_order.quote_currency
        base_currency: str = limit_order.base_currency

        if limit_order.is_buy:
            market.set_balance(quote_currency, market.get_balance(quote_currency) - quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) + base_currency_traded)
        else:
            market.set_balance(quote_currency, market.get_balance(quote_currency) + quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) - base_currency_traded)

        market.trigger_event(MarketEvent.OrderFilled, OrderFilledEvent(
            market.current_timestamp,
            limit_order.client_order_id,
            limit_order.trading_pair,
            TradeType.BUY if limit_order.is_buy else TradeType.SELL,
            OrderType.LIMIT,
            limit_order.price,
            limit_order.quantity,
            AddedToCostTradeFee(Decimal("0"))
        ))
        event_type = MarketEvent.BuyOrderCompleted if limit_order.is_buy else MarketEvent.SellOrderCompleted
        event_class = BuyOrderCompletedEvent if limit_order.is_buy else SellOrderCompletedEvent
        market.trigger_event(event_type, event_class(
            market.current_timestamp,
            limit_order.client_order_id,
            base_currency,
            quote_currency,
            quote_currency,
            base_currency_traded,
            quote_currency_traded,
            Decimal("0"),
            OrderType.LIMIT
        ))

    def test_apply_budget_constraint(self):
        self.strategy = PerpetualMarketMakingStrategy()
        self.strategy.init_params(
            market_info=self.market_info,
            leverage=2,
            position_mode=PositionMode.HEDGE.name.title(),
            bid_spread=Decimal("1"),
            ask_spread=Decimal("1"),
            order_amount=Decimal("2"),
            long_profit_taking_spread=Decimal("1"),
            short_profit_taking_spread=Decimal("1"),
            stop_loss_spread=Decimal("1"),
            time_between_stop_loss_orders=10.0,
            stop_loss_slippage_buffer=self.stop_loss_slippage_buffer,
        )

        self.market.set_balance(self.base_asset, Decimal("2"))
        self.market.set_balance(self.quote_asset, Decimal("10"))

        buys = [
            PriceSize(price=Decimal("5"), size=Decimal("1")),
            PriceSize(price=Decimal("6"), size=Decimal("1")),
        ]
        sells = [
            PriceSize(price=Decimal("7"), size=Decimal("1")),
            PriceSize(price=Decimal("8"), size=Decimal("1")),
        ]
        proposal = Proposal(buys, sells)

        self.strategy.apply_budget_constraint(proposal)

        new_buys = proposal.buys
        new_sells = proposal.sells

        self.assertEqual(2, len(new_buys))  # cumulative 11 for leverage of 20
        self.assertEqual(buys[0], new_buys[0])
        self.assertEqual(buys[1], new_buys[1])
        self.assertEqual(1, len(new_sells))  # cumulative 18 for leverage of 20
        self.assertEqual(sells[0], new_sells[0])

    def test_create_stop_loss_proposal_for_long_position(self):
        position = Position(
            trading_pair=self.trading_pair,
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal(1000),
            entry_price=self.initial_mid_price + Decimal(30),
            amount=Decimal(1),
            leverage=Decimal(10))
        positions = [position]

        proposal = self.strategy.stop_loss_proposal(PositionMode.ONEWAY, positions)

        self.assertEqual(0, len(self.market.limit_orders))
        self.assertEqual(0, len(proposal.buys))
        self.assertEqual(position.entry_price *
                         (Decimal(1) - self.stop_loss_spread) *
                         (Decimal(1) - self.stop_loss_slippage_buffer),
                         proposal.sells[0].price)
        self.assertEqual(abs(position.amount), proposal.sells[0].size)

    def test_create_stop_loss_proposal_for_short_position(self):
        position = Position(
            trading_pair=(self.trading_pair),
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal(1000),
            entry_price=self.initial_mid_price - Decimal(30),
            amount=Decimal(-1),
            leverage=Decimal(10))
        positions = [position]
        proposal = self.strategy.stop_loss_proposal(PositionMode.ONEWAY, positions)

        self.assertEqual(0, len(self.market.limit_orders))
        self.assertEqual(0, len(proposal.sells))
        self.assertEqual(position.entry_price *
                         (Decimal(1) + self.stop_loss_spread) *
                         (Decimal(1) + self.stop_loss_slippage_buffer), proposal.buys[0].price)
        self.assertEqual(abs(position.amount), proposal.buys[0].size)

    def test_stop_loss_order_recreated_after_wait_time_for_long_position(self):
        initial_stop_loss_price = self.initial_mid_price - Decimal("0.1")
        initial_stop_loss_order_id = self.strategy.sell_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            price=initial_stop_loss_price)

        position = Position(
            trading_pair=(self.trading_pair),
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal(1000),
            entry_price=self.initial_mid_price + Decimal(30),
            amount=Decimal(1),
            leverage=Decimal(10))
        self.market.account_positions[self.trading_pair] = position

        # Simulate first stop loss was created at timestamp 1000
        self.strategy._exit_orders[initial_stop_loss_order_id] = self.start_timestamp

        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_orders))
        self.assertEqual(initial_stop_loss_order_id, self.strategy.active_orders[0].client_order_id)

        self.clock.backtest_til(self.start_timestamp + 9)

        self.assertEqual(1, len(self.strategy.active_orders))
        self.assertEqual(initial_stop_loss_order_id, self.strategy.active_orders[0].client_order_id)

        self.clock.backtest_til(self.start_timestamp + 10)

        self.assertEqual(initial_stop_loss_order_id, self.cancel_order_logger.event_log[0].order_id)
        self.assertEqual(1, len(self.strategy.active_orders))
        new_stop_loss_order = self.strategy.active_orders[0]
        self.assertNotEqual(initial_stop_loss_order_id, new_stop_loss_order.client_order_id)
        self.assertFalse(new_stop_loss_order.is_buy)
        self.assertEqual(position.amount, new_stop_loss_order.quantity)
        self.assertEqual(initial_stop_loss_price * (Decimal(1) - self.stop_loss_slippage_buffer),
                         new_stop_loss_order.price)

    def test_stop_loss_order_recreated_after_wait_time_for_short_position(self):
        position = Position(
            trading_pair=(self.trading_pair),
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal(1000),
            entry_price=self.initial_mid_price - Decimal(30),
            amount=Decimal(-1),
            leverage=Decimal(10))
        self.market.account_positions[self.trading_pair] = position

        initial_stop_loss_price = self.initial_mid_price + Decimal("0.1")
        initial_stop_loss_order_id = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            price=initial_stop_loss_price)

        # Simulate first stop loss was created at timestamp 1000
        self.strategy._exit_orders[initial_stop_loss_order_id] = self.start_timestamp

        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_orders))
        self.assertEqual(initial_stop_loss_order_id, self.strategy.active_orders[0].client_order_id)

        self.clock.backtest_til(self.start_timestamp + 9)

        self.assertEqual(1, len(self.strategy.active_orders))
        self.assertEqual(initial_stop_loss_order_id, self.strategy.active_orders[0].client_order_id)

        self.clock.backtest_til(self.start_timestamp + 10)

        self.assertEqual(initial_stop_loss_order_id, self.cancel_order_logger.event_log[0].order_id)
        self.assertEqual(1, len(self.strategy.active_orders))
        new_stop_loss_order = self.strategy.active_orders[0]
        self.assertNotEqual(initial_stop_loss_order_id, new_stop_loss_order.client_order_id)
        self.assertTrue(new_stop_loss_order.is_buy)
        self.assertEqual(abs(position.amount), new_stop_loss_order.quantity)
        self.assertEqual(initial_stop_loss_price * (Decimal(1) + self.stop_loss_slippage_buffer),
                         new_stop_loss_order.price)

    def test_create_profit_taking_proposal_logs_when_one_way_mode_and_multiple_positions(self):
        positions = [
            Position(
                trading_pair=(self.trading_pair),
                position_side=PositionSide.LONG,
                unrealized_pnl=Decimal(1000),
                entry_price=Decimal(50000),
                amount=Decimal(1),
                leverage=Decimal(10)
            ),
            Position(
                trading_pair=(self.trading_pair),
                position_side=PositionSide.SHORT,
                unrealized_pnl=Decimal(1000),
                entry_price=Decimal(50000),
                amount=Decimal(1),
                leverage=Decimal(10)
            )]
        self.strategy.profit_taking_proposal(PositionMode.ONEWAY, positions)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "More than one open position in ONEWAY position mode. "
                "Kindly ensure you do not interact with the exchange through other platforms and"
                " restart this strategy."))

    def test_create_profit_taking_proposal_for_one_way_cancels_other_possible_exit_orders(self):
        order_id = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            price=Decimal(50000))
        positions = [
            Position(
                trading_pair=(self.trading_pair),
                position_side=PositionSide.LONG,
                unrealized_pnl=Decimal(1000),
                entry_price=Decimal(50000),
                amount=Decimal(-1),
                leverage=Decimal(10)
            )]

        self.strategy.profit_taking_proposal(PositionMode.ONEWAY, positions)

        self.assertEqual(0, len(self.market.limit_orders))
        self.assertTrue(
            self._is_logged("INFO", f"Initiated cancellation of buy order {order_id} in favour of take profit order."))

        order_id = self.strategy.sell_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            price=Decimal(50000))
        positions = [
            Position(
                trading_pair=(self.trading_pair),
                position_side=PositionSide.LONG,
                unrealized_pnl=Decimal(1000),
                entry_price=Decimal(50000),
                amount=Decimal(1),
                leverage=Decimal(10)
            )]

        self.strategy.profit_taking_proposal(PositionMode.ONEWAY, positions)

        self.assertEqual(0, len(self.market.limit_orders))
        self.assertTrue(
            self._is_logged("INFO", f"Initiated cancellation of sell order {order_id} in favour of take profit order."))

    def test_create_profit_taking_proposal_for_long_position(self):
        position = Position(
            trading_pair=(self.trading_pair),
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal(1000),
            entry_price=self.initial_mid_price - Decimal(20),
            amount=Decimal(1),
            leverage=Decimal(10))
        positions = [position]

        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.initial_mid_price - 10,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)

        close_proposal = self.strategy.profit_taking_proposal(PositionMode.ONEWAY, positions)

        self.assertEqual(0, len(close_proposal.buys))
        self.assertEqual(position.entry_price * (Decimal(1) + self.long_profit_taking_spread),
                         close_proposal.sells[0].price)
        self.assertEqual(Decimal("1"), close_proposal.sells[0].size)

    def test_create_profit_taking_proposal_for_short_position(self):
        position = Position(
            trading_pair=(self.trading_pair),
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal(1000),
            entry_price=self.initial_mid_price + Decimal(20),
            amount=Decimal(-1),
            leverage=Decimal(10))
        positions = [position]

        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.initial_mid_price - 10,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)

        close_proposal = self.strategy.profit_taking_proposal(PositionMode.ONEWAY, positions)

        self.assertEqual(0, len(close_proposal.sells))
        self.assertEqual(position.entry_price * (Decimal(1) - self.short_profit_taking_spread),
                         close_proposal.buys[0].price)
        self.assertEqual(Decimal("1"), close_proposal.buys[0].size)

    def test_create_profit_taking_proposal_for_long_position_cancel_old_exit_orders(self):
        order_id = self.strategy.sell_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            price=Decimal(self.initial_mid_price))
        self.strategy._exit_orders[order_id] = 1000

        position = Position(
            trading_pair=(self.trading_pair),
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal(1000),
            entry_price=self.initial_mid_price - Decimal(20),
            amount=Decimal(1),
            leverage=Decimal(10))
        positions = [position]

        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.initial_mid_price - 10,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)

        self.strategy.profit_taking_proposal(PositionMode.ONEWAY, positions)

        self.assertEqual(order_id, self.cancel_order_logger.event_log[0].order_id)
        self.assertTrue(
            self._is_logged("INFO",
                            f"Initiated cancellation of previous take profit order {order_id} "
                            f"in favour of new take profit order."))
        self.assertEqual(0, len(self.strategy.active_orders))

    def test_create_profit_taking_proposal_for_short_position_cancel_old_exit_orders(self):
        order_id = self.strategy.buy_with_specific_market(
            market_trading_pair_tuple=self.market_info,
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            price=Decimal(self.initial_mid_price))
        self.strategy._exit_orders[order_id] = 1000

        position = Position(
            trading_pair=(self.trading_pair),
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal(1000),
            entry_price=self.initial_mid_price + Decimal(20),
            amount=Decimal(-1),
            leverage=Decimal(10))
        positions = [position]

        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.initial_mid_price + 10,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)

        self.strategy.profit_taking_proposal(PositionMode.ONEWAY, positions)

        self.assertEqual(order_id, self.cancel_order_logger.event_log[0].order_id)
        self.assertTrue(
            self._is_logged("INFO",
                            f"Initiated cancellation of previous take profit order {order_id} "
                            f"in favour of new take profit order."))
        self.assertEqual(0, len(self.strategy.active_orders))

    def test_tick_creates_buy_and_sell_pairs_when_no_position_opened(self):
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        buy_order = self.strategy.active_buys[0]
        sell_order = self.strategy.active_sells[0]

        self.assertEqual(self.trading_pair, buy_order.trading_pair)
        self.assertEqual(
            self.strategy.get_price() * (Decimal(1) - self.strategy.bid_spread),
            buy_order.price)
        self.assertEqual(Decimal(100), buy_order.quantity)
        self.assertEqual(self.trading_pair, sell_order.trading_pair)
        self.assertEqual(
            self.strategy.get_price() * (Decimal(1) + self.strategy.ask_spread),
            sell_order.price)
        self.assertEqual(Decimal(100), sell_order.quantity)

    def test_active_orders_are_recreated_on_refresh_time(self):
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        buy_order = self.strategy.active_buys[0]
        sell_order = self.strategy.active_sells[0]

        self.clock.backtest_til(self.strategy.current_timestamp + self.strategy.order_refresh_time)

        # All orders should have been cancelled
        self.assertEqual(0, len(self.strategy.active_orders))

        # In the next tick the new orders should be created
        self.clock.backtest_til(self.strategy.current_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))
        self.assertEqual(self.trading_pair, buy_order.trading_pair)
        self.assertEqual(
            self.strategy.get_price() * (Decimal(1) - self.strategy.bid_spread),
            buy_order.price)
        self.assertEqual(Decimal(100), buy_order.quantity)
        self.assertEqual(self.trading_pair, sell_order.trading_pair)
        self.assertEqual(
            self.strategy.get_price() * (Decimal(1) + self.strategy.ask_spread),
            sell_order.price)
        self.assertEqual(Decimal(100), sell_order.quantity)

    def test_active_orders_are_not_refreshed_if_covered_by_refresh_tolerance(self):
        self.strategy.order_refresh_tolerance_pct = Decimal("0.2")

        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        buy_order = self.strategy.active_buys[0]
        sell_order = self.strategy.active_sells[0]

        self.clock.backtest_til(self.strategy.current_timestamp + self.strategy.order_refresh_time)

        # The orders should not be cancelled
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(buy_order, self.strategy.active_buys[0])
        self.assertEqual(1, len(self.strategy.active_sells))
        self.assertEqual(sell_order, self.strategy.active_sells[0])

    def test_orders_creation_with_order_override(self):
        new_strategy = PerpetualMarketMakingStrategy()
        new_strategy.init_params(
            market_info=self.market_info,
            leverage=10,
            position_mode=PositionMode.ONEWAY.name.title(),
            bid_spread=Decimal("0.5"),
            ask_spread=Decimal("0.4"),
            order_amount=Decimal("100"),
            long_profit_taking_spread=self.long_profit_taking_spread,
            short_profit_taking_spread=self.short_profit_taking_spread,
            stop_loss_spread=self.stop_loss_spread,
            time_between_stop_loss_orders=10.0,
            stop_loss_slippage_buffer=self.stop_loss_slippage_buffer,
            order_override={"buy": ["buy", "10", "50"], "sell": ["sell", "20", "40"]}
        )

        self.clock.remove_iterator(self.strategy)
        self._configure_strategy(new_strategy)

        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        buy_order = self.strategy.active_buys[0]
        sell_order = self.strategy.active_sells[0]

        self.assertEqual(self.trading_pair, buy_order.trading_pair)
        self.assertEqual(
            self.strategy.get_price() * (Decimal(1) - Decimal("0.1")),
            buy_order.price)
        self.assertEqual(Decimal(50), buy_order.quantity)
        self.assertEqual(self.trading_pair, sell_order.trading_pair)
        self.assertEqual(
            self.strategy.get_price() * (Decimal(1) + Decimal("0.2")),
            sell_order.price)
        self.assertEqual(Decimal(40), sell_order.quantity)

    def test_orders_not_created_if_not_enough_balance(self):
        self.strategy.order_amount = Decimal("20000")

        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(0, len(self.strategy.active_buys))
        self.assertEqual(0, len(self.strategy.active_sells))
        self.assertTrue(
            self._is_logged(
                "INFO",
                "Insufficient balance: BUY order (price: 50.00, size: 20000.0) is omitted."))
        self.assertTrue(
            self._is_logged(
                "INFO",
                "Insufficient balance: SELL order (price: 140.00, size: 20000.0) is omitted."))
        self.assertTrue(
            self._is_logged(
                "WARNING",
                "You are also at a possible risk of being liquidated if there happens to be an open loss."))

    def test_orders_creation_with_order_optimization_enabled(self):
        self.strategy.order_optimization_enabled = True

        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        buy_order = self.strategy.active_buys[0]
        sell_order = self.strategy.active_sells[0]

        self.assertEqual(self.trading_pair, buy_order.trading_pair)
        self.assertEqual(
            self.strategy.get_price() * (Decimal(1) - self.strategy.bid_spread),
            buy_order.price)
        self.assertEqual(Decimal(100), buy_order.quantity)
        self.assertEqual(self.trading_pair, sell_order.trading_pair)
        self.assertEqual(
            self.strategy.get_price() * (Decimal(1) + self.strategy.ask_spread),
            sell_order.price)
        self.assertEqual(Decimal(100), sell_order.quantity)

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_strategy_logs_fill_and_complete_events_details(self, _):
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        buy_order = self.strategy.active_buys[0]
        sell_order = self.strategy.active_sells[0]

        self.simulate_limit_order_fill(self.market, buy_order)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"({self.trading_pair}) Maker buy order of {buy_order.quantity} {self.base_asset} filled."
            )
        )
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"({self.trading_pair}) Maker buy order {buy_order.client_order_id} "
                f"({buy_order.quantity} {self.base_asset} @ "
                f"{buy_order.price} {self.quote_asset}) has been completely filled."
            )
        )

        self.simulate_limit_order_fill(self.market, sell_order)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"({self.trading_pair}) Maker sell order of {sell_order.quantity} {self.base_asset} filled."
            )
        )
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"({self.trading_pair}) Maker sell order {sell_order.client_order_id} "
                f"({sell_order.quantity} {self.base_asset} @ "
                f"{sell_order.price} {self.quote_asset}) has been completely filled."
            )
        )

    def test_status_text_when_no_open_positions_and_two_orders(self):
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        expected_status = ("\n  Markets:"
                           "\n             Exchange         Market  Best Bid  Best Ask  Ref Price (MidPrice)"
                           "\n    MockPerpConnector COINALPHA-HBOT      99.5     100.5                   100"
                           "\n\n  Assets:"
                           "\n                       HBOT"
                           "\n    Total Balance     50000"
                           "\n    Available Balance 45000"
                           "\n\n  Orders:"
                           "\n     Level Type  Price Spread Amount (Orig)  Amount (Adj) Age"
                           "\n         1 sell    140 40.00%           100           100 n/a"
                           "\n         1  buy     50 50.00%           100           100 n/a"
                           "\n\n  No active positions.")
        status = self.strategy.format_status()

        self.assertEqual(expected_status, status)

    def test_status_text_with_one_open_position_and_no_orders_alive(self):
        position = Position(
            trading_pair=(self.trading_pair),
            position_side=PositionSide.LONG,
            unrealized_pnl=Decimal(1000),
            entry_price=self.market.get_price(self.trading_pair, True),
            amount=Decimal(1),
            leverage=Decimal(10))
        self.market.account_positions[self.trading_pair] = position

        self.clock.backtest_til(self.start_timestamp + 1)

        expected_status = ("\n  Markets:"
                           "\n             Exchange         Market  Best Bid  Best Ask  Ref Price (MidPrice)"
                           "\n    MockPerpConnector COINALPHA-HBOT      99.5     100.5                   100"
                           "\n\n  Assets:"
                           "\n                       HBOT"
                           "\n    Total Balance     50000"
                           "\n    Available Balance 50000"
                           "\n\n  No active maker orders."
                           "\n\n  Positions:"
                           "\n            Symbol Type Entry Price Amount Leverage Unrealized PnL"
                           "\n    COINALPHA-HBOT LONG      100.50      1       10           0.00")
        status = self.strategy.format_status()

        self.assertEqual(expected_status, status)

    def test_get_price_type(self):
        self.assertEqual(PriceType.MidPrice, self.strategy.get_price_type("mid_price"))
        self.assertEqual(PriceType.BestBid, self.strategy.get_price_type("best_bid"))
        self.assertEqual(PriceType.BestAsk, self.strategy.get_price_type("best_ask"))
        self.assertEqual(PriceType.LastTrade, self.strategy.get_price_type("last_price"))
        self.assertEqual(PriceType.LastOwnTrade, self.strategy.get_price_type("last_own_trade_price"))
        self.assertEqual(PriceType.Custom, self.strategy.get_price_type("custom"))

        self.assertRaises(ValueError, self.strategy.get_price_type, "invalid_text")
