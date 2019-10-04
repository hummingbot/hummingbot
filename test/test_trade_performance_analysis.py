import asyncio
import time
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

    def get_price(self, symbol):
        return self.mock_price_dict.get(symbol.upper())


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

    def get_mid_price(self, trading_pair: str) -> float:
        return self.mock_mid_price[trading_pair]


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

    def get_mid_price(self, trading_pair: str) -> float:
        return self.mock_mid_price[trading_pair]


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
                                     self.strategy_1
                                     )

        performance_analysis = PerformanceAnalysis(sql=self.trade_fill_sql)
        trade_performance_stats, market_trading_pair_stats = performance_analysis.calculate_trade_performance(
            start_time, self.strategy_1, [self.trading_pair_tuple_1]
        )

        expected_trade_performance_stats = {
            "portfolio_acquired_quote_value": 24111.45,
            "portfolio_spent_quote_value": 24935.0,
            "portfolio_delta": -823.5499999999993,
            "portfolio_delta_percentage": -3.3027872468417874
        }
        expected_market_trading_pair_stats = {
            "starting_quote_rate": 1.0,
            "asset": {
                "WETH": {
                    "spent": 215.0,
                    "acquired": 207.9,
                    "delta": -7.099999999999994,
                    "delta_percentage": -3.302325581395349
                },
                "DAI": {
                    "spent": 210.0,
                    "acquired": 202.95,
                    "delta": -7.050000000000011,
                    "delta_percentage": -3.3571428571428585
                }
            },
            "end_quote_rate": 115.0,
            "acquired_quote_value": 24111.45,
            "spent_quote_value": 24935.0,
            "trading_pair_delta": -823.5499999999993,
            "trading_pair_delta_percentage": -3.3027872468417874
        }

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
        market_trading_pair_stats = performance_analysis.calculate_asset_delta_from_trades(
            start_time, self.strategy_1, [self.trading_pair_tuple_1]
        )
        expected_stats = {
            "starting_quote_rate": 1.0,
            "asset": {
                "WETH": {
                    "spent": 230.0,
                    "acquired": 198.0
                },
                "DAI": {
                    "spent": 110.0,
                    "acquired": 216.81
                }
            }
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
        trade_performance_stats, market_trading_pair_stats = performance_analysis.calculate_trade_performance(
            start_time, self.strategy_1, [self.trading_pair_tuple_1]
        )

        expected_trade_performance_stats = {
            "portfolio_acquired_quote_value": 23556.06,
            "portfolio_spent_quote_value": 26702.5,
            "portfolio_delta": -3146.4399999999987,
            "portfolio_delta_percentage": -11.78331616889804
        }
        expected_market_trading_pair_stats = {
            "starting_quote_rate": 2.0,
            "asset": {
                "WETH": {
                    "spent": 230.0,
                    "acquired": 202.95,
                    "delta": -27.05000000000001,
                    "delta_percentage": -11.76086956521739
                },
                "DAI": {
                    "spent": 252.5,
                    "acquired": 216.81,
                    "delta": -35.69,
                    "delta_percentage": -14.134653465346537
                }
            },
            "end_quote_rate": 115.0,
            "acquired_quote_value": 23556.06,
            "spent_quote_value": 26702.5,
            "trading_pair_delta": -3146.4399999999987,
            "trading_pair_delta_percentage": -11.78331616889804
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
        trade_performance_stats, market_trading_pair_stats = performance_analysis.calculate_trade_performance(
            start_time, self.strategy_1, [self.trading_pair_tuple_1, self.trading_pair_tuple_2]
        )

        expected_trade_performance_stats = {
            "portfolio_acquired_quote_value": 49025.52947368422,
            "portfolio_spent_quote_value": 53177.23684210527,
            "portfolio_delta": -4151.707368421048,
            "portfolio_delta_percentage": -7.807301798602973
        }
        expected_markettrading_pair_stats_1 = {
            "starting_quote_rate": 1.0,
            "asset": {
                "WETH": {
                    "spent": 215.0,
                    "acquired": 207.9,
                    "delta": -7.099999999999994,
                    "delta_percentage": -3.302325581395349
                },
                "DAI": {
                    "spent": 210.0,
                    "acquired": 202.95,
                    "delta": -7.050000000000011,
                    "delta_percentage": -3.3571428571428585
                }
            },
            "end_quote_rate": 115.0,
            "acquired_quote_value": 24111.45,
            "spent_quote_value": 24935.0,
            "trading_pair_delta": -823.5499999999993,
            "trading_pair_delta_percentage": -3.3027872468417874
        }

        expected_markettrading_pair_stats_2 = {
            "starting_quote_rate": 2.0,
            "asset": {
                "ETH": {
                    "spent": 230.0,
                    "acquired": 202.95,
                    "delta": -27.05000000000001,
                    "delta_percentage": -11.76086956521739
                },
                "USDC": {
                    "spent": 252.5,
                    "acquired": 216.81,
                    "delta": -35.69,
                    "delta_percentage": -14.134653465346537
                }
            },
            "end_quote_rate": 110.0,
            "acquired_quote_value": 24914.079473684214,
            "spent_quote_value": 28242.236842105263,
            "trading_pair_delta": -3011.1899999999987,
            "trading_pair_delta_percentage": -11.784326386850596
        }
        self.assertDictEqual(expected_trade_performance_stats, trade_performance_stats)
        self.assertDictEqual(expected_markettrading_pair_stats_1, market_trading_pair_stats[self.trading_pair_tuple_1])
        self.assertDictEqual(expected_markettrading_pair_stats_2, market_trading_pair_stats[self.trading_pair_tuple_2])
