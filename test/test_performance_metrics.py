from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))
from decimal import Decimal
from typing import List
import unittest
import asyncio
from unittest.mock import patch

from hummingbot.client.performance import calculate_performance_metrics
from hummingbot.core.data_type.trade import Trade, TradeType, TradeFee

trading_pair = "HBOT-USDT"
base, quote = trading_pair.split("-")


class PerformanceMetricsUnitTest(unittest.TestCase):

    def setUp(self):
        pass

    @patch('hummingbot.client.performance.get_last_price')
    async def test_calculate_performance_metrics(self, mock_get_last_price):
        f = asyncio.Future()
        f.set_result(110)
        mock_get_last_price.return_value = f

        trades: List[Trade] = [
            Trade(trading_pair, TradeType.BUY, 100, 10, None, trading_pair, 1, TradeFee(0.0, [(quote, 0)])),
            Trade(trading_pair, TradeType.SELL, 120, 15, None, trading_pair, 1, TradeFee(0.0, [(quote, 0)]))
        ]
        cur_bals = {base: 100, quote: 10000}
        metrics = asyncio.get_event_loop().run_until_complete(
            calculate_performance_metrics("hbot_exchange", trading_pair, trades, cur_bals))
        self.assertEqual(Decimal("250"), metrics.trade_pnl)
        print(metrics)
