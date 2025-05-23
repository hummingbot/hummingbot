from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class FormatStatusExample(ScriptStrategyBase):
    """
    This example shows how to add a custom format_status to a strategy and query the order book.
    Run the command status --live, once the strategy starts.
    """
    markets = {
        "binance_paper_trade": {"ETH-USDT", "BTC-USDT", "POL-USDT", "AVAX-USDT", "WLD-USDT", "DOGE-USDT", "SHIB-USDT", "XRP-USDT", "SOL-USDT"},
        "kucoin_paper_trade": {"ETH-USDT", "BTC-USDT", "POL-USDT", "AVAX-USDT", "WLD-USDT", "DOGE-USDT", "SHIB-USDT", "XRP-USDT", "SOL-USDT"},
        "gate_io_paper_trade": {"ETH-USDT", "BTC-USDT", "POL-USDT", "AVAX-USDT", "WLD-USDT", "DOGE-USDT", "SHIB-USDT", "XRP-USDT", "SOL-USDT"},
    }

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        market_status_df = self.get_market_status_df_with_depth()
        lines.extend(["", "  Market Status Data Frame:"] + ["    " + line for line in market_status_df.to_string(index=False).split("\n")])
        return "\n".join(lines)

    def get_market_status_df_with_depth(self):
        market_status_df = self.market_status_data_frame(self.get_market_trading_pair_tuples())
        market_status_df["Exchange"] = market_status_df.apply(lambda x: x["Exchange"].strip("PaperTrade") + "paper_trade", axis=1)
        market_status_df["Volume (+1%)"] = market_status_df.apply(lambda x: self.get_volume_for_percentage_from_mid_price(x, 0.01), axis=1)
        market_status_df["Volume (-1%)"] = market_status_df.apply(lambda x: self.get_volume_for_percentage_from_mid_price(x, -0.01), axis=1)
        market_status_df.sort_values(by=["Market"], inplace=True)
        return market_status_df

    def get_volume_for_percentage_from_mid_price(self, row, percentage):
        price = row["Mid Price"] * (1 + percentage)
        is_buy = percentage > 0
        result = self.connectors[row["Exchange"]].get_volume_for_price(row["Market"], is_buy, price)
        return result.result_volume
