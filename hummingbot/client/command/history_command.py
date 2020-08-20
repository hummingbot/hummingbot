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
from hummingbot.market.market_base import MarketBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from datetime import datetime
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.settings import MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.config.config_helpers import secondary_market_conversion_rate

s_float_0 = float(0)


if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class HistoryCommand:
    def history(self,  # type: HummingbotApplication
                ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.history)
            return

        if not all(market.ready for market in self.markets.values()):
            self._notify("\n  History stats are not available before Markets are ready.")
            return
        if global_config_map.get("paper_trade_enabled").value:
            self._notify("\n  Paper Trading ON: All orders are simulated, and no real orders are placed.")
        self.list_trades()
        if self.strategy_name != "celo_arb":
            self.trade_performance_report()

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
            market: MarketBase = market_trading_pair_tuple.market
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
                    ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.list_trades)
            return

        lines = []
        if self.strategy is None:
            self._notify("Bot not started. No past trades.")
        else:
            # Query for maximum number of trades to display + 1
            queried_trades: List[TradeFill] = self._get_trades_from_session(self.init_time,
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
