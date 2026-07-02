import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from hummingbot.cli import bot
from hummingbot.cli.commands.history import _balances_for_market, history


def fill(market="binance", symbol="BTC-USDT"):
    return SimpleNamespace(market=market, symbol=symbol)


def perf(return_pct="0.05"):
    return SimpleNamespace(
        num_trades=2, num_buys=1, num_sells=1,
        tot_vol_base=Decimal("1.5"), tot_vol_quote=Decimal("3000"),
        trade_pnl=Decimal("10"), fee_in_quote=Decimal("1"),
        total_pnl=Decimal("9"), return_pct=Decimal(return_pct),
    )


class BalancesForMarketTest(unittest.TestCase):
    def test_exact_market_match(self):
        balances = {"binance": {"BTC": 1.0}, "kucoin": {"ETH": 2.0}}
        self.assertEqual(_balances_for_market("binance", balances), {"BTC": Decimal("1.0")})

    def test_merged_fallback_when_no_match(self):
        balances = {"binance": {"BTC": 1.0, "USDT": 5.0}, "kucoin": {"BTC": 0.5}}
        merged = _balances_for_market("okx", balances)
        self.assertEqual(merged, {"BTC": Decimal("1.5"), "USDT": Decimal("5.0")})

    def test_empty_balances(self):
        self.assertEqual(_balances_for_market("binance", {}), {})


class HistoryCommandTest(unittest.TestCase):
    def _run(self, fills, *, name=None, days=None, balances_status=None, running=False,
             perf_create=None, resolved=None):
        resolved = resolved or ("/tmp/db.sqlite", "conf_x.yml", running)
        perf_create = perf_create or AsyncMock(return_value=perf())
        with patch("hummingbot.cli.commands._common.resolve_db_for_command",
                   return_value=resolved) as resolve_mock, \
                patch("hummingbot.cli.data.get_trades", return_value=fills) as get_trades, \
                patch("hummingbot.client.performance.PerformanceMetrics.create", perf_create), \
                patch.object(bot, "read_status", return_value=balances_status), \
                patch("hummingbot.cli.commands.history.echo") as echo_mock:
            history(name=name, days=days)
        printed = "\n".join(c.args[0] for c in echo_mock.call_args_list)
        return printed, get_trades, resolve_mock

    def test_no_trades(self):
        printed, _, _ = self._run([])
        self.assertEqual(printed, "No trades found.")

    def test_two_markets_with_balances_and_averaged_return(self):
        fills = [fill("binance", "BTC-USDT"), fill("binance", "BTC-USDT"),
                 fill("kucoin", "ETH-USDT")]
        status = {"balances": {"binance": {"BTC": 1.0}, "kucoin": {"ETH": 2.0}}}
        printed, get_trades, _ = self._run(fills, balances_status=status)
        self.assertIn("## history", printed)
        self.assertIn("| binance | BTC-USDT | 2 |", printed)
        self.assertIn("| kucoin | ETH-USDT | 2 |", printed)  # perf.num_trades, not fill count
        self.assertIn("averaged return: 5.00%", printed)
        self.assertNotIn("balances unavailable", printed)
        get_trades.assert_called_once_with("/tmp/db.sqlite", config_file_path="conf_x.yml", days=None)

    def test_error_row_and_missing_balances_hint(self):
        # kucoin errors out; binance succeeds but with no balances anywhere -> hint printed
        async def create(symbol, trades, balances):
            if symbol == "ETH-USDT":
                raise RuntimeError("rate oracle down")
            return perf()

        fills = [fill("binance", "BTC-USDT"), fill("kucoin", "ETH-USDT")]
        printed, _, _ = self._run(fills, balances_status=None, perf_create=create)
        self.assertIn("kucoin/ETH-USDT: (1 trades) error: rate oracle down", printed)
        self.assertIn("current balances unavailable for some markets (bot stopped)", printed)
        self.assertNotIn("averaged return", printed)  # only one non-error row

    def test_running_hint_wording(self):
        fills = [fill()]
        status = {"balances": {}}
        with patch("hummingbot.cli.commands.status._request_fresh_snapshot"):
            printed, _, _ = self._run(fills, balances_status=status, running=True,
                                      resolved=("/tmp/db.sqlite", None, True))
        self.assertIn("run `hbot status` to refresh", printed)

    def test_running_with_no_cached_balances_requests_snapshot(self):
        fills = [fill()]
        reads = [{"balances": {}}, {"balances": {"binance": {"BTC": 1.0}}}]
        with patch("hummingbot.cli.commands._common.resolve_db_for_command",
                   return_value=("/tmp/db.sqlite", None, True)), \
                patch("hummingbot.cli.data.get_trades", return_value=fills), \
                patch("hummingbot.client.performance.PerformanceMetrics.create",
                      AsyncMock(return_value=perf())), \
                patch.object(bot, "read_status", side_effect=reads) as read_status, \
                patch("hummingbot.cli.commands.status._request_fresh_snapshot") as refresh, \
                patch("hummingbot.cli.commands.history.echo") as echo_mock:
            history(name=None, days=None)
        refresh.assert_called_once()
        self.assertEqual(read_status.call_count, 2)
        printed = "\n".join(c.args[0] for c in echo_mock.call_args_list)
        self.assertNotIn("balances unavailable", printed)

    def test_named_bot_skips_balances_and_titles_table(self):
        fills = [fill()]
        with patch("hummingbot.cli.commands._common.resolve_db_for_command",
                   return_value=("/tmp/past.sqlite", None, False)) as resolve_mock, \
                patch("hummingbot.cli.data.get_trades", return_value=fills) as get_trades, \
                patch("hummingbot.client.performance.PerformanceMetrics.create",
                      AsyncMock(return_value=perf())), \
                patch.object(bot, "read_status") as read_status, \
                patch("hummingbot.cli.commands.history.echo") as echo_mock:
            history(name="pastbot", days=7)
        resolve_mock.assert_called_once_with("pastbot")
        read_status.assert_not_called()  # balances come only from the current bot's snapshot
        get_trades.assert_called_once_with("/tmp/past.sqlite", config_file_path=None, days=7)
        printed = "\n".join(c.args[0] for c in echo_mock.call_args_list)
        self.assertIn("## history pastbot", printed)


if __name__ == "__main__":
    unittest.main()
