import logging
import unittest
from decimal import Decimal
from typing import Optional

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderBookTradeEvent
from hummingbot.strategy.fixed_grid.fixed_grid import FixedGridStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

logging.basicConfig(level=logging.ERROR)


class FixedGridUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "HBOT-ETH"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    def setUp(self):
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.market: MockPaperExchange = MockPaperExchange(self.client_config_map)
        self.mid_price = 100
        self.start_order_spread = 0.01
        self.order_refresh_time = 30

        self.n_levels = 10
        self.grid_price_ceiling = 200
        self.grid_price_floor = 20

        self.market.set_balanced_order_book(self.trading_pair,
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
        self.order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.quote_required_strategy = FixedGridStrategy()
        self.quote_required_strategy.init_params(
            self.market_info,
            n_levels=10,
            grid_price_floor = Decimal("20"),
            grid_price_ceiling = Decimal("200"),
            start_order_spread=Decimal("0.01"),
            order_amount=Decimal("52"),
            order_refresh_time=30.0
        )

        self.base_required_strategy = FixedGridStrategy()
        self.base_required_strategy.init_params(
            self.market_info,
            n_levels=10,
            grid_price_floor = Decimal("110"),
            grid_price_ceiling = Decimal("200"),
            start_order_spread=Decimal("0.01"),
            order_amount=Decimal("60"),
            order_refresh_time=30.0
        )

        self.no_rebalance_strategy = FixedGridStrategy()
        self.no_rebalance_strategy.init_params(
            self.market_info,
            n_levels=10,
            grid_price_floor = Decimal("40"),
            grid_price_ceiling = Decimal("130"),
            start_order_spread=Decimal("0.01"),
            order_amount=Decimal("5"),
            order_refresh_time=10.0
        )

    def simulate_maker_market_trade(
            self, is_buy: bool, quantity: Decimal, price: Decimal, market: Optional[MockPaperExchange] = None,
    ):
        if market is None:
            market = self.market
        order_book = market.get_order_book(self.trading_pair)
        trade_event = OrderBookTradeEvent(
            self.trading_pair,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            price,
            quantity
        )
        order_book.apply_trade(trade_event)

    def test_rebalance_with_quote_required_and_grid_operation(self):
        strategy = self.quote_required_strategy
        self.clock.add_iterator(strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(5, strategy.current_level + 1)
        self.assertEqual(260, strategy.base_inv_levels[strategy.current_level])
        self.assertEqual(10400, strategy.quote_inv_levels[strategy.current_level])
        self.assertEqual(104, strategy._quote_inv_levels_current_price[strategy.current_level])

        sell_1 = strategy.active_sells[0]
        self.assertEqual(101, sell_1.price)
        self.assertAlmostEqual(Decimal((104 - 50) * 1.05), sell_1.quantity)

        # After order_refresh_time, a new set of orders is created
        self.clock.backtest_til(self.start_timestamp + 32.0)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertNotEqual(sell_1.client_order_id, strategy.active_sells[0].client_order_id)

        # Simulate rebalance sell order filled
        self.clock.backtest_til(self.start_timestamp + 35.0)
        self.simulate_maker_market_trade(True, 56.7, 101.5)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # Grid placement after rebalance order
        self.clock.backtest_til(self.start_timestamp + 40.0)
        self.assertEqual(True, strategy.inv_correct)
        self.assertEqual(4, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))

        # Simulate grid buy order filled
        self.clock.backtest_til(self.start_timestamp + 46.0)
        self.simulate_maker_market_trade(False, 52.0, 79.0)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(6, len(strategy.active_sells))

        # Simulate 2 grid sell orders filled
        self.clock.backtest_til(self.start_timestamp + 48.0)
        self.simulate_maker_market_trade(True, 52.0, 101.0)
        self.simulate_maker_market_trade(True, 52.0, 121.0)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(4, len(strategy.active_sells))

    def test_rebalance_with_base_required_and_grid_operation(self):
        strategy = self.base_required_strategy
        self.clock.add_iterator(strategy)
        self.market.set_balance("HBOT", Decimal("500"))
        self.market.set_balance("ETH", Decimal("5000"))

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))
        self.assertEqual(1, strategy.current_level + 1)
        self.assertEqual(540, strategy.base_inv_levels[strategy.current_level])
        self.assertEqual(0, strategy.quote_inv_levels[strategy.current_level])
        self.assertEqual(0, strategy._quote_inv_levels_current_price[strategy.current_level])

        buy_1 = strategy.active_buys[0]
        self.assertEqual(99, buy_1.price)
        self.assertAlmostEqual(Decimal((60 * 9 - 500) * 1.05), buy_1.quantity)

        # After order_refresh_time, a new set of orders is created
        self.clock.backtest_til(self.start_timestamp + 35.0)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))
        self.assertNotEqual(buy_1.client_order_id, strategy.active_buys[0].client_order_id)

        # Simulate rebalance buy order filled
        self.clock.backtest_til(self.start_timestamp + 40.0)
        self.simulate_maker_market_trade(False, 42, 98.5)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # Grid placement after rebalance order
        self.clock.backtest_til(self.start_timestamp + 43.0)
        self.assertEqual(True, strategy.inv_correct)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(9, len(strategy.active_sells))

        # Simulate 2 grid sell orders filled
        self.clock.backtest_til(self.start_timestamp + 46.0)
        self.simulate_maker_market_trade(True, 60.0, 121.0)
        self.simulate_maker_market_trade(True, 60.0, 131.0)
        self.assertEqual(2, len(strategy.active_buys))
        self.assertEqual(7, len(strategy.active_sells))

        # Simulate grid buy order filled
        self.simulate_maker_market_trade(False, 60.0, 119.5)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(8, len(strategy.active_sells))

    def test_no_rebalance_required_and_grid_operation(self):
        strategy = self.no_rebalance_strategy
        self.clock.add_iterator(strategy)
        self.market.set_balance("HBOT", Decimal("500"))
        self.market.set_balance("ETH", Decimal("5000"))

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(7, strategy.current_level + 1)
        self.assertEqual(6, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        # Simulate grid sell order filled
        self.clock.backtest_til(self.start_timestamp + 200.0)
        self.simulate_maker_market_trade(True, 5.0, 111.0)
        self.assertEqual(7, len(strategy.active_buys))
        self.assertEqual(2, len(strategy.active_sells))

        # Simulate 2 grid buy orders filled
        self.simulate_maker_market_trade(False, 5.0, 99.5)
        self.simulate_maker_market_trade(False, 5.0, 89.5)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(4, len(strategy.active_sells))
