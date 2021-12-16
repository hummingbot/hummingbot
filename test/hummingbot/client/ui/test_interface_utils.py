import unittest
from decimal import Decimal
import asyncio
from typing import Awaitable
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
from hummingbot.client.ui.interface_utils import start_trade_monitor, format_bytes, start_timer, start_process_monitor


class ExpectedException(Exception):
    pass


class InterfaceUtilsTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.return_queue = asyncio.Queue()
        self.done_event = asyncio.Event()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    async def return_until_empty_then_signal_done_and_release_loop(self, *args, **kwargs):
        if not self.return_queue.empty():
            ret = self.return_queue.get_nowait()
        else:
            self.done_event.set()
            await asyncio.sleep(0.3)  # simply to release loop — the 0.3 seconds are not actually awaited
        return ret

    def test_format_bytes(self):
        size = 1024.
        self.assertEqual("1.00 KB", format_bytes(size))
        self.assertEqual("157.36 GB", format_bytes(168963795964))

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    def test_start_timer(self, mock_sleep):
        mock_timer = MagicMock()
        self.return_queue.put_nowait(None)
        mock_sleep.side_effect = self.return_until_empty_then_signal_done_and_release_loop
        task = self.ev_loop.create_task(start_timer(mock_timer))
        self.async_run_with_timeout(self.done_event.wait())
        task.cancel()
        self.assertEqual('Duration: 0:00:02', mock_timer.log.call_args_list[0].args[0])
        self.assertEqual('Duration: 0:00:03', mock_timer.log.call_args_list[1].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("psutil.Process")
    def test_start_process_monitor(self, mock_process, mock_sleep):
        mock_process.return_value.num_threads.return_value = 2
        mock_process.return_value.cpu_percent.return_value = 30

        memory_info = MagicMock()
        type(memory_info).vms = PropertyMock(return_value=1024.0)
        type(memory_info).rss = PropertyMock(return_value=1024.0)

        mock_process.return_value.memory_info.return_value = memory_info
        mock_monitor = MagicMock()
        mock_sleep.side_effect = self.return_until_empty_then_signal_done_and_release_loop
        task = self.ev_loop.create_task(start_process_monitor(mock_monitor))
        self.async_run_with_timeout(self.done_event.wait())
        task.cancel()
        self.assertEqual(
            "CPU:    30%, Mem:   512.00 B (1.00 KB), Threads:   2, ",
            mock_monitor.log.call_args_list[0].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.ui.interface_utils.PerformanceMetrics.create", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_multi_loops(self, mock_hb_app, mock_perf, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = [MagicMock(market="ExchangeA", symbol="HBOT-USDT")]
        mock_app.get_current_balances = AsyncMock()
        mock_perf.side_effect = [MagicMock(return_pct=Decimal("0.01"), total_pnl=Decimal("2")),
                                 MagicMock(return_pct=Decimal("0.02"), total_pnl=Decimal("2"))]
        self.return_queue.put_nowait(None)
        mock_sleep.side_effect = self.return_until_empty_then_signal_done_and_release_loop
        task = self.ev_loop.create_task(start_trade_monitor(mock_result))
        self.async_run_with_timeout(self.done_event.wait())
        task.cancel()
        self.assertEqual(3, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])
        self.assertEqual('Trades: 1, Total P&L: 2.00 USDT, Return %: 1.00%', mock_result.log.call_args_list[1].args[0])
        self.assertEqual('Trades: 1, Total P&L: 2.00 USDT, Return %: 2.00%', mock_result.log.call_args_list[2].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.ui.interface_utils.PerformanceMetrics.create", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_multi_pairs_diff_quotes(self, mock_hb_app, mock_perf, mock_sleep):
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
        mock_sleep.side_effect = self.return_until_empty_then_signal_done_and_release_loop
        task = self.ev_loop.create_task(start_trade_monitor(mock_result))
        self.async_run_with_timeout(self.done_event.wait())
        task.cancel()
        self.assertEqual(2, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])
        self.assertEqual('Trades: 2, Total P&L: N/A, Return %: 1.50%', mock_result.log.call_args_list[1].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.ui.interface_utils.PerformanceMetrics.create", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_multi_pairs_same_quote(self, mock_hb_app, mock_perf, mock_sleep):
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
        mock_sleep.side_effect = self.return_until_empty_then_signal_done_and_release_loop
        task = self.ev_loop.create_task(start_trade_monitor(mock_result))
        self.async_run_with_timeout(self.done_event.wait())
        task.cancel()
        self.assertEqual(2, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])
        self.assertEqual('Trades: 2, Total P&L: 5.00 USDT, Return %: 1.50%', mock_result.log.call_args_list[1].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_market_not_ready(self, mock_hb_app, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=False)}
        mock_sleep.side_effect = self.return_until_empty_then_signal_done_and_release_loop
        task = self.ev_loop.create_task(start_trade_monitor(mock_result))
        self.async_run_with_timeout(self.done_event.wait())
        task.cancel()
        self.assertEqual(1, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_market_no_trade(self, mock_hb_app, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = []
        mock_sleep.side_effect = self.return_until_empty_then_signal_done_and_release_loop
        task = self.ev_loop.create_task(start_trade_monitor(mock_result))
        self.async_run_with_timeout(self.done_event.wait())
        task.cancel()
        self.assertEqual(1, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_loop_continues_on_failure(self, mock_hb_app, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.side_effect = [RuntimeError(), True]
        mock_sleep.side_effect = self.return_until_empty_then_signal_done_and_release_loop
        task = self.ev_loop.create_task(start_trade_monitor(mock_result))
        self.async_run_with_timeout(self.done_event.wait())
        task.cancel()
        self.assertEqual(2, mock_app.strategy_task.done.call_count)  # was called again after exception
