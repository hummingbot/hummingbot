import asyncio
import platform
import threading
from typing import TYPE_CHECKING, Callable, List, Optional, Set

import hummingbot.client.settings as settings
from hummingbot import init_logging
from hummingbot.client.command.gateway_api_manager import GatewayChainApiManager
from hummingbot.client.config.config_validators import validate_bool
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.exceptions import OracleRateUnavailable

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401

GATEWAY_READY_TIMEOUT = 300  # seconds


class StartCommand(GatewayChainApiManager):
    _in_start_check: bool = False

    async def _run_clock(self):
        with self.trading_core.clock as clock:
            await clock.run()

    async def wait_till_ready(self,  # type: HummingbotApplication
                              func: Callable, *args, **kwargs):
        while True:
            all_ready = all([market.ready for market in self.trading_core.markets.values()])
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

        if self._in_start_check or (
                self.trading_core.strategy_task is not None and not self.trading_core.strategy_task.done()):
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

        if self.strategy_file_name and self.trading_core.strategy_name and is_quickstart:
            if self._strategy_uses_gateway_connector(settings.required_exchanges):
                try:
                    await asyncio.wait_for(self._gateway_monitor.ready_event.wait(), timeout=GATEWAY_READY_TIMEOUT)
                except asyncio.TimeoutError:
                    self.notify(
                        f"TimeoutError waiting for gateway service to go online... Please ensure Gateway is configured correctly."
                        f"Unable to start strategy {self.trading_core.strategy_name}. ")
                    self._in_start_check = False
                    self.trading_core.strategy_name = None
                    self.strategy_file_name = None
                    raise

        if script:
            file_name = script.split(".")[0]
            self.trading_core.strategy_name = file_name
            self.strategy_file_name = conf if conf else file_name
        elif not await self.status_check_all(notify_success=False):
            self.notify("Status checks failed. Start aborted.")
            self._in_start_check = False
            return
        init_logging("hummingbot_logs.yml",
                     self.client_config_map,
                     override_log_level=log_level.upper() if log_level else None,
                     strategy_file_path=self.strategy_file_name)

        # If macOS, disable App Nap.
        if platform.system() == "Darwin":
            import appnope
            appnope.nope()

        self._initialize_notifiers()

        # Delegate strategy initialization to trading_core
        try:
            strategy_config = None
            if self.trading_core.is_script_strategy(self.trading_core.strategy_name):
                if self.strategy_file_name and self.strategy_file_name != self.trading_core.strategy_name:
                    strategy_config = self.strategy_file_name

            success = await self.trading_core.start_strategy(
                self.trading_core.strategy_name,
                strategy_config,
                self.strategy_file_name
            )
            if not success:
                self._in_start_check = False
                self.trading_core.strategy_name = None
                self.strategy_file_name = None
                self.notify("Invalid strategy. Start aborted.")
                return
        except Exception as e:
            self._in_start_check = False
            self.trading_core.strategy_name = None
            self.strategy_file_name = None
            self.notify(f"Invalid strategy. Start aborted {e}.")
            raise

        if any([str(exchange).endswith("paper_trade") for exchange in settings.required_exchanges]):
            self.notify("\nPaper Trading Active: All orders are simulated and no real orders are placed.")

        self.notify(f"\nStatus check complete. Strategy '{self.trading_core.strategy_name}' started successfully.")
        self._in_start_check = False

        # Patch MQTT loggers if MQTT is available
        if self._mqtt:
            self._mqtt.patch_loggers()
            self._mqtt.start_market_events_fw()

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
