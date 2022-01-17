#!/usr/bin/env python

import asyncio
import logging
import time
from collections import deque
from typing import List, Dict, Optional, Tuple, Deque

from hummingbot.client.command import __all__ as commands
from hummingbot.client.tab import __all__ as tab_classes
from hummingbot.core.clock import Clock
from hummingbot.exceptions import ArgumentParserError
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.application_warning import ApplicationWarning
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.connector.exchange.paper_trade import create_paper_trade_market
from hummingbot.client.ui.keybindings import load_key_bindings
from hummingbot.client.ui.parser import load_parser, ThrowingArgumentParser
from hummingbot.client.ui.hummingbot_cli import HummingbotCLI
from hummingbot.client.ui.completer import load_completer
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_helpers import (
    get_strategy_config_map,
    get_connector_class,
    get_eth_wallet_private_key,
)
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.strategy.cross_exchange_market_making import CrossExchangeMarketPair
from hummingbot.core.utils.kill_switch import KillSwitch
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.notifier.telegram_notifier import TelegramNotifier
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.client.config.security import Security
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.client.settings import AllConnectorSettings, ConnectorType
from hummingbot.client.tab.data_types import CommandTab

s_logger = None


class HummingbotApplication(*commands):
    KILL_TIMEOUT = 10.0
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
    def main_application(cls) -> "HummingbotApplication":
        if cls._main_app is None:
            cls._main_app = HummingbotApplication()
        return cls._main_app

    def __init__(self):
        # This is to start fetching trading pairs for auto-complete
        TradingPairFetcher.get_instance()
        self.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        command_tabs = self.init_command_tabs()
        self.parser: ThrowingArgumentParser = load_parser(self, command_tabs)

        self.app = HummingbotCLI(
            input_handler=self._handle_command,
            bindings=load_key_bindings(self),
            completer=load_completer(self),
            command_tabs=command_tabs
        )

        self.markets: Dict[str, ExchangeBase] = {}
        # strategy file name and name get assigned value after import or create command
        self._strategy_file_name: str = None
        self.strategy_name: str = None
        self.strategy_task: Optional[asyncio.Task] = None
        self.strategy: Optional[StrategyBase] = None
        self.market_pair: Optional[CrossExchangeMarketPair] = None
        self.market_trading_pair_tuples: List[MarketTradingPairTuple] = []
        self.clock: Optional[Clock] = None
        self.market_trading_pairs_map = {}
        self.token_list = {}

        self.init_time: float = time.time()
        self.start_time: Optional[int] = None
        self.placeholder_mode = False
        self.log_queue_listener: Optional[logging.handlers.QueueListener] = None
        self.data_feed: Optional[DataFeedBase] = None
        self.notifiers: List[NotifierBase] = []
        self.kill_switch: Optional[KillSwitch] = None
        self._app_warnings: Deque[ApplicationWarning] = deque()
        self._trading_required: bool = True
        self._last_started_strategy_file: Optional[str] = None

        self.trade_fill_db: Optional[SQLConnectionManager] = None
        self.markets_recorder: Optional[MarketsRecorder] = None
        self._script_iterator = None
        self._binance_connector = None

        # gateway variables
        self._shared_client = None

    @property
    def strategy_file_name(self) -> str:
        return self._strategy_file_name

    @strategy_file_name.setter
    def strategy_file_name(self, value: Optional[str]):
        self._strategy_file_name = value
        if value is not None:
            db_name = value.split(".")[0]
            self.trade_fill_db = SQLConnectionManager.get_trade_fills_instance(db_name)
        else:
            self.trade_fill_db = None

    @property
    def strategy_config_map(self):
        if self.strategy_name is not None:
            return get_strategy_config_map(self.strategy_name)
        return None

    def _notify(self, msg: str):
        self.app.log(msg)
        for notifier in self.notifiers:
            notifier.add_msg_to_queue(msg)

    def _handle_command(self, raw_command: str):
        # unset to_stop_config flag it triggered before loading any command
        if self.app.to_stop_config:
            self.app.to_stop_config = False

        raw_command = raw_command.lower().strip()
        command_split = raw_command.split()
        try:
            if self.placeholder_mode:
                pass
            else:
                # Check if help is requested, if yes, print & terminate
                if len(command_split) > 1 and any(arg in ["-h", "--help"] for arg in command_split[1:]):
                    self.help(command_split[0])
                    return

                shortcuts = global_config_map.get("command_shortcuts").value
                shortcut = None
                # see if we match against shortcut command
                if shortcuts is not None:
                    for s in shortcuts:
                        if command_split[0] == s['command']:
                            shortcut = s
                            break

                # perform shortcut expansion
                if shortcut is not None:
                    # check number of arguments
                    num_shortcut_args = len(shortcut['arguments'])
                    if len(command_split) == num_shortcut_args + 1:
                        # notify each expansion if there's more than 1
                        verbose = True if len(shortcut['output']) > 1 else False
                        # do argument replace and re-enter this function with the expanded command
                        for output_cmd in shortcut['output']:
                            final_cmd = output_cmd
                            for i in range(1, num_shortcut_args + 1):
                                final_cmd = final_cmd.replace(f'${i}', command_split[i])
                            if verbose is True:
                                self._notify(f'  >>> {final_cmd}')
                            self._handle_command(final_cmd)
                    else:
                        self._notify('Invalid number of arguments for shortcut')
                # regular command
                else:
                    args = self.parser.parse_args(args=command_split)
                    kwargs = vars(args)
                    if not hasattr(args, "func"):
                        self.app.handle_tab_command(self, command_split[0], kwargs)
                    else:
                        f = args.func
                        del kwargs["func"]
                        f(**kwargs)
        except ArgumentParserError as e:
            if not self.be_silly(raw_command):
                self._notify(str(e))
        except NotImplementedError:
            self._notify("Command not yet implemented. This feature is currently under development.")
        except Exception as e:
            self.logger().error(e, exc_info=True)

    async def _cancel_outstanding_orders(self) -> bool:
        success = True
        try:
            kill_timeout: float = self.KILL_TIMEOUT
            self._notify("Cancelling outstanding orders...")

            for market_name, market in self.markets.items():
                cancellation_results = await market.cancel_all(kill_timeout)
                uncancelled = list(filter(lambda cr: cr.success is False, cancellation_results))
                if len(uncancelled) > 0:
                    success = False
                    uncancelled_order_ids = list(map(lambda cr: cr.order_id, uncancelled))
                    self._notify("\nFailed to cancel the following orders on %s:\n%s" % (
                        market_name,
                        '\n'.join(uncancelled_order_ids)
                    ))
        except Exception:
            self.logger().error("Error canceling outstanding orders.", exc_info=True)
            success = False

        if success:
            self._notify("All outstanding orders cancelled.")
        return success

    async def run(self):
        await self.app.run()

    def add_application_warning(self, app_warning: ApplicationWarning):
        self._expire_old_application_warnings()
        self._app_warnings.append(app_warning)

    def clear_application_warning(self):
        self._app_warnings.clear()

    @staticmethod
    def _initialize_market_assets(market_name: str, trading_pairs: List[str]) -> List[Tuple[str, str]]:
        market_trading_pairs: List[Tuple[str, str]] = [(trading_pair.split('-')) for trading_pair in trading_pairs]
        return market_trading_pairs

    def _initialize_markets(self, market_names: List[Tuple[str, List[str]]]):
        # aggregate trading_pairs if there are duplicate markets

        for market_name, trading_pairs in market_names:
            if market_name not in self.market_trading_pairs_map:
                self.market_trading_pairs_map[market_name] = []
            for hb_trading_pair in trading_pairs:
                self.market_trading_pairs_map[market_name].append(hb_trading_pair)

        for connector_name, trading_pairs in self.market_trading_pairs_map.items():
            conn_setting = AllConnectorSettings.get_connector_settings()[connector_name]

            if connector_name.endswith("paper_trade") and conn_setting.type == ConnectorType.Exchange:
                connector = create_paper_trade_market(conn_setting.parent_name, trading_pairs)
                paper_trade_account_balance = global_config_map.get("paper_trade_account_balance").value
                for asset, balance in paper_trade_account_balance.items():
                    connector.set_balance(asset, balance)
            else:
                Security.update_config_map(global_config_map)
                keys = {key: config.value for key, config in global_config_map.items()
                        if key in conn_setting.config_keys}
                init_params = conn_setting.conn_init_parameters(keys)
                init_params.update(trading_pairs=trading_pairs, trading_required=self._trading_required)
                if conn_setting.use_ethereum_wallet:
                    ethereum_rpc_url = global_config_map.get("ethereum_rpc_url").value
                    # Todo: Hard coded this execption for now until we figure out how to handle all ethereum connectors.
                    if connector_name in ["balancer", "uniswap", "uniswap_v3", "perpetual_finance"]:
                        private_key = get_eth_wallet_private_key()
                        init_params.update(wallet_private_key=private_key, ethereum_rpc_url=ethereum_rpc_url)
                connector_class = get_connector_class(connector_name)
                connector = connector_class(**init_params)
            self.markets[connector_name] = connector

        self.markets_recorder = MarketsRecorder(
            self.trade_fill_db,
            list(self.markets.values()),
            self.strategy_file_name,
            self.strategy_name,
        )
        self.markets_recorder.start()

    def _initialize_notifiers(self):
        if global_config_map.get("telegram_enabled").value:
            # TODO: refactor to use single instance
            if not any([isinstance(n, TelegramNotifier) for n in self.notifiers]):
                self.notifiers.append(
                    TelegramNotifier(
                        token=global_config_map["telegram_token"].value,
                        chat_id=global_config_map["telegram_chat_id"].value,
                        hb=self,
                    )
                )
        for notifier in self.notifiers:
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
