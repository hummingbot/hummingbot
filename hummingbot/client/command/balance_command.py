from hummingbot.client.settings import (
    GLOBAL_CONFIG_PATH,
)
from hummingbot.user.user_balances import UserBalances
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_helpers import (
    save_to_yml
)
from hummingbot.market.celo.celo_cli import CeloCLI
import pandas as pd
from decimal import Decimal
from typing import TYPE_CHECKING, Dict
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

OPTIONS = [
    "limit",
]

OPTION_HELP = {
    "limit": "balance limit [exchange] [ASSET] [AMOUNT]",
}

OPTION_DESCRIPTION = {
    "limit": "Configure the asset limits for specified exchange",
}

LIMIT_GLOBAL_CONFIG = "balance_asset_limit"


class BalanceCommand:
    def balance(self,
                option: str = None,
                exchange: str = None,
                asset: str = None,
                amount: str = None,
                ):
        self.app.clear_input()
        if option is None:
            safe_ensure_future(self.show_balances())

        elif option in OPTIONS:
            config_map = global_config_map
            file_path = GLOBAL_CONFIG_PATH
            if option == "limit":

                config_var = config_map[LIMIT_GLOBAL_CONFIG]
                if exchange is None and asset is None and amount is None:
                    safe_ensure_future(self.show_asset_limits())
                    return

                if asset is not None and amount is not None and exchange is not None:
                    exchange_limit_conf = config_var.value[exchange]
                    asset = asset.upper()
                    self._notify(f"Limit for {asset} token, set to {amount}")
                    exchange_limit_conf[asset] = amount
                    return

                self._notify("Error with command arguments. See command details below.")
                safe_ensure_future(self.list_options())
                return

            save_to_yml(file_path, config_map)

    async def list_options(self):
        row = []
        self._notify(f"List of Option(s) of Balance command\n")
        for option in OPTIONS:
            row.append(f"{option}: {OPTION_DESCRIPTION[option]}")
            row.append(f"   e.g. {OPTION_HELP[option]}")
        self._notify("\n".join(row))

    async def show_balances(self):
        self._notify("Updating balances, please wait...")
        all_ex_bals = await UserBalances.instance().all_balances_all_exchanges()
        all_ex_limits = global_config_map[LIMIT_GLOBAL_CONFIG].value
        for exchange, bals in all_ex_bals.items():
            self._notify(f"\n{exchange}:")
            df = await self.exchange_balances_df(bals, all_ex_limits[exchange])
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
                                   exchange_balances: Dict[str, Decimal],
                                   exchange_limits: Dict[str, str] = None):
        rows = []
        for token, bal in exchange_balances.items():
            limit = Decimal(exchange_limits.get(token, 0))
            if bal == 0 and limit == 0:
                continue
            token = token.upper()
            rows.append({"Asset": token.upper(), "Amount": round(bal, 4), "Limit": round(limit, 4)})
        df = pd.DataFrame(data=rows, columns=["Asset", "Amount", "Limit"])
        df.sort_values(by=["Asset"], inplace=True)
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
        self._notify(f"Balance Limits per exchange...")
        config_var = global_config_map[LIMIT_GLOBAL_CONFIG]
        exchange_limit_conf: Dict[str, Dict[str, str]] = config_var.value

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
