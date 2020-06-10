from hummingbot.user.user_balances import UserBalances
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.market.celo.celo_cli import CeloCLI
import pandas as pd
from numpy import NaN
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class BalanceCommand:
    def balance(self):
        safe_ensure_future(self.show_balances())

    async def show_balances(self):
        self._notify("Updating balances, please wait...")
        df = await self.balances_df()
        lines = ["    " + line for line in df.to_string(index=False).split("\n")]
        self._notify("\n".join(lines))
        eth_address = global_config_map["ethereum_wallet"].value
        if eth_address is not None:
            bal = UserBalances.ethereum_balance()
            bal = round(bal, 4)
            self._notify(f"Ethereum balance in ...{eth_address[-4:]} wallet: {bal} ETH")
            self._notify(f"Note: You may have other ERC 20 tokens in this same address (not shown here).")
        celo_address = global_config_map["celo_address"].value
        if celo_address is not None:
            try:
                if not CeloCLI.unlocked:
                    await self.validate_n_connect_celo()
                bals = CeloCLI.balances()
                self._notify("Celo balances:")
                for token, bal in bals.items():
                    self._notify(f"  {token} - total: {bal.total} locked: {bal.locked}")
            except Exception as e:
                self._notify(f"Celo CLI Error: {str(e)}")

    async def balances_df(self  # type: HummingbotApplication
                          ):
        all_ex_bals = await UserBalances.instance().all_balances_all_exchanges()
        ex_columns = ["Symbol"] + list(all_ex_bals.keys())
        rows = []
        for exchange, bals in all_ex_bals.items():
            for token, bal in bals.items():
                if bal == 0:
                    continue
                token = token.upper()
                if not any(r.get("Symbol") == token for r in rows):
                    rows.append({"Symbol": token})
                row = [r for r in rows if r["Symbol"] == token][0]
                row[exchange] = round(bal, 4)

        df = pd.DataFrame(data=rows, columns=ex_columns)
        df = df.replace(NaN, 0)
        df.sort_values(by=["Symbol"], inplace=True)
        return df
