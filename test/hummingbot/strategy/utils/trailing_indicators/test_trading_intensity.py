import math
import unittest
from decimal import Decimal

import numpy as np
import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.event.events import OrderBookTradeEvent
from hummingbot.strategy.__utils__.trailing_indicators.trading_intensity import TradingIntensityIndicator
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_book_asset_price_delegate import OrderBookAssetPriceDelegate


class TradingIntensityTest(unittest.TestCase):
    INITIAL_RANDOM_SEED = 3141592653
    BUFFER_LENGTH = 50

    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    start_timestamp: float = start.timestamp()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.trading_pair: str = "COINALPHA-HBOT"
        cls.base_asset, cls.quote_asset = cls.trading_pair.split("-")
        cls.initial_mid_price: int = 100

    def setUp(self) -> None:
        np.random.seed(self.INITIAL_RANDOM_SEED)

        trade_fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.25"), taker_percent_fee_decimal=Decimal("0.25")
        )
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.market: MockPaperExchange = MockPaperExchange(client_config_map, trade_fee_schema)
        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.market, self.trading_pair, *self.trading_pair.split("-")
        )
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.initial_mid_price,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)
        self.market.set_balance("COINALPHA", 1)
        self.market.set_balance("HBOT", 500)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair.split("-")[0], 6, 6, 6, 6
            )
        )

        self.price_delegate = OrderBookAssetPriceDelegate(self.market_info.market, self.trading_pair)

        self.indicator = TradingIntensityIndicator(
            order_book=self.market_info.order_book,
            price_delegate=self.price_delegate,
            sampling_length=self.BUFFER_LENGTH)

    @staticmethod
    def make_order_books(original_price_mid, original_spread, original_amount, volatility, spread_stdev, amount_stdev, samples):
        # 0.1% quantization of prices in the orderbook
        PRICE_STEP_FRACTION = 0.01

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

    @staticmethod
    def make_trades(bids_df, asks_df):
        # Estimate market orders that happened
        # Assume every movement in the BBO is caused by a market order and its size is the volume differential

        bid_df_prev = None
        ask_df_prev = None
        bid_prev = None
        ask_prev = None
        price_prev = None

        trades = []

        start = pd.Timestamp("2019-01-01", tz="UTC")
        start_timestamp = start.timestamp()
        timestamp = start_timestamp

        for bid_df, ask_df in zip(bids_df, asks_df):

            trades += [[]]

            bid = bid_df["price"].iloc[0]
            ask = ask_df["price"].iloc[0]

            if bid_prev is not None and ask_prev is not None and price_prev is not None:
                # Higher bids were filled - someone matched them - a determined seller
                # Equal bids - if amount lower - partially filled
                for index, row in bid_df_prev[bid_df_prev['price'] >= bid].iterrows():
                    if row['price'] == bid:
                        if bid_df["amount"].iloc[0] < row['amount']:
                            amount = row['amount'] - bid_df["amount"].iloc[0]
                            new_trade = OrderBookTradeEvent(
                                trading_pair="COINALPHAHBOT",
                                timestamp=timestamp,
                                price=row['price'],
                                amount=amount,
                                type=TradeType.SELL
                            )
                            trades[-1] += [new_trade]
                    else:
                        amount = row['amount']
                        new_trade = OrderBookTradeEvent(
                            trading_pair="COINALPHAHBOT",
                            timestamp=timestamp,
                            price=row['price'],
                            amount=amount,
                            type=TradeType.SELL
                        )
                        trades[-1] += [new_trade]

                # Lower asks were filled - someone matched them - a determined buyer
                # Equal asks - if amount lower - partially filled
                for index, row in ask_df_prev[ask_df_prev['price'] <= ask].iterrows():
                    if row['price'] == ask:
                        if ask_df["amount"].iloc[0] < row['amount']:
                            amount = row['amount'] - ask_df["amount"].iloc[0]
                            new_trade = OrderBookTradeEvent(
                                trading_pair="COINALPHAHBOT",
                                timestamp=timestamp,
                                price=row['price'],
                                amount=amount,
                                type=TradeType.BUY
                            )
                            trades[-1] += [new_trade]
                    else:
                        amount = row['amount']
                        new_trade = OrderBookTradeEvent(
                            trading_pair="COINALPHAHBOT",
                            timestamp=timestamp,
                            price=row['price'],
                            amount=amount,
                            type=TradeType.BUY
                        )
                        trades[-1] += [new_trade]

            # Store previous values
            bid_df_prev = bid_df
            ask_df_prev = ask_df
            bid_prev = bid_df["price"].iloc[0]
            ask_prev = ask_df["price"].iloc[0]
            price_prev = (bid_prev + ask_prev) / 2

            timestamp += 1

        return trades

    def test_calculate_trading_intensity_random(self):
        N_SAMPLES = 300

        original_price_mid = 100
        original_spread = Decimal("10")
        volatility = Decimal("5") / Decimal("100")
        original_amount = Decimal("1")

        spread_stdev = original_spread * Decimal("0.01")
        amount_stdev = original_amount * Decimal("0.01")

        # Generate orderbooks for all ticks
        bids_df, asks_df = TradingIntensityTest.make_order_books(original_price_mid, original_spread, original_amount, volatility, spread_stdev, amount_stdev, N_SAMPLES)
        trades = TradingIntensityTest.make_trades(bids_df, asks_df)

        timestamp = self.start_timestamp
        for bid_df, ask_df, trades_tick in zip(bids_df, asks_df, trades):
            bid = bid_df["price"].iloc[0]
            ask = ask_df["price"].iloc[0]
            mid = (bid + ask) / 2
            for trade in trades_tick:
                self.indicator.register_trade(trade)
            self.indicator.calculate(timestamp)
            self.indicator.last_quotes = [{"timestamp": timestamp, "price": mid}] + self.indicator.last_quotes
            timestamp += 1

        self.assertAlmostEqual(self.indicator.current_value[0], 1.0032422566402444, 4)
        self.assertAlmostEqual(self.indicator.current_value[1], 0.0001595577045670909, 4)

    def test_calculate_trading_intensity_deterministic(self):
        def curve_fn(t_, a_, b_):  # see curve fit in `TradingIntensityIndicator.c_estimate_intensity`
            return a_ * np.exp(-b_ * t_)

        last_price = 1
        trade_price_levels = [2, 3, 4, 5]
        a = 2
        b = 0.1
        ts = [curve_fn(p - last_price, a, b) for p in trade_price_levels]

        timestamp = self.start_timestamp

        trading_intensity_indicator = TradingIntensityIndicator(OrderBook(), self.price_delegate, 1)
        trading_intensity_indicator.last_quotes = [{"timestamp": timestamp, "price": last_price}]

        timestamp += 1

        for p, t in zip(trade_price_levels, ts):
            new_trade = OrderBookTradeEvent(
                trading_pair="COINALPHAHBOT",
                timestamp=timestamp,
                price=p,
                amount=t,
                type=TradeType.SELL,
            )
            trading_intensity_indicator.register_trade(new_trade)

        trading_intensity_indicator.calculate(timestamp)
        alpha, kappa = trading_intensity_indicator.current_value

        self.assertAlmostEqual(a, alpha, 10)
        self.assertAlmostEqual(b, kappa, 10)
