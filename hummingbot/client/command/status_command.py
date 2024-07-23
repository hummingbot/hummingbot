import asyncio
import threading
import time
from collections import OrderedDict, deque
from typing import TYPE_CHECKING, Dict, List

import pandas as pd

from hummingbot import check_dev_mode
from hummingbot.client.command.gateway_command import GatewayCommand
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    get_strategy_config_map,
    missing_required_configs_legacy,
)
from hummingbot.client.config.security import Security
from hummingbot.client.settings import ethereum_wallet_required, required_exchanges
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger.application_warning import ApplicationWarning
from hummingbot.user.user_balances import UserBalances

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


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

    async def strategy_status(self, live: bool = False):
        active_paper_exchanges = [exchange for exchange in self.markets.keys() if exchange.endswith("paper_trade")]

        paper_trade = "\n  Paper Trading Active: All orders are simulated, and no real orders are placed." if len(active_paper_exchanges) > 0 \
            else ""
        if asyncio.iscoroutinefunction(self.strategy.format_status):
            st_status = await self.strategy.format_status()
        else:
            st_status = self.strategy.format_status()
        status = paper_trade + "\n" + st_status
        return status

    def application_warning(self):
        # Application warnings.
        self._expire_old_application_warnings()
        if check_dev_mode() and len(self._app_warnings) > 0:
            app_warning = self._format_application_warnings()
            self.notify(app_warning)
            return app_warning

    async def validate_required_connections(
        self  # type: HummingbotApplication
    ) -> Dict[str, str]:
        invalid_conns = {}
        if not any([str(exchange).endswith("paper_trade") for exchange in required_exchanges]):
            if any([UserBalances.instance().is_gateway_market(exchange) for exchange in required_exchanges]):
                connections = await GatewayCommand.update_exchange(self, self.client_config_map, exchanges=required_exchanges)
            else:
                connections = await UserBalances.instance().update_exchanges(self.client_config_map, exchanges=required_exchanges)
            invalid_conns.update({ex: err_msg for ex, err_msg in connections.items()
                                  if ex in required_exchanges and err_msg is not None})
            if ethereum_wallet_required():
                err_msg = UserBalances.validate_ethereum_wallet()
                if err_msg is not None:
                    invalid_conns["ethereum"] = err_msg
        return invalid_conns

    def missing_configurations_legacy(
        self,  # type: HummingbotApplication
    ) -> List[str]:
        config_map = self.strategy_config_map
        missing_configs = []
        if not isinstance(config_map, ClientConfigAdapter):
            missing_configs = missing_required_configs_legacy(
                get_strategy_config_map(self.strategy_name)
            )
        return missing_configs

    def validate_configs(
        self,  # type: HummingbotApplication
    ) -> List[str]:
        config_map = self.strategy_config_map
        validation_errors = config_map.validate_model() if isinstance(config_map, ClientConfigAdapter) else []
        return validation_errors

    def status(self,  # type: HummingbotApplication
               live: bool = False):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.status, live)
            return

        safe_ensure_future(self.status_check_all(live=live), loop=self.ev_loop)

    async def status_check_all(self,  # type: HummingbotApplication
                               notify_success=True,
                               live=False) -> bool:

        if self.strategy is not None:
            if live:
                await self.stop_live_update()
                self.app.live_updates = True
                while self.app.live_updates and self.strategy:
                    await self.cls_display_delay(
                        await self.strategy_status(live=True) + "\n\n Press escape key to stop update.", 0.1
                    )
                self.app.live_updates = False
                self.notify("Stopped live status display update.")
            else:
                self.notify(await self.strategy_status())
            return True

        # Preliminary checks.
        self.notify("\nPreliminary checks:")
        if self.strategy_name is None or self.strategy_file_name is None:
            self.notify('  - Strategy check: Please import or create a strategy.')
            return False

        if not Security.is_decryption_done():
            self.notify('  - Security check: Encrypted files are being processed. Please wait and try again later.')
            return False

        missing_configs = self.missing_configurations_legacy()
        if missing_configs:
            self.notify("  - Strategy check: Incomplete strategy configuration. The following values are missing.")
            for config in missing_configs:
                self.notify(f"    {config.key}")
        elif notify_success:
            self.notify('  - Strategy check: All required parameters confirmed.')
        validation_errors = self.validate_configs()
        if len(validation_errors) != 0:
            self.notify("  - Strategy check: Validation of the config maps failed. The following errors were flagged.")
            for error in validation_errors:
                self.notify(f"    {error}")
            return False

        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        try:
            invalid_conns = await asyncio.wait_for(self.validate_required_connections(), network_timeout)
        except asyncio.TimeoutError:
            self.notify("\nA network error prevented the connection check to complete. See logs for more details.")
            raise
        if invalid_conns:
            self.notify('  - Exchange check: Invalid connections:')
            for ex, err_msg in invalid_conns.items():
                self.notify(f"    {ex}: {err_msg}")
        elif notify_success:
            self.notify('  - Exchange check: All connections confirmed.')

        if invalid_conns or missing_configs or len(validation_errors) != 0:
            return False

        loading_markets: List[ConnectorBase] = []
        for market in self.markets.values():
            if not market.ready:
                loading_markets.append(market)

        if len(loading_markets) > 0:
            self.notify("  - Connectors check:  Waiting for connectors "
                        f"{','.join([m.name.capitalize() for m in loading_markets])}"
                        " to get ready for trading. \n"
                        "                    Please keep the bot running and try to start again in a few minutes. \n")

            for market in loading_markets:
                market_status_df = pd.DataFrame(data=market.status_dict.items(), columns=["description", "status"])
                self.notify(
                    f"  - {market.display_name.capitalize()} connector status:\n" +
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
                self.notify(f"  - Connector check: {offline_market} is currently offline.")
            return False

        self.notify("  - All checks: Confirmed.")
        return True
