from decimal import Decimal

import pandas as pd
import threading
from typing import (
    Any,
    Dict,
    Set,
    Tuple,
    Optional,
    TYPE_CHECKING,
)
from hummingbot.client.performance_analysis import PerformanceAnalysis
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.market.market_base import MarketBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

ERC = ExchangeRateConversion.get_instance()
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
            self._notify("  History stats are not available before Markets are ready.")
            return
        self.list_trades()
        self.trade_performance_report()

    def balance_snapshot(self,  # type: HummingbotApplication
                         ) -> Dict[str, Dict[str, float]]:
        snapshot: Dict[str, Any] = {}
        for market_name in self.markets:
            balance_dict = self.markets[market_name].get_all_balances()
            balance_dict = {k.upper(): v for k, v in balance_dict.items()}

            for asset in self.assets:
                asset = asset.upper()
                if asset not in snapshot:
                    snapshot[asset] = {}
                if asset in balance_dict:
                    snapshot[asset][market_name] = balance_dict[asset]
                else:
                    snapshot[asset][market_name] = 0.0
        return snapshot

    def balance_comparison_data_frame(self,  # type: HummingbotApplication
                                      market_trading_pair_stats: Dict[MarketTradingPairTuple, any],
                                      ) -> pd.DataFrame:
        if len(self.starting_balances) == 0:
            self._notify("  Balance snapshots are not available before bot starts")
            return
        rows = []
        for market_trading_pair_tuple in self.market_trading_pair_tuples:
            market: MarketBase = market_trading_pair_tuple.market
            for asset in set(a.upper() for a in self.assets):
                asset_delta: Dict[str, float] = market_trading_pair_stats[market_trading_pair_tuple]["asset"].get(
                    asset, {"delta": s_float_0})
                starting_balance = self.starting_balances.get(asset).get(market.name)
                current_balance = self.balance_snapshot().get(asset).get(market.name)
                rows.append([market.display_name,
                             asset,
                             float(starting_balance),
                             float(current_balance),
                             float(current_balance - starting_balance),
                             float(asset_delta["delta"]),
                             ERC.adjust_token_rate(asset, Decimal(1))])
        df = pd.DataFrame(rows, index=None, columns=["Market", "Asset", "Starting", "Current", "Net_Delta",
                                                     "Trade_Delta", "Conversion_Rate"])
        return df

    def _calculate_trade_performance(self,  # type: HummingbotApplication
                                     ) -> Tuple[Dict, Dict]:
        raw_queried_trades = self._get_trades_from_session(self.init_time)
        current_strategy_name: str = self.markets_recorder.strategy_name
        performance_analysis: PerformanceAnalysis = PerformanceAnalysis()
        trade_performance_stats, market_trading_pair_stats = performance_analysis.calculate_trade_performance(
            current_strategy_name,
            self.market_trading_pair_tuples,
            raw_queried_trades,
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
            self._notify("  Performance analysis is not available when the bot is stopped.")
            return

        try:
            trade_performance_stats, market_trading_pair_stats = self._calculate_trade_performance()
            primary_quote_asset: str = self.market_trading_pair_tuples[0].quote_asset.upper()

            trade_performance_status_line = []
            market_df_data: Set[Tuple[str, str, float, float, str, str]] = set()
            market_df_columns = ["Market", "Trading_Pair", "Start_Price", "End_Price",
                                 "Total_Value_Delta", "Profit"]

            for market_trading_pair_tuple, trading_pair_stats in market_trading_pair_stats.items():
                market_df_data.add((
                    market_trading_pair_tuple.market.display_name,
                    market_trading_pair_tuple.trading_pair.upper(),
                    float(trading_pair_stats["starting_quote_rate"]),
                    float(trading_pair_stats["end_quote_rate"]),
                    f"{trading_pair_stats['trading_pair_delta']:.8f} {primary_quote_asset}",
                    f"{trading_pair_stats['trading_pair_delta_percentage']:.3f} %"
                ))

            inventory_df: pd.DataFrame = self.balance_comparison_data_frame(market_trading_pair_stats)
            market_df: pd.DataFrame = pd.DataFrame(data=list(market_df_data), columns=market_df_columns)
            portfolio_delta: Decimal = trade_performance_stats["portfolio_delta"]
            portfolio_delta_percentage: Decimal = trade_performance_stats["portfolio_delta_percentage"]

            trade_performance_status_line.extend(["", "  Inventory:"] +
                                                 ["    " + line for line in inventory_df.to_string().split("\n")])
            trade_performance_status_line.extend(["", "  Market Trading Pair Performance:"] +
                                                 ["    " + line for line in market_df.to_string().split("\n")])

            trade_performance_status_line.extend(
                ["", "  Portfolio Performance:"] +
                [f"    Quote Value Delta: {portfolio_delta:.7g} {primary_quote_asset}"] +
                [f"    Delta Percentage: {portfolio_delta_percentage:.3f} %"])

            self._notify("\n".join(trade_performance_status_line))

        except Exception:
            self.logger().error("Unexpected error running performance analysis.", exc_info=True)
            self._notify("Error running performance analysis.")
