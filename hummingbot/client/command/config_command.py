import asyncio
import logging
from six import string_types
from typing import (
    List,
    Dict,
    Optional,
    Any,
)

from hummingbot.core.utils.wallet_setup import (
    create_and_save_wallet,
    import_and_save_wallet,
    list_wallets,
    unlock_wallet
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.in_memory_config_map import in_memory_config_map
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_helpers import (
    get_strategy_config_map,
    write_config_to_yml,
    load_required_configs,
    parse_cvar_value,
    copy_strategy_template,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ConfigCommand:
    def config(self,  # type: HummingbotApplication
               key: str = None,
               key_list: Optional[List[str]] = None):
        self.app.clear_input()

        if self.strategy or (self.config_complete and key is None):
            asyncio.ensure_future(self.reset_config_loop(key))
            return
        if key is not None and key not in load_required_configs().keys():
            self._notify("Invalid config variable %s" % (key,))
            return
        if key is not None:
            keys = [key]
        elif key_list is not None:
            keys = key_list
        else:
            keys = self._get_empty_configs()
        asyncio.ensure_future(self._config_loop(keys), loop=self.ev_loop)

    @property
    def config_complete(self,  # type: HummingbotApplication
                        ):
        config_map = load_required_configs()
        for key in self._get_empty_configs():
            cvar = config_map.get(key)
            if cvar.value is None and cvar.required:
                return False
        return True

    @staticmethod
    def _get_empty_configs() -> List[str]:
        config_map = load_required_configs()
        return [key for key, config in config_map.items() if config.value is None]

    async def reset_config_loop(self,  # type: HummingbotApplication
                                key: str = None):
        strategy = in_memory_config_map.get("strategy").value

        self.placeholder_mode = True
        self.app.toggle_hide_input()

        if self.strategy:
            choice = await self.app.prompt(prompt=f"Would you like to stop running the {strategy} strategy "
                                                  f"and reconfigure the bot? (y/n) >>> ")
        else:
            choice = await self.app.prompt(prompt=f"Would you like to reconfigure the bot? (y/n) >>> ")

        self.app.change_prompt(prompt=">>> ")
        self.app.toggle_hide_input()
        self.placeholder_mode = False

        if choice.lower() in {"y", "yes"}:
            if self.strategy:
                await self.stop_loop()
            if key is None:
                in_memory_config_map.get("strategy").value = None
                in_memory_config_map.get("strategy_file_path").value = None
            self.config(key)
        else:
            self._notify("Aborted.")

    async def _create_or_import_wallet(self,  # type: HummingbotApplication
                                       ):
        choice = await self.app.prompt(prompt=global_config_map.get("wallet").prompt)
        if choice == "import":
            private_key = await self.app.prompt(prompt="Your wallet private key >>> ", is_password=True)
            password = await self.app.prompt(prompt="A password to protect your wallet key >>> ", is_password=True)

            try:
                self.acct = import_and_save_wallet(password, private_key)
                self._notify("Wallet %s imported into hummingbot" % (self.acct.address,))
            except Exception as e:
                self._notify(f"Failed to import wallet key: {e}")
                result = await self._create_or_import_wallet()
                return result
        elif choice == "create":
            password = await self.app.prompt(prompt="A password to protect your wallet key >>> ", is_password=True)
            self.acct = create_and_save_wallet(password)
            self._notify("New wallet %s created" % (self.acct.address,))
        else:
            self._notify('Invalid choice. Please enter "create" or "import".')
            result = await self._create_or_import_wallet()
            return result
        return self.acct.address

    async def _unlock_wallet(self,  # type: HummingbotApplication
                             ):
        choice = await self.app.prompt(prompt="Would you like to unlock your previously saved wallet? (y/n) >>> ")
        if choice.lower() in {"y", "yes"}:
            wallets = list_wallets()
            self._notify("Existing wallets:")
            self.list(obj="wallets")
            if len(wallets) == 1:
                public_key = wallets[0]
            else:
                public_key = await self.app.prompt(prompt="Which wallet would you like to import ? >>> ")
            password = await self.app.prompt(prompt="Enter your password >>> ", is_password=True)
            try:
                acct = unlock_wallet(public_key=public_key, password=password)
                self._notify("Wallet %s unlocked" % (acct.address,))
                self.acct = acct
                return self.acct.address
            except Exception as e:
                self._notify("Cannot unlock wallet. Please try again.")
                result = await self._unlock_wallet()
                return result
        else:
            value = await self._create_or_import_wallet()
            return value

    async def _import_or_create_strategy_config(self,  # type: HummingbotApplication
                                                ):
        current_strategy: str = in_memory_config_map.get("strategy").value
        strategy_file_path_cv: ConfigVar = in_memory_config_map.get("strategy_file_path")
        choice = await self.app.prompt(prompt="Import previous configs or create a new config file? "
                                              "(import/create) >>> ")
        if choice == "import":
            strategy_path = await self.app.prompt(strategy_file_path_cv.prompt)
            strategy_path = strategy_path
            self._notify(f"Loading previously saved config file from {strategy_path}...")
        elif choice == "create":
            strategy_path = await copy_strategy_template(current_strategy)
            self._notify(f"new config file at {strategy_path} created.")
        else:
            self._notify('Invalid choice. Please enter "create" or "import".')
            strategy_path = await self._import_or_create_strategy_config()

        # Validate response
        if not strategy_file_path_cv.validate(strategy_path):
            self._notify(f"Invalid path {strategy_path}. Please enter \"create\" or \"import\".")
            strategy_path = await self._import_or_create_strategy_config()
        return strategy_path

    async def config_single_variable(self,  # type: HummingbotApplication
                                     cvar: ConfigVar,
                                     is_single_key: bool = False) -> Any:
        if cvar.required or is_single_key:
            if cvar.key == "strategy_file_path":
                val = await self._import_or_create_strategy_config()
            elif cvar.key == "wallet":
                wallets = list_wallets()
                if len(wallets) > 0:
                    val = await self._unlock_wallet()
                else:
                    val = await self._create_or_import_wallet()
                logging.getLogger("hummingbot.public_eth_address").info(val)
            else:
                val = await self.app.prompt(prompt=cvar.prompt, is_password=cvar.is_secure)
            if not cvar.validate(val):
                self._notify("%s is not a valid %s value" % (val, cvar.key))
                val = await self.config_single_variable(cvar)
        else:
            val = cvar.value
        if val is None or (isinstance(val, string_types) and len(val) == 0):
            val = cvar.default
        return val

    async def _config_loop(self,  # type: HummingbotApplication
                           keys: List[str] = []):
        self._notify("Please follow the prompt to complete configurations: ")
        self.placeholder_mode = True
        self.app.toggle_hide_input()

        single_key = len(keys) == 1

        async def inner_loop(_keys: List[str]):
            for key in _keys:
                current_strategy: str = in_memory_config_map.get("strategy").value
                strategy_cm: Dict[str, ConfigVar] = get_strategy_config_map(current_strategy)
                if key in in_memory_config_map:
                    cv: ConfigVar = in_memory_config_map.get(key)
                elif key in global_config_map:
                    cv: ConfigVar = global_config_map.get(key)
                else:
                    cv: ConfigVar = strategy_cm.get(key)

                value = await self.config_single_variable(cv, is_single_key=single_key)
                cv.value = parse_cvar_value(cv, value)
                if single_key:
                    self._notify(f"\nNew config saved:\n{key}: {str(value)}")
            if not self.config_complete:
                await inner_loop(self._get_empty_configs())
        try:
            await inner_loop(keys)
            await write_config_to_yml()
            if not single_key:
                self._notify("\nConfig process complete. Enter \"start\" to start market making.")
                self.app.set_text("start")
        except asyncio.TimeoutError:
            self.logger().error("Prompt timeout")
        except Exception as err:
            self.logger().error("Unknown error while writing config. %s" % (err,), exc_info=True)
        finally:
            self.app.toggle_hide_input()
            self.placeholder_mode = False
            self.app.change_prompt(prompt=">>> ")
