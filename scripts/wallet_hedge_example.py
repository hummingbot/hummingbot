from decimal import Decimal
from typing import Dict

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType
from hummingbot.data_feed.wallet_tracker_data_feed import WalletTrackerDataFeed
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class WalletHedgeExample(ScriptStrategyBase):
    # Wallet params
    token = "WETH"
    wallet_balance_data_feed = WalletTrackerDataFeed(
        chain="ethereum",
        network="goerli",
        wallets={"0xDA50C69342216b538Daf06FfECDa7363E0B96684"},
        tokens={token},
    )
    hedge_threshold = 0.05

    # Hedge params
    hedge_exchange = "kucoin_paper_trade"
    hedge_pair = "ETH-USDT"
    base, quote = hedge_pair.split("-")

    # Balances variables
    balance = 0
    balance_start = 0
    balance_delta = 0
    balance_hedge = 0
    exchange_balance_start = 0
    exchange_balance = 0

    markets = {hedge_exchange: {hedge_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.wallet_balance_data_feed.start()

    def on_stop(self):
        self.wallet_balance_data_feed.stop()

    def on_tick(self):
        self.balance = self.wallet_balance_data_feed.wallet_balances_df[self.token].sum()
        self.exchange_balance = self.get_exchange_base_asset_balance()

        if self.balance_start == 0:  # first run
            self.balance_start = self.balance
            self.balance_hedge = self.balance
            self.exchange_balance_start = self.get_exchange_base_asset_balance()
        else:
            self.balance_delta = self.balance - self.balance_hedge

        mid_price = self.connectors[self.hedge_exchange].get_mid_price(self.hedge_pair)
        if self.balance_delta > 0 and self.balance_delta >= self.hedge_threshold:
            self.sell(self.hedge_exchange, self.hedge_pair, self.balance_delta, OrderType.MARKET, mid_price)
            self.balance_hedge = self.balance
        elif self.balance_delta < 0 and self.balance_delta <= -self.hedge_threshold:
            self.buy(self.hedge_exchange, self.hedge_pair, -self.balance_delta, OrderType.MARKET, mid_price)
            self.balance_hedge = self.balance

    def get_exchange_base_asset_balance(self):
        balance_df = self.get_balance_df()
        row = balance_df.iloc[0]
        return Decimal(row["Total Balance"])

    def format_status(self) -> str:
        if self.wallet_balance_data_feed.is_ready():
            lines = []
            prices_str = format_df_for_printout(self.wallet_balance_data_feed.wallet_balances_df,
                                                table_format="psql", index=True)
            lines.append(f"\nWallet Data Feed:\n{prices_str}")

            precision = 3
            if self.balance_start > 0:
                lines.append("\nWallets:")
                lines.append(f"  Starting {self.token} balance: {round(self.balance_start, precision)}")
                lines.append(f"  Current {self.token} balance: {round(self.balance, precision)}")
                lines.append(f"  Delta: {round(self.balance - self.balance_start, precision)}")
                lines.append("\nExchange:")
                lines.append(f"  Starting {self.base} balance: {round(self.exchange_balance_start, precision)}")
                lines.append(f"  Current {self.base} balance: {round(self.exchange_balance, precision)}")
                lines.append(f"  Delta: {round(self.exchange_balance - self.exchange_balance_start, precision)}")
                lines.append("\nHedge:")
                lines.append(f"  Threshold: {self.hedge_threshold}")
                lines.append(f"  Delta from last hedge: {round(self.balance_delta, precision)}")
            return "\n".join(lines)
        else:
            return "Wallet Data Feed is not ready."
