import asyncio
import time
from decimal import Decimal
from typing import List, Dict
import unittest
from hummingbot.client.performance_analysis import calculate_asset_delta_from_trades, calculate_trade_performance
from hummingbot.core.event.events import TradeFee, OrderType
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType
from hummingbot.model.trade_fill import TradeFill
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class MockMarket1(ExchangeBase):
    def __init__(self):
        super().__init__()
        self.mock_mid_price: Dict[str, float] = {
            "WETHDAI": 115.0
        }

    @property
    def display_name(self):
        return "coinalpha"

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return Decimal(repr(self.mock_mid_price[trading_pair]))


class MockMarket2(ExchangeBase):
    def __init__(self):
        super().__init__()
        self.mock_mid_price: Dict[str, float] = {
            "WETHDAI": 110.0
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
        cls._weth_price = 1.0
        cls._eth_price = 1.0
        cls._dai_price = 0.95
        cls._usdc_price = 1.05
        cls.trading_pair_tuple_1 = MarketTradingPairTuple(MockMarket1(), "WETHDAI", "WETH", "DAI")
        cls.trading_pair_tuple_2 = MarketTradingPairTuple(MockMarket2(), "WETHDAI", "WETH", "DAI")
        cls.strategy_1 = "strategy_1"

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
            ("BUY", 100, 1),
            ("SELL", 100, 0.9),
            ("BUY", 110, 1),
            ("SELL", 115, 1)
        ]
        start_time = int(time.time() * 1e3) - 100000
        self.save_trade_fill_records(test_trades,
                                     self.trading_pair_tuple_1,
                                     OrderType.MARKET.name,
                                     start_time,
                                     self.strategy_1)

        raw_queried_trades = self.get_trades_from_session(start_time)
        m_name = self.trading_pair_tuple_1.market.name
        starting_balances = {"DAI": {m_name: Decimal("1000")}, "WETH": {m_name: Decimal("5")}}
        trade_performance_stats, market_trading_pair_stats = calculate_trade_performance(
            self.strategy_1, [self.trading_pair_tuple_1], raw_queried_trades, starting_balances
        )

        expected_trade_performance_stats = {
            'portfolio_acquired_quote_value': Decimal('430.6500'),
            'portfolio_spent_quote_value': Decimal('428.50'),
            'portfolio_delta': Decimal('2.1500'),
            'portfolio_delta_percentage': Decimal('0.1365079365079365079365079365')}

        expected_market_trading_pair_stats = {
            'starting_quote_rate': Decimal('100.0'),
            'asset': {
                'WETH': {'spent': Decimal('1.9'), 'acquired': Decimal('1.980'),
                         'delta': Decimal('0.080'),
                         'delta_percentage': Decimal('4.210526315789473684210526300')},
                'DAI': {'spent': Decimal('210.00'), 'acquired': Decimal('202.9500'),
                        'delta': Decimal('-7.0500'),
                        'delta_percentage': Decimal('-3.357142857142857142857142860')}},
            'trade_count': 4,
            'end_quote_rate': Decimal('115.0'), 'acquired_quote_value': Decimal('430.6500'),
            'spent_quote_value': Decimal('428.50'), 'starting_quote_value': Decimal('1575.0'),
            'trading_pair_delta': Decimal('2.1500'),
            'trading_pair_delta_percentage': Decimal('0.1365079365079365079365079365')}

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
        raw_queried_trades = self.get_trades_from_session(start_time)
        market_trading_pair_stats = calculate_asset_delta_from_trades(
            self.strategy_1, [self.trading_pair_tuple_1], raw_queried_trades
        )

        expected_stats = {
            'starting_quote_rate': Decimal('1.0'),
            'asset': {'WETH': {'spent': Decimal('230.0'), 'acquired': Decimal('198.000')},
                      'DAI': {'spent': Decimal('110.00'), 'acquired': Decimal('216.8100')}},
            'trade_count': 4
        }
        self.assertDictEqual(expected_stats, market_trading_pair_stats[self.trading_pair_tuple_1])

    def test_calculate_trade_performance(self):
        test_trades = [
            ("BUY", 100, 2),
            ("SELL", 110, 0.9),
            ("BUY", 105, 0.5),
            ("SELL", 120, 1)
        ]
        start_time = int(time.time() * 1e3) - 100000
        self.save_trade_fill_records(test_trades,
                                     self.trading_pair_tuple_1,
                                     OrderType.MARKET.name,
                                     start_time,
                                     self.strategy_1
                                     )
        raw_queried_trades = self.get_trades_from_session(start_time)
        m_name = self.trading_pair_tuple_1.market.name
        starting_balances = {"DAI": {m_name: Decimal("1000")}, "WETH": {m_name: Decimal("5")}}
        trade_performance_stats, market_trading_pair_stats = calculate_trade_performance(
            self.strategy_1, [self.trading_pair_tuple_1], raw_queried_trades, starting_balances
        )

        expected_trade_performance_stats = {
            'portfolio_acquired_quote_value': Decimal('501.4350'),
            'portfolio_spent_quote_value': Decimal('471.00'),
            'portfolio_delta': Decimal('30.4350'),
            'portfolio_delta_percentage': Decimal('1.932380952380952380952380952')
        }
        expected_market_trading_pair_stats = {
            'starting_quote_rate': Decimal('100.0'),
            'asset': {
                'WETH': {'spent': Decimal('1.9'), 'acquired': Decimal('2.475'), 'delta': Decimal('0.575'),
                         'delta_percentage': Decimal('30.26315789473684210526315790')},
                'DAI': {'spent': Decimal('252.50'), 'acquired': Decimal('216.8100'), 'delta': Decimal('-35.6900'),
                        'delta_percentage': Decimal(
                            '-14.13465346534653465346534653')}},
            'trade_count': 4,
            'end_quote_rate': Decimal('115.0'),
            'acquired_quote_value': Decimal('501.4350'),
            'spent_quote_value': Decimal('471.00'),
            'starting_quote_value': Decimal('1575.0'),
            'trading_pair_delta': Decimal('30.4350'),
            'trading_pair_delta_percentage': Decimal('1.932380952380952380952380952')
        }
        self.assertDictEqual(expected_trade_performance_stats, trade_performance_stats)
        self.assertDictEqual(expected_market_trading_pair_stats, market_trading_pair_stats[self.trading_pair_tuple_1])

    def test_multiple_market(self):
        test_trades_1 = [
            ("BUY", 100, 1),
            ("SELL", 100, 0.9),
            ("BUY", 110, 1),
            ("SELL", 115, 1)
        ]
        start_time = int(time.time() * 1e3) - 100000
        self.save_trade_fill_records(test_trades_1,
                                     self.trading_pair_tuple_1,
                                     OrderType.MARKET.name,
                                     start_time,
                                     self.strategy_1
                                     )
        test_trades_2 = [
            ("BUY", 100, 2),
            ("SELL", 110, 0.9),
            ("BUY", 105, 0.5),
            ("SELL", 120, 1)
        ]
        self.save_trade_fill_records(test_trades_2,
                                     self.trading_pair_tuple_2,
                                     OrderType.MARKET.name,
                                     start_time,
                                     self.strategy_1
                                     )
        raw_queried_trades = self.get_trades_from_session(start_time)
        m_name_1 = self.trading_pair_tuple_1.market.name
        m_name_2 = self.trading_pair_tuple_2.market.name

        starting_balances = {"DAI": {m_name_1: Decimal("1000"), m_name_2: Decimal("500")},
                             "WETH": {m_name_1: Decimal("5"), m_name_2: Decimal("1")}}
        trade_performance_stats, market_trading_pair_stats = calculate_trade_performance(
            self.strategy_1, [self.trading_pair_tuple_1, self.trading_pair_tuple_2], raw_queried_trades,
            starting_balances
        )

        expected_trade_performance_stats = {
            'portfolio_acquired_quote_value': Decimal('919.7100'),
            'portfolio_spent_quote_value': Decimal('890.00'),
            'portfolio_delta': Decimal('29.7100'),
            'portfolio_delta_percentage': Decimal('1.359725400457665903890160183')
        }
        expected_markettrading_pair_stats_1 = {
            'starting_quote_rate': Decimal('100.0'),
            'asset': {
                'WETH': {'spent': Decimal('1.9'), 'acquired': Decimal('1.980'), 'delta': Decimal('0.080'),
                         'delta_percentage': Decimal('4.210526315789473684210526300')},
                'DAI': {'spent': Decimal('210.00'), 'acquired': Decimal('202.9500'), 'delta': Decimal('-7.0500'),
                        'delta_percentage': Decimal(
                            '-3.357142857142857142857142860')}
            },
            'trade_count': 4,
            'end_quote_rate': Decimal('115.0'),
            'acquired_quote_value': Decimal('430.6500'),
            'spent_quote_value': Decimal('428.50'),
            'starting_quote_value': Decimal('1575.0'),
            'trading_pair_delta': Decimal('2.1500'),
            'trading_pair_delta_percentage': Decimal('0.1365079365079365079365079365')
        }
        expected_markettrading_pair_stats_2 = {
            'starting_quote_rate': Decimal('100.0'),
            'asset': {
                'WETH': {'spent': Decimal('1.9'), 'acquired': Decimal('2.475'), 'delta': Decimal('0.575'),
                         'delta_percentage': Decimal('30.26315789473684210526315790')},
                'DAI': {'spent': Decimal('252.50'), 'acquired': Decimal('216.8100'), 'delta': Decimal('-35.6900'),
                        'delta_percentage': Decimal('-14.13465346534653465346534653')}},
            'trade_count': 4,
            'end_quote_rate': Decimal('110.0'),
            'acquired_quote_value': Decimal('489.0600'),
            'spent_quote_value': Decimal('461.50'),
            'starting_quote_value': Decimal('610.0'),
            'trading_pair_delta': Decimal('27.5600'),
            'trading_pair_delta_percentage': Decimal('4.518032786885245901639344262')
        }
        self.assertDictEqual(expected_trade_performance_stats, trade_performance_stats)
        self.assertDictEqual(expected_markettrading_pair_stats_1, market_trading_pair_stats[self.trading_pair_tuple_1])
        self.assertDictEqual(expected_markettrading_pair_stats_2, market_trading_pair_stats[self.trading_pair_tuple_2])
