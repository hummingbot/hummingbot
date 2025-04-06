import asyncio
import importlib
import inspect
import platform
import sys
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set

import pandas as pd
import yaml

import hummingbot.client.settings as settings
from hummingbot import init_logging
from hummingbot.client.command.gateway_api_manager import GatewayChainApiManager
from hummingbot.client.command.gateway_command import GatewayCommand
from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.config.config_helpers import get_strategy_starter_file
from hummingbot.client.config.config_validators import validate_bool
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.exceptions import InvalidScriptModule, OracleRateUnavailable
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


GATEWAY_READY_TIMEOUT = 300  # seconds


class StartCommand(GatewayChainApiManager):
    _in_start_check: bool = False

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

    def _strategy_uses_gateway_connector(self, required_exchanges: Set[str]) -> bool:
        exchange_settings: List[settings.ConnectorSetting] = [
            settings.AllConnectorSettings.get_connector_settings().get(e, None)
            for e in required_exchanges
        ]
        return any([s.uses_gateway_generic_connector()
                    for s in exchange_settings])

    def start(self,  # type: HummingbotApplication
              log_level: Optional[str] = None,
              script: Optional[str] = None,
              conf: Optional[str] = None,
              is_quickstart: Optional[bool] = False):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.start, log_level, script)
            return
        safe_ensure_future(self.start_check(log_level, script, conf, is_quickstart), loop=self.ev_loop)

    async def start_check(self,  # type: HummingbotApplication
                          log_level: Optional[str] = None,
                          script: Optional[str] = None,
                          conf: Optional[str] = None,
                          is_quickstart: Optional[bool] = False):

        if self._in_start_check or (self.strategy_task is not None and not self.strategy_task.done()):
            self.notify('The bot is already running - please run "stop" first')
            return

        self._in_start_check = True

        if settings.required_rate_oracle:
            # If the strategy to run requires using the rate oracle to find FX rates, validate there is a rate for
            # each configured token pair
            if not (await self.confirm_oracle_conversion_rate()):
                self.notify("The strategy failed to start.")
                self._in_start_check = False
                return

        if self.strategy_file_name and self.strategy_name and is_quickstart:
            if self._strategy_uses_gateway_connector(settings.required_exchanges):
                try:
                    await asyncio.wait_for(self._gateway_monitor.ready_event.wait(), timeout=GATEWAY_READY_TIMEOUT)
                except asyncio.TimeoutError:
                    self.notify(f"TimeoutError waiting for gateway service to go online... Please ensure Gateway is configured correctly."
                                f"Unable to start strategy {self.strategy_name}. ")
                    self._in_start_check = False
                    self.strategy_name = None
                    self.strategy_file_name = None
                    raise

        if script:
            file_name = script.split(".")[0]
            self.strategy_name = file_name
            self.strategy_file_name = conf if conf else file_name
        elif not await self.status_check_all(notify_success=False):
            self.notify("Status checks failed. Start aborted.")
            self._in_start_check = False
            return
        if self._last_started_strategy_file != self.strategy_file_name:
            init_logging("hummingbot_logs.yml",
                         self.client_config_map,
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
            self._in_start_check = False
            self.strategy_name = None
            self.strategy_file_name = None
            self.notify("Invalid strategy. Start aborted.")
            raise

        if any([str(exchange).endswith("paper_trade") for exchange in settings.required_exchanges]):
            self.notify("\nPaper Trading Active: All orders are simulated and no real orders are placed.")

        for exchange in settings.required_exchanges:
            connector: str = str(exchange)

            # confirm gateway connection
            conn_setting: settings.ConnectorSetting = settings.AllConnectorSettings.get_connector_settings()[connector]
            if conn_setting.uses_gateway_generic_connector():
                connector_details: Dict[str, Any] = conn_setting.conn_init_parameters()
                if connector_details:
                    data: List[List[str]] = [
                        ["chain", connector_details['chain']],
                        ["network", connector_details['network']],
                        ["address", connector_details['address']]
                    ]

                    # check for node URL
                    await self._test_node_url_from_gateway_config(connector_details['chain'], connector_details['network'])

                    await GatewayCommand.update_exchange_balances(self, connector, self.client_config_map)
                    balances: List[str] = [
                        f"{str(PerformanceMetrics.smart_round(v, 8))} {k}"
                        for k, v in GatewayCommand.all_balance(self, connector).items()
                    ]
                    data.append(["balances", ""])
                    for bal in balances:
                        data.append(["", bal])
                    wallet_df: pd.DataFrame = pd.DataFrame(data=data, columns=["", f"{connector} configuration"])
                    self.notify(wallet_df.to_string(index=False))

                    if not is_quickstart:
                        self.app.clear_input()
                        self.placeholder_mode = True
                        use_configuration = await self.app.prompt(prompt="Do you want to continue? (Yes/No) >>> ")
                        self.placeholder_mode = False
                        self.app.change_prompt(prompt=">>> ")

                        if use_configuration in ["N", "n", "No", "no"]:
                            self._in_start_check = False
                            return

                        if use_configuration not in ["Y", "y", "Yes", "yes"]:
                            self.notify("Invalid input. Please execute the `start` command again.")
                            self._in_start_check = False
                            return

        self.notify(f"\nStatus check complete. Starting '{self.strategy_name}' strategy...")
        await self.start_market_making()

        self._in_start_check = False

        # We always start the RateOracle. It is required for PNL calculation.
        RateOracle.get_instance().start()
        if self._mqtt:
            self._mqtt.patch_loggers()

    def start_script_strategy(self):
        script_strategy, config = self.load_script_class()
        markets_list = []
        for conn, pairs in script_strategy.markets.items():
            markets_list.append((conn, list(pairs)))
        self._initialize_markets(markets_list)
        if config:
            self.strategy = script_strategy(self.markets, config)
        else:
            self.strategy = script_strategy(self.markets)

    def load_script_class(self):
        """
        Imports the script module based on its name (module file name) and returns the loaded script class

        :param script_name: name of the module where the script class is defined
        """
        script_name = self.strategy_name
        config = None
        module = sys.modules.get(f"{settings.SCRIPT_STRATEGIES_MODULE}.{script_name}")
        if module is not None:
            script_module = importlib.reload(module)
        else:
            script_module = importlib.import_module(f".{script_name}", package=settings.SCRIPT_STRATEGIES_MODULE)
        try:
            script_class = next((member for member_name, member in inspect.getmembers(script_module)
                                 if inspect.isclass(member) and
                                 issubclass(member, ScriptStrategyBase) and
                                 member not in [ScriptStrategyBase, DirectionalStrategyBase, StrategyV2Base]))
        except StopIteration:
            raise InvalidScriptModule(f"The module {script_name} does not contain any subclass of ScriptStrategyBase")
        if self.strategy_name != self.strategy_file_name:
            try:
                config_class = next((member for member_name, member in inspect.getmembers(script_module)
                                    if inspect.isclass(member) and
                                    issubclass(member, BaseClientModel) and member not in [BaseClientModel, StrategyV2ConfigBase]))
                config = config_class(**self.load_script_yaml_config(config_file_path=self.strategy_file_name))
                script_class.init_markets(config)
            except StopIteration:
                raise InvalidScriptModule(f"The module {script_name} does not contain any subclass of BaseModel")

        return script_class, config

    @staticmethod
    def load_script_yaml_config(config_file_path: str) -> dict:
        with open(settings.SCRIPT_STRATEGY_CONF_DIR_PATH / config_file_path, 'r') as file:
            return yaml.safe_load(file)

    def is_current_strategy_script_strategy(self) -> bool:
        script_file_name = settings.SCRIPT_STRATEGIES_PATH / f"{self.strategy_name}.py"
        return script_file_name.exists()

    async def start_market_making(self,  # type: HummingbotApplication
                                  ):
        try:
            self.start_time = time.time() * 1e3  # Time in milliseconds
            tick_size = self.client_config_map.tick_size
            self.logger().info(f"Creating the clock with tick size: {tick_size}")
            self.clock = Clock(ClockMode.REALTIME, tick_size=tick_size)
            for market in self.markets.values():
                if market is not None:
                    self.clock.add_iterator(market)
                    self.markets_recorder.restore_market_states(self.strategy_file_name, market)
                    if len(market.limit_orders) > 0:
                        self.notify(f"Canceling dangling limit orders on {market.name}...")
                        await market.cancel_all(10.0)
            if self.strategy:
                self.clock.add_iterator(self.strategy)
            self.strategy_task: asyncio.Task = safe_ensure_future(self._run_clock(), loop=self.ev_loop)
            self.notify(f"\n'{self.strategy_name}' strategy started.\n"
                        f"Run `status` command to query the progress.")
            self.logger().info("start command initiated.")

            if self._trading_required:
                self.kill_switch = self.client_config_map.kill_switch_mode.get_kill_switch(self)
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
                msg = await self.oracle_rate_msg(pair)
                self.notify("\nRate Oracle:\n" + msg)
            config = ConfigVar(key="confirm_oracle_use",
                               type_str="bool",
                               prompt="Please confirm to proceed if the above oracle source and rates are correct for "
                                      "this strategy (Yes/No)  >>> ",
                               required_if=lambda: True,
                               validator=lambda v: validate_bool(v))
            await self.prompt_a_config_legacy(config)
            if config.value:
                result = True
        except OracleRateUnavailable:
            self.notify("Oracle rate is not available.")
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")
        return result
