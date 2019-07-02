#!/usr/bin/env python

import asyncio
from collections import (
    deque,
)
from os.path import (
    join,
    dirname
)
import logging
from eth_account.local import LocalAccount
import pandas as pd
import platform
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

import hummingbot.client.commands as commands
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.trade import Trade
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.application_warning import ApplicationWarning
from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket
from hummingbot.market.ddex.ddex_market import DDEXMarket
from hummingbot.market.market_base import MarketBase
from hummingbot.market.radar_relay.radar_relay_market import RadarRelayMarket
from hummingbot.market.bamboo_relay.bamboo_relay_market import BambooRelayMarket
from hummingbot.market.idex.idex_market import IDEXMarket
from hummingbot.model.sql_connection_manager import SQLConnectionManager

from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.client.ui.keybindings import load_key_bindings
from hummingbot.client.ui.parser import (
    load_parser,
    ThrowingArgumentParser
)
from hummingbot.client.ui.hummingbot_cli import HummingbotCLI
from hummingbot.client.ui.completer import load_completer
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
from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.client.config.config_helpers import (
    get_strategy_config_map,
    write_config_to_yml,
    load_required_configs,
    parse_cvar_value,
    copy_strategy_template,
    get_erc20_token_addresses,
)
from hummingbot.client.settings import (
    EXCHANGES,
)
from hummingbot.logger.report_aggregator import ReportAggregator
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.strategy.cross_exchange_market_making import (
    CrossExchangeMarketPair,
)
from hummingbot.strategy.pure_market_making import MarketInfo
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.core.utils.stop_loss_tracker import StopLossTracker
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.notifier.telegram_notifier import TelegramNotifier
from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
from hummingbot.client.liquidity_bounty.bounty_utils import LiquidityBounty
from hummingbot.market.markets_recorder import MarketsRecorder


s_logger = None

MARKET_CLASSES = {
    "bamboo_relay": BambooRelayMarket,
    "binance": BinanceMarket,
    "coinbase_pro": CoinbaseProMarket,
    "idex": IDEXMarket,
    "ddex": DDEXMarket,
    "radar_relay": RadarRelayMarket,
}


class HummingbotApplication(*commands):
    KILL_TIMEOUT = 5.0
    IDEX_KILL_TIMEOUT = 30.0
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
        self.strategy: Optional[StrategyBase] = None
        self.market_pair: Optional[CrossExchangeMarketPair] = None
        self.market_info: Optional[MarketInfo] = None
        self.market_symbol_pairs: List[MarketSymbolPair] = []
        self.clock: Optional[Clock] = None

        self.start_time: Optional[int] = None
        self.assets: Optional[Set[str]] = set()
        self.starting_balances = {}
        self.placeholder_mode = False
        self.log_queue_listener: Optional[logging.handlers.QueueListener] = None
        self.reporting_module: Optional[ReportAggregator] = None
        self.data_feed: Optional[DataFeedBase] = None
        self.stop_loss_tracker: Optional[StopLossTracker] = None
        self.notifiers: List[NotifierBase] = []
        self.liquidity_bounty: Optional[LiquidityBounty] = None
        self._initialize_liquidity_bounty()
        self._app_warnings: Deque[ApplicationWarning] = deque()
        self._trading_required: bool = True

        self.trade_fill_db: SQLConnectionManager = SQLConnectionManager.get_trade_fills_instance()
        self.markets_recorder: Optional[MarketsRecorder] = None

    def init_reporting_module(self):
        if not self.reporting_module:
            self.reporting_module = ReportAggregator(
                self,
                report_aggregation_interval=global_config_map["reporting_aggregation_interval"].value,
                log_report_interval=global_config_map["reporting_log_interval"].value)
        self.reporting_module.start()

    def _notify(self, msg: str):
        self.app.log(msg)
        for notifier in self.notifiers:
            notifier.send_msg(msg)

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
            self._notify("Invalid command: %s" % (str(e),))
        except ArgumentParserError as e:
            self._notify(str(e))
        except NotImplementedError:
            self._notify("Command not yet implemented. This feature is currently under development.")
        except Exception as e:
            self.logger().error(e, exc_info=True)

    async def _cancel_outstanding_orders(self) -> bool:
        on_chain_cancel_on_exit = global_config_map.get("on_chain_cancel_on_exit").value
        success = True
        kill_timeout: float = self.KILL_TIMEOUT
        self._notify("Cancelling outstanding orders...")

        for market_name, market in self.markets.items():
            if market_name == "idex":
                self._notify(f"IDEX cancellations may take up to {int(self.IDEX_KILL_TIMEOUT)} seconds...")
                kill_timeout = self.IDEX_KILL_TIMEOUT
            # By default, the bot does not cancel orders on exit on Radar Relay or Bamboo Relay,
            # since all open orders will expire in a short window
            if not on_chain_cancel_on_exit and (market_name == "radar_relay" or market_name == "bamboo_relay"):
                continue
            cancellation_results = await market.cancel_all(kill_timeout)
            uncancelled = list(filter(lambda cr: cr.success is False, cancellation_results))
            if len(uncancelled) > 0:
                success = False
                uncancelled_order_ids = list(map(lambda cr: cr.order_id, uncancelled))
                self._notify("\nFailed to cancel the following orders on %s:\n%s" % (
                    market_name,
                    '\n'.join(uncancelled_order_ids)
                ))
        if success:
            self._notify("All outstanding orders cancelled.")
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

    async def reset_config_loop(self, key: str = None):
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

    def config(self, key: str = None, key_list: Optional[List[str]] = None):
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

    async def _unlock_wallet(self):
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

    async def _import_or_create_strategy_config(self):
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

    async def config_single_variable(self, cvar: ConfigVar, is_single_key: bool = False) -> Any:
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

    async def _config_loop(self, keys: List[str] = []):
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

    @staticmethod
    def _initialize_market_assets(market_name: str, symbols: List[str]) -> List[Tuple[str, str]]:
        market: MarketBase = MARKET_CLASSES.get(market_name, MarketBase)
        market_symbols: List[Tuple[str, str]] = [market.split_symbol(symbol) for symbol in symbols]
        return market_symbols

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

        # aggregate symbols if there are duplicate markets
        market_symbols_map = {}
        for market_name, symbols in market_names:
            if market_name not in market_symbols_map:
                market_symbols_map[market_name] = []
            market_symbols_map[market_name] += symbols

        for market_name, symbols in market_symbols_map.items():
            if market_name == "ddex" and self.wallet:
                market = DDEXMarket(wallet=self.wallet,
                                    ethereum_rpc_url=ethereum_rpc_url,
                                    order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                                    symbols=symbols,
                                    trading_required=self._trading_required)

            elif market_name == "idex" and self.wallet:
                try:
                    market = IDEXMarket(wallet=self.wallet,
                                        ethereum_rpc_url=ethereum_rpc_url,
                                        order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                                        symbols=symbols,
                                        trading_required=self._trading_required)
                except Exception as e:
                    self.logger().error(str(e))

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
                                           ethereum_rpc_url=ethereum_rpc_url,
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

        self.markets_recorder = MarketsRecorder(
            self.trade_fill_db,
            list(self.markets.values()),
            in_memory_config_map.get("strategy_file_path").value,
            in_memory_config_map.get("strategy").value
        )
        self.markets_recorder.start()

    def _initialize_notifiers(self):
        if global_config_map.get("telegram_enabled").value:
            # TODO: refactor to use single instance
            if not any([isinstance(n, TelegramNotifier) for n in self.notifiers]):
                self.notifiers.append(TelegramNotifier(token=global_config_map["telegram_token"].value,
                                                       chat_id=global_config_map["telegram_chat_id"].value,
                                                       hb=self))
        for notifier in self.notifiers:
            notifier.start()

    def _initialize_liquidity_bounty(self):
        if liquidity_bounty_config_map.get("liquidity_bounty_enabled").value is not None and \
           liquidity_bounty_config_map.get("liquidity_bounty_client_id").value is not None:
            self.liquidity_bounty = LiquidityBounty.get_instance()
            self.liquidity_bounty.start()

    def get_balance(self, currency: str = "WETH", wallet: bool = False, exchange: str = None):
        if wallet:
            if self.wallet is None:
                self._notify('Wallet not available. Please configure your wallet (Enter "config wallet")')
            elif currency is None:
                self._notify(f"{self.get_wallet_balance()}")
            else:
                self._notify(self.wallet.get_balance(currency.upper()))
        elif exchange:
            if exchange in self.markets:
                if currency is None:
                    self._notify(f"{self.get_exchange_balance(exchange)}")
                else:
                    self._notify(self.markets[exchange].get_balance(currency.upper()))
            else:
                self._notify('The exchange you entered has not been initialized. '
                             'You may check your exchange balance after entering the "start" command.')
        else:
            self.help("get_balance")

    def list(self, obj: str):
        if obj == "wallets":
            wallets = list_wallets()
            if len(wallets) == 0:
                self._notify('Wallet not available. Please configure your wallet (Enter "config wallet")')
            else:
                self._notify('\n'.join(wallets))

        elif obj == "exchanges":
            if len(EXCHANGES) == 0:
                self._notify("No exchanges available")
            else:
                self._notify('\n'.join(EXCHANGES))

        elif obj == "configs":
            columns: List[str] = ["Key", "Current Value"]

            global_cvs: List[ConfigVar] = list(in_memory_config_map.values()) + list(global_config_map.values())
            global_data: List[List[str, Any]] = [
                [cv.key, len(str(cv.value)) * "*" if cv.is_secure else str(cv.value)]
                for cv in global_cvs]
            global_df: pd.DataFrame = pd.DataFrame(data=global_data, columns=columns)
            self._notify("\nglobal configs:")
            self._notify(str(global_df))

            strategy = in_memory_config_map.get("strategy").value
            if strategy:
                strategy_cvs: List[ConfigVar] = get_strategy_config_map(strategy).values()
                strategy_data: List[List[str, Any]] = [
                    [cv.key, len(str(cv.value)) * "*" if cv.is_secure else str(cv.value)]
                    for cv in strategy_cvs]
                strategy_df: pd.DataFrame = pd.DataFrame(data=strategy_data, columns=columns)

                self._notify(f"\n{strategy} strategy configs:")
                self._notify(str(strategy_df))

            self._notify("\n")

        elif obj == "trades":
            lines = []
            if self.strategy is None:
                self._notify("No strategy available, cannot show past trades.")
            else:
                if len(self.strategy.trades) > 0:
                    df = Trade.to_pandas(self.strategy.trades)
                    df_lines = str(df).split("\n")
                    lines.extend(["", "  Past trades:"] +
                                 ["    " + line for line in df_lines])
                else:
                    lines.extend(["  No past trades."])
            self._notify("\n".join(lines))
        else:
            self.help("list")

    def stop(self, skip_order_cancellation: bool = False):
        asyncio.ensure_future(self.stop_loop(skip_order_cancellation), loop=self.ev_loop)

    async def stop_loop(self, skip_order_cancellation: bool = False):
        self._notify("\nWinding down...")

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
        self.markets_recorder.stop()
        self.wallet = None
        self.strategy_task = None
        self.strategy = None
        self.market_pair = None
        self.clock = None
        self.markets_recorder = None

    def exit(self, force: bool = False):
        asyncio.ensure_future(self.exit_loop(force), loop=self.ev_loop)

    async def exit_loop(self, force: bool = False):
        if self.strategy_task is not None and not self.strategy_task.cancelled():
            self.strategy_task.cancel()
        if self.strategy:
            self.strategy.stop()
        if force is False and self._trading_required:
            success = await self._cancel_outstanding_orders()
            if not success:
                self._notify('Wind down process terminated: Failed to cancel all outstanding orders. '
                             '\nYou may need to manually cancel remaining orders by logging into your chosen exchanges'
                             '\n\nTo force exit the app, enter "exit -f"')
                return
            # Freeze screen 1 second for better UI
            await asyncio.sleep(1)
        ExchangeRateConversion.get_instance().stop()

        if force is False and self.liquidity_bounty is not None:
            self._notify("Winding down liquidity bounty submission...")
            await self.liquidity_bounty.stop_network()

        self._notify("Winding down notifiers...")
        for notifier in self.notifiers:
            notifier.stop()

        self.app.exit()

    async def export_private_key(self):
        if self.acct is None:
            self._notify("Your wallet is currently locked. Please enter \"config\""
                         " to unlock your wallet first")
        else:
            self.placeholder_mode = True
            self.app.toggle_hide_input()

            ans = await self.app.prompt("Are you sure you want to print your private key in plain text? (y/n) >>> ")

            if ans.lower() in {"y", "yes"}:
                self._notify("\nWarning: Never disclose this key. Anyone with your private keys can steal any assets "
                             "held in your account.\n")
                self._notify("Your private key:")
                self._notify(self.acct.privateKey.hex())

            self.app.change_prompt(prompt=">>> ")
            self.app.toggle_hide_input()
            self.placeholder_mode = False

    def export_trades(self, path: str = ""):
        if not path:
            fname = f"trades_{pd.Timestamp.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
            path = join(dirname(__file__), f"../../logs/{fname}")
        if self.strategy is None:
            self._notify("No strategy available, cannot export past trades.")

        else:
            if len(self.strategy.trades) > 0:
                try:
                    df: pd.DataFrame = Trade.to_pandas(self.strategy.trades)
                    df.to_csv(path, header=True)
                    self._notify(f"Successfully saved trades to {path}")
                except Exception as e:
                    self._notify(f"Error saving trades to {path}: {e}")
            else:
                self._notify("No past trades to export")


