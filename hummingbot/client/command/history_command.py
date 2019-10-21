from decimal import Decimal

import pandas as pd
from typing import (
    Any,
    Dict,
    Set,
    Tuple,
    TYPE_CHECKING)
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

    def get_performance_analysis_with_updated_balance(self,  # type: HummingbotApplication
                                                      ) -> PerformanceAnalysis:
        performance_analysis = PerformanceAnalysis()
        dedup_set: Set[Tuple[str, str, bool]] = set()

        for market_trading_pair_tuple in self.market_trading_pair_tuples:
            for is_base in [True, False]:
                for is_starting in [True, False]:
                    market_name = market_trading_pair_tuple.market.name
                    asset_name = market_trading_pair_tuple.base_asset if is_base else market_trading_pair_tuple.quote_asset
                    asset_name = asset_name.upper()
                    if len(self.assets) == 0 or len(self.markets) == 0:
                        # Prevent KeyError '***SYMBOL***'
                        amount = self.starting_balances[asset_name][market_name]
                    else:
                        amount = self.starting_balances[asset_name][market_name] if is_starting \
                            else self.balance_snapshot()[asset_name][market_name]
                    amount = float(amount)

                    # Adding this check to prevent assets in the same market to be added multiple times
                    if (market_name, asset_name, is_starting) not in dedup_set:
                        dedup_set.add((market_name, asset_name, is_starting))
                        performance_analysis.add_balances(asset_name, amount, is_base, is_starting)

        return performance_analysis

    def get_market_mid_price(self,  # type: HummingbotApplication
                             ) -> float:
        # Compute the current exchange rate. We use the first market_symbol_pair because
        # if the trading pairs are different, such as WETH-DAI and ETH-USD, the currency
        # pairs above will contain the information in terms of the first trading pair.
        market_pair_info = self.market_trading_pair_tuples[0]
        market = market_pair_info.market
        buy_price = market.get_price(market_pair_info.trading_pair, True)
        sell_price = market.get_price(market_pair_info.trading_pair, False)
        price = float((buy_price + sell_price) / 2)
        return price

    def analyze_performance(self,  # type: HummingbotApplication
                            ):
        """ Calculate bot profitability and print to output pane """
        if len(self.starting_balances) == 0:
            self._notify("  Performance analysis is not available before bot starts")
            return

        performance_analysis: PerformanceAnalysis = self.get_performance_analysis_with_updated_balance()
        price: float = self.get_market_mid_price()

        starting_token, starting_amount = performance_analysis.compute_starting(price)
        current_token, current_amount = performance_analysis.compute_current(price)
        delta_token, delta_amount = performance_analysis.compute_delta(price)
        return_performance = performance_analysis.compute_return(price)

        starting_amount = round(starting_amount, 3)
        current_amount = round(current_amount, 3)
        delta_amount = round(delta_amount, 3)
        return_performance = round(return_performance, 3)

        print_performance = "\n"
        print_performance += "  Performance:\n"
        print_performance += "    - Starting Inventory Value: " + str(starting_amount) + " " + starting_token + "\n"
        print_performance += "    - Current Inventory Value: " + str(current_amount) + " " + current_token + "\n"
        print_performance += "    - Delta: " + str(delta_amount) + " " + delta_token + "\n"
        print_performance += "    - Return: " + str(return_performance) + "%"
        self._notify(print_performance)

    def calculate_profitability(self) -> float:
        """ Determine the profitability of the trading bot. """
        performance_analysis: PerformanceAnalysis = self.get_performance_analysis_with_updated_balance()
        price: float = self.get_market_mid_price()
        return_performance = performance_analysis.compute_return(price)
        return return_performance

    def trade_performance_report(self,  # type: HummingbotApplication
                                 ) -> pd.DataFrame:

        if len(self.market_trading_pair_tuples) == 0:
            self._notify("  Performance analysis is not available before bot starts")
            return
        try:
            current_strategy_name: str = self.markets_recorder.strategy_name
            analysis_start_time: int = self.init_time
            primary_quote_asset: str = self.market_trading_pair_tuples[0].quote_asset.upper()
            performance_analysis: PerformanceAnalysis = PerformanceAnalysis()
            trade_performance_stats, market_trading_pair_stats = performance_analysis.calculate_trade_performance(
                analysis_start_time,
                current_strategy_name,
                self.market_trading_pair_tuples
            )
            trade_performance_status_line = []
            market_df_data = []
            market_df_columns = ["Market", "Trading_Pair", "Start_Price", "End_Price",
                                 "Total_Value_Delta", "Profit"]

            for market_trading_pair_tuple, trading_pair_stats in market_trading_pair_stats.items():
                market_df_data.append([
                    market_trading_pair_tuple.market.display_name,
                    market_trading_pair_tuple.trading_pair.upper(),
                    float(trading_pair_stats["starting_quote_rate"]),
                    float(trading_pair_stats["end_quote_rate"]),
                    f"{trading_pair_stats['trading_pair_delta']:.8f} {primary_quote_asset}",
                    f"{trading_pair_stats['trading_pair_delta_percentage']:.3f} %"
                ])

            inventory_df: pd.DataFrame = self.balance_comparison_data_frame(market_trading_pair_stats)
            market_df: pd.DataFrame = pd.DataFrame(data=market_df_data, columns=market_df_columns)
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
            self._notify("Error running performance analysis")
