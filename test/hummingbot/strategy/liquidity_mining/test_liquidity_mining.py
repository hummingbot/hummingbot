from decimal import Decimal
import pandas as pd
import unittest

from hummingbot.connector.exchange.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import PaperTradeExchange
from hummingbot.connector.exchange.paper_trade.market_config import MarketConfig
from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.liquidity_mining.liquidity_mining import LiquidityMiningStrategy

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader


class LiquidityMiningTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "HBOT-ETH"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    def setUp(self) -> None:
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.market: BacktestMarket = BacktestMarket()
        self.book_data: MockOrderBookLoader = MockOrderBookLoader(self.trading_pair, self.base_asset, self.quote_asset)
        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 30
        self.book_data.set_balanced_order_book(mid_price=self.mid_price,
                                               min_price=1,
                                               max_price=200,
                                               price_step_size=1,
                                               volume_step_size=10)
        self.market.add_data(self.book_data)
        self.market.set_balance("USDT", 500)
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

        paper_trade_exchange: PaperTradeExchange = PaperTradeExchange(
            order_book_tracker=BinanceOrderBookTracker(trading_pairs=["ETH-USDT", "BTC-USDT"]),
            config=MarketConfig.default_config(),
            target_market=BinanceExchange
        )

        self.default_strategy = LiquidityMiningStrategy(
            exchange=paper_trade_exchange,
            market_infos=[self.market_info],
            token="USDT",
            order_amount=Decimal(10),
            spread=Decimal(0.5),
            inventory_skew_enabled=False,
            target_base_pct=Decimal(0.5),
            order_refresh_time=60,
            order_refresh_tolerance_pct=Decimal(0.1)
            # inventory_range_multiplier: Decimal = Decimal("1"),
            # volatility_interval: int = 60 * 5,
            # avg_volatility_period: int = 10,
            # volatility_to_spread_multiplier: Decimal = Decimal("1"),
            # max_spread: Decimal = Decimal("-1"),
            # max_order_age: float = 60. * 60.,
            # status_report_interval: float = 900,
            # hb_app_notification: bool = False
        )

    def tearDown(self) -> None:
        pass

    def test_do_nothing(self):
        self.assertEqual(1, 1)
