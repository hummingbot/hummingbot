from hummingbot.client.config.security import Security
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.user.user_balances import UserBalances
import pandas as pd
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

EXCHANGES = {
    "binance",
    "coinbase_pro",
    "huobi",
    "liquid",
    "bittrex",
    "kucoin",
    "kraken"
}


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
        self.placeholder_mode = False
        self.app.toggle_hide_input()
        self.app.change_prompt(prompt=">>> ")
        err_msg = await UserBalances.instance().add_exchange(exchange, *api_keys)
        if err_msg is None:
            self._notify(f"\nYou are now connected to {exchange}.")
        else:
            self._notify(f"\nError: {err_msg}")

    async def show_connections(self  # type: HummingbotApplication
                               ):
        self._notify("\nTesting connections, please wait...")
        await Security.wait_til_decryption_done()
        df, failed_msgs = await self.connection_df()
        lines = ["    " + l for l in df.to_string(index=False).split("\n")]
        if failed_msgs:
            lines.append("\nFailed connections:")
            lines.extend([f"    " + k + ": " + v for k, v in failed_msgs.items()])
        self._notify("\n".join(lines))

    async def connection_df(self  # type: HummingbotApplication
                            ):
        columns = ["Exchange", "  Keys Added", "  Keys Confirmed"]
        data = []
        failed_msgs = {}
        err_msgs = await UserBalances.instance().update_all(reconnect=True)
        for exchange in sorted(EXCHANGES):
            api_keys = (await Security.api_keys(exchange)).values()
            keys_added = "No"
            keys_confirmed = 'No'
            if len(api_keys) > 0:
                keys_added = "Yes"
                err_msg = err_msgs.get(exchange)
                if err_msg is not None:
                    failed_msgs[exchange] = err_msg
                else:
                    keys_confirmed = 'Yes'
            data.append([exchange, keys_added, keys_confirmed])
        return pd.DataFrame(data=data, columns=columns), failed_msgs
