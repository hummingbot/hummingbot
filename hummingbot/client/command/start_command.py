import asyncio
import platform
import threading
import time
from os.path import dirname, exists, join
from typing import Any, Callable, Dict, List, Optional
from typing import TYPE_CHECKING

import pandas as pd

import hummingbot.client.config.global_config_map as global_config
import hummingbot.client.settings as settings
from hummingbot import init_logging
from hummingbot.client.command.rate_command import RateCommand
from hummingbot.client.config.config_helpers import get_strategy_starter_file
from hummingbot.client.config.config_validators import validate_bool
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.connector.connector_status import get_connector_status, warning_messages
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.kill_switch import KillSwitch
from hummingbot.exceptions import OracleRateUnavailable
from hummingbot.pmm_script.pmm_script_iterator import PMMScriptIterator
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.user.user_balances import UserBalances

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class StartCommand:
    async def _run_clock(self):
        with self.clock as clock:
            await clock.run()

    async def wait_till_ready(self,  # type: HummingbotApplication
                              func: Callable, *args, **kwargs):
        while True:
            all_ready = all([market.ready for market in self.markets.values()])
            if not all_ready:
                await asyncio.sleep(0.5)
            else:
                return func(*args, **kwargs)

    def start(self,  # type: HummingbotApplication
              log_level: Optional[str] = None,
              restore: Optional[bool] = False,
              script: Optional[str] = None):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.start, log_level, restore)
            return
        safe_ensure_future(self.start_check(log_level, restore, script), loop=self.ev_loop)

    async def start_check(self,  # type: HummingbotApplication
                          log_level: Optional[str] = None,
                          restore: Optional[bool] = False,
                          strategy_file_name: Optional[str] = None):
        if self.strategy_task is not None and not self.strategy_task.done():
            self.notify('The bot is already running - please run "stop" first')
            return

        if settings.required_rate_oracle:
            # If the strategy to run requires using the rate oracle to find FX rates, validate there is a rate for
            # each configured token pair
            if not (await self.confirm_oracle_conversion_rate()):
                self.notify("The strategy failed to start.")
                return

        if strategy_file_name:
            file_name = strategy_file_name.split(".")[0]
            self.strategy_file_name = file_name
            self.strategy_name = file_name
        elif not await self.status_check_all(notify_success=False):
            self.notify("Status checks failed. Start aborted.")
            return
        if self._last_started_strategy_file != self.strategy_file_name:
            init_logging("hummingbot_logs.yml",
                         override_log_level=log_level.upper() if log_level else None,
                         strategy_file_path=self.strategy_file_name)
            self._last_started_strategy_file = self.strategy_file_name

        # If macOS, disable App Nap.
        if platform.system() == "Darwin":
            import appnope
            appnope.nope()

        self._initialize_notifiers()
        try:
            self._initialize_strategy(self.strategy_name)
        except NotImplementedError:
            self.strategy_name = None
            self.strategy_file_name = None
            self.notify("Invalid strategy. Start aborted.")
            raise

        if any([str(exchange).endswith("paper_trade") for exchange in settings.required_exchanges]):
            self.notify("\nPaper Trading Active: All orders are simulated and no real orders are placed.")

        for exchange in settings.required_exchanges:
            connector: str = str(exchange)
            status: str = get_connector_status(connector)
            warning_msg: Optional[str] = warning_messages.get(connector, None)

            # confirm gateway connection
            conn_setting: settings.ConnectorSetting = settings.AllConnectorSettings.get_connector_settings()[connector]
            if conn_setting.uses_gateway_generic_connector():
                connector_details: Dict[str, Any] = conn_setting.conn_init_parameters()
                if connector_details:
                    data: List[List[str]] = [
                        ["chain", connector_details['chain']],
                        ["network", connector_details['network']],
                        ["wallet_address", connector_details['wallet_address']]
                    ]
                    await UserBalances.instance().update_exchange_balance(connector)
                    balances: List[str] = [
                        f"{str(PerformanceMetrics.smart_round(v, 8))} {k}"
                        for k, v in UserBalances.instance().all_balances(connector).items()
                    ]
                    data.append(["balances", ""])
                    for bal in balances:
                        data.append(["", bal])
                    wallet_df: pd.DataFrame = pd.DataFrame(data=data, columns=["", f"{connector} configuration"])
                    self.notify(wallet_df.to_string(index=False))

                    self.app.clear_input()
                    self.placeholder_mode = True
                    use_configuration = await self.app.prompt(prompt="Do you want to continue? (Yes/No) >>> ")
                    self.placeholder_mode = False
                    self.app.change_prompt(prompt=">>> ")

                    if use_configuration in ["N", "n", "No", "no"]:
                        return

                    if use_configuration not in ["Y", "y", "Yes", "yes"]:
                        self.notify("Invalid input. Please execute the `start` command again.")
                        return

            # Display custom warning message for specific connectors
            elif warning_msg is not None:
                self.notify(f"\nConnector status: {status}\n"
                            f"{warning_msg}")

            # Display warning message if the exchange connector has outstanding issues or not working
            elif not status.endswith("GREEN"):
                self.notify(f"\nConnector status: {status}. This connector has one or more issues.\n"
                            "Refer to our Github page for more info: https://github.com/coinalpha/hummingbot")

        self.notify(f"\nStatus check complete. Starting '{self.strategy_name}' strategy...")
        await self.start_market_making(restore)
        # We always start the RateOracle. It is required for PNL calculation.
        RateOracle.get_instance().start()

    def start_script_strategy(self):
        script_strategy = ScriptStrategyBase.load_script_class(self.strategy_file_name)
        markets_list = []
        for conn, pairs in script_strategy.markets.items():
            markets_list.append((conn, list(pairs)))
        self._initialize_markets(markets_list)
        self.strategy = script_strategy(self.markets)

    def is_current_strategy_script_strategy(self) -> bool:
        script_file_name = join(settings.SCRIPT_STRATEGIES_PATH, f"{self.strategy_file_name}.py")
        return exists(script_file_name)

    async def start_market_making(self,  # type: HummingbotApplication
                                  restore: Optional[bool] = False):
        try:
            self.start_time = time.time() * 1e3  # Time in milliseconds
            self.clock = Clock(ClockMode.REALTIME)
            for market in self.markets.values():
                if market is not None:
                    self.clock.add_iterator(market)
                    self.markets_recorder.restore_market_states(self.strategy_file_name, market)
                    if len(market.limit_orders) > 0:
                        if restore is False:
                            self.notify(f"Cancelling dangling limit orders on {market.name}...")
                            await market.cancel_all(5.0)
                        else:
                            self.notify(f"Restored {len(market.limit_orders)} limit orders on {market.name}...")
            if self.strategy:
                self.clock.add_iterator(self.strategy)
            if global_config.global_config_map[global_config.PMM_SCRIPT_ENABLED_KEY].value:
                pmm_script_file = global_config.global_config_map[global_config.PMM_SCRIPT_FILE_PATH_KEY].value
                folder = dirname(pmm_script_file)
                if folder == "":
                    pmm_script_file = join(settings.PMM_SCRIPTS_PATH, pmm_script_file)
                if self.strategy_name != "pure_market_making":
                    self.notify("Error: PMM script feature is only available for pure_market_making strategy.")
                else:
                    self._pmm_script_iterator = PMMScriptIterator(pmm_script_file,
                                                                  list(self.markets.values()),
                                                                  self.strategy, 0.1)
                    self.clock.add_iterator(self._pmm_script_iterator)
                    self.notify(f"PMM script ({pmm_script_file}) started.")

            self.strategy_task: asyncio.Task = safe_ensure_future(self._run_clock(), loop=self.ev_loop)
            self.notify(f"\n'{self.strategy_name}' strategy started.\n"
                        f"Run `status` command to query the progress.")
            self.logger().info("start command initiated.")

            if self._trading_required:
                self.kill_switch = KillSwitch(self)
                await self.wait_till_ready(self.kill_switch.start)
        except Exception as e:
            self.logger().error(str(e), exc_info=True)

    def _initialize_strategy(self, strategy_name: str):
        if self.is_current_strategy_script_strategy():
            self.start_script_strategy()
        else:
            start_strategy: Callable = get_strategy_starter_file(strategy_name)
            if strategy_name in settings.STRATEGIES:
                start_strategy(self)
            else:
                raise NotImplementedError

    async def confirm_oracle_conversion_rate(self,  # type: HummingbotApplication
                                             ) -> bool:
        try:
            result = False
            self.app.clear_input()
            self.placeholder_mode = True
            self.app.hide_input = True
            for pair in settings.rate_oracle_pairs:
                msg = await RateCommand.oracle_rate_msg(pair)
                self.notify("\nRate Oracle:\n" + msg)
            config = ConfigVar(key="confirm_oracle_use",
                               type_str="bool",
                               prompt="Please confirm to proceed if the above oracle source and rates are correct for "
                                      "this strategy (Yes/No)  >>> ",
                               required_if=lambda: True,
                               validator=lambda v: validate_bool(v))
            await self.prompt_a_config(config)
            if config.value:
                result = True
        except OracleRateUnavailable:
            self.notify("Oracle rate is not available.")
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")
        return result
