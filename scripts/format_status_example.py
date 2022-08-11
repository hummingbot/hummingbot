from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class FormatStatusExample(ScriptStrategyBase):
    """
    This example shows how to add a custom format_status to a strategy.
    Run the command status --live, once the strategy starts.
    """
    markets = {
        "gate_io_paper_trade": {"ETH-USDT"},
        "kucoin_paper_trade": {"ETH-USDT"},
        "binance_paper_trade": {"ETH-USDT"}
    }

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        market_status_df = self.market_status_data_frame(self.get_market_trading_pair_tuples())
        lines.extend(["", "  Market Status:"] + ["    " + line for line in market_status_df.to_string(index=False).split("\n")])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
