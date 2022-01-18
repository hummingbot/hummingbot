import asyncio

from hummingbot.client.settings import (
    GLOBAL_CONFIG_PATH,
    ethereum_required_trading_pairs
)
from hummingbot.user.user_balances import UserBalances
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_helpers import (
    save_to_yml
)
from hummingbot.client.config.config_validators import validate_decimal, validate_exchange
from hummingbot.connector.other.celo.celo_cli import CeloCLI
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
import pandas as pd
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional, List
import threading

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

OPTIONS = [
    "limit",
    "paper"
]


class BalanceCommand:
    def balance(self,
                option: str = None,
                args: List[str] = None
                ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.balance, option, args)
            return

        self.app.clear_input()
        if option is None:
            safe_ensure_future(self.show_balances())

        elif option in OPTIONS:
            config_map = global_config_map
            file_path = GLOBAL_CONFIG_PATH
            if option == "limit":
                config_var = config_map["balance_asset_limit"]
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
                if exchange not in config_var.value or config_var.value[exchange] is None:
                    config_var.value[exchange] = {}
                if amount < 0 and asset in config_var.value[exchange].keys():
                    config_var.value[exchange].pop(asset)
                    self._notify(f"Limit for {asset} on {exchange} exchange removed.")
                elif amount >= 0:
                    config_var.value[exchange][asset] = amount
                    self._notify(f"Limit for {asset} on {exchange} exchange set to {amount}")
                save_to_yml(file_path, config_map)

            elif option == "paper":
                config_var = config_map["paper_trade_account_balance"]
                if args is None or len(args) == 0:
                    safe_ensure_future(self.show_paper_account_balance())
                    return
                if len(args) != 2 or validate_decimal(args[1]) is not None:
                    self._notify("Error: Invalid command arguments")
                    self.notify_balance_paper_set()
                    return
                asset = args[0].upper()
                amount = float(args[1])
                paper_balances = dict(config_var.value) if config_var.value else {}
                paper_balances[asset] = amount
                config_var.value = paper_balances
                self._notify(f"Paper balance for {asset} token set to {amount}")
                save_to_yml(file_path, config_map)

    async def show_balances(self):
        total_col_name = f'Total ({RateOracle.global_token_symbol})'
        self._notify("Updating balances, please wait...")
        network_timeout = float(global_config_map["other_commands_timeout"].value)
        try:
            all_ex_bals = await asyncio.wait_for(
                UserBalances.instance().all_balances_all_exchanges(), network_timeout
            )
        except asyncio.TimeoutError:
            self._notify("\nA network error prevented the balances to update. See logs for more details.")
            raise
        all_ex_avai_bals = UserBalances.instance().all_avai_balances_all_exchanges()
        all_ex_limits: Optional[Dict[str, Dict[str, str]]] = global_config_map["balance_asset_limit"].value

        if all_ex_limits is None:
            all_ex_limits = {}

        exchanges_total = 0

        for exchange, bals in all_ex_bals.items():
            self._notify(f"\n{exchange}:")
            df, allocated_total = await self.exchange_balances_extra_df(bals, all_ex_avai_bals.get(exchange, {}))
            if df.empty:
                self._notify("You have no balance on this exchange.")
            else:
                lines = ["    " + line for line in df.to_string(index=False).split("\n")]
                self._notify("\n".join(lines))
                self._notify(f"\n  Total: {RateOracle.global_token_symbol} {PerformanceMetrics.smart_round(df[total_col_name].sum())}    "
                             f"Allocated: {allocated_total / df[total_col_name].sum():.2%}")
                exchanges_total += df[total_col_name].sum()

        self._notify(f"\n\nExchanges Total: {RateOracle.global_token_symbol} {exchanges_total:.0f}    ")

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
            eth_df = await self.ethereum_balances_df()
            lines = ["    " + line for line in eth_df.to_string(index=False).split("\n")]
            self._notify("\nethereum:")
            self._notify("\n".join(lines))

            # XDAI balances
            xdai_df = await self.xdai_balances_df()
            lines = ["    " + line for line in xdai_df.to_string(index=False).split("\n")]
            self._notify("\nxdai:")
            self._notify("\n".join(lines))

    async def exchange_balances_extra_df(self,  # type: HummingbotApplication
                                         ex_balances: Dict[str, Decimal],
                                         ex_avai_balances: Dict[str, Decimal]):
        total_col_name = f"Total ({RateOracle.global_token_symbol})"
        allocated_total = Decimal("0")
        rows = []
        for token, bal in ex_balances.items():
            if bal == Decimal(0):
                continue
            avai = Decimal(ex_avai_balances.get(token.upper(), 0)) if ex_avai_balances is not None else Decimal(0)
            allocated = f"{(bal - avai) / bal:.0%}"
            rate = await RateOracle.global_rate(token)
            rate = Decimal("0") if rate is None else rate
            global_value = rate * bal
            allocated_total += rate * (bal - avai)
            rows.append({"Asset": token.upper(),
                         "Total": round(bal, 4),
                         total_col_name: PerformanceMetrics.smart_round(global_value),
                         "Allocated": allocated,
                         })
        df = pd.DataFrame(data=rows, columns=["Asset", "Total", total_col_name, "Allocated"])
        df.sort_values(by=["Asset"], inplace=True)
        return df, allocated_total

    async def celo_balances_df(self,  # type: HummingbotApplication
                               ):
        rows = []
        bals = CeloCLI.balances()
        for token, bal in bals.items():
            rows.append({"Asset": token.upper(), "Amount": round(bal.total, 4)})
        df = pd.DataFrame(data=rows, columns=["Asset", "Amount"])
        df.sort_values(by=["Asset"], inplace=True)
        return df

    async def ethereum_balances_df(self,  # type: HummingbotApplication
                                   ):
        rows = []
        if ethereum_required_trading_pairs():
            bals = await UserBalances.eth_n_erc20_balances()
            for token, bal in bals.items():
                rows.append({"Asset": token, "Amount": round(bal, 4)})
        else:
            eth_bal = UserBalances.ethereum_balance()
            rows.append({"Asset": "ETH", "Amount": round(eth_bal, 4)})
        df = pd.DataFrame(data=rows, columns=["Asset", "Amount"])
        df.sort_values(by=["Asset"], inplace=True)
        return df

    async def xdai_balances_df(self,  # type: HummingbotApplication
                               ):
        rows = []
        bals = await UserBalances.xdai_balances()
        for token, bal in bals.items():
            rows.append({"Asset": token, "Amount": round(bal, 4)})
        df = pd.DataFrame(data=rows, columns=["Asset", "Amount"])
        df.sort_values(by=["Asset"], inplace=True)
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
        config_var = global_config_map["balance_asset_limit"]
        exchange_limit_conf: Dict[str, Dict[str, str]] = config_var.value

        if not any(list(exchange_limit_conf.values())):
            self._notify("You have not set any limits.")
            self.notify_balance_limit_set()
            return

        self._notify("Balance Limits per exchange...")

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

    async def paper_acccount_balance_df(self, paper_balances: Dict[str, Decimal]):
        rows = []
        for asset, balance in paper_balances.items():
            rows.append({"Asset": asset, "Balance": round(Decimal(str(balance)), 4)})
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
        paper_balances = global_config_map["paper_trade_account_balance"].value
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
