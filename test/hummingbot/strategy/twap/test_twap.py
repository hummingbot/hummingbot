#!/usr/bin/env python
from decimal import Decimal
from datetime import datetime
import math
import logging

import pandas as pd
from typing import List
import unittest
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger

from hummingbot.core.event.events import (
    MarketEvent,
    TradeType,
    OrderType,
    OrderFilledEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderCancelledEvent,
    MarketOrderFailureEvent,
    OrderExpiredEvent
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.conditional_execution_state import RunInTimeConditionalExecutionState
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.twap import TwapTradeStrategy
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange

logging.basicConfig(level=logging.ERROR)


class TWAPUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    maker_trading_pairs: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]
    clock_tick_size = 10

    level = 0
    log_records = []

    def setUp(self):

        super().setUp()
        self.log_records = []

        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.market: MockPaperExchange = MockPaperExchange()
        self.mid_price = 100
        self.order_delay_time = 15
        self.cancel_order_wait_time = 45
        self.market.set_balanced_order_book(trading_pair=self.maker_trading_pairs[0],
                                            mid_price=self.mid_price, min_price=1,
                                            max_price=200, price_step_size=1, volume_step_size=10)
        self.market.set_balance("COINALPHA", 500)
        self.market.set_balance("WETH", 50000)
        self.market.set_balance("QETH", 500)
        self.market.set_quantization_param(
            QuantizationParams(
                self.maker_trading_pairs[0], 6, 6, 6, 6
            )
        )

        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            *(
                [self.market] + self.maker_trading_pairs
            )
        )

        # Define strategies to test
        self.limit_buy_strategy: TwapTradeStrategy = TwapTradeStrategy(
            [self.market_info],
            order_price=Decimal("99"),
            cancel_order_wait_time=self.cancel_order_wait_time,
            is_buy=True,
            order_delay_time=self.order_delay_time,
            target_asset_amount=Decimal("2.0"),
            order_step_size=Decimal("1.0")
        )
        self.limit_sell_strategy: TwapTradeStrategy = TwapTradeStrategy(
            [self.market_info],
            order_price=Decimal("101"),
            cancel_order_wait_time=self.cancel_order_wait_time,
            is_buy=False,
            order_delay_time=self.order_delay_time,
            target_asset_amount=Decimal("5.0"),
            order_step_size=Decimal("1.67")
        )

        self.clock.add_iterator(self.market)
        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.buy_order_completed_logger: EventLogger = EventLogger()
        self.sell_order_completed_logger: EventLogger = EventLogger()

        self.market.add_listener(MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger)
        self.market.add_listener(MarketEvent.SellOrderCompleted, self.sell_order_completed_logger)
        self.market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage().startswith(message)
                   for record in self.log_records)

    @staticmethod
    def simulate_limit_order_fill(market: MockPaperExchange, limit_order: LimitOrder):
        quote_currency_traded: Decimal = limit_order.price * limit_order.quantity
        base_currency_traded: Decimal = limit_order.quantity
        quote_currency: str = limit_order.quote_currency
        base_currency: str = limit_order.base_currency

        if limit_order.is_buy:
            market.set_balance(quote_currency, market.get_balance(quote_currency) - quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) + base_currency_traded)
            market.trigger_event(MarketEvent.OrderFilled, OrderFilledEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                limit_order.trading_pair,
                TradeType.BUY,
                OrderType.LIMIT,
                limit_order.price,
                limit_order.quantity,
                AddedToCostTradeFee(Decimal("0"))
            ))
            market.trigger_event(MarketEvent.BuyOrderCompleted, BuyOrderCompletedEvent(
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
        else:
            market.set_balance(quote_currency, market.get_balance(quote_currency) + quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) - base_currency_traded)
            market.trigger_event(MarketEvent.OrderFilled, OrderFilledEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                limit_order.trading_pair,
                TradeType.SELL,
                OrderType.LIMIT,
                limit_order.price,
                limit_order.quantity,
                AddedToCostTradeFee(Decimal("0"))
            ))
            market.trigger_event(MarketEvent.SellOrderCompleted, SellOrderCompletedEvent(
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

    def test_limit_buy_order(self):
        self.clock.add_iterator(self.limit_buy_strategy)

        # test whether number of orders is one at start
        # check whether the order is buy
        # check whether the price is correct
        # check whether amount is correct
        order_time_1 = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(order_time_1)
        self.assertEqual(1, len(self.limit_buy_strategy.active_bids))
        first_bid_order: LimitOrder = self.limit_buy_strategy.active_bids[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(1, first_bid_order.quantity)

        # test whether number of orders is two after time delay
        # check whether the order is buy
        # check whether the price is correct
        # check whether amount is correct
        order_time_2 = order_time_1 + self.clock_tick_size * math.ceil(self.order_delay_time / self.clock_tick_size)
        self.clock.backtest_til(order_time_2)
        self.assertEqual(2, len(self.limit_buy_strategy.active_bids))
        second_bid_order: LimitOrder = self.limit_buy_strategy.active_bids[1][1]
        self.assertEqual(Decimal("99"), second_bid_order.price)
        self.assertEqual(1, second_bid_order.quantity)

        # Check whether order is cancelled after cancel_order_wait_time
        cancel_time_1 = order_time_1 + self.cancel_order_wait_time
        self.clock.backtest_til(cancel_time_1)
        self.assertEqual(1, len(self.limit_buy_strategy.active_bids))
        self.assertEqual(self.limit_buy_strategy.active_bids[0][1], second_bid_order)

        cancel_time_2 = order_time_2 + self.cancel_order_wait_time
        self.clock.backtest_til(cancel_time_2)
        self.assertEqual(1, len(self.limit_buy_strategy.active_bids))
        self.assertNotEqual(self.limit_buy_strategy.active_bids[0][1], first_bid_order)
        self.assertNotEqual(self.limit_buy_strategy.active_bids[0][1], second_bid_order)

    def test_limit_sell_order(self):
        self.clock.add_iterator(self.limit_sell_strategy)
        # check no orders are placed before time delay
        self.clock.backtest_til(self.start_timestamp)
        self.assertEqual(0, len(self.limit_sell_strategy.active_asks))

        # test whether number of orders is one at start
        # check whether the order is sell
        # check whether the price is correct
        # check whether amount is correct
        order_time_1 = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(order_time_1)
        self.assertEqual(1, len(self.limit_sell_strategy.active_asks))
        ask_order: LimitOrder = self.limit_sell_strategy.active_asks[0][1]
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.67000"), ask_order.quantity)

        # test whether number of orders is two after time delay
        # check whether the order is sell
        # check whether the price is correct
        # check whether amount is correct
        order_time_2 = order_time_1 + self.clock_tick_size * math.ceil(self.order_delay_time / self.clock_tick_size)
        self.clock.backtest_til(order_time_2)
        self.assertEqual(2, len(self.limit_sell_strategy.active_asks))
        ask_order: LimitOrder = self.limit_sell_strategy.active_asks[1][1]
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.67000"), ask_order.quantity)

        # test whether number of orders is three after two time delays
        # check whether the order is sell
        # check whether the price is correct
        # check whether amount is correct
        order_time_3 = order_time_2 + self.clock_tick_size * math.ceil(self.order_delay_time / self.clock_tick_size)
        self.clock.backtest_til(order_time_3)
        self.assertEqual(3, len(self.limit_sell_strategy.active_asks))
        ask_order: LimitOrder = self.limit_sell_strategy.active_asks[2][1]
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.66000"), ask_order.quantity)

    def test_order_filled_events(self):
        self.clock.add_iterator(self.limit_buy_strategy)
        self.clock.add_iterator(self.limit_sell_strategy)
        # check no orders are placed before time delay
        self.clock.backtest_til(self.start_timestamp)
        self.assertEqual(0, len(self.limit_buy_strategy.active_bids))

        # test whether number of orders is one
        # check whether the order is sell
        # check whether the price is correct
        # check whether amount is correct
        self.clock.backtest_til(self.start_timestamp + math.ceil(self.clock_tick_size / self.order_delay_time))
        self.assertEqual(1, len(self.limit_sell_strategy.active_asks))
        ask_order: LimitOrder = self.limit_sell_strategy.active_asks[0][1]
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.67000"), ask_order.quantity)

        self.assertEqual(1, len(self.limit_buy_strategy.active_bids))
        bid_order: LimitOrder = self.limit_buy_strategy.active_bids[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(1, bid_order.quantity)

        # Simulate market fill for limit buy and limit sell
        self.simulate_limit_order_fill(self.market, bid_order)
        self.simulate_limit_order_fill(self.market, ask_order)

        fill_events = self.maker_order_fill_logger.event_log
        self.assertEqual(2, len(fill_events))
        bid_fills: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.SELL]
        ask_fills: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.BUY]
        self.assertEqual(1, len(bid_fills))
        self.assertEqual(1, len(ask_fills))

    def test_with_insufficient_balance(self):
        # Set base balance to zero and check if sell strategies don't place orders
        self.clock.add_iterator(self.limit_buy_strategy)
        self.market.set_balance("WETH", 0)
        end_ts = self.start_timestamp + self.clock_tick_size + self.order_delay_time
        self.clock.backtest_til(end_ts)
        self.assertEqual(0, len(self.limit_buy_strategy.active_bids))
        market_buy_events: List[BuyOrderCompletedEvent] = [t for t in self.buy_order_completed_logger.event_log
                                                           if isinstance(t, BuyOrderCompletedEvent)]
        self.assertEqual(0, len(market_buy_events))

        self.clock.add_iterator(self.limit_sell_strategy)
        self.market.set_balance("COINALPHA", 0)
        end_ts += self.clock_tick_size + self.order_delay_time
        self.clock.backtest_til(end_ts)
        self.assertEqual(0, len(self.limit_sell_strategy.active_asks))
        market_sell_events: List[SellOrderCompletedEvent] = [t for t in self.sell_order_completed_logger.event_log
                                                             if isinstance(t, SellOrderCompletedEvent)]
        self.assertEqual(0, len(market_sell_events))

    def test_remaining_quantity_updated_after_cancel_order_event(self):
        self.limit_buy_strategy.logger().setLevel(1)
        self.limit_buy_strategy.logger().addHandler(self)

        self.clock.add_iterator(self.limit_buy_strategy)
        # check no orders are placed before time delay
        self.clock.backtest_til(self.start_timestamp)
        self.assertEqual(0, len(self.limit_buy_strategy.active_bids))

        # one order created after first tick
        self.clock.backtest_til(self.start_timestamp + math.ceil(self.clock_tick_size / self.order_delay_time))
        self.assertEqual(1, len(self.limit_buy_strategy.active_bids))
        bid_order: LimitOrder = self.limit_buy_strategy.active_bids[0][1]
        self.assertEqual(1, bid_order.quantity)
        self.assertEqual(self.limit_buy_strategy._quantity_remaining, 1)

        # Simulate order cancel
        self.market.trigger_event(MarketEvent.OrderCancelled, OrderCancelledEvent(
            self.market.current_timestamp,
            bid_order.client_order_id))

        self.assertEqual(0, len(self.limit_buy_strategy.active_bids))
        self.assertEqual(self.limit_buy_strategy._quantity_remaining, 2)

        self.assertTrue(self._is_logged('INFO',
                                        f"Updating status after order cancel (id: {bid_order.client_order_id})"))

    def test_remaining_quantity_updated_after_failed_order_event(self):
        self.limit_buy_strategy.logger().setLevel(1)
        self.limit_buy_strategy.logger().addHandler(self)

        self.clock.add_iterator(self.limit_buy_strategy)
        # check no orders are placed before time delay
        self.clock.backtest_til(self.start_timestamp)
        self.assertEqual(0, len(self.limit_buy_strategy.active_bids))

        # one order created after first tick
        self.clock.backtest_til(self.start_timestamp + math.ceil(self.clock_tick_size / self.order_delay_time))
        self.assertEqual(1, len(self.limit_buy_strategy.active_bids))
        bid_order: LimitOrder = self.limit_buy_strategy.active_bids[0][1]
        self.assertEqual(1, bid_order.quantity)
        self.assertEqual(self.limit_buy_strategy._quantity_remaining, 1)

        # Simulate order cancel
        self.market.trigger_event(MarketEvent.OrderFailure, MarketOrderFailureEvent(
            self.market.current_timestamp,
            bid_order.client_order_id,
            OrderType.LIMIT))

        self.assertEqual(0, len(self.limit_buy_strategy.active_bids))
        self.assertEqual(self.limit_buy_strategy._quantity_remaining, 2)

        self.assertTrue(self._is_logged('INFO',
                                        f"Updating status after order fail (id: {bid_order.client_order_id})"))

    def test_remaining_quantity_updated_after_expired_order_event(self):
        self.limit_buy_strategy.logger().setLevel(1)
        self.limit_buy_strategy.logger().addHandler(self)

        self.clock.add_iterator(self.limit_buy_strategy)
        # check no orders are placed before time delay
        self.clock.backtest_til(self.start_timestamp)
        self.assertEqual(0, len(self.limit_buy_strategy.active_bids))

        # one order created after first tick
        self.clock.backtest_til(self.start_timestamp + math.ceil(self.clock_tick_size / self.order_delay_time))
        self.assertEqual(1, len(self.limit_buy_strategy.active_bids))
        bid_order: LimitOrder = self.limit_buy_strategy.active_bids[0][1]
        self.assertEqual(1, bid_order.quantity)
        self.assertEqual(self.limit_buy_strategy._quantity_remaining, 1)

        # Simulate order cancel
        self.market.trigger_event(MarketEvent.OrderExpired, OrderExpiredEvent(
            self.market.current_timestamp,
            bid_order.client_order_id))

        self.assertEqual(0, len(self.limit_buy_strategy.active_bids))
        self.assertEqual(self.limit_buy_strategy._quantity_remaining, 2)

        self.assertTrue(self._is_logged('INFO',
                                        f"Updating status after order expire (id: {bid_order.client_order_id})"))

    def test_status_after_first_order_filled(self):
        self.clock.add_iterator(self.limit_sell_strategy)
        self.clock.backtest_til(self.start_timestamp)

        order_time_1 = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(order_time_1)
        ask_order: LimitOrder = self.limit_sell_strategy.active_asks[0][1]
        self.simulate_limit_order_fill(self.market, ask_order)

        order_time_2 = order_time_1 + self.clock_tick_size * math.ceil(self.order_delay_time / self.clock_tick_size)
        self.clock.backtest_til(order_time_2)
        ask_order2: LimitOrder = self.limit_sell_strategy.active_asks[0][1]

        base_balance = self.market_info.base_balance
        available_base_balance = self.market.get_available_balance(self.market_info.base_asset)
        quote_balance = self.market_info.quote_balance
        available_quote_balance = self.market.get_available_balance(self.market_info.quote_asset)

        buy_not_started_status = self.limit_buy_strategy.format_status()
        expected_buy_status = ("\n  Configuration:\n"
                               "    Total amount: 2.00 COINALPHA"
                               "    Order price: 99.00 WETH"
                               "    Order size: 1 COINALPHA\n"
                               "    Execution type: run continuously\n\n"
                               "  Markets:\n"
                               "                Exchange          Market  Best Bid Price  Best Ask Price  Mid Price\n"
                               "    0  MockPaperExchange  COINALPHA-WETH            99.5           100.5        100\n\n"
                               "  Assets:\n"
                               "                Exchange      Asset  Total Balance  Available Balance\n"
                               "    0  MockPaperExchange  COINALPHA         "
                               f"{base_balance:.2f}             "
                               f"{available_base_balance:.2f}\n"
                               "    1  MockPaperExchange       WETH       "
                               f"{quote_balance:.2f}           "
                               f"{available_quote_balance:.2f}\n\n"
                               "  No active maker orders.\n\n"
                               "  Average filled orders price: 0 WETH\n"
                               "  Pending amount: 2.00 COINALPHA")

        sell_started_status = self.limit_sell_strategy.format_status()
        expected_sell_status = ("\n  Configuration:\n"
                                "    Total amount: 5.00 COINALPHA"
                                "    Order price: 101.0 WETH"
                                "    Order size: 1.67 COINALPHA\n"
                                "    Execution type: run continuously\n\n"
                                "  Markets:\n"
                                "                Exchange          Market  Best Bid Price  Best Ask Price  Mid Price\n"
                                "    0  MockPaperExchange  COINALPHA-WETH            99.5           100.5        100\n\n"
                                "  Assets:\n"
                                "                Exchange      Asset  Total Balance  Available Balance\n"
                                "    0  MockPaperExchange  COINALPHA         "
                                f"{base_balance:.2f}             "
                                f"{available_base_balance:.2f}\n"
                                "    1  MockPaperExchange       WETH       "
                                f"{quote_balance:.2f}           "
                                f"{available_quote_balance:.2f}\n\n"
                                "  Active orders:\n"
                                "      Order ID  Type  Price Spread  Amount  Age Hang\n"
                                f"    0  ...{ask_order2.client_order_id[-4:]}  sell    101  0.00%    1.67  n/a  n/a\n\n"
                                "  Average filled orders price: 101.0 WETH\n"
                                "  Pending amount: 1.66 COINALPHA")

        self.assertEqual(expected_buy_status, buy_not_started_status)
        self.assertEqual(expected_sell_status, sell_started_status)

    def test_strategy_time_span_execution(self):
        span_start_time = self.start_timestamp + (self.clock_tick_size * 5)
        span_end_time = self.start_timestamp + (self.clock_tick_size * 7)
        strategy = TwapTradeStrategy(
            [self.market_info],
            order_price=Decimal("99"),
            cancel_order_wait_time=self.cancel_order_wait_time,
            is_buy=True,
            order_delay_time=self.order_delay_time,
            target_asset_amount=Decimal("100.0"),
            order_step_size=Decimal("1.0"),
            execution_state=RunInTimeConditionalExecutionState(start_timestamp=datetime.fromtimestamp(span_start_time),
                                                               end_timestamp=datetime.fromtimestamp(span_end_time))
        )

        self.clock.add_iterator(strategy)
        # check no orders are placed before span start
        self.clock.backtest_til(span_start_time - self.clock_tick_size)
        self.assertEqual(0, len(self.limit_sell_strategy.active_asks))

        order_time_1 = span_start_time + self.clock_tick_size
        self.clock.backtest_til(order_time_1)
        self.assertEqual(1, len(strategy.active_bids))
        first_bid_order: LimitOrder = strategy.active_bids[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(1, first_bid_order.quantity)

        # check no orders are placed after span end
        order_time_2 = span_end_time + (self.clock_tick_size * 10)
        self.clock.backtest_til(order_time_2)
        self.assertEqual(1, len(strategy.active_bids))

    def test_strategy_delayed_start_execution(self):
        delayed_start_time = self.start_timestamp + (self.clock_tick_size * 5)
        strategy = TwapTradeStrategy(
            [self.market_info],
            order_price=Decimal("99"),
            cancel_order_wait_time=self.cancel_order_wait_time,
            is_buy=True,
            order_delay_time=self.order_delay_time,
            target_asset_amount=Decimal("100.0"),
            order_step_size=Decimal("1.0"),
            execution_state=RunInTimeConditionalExecutionState(start_timestamp=datetime.fromtimestamp(delayed_start_time))
        )

        self.clock.add_iterator(strategy)
        # check no orders are placed before start
        self.clock.backtest_til(delayed_start_time - self.clock_tick_size)
        self.assertEqual(0, len(self.limit_sell_strategy.active_asks))

        order_time_1 = delayed_start_time + self.clock_tick_size
        self.clock.backtest_til(order_time_1)
        self.assertEqual(1, len(strategy.active_bids))
        first_bid_order: LimitOrder = strategy.active_bids[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(1, first_bid_order.quantity)
