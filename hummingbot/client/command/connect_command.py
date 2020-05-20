from hummingbot.client.config.security import Security
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.user.user_balances import UserBalances
from hummingbot.client.config.config_helpers import save_to_yml
from hummingbot.client.settings import GLOBAL_CONFIG_PATH
import pandas as pd
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

OPTIONS = {
    "binance",
    "coinbase_pro",
    "huobi",
    "liquid",
    "bittrex",
    "kucoin",
    "kraken",
    "ethereum"
}


class ConnectCommand:
    def connect(self,  # type: HummingbotApplication
                option: str):
        if option is None:
            safe_ensure_future(self.show_connections())
        elif option == "ethereum":
            safe_ensure_future(self.connect_ethereum())
        else:
            safe_ensure_future(self.connect_exchange(option))

    async def connect_exchange(self,  # type: HummingbotApplication
                               exchange):
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        exchange_configs = [c for c in global_config_map.values() if exchange in c.key and c.is_connect_key]
        to_connect = True
        if Security.encrypted_file_exists(exchange_configs[0].key):
            await Security.wait_til_decryption_done()
            api_key_config = [c for c in exchange_configs if "api_key" in c.key][0]
            api_key = Security.decrypted_value(api_key_config.key)
            answer = await self.app.prompt(prompt=f"Would you like to replace your existing {exchange} API key "
                                                  f"...{api_key[-4:]} (Yes/No)? >>> ")
            if answer.lower() not in ("yes", "y"):
                to_connect = False
        if to_connect:
            for config in exchange_configs:
                await self.prompt_a_config(config)
                Security.update_secure_config(config.key, config.value)
            api_keys = (await Security.api_keys(exchange)).values()
            err_msg = await UserBalances.instance().add_exchange(exchange, *api_keys)
            if err_msg is None:
                self._notify(f"\nYou are now connected to {exchange}.")
            else:
                self._notify(f"\nError: {err_msg}")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

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
        err_msgs = await UserBalances.instance().update_exchanges(reconnect=True)
        for option in sorted(OPTIONS):
            keys_added = "No"
            keys_confirmed = 'No'
            if option == "ethereum":
                eth_address = global_config_map["ethereum_wallet"].value
                if eth_address is not None and eth_address in Security.private_keys():
                    keys_added = "Yes"
                    err_msg = UserBalances.validate_ethereum_wallet()
                    if err_msg is not None:
                        failed_msgs[option] = err_msg
                    else:
                        keys_confirmed = 'Yes'
            else:
                api_keys = (await Security.api_keys(option)).values()
                if len(api_keys) > 0:
                    keys_added = "Yes"
                    err_msg = err_msgs.get(option)
                    if err_msg is not None:
                        failed_msgs[option] = err_msg
                    else:
                        keys_confirmed = 'Yes'
            data.append([option, keys_added, keys_confirmed])
        return pd.DataFrame(data=data, columns=columns), failed_msgs

    async def connect_ethereum(self,  # type: HummingbotApplication
                               ):
        self.placeholder_mode = True
        self.app.hide_input = True
        ether_wallet = global_config_map["ethereum_wallet"].value
        to_connect = True
        if ether_wallet is not None:
            answer = await self.app.prompt(prompt=f"Would you like to replace your existing Ethereum wallet "
                                                  f"...{ether_wallet[-4:]} (Yes/No)? >>> ")
            if answer.lower() not in ("yes", "y"):
                to_connect = False
        if to_connect:
            private_key = await self.app.prompt(prompt="Enter your wallet private key >>> ", is_password=True)
            public_address = Security.add_private_key(private_key)
            global_config_map["ethereum_wallet"].value = public_address
            await self.prompt_a_config(global_config_map["ethereum_rpc_url"])
            save_to_yml(GLOBAL_CONFIG_PATH, global_config_map)
            err_msg = UserBalances.validate_ethereum_wallet()
            if err_msg is None:
                self._notify(f"Wallet {public_address} connected to hummingbot.")
            else:
                self._notify(f"\nError: {err_msg}")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")
