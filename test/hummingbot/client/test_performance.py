import asyncio
import time
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import MagicMock, patch

from hummingbot.client.performance import PerformanceMetrics
from hummingbot.core.data_type.common import PositionAction, OrderType, TradeType
from hummingbot.core.data_type.trade import Trade
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.model.order import Order  # noqa — Order needs to be defined for TradeFill
from hummingbot.model.order_status import OrderStatus  # noqa — Order needs to be defined for TradeFill
from hummingbot.model.trade_fill import TradeFill

trading_pair = "HBOT-USDT"
base, quote = trading_pair.split("-")


class PerformanceMetricsUnitTest(unittest.TestCase):

    def tearDown(self) -> None:
        RateOracle._shared_instance = None
        super().tearDown()

    def mock_trade(self, id, amount, price, position="OPEN", type="BUY", fee=None):
        trade = MagicMock()
        trade.order_id = id
        trade.position = position
        trade.trade_type = type
        trade.amount = amount
        trade.price = price
        if fee:
            trade.trade_fee = fee.to_json()

        return trade

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_position_order_returns_nothing_when_no_open_and_no_close_orders(self):
        trade_for_open = [self.mock_trade(id=f"order{i}", amount=100, price=10, position="INVALID")
                          for i in range(3)]
        trades_for_close = [self.mock_trade(id=f"order{i}", amount=100, price=10, position="INVALID")
                            for i in range(2)]

        self.assertIsNone(PerformanceMetrics.position_order(trade_for_open, trades_for_close))

        trade_for_open[1].position = "OPEN"

        self.assertIsNone(PerformanceMetrics.position_order(trade_for_open, trades_for_close))

        trade_for_open[1].position = "INVALID"
        trades_for_close[-1].position = "CLOSE"

        self.assertIsNone(PerformanceMetrics.position_order(trade_for_open, trades_for_close))

    def test_position_order_returns_open_and_close_pair(self):
        trades_for_open = [self.mock_trade(id=f"order{i}", amount=100, price=10, position="INVALID")
                           for i in range(3)]
        trades_for_close = [self.mock_trade(id=f"order{i}", amount=100, price=10, position="INVALID")
                            for i in range(2)]

        trades_for_open[1].position = "OPEN"
        trades_for_close[-1].position = "CLOSE"

        selected_open, selected_close = PerformanceMetrics.position_order(trades_for_open.copy(),
                                                                          trades_for_close.copy())
        self.assertEqual(selected_open, trades_for_open[1])
        self.assertEqual(selected_close, trades_for_close[-1])

    def test_aggregated_position_with_no_trades(self):
        aggregated_buys, aggregated_sells = PerformanceMetrics.aggregate_position_order([], [])

        self.assertEqual(len(aggregated_buys), 0)
        self.assertEqual(len(aggregated_sells), 0)

    def test_aggregated_position_for_unrelated_trades(self):
        trades = []

        trades.append(self.mock_trade(id="order1", amount=100, price=10))
        trades.append(self.mock_trade(id="order2", amount=200, price=15))
        trades.append(self.mock_trade(id="order3", amount=300, price=20))

        aggregated_buys, aggregated_sells = PerformanceMetrics.aggregate_position_order(trades, [])

        self.assertEqual(aggregated_buys, trades)
        self.assertEqual(len(aggregated_sells), 0)

        aggregated_buys, aggregated_sells = PerformanceMetrics.aggregate_position_order([], trades)

        self.assertEqual(len(aggregated_buys), 0)
        self.assertEqual(aggregated_sells, trades)

    def test_aggregated_position_with_two_related_trades_from_three(self):
        trades = []

        trades.append(self.mock_trade(id="order1", amount=100, price=10))
        trades.append(self.mock_trade(id="order2", amount=200, price=15))
        trades.append(self.mock_trade(id="order1", amount=300, price=20))

        aggregated_buys, aggregated_sells = PerformanceMetrics.aggregate_position_order(trades, [])

        self.assertEqual(len(aggregated_buys), 2)
        trade = aggregated_buys[0]
        self.assertTrue(trade.order_id == "order1" and trade.amount == 400 and trade.price == 15)
        self.assertEqual(aggregated_buys[1], trades[1])
        self.assertEqual(len(aggregated_sells), 0)

        trades = []

        trades.append(self.mock_trade(id="order1", amount=100, price=10))
        trades.append(self.mock_trade(id="order2", amount=200, price=15))
        trades.append(self.mock_trade(id="order1", amount=300, price=20))

        aggregated_buys, aggregated_sells = PerformanceMetrics.aggregate_position_order([], trades)

        self.assertEqual(len(aggregated_buys), 0)
        self.assertEqual(len(aggregated_sells), 2)
        trade = aggregated_sells[0]
        self.assertTrue(trade.order_id == "order1" and trade.amount == 400 and trade.price == 15)
        self.assertEqual(aggregated_sells[1], trades[1])

    def test_performance_metrics(self):
        rate_oracle = RateOracle()
        rate_oracle._prices["USDT-HBOT"] = Decimal("5")
        RateOracle._shared_instance = rate_oracle

        trade_fee = AddedToCostTradeFee(flat_fees=[TokenAmount(quote, Decimal("0"))])
        trades = [
            TradeFill(
                config_file_path="some-strategy.yml",
                strategy="pure_market_making",
                market="binance",
                symbol=trading_pair,
                base_asset=base,
                quote_asset=quote,
                timestamp=int(time.time()),
                order_id="someId0",
                trade_type="BUY",
                order_type="LIMIT",
                price=100,
                amount=10,
                trade_fee=trade_fee.to_json(),
                exchange_trade_id="someExchangeId0",
                position=PositionAction.NIL.value,
            ),
            TradeFill(
                config_file_path="some-strategy.yml",
                strategy="pure_market_making",
                market="binance",
                symbol=trading_pair,
                base_asset=base,
                quote_asset=quote,
                timestamp=int(time.time()),
                order_id="someId1",
                trade_type="SELL",
                order_type="LIMIT",
                price=120,
                amount=15,
                trade_fee=trade_fee.to_json(),
                exchange_trade_id="someExchangeId1",
                position=PositionAction.NIL.value,
            )
        ]
        cur_bals = {base: 100, quote: 10000}
        metrics = asyncio.get_event_loop().run_until_complete(
            PerformanceMetrics.create(trading_pair, trades, cur_bals))
        self.assertEqual(Decimal("799"), metrics.trade_pnl)
        print(metrics)

    @patch('hummingbot.client.performance.PerformanceMetrics._is_trade_fill')
    def test_performance_metrics_for_derivatives(self, is_trade_fill_mock):
        rate_oracle = RateOracle()
        rate_oracle._prices["USDT-HBOT"] = Decimal("5")
        RateOracle._shared_instance = rate_oracle

        is_trade_fill_mock.return_value = True
        trades = []
        trades.append(self.mock_trade(id="order1",
                                      amount=Decimal("100"),
                                      price=Decimal("10"),
                                      position="OPEN",
                                      type="BUY",
                                      fee=AddedToCostTradeFee(flat_fees=[TokenAmount(quote, Decimal("0"))])))
        trades.append(self.mock_trade(id="order2",
                                      amount=Decimal("100"),
                                      price=Decimal("15"),
                                      position="CLOSE",
                                      type="SELL",
                                      fee=AddedToCostTradeFee(flat_fees=[TokenAmount(quote, Decimal("0"))])))
        trades.append(self.mock_trade(id="order3",
                                      amount=Decimal("100"),
                                      price=Decimal("20"),
                                      position="OPEN",
                                      type="SELL",
                                      fee=AddedToCostTradeFee(Decimal("0.1"),
                                                              flat_fees=[TokenAmount("USD", Decimal("0"))])))
        trades.append(self.mock_trade(id="order4",
                                      amount=Decimal("100"),
                                      price=Decimal("15"),
                                      position="CLOSE",
                                      type="BUY",
                                      fee=AddedToCostTradeFee(Decimal("0.1"),
                                                              flat_fees=[TokenAmount("USD", Decimal("0"))])))

        cur_bals = {base: 100, quote: 10000}
        metrics = asyncio.get_event_loop().run_until_complete(
            PerformanceMetrics.create(trading_pair, trades, cur_bals))
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
        self.assertEqual(metrics.cur_price, Decimal("0.2"))
        self.assertEqual(metrics.trade_pnl, Decimal("1000"))
        self.assertEqual(metrics.total_pnl, Decimal("650"))

    def test_smart_round(self):
        value = PerformanceMetrics.smart_round(None)
        self.assertIsNone(value)
        value = PerformanceMetrics.smart_round(Decimal("NaN"))
        self.assertTrue(value.is_nan())

        value = PerformanceMetrics.smart_round(Decimal("10000.123456789"))
        self.assertEqual(value, Decimal("10000"))
        value = PerformanceMetrics.smart_round(Decimal("100.123456789"))
        self.assertEqual(value, Decimal("100.1"))
        value = PerformanceMetrics.smart_round(Decimal("1.123456789"))
        self.assertEqual(value, Decimal("1.12"))
        value = PerformanceMetrics.smart_round(Decimal("0.123456789"))
        self.assertEqual(value, Decimal("0.1234"))
        value = PerformanceMetrics.smart_round(Decimal("0.000456789"))
        self.assertEqual(value, Decimal("0.00045"))
        value = PerformanceMetrics.smart_round(Decimal("0.000056789"))
        self.assertEqual(value, Decimal("0.00005678"))
        value = PerformanceMetrics.smart_round(Decimal("0"))
        self.assertEqual(value, Decimal("0"))

        value = PerformanceMetrics.smart_round(Decimal("0.123456"), 2)
        self.assertEqual(value, Decimal("0.12"))

    def test_calculate_fees_in_quote_for_one_trade_with_fees_different_tokens(self):
        rate_oracle = RateOracle()
        rate_oracle._prices["DAI-COINALPHA"] = Decimal("2")
        rate_oracle._prices["USDT-DAI"] = Decimal("0.9")
        RateOracle._shared_instance = rate_oracle

        performance_metric = PerformanceMetrics()
        flat_fees = [
            TokenAmount(token="USDT", amount=Decimal("10")),
            TokenAmount(token="DAI", amount=Decimal("5")),
        ]
        trade = Trade(
            trading_pair="HBOT-COINALPHA",
            side=TradeType.BUY,
            price=Decimal("1000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            market="binance",
            timestamp=1640001112.223,
            trade_fee=AddedToCostTradeFee(percent=Decimal("0.1"),
                                          percent_token="COINALPHA",
                                          flat_fees=flat_fees)
        )

        self.async_run_with_timeout(performance_metric._calculate_fees(
            quote="COINALPHA",
            trades=[trade]))

        expected_fee_amount = trade.amount * trade.price * trade.trade_fee.percent
        expected_fee_amount += flat_fees[0].amount * Decimal("0.9") * Decimal("2")
        expected_fee_amount += flat_fees[1].amount * Decimal("2")
        self.assertEqual(expected_fee_amount, performance_metric.fee_in_quote)

    def test_calculate_fees_in_quote_for_one_trade_fill_with_fees_different_tokens(self):
        rate_oracle = RateOracle()
        rate_oracle._prices["DAI-COINALPHA"] = Decimal("2")
        rate_oracle._prices["USDT-DAI"] = Decimal("0.9")
        RateOracle._shared_instance = rate_oracle

        performance_metric = PerformanceMetrics()
        flat_fees = [
            TokenAmount(token="USDT", amount=Decimal("10")),
            TokenAmount(token="DAI", amount=Decimal("5")),
        ]
        trade = TradeFill(
            config_file_path="some-strategy.yml",
            strategy="pure_market_making",
            market="binance",
            symbol="HBOT-COINALPHA",
            base_asset="HBOT",
            quote_asset="COINALPHA",
            timestamp=int(time.time()),
            order_id="someId0",
            trade_type="BUY",
            order_type="LIMIT",
            price=1000,
            amount=1,
            trade_fee=AddedToCostTradeFee(percent=Decimal("0.1"),
                                          percent_token="COINALPHA",
                                          flat_fees=flat_fees).to_json(),
            exchange_trade_id="someExchangeId0",
            position=PositionAction.NIL.value,
        )

        self.async_run_with_timeout(performance_metric._calculate_fees(
            quote="COINALPHA",
            trades=[trade]))

        expected_fee_amount = Decimal(str(trade.amount)) * Decimal(str(trade.price)) * Decimal("0.1")
        expected_fee_amount += flat_fees[0].amount * Decimal("0.9") * Decimal("2")
        expected_fee_amount += flat_fees[1].amount * Decimal("2")
        self.assertEqual(expected_fee_amount, performance_metric.fee_in_quote)
