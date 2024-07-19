import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from prompt_toolkit.utils import is_windows

from hummingbot.client.command.gateway_command import GatewayCommand
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    missing_required_configs_legacy,
    save_to_yml,
    save_to_yml_legacy,
)
from hummingbot.client.config.config_validators import validate_bool, validate_decimal
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.security import Security
from hummingbot.client.config.strategy_config_data_types import BaseTradingStrategyConfigMap
from hummingbot.client.settings import CLIENT_CONFIG_PATH, STRATEGIES_CONF_DIR_PATH
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.client.ui.style import load_style
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.utils import map_df_to_str
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.model.inventory_cost import InventoryCost
from hummingbot.strategy.perpetual_market_making import PerpetualMarketMakingStrategy
from hummingbot.strategy.pure_market_making import PureMarketMakingStrategy
from hummingbot.user.user_balances import UserBalances

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401

no_restart_pmm_keys_in_percentage = ["bid_spread", "ask_spread", "order_level_spread", "inventory_target_base_pct"]
no_restart_pmm_keys = ["order_amount",
                       "order_levels",
                       "filled_order_delay",
                       "inventory_skew_enabled",
                       "inventory_range_multiplier",
                       "price_ceiling",
                       "price_floor",
                       "moving_price_band_enabled",
                       "price_ceiling_pct",
                       "price_floor_pct",
                       "price_band_refresh_time"
                       "order_optimization_enabled",
                       "bid_order_optimization_depth",
                       "ask_order_optimization_depth"
                       ]
client_configs_to_display = ["autofill_import",
                             "kill_switch_mode",
                             "kill_switch_rate",
                             "telegram_mode",
                             "telegram_token",
                             "telegram_chat_id",
                             "mqtt_bridge",
                             "mqtt_host",
                             "mqtt_port",
                             "mqtt_namespace",
                             "mqtt_username",
                             "mqtt_password",
                             "mqtt_ssl",
                             "mqtt_logger",
                             "mqtt_notifier",
                             "mqtt_commands",
                             "mqtt_events",
                             "mqtt_external_events",
                             "mqtt_autostart",
                             "instance_id",
                             "send_error_logs",
                             "ethereum_chain_name",
                             "gateway",
                             "gateway_api_host",
                             "gateway_api_port",
                             "rate_oracle_source",
                             "extra_tokens",
                             "fetch_pairs_from_all_exchanges",
                             "global_token",
                             "global_token_name",
                             "global_token_symbol",
                             "rate_limits_share_pct",
                             "commands_timeout",
                             "create_command_timeout",
                             "other_commands_timeout",
                             "tables_format",
                             "tick_size",
                             "market_data_collection",
                             "market_data_collection_enabled",
                             "market_data_collection_interval",
                             "market_data_collection_depth",
                             ]
color_settings_to_display = ["top_pane",
                             "bottom_pane",
                             "output_pane",
                             "input_pane",
                             "logs_pane",
                             "terminal_primary"]
columns = ["Key", "Value"]


class ConfigCommand:
    def config(self,  # type: HummingbotApplication
               key: str = None,
               value: str = None):
        self.app.clear_input()
        if key is None:
            self.list_configs()
            return
        else:
            if key not in self.configurable_keys():
                self.notify("Invalid key, please choose from the list.")
                return
            safe_ensure_future(self._config_single_key(key, value), loop=self.ev_loop)

    def list_configs(self,  # type: HummingbotApplication
                     ):
        self.list_client_configs()
        self.list_strategy_configs()

    def list_client_configs(
            self,  # type: HummingbotApplication
    ):
        data = self.build_model_df_data(self.client_config_map, to_print=client_configs_to_display)
        df = map_df_to_str(pd.DataFrame(data=data, columns=columns))
        self.notify("\nGlobal Configurations:")
        lines = ["    " + line for line in format_df_for_printout(
            df,
            table_format=self.client_config_map.tables_format,
            max_col_width=50).split("\n")]
        self.notify("\n".join(lines))

        data = self.build_model_df_data(self.client_config_map, to_print=color_settings_to_display)
        df = map_df_to_str(pd.DataFrame(data=data, columns=columns))
        self.notify("\nColor Settings:")
        lines = ["    " + line for line in format_df_for_printout(
            df,
            table_format=self.client_config_map.tables_format,
            max_col_width=50).split("\n")]
        self.notify("\n".join(lines))

    def list_strategy_configs(
            self,  # type: HummingbotApplication
    ):
        if self.strategy_name is not None:
            config_map = self.strategy_config_map
            data = self.build_df_data_from_config_map(config_map)
            df = map_df_to_str(pd.DataFrame(data=data, columns=columns))
            self.notify("\nStrategy Configurations:")
            lines = ["    " + line for line in format_df_for_printout(
                df,
                table_format=self.client_config_map.tables_format,
                max_col_width=50).split("\n")]
            self.notify("\n".join(lines))

    def build_df_data_from_config_map(
            self,  # type: HummingbotApplication
            config_map: Union[ClientConfigAdapter, Dict[str, ConfigVar]]
    ) -> List[Tuple[str, Any]]:
        if isinstance(config_map, ClientConfigAdapter):
            data = self.build_model_df_data(config_map)
        else:  # legacy
            data = [[cv.printable_key or cv.key, cv.value] for cv in self.strategy_config_map.values() if
                    not cv.is_secure]
        return data

    @staticmethod
    def build_model_df_data(
            config_map: ClientConfigAdapter, to_print: Optional[List[str]] = None
    ) -> List[Tuple[str, Any]]:
        model_data = []
        for traversal_item in config_map.traverse():
            if to_print is not None and traversal_item.attr not in to_print:
                continue
            attr_printout = (
                "  " * (traversal_item.depth - 1)
                + (u"\u221F " if not is_windows() else "  ")
                + traversal_item.attr
            ) if traversal_item.depth else traversal_item.attr
            model_data.append((attr_printout, traversal_item.printable_value))
        return model_data

    def configurable_keys(self,  # type: HummingbotApplication
                          ) -> List[str]:
        """
        Returns a list of configurable keys - using config command, excluding exchanges api keys
        as they are set from connect command.
        """
        keys = [
            traversal_item.config_path
            for traversal_item in self.client_config_map.traverse()
            if (traversal_item.client_field_data is not None and traversal_item.client_field_data.prompt is not None)
        ]
        if self.strategy_config_map is not None:
            if isinstance(self.strategy_config_map, ClientConfigAdapter):
                keys.extend([
                    traversal_item.config_path
                    for traversal_item in self.strategy_config_map.traverse()
                    if (traversal_item.client_field_data is not None
                        and traversal_item.client_field_data.prompt is not None)
                ])
            else:  # legacy
                keys.extend(
                    [c.key for c in self.strategy_config_map.values() if c.prompt is not None and c.key != 'strategy'])
        return keys

    async def check_password(self,  # type: HummingbotApplication
                             ):
        password = await self.app.prompt(prompt="Enter your password >>> ", is_password=True)
        if password != Security.secrets_manager.password.get_secret_value():
            self.notify("Invalid password, please try again.")
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
            if (
                    not isinstance(self.strategy_config_map, (type(None), ClientConfigAdapter))
                    and key in self.strategy_config_map
            ):
                await self._config_single_key_legacy(key, input_value)
            else:
                client_config_key = key in self.client_config_map.config_paths()
                if client_config_key:
                    config_map = self.client_config_map
                    file_path = CLIENT_CONFIG_PATH
                elif self.strategy is not None:
                    self.notify("Configuring the strategy while it is running is not currently supported.")
                    return
                else:
                    config_map = self.strategy_config_map
                    if self.strategy_file_name is not None:
                        file_path = STRATEGIES_CONF_DIR_PATH / self.strategy_file_name
                    else:
                        self.notify("Strategy file name is not configured.")
                        return

                if input_value is None:
                    self.notify("Please follow the prompt to complete configurations: ")
                if key == "inventory_target_base_pct":
                    await self.asset_ratio_maintenance_prompt(config_map, input_value)
                elif key == "inventory_price":
                    await self.inventory_price_prompt(config_map, input_value)
                else:
                    await self.prompt_a_config(config_map, key, input_value, assign_default=False)
                if self.app.to_stop_config:
                    self.app.to_stop_config = False
                    return
                save_to_yml(file_path, config_map)
                self.notify("\nNew configuration saved.")
                if client_config_key:
                    self.list_client_configs()
                else:
                    self.list_strategy_configs()
                self.app.style = load_style(self.client_config_map)
        except asyncio.TimeoutError:
            self.logger().error("Prompt timeout")
        except Exception as err:
            self.logger().error(str(err), exc_info=True)
        finally:
            self.app.hide_input = False
            self.placeholder_mode = False
            self.app.change_prompt(prompt=">>> ")

    async def _config_single_key_legacy(
            self,  # type: HummingbotApplication
            key: str,
            input_value: Any,
    ):  # pragma: no cover
        config_var, config_map, file_path = None, None, None
        if self.strategy_config_map is not None and key in self.strategy_config_map:
            config_map = self.strategy_config_map
            file_path = STRATEGIES_CONF_DIR_PATH / self.strategy_file_name
        config_var = config_map[key]
        if config_var.key == "strategy":
            self.notify("You cannot change the strategy of a loaded configuration.")
            self.notify("Please use 'import xxx.yml' or 'create' to configure the intended strategy")
            return
        if input_value is None:
            self.notify("Please follow the prompt to complete configurations: ")
        if config_var.key == "inventory_target_base_pct":
            await self.asset_ratio_maintenance_prompt_legacy(config_map, input_value)
        elif config_var.key == "inventory_price":
            await self.inventory_price_prompt_legacy(config_map, input_value)
        else:
            await self.prompt_a_config_legacy(config_var, input_value=input_value, assign_default=False)
        if self.app.to_stop_config:
            self.app.to_stop_config = False
            return
        missings = missing_required_configs_legacy(config_map)
        if missings:
            self.notify("\nThere are other configuration required, please follow the prompt to complete them.")
        missings = await self._prompt_missing_configs(config_map)
        save_to_yml_legacy(str(file_path), config_map)
        self.notify("\nNew configuration saved:")
        self.notify(f"{key}: {str(config_var.value)}")
        self.app.app.style = load_style(self.client_config_map)
        for config in missings:
            self.notify(f"{config.key}: {str(config.value)}")
        if (
                isinstance(self.strategy, PureMarketMakingStrategy) or
                isinstance(self.strategy, PerpetualMarketMakingStrategy)
        ):
            updated = ConfigCommand.update_running_mm(self.strategy, key, config_var.value)
            if updated:
                self.notify(f"\nThe current {self.strategy_name} strategy has been updated "
                            f"to reflect the new configuration.")

    async def _prompt_missing_configs(self,  # type: HummingbotApplication
                                      config_map):
        missings = missing_required_configs_legacy(config_map)
        for config in missings:
            await self.prompt_a_config_legacy(config)
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
        if missing_required_configs_legacy(config_map):
            return missings + (await self._prompt_missing_configs(config_map))
        return missings

    async def asset_ratio_maintenance_prompt(
            self,  # type: HummingbotApplication
            config_map: BaseTradingStrategyConfigMap,
            input_value: Any = None,
    ):  # pragma: no cover
        if input_value:
            config_map.inventory_target_base_pct = input_value
        else:
            exchange = config_map.exchange
            market = config_map.market
            base, quote = split_hb_trading_pair(market)
            if UserBalances.instance().is_gateway_market(exchange):
                balances = await GatewayCommand.balance(self, exchange, config_map, base, quote)
            else:
                balances = await UserBalances.instance().balances(exchange, config_map, base, quote)
            if balances is None:
                return
            base_ratio = await UserBalances.base_amount_ratio(exchange, market, balances)
            if base_ratio is None:
                return
            base_ratio = round(base_ratio, 3)
            quote_ratio = 1 - base_ratio

            cvar = ConfigVar(key="temp_config",
                             prompt=f"On {exchange}, you have {balances.get(base, 0):.4f} {base} and "
                                    f"{balances.get(quote, 0):.4f} {quote}. By market value, "
                                    f"your current inventory split is {base_ratio:.1%} {base} "
                                    f"and {quote_ratio:.1%} {quote}."
                                    f" Would you like to keep this ratio? (Yes/No) >>> ",
                             required_if=lambda: True,
                             type_str="bool",
                             validator=validate_bool)
            await self.prompt_a_config_legacy(cvar)
            if cvar.value:
                config_map.inventory_target_base_pct = round(base_ratio * Decimal('100'), 1)
            elif self.app.to_stop_config:
                self.app.to_stop_config = False
            else:
                await self.prompt_a_config(config_map, config="inventory_target_base_pct")

    async def asset_ratio_maintenance_prompt_legacy(
            self,  # type: HummingbotApplication
            config_map,
            input_value=None,
    ):
        if input_value:
            config_map['inventory_target_base_pct'].value = Decimal(input_value)
        else:
            exchange = config_map['exchange'].value
            market = config_map["market"].value
            base, quote = market.split("-")
            if UserBalances.instance().is_gateway_market(exchange):
                balances = await GatewayCommand.balance(self, exchange, config_map, base, quote)
            else:
                balances = await UserBalances.instance().balances(exchange, config_map, base, quote)
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
            await self.prompt_a_config_legacy(cvar)
            if cvar.value:
                config_map['inventory_target_base_pct'].value = round(base_ratio * Decimal('100'), 1)
            else:
                if self.app.to_stop_config:
                    self.app.to_stop_config = False
                    return
                await self.prompt_a_config_legacy(config_map["inventory_target_base_pct"])

    async def inventory_price_prompt(
            self,  # type: HummingbotApplication
            model: BaseTradingStrategyConfigMap,
            input_value=None,
    ):
        """
        Not currently used.
        """
        raise NotImplementedError

    async def inventory_price_prompt_legacy(
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
                balances = self.client_config_map.paper_trade.paper_trade_account_balance
            elif UserBalances.instance().is_gateway_market(exchange):
                balances = await GatewayCommand.balance(self, exchange, config_map, base_asset, quote_asset)
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
            await self.prompt_a_config_legacy(cvar)
            config_map[key].value = cvar.value

            try:
                quote_volume = balances[base_asset] * cvar.value
            except TypeError:
                # TypeError: unsupported operand type(s) for *: 'decimal.Decimal' and 'NoneType' - bad input / no input
                self.notify("Inventory price not updated due to bad input")
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
