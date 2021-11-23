#!/usr/bin/env python
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
import unittest
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderBookTradeEvent,
    TradeType
)
from hummingbot.strategy.pure_market_making.pure_market_making import PureMarketMakingStrategy
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange


class PMMRefreshToleranceUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "HBOT-ETH"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    def simulate_maker_market_trade(self, is_buy: bool, quantity: Decimal, price: Decimal):
        order_book = self.market.get_order_book(self.trading_pair)
        trade_event = OrderBookTradeEvent(
            self.trading_pair,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            price,
            quantity
        )
        order_book.apply_trade(trade_event)

    def setUp(self):
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.market: MockPaperExchange = MockPaperExchange()
        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 30
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.mid_price,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)
        self.market.set_balance("HBOT", 500)
        self.market.set_balance("ETH", 5000)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.market_info = MarketTradingPairTuple(self.market, self.trading_pair,
                                                  self.base_asset, self.quote_asset)
        self.clock.add_iterator(self.market)
        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    def test_strategy_ping_pong_on_ask_fill(self):
        self.strategy = PureMarketMakingStrategy()
        self.strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5,
            filled_order_delay=5,
            order_refresh_tolerance_pct=-1,
            ping_pong_enabled=True,
        )
        self.clock.add_iterator(self.strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        self.simulate_maker_market_trade(True, Decimal(100), Decimal("101.1"))

        self.clock.backtest_til(
            self.start_timestamp + 2 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(0, len(self.strategy.active_sells))
        old_bid = self.strategy.active_buys[0]

        self.clock.backtest_til(
            self.start_timestamp + 7 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(0, len(self.strategy.active_sells))
        # After new order create cycle (after filled_order_delay), check if a new order is created
        self.assertTrue(old_bid.client_order_id != self.strategy.active_buys[0].client_order_id)

        self.simulate_maker_market_trade(False, Decimal(100), Decimal("98.9"))

        self.clock.backtest_til(
            self.start_timestamp + 15 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

    def test_strategy_ping_pong_on_bid_fill(self):
        self.strategy = PureMarketMakingStrategy()
        self.strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5,
            filled_order_delay=5,
            order_refresh_tolerance_pct=-1,
            ping_pong_enabled=True,
        )
        self.clock.add_iterator(self.strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        self.simulate_maker_market_trade(False, Decimal(100), Decimal("98.9"))

        self.clock.backtest_til(
            self.start_timestamp + 2 * self.clock_tick_size
        )
        self.assertEqual(0, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))
        old_ask = self.strategy.active_sells[0]

        self.clock.backtest_til(
            self.start_timestamp + 7 * self.clock_tick_size
        )
        self.assertEqual(0, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        # After new order create cycle (after filled_order_delay), check if a new order is created
        self.assertTrue(old_ask.client_order_id != self.strategy.active_sells[0].client_order_id)

        self.simulate_maker_market_trade(True, Decimal(100), Decimal("101.1"))

        self.clock.backtest_til(
            self.start_timestamp + 15 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

    def test_multiple_orders_ping_pong(self):
        self.strategy = PureMarketMakingStrategy()
        self.strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_levels=5,
            order_level_amount=Decimal("1"),
            order_level_spread=Decimal("0.01"),
            order_refresh_time=5,
            order_refresh_tolerance_pct=-1,
            filled_order_delay=5,
            ping_pong_enabled=True,
        )
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)

        self.assertEqual(5, len(self.strategy.active_buys))
        self.assertEqual(5, len(self.strategy.active_sells))

        self.simulate_maker_market_trade(True, Decimal(100), Decimal("102.50"))
        # After market trade happens, 2 of the asks orders are filled.
        self.assertEqual(5, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))
        self.clock.backtest_til(
            self.start_timestamp + 2 * self.clock_tick_size
        )
        # Not refreshing time yet, still same active orders
        self.assertEqual(5, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))
        old_bids = self.strategy.active_buys
        old_asks = self.strategy.active_sells
        self.clock.backtest_til(
            self.start_timestamp + 7 * self.clock_tick_size
        )
        # After order refresh, same numbers of orders but it's a new set.
        self.assertEqual(5, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))
        self.assertNotEqual([o.client_order_id for o in old_asks],
                            [o.client_order_id for o in self.strategy.active_sells])
        self.assertNotEqual([o.client_order_id for o in old_bids],
                            [o.client_order_id for o in self.strategy.active_buys])

        # Simulate sell trade, the first bid gets taken out
        self.simulate_maker_market_trade(False, Decimal(100), Decimal("98.9"))
        self.assertEqual(4, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))
        self.clock.backtest_til(
            self.start_timestamp + 13 * self.clock_tick_size
        )

        # After refresh, same numbers of orders
        self.assertEqual(4, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))

        # Another bid order is filled.
        self.simulate_maker_market_trade(False, Decimal(100), Decimal("97.9"))
        self.assertEqual(3, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))

        self.clock.backtest_til(
            self.start_timestamp + 20 * self.clock_tick_size
        )

        # After refresh, numbers of orders back to order_levels of 5
        self.assertEqual(5, len(self.strategy.active_buys))
        self.assertEqual(5, len(self.strategy.active_sells))
