from decimal import Decimal
from collections import defaultdict

import pandas as pd
import threading
import time
from typing import (
    Any,
    Dict,
    Set,
    Tuple,
    Optional,
    TYPE_CHECKING,
    List
)
from hummingbot.client.performance_analysis import calculate_trade_performance
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from datetime import datetime
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.settings import MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.config.config_helpers import secondary_market_conversion_rate

s_float_0 = float(0)
s_decimal_0 = Decimal("0")


if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


def get_timestamp(days_ago: float = 0.) -> float:
    return time.time() - (60. * 60. * 24. * days_ago)


def smart_round(value: Decimal) -> Decimal:
    if abs(value) > 100:
        step = Decimal("0.1")
    elif 100 > abs(value) > 0:
        step = Decimal("0.01")
    elif 0 > abs(value) > Decimal("0.01"):
        step = Decimal("0.001")
    elif Decimal("0.01") > abs(value) > Decimal("0.0001"):
        step = Decimal("0.00001")
    else:
        step = Decimal("0.000001")
    return (value // step) * step


class HistoryCommand:
    def history(self,  # type: HummingbotApplication
                days: float = 0,
                verbose: bool = False,
                ):
        days = 10.
        verbose = True
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.history)
            return

        if self.strategy_file_name is None:
            self._notify("\n  Please first import a strategy config file of which to show historical performance.")
            return
        if global_config_map.get("paper_trade_enabled").value:
            self._notify("\n  Paper Trading ON: All orders are simulated, and no real orders are placed.")
        if verbose:
            self.list_trades(days=days)
        if self.strategy_name != "celo_arb":
            self.history_report(days=days)

    def history_report(self,  # type: HummingbotApplication
                       days: float = 0.0):
        start_time = get_timestamp(days)
        current_balances = self.balance_snapshot()
        trades: List[TradeFill] = self._get_trades_from_session(int(start_time * 1e3),
                                                                config_file_path=self.strategy_file_name)
        market_info: Set[Tuple[str, str]] = set((t.market, t.symbol) for t in trades)
        for market, symbol in market_info:
            cur_trades = [t for t in trades if t.market == market and t.symbol == symbol]
            self.history_report_by_market(start_time, market, symbol, cur_trades, current_balances)

    def history_report_by_market(self,  # type: HummingbotApplication
                                 start_time: float,
                                 market: str,
                                 trading_pair: str,
                                 trades: List[TradeFill],
                                 current_balances: Dict[str, Dict[str, Decimal]]):
        lines = []
        base, quote = trading_pair.split("-")
        current_time = get_timestamp()
        lines.extend(
            [f"    Start Time: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}"] +
            [f"    Curent Time: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}"] +
            [f"    Duration: {pd.Timedelta(seconds=int(current_time - start_time))}"]
        )

        buys = [t for t in trades if t.trade_type.upper() == "BUY"]
        sells = [t for t in trades if t.trade_type.upper() == "SELL"]
        b_vol_base = Decimal(str(sum(b.amount for b in buys)))
        s_vol_base = Decimal(str(sum(s.amount for s in sells))) * Decimal("-1")
        tot_vol_base = b_vol_base + s_vol_base
        b_vol_quote = Decimal(str(sum(b.amount * b.price for b in buys))) * Decimal("-1")
        s_vol_quote = Decimal(str(sum(s.amount * s.price for s in sells)))
        tot_vol_quote = b_vol_quote + s_vol_quote
        avg_b_price = b_vol_quote / b_vol_base if b_vol_base != s_decimal_0 else s_decimal_0
        avg_s_price = s_vol_quote / s_vol_base if s_vol_base != s_decimal_0 else s_decimal_0
        avg_tot_price = tot_vol_quote / tot_vol_base if tot_vol_base != s_decimal_0 else s_decimal_0
        avg_b_price = abs(avg_b_price)
        avg_s_price = abs(avg_s_price)
        avg_tot_price = abs(avg_tot_price)

        trades_columns = ["", "buy", "sell", "total"]
        trades_data = [
            [f"{'Number of trades':<27}", len(buys), len(sells), len(trades)],
            [f"{f'Total trade volume ({base})':<27}",
             smart_round(b_vol_base),
             smart_round(s_vol_base),
             smart_round(tot_vol_base)],
            [f"{f'Total trade volume ({quote})':<27}",
             smart_round(b_vol_quote),
             smart_round(s_vol_quote),
             smart_round(tot_vol_quote)],
            [f"{'Avg price':<27}",
             smart_round(avg_b_price),
             smart_round(avg_s_price),
             smart_round(avg_tot_price)],
        ]
        trades_df: pd.DataFrame = pd.DataFrame(data=trades_data, columns=trades_columns)
        lines.extend(["", "  Trades:"] + ["    " + line for line in trades_df.to_string(index=False).split("\n")])

        base_balance = current_balances[market].get(base, s_decimal_0)
        quote_balance = current_balances[market].get(quote, s_decimal_0)
        start_base = base_balance - tot_vol_base
        start_quote = quote_balance - tot_vol_quote
        start_price = trades[0].price
        assets_columns = ["", "start", "current", "change"]
        assets_data = [
            [f"{base:<17}", smart_round(start_base), smart_round(base_balance), smart_round(tot_vol_base)],
            [f"{quote:<17}", smart_round(start_quote), smart_round(quote_balance), smart_round(tot_vol_quote)],
            [f"{trading_pair + ' price':<17}", start_price, 0, 0],
            [f"{'Base asset %':<17}", 0, 0, 0],
        ]
        assets_df: pd.DataFrame = pd.DataFrame(data=assets_data, columns=assets_columns)
        lines.extend(["", "  Assets:"] + ["    " + line for line in assets_df.to_string(index=False).split("\n")])

        perf_data = [
            ["Hold portfolio value    ", 0],
            ["Current portfolio value ", 0],
            ["Trade P&L               ", 0],
            ["Fees paid               ", 0],
            ["Total P&L               ", 0],
            ["Return %                ", 0],
        ]
        perf_df: pd.DataFrame = pd.DataFrame(data=perf_data)
        lines.extend(["", "  Performance:"] +
                     ["    " + line for line in perf_df.to_string(index=False, header=False).split("\n")])

        self._notify("\n".join(lines))
        return

        trade_performance_stats, market_trading_pair_stats = self._calculate_trade_performance()
        primary_quote_asset: str = self.market_trading_pair_tuples[0].quote_asset.upper()

        trade_performance_status_line = []
        market_df_data: Set[Tuple[str, str, Decimal, Decimal, str, str]] = set()
        market_df_columns = ["Market", "Pair", "Start Price", "End Price",
                             "Trades", "Trade Value Delta"]

        for market_trading_pair_tuple, trading_pair_stats in market_trading_pair_stats.items():
            market_df_data.add((
                market_trading_pair_tuple.market.display_name,
                market_trading_pair_tuple.trading_pair.upper(),
                trading_pair_stats["starting_quote_rate"],
                trading_pair_stats["end_quote_rate"],
                trading_pair_stats["trade_count"],
                f"{trading_pair_stats['trading_pair_delta']:.8f} {primary_quote_asset}"
            ))

        inventory_df: pd.DataFrame = self.balance_comparison_data_frame(market_trading_pair_stats)
        market_df: pd.DataFrame = pd.DataFrame(data=list(market_df_data), columns=market_df_columns)
        portfolio_delta: Decimal = trade_performance_stats["portfolio_delta"]
        portfolio_delta_percentage: Decimal = trade_performance_stats["portfolio_delta_percentage"]

        trade_performance_status_line.extend(["", "  Inventory:"] +
                                             ["    " + line for line in inventory_df.to_string().split("\n")])
        trade_performance_status_line.extend(["", "  Markets:"] +
                                             ["    " + line for line in market_df.to_string().split("\n")])

        trade_performance_status_line.extend(
            ["", "  Performance:"] +
            [f"    Started: {datetime.fromtimestamp(self.start_time//1e3)}"] +
            [f"    Duration: {pd.Timedelta(seconds=abs(int(time.time() - self.start_time/1e3)))}"] +
            [f"    Total Trade Value Delta: {portfolio_delta:.7g} {primary_quote_asset}"] +
            [f"    Return %: {portfolio_delta_percentage:.4f} %"])

        self._notify("\n".join(trade_performance_status_line))

    def balance_snapshot(self,  # type: HummingbotApplication
                         ) -> Dict[str, Dict[str, Decimal]]:
        snapshot: Dict[str, Any] = defaultdict(dict)
        for market_name in self.markets:
            balance_dict = self.markets[market_name].get_all_balances()
            balance_dict = {k.upper(): v for k, v in balance_dict.items()}

            for asset in balance_dict:
                snapshot[asset][market_name] = Decimal(balance_dict[asset])

            for asset in self.assets:
                asset = asset.upper()
                if asset not in balance_dict:
                    snapshot[asset][market_name] = Decimal("0")
        return snapshot

    def balance_comparison_data_frame(self,  # type: HummingbotApplication
                                      market_trading_pair_stats: Dict[MarketTradingPairTuple, any],
                                      ) -> pd.DataFrame:
        if len(self.starting_balances) == 0:
            self._notify("\n  Balance snapshots are not available before bot starts")
            return
        rows = []
        for market_trading_pair_tuple in self.market_trading_pair_tuples:
            market: ExchangeBase = market_trading_pair_tuple.market
            for asset in set(a.upper() for a in self.assets):
                asset_delta: Dict[str, Decimal] = market_trading_pair_stats[market_trading_pair_tuple]["asset"].get(
                    asset, {"delta": Decimal("0")})
                starting_balance = self.starting_balances.get(asset).get(market.name)
                current_balance = self.balance_snapshot().get(asset).get(market.name)
                rows.append([market.display_name,
                             asset,
                             f"{starting_balance:.4f}",
                             f"{current_balance:.4f}",
                             f"{current_balance - starting_balance:.4f}",
                             f"{asset_delta['delta']:.4f}"])
        df = pd.DataFrame(rows, index=None, columns=["Market", "Asset", "Starting", "Current", "Net Delta",
                                                     "Trade Delta"])
        return df

    def _calculate_trade_performance(self,  # type: HummingbotApplication
                                     ) -> Tuple[Dict, Dict]:
        raw_queried_trades = self._get_trades_from_session(self.init_time, config_file_path=self.strategy_file_name)
        current_strategy_name: str = self.markets_recorder.strategy_name
        conversion_rate = secondary_market_conversion_rate(current_strategy_name)
        trade_performance_stats, market_trading_pair_stats = calculate_trade_performance(
            current_strategy_name,
            self.market_trading_pair_tuples,
            raw_queried_trades,
            self.starting_balances,
            secondary_market_conversion_rate=conversion_rate
        )
        return trade_performance_stats, market_trading_pair_stats

    def calculate_profitability(self,  # type: HummingbotApplication
                                ) -> Decimal:
        """
        Determines the profitability of the trading bot.
        This function is used by the KillSwitch class.
        Must be updated if the method of performance report gets updated.
        """
        if not self.markets_recorder:
            return Decimal("0.0")
        trade_performance_stats, _ = self._calculate_trade_performance()
        portfolio_delta_percentage: Decimal = trade_performance_stats["portfolio_delta_percentage"]
        return portfolio_delta_percentage

    def trade_performance_report(self,  # type: HummingbotApplication
                                 ) -> Optional[pd.DataFrame]:
        if len(self.market_trading_pair_tuples) == 0 or self.markets_recorder is None:
            self._notify("\n  Performance analysis is not available when the bot is stopped.")
            return

        try:
            trade_performance_stats, market_trading_pair_stats = self._calculate_trade_performance()
            primary_quote_asset: str = self.market_trading_pair_tuples[0].quote_asset.upper()

            trade_performance_status_line = []
            market_df_data: Set[Tuple[str, str, Decimal, Decimal, str, str]] = set()
            market_df_columns = ["Market", "Pair", "Start Price", "End Price",
                                 "Trades", "Trade Value Delta"]

            for market_trading_pair_tuple, trading_pair_stats in market_trading_pair_stats.items():
                market_df_data.add((
                    market_trading_pair_tuple.market.display_name,
                    market_trading_pair_tuple.trading_pair.upper(),
                    trading_pair_stats["starting_quote_rate"],
                    trading_pair_stats["end_quote_rate"],
                    trading_pair_stats["trade_count"],
                    f"{trading_pair_stats['trading_pair_delta']:.8f} {primary_quote_asset}"
                ))

            inventory_df: pd.DataFrame = self.balance_comparison_data_frame(market_trading_pair_stats)
            market_df: pd.DataFrame = pd.DataFrame(data=list(market_df_data), columns=market_df_columns)
            portfolio_delta: Decimal = trade_performance_stats["portfolio_delta"]
            portfolio_delta_percentage: Decimal = trade_performance_stats["portfolio_delta_percentage"]

            trade_performance_status_line.extend(["", "  Inventory:"] +
                                                 ["    " + line for line in inventory_df.to_string().split("\n")])
            trade_performance_status_line.extend(["", "  Markets:"] +
                                                 ["    " + line for line in market_df.to_string().split("\n")])

            trade_performance_status_line.extend(
                ["", "  Performance:"] +
                [f"    Started: {datetime.fromtimestamp(self.start_time//1e3)}"] +
                [f"    Duration: {pd.Timedelta(seconds=abs(int(time.time() - self.start_time/1e3)))}"] +
                [f"    Total Trade Value Delta: {portfolio_delta:.7g} {primary_quote_asset}"] +
                [f"    Return %: {portfolio_delta_percentage:.4f} %"])

            self._notify("\n".join(trade_performance_status_line))

        except Exception:
            self.logger().error("Unexpected error running performance analysis.", exc_info=True)
            self._notify("Error running performance analysis.")

    def list_trades(self,  # type: HummingbotApplication
                    days: float = 0.0):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.list_trades)
            return

        lines = []
        start_timestamp = get_timestamp(days)
        start_timestamp = int(start_timestamp * 1e3)
        queried_trades: List[TradeFill] = self._get_trades_from_session(start_timestamp,
                                                                        MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT + 1,
                                                                        self.strategy_file_name)
        if self.strategy_name == "celo_arb":
            celo_trades = self.strategy.celo_orders_to_trade_fills()
            queried_trades = queried_trades + celo_trades
        df: pd.DataFrame = TradeFill.to_pandas(queried_trades)

        if len(df) > 0:
            # Check if number of trades exceed maximum number of trades to display
            if len(df) > MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT:
                df_lines = str(df[:MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT]).split("\n")
                self._notify(
                    f"\n  Showing last {MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT} trades in the current session.")
            else:
                df_lines = str(df).split("\n")
            lines.extend(["", "  Recent trades:"] +
                         ["    " + line for line in df_lines])
        else:
            lines.extend(["\n  No past trades in this session."])
        self._notify("\n".join(lines))
