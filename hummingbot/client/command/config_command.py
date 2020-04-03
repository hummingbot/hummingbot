import asyncio
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
    unlock_wallet,
    save_wallet
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
    parse_cvar_default_value_prompt
)
from hummingbot.client.config.security import Security
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.pure_market_making import (
    PureMarketMakingStrategyV2
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


no_restart_pmm_keys = ["bid_place_threshold", "ask_place_threshold"]


class ConfigCommand:
    def config(self,  # type: HummingbotApplication
               key: str = None,
               key_list: Optional[List[str]] = None):
        """
        Router function that for all commands related to bot configuration
        """
        self.app.clear_input()
        if (key is None and (self.strategy or self.config_complete)) or \
                (isinstance(self.strategy, PureMarketMakingStrategyV2) and key not in no_restart_pmm_keys):
            safe_ensure_future(self.reset_config_loop(key))
            return

        if key is not None:
            try:
                self._get_config_var_with_key(key)
                safe_ensure_future(self._config_single_key(key), loop=self.ev_loop)
            except ValueError as e:
                self.logger().error(e)
                self._notify("Invalid config variable %s" % (key,))

        elif key_list is not None:
            keys = key_list
            safe_ensure_future(self._config_loop(keys), loop=self.ev_loop)
        else:
            keys = self._get_empty_configs()
            safe_ensure_future(self._config_loop(keys), loop=self.ev_loop)

    @property
    def config_complete(self,  # type: HummingbotApplication
                        ) -> bool:
        """
        Returns bool value that indicates if the bot's configuration is all complete.
        """
        if not Security.is_decryption_done():
            return False
        config_map = load_required_configs()
        keys = self._get_empty_configs()
        for key in keys:
            cvar = config_map.get(key)
            if cvar.value is None and cvar.required:
                if cvar.is_secure and cvar.key != "wallet":
                    cvar.value = Security.decrypted_value(cvar.key)
                    continue
                return False
        return True

    @staticmethod
    def _get_empty_configs() -> List[str]:
        """
        Returns a list of required config keys whose current value is None or an empty string.
        """
        config_map = load_required_configs()
        return [key for key, config in config_map.items() if config.value is None]

    @staticmethod
    def get_all_available_config_keys() -> List[str]:
        """
        Returns a list of config keys that are currently relevant, including the ones that are not required.
        """
        all_available_config_keys = list(in_memory_config_map.keys()) + list(global_config_map.keys())
        current_strategy: str = global_config_map.get("strategy").value
        strategy_cm: Optional[Dict[str, ConfigVar]] = get_strategy_config_map(current_strategy)
        if strategy_cm:
            all_available_config_keys += list(strategy_cm.keys())
        return all_available_config_keys

    async def reset_config_loop(self,  # type: HummingbotApplication
                                key: str = None):
        """
        Handler function that allows user to redo the config step.
        """
        strategy = global_config_map.get("strategy").value
        strategy_cm = get_strategy_config_map(strategy)

        self.placeholder_mode = True
        self.app.toggle_hide_input()

        if self.strategy:
            choice = await self.app.prompt(prompt=f"Would you like to stop running the {strategy} strategy "
                                                  f"and reconfigure the bot? (Yes/No) >>> ")
        else:
            choice = await self.app.prompt(prompt=f"Would you like to reconfigure the bot? (Yes/No) >>> ")

        self.app.change_prompt(prompt=">>> ")
        self.app.toggle_hide_input()
        self.placeholder_mode = False

        if choice.lower() in {"y", "yes"}:
            # Clear application states that are specific to config
            self.starting_balances = {}

            if self.strategy:
                await self.stop_loop()
            if key is None:
                # Clear original strategy config map
                if strategy_cm:
                    for k in strategy_cm:
                        strategy_cm[k].value = None
                global_config_map.get("strategy").value = None
                in_memory_config_map.get("strategy_file_path").value = None
                self.clear_application_warning()
            self.config(key)
        else:
            self._notify("Aborted.")

    async def _create_or_import_wallet(self,  # type: HummingbotApplication
                                       ):
        """
        Special handler function that asks the user to either create a new wallet,
        or import one by entering the private key.
        """
        choice = await self.app.prompt(prompt=global_config_map.get("wallet").prompt)
        if choice == "import":
            private_key = await self.app.prompt(prompt="Your wallet private key >>> ", is_password=True)
            try:
                self.acct = import_and_save_wallet(Security.password, private_key)
                self._notify("Wallet %s imported into hummingbot" % (self.acct.address,))
            except Exception as e:
                self._notify(f"Failed to import wallet key: {e}")
                result = await self._create_or_import_wallet()
                return result
        elif choice == "create":
            self.acct = create_and_save_wallet(Security.password)
            self._notify("New wallet %s created" % (self.acct.address,))
        else:
            self._notify('Invalid choice. Please enter "create" or "import".')
            result = await self._create_or_import_wallet()
            return result
        return self.acct.address

    async def _unlock_wallet(self,  # type: HummingbotApplication
                             ):
        """
        Special handler function that helps the user unlock an existing wallet, or redirect user to create a new wallet.
        """
        choice = await self.app.prompt(prompt="Would you like to unlock your previously saved wallet? (Yes/No) >>> ")
        if choice.lower() in {"y", "yes"}:
            wallets = list_wallets()
            self._notify("Existing wallets:")
            self.list(obj="wallets")
            if len(wallets) == 1:
                public_key = wallets[0]
            else:
                public_key = await self.app.prompt(prompt="Which wallet would you like to import ? >>> ")
            try:
                acct = unlock_wallet(public_key=public_key, password=Security.password)
                self._notify("Wallet %s unlocked" % (acct.address,))
                self.acct = acct
                return self.acct.address
            except ValueError as err:
                if str(err) != "MAC mismatch":
                    raise err
                self._notify("The wallet was locked by a different password.")
                old_password = await self.app.prompt(prompt="Please enter the password >>> ", is_password=True)
                try:
                    acct = unlock_wallet(public_key=public_key, password=old_password)
                    self._notify("Wallet %s unlocked" % (acct.address,))
                    save_wallet(acct, Security.password)
                    self._notify(f"Wallet {acct.address} is now saved with your main password.")
                    self.acct = acct
                    return self.acct.address
                except ValueError as err:
                    if str(err) != "MAC mismatch":
                        raise err
                    self._notify("Cannot unlock wallet. Please try again.")
                    return await self._unlock_wallet()
        else:
            value = await self._create_or_import_wallet()
            return value

    async def _import_or_create_strategy_config(self,  # type: HummingbotApplication
                                                ):
        """
        Special handler function that asks if the user wants to import or create a new strategy config.
        """
        current_strategy: str = global_config_map.get("strategy").value
        # A quick fix here, this is because global_config_map gets assigned values later on
        # when there is no conf_global.yml
        if current_strategy is None:
            current_strategy = global_config_map.get("strategy").default
        strategy_file_path_cv: ConfigVar = in_memory_config_map.get("strategy_file_path")
        choice = await self.app.prompt(prompt="Import previous configs or create a new config file? "
                                              "(import/create) >>> ")
        if choice == "import":
            strategy_path = await self.app.prompt(strategy_file_path_cv.prompt)
            strategy_path = strategy_path
            self._notify(f"Loading previously saved config file from {strategy_path}...")
        elif choice == "create":
            strategy_path = await copy_strategy_template(current_strategy)
            self._notify(f"A new config file {strategy_path} created.")
            self._notify(f"Please see https://docs.hummingbot.io/strategies/{current_strategy.replace('_', '-')}/ "
                         f"while setting up these below configuration.")
        else:
            self._notify('Invalid choice. Please enter "create" or "import".')
            strategy_path = await self._import_or_create_strategy_config()
        return strategy_path

    async def check_password(self,  # type: HummingbotApplication
                             ):
        password = await self.app.prompt(prompt="Enter your password >>> ", is_password=True)
        if password != Security.password:
            self._notify("Invalid password, please try again.")
            return False
        else:
            return True

    async def prompt_single_variable(self,  # type: HummingbotApplication
                                     cvar: ConfigVar,
                                     requirement_overwrite: bool = False) -> Any:
        """
        Prompt a single variable in the input pane, validates and returns the user input
        :param cvar: the config var to be prompted
        :param requirement_overwrite: Set to true when a config var is forced to be prompted,
               even if it is not required by default setting
        :return: a validated user input or the variable's default value
        """
        if cvar.required or requirement_overwrite:
            if cvar.key == "strategy_file_path":
                val = await self._import_or_create_strategy_config()
            elif cvar.key == "wallet":
                wallets = list_wallets()
                if len(wallets) > 0:
                    val = await self._unlock_wallet()
                else:
                    val = await self._create_or_import_wallet()
            else:
                if cvar.value is None:
                    self.app.set_text(parse_cvar_default_value_prompt(cvar))
                val = await self.app.prompt(prompt=cvar.prompt, is_password=cvar.is_secure)

            if not cvar.validate(val):
                # If the user inputs an empty string, use the default
                val_is_empty = val is None or (isinstance(val, str) and len(val) == 0)
                if cvar.default is not None and val_is_empty:
                    val = cvar.default
                else:
                    self._notify("%s is not a valid %s value" % (val, cvar.key))
                    val = await self.prompt_single_variable(cvar, requirement_overwrite)
        else:
            val = cvar.value
        if val is None or (isinstance(val, str) and len(val) == 0):
            val = cvar.default
        return val

    @staticmethod
    def _get_config_var_with_key(key: str) -> ConfigVar:
        """
        Check if key exists in `in_memory_config-map`, `global_config_map`, and `strategy_config_map`.
        If so, return the corresponding ConfigVar for that key
        """
        current_strategy: str = global_config_map.get("strategy").value
        strategy_cm: Optional[Dict[str, ConfigVar]] = get_strategy_config_map(current_strategy)
        if key in in_memory_config_map:
            cv: ConfigVar = in_memory_config_map.get(key)
        elif key in global_config_map:
            cv: ConfigVar = global_config_map.get(key)
        elif strategy_cm is not None and key in strategy_cm:
            cv: ConfigVar = strategy_cm.get(key)
        else:
            raise ValueError(f"No config variable associated with key name {key}")
        return cv

    async def _inner_config_loop(self, keys: List[str]):
        """
        Inner loop used by `self._config_loop` that recursively calls itself until all required configs are filled.
        This enables the bot to detect any newly added requirements as the user fills currently required variables.
        Use case example:
        When the user selects a particular market, the API keys related to that market becomes required.
        :param keys:
        """
        for key in keys:
            cv: ConfigVar = self._get_config_var_with_key(key)
            if cv.value is not None and cv.key != "wallet":
                continue
            if cv.is_secure and Security.encrypted_file_exists(cv.key):
                await Security.wait_til_decryption_done()
            value = await self.prompt_single_variable(cv, requirement_overwrite=False)
            cv.value = parse_cvar_value(cv, value)
            if self.config_complete:
                break
        if not self.config_complete:
            await self._inner_config_loop(self._get_empty_configs())

    async def _config_loop(self,  # type: HummingbotApplication
                           keys: List[str] = []):
        """
        Loop until all necessary config variables are complete and the bot is ready for "start"
        """
        self._notify("Please follow the prompt to complete configurations: ")
        self.placeholder_mode = True
        self.app.toggle_hide_input()

        try:
            await self._inner_config_loop(keys)
            await write_config_to_yml(self.strategy_name, self.strategy_file_name)
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

    # Make this function static so unit testing can be performed.
    @staticmethod
    def update_running_pure_mm(pure_mm_strategy: PureMarketMakingStrategyV2, key: str, new_value: Any):
        if key == "bid_place_threshold":
            pure_mm_strategy.pricing_delegate.bid_spread = new_value
        elif key == "ask_place_threshold":
            pure_mm_strategy.pricing_delegate.ask_spread = new_value

    async def _config_single_key(self,  # type: HummingbotApplication
                                 key: str):
        """
        Configure a single variable only.
        Prompt the user to finish all configurations if there are remaining empty configs at the end.
        """
        self._notify("Please follow the prompt to complete configurations: ")
        self.placeholder_mode = True
        self.app.toggle_hide_input()

        try:
            cv: ConfigVar = self._get_config_var_with_key(key)
            value = await self.prompt_single_variable(cv, requirement_overwrite=True)
            cv.value = parse_cvar_value(cv, value)
            if cv.is_secure:
                Security.update_secure_config(cv.key, cv.value)
            else:
                await write_config_to_yml(self.strategy_name, self.strategy_file_name)
            self._notify(f"\nNew config saved:\n{key}: {str(value)}")
            if isinstance(self.strategy, PureMarketMakingStrategyV2):
                ConfigCommand.update_running_pure_mm(self.strategy, key, cv.value)

        except asyncio.TimeoutError:
            self.logger().error("Prompt timeout")
        except Exception as err:
            self.logger().error("Unknown error while writing config. %s" % (err,), exc_info=True)
        finally:
            self.app.toggle_hide_input()
            self.placeholder_mode = False
            self.app.change_prompt(prompt=">>> ")
