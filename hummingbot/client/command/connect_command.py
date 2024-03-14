import asyncio
from typing import TYPE_CHECKING, Dict, Optional

import pandas as pd

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.security import Security
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.user.user_balances import UserBalances

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401

OPTIONS = {cs.name for cs in AllConnectorSettings.get_connector_settings().values()
           if not cs.use_ethereum_wallet and not cs.uses_gateway_generic_connector() if cs.name != "probit_kr"}


class ConnectCommand:
    def connect(self,  # type: HummingbotApplication
                option: str):
        if option is None:
            safe_ensure_future(self.show_connections())
        else:
            safe_ensure_future(self.connect_exchange(option))

    async def connect_exchange(self,  # type: HummingbotApplication
                               connector_name):
        # instruct users to use gateway connect if connector is a gateway connector
        if AllConnectorSettings.get_connector_settings()[connector_name].uses_gateway_generic_connector():
            self.notify("This is a gateway connector. Use `gateway connect` command instead.")
            return

        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        if connector_name == "kraken":
            self.notify("Reminder: Please ensure your Kraken API Key Nonce Window is at least 10.")
        connector_config = ClientConfigAdapter(AllConnectorSettings.get_connector_config_keys(connector_name))
        if Security.connector_config_file_exists(connector_name):
            await Security.wait_til_decryption_done()
            api_key_config = [
                c.printable_value for c in connector_config.traverse(secure=False) if "api_key" in c.attr
            ]
            if api_key_config:
                api_key = api_key_config[0]
                prompt = (
                    f"Would you like to replace your existing {connector_name} API key {api_key} (Yes/No)? >>> "
                )
            else:
                prompt = f"Would you like to replace your existing {connector_name} key (Yes/No)? >>> "
            answer = await self.app.prompt(prompt=prompt)
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
            if answer.lower() in ("yes", "y"):
                previous_keys = Security.api_keys(connector_name)
                await self._perform_connect(connector_config, previous_keys)
        else:
            await self._perform_connect(connector_config)
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

    async def show_connections(self  # type: HummingbotApplication
                               ):
        self.notify("\nTesting connections, please wait...")
        df, failed_msgs = await self.connection_df()
        lines = ["    " + line for line in format_df_for_printout(
            df,
            table_format=self.client_config_map.tables_format).split("\n")]
        if failed_msgs:
            lines.append("\nFailed connections:")
            lines.extend(["    " + k + ": " + v for k, v in failed_msgs.items()])
        self.notify("\n".join(lines))

    async def connection_df(self  # type: HummingbotApplication
                            ):
        await Security.wait_til_decryption_done()
        columns = ["Exchange", "  Keys Added", "  Keys Confirmed"]
        data = []
        failed_msgs = {}
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        try:
            err_msgs = await asyncio.wait_for(
                UserBalances.instance().update_exchanges(self.client_config_map, reconnect=True), network_timeout
            )
        except asyncio.TimeoutError:
            self.notify("\nA network error prevented the connection table to populate. See logs for more details.")
            raise
        for option in sorted(OPTIONS):
            keys_added = "No"
            keys_confirmed = "No"
            api_keys = (
                Security.api_keys(option).values()
                if not UserBalances.instance().is_gateway_market(option)
                else {}
            )
            if len(api_keys) > 0:
                keys_added = "Yes"
                err_msg = err_msgs.get(option)
                if err_msg is not None:
                    failed_msgs[option] = err_msg
                else:
                    keys_confirmed = "Yes"
            data.append([option, keys_added, keys_confirmed])
        return pd.DataFrame(data=data, columns=columns), failed_msgs

    async def validate_n_connect_connector(
        self,  # type: HummingbotApplication
        connector_name: str,
    ) -> Optional[str]:
        await Security.wait_til_decryption_done()
        api_keys = Security.api_keys(connector_name)
        network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
        try:
            err_msg = await asyncio.wait_for(
                UserBalances.instance().add_exchange(connector_name, self.client_config_map, **api_keys),
                network_timeout,
            )
        except asyncio.TimeoutError:
            self.notify(
                "\nA network error prevented the connection to complete. See logs for more details.")
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")
            raise
        return err_msg

    async def _perform_connect(self, connector_config: ClientConfigAdapter, previous_keys: Optional[Dict] = None):
        connector_name = connector_config.connector
        original_config = connector_config.full_copy()
        await self.prompt_for_model_config(connector_config)
        self.app.change_prompt(prompt=">>> ")
        if self.app.to_stop_config:
            self.app.to_stop_config = False
            return
        Security.update_secure_config(connector_config)
        err_msg = await self.validate_n_connect_connector(connector_name)
        if err_msg is None:
            self.notify(f"\nYou are now connected to {connector_name}.")
            safe_ensure_future(TradingPairFetcher.get_instance(client_config_map=ClientConfigAdapter).fetch_all(client_config_map=ClientConfigAdapter))
        else:
            self.notify(f"\nError: {err_msg}")
            if previous_keys is not None:
                Security.update_secure_config(original_config)
