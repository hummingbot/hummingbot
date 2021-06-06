#!/usr/bin/env python
import unittest
import pandas as pd
import math
import numpy as np

from decimal import Decimal
from typing import (
    List,
    Tuple,
)

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import (
    QuantizationParams,
)
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.strategy.avellaneda_market_making import AvellanedaMarketMakingStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from hummingbot.strategy.__utils__.trailing_indicators.average_volatility import AverageVolatilityIndicator
from hummingbot.core.event.events import OrderType
from hummingbot.strategy.avellaneda_market_making.data_types import PriceSize, Proposal

s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("NaN")


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

        # Testing Constants
        cls.low_vol: Decimal = Decimal("0.5462346278631169")
        cls.high_vol: Decimal = Decimal("10.884136001718568")

        # Strategy Initial Configuration Parameters
        cls.order_amount: Decimal = Decimal("100")
        cls.inventory_target_base_pct: Decimal = Decimal("0.5")     # Indicates 50%
        cls.min_spread: Decimal = Decimal("0.15")                   # Default strategy value
        cls.max_spread: Decimal = Decimal("2")                      # Default strategy value
        cls.vol_to_spread_multiplier: Decimal = Decimal("1.3")      # Default strategy value

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
            min_spread=self.min_spread,
            max_spread=self.max_spread,
            inventory_target_base_pct=self.inventory_target_base_pct,
            vol_to_spread_multiplier=self.vol_to_spread_multiplier,
        )

        self.avg_vol_indicator: AverageVolatilityIndicator = AverageVolatilityIndicator(sampling_length=100,
                                                                                        processing_length=1)

        self.strategy.avg_vol = self.avg_vol_indicator

        self.clock.add_iterator(self.market)
        self.clock.add_iterator(self.strategy)
        self.strategy.start(self.clock)

    @staticmethod
    def simulate_low_volatility(strategy: AvellanedaMarketMakingStrategy):
        N_SAMPLES = 1000
        BUFFER_SIZE = 30  # Default Buffer Size used for tests
        INITIAL_RANDOM_SEED = 3141592653
        original_price = 100
        volatility = AvellanedaMarketMakingUnitTests.low_vol / Decimal("100")  # Assuming 0.5% volatility
        np.random.seed(INITIAL_RANDOM_SEED)     # Using this hardcoded random seed we guarantee random samples generated are always the same
        samples = np.random.normal(original_price, volatility * original_price, N_SAMPLES)

        # This replicates the same indicator Avellaneda uses if volatility_buffer_samples = 30
        volatility_indicator = AverageVolatilityIndicator(BUFFER_SIZE, 1)

        for sample in samples:
            volatility_indicator.add_sample(sample)

        # Note: Current Value of volatility is 0.5945301953179808
        strategy.avg_vol = volatility_indicator

    @staticmethod
    def simulate_high_volatility(strategy: AvellanedaMarketMakingStrategy):
        N_SAMPLES = 1000
        BUFFER_SIZE = 30  # Default Buffer Size used for tests
        INITIAL_RANDOM_SEED = 3141592653
        original_price = 100
        volatility = AvellanedaMarketMakingUnitTests.high_vol / Decimal("100")  # Assuming 10% volatility
        np.random.seed(INITIAL_RANDOM_SEED)     # Using this hardcoded random seed we guarantee random samples generated are always the same
        samples = np.random.normal(original_price, volatility * original_price, N_SAMPLES)

        # This replicates the same indicator Avellaneda uses if volatility_buffer_samples = 30
        volatility_indicator = AverageVolatilityIndicator(BUFFER_SIZE, 1)

        for sample in samples:
            volatility_indicator.add_sample(sample)

        # Note: Current Value of volatility is 10.884136001718568
        strategy.avg_vol = volatility_indicator

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
        self.assertEqual(self.inventory_target_base_pct, self.strategy.inventory_target_base_pct)

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

    def test_execute_orders_proposal(self):
        self.assertEqual(0, len(self.strategy.active_orders))

        buys: List[PriceSize] = [PriceSize(price=Decimal("99"), size=Decimal("1"))]
        sells: List[PriceSize] = [PriceSize(price=Decimal("101"), size=Decimal("1"))]
        proposal: Proposal = Proposal(buys, sells)

        self.strategy.execute_orders_proposal(proposal)

        self.assertEqual(2, len(self.strategy.active_orders))

    def test_cancel_order(self):
        self.assertEqual(0, len(self.strategy.active_orders))

        buys: List[PriceSize] = [PriceSize(price=Decimal("99"), size=Decimal("1"))]
        sells: List[PriceSize] = [PriceSize(price=Decimal("101"), size=Decimal("1"))]
        proposal: Proposal = Proposal(buys, sells)

        self.strategy.execute_orders_proposal(proposal)

        self.assertEqual(2, len(self.strategy.active_orders))

        for order in self.strategy.active_orders:
            self.strategy.cancel_order(order.client_order_id)

        self.assertEqual(0, len(self.strategy.active_orders))

    def test_is_algorithm_ready(self):
        self.assertFalse(self.strategy.is_algorithm_ready())

        self.simulate_high_volatility(self.strategy)

        self.assertTrue(self.strategy.is_algorithm_ready())

    def test_volatility_diff_from_last_parameter_calculation(self):
        # Initial volatility check. Should return s_decimal_zero
        self.assertEqual(s_decimal_zero, self.strategy.volatility_diff_from_last_parameter_calculation(self.strategy.get_volatility()))

        # Simulate buffers being filled and initial market volatility
        self.simulate_low_volatility(self.strategy)
        self.strategy.collect_market_variables(self.strategy.current_timestamp)
        self.strategy.recalculate_parameters()
        initial_vol: Decimal = self.strategy.get_volatility()

        # Simulate change in volatitly
        self.simulate_high_volatility(self.strategy)
        new_vol = self.strategy.get_volatility()

        self.assertNotEqual(s_decimal_zero, self.strategy.volatility_diff_from_last_parameter_calculation(self.strategy.get_volatility()))

        expected_diff_vol: Decimal = abs(initial_vol - new_vol) / initial_vol
        self.assertEqual(expected_diff_vol, self.strategy.volatility_diff_from_last_parameter_calculation(self.strategy.get_volatility()))

    def test_get_spread(self):
        order_book: OrderBook = self.market.get_order_book(self.trading_pair)
        expected_spread = order_book.get_price(True) - order_book.get_price(False)

        self.assertEqual(expected_spread, self.strategy.get_spread())

    def test_get_volatility(self):
        # Initial Volatility
        self.assertTrue(math.isnan(self.strategy.get_volatility()))

        # Simulate volatility update
        self.simulate_low_volatility(self.strategy)

        # Check updated volatility
        self.assertAlmostEqual(self.low_vol, self.strategy.get_volatility(), 1)

    def test_calculate_target_inventory(self):
        # Calculate expected quantize order amount
        current_price = self.market_info.get_mid_price()

        base_asset_amount = self.market.get_balance(self.trading_pair.split("-")[0])
        quote_asset_amount = self.market.get_balance(self.trading_pair.split("-")[1])
        base_value = base_asset_amount * current_price
        inventory_value = base_value + quote_asset_amount
        target_inventory_value = Decimal((inventory_value * self.inventory_target_base_pct) / current_price)

        expected_quantize_order_amount = self.market.quantize_order_amount(self.trading_pair, target_inventory_value)

        self.assertEqual(expected_quantize_order_amount, self.strategy.calculate_target_inventory())

    def test_get_min_and_max_spread(self):
        # Simulate low volatility. vol approx. 0.5%
        self.simulate_low_volatility(self.strategy)

        # Calculating min and max spread in low volatility
        curr_price: Decimal = self.strategy.get_price()
        expected_min_spread: Decimal = self.min_spread * curr_price
        expected_max_spread: Decimal = self.max_spread * curr_price * (expected_min_spread / (self.min_spread * curr_price))

        self.assertEqual((expected_min_spread, expected_max_spread), self.strategy._get_min_and_max_spread())

        # Simulate high volatility. vol approx. 10%
        self.simulate_high_volatility(self.strategy)

        curr_price: Decimal = self.strategy.get_price()
        curr_vol: Decimal = self.strategy.get_volatility()
        expected_min_spread: Decimal = self.vol_to_spread_multiplier * curr_vol
        expected_max_spread: Decimal = self.max_spread * curr_price * (expected_min_spread / (self.min_spread * curr_price))

        self.assertEqual((expected_min_spread, expected_max_spread), self.strategy._get_min_and_max_spread())

    def test_recalculate_parameters(self):

        # Simulate low volatility
        self.simulate_low_volatility(self.strategy)
        self.strategy.collect_market_variables(self.strategy.current_timestamp)
        self.strategy.recalculate_parameters()

        # Check initial gamma, kappa, eta, latest_parameter_calculation_vol
        expected_gamma = Decimal('0.003298')
        expected_kappa = Decimal('0.004993')
        expected_eta = Decimal('0.004186')

        self.assertAlmostEqual(expected_gamma, self.strategy.gamma, 5)
        self.assertAlmostEqual(expected_kappa, self.strategy.kappa, 5)
        self.assertAlmostEqual(expected_eta, self.strategy.eta, 5)

        # Simulate high volatility
        self.simulate_high_volatility(self.strategy)
        self.strategy.collect_market_variables(self.strategy.current_timestamp)
        self.strategy.recalculate_parameters()

        # Check new gamma, kappa, eta, latest_parameter_calculation_vol
        expected_gamma = Decimal('0.000008')
        expected_kappa = Decimal('0.006429')
        expected_eta = Decimal('0.004186')

        self.assertAlmostEqual(expected_gamma, self.strategy.gamma, 5)
        self.assertAlmostEqual(expected_kappa, self.strategy.kappa, 5)
        self.assertAlmostEqual(expected_eta, self.strategy.eta, 5)

    def test_calculate_reserved_price_and_optimal_spread(self):
        # Simulate low volatility
        self.simulate_low_volatility(self.strategy)

        # Prepare market variables and parameters for calculation
        self.strategy.collect_market_variables(self.strategy.current_timestamp)
        self.strategy.recalculate_parameters()
        self.strategy.calculate_reserved_price_and_optimal_spread()

        # Check reserved_price, optimal_ask and optimal_bid
        self.assertAlmostEqual(Decimal("53.75"), self.strategy.reserved_price, 2)
        self.assertAlmostEqual(Decimal("207.5"), self.strategy.optimal_ask, 1)
        self.assertAlmostEqual(Decimal("-100.0"), self.strategy.optimal_bid, 1)

        # Simulate high volatility
        self.simulate_high_volatility(self.strategy)

        # Prepare market variables and parameters for calculation
        self.strategy.collect_market_variables(self.strategy.current_timestamp)
        self.strategy.recalculate_parameters()
        self.strategy.calculate_reserved_price_and_optimal_spread()

        # Check reserved_price, optimal_ask and optimal_bid
        self.assertAlmostEqual(Decimal("53.24"), self.strategy.reserved_price, 2)
        self.assertAlmostEqual(Decimal("208.68"), self.strategy.optimal_ask, 2)
        self.assertAlmostEqual(Decimal("-102.19"), self.strategy.optimal_bid, 1)

    def test_create_proposal_based_on_order_override(self):
        # Initial check for empty order_override
        expected_output: Tuple[List, List] = ([], [])
        self.assertEqual(expected_output, self.strategy.create_proposal_based_on_order_override())

        order_override = {
            "order_1": ["sell", 2.5, 100],
            "order_2": ["buy", 0.5, 100]
        }

        # Re-initialize strategy with order_ride configurations
        self.strategy = AvellanedaMarketMakingStrategy(
            market_info=self.market_info,
            order_amount=self.order_amount,
            order_override=order_override,
        )

        expected_proposal = (list(), list())
        for order in order_override.values():
            list_to_append = expected_proposal[0] if order[0] == "buy" else expected_proposal[1]
            if "buy" == order[0]:
                price = self.strategy.get_price() * (Decimal("1") - Decimal(str(order[1])) / Decimal("100"))
            else:
                price = self.strategy.get_price() * (Decimal("1") + Decimal(str(order[1])) / Decimal("100"))

            price = self.market.quantize_order_price(self.trading_pair, price)
            size = self.market.quantize_order_amount(self.trading_pair, Decimal(str(order[2])))

            list_to_append.append(PriceSize(price, size))

        self.assertEqual(str(expected_proposal), str(self.strategy.create_proposal_based_on_order_override()))

    def test_get_logspaced_level_spreads(self):
        # Re-initialize strategy with order_level configurations
        self.strategy = AvellanedaMarketMakingStrategy(
            market_info=self.market_info,
            order_amount=self.order_amount,
            order_levels=2,
        )
        self.strategy.start(self.clock)

        # Simulate low volatility.
        # Note: bid/ask_level_spreads Requires volatility, optimal_bid, optimal_ask to be defined
        self.simulate_low_volatility(self.strategy)

        self.strategy.collect_market_variables(self.strategy.current_timestamp)
        self.strategy.recalculate_parameters()
        self.strategy.calculate_reserved_price_and_optimal_spread()

        # TODO: Show exact calculation. Find a better max_spread parameter to better illustrate bid levels
        expected_bid_spreads = [0.0, 0.0]
        expected_ask_spreads = [0.0, 92.5]

        bid_level_spreads, ask_level_spreads = self.strategy._get_logspaced_level_spreads()
        for i, spread in enumerate(bid_level_spreads):
            self.assertAlmostEqual(expected_bid_spreads[i], spread, 1)

        for i, spread in enumerate(ask_level_spreads):
            self.assertAlmostEqual(expected_ask_spreads[i], spread, 1)

        # Simulate high volatility. Find a better max_spread parameter to better illustrate bid levels
        # Note: bid/ask_level_spreads Requires volatility, optimal_bid, optimal_ask to be defined
        self.simulate_high_volatility(self.strategy)

        self.strategy.collect_market_variables(self.strategy.current_timestamp)
        self.strategy.recalculate_parameters()
        self.strategy.calculate_reserved_price_and_optimal_spread()

        # TODO: Show exact calculation
        expected_bid_spreads = [0.0, 0.0]
        expected_ask_spreads = [0.0, 93.5]

        bid_level_spreads, ask_level_spreads = self.strategy._get_logspaced_level_spreads()
        for i, spread in enumerate(bid_level_spreads):
            self.assertAlmostEqual(expected_bid_spreads[i], spread, 1)

        for i, spread in enumerate(ask_level_spreads):
            self.assertAlmostEqual(expected_ask_spreads[i], spread, 1)

    def test_create_proposal_based_on_order_levels(self):
        # Simulate low volatility
        self.simulate_low_volatility(self.strategy)

        # Prepare market variables and parameters for calculation
        self.strategy.collect_market_variables(self.strategy.current_timestamp)
        self.strategy.recalculate_parameters()
        self.strategy.calculate_reserved_price_and_optimal_spread()

        #
        print()
        # Re-initialize strategy with order_level configurations
        self.strategy = AvellanedaMarketMakingStrategy(
            market_info=self.market_info,
            order_amount=self.order_amount,
            order_level=2,
        )

    def test_create_basic_proposal(self):
        pass

    def test_create_base_proposal(self):
        pass

    def test_get_adjusted_available_balance(self):
        expected_available_balance: Tuple[Decimal, Decimal] = (Decimal("500"), Decimal("5000"))  # Initial asset balance
        self.assertEqual(expected_available_balance, self.strategy.get_adjusted_available_balance(self.strategy.active_orders))

        # Simulate order being placed
        limit_order: LimitOrder = LimitOrder(client_order_id="test",
                                             trading_pair=self.trading_pair,
                                             is_buy=True,
                                             base_currency=self.trading_pair.split("-")[0],
                                             quote_currency=self.trading_pair.split("-")[1],
                                             price=Decimal("101.0"),
                                             quantity=Decimal("10"))

        self.simulate_place_limit_order(self.strategy, self.market_info, limit_order)

        self.assertEqual(expected_available_balance, self.strategy.get_adjusted_available_balance(self.strategy.active_orders))

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

    def test_integrated_avellaneda_strategy(self):
        # TODO: Implement an integrated test that essentially runs the entire strategy for 3 cycles

        # 1. self._all_markets_ready
        # (1) True
        # (2) False

        # 2. self.c_collect_market_variables()
        # Check if new sample has been added to the RingBuffer of the avg vol indicator
        # Check value of the self._q_adjustment_factor
        # (1) self._time_left == 0
        #     - Check if self.c_recalculate_parameters() is called and the variables have been updated
        # (2) self._time_left > 0

        # 3. self.c_is_algorithm_ready()
        #   (1) True
        #       Condition: (self._gamma is None) or (self._kappa is None) or (self._parameters_based_on_spread and (diff in vol > vol_threshold ))
        #       - self.c_recalculate_parameters
        #       - self.c_calculate_reserved_price_and_optimal_spread()
        #       - proposal = self.c_create_base_proposal()
        #       - self.c_apply_order_amount_eta_transformation(proposal)
        #       - self.c_apply_order_price_modifiers(proposal)
        #       - self.c_apply_budget_constraint(proposal)
        #       - self.c_cancel_active_orders(proposal)
        #       - refreshed_proposal = self.c_aged_order_refresh()
        #         (1) is not None
        #             - self.c_execute_order_proposal(refresh_proposal)
        #
        #       - self.c_to_create_order(proposal):
        #         (1) True
        #             - self.c_execute_order_proposal(refresh_proposal)
        #   (2) False
        #       - Update self._ticks_to_be_ready

        # Check active_orders()
        pass
