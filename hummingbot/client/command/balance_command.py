from hummingbot.user.user_balances import UserBalances
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map

from hummingbot.client.config.config_helpers import (
    save_to_yml
)
from hummingbot.client.config.config_validators import validate_decimal, validate_exchange
from hummingbot.market.celo.celo_cli import CeloCLI
import pandas as pd
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional, List, Any

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

OPTIONS = [
    "limit",
    "paper"
]

OPTION_HELP = {
    "limit": "balance limit [exchange] [ASSET] [AMOUNT]",
    "paper": "balance paper [ASSET] [AMOUNT]"
}

OPTION_DESCRIPTION = {
    "limit": "Configure the asset limits for specified exchange",
    "paper": "Configure asset balances used in paper trading mode"
}

LIMIT_GLOBAL_CONFIG = "balance_asset_limit"
PAPER_ACC_BALANCE_CONFIG = "paper_trade_account_balance"


class BalanceCommand:
    def balance(self,
                option: str = None,
                args: List[str] = None
                ):
        self.app.clear_input()
        if option is None:
            safe_ensure_future(self.show_balances())

        elif option in OPTIONS:
            config_map = global_config_map
            file_path = GLOBAL_CONFIG_PATH
            if option == "limit":
                config_var = config_map[LIMIT_GLOBAL_CONFIG]
                if args is None or len(args) == 0:
                    safe_ensure_future(self.show_asset_limits())
                    return
                if len(args) != 3 or validate_exchange(args[0]) is not None or validate_decimal(args[2]) is not None:
                    self._notify("Error: Invalid command arguments")
                    self.notify_balance_limit_set()
                    return
                exchange = args[0]
                asset = args[1].upper()
                amount = float(args[2])
                exchange_limit_conf = config_var.value[exchange]
                if exchange_limit_conf is None:
                    config_var.value.update({asset: {}})
                self._notify(f"Limit for {asset} on {exchange} exchange set to {amount}")
                config_var.value[exchange].update({asset: amount})
                save_to_yml(file_path, config_map)

            elif option == "paper":
                config_var = config_map[PAPER_ACC_BALANCE_CONFIG]
                if args is None or len(args) == 0:
                    safe_ensure_future(self.show_paper_account_balance())
                    return
                if len(args) != 2 or validate_decimal(args[1]) is not None:
                    self._notify("Error: Invalid command arguments")
                    self.notify_balance_paper_set()
                    return
                asset = args[0].upper()
                amount = float(args[1])
                asset_config = [c for c in config_var.value if c[0] == asset]
                if asset_config:
                    asset_config[0][1] = amount
                else:
                    config_var.value.append([asset, amount])
                self._notify(f"Paper balance for {asset} token set to {amount}")
                save_to_yml(file_path, config_map)

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


    async def asset_limits_df(self,
                              asset_limit_conf: Dict[str, str]):
        rows = []
        for token, amount in asset_limit_conf.items():
            rows.append({"Asset": token, "Limit": round(Decimal(amount), 4)})

        df = pd.DataFrame(data=rows, columns=["Asset", "Limit"])
        df.sort_values(by=["Asset"], inplace=True)
        return df

    async def show_asset_limits(self):
        config_var = global_config_map[LIMIT_GLOBAL_CONFIG]
        exchange_limit_conf: Dict[str, Dict[str, str]] = config_var.value

        if not any(list(exchange_limit_conf.values())):
            self._notify("You have not set any limits.")
            self.notify_balance_limit_set()
            return

        self._notify(f"Balance Limits per exchange...")

        for exchange, asset_limit_config in exchange_limit_conf.items():
            if asset_limit_config is None:
                continue

            self._notify(f"\n{exchange}")
            df = await self.asset_limits_df(asset_limit_config)
            if df.empty:
                self._notify("You have no limits on this exchange.")
            else:
                lines = ["    " + line for line in df.to_string(index=False).split("\n")]
                self._notify("\n".join(lines))
        self._notify("\n")
        return

    async def paper_acccount_balance_df(self, paper_balances: List[List[Any]]):
        rows = []
        for balance in paper_balances:
            rows.append({"Asset": balance[0], "Balance": round(Decimal(balance[1]), 4)})
        df = pd.DataFrame(data=rows, columns=["Asset", "Balance"])
        df.sort_values(by=["Asset"], inplace=True)
        return df

    def notify_balance_limit_set(self):
        self._notify("To set a balance limit (how much the bot can use): \n"
                     "    balance limit [EXCHANGE] [ASSET] [AMOUNT]\n"
                     "e.g. balance limit binance BTC 0.1")

    def notify_balance_paper_set(self):
        self._notify("To set a paper account balance: \n"
                     "    balance paper [ASSET] [AMOUNT]\n"
                     "e.g. balance paper BTC 0.1")

    async def show_paper_account_balance(self):
        paper_balances = global_config_map[PAPER_ACC_BALANCE_CONFIG].value
        if not paper_balances:
            self._notify("You have not set any paper account balance.")
            self.notify_balance_paper_set()
            return
        self._notify("Paper account balances:")
        df = await self.paper_acccount_balance_df(paper_balances)
        lines = ["    " + line for line in df.to_string(index=False).split("\n")]
        self._notify("\n".join(lines))
        self._notify("\n")
        return

