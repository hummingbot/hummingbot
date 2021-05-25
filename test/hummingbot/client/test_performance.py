from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))
from decimal import Decimal
from typing import List
import unittest
import asyncio
from unittest.mock import MagicMock, patch

from hummingbot.client.performance import (
    calculate_performance_metrics,
    position_order,
    aggregate_position_order,
    smart_round)
from hummingbot.core.data_type.trade import Trade, TradeType, TradeFee


trading_pair = "HBOT-USDT"
base, quote = trading_pair.split("-")


class PerformanceMetricsUnitTest(unittest.TestCase):

    def mock_trade(self, id, amount, price, position="OPEN", type="BUY", fee=None):
        trade = MagicMock()
        trade.order_id = id
        trade.position = position
        trade.trade_type = type
        trade.amount = amount
        trade.price = price
        if fee:
            trade.trade_fee = TradeFee.to_json(fee)

        return trade

    def test_position_order_returns_nothing_when_no_open_and_no_close_orders(self):
        tradesForOpen = [self.mock_trade(id=f"order{i}", amount=100, price=10, position="INVALID")
                         for i in range(3)]
        tradesForClose = [self.mock_trade(id=f"order{i}", amount=100, price=10, position="INVALID")
                          for i in range(2)]

        self.assertIsNone(position_order(tradesForOpen, tradesForClose))

        tradesForOpen[1].position = "OPEN"

        self.assertIsNone(position_order(tradesForOpen, tradesForClose))

        tradesForOpen[1].position = "INVALID"
        tradesForClose[-1].position = "CLOSE"

        self.assertIsNone(position_order(tradesForOpen, tradesForClose))

    def test_position_order_returns_open_and_close_pair(self):
        tradesForOpen = [self.mock_trade(id=f"order{i}", amount=100, price=10, position="INVALID")
                         for i in range(3)]
        tradesForClose = [self.mock_trade(id=f"order{i}", amount=100, price=10, position="INVALID")
                          for i in range(2)]

        tradesForOpen[1].position = "OPEN"
        tradesForClose[-1].position = "CLOSE"

        selectedOpen, selectedClose = position_order(tradesForOpen.copy(), tradesForClose.copy())
        self.assertEqual(selectedOpen, tradesForOpen[1])
        self.assertEqual(selectedClose, tradesForClose[-1])

    def test_aggregated_position_with_no_trades(self):
        aggregatedBuys, aggregatedSells = aggregate_position_order([], [])

        self.assertEqual(len(aggregatedBuys), 0)
        self.assertEqual(len(aggregatedSells), 0)

    def test_aggregated_position_for_unrelated_trades(self):
        trades = []

        trades.append(self.mock_trade(id="order1", amount=100, price=10))
        trades.append(self.mock_trade(id="order2", amount=200, price=15))
        trades.append(self.mock_trade(id="order3", amount=300, price=20))

        aggregatedBuys, aggregatedSells = aggregate_position_order(trades, [])

        self.assertEqual(aggregatedBuys, trades)
        self.assertEqual(len(aggregatedSells), 0)

        aggregatedBuys, aggregatedSells = aggregate_position_order([], trades)

        self.assertEqual(len(aggregatedBuys), 0)
        self.assertEqual(aggregatedSells, trades)

    def test_aggregated_position_with_two_related_trades_from_three(self):
        trades = []

        trades.append(self.mock_trade(id="order1", amount=100, price=10))
        trades.append(self.mock_trade(id="order2", amount=200, price=15))
        trades.append(self.mock_trade(id="order1", amount=300, price=20))

        aggregatedBuys, aggregatedSells = aggregate_position_order(trades, [])

        self.assertEqual(len(aggregatedBuys), 2)
        trade = aggregatedBuys[0]
        self.assertTrue(trade.order_id == "order1" and trade.amount == 400 and trade.price == 15)
        self.assertEqual(aggregatedBuys[1], trades[1])
        self.assertEqual(len(aggregatedSells), 0)

        trades = []

        trades.append(self.mock_trade(id="order1", amount=100, price=10))
        trades.append(self.mock_trade(id="order2", amount=200, price=15))
        trades.append(self.mock_trade(id="order1", amount=300, price=20))

        aggregatedBuys, aggregatedSells = aggregate_position_order([], trades)

        self.assertEqual(len(aggregatedBuys), 0)
        self.assertEqual(len(aggregatedSells), 2)
        trade = aggregatedSells[0]
        self.assertTrue(trade.order_id == "order1" and trade.amount == 400 and trade.price == 15)
        self.assertEqual(aggregatedSells[1], trades[1])

    def test_calculate_performance_metrics(self):
        trades: List[Trade] = [
            Trade(trading_pair, TradeType.BUY, 100, 10, None, trading_pair, 1, TradeFee(0.0, [(quote, 0)])),
            Trade(trading_pair, TradeType.SELL, 120, 15, None, trading_pair, 1, TradeFee(0.0, [(quote, 0)]))
        ]
        cur_bals = {base: 100, quote: 10000}
        metrics = asyncio.get_event_loop().run_until_complete(
            calculate_performance_metrics("hbot_exchange", trading_pair, trades, cur_bals))
        self.assertEqual(Decimal("200"), metrics.trade_pnl)
        print(metrics)

    @patch('hummingbot.client.performance.is_trade_fill')
    def test_calculate_performance_metrics_for_derivatives(self, is_trade_fill_mock):
        is_trade_fill_mock.return_value = True
        trades = []
        trades.append(self.mock_trade(id="order1",
                                      amount=100,
                                      price=10,
                                      position="OPEN",
                                      type="BUY",
                                      fee=TradeFee(0.0, [(quote, 0)])))
        trades.append(self.mock_trade(id="order2",
                                      amount=100,
                                      price=15,
                                      position="CLOSE",
                                      type="SELL",
                                      fee=TradeFee(0.0, [(quote, 0)])))
        trades.append(self.mock_trade(id="order3",
                                      amount=100,
                                      price=20,
                                      position="OPEN",
                                      type="SELL",
                                      fee=TradeFee(0.1, [("USD", 0)])))
        trades.append(self.mock_trade(id="order4",
                                      amount=100,
                                      price=15,
                                      position="CLOSE",
                                      type="BUY",
                                      fee=TradeFee(0.1, [("USD", 0)])))

        cur_bals = {base: 100, quote: 10000}
        metrics = asyncio.get_event_loop().run_until_complete(calculate_performance_metrics("hbot_exchange", trading_pair, trades, cur_bals))
        self.assertEqual(metrics.num_buys, 2)
        self.assertEqual(metrics.num_sells, 2)
        self.assertEqual(metrics.num_trades, 4)
        self.assertEqual(metrics.b_vol_base, Decimal("200"))
        self.assertEqual(metrics.s_vol_base, Decimal("-200"))
        self.assertEqual(metrics.tot_vol_base, Decimal("0"))
        self.assertEqual(metrics.b_vol_quote, Decimal("-2500"))
        self.assertEqual(metrics.s_vol_quote, Decimal("3500"))
        self.assertEqual(metrics.tot_vol_quote, Decimal("1000"))
        self.assertEqual(metrics.avg_b_price, Decimal("12.5"))
        self.assertEqual(metrics.avg_s_price, Decimal("17.5"))
        self.assertEqual(metrics.avg_tot_price, Decimal("15"))
        self.assertEqual(metrics.start_base_bal, Decimal("100"))
        self.assertEqual(metrics.start_quote_bal, Decimal("9000"))
        self.assertEqual(metrics.cur_base_bal, 100)
        self.assertEqual(metrics.cur_quote_bal, 10000),
        self.assertEqual(metrics.start_price, Decimal("10")),
        self.assertEqual(metrics.cur_price, Decimal("15"))
        self.assertEqual(metrics.trade_pnl, Decimal("1000"))
        self.assertEqual(metrics.total_pnl, Decimal("650"))

    def test_smart_round(self):
        value = smart_round(None)
        self.assertIsNone(value)
        value = smart_round(Decimal("NaN"))
        self.assertTrue(value.is_nan())

        value = smart_round(Decimal("10000.123456789"))
        self.assertEqual(value, Decimal("10000"))
        value = smart_round(Decimal("100.123456789"))
        self.assertEqual(value, Decimal("100.1"))
        value = smart_round(Decimal("1.123456789"))
        self.assertEqual(value, Decimal("1.12"))
        value = smart_round(Decimal("0.123456789"))
        self.assertEqual(value, Decimal("0.1234"))
        value = smart_round(Decimal("0.000456789"))
        self.assertEqual(value, Decimal("0.00045"))
        value = smart_round(Decimal("0.000056789"))
        self.assertEqual(value, Decimal("0.00005678"))
        value = smart_round(Decimal("0"))
        self.assertEqual(value, Decimal("0"))

        value = smart_round(Decimal("0.123456"), 2)
        self.assertEqual(value, Decimal("0.12"))
