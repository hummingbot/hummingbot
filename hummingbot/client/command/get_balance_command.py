import pandas as pd
from typing import TYPE_CHECKING

from hummingbot.connector.exchange_base import ExchangeBase

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class GetBalanceCommand:
    def get_wallet_balance(self,  # type: HummingbotApplication
                           ) -> pd.DataFrame:
        return pd.DataFrame(data=list(self.wallet.get_all_balances().items()),
                            columns=["currency", "balance"]).set_index("currency")

    def get_exchange_balance(self,  # type: HummingbotApplication
                             exchange_name: str) -> pd.DataFrame:
        market: ExchangeBase = self.markets[exchange_name]
        raw_balance: pd.DataFrame = pd.DataFrame(data=list(market.get_all_balances().items()),
                                                 columns=["currency", "balance"]).set_index("currency")
        return raw_balance[raw_balance.balance > 0]

    def get_balance(self,  # type: HummingbotApplication
                    currency: str = "WETH",
                    wallet: bool = False,
                    exchange: str = None):
        if wallet:
            if self.wallet is None:
                self._notify('Wallet not available. Please configure your wallet (Enter "config wallet")')
            elif currency is None:
                self._notify(f"{self.get_wallet_balance()}")
            else:
                self._notify(self.wallet.get_balance(currency.upper()))
        elif exchange:
            if exchange in self.markets:
                if currency is None:
                    self._notify(f"{self.get_exchange_balance(exchange)}")
                else:
                    self._notify(self.markets[exchange].get_balance(currency.upper()))
            else:
                self._notify('The exchange you entered has not been initialized. '
                             'You may check your exchange balance after entering the "start" command.')
        else:
            self.help("get_balance")
