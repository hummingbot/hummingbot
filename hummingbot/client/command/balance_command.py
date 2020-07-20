from hummingbot.user.user_balances import UserBalances
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.market.celo.celo_cli import CeloCLI
import pandas as pd
from decimal import Decimal
from typing import TYPE_CHECKING, Dict
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class BalanceCommand:
    def balance(self):
        safe_ensure_future(self.show_balances())

    async def show_balances(self):
        self._notify("Updating balances, please wait...")
        all_ex_bals = await UserBalances.instance().all_balances_all_exchanges()
        for exchange, bals in all_ex_bals.items():
            self._notify(f"\n{exchange}:")
            df = await self.exchange_balances_df(bals)
            if df.empty:
                self._notify("You have no balance on this exchange.")
            else:
                lines = ["    " + line for line in df.to_string(index=False).split("\n")]
                self._notify("\n".join(lines))

        celo_address = global_config_map["celo_address"].value
        if celo_address is not None:
            try:
                if not CeloCLI.unlocked:
                    await self.validate_n_connect_celo()
                df = await self.celo_balances_df()
                lines = ["    " + line for line in df.to_string(index=False).split("\n")]
                self._notify("\ncelo:")
                self._notify("\n".join(lines))
            except Exception as e:
                self._notify(f"\ncelo CLI Error: {str(e)}")

        eth_address = global_config_map["ethereum_wallet"].value
        if eth_address is not None:
            df = await self.ethereum_balances_df()
            lines = ["    " + line for line in df.to_string(index=False).split("\n")]
            self._notify("\nethereum:")
            self._notify("\n".join(lines))

    async def exchange_balances_df(self,  # type: HummingbotApplication
                                   ex_bals: Dict[str, Decimal]):
        rows = []
        for token, bal in ex_bals.items():
            if bal == 0:
                continue
            token = token.upper()
            rows.append({"asset": token.upper(), "amount": round(bal, 4)})
        df = pd.DataFrame(data=rows, columns=["asset", "amount"])
        df.sort_values(by=["asset"], inplace=True)
        return df

    async def celo_balances_df(self,  # type: HummingbotApplication
                               ):
        rows = []
        bals = CeloCLI.balances()
        for token, bal in bals.items():
            rows.append({"asset": token.upper(), "amount": round(bal.total, 4)})
        df = pd.DataFrame(data=rows, columns=["asset", "amount"])
        df.sort_values(by=["asset"], inplace=True)
        return df

    async def ethereum_balances_df(self,  # type: HummingbotApplication
                                   ):
        rows = []
        bal = UserBalances.ethereum_balance()
        rows.append({"asset": "ETH", "amount": round(bal, 4)})
        df = pd.DataFrame(data=rows, columns=["asset", "amount"])
        df.sort_values(by=["asset"], inplace=True)
        return df
