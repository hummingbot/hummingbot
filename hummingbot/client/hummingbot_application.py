#!/usr/bin/env python

import asyncio
from collections import deque
import logging
import time
from eth_account.local import LocalAccount
from typing import (
    List,
    Dict,
    Optional,
    Tuple,
    Set,
    Deque
)

from hummingbot.client.command import __all__ as commands
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.application_warning import ApplicationWarning
from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.market.bittrex.bittrex_market import BittrexMarket
from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket
from hummingbot.market.ddex.ddex_market import DDEXMarket
from hummingbot.market.huobi.huobi_market import HuobiMarket
from hummingbot.market.market_base import MarketBase
from hummingbot.market.paper_trade import create_paper_trade_market
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
from hummingbot.client.errors import (
    InvalidCommandError,
    ArgumentParserError
)
from hummingbot.client.config.in_memory_config_map import in_memory_config_map
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.client.config.config_helpers import get_erc20_token_addresses
from hummingbot.logger.report_aggregator import ReportAggregator
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.strategy.cross_exchange_market_making import CrossExchangeMarketPair

from hummingbot.core.utils.kill_switch import KillSwitch
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.notifier.telegram_notifier import TelegramNotifier
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.client.liquidity_bounty.bounty_utils import LiquidityBounty
from hummingbot.market.markets_recorder import MarketsRecorder


s_logger = None

MARKET_CLASSES = {
    "bamboo_relay": BambooRelayMarket,
    "binance": BinanceMarket,
    "coinbase_pro": CoinbaseProMarket,
    "ddex": DDEXMarket,
    "huobi": HuobiMarket,
    "idex": IDEXMarket,
    "radar_relay": RadarRelayMarket,
    "bittrex": BittrexMarket
}


class HummingbotApplication(*commands):
    KILL_TIMEOUT = 10.0
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
        self.market_trading_pair_tuples: List[MarketTradingPairTuple] = []
        self.clock: Optional[Clock] = None

        self.init_time: int = int(time.time() * 1e3)
        self.start_time: Optional[int] = None
        self.assets: Optional[Set[str]] = set()
        self.starting_balances = {}
        self.placeholder_mode = False
        self.log_queue_listener: Optional[logging.handlers.QueueListener] = None
        self.reporting_module: Optional[ReportAggregator] = None
        self.data_feed: Optional[DataFeedBase] = None
        self.notifiers: List[NotifierBase] = []
        self.kill_switch: Optional[KillSwitch] = None
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
            notifier.add_msg_to_queue(msg)

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
        success = True
        try:
            on_chain_cancel_on_exit = global_config_map.get("on_chain_cancel_on_exit").value
            bamboo_relay_use_coordinator = global_config_map.get("bamboo_relay_use_coordinator").value
            kill_timeout: float = self.KILL_TIMEOUT
            self._notify("Cancelling outstanding orders...")

            for market_name, market in self.markets.items():
                if market_name == "idex":
                    self._notify(f"IDEX cancellations may take up to {int(self.IDEX_KILL_TIMEOUT)} seconds...")
                    kill_timeout = self.IDEX_KILL_TIMEOUT
                # By default, the bot does not cancel orders on exit on Radar Relay or Bamboo Relay,
                # since all open orders will expire in a short window
                if not on_chain_cancel_on_exit and (market_name == "radar_relay" or (market_name == "bamboo_relay" and not bamboo_relay_use_coordinator)):
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
        except Exception:
            self.logger().error(f"Error canceling outstanding orders.", exc_info=True)
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
            if global_config_map.get("paper_trade_enabled").value:
                self._notify(f"\nPaper trade is enabled for market {market_name}")
                try:
                    market = create_paper_trade_market(market_name, symbols)
                except Exception:
                    raise
                paper_trade_account_balance = global_config_map.get("paper_trade_account_balance").value
                for asset, balance in paper_trade_account_balance:
                    market.set_balance(asset, balance)

            elif market_name == "ddex" and self.wallet:
                market = DDEXMarket(wallet=self.wallet,
                                    ethereum_rpc_url=ethereum_rpc_url,
                                    order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                                    symbols=symbols,
                                    trading_required=self._trading_required)

            elif market_name == "idex" and self.wallet:
                idex_api_key: str = global_config_map.get("idex_api_key").value
                try:
                    market = IDEXMarket(idex_api_key=idex_api_key,
                                        wallet=self.wallet,
                                        ethereum_rpc_url=ethereum_rpc_url,
                                        order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                                        symbols=symbols,
                                        trading_required=self._trading_required)
                except Exception as e:
                    self.logger().error(str(e))

            elif market_name == "binance":
                binance_api_key = global_config_map.get("binance_api_key").value
                binance_api_secret = global_config_map.get("binance_api_secret").value
                market = BinanceMarket(binance_api_key,
                                       binance_api_secret,
                                       order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                                       symbols=symbols,
                                       trading_required=self._trading_required)

            elif market_name == "radar_relay" and self.wallet:
                market = RadarRelayMarket(wallet=self.wallet,
                                          ethereum_rpc_url=ethereum_rpc_url,
                                          symbols=symbols,
                                          trading_required=self._trading_required)

            elif market_name == "bamboo_relay" and self.wallet:
                use_coordinator = global_config_map.get("bamboo_relay_use_coordinator").value
                pre_emptive_soft_cancels = global_config_map.get("bamboo_relay_pre_emptive_soft_cancels").value
                market = BambooRelayMarket(wallet=self.wallet,
                                           ethereum_rpc_url=ethereum_rpc_url,
                                           symbols=symbols,
                                           use_coordinator=use_coordinator,
                                           pre_emptive_soft_cancels=pre_emptive_soft_cancels,
                                           trading_required=self._trading_required)

            elif market_name == "coinbase_pro":
                coinbase_pro_api_key = global_config_map.get("coinbase_pro_api_key").value
                coinbase_pro_secret_key = global_config_map.get("coinbase_pro_secret_key").value
                coinbase_pro_passphrase = global_config_map.get("coinbase_pro_passphrase").value

                market = CoinbaseProMarket(coinbase_pro_api_key,
                                           coinbase_pro_secret_key,
                                           coinbase_pro_passphrase,
                                           symbols=symbols,
                                           trading_required=self._trading_required)
            elif market_name == "huobi":
                huobi_api_key = global_config_map.get("huobi_api_key").value
                huobi_secret_key = global_config_map.get("huobi_secret_key").value
                market = HuobiMarket(huobi_api_key,
                                     huobi_secret_key,
                                     order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                                     symbols=symbols,
                                     trading_required=self._trading_required)
            elif market_name == "bittrex":
                bittrex_api_key = global_config_map.get("bittrex_api_key").value
                bittrex_secret_key = global_config_map.get("bittrex_secret_key").value
                market = BittrexMarket(bittrex_api_key,
                                       bittrex_secret_key,
                                       order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
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
