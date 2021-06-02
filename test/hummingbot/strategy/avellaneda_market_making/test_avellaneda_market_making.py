#!/usr/bin/env python
import unittest
import pandas as pd
import numpy as np

from decimal import Decimal

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import (
    QuantizationParams,
)
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.avellaneda_market_making import AvellanedaMarketMakingStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from hummingbot.strategy.__utils__.trailing_indicators.average_volatility import AverageVolatilityIndicator
from hummingbot.core.event.events import OrderType

s_decimal_zero = Decimal(0)


class AvellanedaMarketMakingUnitTests(unittest.TestCase):

    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()

    @classmethod
    def setUpClass(cls):
        cls.trading_pair: str = "COINALPHA-HBOT"
        cls.initial_mid_price: int = 100

        cls.clock_tick_size: int = 1
        cls.clock: Clock = Clock(ClockMode.BACKTEST, cls.clock_tick_size, cls.start_timestamp, cls.end_timestamp)

        # Strategy Initial Configuration Parameters
        cls.order_amount: Decimal = Decimal("100")

    def setUp(self):
        self.market: BacktestMarket = BacktestMarket()
        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.market, self.trading_pair, *self.trading_pair.split("-")
        )

        self.order_book_data: MockOrderBookLoader = MockOrderBookLoader(
            self.trading_pair, *self.trading_pair.split("-")
        )
        self.order_book_data.set_balanced_order_book(mid_price=self.initial_mid_price,
                                                     min_price=1,
                                                     max_price=200,
                                                     price_step_size=1,
                                                     volume_step_size=10)
        self.market.add_data(self.order_book_data)
        self.market.set_balance("COINALPHA", 500)
        self.market.set_balance("HBOT", 5000)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair.split("-")[0], 6, 6, 6, 6
            )
        )

        self.strategy: AvellanedaMarketMakingStrategy = AvellanedaMarketMakingStrategy(
            market_info=self.market_info,
            order_amount=self.order_amount,
        )
        self.clock.add_iterator(self.market)
        self.clock.add_iterator(self.strategy)

    @staticmethod
    def simulate_volatility_increase(strategy):
        N_SAMPLES = 1000
        BUFFER_SIZE = 100
        INITIAL_RANDOM_SEED = 3141592653
        original_price = 100
        volatility = 0.005       # 0.5% of volatility (If asset is liquid, this is quite high!)
        np.random.seed(INITIAL_RANDOM_SEED)     # Using this hardcoded random seed we guarantee random samples generated are always the same
        samples = np.random.normal(original_price, volatility * original_price, N_SAMPLES)

        '''
        Idea is that this samples created guarantee the volatility is going to be the one you want.
        I'm testing the indicator volatility, but you could actually fix the rest of the parameters by fixing the samples.
        You can then change the volatility to be approximately equal to what you need. In this case ~0.5%
        '''
        volatility_indicator = AverageVolatilityIndicator(BUFFER_SIZE, 1)  # This replicates the same indicator Avellaneda uses if volatility_buffer_samples = 100

        for sample in samples:
            volatility_indicator.add_sample(sample)
            # TODO: Investigate how to add samples into strategy's AverageVolatilityIndicator
            # strategy._avg_vol.add_sample(sample)

        # The nice thing about harcoding the random seed is that you can harcode the assertions and it should work.
        # At the minimum change in any calculation this assertion will fail, and that looks good to me as a reminder to developer contributing with new code,
        # to assess if result of this test changing is reasonable or not (if in the future some calculations are changed on purpose and result changes, then test is rebased).
        # self.assertEqual(volatility_indicator.current_value, 0.5018627218927454)
        # unittest.TestCase.assertEqual(strategy._avg_vol, 0.5018627218927454)

    @staticmethod
    def simulate_place_limit_order(strategy: AvellanedaMarketMakingStrategy, market_info: MarketTradingPairTuple, order: LimitOrder):
        if order.is_buy:
            return strategy.buy_with_specific_market(market_trading_pair_tuple=market_info,
                                                     order_type=OrderType.LIMIT,
                                                     price=order.price,
                                                     amount=order.quantity
                                                     )
        else:
            return strategy.sell_with_specific_market(market_trading_pair_tuple=market_info,
                                                      order_type=OrderType.LIMIT,
                                                      price=order.price,
                                                      amount=order.quantity)

    def test_all_markets_ready(self):
        self.assertTrue(self.strategy.all_markets_ready())

    def test_market_info(self):
        self.assertEqual(self.market_info, self.strategy.market_info)

    def test_order_refresh_tolerance_pct(self):
        # Default value for order_refresh_tolerance_pct
        self.assertEqual(Decimal(-1), self.strategy.order_refresh_tolerance_pct)

        # Test setter method
        self.strategy.order_refresh_tolerance_pct = Decimal("1")

        self.assertEqual(Decimal("1"), self.strategy.order_refresh_tolerance_pct)

    def test_order_amount(self):
        self.assertEqual(self.order_amount, self.strategy.order_amount)

        # Test setter method
        self.strategy.order_amount = Decimal("1")

        self.assertEqual(Decimal("1"), self.strategy.order_amount)

    def test_inventory_target_base_pct(self):
        self.assertEqual(s_decimal_zero, self.strategy.inventory_target_base_pct)

        # Test setter method
        self.strategy.inventory_target_base_pct = Decimal("1")

        self.assertEqual(Decimal("1"), self.strategy.inventory_target_base_pct)

    def test_order_optimization_enabled(self):
        self.assertFalse(s_decimal_zero, self.strategy.order_optimization_enabled)

        # Test setter method
        self.strategy.order_optimization_enabled = True

        self.assertTrue(self.strategy.order_optimization_enabled)

    def test_order_refresh_time(self):
        self.assertEqual(float(30.0), self.strategy.order_refresh_time)

        # Test setter method
        self.strategy.order_refresh_time = float(1.0)

        self.assertEqual(float(1.0), self.strategy.order_refresh_time)

    def test_filled_order_delay(self):
        self.assertEqual(float(60.0), self.strategy.filled_order_delay)

        # Test setter method
        self.strategy.filled_order_delay = float(1.0)

        self.assertEqual(float(1.0), self.strategy.filled_order_delay)

    def test_add_transaction_costs_to_orders(self):
        self.assertTrue(self.strategy.order_optimization_enabled)

        # Test setter method
        self.strategy.order_optimization_enabled = False

        self.assertFalse(self.strategy.order_optimization_enabled)

    def test_base_asset(self):
        self.assertEqual(self.trading_pair.split("-")[0], self.strategy.base_asset)

    def test_quote_asset(self):
        self.assertEqual(self.trading_pair.split("-")[1], self.strategy.quote_asset)

    def test_trading_pair(self):
        self.assertEqual(self.trading_pair, self.strategy.trading_pair)

    def test_get_price(self):
        # Avellaneda Strategy get_price is simply a wrapper for MarketTradingPairTuple.get_mid_price()
        self.assertEqual(self.market_info.get_mid_price(), self.strategy.get_price())

    def test_get_last_price(self):
        # TODO: Determine if the get_last_price() function is needed in Avellaneda Strategy
        # Note: MarketTrradingPairTuple does not have a get_last_price() function

        # self.assertEqual(self.market_info.get_last_price(), self.strategy.get_last_price())
        pass

    def test_get_mid_price(self):
        self.assertEqual(self.market_info.get_mid_price(), self.strategy.get_mid_price())

    def test_market_info_to_active_orders(self):
        order_tracker = self.strategy.order_tracker

        self.assertEqual(order_tracker.market_pair_to_active_orders, self.strategy.market_info_to_active_orders)

        # Simulate order being placed
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=True,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("101.0"),
                                             quantity=Decimal("10"))

        self.simulate_place_limit_order(self.strategy, self.market_info, limit_order)

        self.assertEqual(1, len(self.strategy.market_info_to_active_orders))
        self.assertEqual(order_tracker.market_pair_to_active_orders, self.strategy.market_info_to_active_orders)

    def test_active_orders(self):
        self.assertEqual(0, len(self.strategy.active_orders))

        # Simulate order being placed
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=True,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("101.0"),
                                             quantity=Decimal("10"))

        self.simulate_place_limit_order(self.strategy, self.market_info, limit_order)

        self.assertEqual(1, len(self.strategy.active_orders))

    def test_active_buys(self):
        self.assertEqual(0, len(self.strategy.active_buys))

        # Simulate order being placed
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=True,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("101.0"),
                                             quantity=Decimal("10"))

        self.simulate_place_limit_order(self.strategy, self.market_info, limit_order)

        self.assertEqual(1, len(self.strategy.active_buys))

    def test_active_sells(self):
        self.assertEqual(0, len(self.strategy.active_sells))

        # Simulate order being placed
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=False,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("101.0"),
                                             quantity=Decimal("10"))

        self.simulate_place_limit_order(self.strategy, self.market_info, limit_order)

        self.assertEqual(1, len(self.strategy.active_sells))

    def test_logging_options(self):
        self.assertEqual(AvellanedaMarketMakingStrategy.OPTION_LOG_ALL, self.strategy.logging_options)

        # Test setter method
        self.strategy.logging_options = AvellanedaMarketMakingStrategy.OPTION_LOG_CREATE_ORDER

        self.assertEqual(AvellanedaMarketMakingStrategy.OPTION_LOG_CREATE_ORDER, self.strategy.logging_options)

    def test_order_tracker(self):
        # TODO: replicate order_tracker property in Avellaneda strategy. Already exists in StrategyBase
        pass

    def test_pure_mm_asset_df(self):
        pass

    def test_active_orders_df(self):
        pass

    def test_market_data_frame(self):
        pass

    def test_format_status(self):
        pass

    def test_cancel_order(self):
        pass

    def test_volatility_diff_from_last_parameter_calculation(self):
        pass

    def test_get_spread(self):
        pass

    def test_get_volatility(self):
        pass

    def test_calculate_target_inventory(self):
        pass

    def test_get_min_and_max_spread(self):
        pass

    def test_recalculate_parameters(self):
        pass

    def test_is_algorithm_ready(self):
        pass

    def test_create_proposal_based_on_order_override(self):
        pass

    def test_create_proposal_based_on_order_levels(self):
        pass

    def test_create_base_proposal(self):
        pass

    def test_get_adjusted_available_balance(self):
        pass

    def test_apply_order_price_modifiers(self):
        pass

    def test_apply_budget_constraint(self):
        pass

    def test_apply_order_optimization(self):
        pass

    def test_apply_order_amount_eta_transformation(self):
        pass

    def test_apply_add_transaction_costs(self):
        pass

    def test_cancel_active_orders(self):
        pass

    def test_aged_order_refresh(self):
        pass

    def test_to_create_orders(self):
        pass

    def test_execute_orders_proposal(self):
        pass

    def test_integrated_avellaneda_strategy(self):
        # TODO: Implement an integrated test that essentially runs the entire bot.
        pass
