import asyncio
import threading
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List

import pandas as pd

from hummingbot.client.config.config_validators import validate_decimal, validate_exchange
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.user.user_balances import UserBalances

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401

OPTIONS = [
    "limit",
    "paper"
]


class BalanceCommand:
    def balance(self,  # type: HummingbotApplication
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
            if option == "limit":
                balance_asset_limit = self.client_config_map.balance_asset_limit
                if args is None or len(args) == 0:
                    safe_ensure_future(self.show_asset_limits())
                    return
                if len(args) != 3 or validate_exchange(args[0]) is not None or validate_decimal(args[2]) is not None:
                    self.notify("Error: Invalid command arguments")
                    self.notify_balance_limit_set()
                    return
                exchange = args[0]
                asset = args[1].upper()
                amount = float(args[2])
                if balance_asset_limit.get(exchange) is None:
                    balance_asset_limit[exchange] = {}
                if amount < 0 and asset in balance_asset_limit[exchange].keys():
                    balance_asset_limit[exchange].pop(asset)
                    self.notify(f"Limit for {asset} on {exchange} exchange removed.")
                elif amount >= 0:
                    balance_asset_limit[exchange][asset] = amount
                    self.notify(f"Limit for {asset} on {exchange} exchange set to {amount}")
                self.save_client_config()

            elif option == "paper":
                paper_balances = self.client_config_map.paper_trade.paper_trade_account_balance
                if args is None or len(args) == 0:
                    safe_ensure_future(self.show_paper_account_balance())
                    return
                if len(args) != 2 or validate_decimal(args[1]) is not None:
                    self.notify("Error: Invalid command arguments")
                    self.notify_balance_paper_set()
                    return
                asset = args[0].upper()
                amount = float(args[1])
                paper_balances[asset] = amount
                self.notify(f"Paper balance for {asset} token set to {amount}")
                self.save_client_config()

    async def show_balances(
        self  # type: HummingbotApplication
    ):
        global_token_symbol = self.client_config_map.global_token.global_token_symbol
        total_col_name = f"Total ({global_token_symbol})"
        sum_not_for_show_name = "sum_not_for_show"
        self.notify("Updating balances, please wait...")
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        try:
            all_ex_bals = await asyncio.wait_for(
                UserBalances.instance().all_balances_all_exchanges(self.client_config_map), network_timeout
            )
        except asyncio.TimeoutError:
            self.notify("\nA network error prevented the balances to update. See logs for more details.")
            raise
        all_ex_avai_bals = UserBalances.instance().all_available_balances_all_exchanges()

        exchanges_total = 0

        for exchange, bals in all_ex_bals.items():
            self.notify(f"\n{exchange}:")
            df, allocated_total = await self.exchange_balances_extra_df(exchange, bals, all_ex_avai_bals.get(exchange, {}))
            if df.empty:
                self.notify("You have no balance on this exchange.")
            else:
                lines = [
                    "    " + line for line in df.drop(sum_not_for_show_name, axis=1).to_string(index=False).split("\n")
                ]
                self.notify("\n".join(lines))
                self.notify(f"\n  Total: {global_token_symbol} "
                            f"{PerformanceMetrics.smart_round(df[total_col_name].sum())}")
                allocated_percentage = 0
                if df[sum_not_for_show_name].sum() != Decimal("0"):
                    allocated_percentage = allocated_total / df[sum_not_for_show_name].sum()
                self.notify(f"Allocated: {allocated_percentage:.2%}")
                exchanges_total += df[total_col_name].sum()

        self.notify(f"\n\nExchanges Total: {global_token_symbol} {exchanges_total:.0f}    ")

    async def exchange_balances_extra_df(self,  # type: HummingbotApplication
                                         exchange: str,
                                         ex_balances: Dict[str, Decimal],
                                         ex_avai_balances: Dict[str, Decimal]):
        conn_setting = AllConnectorSettings.get_connector_settings()[exchange]
        global_token_symbol = self.client_config_map.global_token.global_token_symbol
        total_col_name = f"Total ({global_token_symbol})"
        allocated_total = Decimal("0")
        rows = []
        for token, bal in ex_balances.items():
            avai = Decimal(ex_avai_balances.get(token.upper(), 0)) if ex_avai_balances is not None else Decimal(0)
            # show zero balances if it is a gateway connector (the user manually
            # chose to show those values with 'gateway connector-tokens')
            if conn_setting.uses_gateway_generic_connector():
                if bal == Decimal(0):
                    allocated = "0%"
                else:
                    allocated = f"{(bal - avai) / bal:.0%}"
            else:
                # the exchange is CEX. Only show balance if non-zero.
                if bal == Decimal(0):
                    continue
                allocated = f"{(bal - avai) / bal:.0%}"

            rate = await RateOracle.get_instance().get_rate(base_token=token)
            rate = Decimal("0") if rate is None else rate
            global_value = rate * bal
            allocated_total += rate * (bal - avai)
            rows.append({"Asset": token.upper(),
                         "Total": round(bal, 4),
                         total_col_name: PerformanceMetrics.smart_round(global_value),
                         "sum_not_for_show": global_value,
                         "Allocated": allocated,
                         })
        df = pd.DataFrame(data=rows, columns=["Asset", "Total", total_col_name, "sum_not_for_show", "Allocated"])
        df.sort_values(by=["Asset"], inplace=True)
        return df, allocated_total

    async def asset_limits_df(self,
                              asset_limit_conf: Dict[str, str]):
        rows = []
        for token, amount in asset_limit_conf.items():
            rows.append({"Asset": token, "Limit": round(Decimal(amount), 4)})

        df = pd.DataFrame(data=rows, columns=["Asset", "Limit"])
        df.sort_values(by=["Asset"], inplace=True)
        return df

    async def show_asset_limits(
        self  # type: HummingbotApplication
    ):
        exchange_limit_conf = self.client_config_map.balance_asset_limit

        if not any(list(exchange_limit_conf.values())):
            self.notify("You have not set any limits.")
            self.notify_balance_limit_set()
            return

        self.notify("Balance Limits per exchange...")

        for exchange, asset_limit_config in exchange_limit_conf.items():
            if asset_limit_config is None:
                continue

            self.notify(f"\n{exchange}")
            df = await self.asset_limits_df(asset_limit_config)
            if df.empty:
                self.notify("You have no limits on this exchange.")
            else:
                lines = ["    " + line for line in df.to_string(index=False).split("\n")]
                self.notify("\n".join(lines))
        self.notify("\n")
        return

    async def paper_acccount_balance_df(self, paper_balances: Dict[str, Decimal]):
        rows = []
        for asset, balance in paper_balances.items():
            rows.append({"Asset": asset, "Balance": round(Decimal(str(balance)), 4)})
        df = pd.DataFrame(data=rows, columns=["Asset", "Balance"])
        df.sort_values(by=["Asset"], inplace=True)
        return df

    def notify_balance_limit_set(self):
        self.notify("To set a balance limit (how much the bot can use): \n"
                    "    balance limit [EXCHANGE] [ASSET] [AMOUNT]\n"
                    "e.g. balance limit binance BTC 0.1")

    def notify_balance_paper_set(self):
        self.notify("To set a paper account balance: \n"
                    "    balance paper [ASSET] [AMOUNT]\n"
                    "e.g. balance paper BTC 0.1")

    async def show_paper_account_balance(
        self  # type: HummingbotApplication
    ):
        paper_balances = self.client_config_map.paper_trade.paper_trade_account_balance
        if not paper_balances:
            self.notify("You have not set any paper account balance.")
            self.notify_balance_paper_set()
            return
        self.notify("Paper account balances:")
        df = await self.paper_acccount_balance_df(paper_balances)
        lines = ["    " + line for line in df.to_string(index=False).split("\n")]
        self.notify("\n".join(lines))
        self.notify("\n")
        return
