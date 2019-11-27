import asyncio
import time
from decimal import Decimal
from typing import List, Dict
import unittest
from hummingbot.client.performance_analysis import PerformanceAnalysis
from hummingbot.core.event.events import TradeFee, OrderType
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)

from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.market.market_base import MarketBase
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType
from hummingbot.model.trade_fill import TradeFill
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class MockDataFeed1(DataFeedBase):
    _mdf_shared_instance: "MockDataFeed1" = None

    @classmethod
    def get_instance(cls) -> "MockDataFeed1":
        if cls._mdf_shared_instance is None:
            cls._mdf_shared_instance = MockDataFeed1()
        return cls._mdf_shared_instance

    @property
    def name(self):
        return "coin_alpha_feed"

    @property
    def price_dict(self):
        return self.mock_price_dict

    def __init__(self):
        super().__init__()
        self.mock_price_dict = {
            "WETH": 1.0,
            "ETH": 1.0,
            "DAI": 0.95,
            "USDC": 1.05,
            "USD": 1.0
        }

    def get_price(self, trading_pair):
        return self.mock_price_dict.get(trading_pair.upper())

    async def start_network(self):
        pass

    async def stop_network(self):
        pass


class MockMarket1(MarketBase):
    def __init__(self):
        super().__init__()
        self.mock_mid_price: Dict[str, float] = {
            "WETHDAI": 115.0,
            "ETHUSDC": 110.0
        }

    @property
    def display_name(self):
        return "coinalpha"

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return Decimal(repr(self.mock_mid_price[trading_pair]))


class MockMarket2(MarketBase):
    def __init__(self):
        super().__init__()
        self.mock_mid_price: Dict[str, float] = {
            "WETHDAI": 115.0,
            "ETHUSDC": 110.0
        }

    @property
    def display_name(self):
        return "coinalpha2"

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return Decimal(repr(self.mock_mid_price[trading_pair]))


class TestTradePerformanceAnalysis(unittest.TestCase):
    @staticmethod
    async def run_parallel_async(*tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    @classmethod
    def setUpClass(cls):
        cls.maxDiff = None
        cls.trade_fill_sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path="")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        ExchangeRateConversion.get_instance().set_data_feeds([MockDataFeed1.get_instance()])
        cls._weth_price = 1.0
        cls._eth_price = 1.0
        cls._dai_price = 0.95
        cls._usdc_price = 1.05

        cls.trading_pair_tuple_1 = MarketTradingPairTuple(MockMarket1(), "WETHDAI", "WETH", "DAI")
        cls.trading_pair_tuple_2 = MarketTradingPairTuple(MockMarket2(), "ETHUSDC", "ETH", "USDC")
        cls.strategy_1 = "strategy_1"
        ExchangeRateConversion.set_global_exchange_rate_config({
            "default_data_feed": "coin_alpha_feed"
        })
        ExchangeRateConversion.get_instance().start()
        cls.ev_loop.run_until_complete(cls.run_parallel_async(ExchangeRateConversion.get_instance().wait_till_ready()))

    def setUp(self):
        for table in [TradeFill.__table__]:
            self.trade_fill_sql.get_shared_session().execute(table.delete())

    def create_trade_fill_records(self,
                                  trade_price_amount_list,
                                  market_trading_pair_tuple: MarketTradingPairTuple,
                                  order_type,
                                  start_time,
                                  strategy):
        for i, trade_data in enumerate(trade_price_amount_list):
            yield {
                "config_file_path": "path",
                "strategy": strategy,
                "market": market_trading_pair_tuple.market.display_name,
                "symbol": market_trading_pair_tuple.trading_pair,
                "base_asset": market_trading_pair_tuple.base_asset,
                "quote_asset": market_trading_pair_tuple.quote_asset,
                "timestamp": start_time + i + 1,
                "order_id": f"{i}_{market_trading_pair_tuple.trading_pair}",
                "trade_type": trade_data[0],
                "order_type": order_type,
                "price": float(trade_data[1]),
                "amount": float(trade_data[2]),
                "trade_fee": TradeFee.to_json(TradeFee(0.01)),
                "exchange_trade_id": f"{i}_{market_trading_pair_tuple.trading_pair}"
            }

    def save_trade_fill_records(self,
                                trade_price_amount_list,
                                market_trading_pair_tuple: MarketTradingPairTuple,
                                order_type,
                                start_time,
                                strategy):
        trade_records: List[TradeFill] = []
        for trade in self.create_trade_fill_records(trade_price_amount_list, market_trading_pair_tuple, order_type,
                                                    start_time, strategy):
            trade_records.append(TradeFill(**trade))
        self.trade_fill_sql.get_shared_session().add_all(trade_records)

    def get_trades_from_session(self, start_timestamp: int) -> List[TradeFill]:
        session = self.trade_fill_sql.get_shared_session()
        query = (session
                 .query(TradeFill)
                 .filter(TradeFill.timestamp >= start_timestamp)
                 .order_by(TradeFill.timestamp.desc()))
        result: List[TradeFill] = query.all() or []
        result.reverse()
        return result

    def test_calculate_trade_quote_delta_with_fees(self):
        test_trades = [
            ("BUY", 1, 100),
            ("SELL", 0.9, 100),
            ("BUY", 1, 110),
            ("SELL", 1, 115)
        ]
        start_time = int(time.time() * 1e3) - 100000
        self.save_trade_fill_records(test_trades,
                                     self.trading_pair_tuple_1,
                                     OrderType.MARKET.name,
                                     start_time,
                                     self.strategy_1)

        raw_queried_trades = self.get_trades_from_session(start_time)
        performance_analysis = PerformanceAnalysis(sql=self.trade_fill_sql)
        trade_performance_stats, market_trading_pair_stats = performance_analysis.calculate_trade_performance(
            self.strategy_1, [self.trading_pair_tuple_1], raw_queried_trades,
        )

        expected_trade_performance_stats = {
            "portfolio_acquired_quote_value": Decimal("24111.45"),
            "portfolio_delta": Decimal("-823.55"),
            "portfolio_delta_percentage": Decimal("-3.302787246841788650491277320"),
            "portfolio_spent_quote_value": Decimal("24935.0")}

        expected_market_trading_pair_stats = {
            "acquired_quote_value": Decimal("24111.45"),
            "asset": {
                "DAI": {
                    "acquired": Decimal("202.9500000000000021555673912"),
                    "delta": Decimal("-7.0499999999999978444326088"),
                    "delta_percentage": Decimal("-3.357142857142856116396480380"),
                    "spent": Decimal("210")},
                "WETH": {
                    "acquired": Decimal("207.8999999999999999562849684"),
                    "delta": Decimal("-7.1000000000000000437150316"),
                    "delta_percentage": Decimal("-3.302325581395348857541875160"),
                    "spent": Decimal("215")}},
            "end_quote_rate": Decimal("115.0"),
            "spent_quote_value": Decimal("24935.0"),
            "starting_quote_rate": Decimal("1.0"),
            "trading_pair_delta": Decimal("-823.55000000000000287166124"),
            "trading_pair_delta_percentage": Decimal("-3.302787246841788662007865410")}

        self.assertDictEqual(trade_performance_stats, expected_trade_performance_stats)
        self.assertDictEqual(expected_market_trading_pair_stats, market_trading_pair_stats[self.trading_pair_tuple_1])

    def test_calculate_asset_delta_from_trades(self):
        test_trades = [
            ("BUY", 1, 100),
            ("SELL", 0.9, 110),
            ("BUY", 0.1, 100),
            ("SELL", 1, 120)
        ]
        start_time = int(time.time() * 1e3) - 100000
        self.save_trade_fill_records(test_trades,
                                     self.trading_pair_tuple_1,
                                     OrderType.MARKET.name,
                                     start_time,
                                     self.strategy_1
                                     )

        performance_analysis = PerformanceAnalysis(sql=self.trade_fill_sql)
        raw_queried_trades = self.get_trades_from_session(start_time)
        market_trading_pair_stats = performance_analysis.calculate_asset_delta_from_trades(
            self.strategy_1, [self.trading_pair_tuple_1], raw_queried_trades
        )

        expected_stats = {
            'asset': {
                'DAI': {
                    'acquired': Decimal('216.8100000000000023724772146'),
                    'spent': Decimal('110.0000000000000005551115123')
                },
                'WETH': {
                    'acquired': Decimal('197.9999999999999999583666366'),
                    'spent': Decimal('230')
                }
            },
            'starting_quote_rate': Decimal('1.0')
        }
        self.assertDictEqual(expected_stats, market_trading_pair_stats[self.trading_pair_tuple_1])

    def test_calculate_trade_performance(self):
        test_trades = [
            ("BUY", 2, 100),
            ("SELL", 0.9, 110),
            ("BUY", 0.5, 105),
            ("SELL", 1, 120)
        ]
        start_time = int(time.time() * 1e3) - 100000
        self.save_trade_fill_records(test_trades,
                                     self.trading_pair_tuple_1,
                                     OrderType.MARKET.name,
                                     start_time,
                                     self.strategy_1
                                     )

        performance_analysis = PerformanceAnalysis(sql=self.trade_fill_sql)
        raw_queried_trades = self.get_trades_from_session(start_time)
        trade_performance_stats, market_trading_pair_stats = performance_analysis.calculate_trade_performance(
            self.strategy_1, [self.trading_pair_tuple_1], raw_queried_trades,
        )

        expected_trade_performance_stats = {
            'portfolio_acquired_quote_value': Decimal('23556.06'),
            'portfolio_delta': Decimal('-3146.44'),
            'portfolio_delta_percentage': Decimal('-11.78331616889804325437693100'),
            'portfolio_spent_quote_value': Decimal('26702.5')
        }
        expected_market_trading_pair_stats = {
            'acquired_quote_value': Decimal('23556.06'),
            'asset': {
                'DAI': {
                    'acquired': Decimal('216.8100000000000023724772146'),
                    'delta': Decimal('-35.6899999999999976275227854'),
                    'delta_percentage': Decimal('-14.13465346534653371387041006'),
                    'spent': Decimal('252.5')
                },
                'WETH': {
                    'acquired': Decimal('202.9499999999999999573258025'),
                    'delta': Decimal('-27.0500000000000000426741975'),
                    'delta_percentage': Decimal('-11.76086956521739132290182500'),
                    'spent': Decimal('230')}},
            'end_quote_rate': Decimal('115.0'),
            'spent_quote_value': Decimal('26702.5'),
            'starting_quote_rate': Decimal('2.0'),
            'trading_pair_delta': Decimal('-3146.44000000000000253505550'),
            'trading_pair_delta_percentage': Decimal('-11.78331616889804326387063196')
        }

        self.assertDictEqual(expected_trade_performance_stats, trade_performance_stats)
        self.assertDictEqual(expected_market_trading_pair_stats, market_trading_pair_stats[self.trading_pair_tuple_1])

    def test_multiple_market(self):
        test_trades_1 = [
            ("BUY", 1, 100),
            ("SELL", 0.9, 100),
            ("BUY", 1, 110),
            ("SELL", 1, 115)
        ]
        start_time = int(time.time() * 1e3) - 100000
        self.save_trade_fill_records(test_trades_1,
                                     self.trading_pair_tuple_1,
                                     OrderType.MARKET.name,
                                     start_time,
                                     self.strategy_1
                                     )
        test_trades_2 = [
            ("BUY", 2, 100),
            ("SELL", 0.9, 110),
            ("BUY", 0.5, 105),
            ("SELL", 1, 120)
        ]
        self.save_trade_fill_records(test_trades_2,
                                     self.trading_pair_tuple_2,
                                     OrderType.MARKET.name,
                                     start_time,
                                     self.strategy_1
                                     )

        performance_analysis = PerformanceAnalysis(sql=self.trade_fill_sql)
        raw_queried_trades = self.get_trades_from_session(start_time)
        trade_performance_stats, market_trading_pair_stats = performance_analysis.calculate_trade_performance(
            self.strategy_1, [self.trading_pair_tuple_1, self.trading_pair_tuple_2], raw_queried_trades
        )

        expected_trade_performance_stats = {
            'portfolio_acquired_quote_value': Decimal('49025.529473684214'),
            'portfolio_delta': Decimal('-4151.707368421049'),
            'portfolio_delta_percentage': Decimal('-7.807301798602976761843492980'),
            'portfolio_spent_quote_value': Decimal('53177.236842105263')
        }
        expected_markettrading_pair_stats_1 = {
            'acquired_quote_value': Decimal('24111.45'),
            'asset': {
                'DAI': {
                    'acquired': Decimal('202.9500000000000021555673912'),
                    'delta': Decimal('-7.0499999999999978444326088'),
                    'delta_percentage': Decimal('-3.357142857142856116396480380'),
                    'spent': Decimal('210')
                },
                'WETH': {
                    'acquired': Decimal('207.8999999999999999562849684'),
                    'delta': Decimal('-7.1000000000000000437150316'),
                    'delta_percentage': Decimal('-3.302325581395348857541875160'),
                    'spent': Decimal('215')}},
            'end_quote_rate': Decimal('115.0'),
            'spent_quote_value': Decimal('24935.0'),
            'starting_quote_rate': Decimal('1.0'),
            'trading_pair_delta': Decimal('-823.55000000000000287166124'),
            'trading_pair_delta_percentage': Decimal('-3.302787246841788662007865410')
        }
        expected_markettrading_pair_stats_2 = {
            'acquired_quote_value': Decimal('24914.079473684214'),
            'asset': {
                'ETH': {
                    'acquired': Decimal('202.9499999999999999573258025'),
                    'delta': Decimal('-27.0500000000000000426741975'),
                    'delta_percentage': Decimal('-11.76086956521739132290182500'),
                    'spent': Decimal('230')},
                'USDC': {
                    'acquired': Decimal('216.8100000000000023724772146'),
                    'delta': Decimal('-35.6899999999999976275227854'),
                    'delta_percentage': Decimal('-14.13465346534653371387041006'),
                    'spent': Decimal('252.5')}},
            'end_quote_rate': Decimal('110.0'),
            'spent_quote_value': Decimal('28242.236842105263'),
            'starting_quote_rate': Decimal('2.0'),
            'trading_pair_delta': Decimal('-3011.19000000000000232168451'),
            'trading_pair_delta_percentage': Decimal('-11.78432638685060171146339697')
        }
        self.assertDictEqual(expected_trade_performance_stats, trade_performance_stats)
        self.assertDictEqual(expected_markettrading_pair_stats_1, market_trading_pair_stats[self.trading_pair_tuple_1])
        self.assertDictEqual(expected_markettrading_pair_stats_2, market_trading_pair_stats[self.trading_pair_tuple_2])
