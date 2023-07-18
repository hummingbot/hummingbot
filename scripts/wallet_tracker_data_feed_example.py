from typing import Dict

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.wallet_tracker_data_feed import WalletTrackerDataFeed
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AMMDataFeedExample(ScriptStrategyBase):
    wallet_balance_data_feed = WalletTrackerDataFeed(
        chain="polygon",
        network="mainnet",
        wallets={"0x78afCe8414fb4DfcB01c35Db53547e71283779E7"},
        tokens={"USDC", "USDT", "ETH", "MATIC"},
    )
    markets = {"binance_paper_trade": {"BTC-USDT"}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.wallet_balance_data_feed.start()

    def on_stop(self):
        self.wallet_balance_data_feed.stop()

    def on_tick(self):
        if self.wallet_balance_data_feed.is_ready():
            self.logger().info(f"AMM Data Feed is ready.\n{self.wallet_balance_data_feed._wallet_balances}")
        else:
            self.logger().info("AMM Data Feed is not ready.")

    def format_status(self) -> str:
        if self.wallet_balance_data_feed.is_ready():
            lines = []

            prices_str = format_df_for_printout(self.wallet_balance_data_feed.wallet_balances_df,
                                                table_format="psql", index=True)
            lines.append(f"AMM Data Feed is ready.\n{prices_str}")
            return "\n".join(lines)
        else:
            return "AMM Data Feed is not ready."
