from hummingbot.user.user_balances import UserBalances
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion as ERC
from hummingbot.client.config.global_config_map import global_config_map
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

    async def balances_df(self  # type: HummingbotApplication
                          ):
        all_ex_bals = await UserBalances.instance().all_balances_all_exchanges()
        ex_columns = [ex for ex, bals in all_ex_bals.items() if any(bal > 0 for bal in bals.values())]
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
        for row in rows:
            ex_total = 0
            for ex, amount in row.items():
                try:
                    if ex != "Symbol":
                        ex_total += ERC.get_instance().convert_token_value_decimal(amount, row["Symbol"], "USD")
                except Exception:
                    continue
            row["Total(USD)"] = round(ex_total, 2)
        last_row = {"Symbol": "Total(USD)"}
        for ex in ex_columns:
            token_total = 0
            for row in rows:
                try:
                    token_total += ERC.get_instance().convert_token_value_decimal(row[ex], row["Symbol"], "USD")
                except Exception:
                    continue
            last_row[ex] = round(token_total, 2)
        last_row["Total(USD)"] = round(sum(amount for ex, amount in last_row.items() if ex in ex_columns), 2)
        ex_columns.sort(key=lambda ex: last_row[ex], reverse=True)
        columns = ["Symbol"] + ex_columns + ["Total(USD)"]
        df = pd.DataFrame(data=rows, columns=columns)
        df = df.replace(NaN, 0)
        df.sort_values(by=["Total(USD)"], inplace=True, ascending=False)
        df = df.append(last_row, ignore_index=True, sort=False)
        return df
