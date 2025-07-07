import asyncio
import logging
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Union

from hummingbot.client.command import __all__ as commands
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    get_strategy_config_map,
    load_client_config_map_from_file,
    load_ssl_config_map_from_file,
    save_to_yml,
)
from hummingbot.client.config.gateway_ssl_config_map import SSLConfigMap
from hummingbot.client.config.strategy_config_data_types import BaseStrategyConfigMap
from hummingbot.client.settings import CLIENT_CONFIG_PATH
from hummingbot.client.tab import __all__ as tab_classes
from hummingbot.client.tab.data_types import CommandTab
from hummingbot.client.ui.completer import load_completer
from hummingbot.client.ui.hummingbot_cli import HummingbotCLI
from hummingbot.client.ui.keybindings import load_key_bindings
from hummingbot.client.ui.parser import ThrowingArgumentParser, load_parser
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.gateway.gateway_status_monitor import GatewayStatusMonitor
from hummingbot.core.trading_core import TradingCore
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.exceptions import ArgumentParserError
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.application_warning import ApplicationWarning
from hummingbot.remote_iface.mqtt import MQTTGateway

s_logger = None


class HummingbotApplication(*commands):
    KILL_TIMEOUT = 20.0
    APP_WARNING_EXPIRY_DURATION = 3600.0
    APP_WARNING_STATUS_LIMIT = 6

    _main_app: Optional["HummingbotApplication"] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    @classmethod
    def main_application(cls, client_config_map: Optional[ClientConfigAdapter] = None, headless_mode: bool = False) -> "HummingbotApplication":
        if cls._main_app is None:
            cls._main_app = HummingbotApplication(client_config_map=client_config_map, headless_mode=headless_mode)
        return cls._main_app

    def __init__(self, client_config_map: Optional[ClientConfigAdapter] = None, headless_mode: bool = False):
        self.client_config_map: Union[ClientConfigMap, ClientConfigAdapter] = (  # type-hint enables IDE auto-complete
            client_config_map or load_client_config_map_from_file()
        )
        self.headless_mode = headless_mode
        self.ssl_config_map: SSLConfigMap = (  # type-hint enables IDE auto-complete
            load_ssl_config_map_from_file()
        )
        self.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        # Initialize core trading functionality
        self.trading_core = TradingCore(self.client_config_map)

        # Application-specific properties
        self.init_time: float = time.time()
        self.placeholder_mode = False
        self._app_warnings: Deque[ApplicationWarning] = deque()

        # MQTT management
        self._mqtt: Optional[MQTTGateway] = None

        # Script configuration support
        self.script_config: Optional[str] = None
        self._gateway_monitor = GatewayStatusMonitor(self)
        self._gateway_monitor.start()

        # Initialize UI components only if not in headless mode
        if not headless_mode:
            self._init_ui_components()
            TradingPairFetcher.get_instance(self.client_config_map)
        else:
            # In headless mode, we don't initialize UI components
            self.app = None
            self.parser = None

        # MQTT Bridge (always available in both modes)
        if self.client_config_map.mqtt_bridge.mqtt_autostart:
            self.mqtt_start()

    def _init_ui_components(self):
        """Initialize UI components (CLI, parser, etc.) for non-headless mode."""
        command_tabs = self.init_command_tabs()
        self.parser: ThrowingArgumentParser = load_parser(self, command_tabs)
        self.app = HummingbotCLI(
            self.client_config_map,
            input_handler=self._handle_command,
            bindings=load_key_bindings(self),
            completer=load_completer(self),
            command_tabs=command_tabs
        )

    @property
    def instance_id(self) -> str:
        return self.client_config_map.instance_id

    @property
    def fetch_pairs_from_all_exchanges(self) -> bool:
        return self.client_config_map.fetch_pairs_from_all_exchanges

    @property
    def gateway_config_keys(self) -> List[str]:
        return self._gateway_monitor.gateway_config_keys

    @property
    def strategy_file_name(self) -> str:
        return self.trading_core.strategy_file_name

    @strategy_file_name.setter
    def strategy_file_name(self, value: Optional[str]):
        self.trading_core.strategy_file_name = value

    @property
    def strategy_name(self) -> str:
        return self.trading_core.strategy_name

    @strategy_name.setter
    def strategy_name(self, value: Optional[str]):
        self.trading_core.strategy_name = value

    @property
    def markets(self) -> Dict[str, ExchangeBase]:
        return self.trading_core.markets

    @property
    def notifiers(self):
        return self.trading_core.notifiers

    @property
    def strategy_config_map(self):
        if self.trading_core.strategy_config_map is not None:
            return self.trading_core.strategy_config_map
        if self.trading_core.strategy_name is not None:
            return get_strategy_config_map(self.trading_core.strategy_name)
        return None

    @strategy_config_map.setter
    def strategy_config_map(self, config_map: BaseStrategyConfigMap):
        self.trading_core.strategy_config_map = config_map

    def notify(self, msg: str):
        # In headless mode, just log to console and notifiers
        if self.headless_mode:
            self.logger().info(msg)
        else:
            self.app.log(msg)
        for notifier in self.trading_core.notifiers:
            notifier.add_message_to_queue(msg)

    def _handle_command(self, raw_command: str):
        # unset to_stop_config flag it triggered before loading any command (UI mode only)
        if not self.headless_mode and hasattr(self, 'app') and self.app.to_stop_config:
            self.app.to_stop_config = False

        raw_command = raw_command.strip()
        # NOTE: Only done for config command
        if raw_command.startswith("config"):
            command_split = raw_command.split(maxsplit=2)
        else:
            command_split = raw_command.split()
        try:
            if self.placeholder_mode:
                pass
            elif len(command_split) == 0:
                pass
            else:
                # Check if help is requested, if yes, print & terminate
                if len(command_split) > 1 and any(arg in ["-h", "--help"] for arg in command_split[1:]):
                    self.help(raw_command)
                    return

                # regular command
                if self.headless_mode and not hasattr(self, 'parser'):
                    self.notify("Command parsing not available in headless mode")
                    return

                args = self.parser.parse_args(args=command_split)
                kwargs = vars(args)
                if not hasattr(args, "func"):
                    if not self.headless_mode:
                        self.app.handle_tab_command(self, command_split[0], kwargs)
                    else:
                        self.notify(f"Tab command '{command_split[0]}' not available in headless mode")
                else:
                    f = args.func
                    del kwargs["func"]
                    f(**kwargs)
        except ArgumentParserError as e:
            if not self.be_silly(raw_command):
                self.notify(str(e))
        except NotImplementedError:
            self.notify("Command not yet implemented. This feature is currently under development.")
        except Exception as e:
            self.logger().error(e, exc_info=True)

    async def run(self):
        """Run the application - either UI mode or headless mode."""
        if self.headless_mode:
            # Start MQTT market events forwarding if MQTT is available
            if self._mqtt is not None:
                self._mqtt.start_market_events_fw()
            await self.run_headless()
        else:
            await self.app.run()

    async def run_headless(self):
        """Run in headless mode - just keep alive for MQTT/strategy execution."""
        try:
            self.logger().info("Starting Hummingbot in headless mode...")

            # Validate MQTT is enabled for headless mode
            if not self.client_config_map.mqtt_bridge.mqtt_autostart:
                error_msg = (
                    "ERROR: MQTT must be enabled for headless mode!\n"
                    "Without MQTT, there would be no way to control the bot.\n"
                    "Please enable MQTT by setting 'mqtt_autostart: true' in your config file.\n"
                    "You can also start it manually with 'mqtt start' before switching to headless mode."
                )
                self.logger().error(error_msg)
                raise RuntimeError("MQTT is required for headless mode")

            self.logger().info("MQTT enabled - waiting for MQTT commands...")
            self.logger().info("Bot is ready to receive commands via MQTT")

            # Keep running until shutdown
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            self.logger().info("Shutdown requested...")
        except Exception as e:
            self.logger().error(f"Error in headless mode: {e}")
            raise
        finally:
            await self.trading_core.shutdown()

    def add_application_warning(self, app_warning: ApplicationWarning):
        self._expire_old_application_warnings()
        self._app_warnings.append(app_warning)

    def clear_application_warning(self):
        self._app_warnings.clear()

    def _initialize_notifiers(self):
        """Initialize notifiers by delegating to TradingCore."""
        for notifier in self.trading_core.notifiers:
            notifier.start()

    def init_command_tabs(self) -> Dict[str, CommandTab]:
        """
        Initiates and returns a CommandTab dictionary with mostly defaults and None values, These values will be
        populated later on by HummingbotCLI
        """
        command_tabs: Dict[str, CommandTab] = {}
        for tab_class in tab_classes:
            name = tab_class.get_command_name()
            command_tabs[name] = CommandTab(name, None, None, None, tab_class)
        return command_tabs

    def save_client_config(self):
        save_to_yml(CLIENT_CONFIG_PATH, self.client_config_map)
