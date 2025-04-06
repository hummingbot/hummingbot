import asyncio
import threading
import time
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

import pandas as pd

from hummingbot.client.command.gateway_command import GatewayCommand
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.settings import MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT, AllConnectorSettings
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.model.trade_fill import TradeFill
from hummingbot.user.user_balances import UserBalances

s_float_0 = float(0)
s_decimal_0 = Decimal("0")


if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def get_timestamp(days_ago: float = 0.) -> float:
    return time.time() - (60. * 60. * 24. * days_ago)


class HistoryCommand:
    def history(self,  # type: HummingbotApplication
                days: float = 0,
                verbose: bool = False,
                precision: Optional[int] = None
                ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.history, days, verbose, precision)
            return

        if self.strategy_file_name is None:
            self.notify("\n  Please first import a strategy config file of which to show historical performance.")
            return
        start_time = get_timestamp(days) if days > 0 else self.init_time
        with self.trade_fill_db.get_new_session() as session:
            trades: List[TradeFill] = self._get_trades_from_session(
                int(start_time * 1e3),
                session=session,
                config_file_path=self.strategy_file_name)
            if not trades:
                self.notify("\n  No past trades to report.")
                return
            if verbose:
                self.list_trades(start_time)
            safe_ensure_future(self.history_report(start_time, trades, precision))

    def get_history_trades_json(self,  # type: HummingbotApplication
                                days: float = 0):
        if self.strategy_file_name is None:
            return
        start_time = get_timestamp(days) if days > 0 else self.init_time
        with self.trade_fill_db.get_new_session() as session:
            trades: List[TradeFill] = self._get_trades_from_session(
                int(start_time * 1e3),
                session=session,
                config_file_path=self.strategy_file_name)
            return list([TradeFill.to_bounty_api_json(t) for t in trades])

    async def history_report(self,  # type: HummingbotApplication
                             start_time: float,
                             trades: List[TradeFill],
                             precision: Optional[int] = None,
                             display_report: bool = True) -> Decimal:
        market_info: Set[Tuple[str, str]] = set((t.market, t.symbol) for t in trades)
        if display_report:
            self.report_header(start_time)
        return_pcts = []
        for market, symbol in market_info:
            cur_trades = [t for t in trades if t.market == market and t.symbol == symbol]
            network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
            try:
                cur_balances = await asyncio.wait_for(self.get_current_balances(market), network_timeout)
            except asyncio.TimeoutError:
                self.notify(
                    "\nA network error prevented the balances retrieval to complete. See logs for more details."
                )
                raise
            perf = await PerformanceMetrics.create(symbol, cur_trades, cur_balances)
            if display_report:
                self.report_performance_by_market(market, symbol, perf, precision)
            return_pcts.append(perf.return_pct)
        avg_return = sum(return_pcts) / len(return_pcts) if len(return_pcts) > 0 else s_decimal_0
        if display_report and len(return_pcts) > 1:
            self.notify(f"\nAveraged Return = {avg_return:.2%}")
        return avg_return

    async def get_current_balances(self,  # type: HummingbotApplication
                                   market: str):
        if market in self.markets and self.markets[market].ready:
            return self.markets[market].get_all_balances()
        elif "Paper" in market:
            paper_balances = self.client_config_map.paper_trade.paper_trade_account_balance
            if paper_balances is None:
                return {}
            return {token: Decimal(str(bal)) for token, bal in paper_balances.items()}
        else:
            if UserBalances.instance().is_gateway_market(market):
                await GatewayCommand.update_exchange_balances(self, market, self.client_config_map)
                return GatewayCommand.all_balance(self, market)
            else:
                await UserBalances.instance().update_exchange_balance(market, self.client_config_map)
                return UserBalances.instance().all_balances(market)

    def report_header(self,  # type: HummingbotApplication
                      start_time: float):
        lines = []
        current_time = get_timestamp()
        lines.extend(
            [f"\nStart Time: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}"] +
            [f"Current Time: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}"] +
            [f"Duration: {pd.Timedelta(seconds=int(current_time - start_time))}"]
        )
        self.notify("\n".join(lines))

    def report_performance_by_market(self,  # type: HummingbotApplication
                                     market: str,
                                     trading_pair: str,
                                     perf: PerformanceMetrics,
                                     precision: int):
        lines = []
        base, quote = trading_pair.split("-")
        lines.extend(
            [f"\n{market} / {trading_pair}"]
        )

        trades_columns = ["", "buy", "sell", "total"]
        trades_data = [
            [f"{'Number of trades':<27}", perf.num_buys, perf.num_sells, perf.num_trades],
            [f"{f'Total trade volume ({base})':<27}",
             PerformanceMetrics.smart_round(perf.b_vol_base, precision),
             PerformanceMetrics.smart_round(perf.s_vol_base, precision),
             PerformanceMetrics.smart_round(perf.tot_vol_base, precision)],
            [f"{f'Total trade volume ({quote})':<27}",
             PerformanceMetrics.smart_round(perf.b_vol_quote, precision),
             PerformanceMetrics.smart_round(perf.s_vol_quote, precision),
             PerformanceMetrics.smart_round(perf.tot_vol_quote, precision)],
            [f"{'Avg price':<27}",
             PerformanceMetrics.smart_round(perf.avg_b_price, precision),
             PerformanceMetrics.smart_round(perf.avg_s_price, precision),
             PerformanceMetrics.smart_round(perf.avg_tot_price, precision)],
        ]
        trades_df: pd.DataFrame = pd.DataFrame(data=trades_data, columns=trades_columns)
        lines.extend(["", "  Trades:"] + ["    " + line for line in trades_df.to_string(index=False).split("\n")])

        assets_columns = ["", "start", "current", "change"]
        assets_data = [
            [f"{base:<17}", "-", "-", "-"] if market in AllConnectorSettings.get_derivative_names() else  # No base asset for derivatives because they are margined
            [f"{base:<17}",
             PerformanceMetrics.smart_round(perf.start_base_bal, precision),
             PerformanceMetrics.smart_round(perf.cur_base_bal, precision),
             PerformanceMetrics.smart_round(perf.tot_vol_base, precision)],
            [f"{quote:<17}",
             PerformanceMetrics.smart_round(perf.start_quote_bal, precision),
             PerformanceMetrics.smart_round(perf.cur_quote_bal, precision),
             PerformanceMetrics.smart_round(perf.tot_vol_quote, precision)],
            [f"{trading_pair + ' price':<17}",
             PerformanceMetrics.smart_round(perf.start_price),
             PerformanceMetrics.smart_round(perf.cur_price),
             PerformanceMetrics.smart_round(perf.cur_price - perf.start_price)],
            [f"{'Base asset %':<17}", "-", "-", "-"] if market in AllConnectorSettings.get_derivative_names() else  # No base asset for derivatives because they are margined
            [f"{'Base asset %':<17}",
             f"{perf.start_base_ratio_pct:.2%}",
             f"{perf.cur_base_ratio_pct:.2%}",
             f"{perf.cur_base_ratio_pct - perf.start_base_ratio_pct:.2%}"],
        ]
        assets_df: pd.DataFrame = pd.DataFrame(data=assets_data, columns=assets_columns)
        lines.extend(["", "  Assets:"] + ["    " + line for line in assets_df.to_string(index=False).split("\n")])

        perf_data = [
            ["Hold portfolio value    ", f"{PerformanceMetrics.smart_round(perf.hold_value, precision)} {quote}"],
            ["Current portfolio value ", f"{PerformanceMetrics.smart_round(perf.cur_value, precision)} {quote}"],
            ["Trade P&L               ", f"{PerformanceMetrics.smart_round(perf.trade_pnl, precision)} {quote}"]
        ]
        perf_data.extend(
            ["Fees paid               ", f"{PerformanceMetrics.smart_round(fee_amount, precision)} {fee_token}"]
            for fee_token, fee_amount in perf.fees.items()
        )
        perf_data.extend(
            [["Total P&L               ", f"{PerformanceMetrics.smart_round(perf.total_pnl, precision)} {quote}"],
             ["Return %                ", f"{perf.return_pct:.2%}"]]
        )
        perf_df: pd.DataFrame = pd.DataFrame(data=perf_data)
        lines.extend(["", "  Performance:"] +
                     ["    " + line for line in perf_df.to_string(index=False, header=False).split("\n")])

        self.notify("\n".join(lines))

    async def calculate_profitability(self,  # type: HummingbotApplication
                                      ) -> Decimal:
        """
        Determines the profitability of the trading bot.
        This function is used by the KillSwitch class.
        Must be updated if the method of performance report gets updated.
        """
        if not self.markets_recorder:
            return s_decimal_0
        if any(not market.ready for market in self.markets.values()):
            return s_decimal_0

        start_time = self.init_time

        with self.trade_fill_db.get_new_session() as session:
            trades: List[TradeFill] = self._get_trades_from_session(
                int(start_time * 1e3),
                session=session,
                config_file_path=self.strategy_file_name)
            avg_return = await self.history_report(start_time, trades, display_report=False)
        return avg_return

    def list_trades(self,  # type: HummingbotApplication
                    start_time: float):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.list_trades, start_time)
            return

        lines = []

        with self.trade_fill_db.get_new_session() as session:
            queried_trades: List[TradeFill] = self._get_trades_from_session(
                int(start_time * 1e3),
                session=session,
                number_of_rows=MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT + 1,
                config_file_path=self.strategy_file_name)
            df: pd.DataFrame = TradeFill.to_pandas(queried_trades)

        if len(df) > 0:
            # Check if number of trades exceed maximum number of trades to display
            if len(df) > MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT:
                df = df[:MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT]
                self.notify(
                    f"\n  Showing last {MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT} trades in the current session.")
            df_lines = format_df_for_printout(df, self.client_config_map.tables_format).split("\n")
            lines.extend(["", "  Recent trades:"] +
                         ["    " + line for line in df_lines])
        else:
            lines.extend(["\n  No past trades in this session."])
        self.notify("\n".join(lines))
