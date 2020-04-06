from decimal import Decimal
from hummingbot.client.settings import EXCHANGES
from hummingbot.client.config.security import Security
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_helpers import parse_cvar_value
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.user.user_balances import UserBalances
import pandas as pd
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


def parse_config_default_to_text(config: ConfigVar) -> str:
    """
    :param config: ConfigVar object
    :return: text for default value prompt
    """
    if config.default is None:
        default = ""
    elif callable(config.default):
        default = config.default()
    elif config.type == 'bool' and isinstance(config.prompt, str) and "Yes/No" in config.prompt:
        default = "Yes" if config.default else "No"
    else:
        default = str(config.default)
    if isinstance(default, Decimal):
        default = "{0:.4f}".format(default)
    return default


class ConnectCommand:
    def connect(self,  # type: HummingbotApplication
                exchange: str):
        if exchange is None:
            safe_ensure_future(self.show_connections())
        else:
            safe_ensure_future(self.prompt_api_keys(exchange))

    async def prompt_api_keys(self,  # type: HummingbotApplication
                              exchange):
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.toggle_hide_input()
        exchange_configs = [c for c in global_config_map.values() if exchange in c.key]
        for config in exchange_configs:
            await self.prompt_a_config(config)
            Security.update_secure_config(config.key, config.value)
        api_keys = (await Security.api_keys(exchange)).values()
        err_msg = await UserBalances.instance().add_exchange(exchange, *api_keys)
        if err_msg is None:
            self._notify(f"\nYou are now connected to {exchange}")
        else:
            self._notify(f"\nError: {err_msg}")
        self.placeholder_mode = False
        self.app.toggle_hide_input()
        self.app.change_prompt(prompt=">>> ")

    async def show_connections(self  # type: HummingbotApplication
                               ):
        self._notify("\nTesting connections, please wait...")
        await Security.wait_til_decryption_done()
        df, failed_msgs = await self.connection_df()
        lines = ["    " + l for l in df.to_string(index=False).split("\n")]
        if failed_msgs:
            lines.append("Failed connections:")
            lines.extend([f"    " + k + ": " + v for k, v in failed_msgs.items()])
        self._notify("\n".join(lines))

    async def connection_df(self  # type: HummingbotApplication
                            ):
        columns = ["Exchange", "Keys Saved", "Connected"]
        data = []
        failed_msgs = {}
        for exchange in sorted(EXCHANGES):
            api_keys = (await Security.api_keys(exchange)).values()
            keys_saved = "No"
            connected = 'No'
            if len(api_keys) > 0:
                keys_saved = "Yes"
                err_msg = await UserBalances.instance().add_exchange(exchange, *api_keys)
                if err_msg is not None:
                    failed_msgs[exchange] = err_msg
                else:
                    connected = 'Yes'
            data.append([exchange, keys_saved, connected])
        return pd.DataFrame(data=data, columns=columns), failed_msgs

    async def prompt_a_config(self,  # type: HummingbotApplication
                              config: ConfigVar):
        self.app.set_text(parse_config_default_to_text(config))
        input = await self.app.prompt(prompt=config.prompt, is_password=config.is_secure)
        valid = config.validate(input)
        # ToDo: this should be from the above validate function.
        msg = "Invalid input."
        if not valid:
            self._notify(msg)
            await self.prompt_a_config(config)
        else:
            config.value = parse_cvar_value(config, input)
