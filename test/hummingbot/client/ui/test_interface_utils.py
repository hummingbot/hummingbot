import unittest
from decimal import Decimal
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from hummingbot.client.ui.interface_utils import start_trade_monitor


class InterfaceUtilsTest(unittest.TestCase):

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.ui.interface_utils.PerformanceMetrics.create", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    async def _test_start_trade_monitor_multi_loops(self, mock_hb_app, mock_perf, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = [MagicMock(market="ExchangeA", symbol="HBOT-USDT")]
        mock_app.get_current_balances = AsyncMock()
        mock_perf.side_effect = [MagicMock(return_pct=Decimal("0.01"), total_pnl=Decimal("2")),
                                 MagicMock(return_pct=Decimal("0.02"), total_pnl=Decimal("2"))]
        mock_sleep.side_effect = [None, Exception("returns")]
        with self.assertRaises(Exception) as context:
            await start_trade_monitor(mock_result)
        self.assertEqual('returns', str(context.exception))
        self.assertEqual(3, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])
        self.assertEqual('Trades: 1, Total P&L: 2.00 USDT, Return %: 1.00%', mock_result.log.call_args_list[1].args[0])
        self.assertEqual('Trades: 1, Total P&L: 2.00 USDT, Return %: 2.00%', mock_result.log.call_args_list[2].args[0])

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.ui.interface_utils.PerformanceMetrics.create", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    async def _test_start_trade_monitor_multi_pairs_diff_quotes(self, mock_hb_app, mock_perf, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = [
            MagicMock(market="ExchangeA", symbol="HBOT-USDT"),
            MagicMock(market="ExchangeA", symbol="HBOT-BTC")
        ]
        mock_app.get_current_balances = AsyncMock()
        mock_perf.side_effect = [MagicMock(return_pct=Decimal("0.01"), total_pnl=Decimal("2")),
                                 MagicMock(return_pct=Decimal("0.02"), total_pnl=Decimal("3"))]
        mock_sleep.side_effect = Exception("returns")
        with self.assertRaises(Exception) as context:
            await start_trade_monitor(mock_result)
        self.assertEqual('returns', str(context.exception))
        self.assertEqual(2, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])
        self.assertEqual('Trades: 2, Total P&L: N/A, Return %: 1.50%', mock_result.log.call_args_list[1].args[0])

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.ui.interface_utils.PerformanceMetrics.create", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    async def _test_start_trade_monitor_multi_pairs_same_quote(self, mock_hb_app, mock_perf, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = [
            MagicMock(market="ExchangeA", symbol="HBOT-USDT"),
            MagicMock(market="ExchangeA", symbol="BTC-USDT")
        ]
        mock_app.get_current_balances = AsyncMock()
        mock_perf.side_effect = [MagicMock(return_pct=Decimal("0.01"), total_pnl=Decimal("2")),
                                 MagicMock(return_pct=Decimal("0.02"), total_pnl=Decimal("3"))]
        mock_sleep.side_effect = Exception("returns")
        with self.assertRaises(Exception) as context:
            await start_trade_monitor(mock_result)
        self.assertEqual('returns', str(context.exception))
        self.assertEqual(2, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])
        self.assertEqual('Trades: 2, Total P&L: 5.00 USDT, Return %: 1.50%', mock_result.log.call_args_list[1].args[0])

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    async def _test_start_trade_monitor_market_not_ready(self, mock_hb_app, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=False)}
        mock_sleep.side_effect = Exception("returns")
        with self.assertRaises(Exception) as context:
            await start_trade_monitor(mock_result)
        self.assertEqual('returns', str(context.exception))
        self.assertEqual(1, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    async def _test_start_trade_monitor_market_no_trade(self, mock_hb_app, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = []
        mock_sleep.side_effect = Exception("returns")
        with self.assertRaises(Exception) as context:
            await start_trade_monitor(mock_result)
        self.assertEqual('returns', str(context.exception))
        self.assertEqual(1, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])

    def test_start_trade_monitor_market_no_trade(self):
        asyncio.get_event_loop().run_until_complete(self._test_start_trade_monitor_market_no_trade())

    def test_start_trade_monitor_market_not_ready(self):
        asyncio.get_event_loop().run_until_complete(self._test_start_trade_monitor_market_not_ready())

    def test_start_trade_monitor_multi_loops(self):
        asyncio.get_event_loop().run_until_complete(self._test_start_trade_monitor_multi_loops())

    def test_start_trade_monitor_multi_pairs_diff_quotes(self):
        asyncio.get_event_loop().run_until_complete(self._test_start_trade_monitor_multi_pairs_diff_quotes())

    def test_start_trade_monitor_multi_pairs_same_quote(self):
        asyncio.get_event_loop().run_until_complete(self._test_start_trade_monitor_multi_pairs_same_quote())
