#!/usr/bin/env python

import asyncio
from collections import (
    deque,
    OrderedDict
)
from os.path import (
    join,
    dirname
)
import logging
import argparse
from eth_account.local import LocalAccount
import pandas as pd
import platform
import re
from six import string_types
import time
from typing import (
    List,
    Dict,
    Optional,
    Tuple,
    Any,
    Set,
    Callable,
    Deque
)

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.application_warning import ApplicationWarning
from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket
from hummingbot.market.ddex.ddex_market import DDEXMarket
from hummingbot.market.market_base import MarketBase
from hummingbot.market.radar_relay.radar_relay_market import RadarRelayMarket
from hummingbot.market.bamboo_relay.bamboo_relay_market import BambooRelayMarket
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.trade import Trade

from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot import init_logging
from hummingbot.client.ui.keybindings import load_key_bindings
from hummingbot.client.ui.parser import (
    load_parser,
    ThrowingArgumentParser
)
from hummingbot.client.ui.hummingbot_cli import HummingbotCLI
from hummingbot.client.ui.completer import load_completer
from hummingbot.core.utils.symbol_fetcher import SymbolFetcher
from hummingbot.core.utils.symbol_splitter import SymbolSplitter
from hummingbot.core.utils.wallet_setup import (
    create_and_save_wallet,
    import_and_save_wallet,
    list_wallets,
    unlock_wallet
)
from hummingbot.client.errors import (
    InvalidCommandError,
    ArgumentParserError
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
    get_erc20_token_addresses,
)
from hummingbot.client.settings import EXCHANGES
from hummingbot.logger.report_aggregator import ReportAggregator
from hummingbot.strategy.cross_exchange_market_making import (
    CrossExchangeMarketMakingStrategy,
    CrossExchangeMarketPair,
)
from hummingbot.strategy.arbitrage import (
    ArbitrageStrategy,
    ArbitrageMarketPair
)
from hummingbot.strategy.pure_market_making import (
    PureMarketMakingStrategy,
    PureMarketPair
)

from hummingbot.strategy.discovery import (
    DiscoveryStrategy,
    DiscoveryMarketPair
)
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.core.utils.ethereum import check_web3
from hummingbot.core.utils.stop_loss_tracker import StopLossTracker
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.data_feed.coin_cap_data_feed import CoinCapDataFeed

s_logger = None


class HummingbotApplication:
    KILL_TIMEOUT = 5.0
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
        self.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self.parser: ThrowingArgumentParser = load_parser(self)
        self.app = HummingbotCLI(
            input_handler=self._handle_command,
            bindings=load_key_bindings(self),
            completer=load_completer(self))

        self.acct: Optional[LocalAccount] = None
        self.markets: Dict[str, MarketBase] = {}
        self.wallet: Optional[Web3Wallet] = None
        self.strategy_task: Optional[asyncio.Task] = None
        self.strategy: Optional[CrossExchangeMarketMakingStrategy] = None
        self.market_pair: Optional[CrossExchangeMarketPair] = None
        self.clock: Optional[Clock] = None

        self.assets: Optional[Set[str]] = set()
        self.starting_balances = {}
        self.placeholder_mode = False
        self.log_queue_listener: Optional[logging.handlers.QueueListener] = None
        self.reporting_module: Optional[ReportAggregator] = None
        self.data_feed: Optional[DataFeedBase] = None
        self.stop_loss_tracker: Optional[StopLossTracker] = None
        self._app_warnings: Deque[ApplicationWarning] = deque()
        self._trading_required: bool = True

    def init_reporting_module(self):
        if not self.reporting_module:
            self.reporting_module = ReportAggregator(
                self,
                report_aggregation_interval=global_config_map["reporting_aggregation_interval"].value,
                log_report_interval=global_config_map["reporting_log_interval"].value)
        self.reporting_module.start()

    def _handle_command(self, raw_command: str):
        raw_command = raw_command.lower().strip()
        try:
            if self.placeholder_mode:
                pass
            else:
                logging.getLogger("hummingbot.command_history").info(raw_command)
                args = self.parser.parse_args(args=raw_command.split())
                kwargs = vars(args)
                if not hasattr(args, "func"):
                    return
                f = args.func
                del kwargs['func']
                f(**kwargs)
        except InvalidCommandError as e:
            self.app.log("Invalid command: %s" % (str(e),))
        except ArgumentParserError as e:
            self.app.log(str(e))
        except NotImplementedError:
            self.app.log("Command not yet implemented. This feature is currently under development.")
        except Exception as e:
            self.logger().error(e, exc_info=True)

    async def _cancel_outstanding_orders(self) -> bool:
        on_chain_cancel_on_exit = global_config_map.get("on_chain_cancel_on_exit").value
        success = True
        self.app.log("Cancelling outstanding orders...")
        for market_name, market in self.markets.items():
            # By default, the bot does not cancel orders on exit on Radar Relay or Bamboo Relay, since all open orders will
            # expire in a short window
            if not on_chain_cancel_on_exit and (market_name == "radar_relay" or market_name == "bamboo_relay"):
                continue
            cancellation_results = await market.cancel_all(self.KILL_TIMEOUT)
            uncancelled = list(filter(lambda cr: cr.success is False, cancellation_results))
            if len(uncancelled) > 0:
                success = False
                uncancelled_order_ids = list(map(lambda cr: cr.order_id, uncancelled))
                self.app.log("\nFailed to cancel the following orders on %s:\n%s" % (
                    market_name,
                    '\n'.join(uncancelled_order_ids)
                ))
        if success:
            self.app.log("All outstanding orders cancelled.")
        return success

    async def run(self):
        await self.app.run()

    @property
    def config_complete(self):
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

    def get_wallet_balance(self) -> pd.DataFrame:
        return pd.DataFrame(data=list(self.wallet.get_all_balances().items()),
                            columns=["currency", "balance"]).set_index("currency")

    def get_exchange_balance(self, exchange_name: str) -> pd.DataFrame:
        market: MarketBase = self.markets[exchange_name]
        raw_balance: pd.DataFrame = pd.DataFrame(data=list(market.get_all_balances().items()),
                                                 columns=["currency", "balance"]).set_index("currency")
        return raw_balance[raw_balance.balance > 0]

    def config(self, key: str = None):
        self.app.clear_input()
        if key is not None and key not in load_required_configs().keys():
            self.app.log("Invalid config variable %s" % (key,))
            return
        if key is not None:
            keys = [key]
        else:
            keys = self._get_empty_configs()
        asyncio.ensure_future(self._config_loop(keys))

    def _expire_old_application_warnings(self):
        now: float = time.time()
        expiry_threshold: float = now - self.APP_WARNING_EXPIRY_DURATION
        while len(self._app_warnings) > 0 and self._app_warnings[0].timestamp < expiry_threshold:
            self._app_warnings.popleft()

    def add_application_warning(self, app_warning: ApplicationWarning):
        self._expire_old_application_warnings()
        self._app_warnings.append(app_warning)

    async def _create_or_import_wallet(self):
        choice = await self.app.prompt(prompt=global_config_map.get("wallet").prompt)
        if choice == "import":
            private_key = await self.app.prompt(prompt="Your wallet private key >>> ", is_password=True)
            password = await self.app.prompt(prompt="A password to protect your wallet key >>> ", is_password=True)

            try:
                self.acct = import_and_save_wallet(password, private_key)
                self.app.log("Wallet %s imported into hummingbot" % (self.acct.address,))
            except Exception as e:
                self.app.log(f"Failed to import wallet key: {e}")
                result = await self._create_or_import_wallet()
                return result
        elif choice == "create":
            password = await self.app.prompt(prompt="A password to protect your wallet key >>> ", is_password=True)
            self.acct = create_and_save_wallet(password)
            self.app.log("New wallet %s created" % (self.acct.address,))
        else:
            self.app.log('Invalid choice. Please enter "create" or "import".')
            result = await self._create_or_import_wallet()
            return result
        return self.acct.address

    async def _unlock_wallet(self):
        choice = await self.app.prompt(prompt="Would you like to unlock your previously saved wallet? (y/n) >>> ")
        if choice.lower() in {"y", "yes"}:
            wallets = list_wallets()
            self.app.log("Existing wallets:")
            self.list(obj="wallets")
            if len(wallets) == 1:
                public_key = wallets[0]
            else:
                public_key = await self.app.prompt(prompt="Which wallet would you like to import ? >>> ")
            password = await self.app.prompt(prompt="Enter your password >>> ", is_password=True)
            try:
                acct = unlock_wallet(public_key=public_key, password=password)
                self.app.log("Wallet %s unlocked" % (acct.address,))
                self.acct = acct
                return self.acct.address
            except Exception as e:
                self.app.log("Cannot unlock wallet. Please try again.")
                result = await self._unlock_wallet()
                return result
        else:
            value = await self._create_or_import_wallet()
            return value

    async def _import_or_create_strategy_config(self):
        current_strategy: str = in_memory_config_map.get("strategy").value
        strategy_file_path_cv: ConfigVar = in_memory_config_map.get("strategy_file_path")
        choice = await self.app.prompt(prompt="Import previous configs or create a new config file? "
                                              "(import/create) >>> ")
        if choice == "import":
            strategy_path = await self.app.prompt(strategy_file_path_cv.prompt)
            strategy_path = strategy_path
            self.app.log(f"Loading previously saved config file from {strategy_path}...")
        elif choice == "create":
            strategy_path = await copy_strategy_template(current_strategy)
            self.app.log(f"new config file at {strategy_path} created.")
        else:
            self.app.log('Invalid choice. Please enter "create" or "import".')
            strategy_path = await self._import_or_create_strategy_config()

        # Validate response
        if not strategy_file_path_cv.validate(strategy_path):
            self.app.log(f"Invalid path {strategy_path}. Please enter \"create\" or \"import\".")
            strategy_path = await self._import_or_create_strategy_config()
        return strategy_path

    async def _config_loop(self, keys: List[str] = []):
        self.app.log("Please follow the prompt to complete configurations: ")
        self.placeholder_mode = True
        self.app.toggle_hide_input()

        single_key = len(keys) == 1

        async def single_prompt(cvar: ConfigVar):
            if cvar.required or single_key:
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
                    self.app.log("%s is not a valid %s value" % (val, cvar.key))
                    val = await single_prompt(cvar)
            else:
                val = cvar.value
            if val is None or (isinstance(val, string_types) and len(val) == 0):
                val = cvar.default
            return val

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

                value = await single_prompt(cv)
                cv.value = parse_cvar_value(cv, value)
                if single_key:
                    self.app.log(f"\nNew config saved:\n{key}: {str(value)}")
            if not self.config_complete:
                await inner_loop(self._get_empty_configs())
        try:
            await inner_loop(keys)
            await write_config_to_yml()
            if not single_key:
                self.app.log("\nConfig process complete. Enter \"start\" to start market making.")
                self.app.set_text("start")
        except asyncio.TimeoutError:
            self.logger().error("Prompt timeout")
        except Exception as err:
            self.logger().error("Unknown error while writing config. %s" % (err,), exc_info=True)
        finally:
            self.app.toggle_hide_input()
            self.placeholder_mode = False
            self.app.change_prompt(prompt=">>> ")

    def _initialize_wallet(self, token_symbols: List[str]):
        ethereum_rpc_url = global_config_map.get("ethereum_rpc_url").value
        erc20_token_addresses = get_erc20_token_addresses(token_symbols)

        if self.acct is not None:
            self.wallet: Web3Wallet = Web3Wallet(private_key=self.acct.privateKey,
                                                 backend_urls=[ethereum_rpc_url],
                                                 erc20_token_addresses=erc20_token_addresses,
                                                 chain=EthereumChain.MAIN_NET)

    def _initialize_markets(self, market_names: List[Tuple[str, List[str]]]):
        ethereum_rpc_url = global_config_map.get("ethereum_rpc_url").value
        for market_name, symbols in market_names:
            if market_name == "ddex" and self.wallet:
                market = DDEXMarket(wallet=self.wallet,
                                    ethereum_rpc_url=ethereum_rpc_url,
                                    order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                                    symbols=symbols,
                                    trading_required=self._trading_required)

            elif market_name == "binance":
                binance_api_key = global_config_map.get("binance_api_key").value
                binance_api_secret = global_config_map.get("binance_api_secret").value
                market = BinanceMarket(ethereum_rpc_url=ethereum_rpc_url,
                                       binance_api_key=binance_api_key,
                                       binance_api_secret=binance_api_secret,
                                       order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                                       symbols=symbols,
                                       trading_required=self._trading_required)

            elif market_name == "radar_relay" and self.wallet:
                market = RadarRelayMarket(wallet=self.wallet,
                                          ethereum_rpc_url=ethereum_rpc_url,
                                          symbols=symbols,
                                          trading_required=self._trading_required)

            elif market_name == "bamboo_relay" and self.wallet:
                market = BambooRelayMarket(wallet=self.wallet,
                                          web3_url=ethereum_rpc_url,
                                          symbols=symbols)

            elif market_name == "coinbase_pro":
                coinbase_pro_api_key = global_config_map.get("coinbase_pro_api_key").value
                coinbase_pro_secret_key = global_config_map.get("coinbase_pro_secret_key").value
                coinbase_pro_passphrase = global_config_map.get("coinbase_pro_passphrase").value

                market = CoinbaseProMarket(ethereum_rpc_url=ethereum_rpc_url,
                                           coinbase_pro_api_key=coinbase_pro_api_key,
                                           coinbase_pro_secret_key=coinbase_pro_secret_key,
                                           coinbase_pro_passphrase=coinbase_pro_passphrase,
                                           symbols=symbols,
                                           trading_required=self._trading_required)

            else:
                raise ValueError(f"Market name {market_name} is invalid.")

            self.markets[market_name]: MarketBase = market

    def _format_application_warnings(self) -> str:
        lines: List[str] = []
        if len(self._app_warnings) < 1:
            return ""

        lines.append("\n  Warnings:")

        if len(self._app_warnings) < self.APP_WARNING_STATUS_LIMIT:
            for app_warning in reversed(self._app_warnings):
                lines.append(f"    * {pd.Timestamp(app_warning.timestamp, unit='s')} - "
                             f"({app_warning.logger_name}) - {app_warning.warning_msg}")
        else:
            module_based_warnings: OrderedDict = OrderedDict()
            for app_warning in reversed(self._app_warnings):
                logger_name: str = app_warning.logger_name
                if logger_name not in module_based_warnings:
                    module_based_warnings[logger_name] = deque([app_warning])
                else:
                    module_based_warnings[logger_name].append(app_warning)

            warning_lines: List[str] = []
            while len(warning_lines) < self.APP_WARNING_STATUS_LIMIT:
                logger_keys: List[str] = list(module_based_warnings.keys())
                for key in logger_keys:
                    warning_item: ApplicationWarning = module_based_warnings[key].popleft()
                    if len(module_based_warnings[key]) < 1:
                        del module_based_warnings[key]
                    warning_lines.append(f"    * {pd.Timestamp(warning_item.timestamp, unit='s')} - "
                                         f"({key}) - {warning_item.warning_msg}")
            lines.extend(warning_lines[:self.APP_WARNING_STATUS_LIMIT])

        return "\n".join(lines)

    def status(self) -> bool:
        # Preliminary checks.
        self.app.log("\n  Preliminary checks:")
        if self.config_complete:
            self.app.log("   - Config check: Config complete")
        else:
            self.app.log('   x Config check: Pending config. Please enter "config" before starting the bot.')
            return False

        eth_node_valid = check_web3(global_config_map.get("ethereum_rpc_url").value)
        if eth_node_valid:
            self.app.log("   - Node check: Ethereum node running and current")
        else:
            self.app.log('   x Node check: Bad ethereum rpc url. Your node may be syncing. '
                         'Please re-configure by entering "config ethereum_rpc_url"')
            return False

        if self.wallet is not None:
            if self.wallet.network_status is NetworkStatus.CONNECTED:
                if self._trading_required:
                    has_minimum_eth = self.wallet.get_balance("ETH") > 0.01
                    if has_minimum_eth:
                        self.app.log("   - ETH wallet check: Minimum ETH requirement satisfied")
                    else:
                        self.app.log("   x ETH wallet check: Not enough ETH in wallet. "
                                     "A small amount of Ether is required for sending transactions on "
                                     "Decentralized Exchanges")
            else:
                self.app.log("   x ETH wallet check: ETH wallet is not connected.")

        loading_markets: List[MarketBase] = []
        for market in self.markets.values():
            if not market.ready:
                loading_markets.append(market)

        if len(loading_markets) > 0:
            self.app.log(f"   x Market check:  Waiting for markets " +
                         ",".join([m.name.capitalize()  for m in loading_markets]) + f" to get ready for trading. \n"
                         f"                    Please keep the bot running and try to start again in a few minutes. \n")

            for market in loading_markets:
                market_status_df = pd.DataFrame(data=market.status_dict.items(), columns=["description", "status"])
                self.app.log(
                    f"   x {market.name.capitalize()} market status:\n" +
                    "\n".join(["     " + line for line in market_status_df.to_string(index=False,).split("\n")]) +
                    "\n"
                )
            return False

        elif not all([market.network_status is NetworkStatus.CONNECTED for market in self.markets.values()]):
            offline_markets: List[str] = [
                market_name
                for market_name, market
                in self.markets.items()
                if market.network_status is not NetworkStatus.CONNECTED
            ]
            for offline_market in offline_markets:
                self.app.log(f"   x Market check:  {offline_market} is currently offline.")

        # See if we can print out the strategy status.
        self.app.log("   - Market check: All markets ready")
        if self.strategy is None:
            self.app.log("   x initializing strategy.")
        else:
            self.app.log(self.strategy.format_status() + "\n")

        # Application warnings.
        self._expire_old_application_warnings()
        if len(self._app_warnings) > 0:
            self.app.log(self._format_application_warnings())

        return True

    def help(self, command):
        if command == 'all':
            self.app.log(self.parser.format_help())
        else:
            subparsers_actions = [
                action for action in self.parser._actions if isinstance(action, argparse._SubParsersAction)]

            for subparsers_action in subparsers_actions:
                subparser = subparsers_action.choices.get(command)
                self.app.log(subparser.format_help())

    def get_balance(self, currency: str = "WETH", wallet: bool = False, exchange: str = None):
        if wallet:
            if self.wallet is None:
                self.app.log('Wallet not available. Please configure your wallet (Enter "config wallet")')
            elif currency is None:
                self.app.log(f"{self.get_wallet_balance()}")
            else:
                self.app.log(self.wallet.get_balance(currency.upper()))
        elif exchange:
            if exchange in self.markets:
                if currency is None:
                    self.app.log(f"{self.get_exchange_balance(exchange)}")
                else:
                    self.app.log(self.markets[exchange].get_balance(currency.upper()))
            else:
                self.app.log('The exchange you entered has not been initialized. '
                             'You may check your exchange balance after entering the "start" command.')
        else:
            self.help("get_balance")

    def list(self, obj: str):
        if obj == "wallets":
            wallets = list_wallets()
            if len(wallets) == 0:
                self.app.log('Wallet not available. Please configure your wallet (Enter "config wallet")')
            else:
                self.app.log('\n'.join(wallets))

        elif obj == "exchanges":
            if len(EXCHANGES) == 0:
                self.app.log("No exchanges available")
            else:
                self.app.log('\n'.join(EXCHANGES))

        elif obj == "configs":
            columns: List[str] = ["Key", "Current Value"]

            global_cvs: List[ConfigVar] = list(in_memory_config_map.values()) + list(global_config_map.values())
            global_data: List[List[str, Any]] = [
                [cv.key, len(str(cv.value)) * "*" if cv.is_secure else str(cv.value)]
                for cv in global_cvs]
            global_df: pd.DataFrame = pd.DataFrame(data=global_data, columns=columns)
            self.app.log("\nglobal configs:")
            self.app.log(str(global_df))

            strategy = in_memory_config_map.get("strategy").value
            if strategy:
                strategy_cvs: List[ConfigVar] = get_strategy_config_map(strategy).values()
                strategy_data: List[List[str, Any]] = [
                    [cv.key, len(str(cv.value)) * "*" if cv.is_secure else str(cv.value)]
                    for cv in strategy_cvs]
                strategy_df: pd.DataFrame = pd.DataFrame(data=strategy_data, columns=columns)

                self.app.log(f"\n{strategy} strategy configs:")
                self.app.log(str(strategy_df))

            self.app.log("\n")

        elif obj == "trades":
            lines = []
            if self.strategy is None:
                self.app.log("No strategy available, cannot show past trades.")
            else:
                if len(self.strategy.trades) > 0:
                    df = Trade.to_pandas(self.strategy.trades)
                    df_lines = str(df).split("\n")
                    lines.extend(["", "  Past trades:"] +
                                 ["    " + line for line in df_lines])
                else:
                    lines.extend(["  No past trades."])
            self.app.log("\n".join(lines))
        else:
            self.help("list")

    def describe(self, wallet: bool = False, exchange: str = None):
        if wallet:
            if self.wallet is None:
                self.app.log('None available. Your wallet may not have been initialized. Enter "start" to initialize '
                             'your wallet.')
            else:
                self.app.log(self.wallet.address)
                self.app.log(f"{self.get_wallet_balance()}")
        elif exchange is not None:
            if exchange in self.markets:
                self.app.log(f"{self.get_exchange_balance(exchange)}")
            else:
                raise InvalidCommandError("The exchange you specified has not been initialized")
        else:
            self.help("describe")

    def start(self, log_level: Optional[str] = None):
        is_valid = self.status()
        if not is_valid:
            return

        if log_level is not None:
            init_logging("hummingbot_logs.yml", override_log_level=log_level.upper())

        # If macOS, disable App Nap.
        if platform.system() == "Darwin":
            import appnope
            appnope.nope()

        # TODO add option to select data feed
        self.data_feed: DataFeedBase = CoinCapDataFeed.get_instance()

        ExchangeRateConversion.get_instance().start()
        strategy_name = in_memory_config_map.get("strategy").value
        self.init_reporting_module()
        self.app.log(f"\n  Status check complete. Starting '{strategy_name}' strategy...")
        asyncio.ensure_future(self.start_market_making(strategy_name))

    async def _run_clock(self):
        with self.clock as clock:
            await clock.run()

    async def start_market_making(self, strategy_name: str):
        strategy_cm = get_strategy_config_map(strategy_name)
        if strategy_name == "cross_exchange_market_making":
            maker_market = strategy_cm.get("maker_market").value.lower()
            taker_market = strategy_cm.get("taker_market").value.lower()
            raw_maker_symbol = strategy_cm.get("maker_market_symbol").value.upper()
            raw_taker_symbol = strategy_cm.get("taker_market_symbol").value.upper()
            min_profitability = strategy_cm.get("min_profitability").value
            trade_size_override = strategy_cm.get("trade_size_override").value
            strategy_report_interval = global_config_map.get("strategy_report_interval").value
            limit_order_min_expiration = strategy_cm.get("limit_order_min_expiration").value
            cancel_order_threshold = strategy_cm.get("cancel_order_threshold").value
            active_order_canceling = strategy_cm.get("active_order_canceling").value
            top_depth_tolerance_rules = [(re.compile(re_str), value)
                                         for re_str, value
                                         in strategy_cm.get("top_depth_tolerance").value]
            top_depth_tolerance = 0.0

            for regex, tolerance_value in top_depth_tolerance_rules:
                if regex.match(raw_maker_symbol) is not None:
                    top_depth_tolerance = tolerance_value

            try:
                maker_assets: Tuple[str, str] = SymbolSplitter.split(maker_market, raw_maker_symbol)
                taker_assets: Tuple[str, str] = SymbolSplitter.split(taker_market, raw_taker_symbol)
            except ValueError as e:
                self.app.log(str(e))
                return

            market_names: List[Tuple[str, List[str]]] = [
                (maker_market, [raw_maker_symbol]),
                (taker_market, [raw_taker_symbol])
            ]
            self._initialize_wallet(token_symbols=list(set(maker_assets + taker_assets)))
            self._initialize_markets(market_names)
            self.assets = set(maker_assets + taker_assets)

            self.market_pair = CrossExchangeMarketPair(*([self.markets[maker_market], raw_maker_symbol] +
                                                         list(maker_assets) +
                                                         [self.markets[taker_market], raw_taker_symbol] +
                                                         list(taker_assets) + [top_depth_tolerance]))

            strategy_logging_options = (CrossExchangeMarketMakingStrategy.OPTION_LOG_CREATE_ORDER |
                                        CrossExchangeMarketMakingStrategy.OPTION_LOG_ADJUST_ORDER |
                                        CrossExchangeMarketMakingStrategy.OPTION_LOG_MAKER_ORDER_FILLED |
                                        CrossExchangeMarketMakingStrategy.OPTION_LOG_REMOVING_ORDER |
                                        CrossExchangeMarketMakingStrategy.OPTION_LOG_STATUS_REPORT |
                                        CrossExchangeMarketMakingStrategy.OPTION_LOG_MAKER_ORDER_HEDGED)

            self.strategy = CrossExchangeMarketMakingStrategy(market_pairs=[self.market_pair],
                                                              min_profitability=min_profitability,
                                                              status_report_interval=strategy_report_interval,
                                                              logging_options=strategy_logging_options,
                                                              trade_size_override=trade_size_override,
                                                              limit_order_min_expiration=limit_order_min_expiration,
                                                              cancel_order_threshold=cancel_order_threshold,
                                                              active_order_canceling=active_order_canceling)

        elif strategy_name == "arbitrage":
            primary_market = strategy_cm.get("primary_market").value.lower()
            secondary_market = strategy_cm.get("secondary_market").value.lower()
            raw_primary_symbol = strategy_cm.get("primary_market_symbol").value.upper()
            raw_secondary_symbol = strategy_cm.get("secondary_market_symbol").value.upper()
            min_profitability = strategy_cm.get("min_profitability").value
            try:
                primary_assets: Tuple[str, str] = SymbolSplitter.split(primary_market, raw_primary_symbol)
                secondary_assets: Tuple[str, str] = SymbolSplitter.split(secondary_market, raw_secondary_symbol)

            except ValueError as e:
                self.app.log(str(e))
                return

            market_names: List[Tuple[str, List[str]]] = [(primary_market, [raw_primary_symbol]),
                                                         (secondary_market, [raw_secondary_symbol])]
            self._initialize_wallet(token_symbols=list(set(primary_assets + secondary_assets)))
            self._initialize_markets(market_names)
            self.assets = set(primary_assets + secondary_assets)

            self.market_pair = ArbitrageMarketPair(*([self.markets[primary_market], raw_primary_symbol] +
                                                     list(primary_assets) +
                                                     [self.markets[secondary_market], raw_secondary_symbol] +
                                                     list(secondary_assets)))

            strategy_logging_options = ArbitrageStrategy.OPTION_LOG_ALL

            self.strategy = ArbitrageStrategy(market_pairs=[self.market_pair],
                                              min_profitability=min_profitability,
                                              logging_options=strategy_logging_options)

        elif strategy_name == "pure_market_making":
            order_size = strategy_cm.get("order_amount").value
            cancel_order_wait_time = strategy_cm.get("cancel_order_wait_time").value
            bid_place_threshold = strategy_cm.get("bid_place_threshold").value
            ask_place_threshold = strategy_cm.get("ask_place_threshold").value
            maker_market = strategy_cm.get("maker_market").value.lower()
            raw_maker_symbol = strategy_cm.get("maker_market_symbol").value.upper()
            try:
                primary_assets: Tuple[str, str] = SymbolSplitter.split(maker_market, raw_maker_symbol)

            except ValueError as e:
                self.app.log(str(e))
                return

            market_names: List[Tuple[str, List[str]]] = [(maker_market, [raw_maker_symbol])]

            self._initialize_wallet(token_symbols=list(set(primary_assets)))
            self._initialize_markets(market_names)
            self.assets = set(primary_assets)

            self.market_pair = PureMarketPair(*([self.markets[maker_market], raw_maker_symbol] +
                                                     list(primary_assets)))
            strategy_logging_options = PureMarketMakingStrategy.OPTION_LOG_ALL

            self.strategy = PureMarketMakingStrategy(market_pairs=[self.market_pair],
                                                     order_size = order_size,
                                                     bid_place_threshold = bid_place_threshold,
                                                     ask_place_threshold = ask_place_threshold,
                                                     cancel_order_wait_time = cancel_order_wait_time,
                                                     logging_options=strategy_logging_options)

        elif strategy_name == "discovery":
            try:
                market_1 = strategy_cm.get("primary_market").value.lower()
                market_2 = strategy_cm.get("secondary_market").value.lower()
                target_symbol_1 = list(strategy_cm.get("target_symbol_1").value)
                target_symbol_2 = list(strategy_cm.get("target_symbol_2").value)
                target_profitability = float(strategy_cm.get("target_profitability").value)
                target_amount = float(strategy_cm.get("target_amount").value)
                equivalent_token: List[List[str]] = list(strategy_cm.get("equivalent_tokens").value)

                if not target_symbol_2:
                    target_symbol_2 = SymbolFetcher.get_instance().symbols.get(market_2, [])
                if not target_symbol_1:
                    target_symbol_1 = SymbolFetcher.get_instance().symbols.get(market_1, [])

                market_names: List[Tuple[str, List[str]]] = [(market_1, target_symbol_1),
                                                             (market_2, target_symbol_2)]

                target_base_quote_1: List[Tuple[str, str]] = [
                    SymbolSplitter.split(market_1, symbol) for symbol in target_symbol_1
                ]
                target_base_quote_2: List[Tuple[str, str]] = [
                    SymbolSplitter.split(market_2, symbol) for symbol in target_symbol_2
                ]

                self._trading_required = False
                self._initialize_wallet(token_symbols=[])  # wallet required only for dex hard dependency
                self._initialize_markets(market_names)
                self.market_pair = DiscoveryMarketPair(
                    *([self.markets[market_1], self.markets[market_1].get_active_exchange_markets] +
                      [self.markets[market_2], self.markets[market_2].get_active_exchange_markets]))
                self.strategy = DiscoveryStrategy(market_pairs=[self.market_pair],
                                                  target_symbols=target_base_quote_1 + target_base_quote_2,
                                                  equivalent_token=equivalent_token,
                                                  target_profitability=target_profitability,
                                                  target_amount=target_amount
                                                  )
            except Exception as e:
                self.app.log(str(e))
                self.logger().error("Error initializing strategy.", exc_info=True)
        else:
            raise NotImplementedError

        try:
            self.clock = Clock(ClockMode.REALTIME)
            if self.wallet is not None:
                self.clock.add_iterator(self.wallet)
            for market in self.markets.values():
                if market is not None:
                    self.clock.add_iterator(market)
            if self.strategy:
                self.clock.add_iterator(self.strategy)
            self.strategy_task: asyncio.Task = asyncio.ensure_future(self._run_clock())
            self.app.log(f"\n  '{strategy_name}' strategy started.\n"
                         f"  You can use the `status` command to query the progress.")

            self.starting_balances = await self.wait_till_ready(self.balance_snapshot)
            self.stop_loss_tracker = StopLossTracker(self.data_feed,
                                                     list(self.assets),
                                                     list(self.markets.values()),
                                                     lambda *args, **kwargs: asyncio.ensure_future(
                                                         self.stop(*args, **kwargs)
                                                     ))
            await self.wait_till_ready(self.stop_loss_tracker.start)
        except Exception as e:
            self.logger().error(str(e), exc_info=True)

    async def stop(self, skip_order_cancellation: bool = False):
        self.app.log("\nWinding down...")

        # Restore App Nap on macOS.
        if platform.system() == "Darwin":
            import appnope
            appnope.nap()

        if self._trading_required and not skip_order_cancellation:
            # Remove the strategy from clock before cancelling orders, to
            # prevent race condition where the strategy tries to create more
            # orders during cancellation.
            self.clock.remove_iterator(self.strategy)
            success = await self._cancel_outstanding_orders()
            if success:
                # Only erase markets when cancellation has been successful
                self.markets = {}
        if self.reporting_module:
            self.reporting_module.stop()
        if self.strategy_task is not None and not self.strategy_task.cancelled():
            self.strategy_task.cancel()
        if self.strategy:
            self.strategy.stop()
        ExchangeRateConversion.get_instance().stop()
        self.stop_loss_tracker.stop()
        self.wallet = None
        self.strategy_task = None
        self.strategy = None
        self.market_pair = None
        self.clock = None

    async def exit(self, force: bool = False):
        if self.strategy_task is not None and not self.strategy_task.cancelled():
            self.strategy_task.cancel()
        if self.strategy:
            self.strategy.stop()
        if force is False and self._trading_required:
            success = await self._cancel_outstanding_orders()
            if not success:
                self.app.log('Wind down process terminated: Failed to cancel all outstanding orders. '
                             '\nYou may need to manually cancel remaining orders by logging into your chosen exchanges'
                             '\n\nTo force exit the app, enter "exit -f"')
                return
            # Freeze screen 1 second for better UI
            await asyncio.sleep(1)
        ExchangeRateConversion.get_instance().stop()
        self.app.exit()

    async def export_private_key(self):
        if self.acct is None:
            self.app.log("Your wallet is currently locked. Please enter \"config\""
                         " to unlock your wallet first")
        else:
            self.placeholder_mode = True
            self.app.toggle_hide_input()

            ans = await self.app.prompt("Are you sure you want to print your private key in plain text? (y/n) >>> ")

            if ans.lower() in {"y", "yes"}:
                self.app.log("\nWarning: Never disclose this key. Anyone with your private keys can steal any assets "
                             "held in your account.\n")
                self.app.log("Your private key:")
                self.app.log(self.acct.privateKey.hex())

            self.app.change_prompt(prompt=">>> ")
            self.app.toggle_hide_input()
            self.placeholder_mode = False

    def export_trades(self, path: str = ""):
        if not path:
            fname = f"trades_{pd.Timestamp.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
            path = join(dirname(__file__), f"../../logs/{fname}")

        if self.strategy is None:
            self.app.log("No strategy available, cannot export past trades.")

        else:
            if len(self.strategy.trades) > 0:
                try:
                    df: pd.DataFrame = Trade.to_pandas(self.strategy.trades)
                    df.to_csv(path, header=True)
                    self.app.log(f"Successfully saved trades to {path}")
                except Exception as e:
                    self.app.log(f"Error saving trades to {path}: {e}")

    def history(self):
        self.list("trades")
        self.compare_balance_snapshots()

    async def wait_till_ready(self, func: Callable, *args, **kwargs):
        while True:
            all_ready = all([market.ready for market in self.markets.values()])
            if not all_ready:
                await asyncio.sleep(0.5)
            else:
                return func(*args, **kwargs)

    def balance_snapshot(self) -> Dict[str, Dict[str, float]]:
        snapshot: Dict[str, Any] = {}
        for market_name in self.markets:
            balance_dict = self.markets[market_name].get_all_balances()
            for c in self.assets:
                if c not in snapshot:
                    snapshot[c] = {}
                if c in balance_dict:
                    snapshot[c][market_name] = balance_dict[c]
                else:
                    snapshot[c][market_name] = 0.0
        return snapshot

    def compare_balance_snapshots(self):
        if len(self.starting_balances) == 0:
            self.app.log("  Balance snapshots are not available before bot starts")
            return

        rows = []
        for market_name in self.markets:
            for asset in self.assets:
                starting_balance = self.starting_balances.get(asset).get(market_name)
                current_balance = self.balance_snapshot().get(asset).get(market_name)
                rows.append([market_name, asset, starting_balance, current_balance, current_balance - starting_balance])

        df = pd.DataFrame(rows, index=None, columns=["Market", "Asset", "Starting", "Current", "Delta"])
        lines = ["", "  Performance:"] + ["    " + line for line in str(df).split("\n")]
        self.app.log("\n".join(lines))
