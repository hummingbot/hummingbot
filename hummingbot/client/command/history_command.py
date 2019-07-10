import pandas as pd
from typing import (
    Any,
    Dict,
    TYPE_CHECKING,
)
from hummingbot.client.performance_analysis import PerformanceAnalysis

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class HistoryCommand:
    def history(self,  # type: HummingbotApplication
                ):
        self.list("trades")
        self.compare_balance_snapshots()
        self.analyze_performance()

    def balance_snapshot(self,  # type: HummingbotApplication
                         ) -> Dict[str, Dict[str, float]]:
        snapshot: Dict[str, Any] = {}
        for market_name in self.markets:
            balance_dict = self.markets[market_name].get_all_balances()
            for c in self.assets:
                if c not in snapshot:
                    snapshot[c] = {}
                if c in balance_dict:
                    snapshot[c][market_name] = balance_dict[c]
                else:
                    snapshot[c][market_name] = 0.0
        return snapshot

    def compare_balance_snapshots(self,  # type: HummingbotApplication
                                  ):
        if len(self.starting_balances) == 0:
            self._notify("  Balance snapshots are not available before bot starts")
            return

        rows = []
        for market_name in self.markets:
            for asset in self.assets:
                starting_balance = self.starting_balances.get(asset).get(market_name)
                current_balance = self.balance_snapshot().get(asset).get(market_name)
                rows.append([market_name,
                             asset,
                             starting_balance,
                             current_balance,
                             current_balance - starting_balance])

        df = pd.DataFrame(rows, index=None, columns=["Market", "Asset", "Starting", "Current", "Delta"])
        lines = ["", "  Inventory:"] + ["    " + line for line in str(df).split("\n")]
        self._notify("\n".join(lines))

    def analyze_performance(self,  # type: HummingbotApplication
                            ):
        """ Determine the profitability of the trading bot. """
        if len(self.starting_balances) == 0:
            self._notify("  Performance analysis is not available before bot starts")
            return

        performance_analysis = PerformanceAnalysis()

        for market_symbol_pair in self.market_symbol_pairs:
            for is_base in [True, False]:
                for is_starting in [True, False]:
                    market_name = market_symbol_pair.market.name
                    asset_name = market_symbol_pair.base_asset if is_base else market_symbol_pair.quote_asset
                    amount = self.starting_balances[asset_name][market_name] if is_starting \
                        else self.balance_snapshot()[asset_name][market_name]
                    amount = float(amount)
                    performance_analysis.add_balances(asset_name, amount, is_base, is_starting)

        # Compute the current exchange rate. We use the first market_symbol_pair because
        # if the trading pairs are different, such as WETH-DAI and ETH-USD, the currency
        # pairs above will contain the information in terms of the first trading pair.
        market_pair_info = self.market_symbol_pairs[0]
        market = market_pair_info.market
        buy_price = market.get_price(market_pair_info.trading_pair, True)
        sell_price = market.get_price(market_pair_info.trading_pair, False)
        price = (buy_price + sell_price)/2.0

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


