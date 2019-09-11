import pandas as pd
import time
from collections import (
    deque,
    OrderedDict
)
from typing import List

from hummingbot import check_dev_mode
from hummingbot.logger.application_warning import ApplicationWarning
from hummingbot.market.market_base import MarketBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.ethereum import check_web3

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class StatusCommand:
    def _expire_old_application_warnings(self,  # type: HummingbotApplication
                                         ):
        now: float = time.time()
        expiry_threshold: float = now - self.APP_WARNING_EXPIRY_DURATION
        while len(self._app_warnings) > 0 and self._app_warnings[0].timestamp < expiry_threshold:
            self._app_warnings.popleft()

    def _format_application_warnings(self,  # type: HummingbotApplication
                                     ) -> str:
        lines: List[str] = []
        if len(self._app_warnings) < 1:
            return ""

        lines.append("\n  Warnings:")

        if len(self._app_warnings) < self.APP_WARNING_STATUS_LIMIT:
            for app_warning in reversed(self._app_warnings):
                lines.append(f"    * {pd.Timestamp(app_warning.timestamp, unit='s')} - "
                             f"({app_warning.logger_name}) - {app_warning.warning_msg}")
        else:
            module_based_warnings: OrderedDict = OrderedDict()
            for app_warning in reversed(self._app_warnings):
                logger_name: str = app_warning.logger_name
                if logger_name not in module_based_warnings:
                    module_based_warnings[logger_name] = deque([app_warning])
                else:
                    module_based_warnings[logger_name].append(app_warning)

            warning_lines: List[str] = []
            while len(warning_lines) < self.APP_WARNING_STATUS_LIMIT:
                logger_keys: List[str] = list(module_based_warnings.keys())
                for key in logger_keys:
                    warning_item: ApplicationWarning = module_based_warnings[key].popleft()
                    if len(module_based_warnings[key]) < 1:
                        del module_based_warnings[key]
                    warning_lines.append(f"    * {pd.Timestamp(warning_item.timestamp, unit='s')} - "
                                         f"({key}) - {warning_item.warning_msg}")
            lines.extend(warning_lines[:self.APP_WARNING_STATUS_LIMIT])

        return "\n".join(lines)

    def status(self,  # type: HummingbotApplication
               ) -> bool:
        # Preliminary checks.
        self._notify("\n  Preliminary checks:")
        if self.config_complete:
            self._notify("   - Config check: Config complete")
        else:
            self._notify('   x Config check: Pending config. Please enter "config" before starting the bot.')
            return False

        if self.wallet is not None:
            # Only check node url when a wallet has been initialized
            eth_node_valid = check_web3(global_config_map.get("ethereum_rpc_url").value)
            if eth_node_valid:
                self._notify("   - Node check: Ethereum node running and current")
            else:
                self._notify('   x Node check: Bad ethereum rpc url. Your node may be syncing. '
                             'Please re-configure by entering "config ethereum_rpc_url"')
                return False

            if self.wallet.network_status is NetworkStatus.CONNECTED:
                if self._trading_required:
                    has_minimum_eth = self.wallet.get_balance("ETH") > 0.01
                    if has_minimum_eth:
                        self._notify("   - ETH wallet check: Minimum ETH requirement satisfied")
                    else:
                        self._notify("   x ETH wallet check: Not enough ETH in wallet. "
                                     "A small amount of Ether is required for sending transactions on "
                                     "Decentralized Exchanges")
            else:
                self._notify("   x ETH wallet check: ETH wallet is not connected.")

        loading_markets: List[MarketBase] = []
        for market in self.markets.values():
            if not market.ready:
                loading_markets.append(market)

        if len(loading_markets) > 0:
            self._notify(f"   x Market check:  Waiting for markets " +
                         ",".join([m.name.capitalize() for m in loading_markets]) + f" to get ready for trading. \n"
                         f"                    Please keep the bot running and try to start again in a few minutes. \n")

            for market in loading_markets:
                market_status_df = pd.DataFrame(data=market.status_dict.items(), columns=["description", "status"])
                self._notify(
                    f"   x {market.display_name.capitalize()} market status:\n" +
                    "\n".join(["     " + line for line in market_status_df.to_string(index=False,).split("\n")]) +
                    "\n"
                )
            return False

        elif not all([market.network_status is NetworkStatus.CONNECTED for market in self.markets.values()]):
            offline_markets: List[str] = [
                market_name
                for market_name, market
                in self.markets.items()
                if market.network_status is not NetworkStatus.CONNECTED
            ]
            for offline_market in offline_markets:
                self._notify(f"   x Market check:  {offline_market} is currently offline.")

        # See if we can print out the strategy status.
        self._notify("   - Market check: All markets ready")
        if self.strategy is None:
            self._notify("   x initializing strategy.")
        else:
            self._notify(self.strategy.format_status() + "\n")

        # Application warnings.
        self._expire_old_application_warnings()
        if check_dev_mode() and len(self._app_warnings) > 0:
            self._notify(self._format_application_warnings())

        return True
