from decimal import Decimal
import math
import numpy as np
import pandas as pd
import unittest
from hummingbot.strategy.__utils__.trailing_indicators.trading_intensity import TradingIntensityIndicator


class TradingIntensityTest(unittest.TestCase):
    INITIAL_RANDOM_SEED = 3141592653
    BUFFER_LENGTH = 200

    def setUp(self) -> None:
        np.random.seed(self.INITIAL_RANDOM_SEED)

    @staticmethod
    def make_order_books(original_price_mid, original_spread, original_amount, volatility, spread_stdev, amount_stdev, samples):
        # 0.1% quantization of prices in the orderbook
        PRICE_STEP_FRACTION = 0.001

        # Generate BBO quotes
        samples_mid = np.random.normal(original_price_mid, volatility * original_price_mid, samples)
        samples_spread = np.random.normal(original_spread, spread_stdev, samples)

        samples_price_bid = np.subtract(samples_mid, np.divide(samples_spread, 2))
        samples_price_ask = np.add(samples_mid, np.divide(samples_spread, 2))

        samples_amount_bid = np.random.normal(original_amount, amount_stdev, samples)
        samples_amount_ask = np.random.normal(original_amount, amount_stdev, samples)

        # A full orderbook is not necessary, only up to the BBO max deviation
        price_depth_max = max(max(samples_price_bid) - min(samples_price_bid), max(samples_price_ask) - min(samples_price_ask))

        bid_dfs = []
        ask_dfs = []

        # Generate an orderbook for every tick
        for price_bid, amount_bid, price_ask, amount_ask in zip(samples_price_bid, samples_amount_bid, samples_price_ask, samples_amount_ask):
            bid_df, ask_df = TradingIntensityTest.make_order_book(price_bid, amount_bid, price_ask, amount_ask, price_depth_max, original_price_mid * PRICE_STEP_FRACTION, amount_stdev)
            bid_dfs += [bid_df]
            ask_dfs += [ask_df]

        return bid_dfs, ask_dfs

    @staticmethod
    def make_order_book(price_bid, amount_bid, price_ask, amount_ask, price_depth, price_step, amount_stdev, ):

        prices_bid = np.linspace(price_bid, price_bid - price_depth, math.ceil(price_depth / price_step))
        amounts_bid = np.random.normal(amount_bid, amount_stdev, len(prices_bid))
        amounts_bid[0] = amount_bid

        prices_ask = np.linspace(price_ask, price_ask + price_depth, math.ceil(price_depth / price_step))
        amounts_ask = np.random.normal(amount_ask, amount_stdev, len(prices_ask))
        amounts_ask[0] = amount_ask

        data_bid = {'price': prices_bid, 'amount': amounts_bid}
        bid_df = pd.DataFrame(data=data_bid)

        data_ask = {'price': prices_ask, 'amount': amounts_ask}
        ask_df = pd.DataFrame(data=data_ask)

        return bid_df, ask_df

    def test_calculate_trading_intensity(self):
        N_SAMPLES = 1000

        self.indicator = TradingIntensityIndicator(self.BUFFER_LENGTH)

        original_price_mid = 100
        original_spread = Decimal("10")
        volatility = Decimal("5") / Decimal("100")
        original_amount = Decimal("1")

        spread_stdev = original_spread * Decimal("0.01")
        amount_stdev = original_amount * Decimal("0.01")

        # Generate orderbooks for all ticks
        bids_df, asks_df = TradingIntensityTest.make_order_books(original_price_mid, original_spread, original_amount, volatility, spread_stdev, amount_stdev, N_SAMPLES)

        for bid_df, ask_df in zip(bids_df, asks_df):
            snapshot = (bid_df, ask_df)
            self.indicator.add_sample(snapshot)

        self.assertAlmostEqual(self.indicator.current_value[0], 1.0006118838992204, 4)
        self.assertAlmostEqual(self.indicator.current_value[1], 0.00016076949224819458, 4)
