import asyncio
from decimal import Decimal
from os.path import join
from typing import (
    Any,
    List,
    TYPE_CHECKING,
)

import pandas as pd

from hummingbot.client.config.config_helpers import (
    missing_required_configs,
    save_to_yml,
)
from hummingbot.client.config.config_validators import validate_bool, validate_decimal
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.security import Security
from hummingbot.client.settings import (
    CONF_FILE_PATH,
    GLOBAL_CONFIG_PATH,
)
from hummingbot.client.ui.style import load_style
from hummingbot.core.utils import map_df_to_str
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.model.inventory_cost import InventoryCost
from hummingbot.strategy.perpetual_market_making import PerpetualMarketMakingStrategy
from hummingbot.strategy.pure_market_making import PureMarketMakingStrategy
from hummingbot.user.user_balances import UserBalances

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

no_restart_pmm_keys_in_percentage = ["bid_spread", "ask_spread", "order_level_spread", "inventory_target_base_pct"]
no_restart_pmm_keys = ["order_amount",
                       "order_levels",
                       "filled_order_delay",
                       "inventory_skew_enabled",
                       "inventory_range_multiplier"]
global_configs_to_display = ["autofill_import",
                             "kill_switch_enabled",
                             "kill_switch_rate",
                             "telegram_enabled",
                             "telegram_token",
                             "telegram_chat_id",
                             "send_error_logs",
                             "script_enabled",
                             "script_file_path",
                             "ethereum_chain_name",
                             "gateway_enabled",
                             "gateway_cert_passphrase",
                             "gateway_api_host",
                             "gateway_api_port",
                             "rate_oracle_source",
                             "global_token",
                             "global_token_symbol",
                             "rate_limits_share_pct",
                             "create_command_timeout",
                             "other_commands_timeout"]
color_settings_to_display = ["top-pane",
                             "bottom-pane",
                             "output-pane",
                             "input-pane",
                             "logs-pane",
                             "terminal-primary"]


class ConfigCommand:
    def config(self,  # type: HummingbotApplication
               key: str = None,
               value: str = None):
        self.app.clear_input()
        if key is None:
            self.list_configs()
            return
        else:
            if key not in self.config_able_keys():
                self._notify("Invalid key, please choose from the list.")
                return
            safe_ensure_future(self._config_single_key(key, value), loop=self.ev_loop)

    def list_configs(self,  # type: HummingbotApplication
                     ):
        columns = ["Key", "  Value"]
        data = [[cv.key, cv.value] for cv in global_config_map.values()
                if cv.key in global_configs_to_display and not cv.is_secure]
        df = map_df_to_str(pd.DataFrame(data=data, columns=columns))
        self._notify("\nGlobal Configurations:")
        lines = ["    " + line for line in df.to_string(index=False, max_colwidth=50).split("\n")]
        self._notify("\n".join(lines))

        data = [[cv.key, cv.value] for cv in global_config_map.values()
                if cv.key in color_settings_to_display and not cv.is_secure]
        df = map_df_to_str(pd.DataFrame(data=data, columns=columns))
        self._notify("\nColor Settings:")
        lines = ["    " + line for line in df.to_string(index=False, max_colwidth=50).split("\n")]
        self._notify("\n".join(lines))

        if self.strategy_name is not None:
            data = [[cv.printable_key or cv.key, cv.value] for cv in self.strategy_config_map.values() if not cv.is_secure]
            df = map_df_to_str(pd.DataFrame(data=data, columns=columns))
            self._notify("\nStrategy Configurations:")
            lines = ["    " + line for line in df.to_string(index=False, max_colwidth=50).split("\n")]
            self._notify("\n".join(lines))

    def config_able_keys(self  # type: HummingbotApplication
                         ) -> List[str]:
        """
        Returns a list of configurable keys - using config command, excluding exchanges api keys
        as they are set from connect command.
        """
        keys = [c.key for c in global_config_map.values() if c.prompt is not None and not c.is_connect_key]
        if self.strategy_config_map is not None:
            keys += [c.key for c in self.strategy_config_map.values() if c.prompt is not None]
        return keys

    async def check_password(self,  # type: HummingbotApplication
                             ):
        password = await self.app.prompt(prompt="Enter your password >>> ", is_password=True)
        if password != Security.password:
            self._notify("Invalid password, please try again.")
            return False
        else:
            return True

    # Make this function static so unit testing can be performed.
    @staticmethod
    def update_running_mm(mm_strategy, key: str, new_value: Any):
        if key in no_restart_pmm_keys_in_percentage:
            setattr(mm_strategy, key, new_value / Decimal("100"))
            return True
        elif key in no_restart_pmm_keys:
            setattr(mm_strategy, key, new_value)
            return True
        return False

    async def _config_single_key(self,  # type: HummingbotApplication
                                 key: str,
                                 input_value):
        """
        Configure a single variable only.
        Prompt the user to finish all configurations if there are remaining empty configs at the end.
        """

        self.placeholder_mode = True
        self.app.hide_input = True

        try:
            config_var, config_map, file_path = None, None, None
            if key in global_config_map:
                config_map = global_config_map
                file_path = GLOBAL_CONFIG_PATH
            elif self.strategy_config_map is not None and key in self.strategy_config_map:
                config_map = self.strategy_config_map
                file_path = join(CONF_FILE_PATH, self.strategy_file_name)
            config_var = config_map[key]
            if input_value is None:
                self._notify("Please follow the prompt to complete configurations: ")
            if config_var.key == "inventory_target_base_pct":
                await self.asset_ratio_maintenance_prompt(config_map, input_value)
            elif config_var.key == "inventory_price":
                await self.inventory_price_prompt(config_map, input_value)
            else:
                await self.prompt_a_config(config_var, input_value=input_value, assign_default=False)
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
            await self.update_all_secure_configs()
            missings = missing_required_configs(config_map)
            if missings:
                self._notify("\nThere are other configuration required, please follow the prompt to complete them.")
            missings = await self._prompt_missing_configs(config_map)
            save_to_yml(file_path, config_map)
            self._notify("\nNew configuration saved:")
            self._notify(f"{key}: {str(config_var.value)}")
            self.app.app.style = load_style()
            for config in missings:
                self._notify(f"{config.key}: {str(config.value)}")
            if isinstance(self.strategy, PureMarketMakingStrategy) or \
               isinstance(self.strategy, PerpetualMarketMakingStrategy):
                updated = ConfigCommand.update_running_mm(self.strategy, key, config_var.value)
                if updated:
                    self._notify(f"\nThe current {self.strategy_name} strategy has been updated "
                                 f"to reflect the new configuration.")
        except asyncio.TimeoutError:
            self.logger().error("Prompt timeout")
        except Exception as err:
            self.logger().error(str(err), exc_info=True)
        finally:
            self.app.hide_input = False
            self.placeholder_mode = False
            self.app.change_prompt(prompt=">>> ")

    async def _prompt_missing_configs(self,  # type: HummingbotApplication
                                      config_map):
        missings = missing_required_configs(config_map)
        for config in missings:
            await self.prompt_a_config(config)
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
        if missing_required_configs(config_map):
            return missings + (await self._prompt_missing_configs(config_map))
        return missings

    async def asset_ratio_maintenance_prompt(self,  # type: HummingbotApplication
                                             config_map,
                                             input_value = None):
        if input_value:
            config_map['inventory_target_base_pct'].value = Decimal(input_value)
        else:
            exchange = config_map['exchange'].value
            market = config_map["market"].value
            base, quote = market.split("-")
            balances = await UserBalances.instance().balances(exchange, base, quote)
            if balances is None:
                return
            base_ratio = await UserBalances.base_amount_ratio(exchange, market, balances)
            if base_ratio is None:
                return
            base_ratio = round(base_ratio, 3)
            quote_ratio = 1 - base_ratio
            base, quote = config_map["market"].value.split("-")

            cvar = ConfigVar(key="temp_config",
                             prompt=f"On {exchange}, you have {balances.get(base, 0):.4f} {base} and "
                                    f"{balances.get(quote, 0):.4f} {quote}. By market value, "
                                    f"your current inventory split is {base_ratio:.1%} {base} "
                                    f"and {quote_ratio:.1%} {quote}."
                                    f" Would you like to keep this ratio? (Yes/No) >>> ",
                             required_if=lambda: True,
                             type_str="bool",
                             validator=validate_bool)
            await self.prompt_a_config(cvar)
            if cvar.value:
                config_map['inventory_target_base_pct'].value = round(base_ratio * Decimal('100'), 1)
            else:
                if self.app.to_stop_config:
                    self.app.to_stop_config = False
                    return
                await self.prompt_a_config(config_map["inventory_target_base_pct"])

    async def inventory_price_prompt(
        self,  # type: HummingbotApplication
        config_map,
        input_value=None,
    ):
        key = "inventory_price"
        if input_value:
            config_map[key].value = Decimal(input_value)
        else:
            exchange = config_map["exchange"].value
            market = config_map["market"].value
            base_asset, quote_asset = market.split("-")

            if exchange.endswith("paper_trade"):
                balances = global_config_map["paper_trade_account_balance"].value
            else:
                balances = await UserBalances.instance().balances(
                    exchange, base_asset, quote_asset
                )
            if balances.get(base_asset) is None:
                return

            cvar = ConfigVar(
                key="temp_config",
                prompt=f"On {exchange}, you have {balances[base_asset]:.4f} {base_asset}. "
                f"What was the price for this amount in {quote_asset}?  >>> ",
                required_if=lambda: True,
                type_str="decimal",
                validator=lambda v: validate_decimal(
                    v, min_value=Decimal("0"), inclusive=True
                ),
            )
            await self.prompt_a_config(cvar)
            config_map[key].value = cvar.value

            try:
                quote_volume = balances[base_asset] * cvar.value
            except TypeError:
                # TypeError: unsupported operand type(s) for *: 'decimal.Decimal' and 'NoneType' - bad input / no input
                self._notify("Inventory price not updated due to bad input")
                return

            with self.trade_fill_db.get_new_session() as session:
                with session.begin():
                    InventoryCost.add_volume(
                        session,
                        base_asset=base_asset,
                        quote_asset=quote_asset,
                        base_volume=balances[base_asset],
                        quote_volume=quote_volume,
                        overwrite=True,
                    )
