import aiohttp
import asyncio
from async_timeout import timeout
from collections import (
    deque,
    OrderedDict
)
import copy
import logging
import math
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple
)
from decimal import Decimal
from libc.stdint cimport int64_t
from web3 import Web3
from zero_ex.order_utils import (
    generate_order_hash_hex,
    jsdict_order_to_struct,
    Order as ZeroExOrder
)

from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderExpiredEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    MarketOrderFailureEvent,
    TradeType,
    TradeFee
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bamboo_relay.bamboo_relay_api_order_book_data_source import BambooRelayAPIOrderBookDataSource
from hummingbot.market.bamboo_relay.bamboo_relay_in_flight_order cimport BambooRelayInFlightOrder
from hummingbot.market.bamboo_relay.bamboo_relay_order_book_tracker import BambooRelayOrderBookTracker
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import (
    MarketBase,
    OrderType,
    NaN,
    s_decimal_NaN)
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.wallet.ethereum.zero_ex.zero_ex_custom_utils import fix_signature
from hummingbot.wallet.ethereum.zero_ex.zero_ex_exchange import ZeroExExchange
from hummingbot.wallet.ethereum.zero_ex.zero_ex_coordinator import ZeroExCoordinator

brm_logger = None
s_decimal_0 = Decimal(0)

ZERO_EX_MAINNET_ERC20_PROXY = "0x95e6f48254609a6ee006f7d493c8e5fb97094cef"
ZERO_EX_MAINNET_EXCHANGE_ADDRESS = "0x080bf510fcbf18b91105470639e9561022937712"
ZERO_EX_MAINNET_COORDINATOR_ADDRESS = "0xa14857e8930acd9a882d33ec20559beb5479c8a6"
ZERO_EX_MAINNET_COORDINATOR_REGISTRY_ADDRESS = "0x45797531b873fd5e519477a070a955764c1a5b07"

ZERO_EX_ROPSTEN_ERC20_PROXY = "0xb1408f4c245a23c31b98d2c626777d4c0d766caa"
ZERO_EX_ROPSTEN_EXCHANGE_ADDRESS = "0xbff9493f92a3df4b0429b6d00743b3cfb4c85831"
ZERO_EX_ROPSTEN_COORDINATOR_ADDRESS = "0x2ba02e03ee0029311e0f43715307870a3e701b53"
ZERO_EX_ROPSTEN_COORDINATOR_REGISTRY_ADDRESS = "0x403cc23e88c17c4652fb904784d1af640a6722d9"

ZERO_EX_RINKEBY_ERC20_PROXY = "0x2f5ae4f6106e89b4147651688a92256885c5f410"
ZERO_EX_RINKEBY_EXCHANGE_ADDRESS = "0xbff9493f92a3df4b0429b6d00743b3cfb4c85831"
ZERO_EX_RINKEBY_COORDINATOR_ADDRESS = "0x2ba02e03ee0029311e0f43715307870a3e701b53"
ZERO_EX_RINKEBY_COORDINATOR_REGISTRY_ADDRESS = "0x1084b6a398e47907bae43fec3ff4b677db6e4fee"

ZERO_EX_KOVAN_ERC20_PROXY = "0xf1ec01d6236d3cd881a0bf0130ea25fe4234003e"
ZERO_EX_KOVAN_EXCHANGE_ADDRESS = "0x30589010550762d2f0d06f650d8e8b6ade6dbf4b"
ZERO_EX_KOVAN_COORDINATOR_ADDRESS = "0x2ba02e03ee0029311e0f43715307870a3e701b53"
ZERO_EX_KOVAN_COORDINATOR_REGISTRY_ADDRESS = "0x09fb99968c016a3ff537bf58fb3d9fe55a7975d5"

BAMBOO_RELAY_REST_ENDPOINT = "https://rest.bamboorelay.com/"


cdef class BambooRelayTransactionTracker(TransactionTracker):
    cdef:
        BambooRelayMarket _owner

    def __init__(self, owner: BambooRelayMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class BambooRelayMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value
    MARKET_ORDER_EXPIRED_EVENT_TAG = MarketEvent.OrderExpired.value

    API_CALL_TIMEOUT = 10.0
    CANCEL_EXPIRY_TIME = 60.0
    ORDER_EXPIRY_TIME = 60.0 * 15
    PRE_EMPTIVE_SOFT_CANCEL_TIME = 30.0
    ORDER_CREATION_BACKOFF_TIME = 3
    UPDATE_RULES_INTERVAL = 60.0
    UPDATE_OPEN_LIMIT_ORDERS_INTERVAL = 10.0
    UPDATE_MARKET_ORDERS_INTERVAL = 10.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global brm_logger
        if brm_logger is None:
            brm_logger = logging.getLogger(__name__)
        return brm_logger

    def __init__(self,
                 wallet: Web3Wallet,
                 ethereum_rpc_url: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None,
                 use_coordinator: Optional[bool] = True,
                 pre_emptive_soft_cancels: Optional[bool] = True,
                 trading_required: bool = True):
        cdef:
            str coordinator_address
            str coordinator_registry_address
        super().__init__()
        self._trading_required = trading_required
        self._order_book_tracker = BambooRelayOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                               symbols=symbols,
                                                               chain=wallet.chain)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_failed_limit_order_timestamp = 0
        self._last_update_limit_order_timestamp = 0
        self._last_update_market_order_timestamp = 0
        self._last_update_trading_rules_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_limit_orders = {}  # limit orders are off chain
        self._in_flight_market_orders = {}  # market orders are on chain
        self._in_flight_pending_limit_orders = OrderedDict()  # in the case that an order needs to be cancelled before its been accepted
        self._in_flight_cancels = OrderedDict()
        self._in_flight_pending_cancels = OrderedDict()
        self._order_expiry_queue = deque()
        self._tx_tracker = BambooRelayTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        self._provider = Web3.HTTPProvider(ethereum_rpc_url)
        self._withdraw_rules = {}
        self._trading_rules = {}
        self._pending_approval_tx_hashes = set()
        self._status_polling_task = None
        self._order_tracker_task = None
        self._approval_tx_polling_task = None
        self._wallet = wallet
        self._use_coordinator = use_coordinator
        self._pre_emptive_soft_cancels = pre_emptive_soft_cancels
        self._latest_salt = -1
        if wallet.chain is EthereumChain.MAIN_NET:
            self._api_prefix = "main/0x"
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_EXCHANGE_ADDRESS)
            coordinator_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_ERC20_PROXY)
        elif wallet.chain is EthereumChain.ROPSTEN:
            self._api_prefix = "ropsten/0x"
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_EXCHANGE_ADDRESS)
            coordinator_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_ERC20_PROXY)
        elif wallet.chain is EthereumChain.RINKEBY:
            self._api_prefix = "rinkeby/0x"
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_EXCHANGE_ADDRESS)
            coordinator_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_ERC20_PROXY)
        elif wallet.chain is EthereumChain.KOVAN:
            self._api_prefix = "kovan/0x"
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_KOVAN_EXCHANGE_ADDRESS)
            coordinator_address = Web3.toChecksumAddress(ZERO_EX_KOVAN_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_KOVAN_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_KOVAN_ERC20_PROXY)
        self._exchange = ZeroExExchange(self._w3, self._exchange_address, wallet)
        self._coordinator = ZeroExCoordinator(self._provider,
                                              self._w3,
                                              self._exchange_address,
                                              coordinator_address,
                                              coordinator_registry_address,
                                              wallet)

    @property
    def name(self) -> str:
        return "bamboo_relay"

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": len(self._order_book_tracker.order_books) > 0,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True,
            "token_approval": len(self._pending_approval_tx_hashes) == 0 if self._trading_required else True
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def wallet(self) -> Web3Wallet:
        return self._wallet

    @property
    def use_coordinator(self) -> bool:
        return self._use_coordinator

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_limit_orders(self) -> Dict[str, BambooRelayInFlightOrder]:
        return self._in_flight_limit_orders

    @property
    def in_flight_market_orders(self) -> Dict[str, BambooRelayInFlightOrder]:
        return self._in_flight_market_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            list retval = []
            BambooRelayInFlightOrder typed_in_flight_order
            str base_currency
            str quote_currency
            set expiring_order_ids = set([order_id for _, order_id in self._order_expiry_queue])

        for in_flight_order in self._in_flight_limit_orders.values():
            typed_in_flight_order = in_flight_order
            if typed_in_flight_order.order_type is not OrderType.LIMIT:
                continue
            if typed_in_flight_order.client_order_id in expiring_order_ids:
                continue
            retval.append(typed_in_flight_order.to_limit_order())
        return retval

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {
            "market_orders": {
                key: value.to_json()
                for key, value in self._in_flight_market_orders.items()
            },
            "limit_orders": {
                key: value.to_json()
                for key, value in self._in_flight_limit_orders.items()
            }
        }

    def reset_state(self):
        self._in_flight_market_orders = {}
        self._in_flight_limit_orders = {}
        self._in_flight_pending_limit_orders = OrderedDict()
        self._in_flight_cancels = OrderedDict()
        self._in_flight_pending_cancels = OrderedDict()
        self._order_expiry_queue = deque()

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        # ignore saved orders that may not reflect current version schema
        try:
            self._in_flight_market_orders.update({
                key: BambooRelayInFlightOrder.from_json(value)
                for key, value in saved_states["market_orders"].items()
            })
            self._in_flight_limit_orders.update({
                key: BambooRelayInFlightOrder.from_json(value)
                for key, value in saved_states["limit_orders"].items()
            })
        except Exception:
            self.logger().error(f"Error restoring tracking states.", exc_info=True)

    async def get_active_exchange_markets(self):
        return await BambooRelayAPIOrderBookDataSource.get_active_exchange_markets(self._api_prefix)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                self._update_balances()
                await safe_gather(
                    self._update_trading_rules(),
                    self._update_limit_order_status(),
                    self._update_market_order_status()
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg="Failed to fetch account updates on Bamboo Relay. Check network connection."
                )
                await asyncio.sleep(0.5)

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object trade_type,
                          object amount,
                          object price):
        cdef:
            int gas_estimate = 130000  # approximate gas used for 0x market orders
            double transaction_cost_eth

        # there are no fees for makers on Bamboo Relay
        if order_type is OrderType.LIMIT:
            return TradeFee(percent=Decimal(0.0))
        # only fee for takers is gas cost of transaction
        transaction_cost_eth = self._wallet.gas_price * gas_estimate / 1e18
        return TradeFee(percent=Decimal(0.0), flat_fees=[("ETH", transaction_cost_eth)])

    def _update_balances(self):
        self._account_balances = self.wallet.get_all_balances()

    async def list_market(self) -> Dict[str, Any]:
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/markets?perPage=1000&include=base"
        return await self._api_request(http_method="get", url=url, headers={"User-Agent": "hummingbot"})

    async def _update_trading_rules(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_trading_rules_timestamp > self.UPDATE_RULES_INTERVAL or len(self._trading_rules) < 1:
            markets = await self.list_market()
            trading_rules_list = self._format_trading_rules(markets)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule
            self._last_update_trading_rules_timestamp = current_timestamp

    def _format_trading_rules(self, markets: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list retval = []
        for market in markets:
            try:
                symbol = market["id"]
                retval.append(TradingRule(symbol,
                                          min_order_size=Decimal(market["minOrderSize"]),
                                          max_order_size=Decimal(market["maxOrderSize"]),
                                          max_price_significant_digits=Decimal(market['quoteIncrement']),
                                          min_price_increment=Decimal(f"1e-{market['quoteTokenDecimals']}"),
                                          min_base_amount_increment=Decimal(f"1e-{market['baseTokenDecimals']}")))
            except Exception:
                self.logger().error(f"Error parsing the symbol {symbol}. Skipping.", exc_info=True)
        return retval

    async def get_account_orders(self) -> List[Dict[str, Any]]:
        list_account_orders_url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/accounts/{self._wallet.address}/orders"
        return await self._api_request(http_method="get", url=list_account_orders_url,
                                       headers={"User-Agent": "hummingbot"})

    async def get_order(self, order_hash: str) -> Dict[str, Any]:
        order_url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/orders/{order_hash}"
        return await self._api_request("get", url=order_url, headers={"User-Agent": "hummingbot"})

    async def _get_order_updates(self, tracked_limit_orders: List[BambooRelayInFlightOrder]) -> List[Dict[str, Any]]:
        account_orders_list = await self.get_account_orders()
        account_orders_map = {}
        for account_order in account_orders_list:
            account_orders_map[account_order["orderHash"]] = account_order

        order_updates = []
        tasks = []
        tasks_index = []

        for i, tracked_order in enumerate(tracked_limit_orders):
            order_hash = tracked_order.exchange_order_id
            order_update = account_orders_map.get(order_hash, None)
            if order_update is None:
                tasks.append(self.get_order(order_hash))
                tasks_index.append(i)
            order_updates.append(order_update)

        res_order_updates = await safe_gather(*tasks, return_exceptions=True)

        for i, ou in enumerate(res_order_updates):
            order_updates[tasks_index[i]] = ou

        return order_updates

    async def _update_limit_order_status(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_limit_order_timestamp <= self.UPDATE_OPEN_LIMIT_ORDERS_INTERVAL:
            return

        if len(self._in_flight_limit_orders) > 0:
            tracked_limit_orders = list(self._in_flight_limit_orders.values())
            order_updates = await self._get_order_updates(tracked_limit_orders)
            for order_update, tracked_limit_order in zip(order_updates, tracked_limit_orders):
                if isinstance(order_update, Exception):
                    self.logger().network(
                        f"Error fetching status update for the order "
                        f"{tracked_limit_order.client_order_id}: {order_update}.",
                        app_warning_msg=f"Failed to fetch status update for the order "
                                        f"{tracked_limit_order.client_order_id}. "
                                        f"Check Ethereum wallet and network connection."
                    )
                    continue
                previous_is_done = tracked_limit_order.is_done
                previous_is_cancelled = tracked_limit_order.is_cancelled
                previous_is_failure = tracked_limit_order.is_failure
                previous_is_expired = tracked_limit_order.is_expired
                order_state = order_update["state"]
                order_remaining_base_token_amount = Decimal(order_update["remainingBaseTokenAmount"])
                order_remaining_quote_token_amount = Decimal(order_update["remainingQuoteTokenAmount"])
                order_executed_amount_base = Decimal(tracked_limit_order.available_amount_base) - order_remaining_base_token_amount
                total_executed_amount_base = Decimal(tracked_limit_order.amount) - order_remaining_base_token_amount

                tracked_limit_order.last_state = order_state
                tracked_limit_order.executed_amount_base = total_executed_amount_base
                tracked_limit_order.available_amount_base = order_remaining_base_token_amount
                tracked_limit_order.executed_amount_quote = order_remaining_quote_token_amount
                if order_executed_amount_base > 0:
                    self.logger().info(f"Filled {order_executed_amount_base} out of {tracked_limit_order.amount} of the "
                                       f"limit order {tracked_limit_order.client_order_id}.")
                    self.c_trigger_event(
                        self.MARKET_ORDER_FILLED_EVENT_TAG,
                        OrderFilledEvent(
                            self._current_timestamp,
                            tracked_limit_order.client_order_id,
                            tracked_limit_order.symbol,
                            tracked_limit_order.trade_type,
                            OrderType.LIMIT,
                            tracked_limit_order.price,
                            order_executed_amount_base,
                            TradeFee(0.0)  # no fee for limit order fills
                        )
                    )

                # do not retrigger order events if order was already in that state previously
                if not previous_is_cancelled and tracked_limit_order.is_cancelled:
                    if (self._in_flight_cancels.get(tracked_limit_order.client_order_id, 0) >
                            self._current_timestamp - self.CANCEL_EXPIRY_TIME):
                        # This cancel was originated from this connector, and the cancel event should have been
                        # emitted in the cancel_order() call already.
                        del self._in_flight_cancels[tracked_limit_order.client_order_id]
                    else:
                        self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has cancelled according "
                                           f"to order status API.")
                        self.c_expire_order(tracked_limit_order.client_order_id)
                        self.c_trigger_event(
                            self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                            OrderCancelledEvent(self._current_timestamp, tracked_limit_order.client_order_id)
                        )
                elif not previous_is_expired and tracked_limit_order.is_expired:
                    self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has expired according "
                                       f"to order status API.")
                    self.c_expire_order(tracked_limit_order.client_order_id)
                    self.c_trigger_event(
                        self.MARKET_ORDER_EXPIRED_EVENT_TAG,
                        OrderExpiredEvent(self._current_timestamp, tracked_limit_order.client_order_id)
                    )
                elif not previous_is_failure and tracked_limit_order.is_failure:
                    self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has failed "
                                       f"according to order status API.")
                    self.c_expire_order(tracked_limit_order.client_order_id)
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(self._current_timestamp,
                                                tracked_limit_order.client_order_id,
                                                OrderType.LIMIT)
                    )
                elif not previous_is_done and tracked_limit_order.is_done:
                    self.c_expire_order(tracked_limit_order.client_order_id)
                    if tracked_limit_order.trade_type is TradeType.BUY:
                        self.logger().info(f"The limit buy order {tracked_limit_order.client_order_id}"
                                           f"has completed according to order status API.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_limit_order.client_order_id,
                                                                    tracked_limit_order.base_asset,
                                                                    tracked_limit_order.quote_asset,
                                                                    tracked_limit_order.quote_asset,
                                                                    tracked_limit_order.executed_amount_base,
                                                                    tracked_limit_order.executed_amount_quote,
                                                                    tracked_limit_order.gas_fee_amount,
                                                                    OrderType.LIMIT))
                    else:
                        self.logger().info(f"The limit sell order {tracked_limit_order.client_order_id}"
                                           f"has completed according to order status API.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_limit_order.client_order_id,
                                                                     tracked_limit_order.base_asset,
                                                                     tracked_limit_order.quote_asset,
                                                                     tracked_limit_order.quote_asset,
                                                                     tracked_limit_order.executed_amount_base,
                                                                     tracked_limit_order.executed_amount_quote,
                                                                     tracked_limit_order.gas_fee_amount,
                                                                     OrderType.LIMIT))
                elif self._pre_emptive_soft_cancels and (
                        tracked_limit_order.is_coordinated and
                        not tracked_limit_order.is_cancelled and
                        not tracked_limit_order.is_expired and
                        not tracked_limit_order.is_failure and
                        not tracked_limit_order.is_done and
                        tracked_limit_order.expires <= current_timestamp + self.PRE_EMPTIVE_SOFT_CANCEL_TIME):

                    if tracked_limit_order.trade_type is TradeType.BUY:
                        self.logger().info(f"The limit buy order {tracked_limit_order.client_order_id} "
                                           f"will be pre-emptively soft cancelled.")
                    else:
                        self.logger().info(f"The limit sell order {tracked_limit_order.client_order_id} "
                                           f"will be pre-emptively soft cancelled.")
                    self.c_cancel("", tracked_limit_order.client_order_id)
        self._last_update_limit_order_timestamp = current_timestamp

    async def _update_market_order_status(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_market_order_timestamp <= self.UPDATE_MARKET_ORDERS_INTERVAL:
            return

        if len(self._in_flight_market_orders) > 0:
            tracked_market_orders = list(self._in_flight_market_orders.values())
            for tracked_market_order in tracked_market_orders:
                receipt = self.get_tx_hash_receipt(tracked_market_order.tx_hash)

                if receipt is None:
                    continue

                if receipt["status"] == 0:
                    err_msg = (f"The market order {tracked_market_order.client_order_id}"
                               f"has failed according to transaction hash {tracked_market_order.tx_hash}.")
                    self.logger().network(err_msg, app_warning_msg=err_msg)
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(self._current_timestamp,
                                                tracked_market_order.client_order_id,
                                                OrderType.MARKET)
                    )
                elif receipt["status"] == 1:
                    gas_used = Decimal(receipt.get("gasUsed", 0.0))
                    self.c_trigger_event(
                        self.MARKET_ORDER_FILLED_EVENT_TAG,
                        OrderFilledEvent(
                            self._current_timestamp,
                            tracked_market_order.client_order_id,
                            tracked_market_order.symbol,
                            tracked_market_order.trade_type,
                            OrderType.MARKET,
                            tracked_market_order.price,
                            tracked_market_order.amount,
                            TradeFee(Decimal(0.0), [("ETH", gas_used)])
                        )
                    )
                    if tracked_market_order.trade_type is TradeType.BUY:
                        self.logger().info(f"The market buy order "
                                           f"{tracked_market_order.client_order_id} has completed according to "
                                           f"transaction hash {tracked_market_order.tx_hash}.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_market_order.client_order_id,
                                                                    tracked_market_order.base_asset,
                                                                    tracked_market_order.quote_asset,
                                                                    tracked_market_order.quote_asset,
                                                                    tracked_market_order.amount,
                                                                    tracked_market_order.executed_amount_quote,
                                                                    tracked_market_order.gas_fee_amount,
                                                                    OrderType.MARKET))
                    else:
                        self.logger().info(f"The market sell order "
                                           f"{tracked_market_order.client_order_id} has completed according to "
                                           f"transaction hash {tracked_market_order.tx_hash}.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_market_order.client_order_id,
                                                                     tracked_market_order.base_asset,
                                                                     tracked_market_order.quote_asset,
                                                                     tracked_market_order.quote_asset,
                                                                     tracked_market_order.amount,
                                                                     tracked_market_order.executed_amount_quote,
                                                                     tracked_market_order.gas_fee_amount,
                                                                     OrderType.MARKET))
                else:
                    err_msg = (f"Unrecognized transaction status for market order "
                               f"{tracked_market_order.client_order_id}. Check transaction hash "
                               f"{tracked_market_order.tx_hash} for more details.")
                    self.logger().network(err_msg, app_warning_msg=err_msg)
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(self._current_timestamp,
                                                tracked_market_order.client_order_id,
                                                OrderType.MARKET)
                    )

                self.c_stop_tracking_order(tracked_market_order.tx_hash)
        self._last_update_market_order_timestamp = current_timestamp

    async def _approval_tx_polling_loop(self):
        while len(self._pending_approval_tx_hashes) > 0:
            try:
                if len(self._pending_approval_tx_hashes) > 0:
                    for tx_hash in list(self._pending_approval_tx_hashes):
                        receipt = self._w3.eth.getTransactionReceipt(tx_hash)
                        if receipt is not None:
                            self._pending_approval_tx_hashes.remove(tx_hash)
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching approval transactions.",
                    exc_info=True,
                    app_warning_msg="Could not get token approval status. "
                                    "Check Ethereum wallet and network connection."
                )
            finally:
                await asyncio.sleep(1.0)

    async def _api_request(self,
                           http_method: str,
                           url: str,
                           data: Optional[Dict[str, Any]] = None,
                           headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as client:
            async with client.request(http_method,
                                      url=url,
                                      timeout=self.API_CALL_TIMEOUT,
                                      json=data,
                                      headers=headers) as response:
                try:
                    if response.status == 201:
                        return response
                    elif response.status == 200:
                        response_json = await response.json()
                        return response_json
                    else:
                        raise IOError
                except Exception:
                    if response.status == 502:
                        raise IOError(f"Error fetching data from {url}. "
                                      f"HTTP status is {response.status} - Server Error: Bad Gateway.")
                    else:
                        response_text = await response.text()
                        raise IOError(f"Error fetching data from {url}. "
                                      f"HTTP status is {response.status} - {response_text}.")

    async def request_signed_market_orders(self, symbol: str, trade_type: TradeType, amount: str) -> Dict[str, Any]:
        if trade_type is TradeType.BUY:
            order_type = "BUY"
        elif trade_type is TradeType.SELL:
            order_type = "SELL"
        else:
            raise ValueError("Invalid trade_type. Aborting.")
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/markets/{symbol}/order/market"
        data = {
            "type": order_type,
            "quantity": amount
        }
        response_data = await self._api_request(http_method="post", url=url, data=data, headers={"User-Agent": "hummingbot"})
        return response_data

    async def request_unsigned_limit_order(self,
                                           symbol: str,
                                           trade_type: TradeType,
                                           is_coordinated: bool,
                                           amount: str,
                                           price: str,
                                           expires: int) -> Dict[str, Any]:
        if trade_type is TradeType.BUY:
            order_type = "BUY"
        elif trade_type is TradeType.SELL:
            order_type = "SELL"
        else:
            raise ValueError("Invalid trade_type. Aborting.")
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/markets/{symbol}/order/limit"
        data = {
            "type": order_type,
            "useCoordinator": is_coordinated,
            "quantity": amount,
            "price": price,
            "expiration": expires
        }
        return await self._api_request(http_method="post", url=url, data=data, headers={"User-Agent": "hummingbot"})

    def get_order_hash_hex(self, unsigned_order: Dict[str, Any]) -> str:
        order_struct = jsdict_order_to_struct(unsigned_order)
        order_hash_hex = generate_order_hash_hex(order=order_struct,
                                                 exchange_address=self._exchange_address.lower())
        return order_hash_hex

    def get_zero_ex_signature(self, order_hash_hex: str) -> str:
        signature = self._wallet.current_backend.sign_hash(hexstr=order_hash_hex)
        fixed_signature = fix_signature(self._provider, self._wallet.address, order_hash_hex, signature)
        return fixed_signature

    async def submit_market_order(self,
                                  symbol: str,
                                  trade_type: TradeType,
                                  amount: Decimal) -> Tuple[float, str]:
        if trade_type is not TradeType.BUY and trade_type is not TradeType.SELL:
            raise ValueError("Invalid trade_type. Aborting.")

        response = await self.request_signed_market_orders(symbol=symbol,
                                                           trade_type=trade_type,
                                                           amount=str(amount))
        signed_market_orders = response["orders"]
        average_price = float(response["averagePrice"])
        is_coordinated = bool(response["isCoordinated"])
        base_asset_increment = self.trading_rules.get(symbol).min_base_amount_increment
        base_asset_decimals = -int(math.ceil(math.log10(float(base_asset_increment))))
        max_base_amount_with_decimals = Decimal(amount) * Decimal(f"1e{base_asset_decimals}")

        tx_hash = ""
        total_base_quantity = Decimal(response["totalBaseQuantity"])
        total_quote_quantity = Decimal(response["totalQuoteQuantity"])
        total_base_amount = Decimal(response["totalBaseAmount"])
        total_quote_amount = Decimal(response["totalQuoteAmount"])

        # Sanity check
        if total_base_quantity > Decimal(amount):
            raise ValueError(f"API returned incorrect values for market order")

        # Single orders to use fillOrder, multiple to use batchFill
        if len(signed_market_orders) == 1:
            signed_market_order = signed_market_orders[0]
            signature = signed_market_order["signature"]
            del signed_market_order["signature"]
            order = jsdict_order_to_struct(signed_market_order)

            # Sanity check on rates returned
            if trade_type is TradeType.BUY:
                calculated_maker_amount = math.floor(
                    (total_base_amount * Decimal(signed_market_order["takerAssetAmount"])) /
                    Decimal(signed_market_order["takerAssetAmount"])
                )
                taker_asset_fill_amount = total_quote_amount
                if calculated_maker_amount > max_base_amount_with_decimals:
                    raise ValueError(f"API returned incorrect values for market order")
            else:
                taker_asset_fill_amount = total_base_amount

            if is_coordinated:
                tx_hash = await self._coordinator.fill_order(order, taker_asset_fill_amount, signature)
            else:
                tx_hash = self._exchange.fill_order(order, taker_asset_fill_amount, signature)
        else:
            taker_asset_fill_amounts: List[Decimal] = []
            signatures: List[str] = []
            orders: List[ZeroExOrder] = []

            if trade_type is TradeType.BUY:
                target_taker_amount = total_quote_amount
            else:
                target_taker_amount = total_base_amount
            remaining_taker_fill_amounts = response["remainingTakerFillAmounts"]
            remaining_maker_fill_amounts = response["remainingMakerFillAmounts"]
            total_maker_asset_fill_amount = Decimal(0)
            total_taker_asset_fill_amount = Decimal(0)

            for idx, order in enumerate(signed_market_orders):
                signatures.append(order["signature"])
                del order["signature"]
                orders.append(jsdict_order_to_struct(order))
                taker_fill_amount = Decimal(remaining_taker_fill_amounts[idx])
                maker_fill_amount = Decimal(remaining_maker_fill_amounts[idx])
                new_total_taker_asset_fill_amount = total_taker_asset_fill_amount + taker_fill_amount
                if target_taker_amount > new_total_taker_asset_fill_amount:
                    taker_asset_fill_amounts.append(taker_fill_amount)
                    total_maker_asset_fill_amount = total_maker_asset_fill_amount + maker_fill_amount
                    total_taker_asset_fill_amount = new_total_taker_asset_fill_amount
                else:
                    # calculate
                    remaining_taker_amount = target_taker_amount - total_taker_asset_fill_amount
                    taker_asset_fill_amounts.append(remaining_taker_amount)
                    order_maker_fill_amount = math.floor(
                        (remaining_taker_amount * Decimal(order["makerAssetAmount"])) / Decimal(order["takerAssetAmount"])
                    )
                    total_maker_asset_fill_amount = total_maker_asset_fill_amount + order_maker_fill_amount
                    total_taker_asset_fill_amount = remaining_taker_amount
                    break

            # Sanity check on rates returned
            if trade_type is TradeType.BUY and total_maker_asset_fill_amount > max_base_amount_with_decimals:
                raise ValueError(f"API returned incorrect values for market order")
            elif total_taker_asset_fill_amount > max_base_amount_with_decimals:
                raise ValueError(f"API returned incorrect values for market order")

            if is_coordinated:
                tx_hash = await self._coordinator.batch_fill_orders(orders, taker_asset_fill_amounts, signatures)
            else:
                tx_hash = self._exchange.batch_fill_orders(orders, taker_asset_fill_amounts, signatures)

        return average_price, tx_hash, is_coordinated

    async def submit_limit_order(self,
                                 symbol: str,
                                 trade_type: TradeType,
                                 is_coordinated: bool,
                                 amount: Decimal,
                                 price: str,
                                 expires: int) -> Tuple[str, ZeroExOrder]:
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/orders"
        unsigned_limit_order = await self.request_unsigned_limit_order(symbol=symbol,
                                                                       trade_type=trade_type,
                                                                       is_coordinated=self._use_coordinator,
                                                                       amount=str(amount),
                                                                       price=price,
                                                                       expires=expires)
        unsigned_limit_order["makerAddress"] = self._wallet.address.lower()
        order_hash_hex = self.get_order_hash_hex(unsigned_limit_order)
        signed_limit_order = copy.deepcopy(unsigned_limit_order)
        signature = self.get_zero_ex_signature(order_hash_hex)
        signed_limit_order["signature"] = signature
        try:
            await self._api_request(http_method="post", url=url, data=signed_limit_order,
                                    headers={"User-Agent": "hummingbot"})
            self._latest_salt = int(unsigned_limit_order["salt"])
            order_hash = self._w3.toHex(hexstr=order_hash_hex)
            del unsigned_limit_order["signature"]
            zero_ex_order = jsdict_order_to_struct(unsigned_limit_order)
            return order_hash, zero_ex_order
        except Exception as ex:
            self._last_failed_limit_order_timestamp = self._current_timestamp
            raise ex

    cdef c_cancel(self, str symbol, str client_order_id):
        # Skip this logic if we are not using the coordinator
        if not self._use_coordinator:
            safe_ensure_future(self.cancel_order(client_order_id))
            return

        # Limit order is pending has not been created, so it can't be cancelled yet
        if client_order_id in self._in_flight_pending_limit_orders:
            self._in_flight_pending_cancels[client_order_id] = self._current_timestamp
            return

        # If there's an ongoing cancel on this order within the expiry time, don't do it again.
        if self._in_flight_cancels.get(client_order_id, 0) > self._current_timestamp - self.CANCEL_EXPIRY_TIME:
            return

        # Maintain the in flight orders list vs. expiry invariant.
        cdef:
            list keys_to_delete = []

        for k, cancel_timestamp in self._in_flight_cancels.items():
            if cancel_timestamp < self._current_timestamp - self.CANCEL_EXPIRY_TIME:
                keys_to_delete.append(k)
            else:
                break
        for k in keys_to_delete:
            del self._in_flight_cancels[k]

        # Record the in-flight cancellation.
        self._in_flight_cancels[client_order_id] = self._current_timestamp

        # Execute the cancel asynchronously.
        safe_ensure_future(self.cancel_order(client_order_id))

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        in_flight_limit_orders = self._in_flight_limit_orders.values()
        incomplete_order_ids = []
        incomplete_orders = []
        has_coordinated_order = False

        for order in in_flight_limit_orders:
            if not (order.is_done or
                    order.is_cancelled or
                    order.is_expired or
                    order.is_failure or
                    order.client_order_id in self._in_flight_cancels or
                    order.client_order_id in self._in_flight_pending_cancels):
                incomplete_order_ids.append(order.client_order_id)
                incomplete_orders.append(order)
            if order.is_coordinated:
                has_coordinated_order = True
        if self._latest_salt == -1 or len(incomplete_order_ids) == 0:
            return []

        if has_coordinated_order:
            orders = [o.zero_ex_order for o in incomplete_orders]
            try:
                soft_cancel_result = await self._coordinator.batch_soft_cancel_orders(orders)

                return [CancellationResult(oid, True) for oid in incomplete_order_ids]
            except Exception:
                self.logger().network(
                    f"Unexpected error cancelling orders.",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel orders on Bamboo Relay. "
                                    f"Coordinator rejected cancellation request."
                )
        else:
            tx_hash = self._exchange.cancel_orders_up_to(self._latest_salt)
            receipt = None
            try:
                async with timeout(timeout_seconds):
                    while receipt is None:
                        receipt = self.get_tx_hash_receipt(tx_hash)
                        if receipt is None:
                            await asyncio.sleep(1.0)
                            continue
                        if receipt["status"] == 0:
                            return [CancellationResult(oid, False) for oid in incomplete_order_ids]
                        elif receipt["status"] == 1:
                            return [CancellationResult(oid, True) for oid in incomplete_order_ids]
            except Exception:
                self.logger().network(
                    f"Unexpected error cancelling orders.",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel orders on Bamboo Relay. "
                                    f"Check Ethereum wallet and network connection."
                )
        return [CancellationResult(oid, False) for oid in incomplete_order_ids]

    async def execute_trade(self,
                            order_id: str,
                            order_type: OrderType,
                            trade_type: TradeType,
                            symbol: str,
                            amount: Decimal,
                            price: Decimal,
                            expires: int) -> str:
        cdef:
            str q_price
            object q_amt = self.c_quantize_order_amount(symbol, amount)
            TradingRule trading_rule = self._trading_rules[symbol]
            str trade_type_desc = "buy" if trade_type is TradeType.BUY else "sell"
            str type_str = "limit" if order_type is OrderType.LIMIT else "market"
        try:
            if q_amt < trading_rule.min_order_size:
                raise ValueError(f"{trade_type_desc.capitalize()} order amount {q_amt} is lower than the "
                                 f"minimum order size {trading_rule.min_order_size}")
            if q_amt > trading_rule.max_order_size:
                raise ValueError(f"{trade_type_desc.capitalize()} order amount {q_amt} is greater than the "
                                 f"maximum order size {trading_rule.max_order_size}")

            if order_type is OrderType.LIMIT:
                if math.isnan(price):
                    raise ValueError(f"Limit orders require a price. Aborting.")
                elif expires is None:
                    raise ValueError(f"Limit orders require an expiration timestamp 'expiration_ts'. Aborting.")
                elif expires < time.time():
                    raise ValueError(f"expiration time {expires} must be greater than current time {time.time()}")
                else:
                    q_price = str(self.c_quantize_order_price(symbol, price))
                    exchange_order_id, zero_ex_order = await self.submit_limit_order(symbol=symbol,
                                                                                     trade_type=trade_type,
                                                                                     is_coordinated=self._use_coordinator,
                                                                                     amount=q_amt,
                                                                                     price=q_price,
                                                                                     expires=expires)
                    self.c_start_tracking_limit_order(order_id=order_id,
                                                      exchange_order_id=exchange_order_id,
                                                      symbol=symbol,
                                                      order_type=order_type,
                                                      trade_type=trade_type,
                                                      is_coordinated=self._use_coordinator,
                                                      price=q_price,
                                                      amount=q_amt,
                                                      expires=expires,
                                                      zero_ex_order=zero_ex_order)
                    if order_id in self._in_flight_pending_limit_orders:
                        # We have attempted to previously cancel this order before it was resolved as placed
                        if order_id in self._in_flight_pending_cancels:
                            del self._in_flight_pending_cancels[order_id]
                            self.c_cancel("", order_id)
                        del self._in_flight_pending_limit_orders[order_id]
            elif order_type is OrderType.MARKET:
                avg_price, tx_hash, is_coordinated = await self.submit_market_order(symbol=symbol,
                                                                                    trade_type=trade_type,
                                                                                    amount=q_amt)
                q_price = str(self.c_quantize_order_price(symbol, Decimal(avg_price)))
                self.c_start_tracking_market_order(order_id=order_id,
                                                   symbol=symbol,
                                                   order_type=order_type,
                                                   is_coordinated=is_coordinated,
                                                   trade_type=trade_type,
                                                   price=q_price,
                                                   amount=q_amt,
                                                   tx_hash=tx_hash)
            if trade_type is TradeType.BUY:
                self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                     BuyOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         symbol,
                                         q_amt,
                                         q_price,
                                         order_id
                                     ))
            else:
                self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                     SellOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         symbol,
                                         q_amt,
                                         q_price,
                                         order_id
                                     ))
            return order_id
        except Exception:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {type_str} {trade_type_desc} order to Bamboo Relay for {str(q_amt)} {symbol}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit {type_str} {trade_type_desc} order to Bamboo Relay. "
                                f"Check Ethereum wallet and network connection."
            )
            self.c_trigger_event(
                self.MARKET_ORDER_FAILURE_EVENT_TAG,
                MarketOrderFailureEvent(self._current_timestamp, order_id, order_type)
            )

    cdef str c_buy(self,
                   str symbol,
                   object amount,
                   object order_type=OrderType.MARKET,
                   object price=s_decimal_NaN,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"buy-{symbol}-{tracking_nonce}")
            double current_timestamp = self._current_timestamp
        expires = kwargs.get("expiration_ts", None)
        if expires is not None:
            expires = int(expires)
        if order_type is OrderType.LIMIT:
            # Don't spam the server endpoint if a order placement failed recently
            if current_timestamp - self._last_failed_limit_order_timestamp <= self.ORDER_CREATION_BACKOFF_TIME:
                raise
            # Record the in-flight limit order placement.
            self._in_flight_pending_limit_orders[order_id] = self._current_timestamp
        safe_ensure_future(self.execute_trade(order_id=order_id,
                                              order_type=order_type,
                                              trade_type=TradeType.BUY,
                                              symbol=symbol,
                                              amount=amount,
                                              price=price,
                                              expires=expires))
        return order_id

    cdef str c_sell(self,
                    str symbol,
                    object amount,
                    object order_type=OrderType.MARKET,
                    object price=s_decimal_NaN,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")
            double current_timestamp = self._current_timestamp
        expires = kwargs.get("expiration_ts", None)
        if expires is not None:
            expires = int(expires)
        if order_type is OrderType.LIMIT:
            # Don't spam the server endpoint if a order placement failed recently
            if current_timestamp - self._last_failed_limit_order_timestamp <= self.ORDER_CREATION_BACKOFF_TIME:
                raise
            # Record the in-flight limit order placement.
            self._in_flight_pending_limit_orders[order_id] = self._current_timestamp
        safe_ensure_future(self.execute_trade(order_id=order_id,
                                              order_type=order_type,
                                              trade_type=TradeType.SELL,
                                              symbol=symbol,
                                              amount=amount,
                                              price=price,
                                              expires=expires))
        return order_id

    async def cancel_order(self, client_order_id: str) -> Dict[str, Any]:
        cdef:
            BambooRelayInFlightOrder order = self._in_flight_limit_orders.get(client_order_id)

        if not order:
            self.logger().info(f"Failed to cancel order {client_order_id}. Order not found in tracked orders.")
            if client_order_id in self._in_flight_cancels:
                del self._in_flight_cancels[client_order_id]
            return {}

        if order.is_coordinated:
            await self._coordinator.soft_cancel_order(order.zero_ex_order)

            self.logger().info(f"The limit order {order.client_order_id} has been soft cancelled according "
                               f"to the Coordinator server.")
            self.c_expire_order(order.client_order_id)
            self.c_trigger_event(
                self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                OrderCancelledEvent(self._current_timestamp, order.client_order_id)
            )

            return True
        else:
            return self._exchange.cancel_order(order.zero_ex_order)

    def get_tx_hash_receipt(self, tx_hash: str) -> Dict[str, Any]:
        return self._w3.eth.getTransactionReceipt(tx_hash)

    async def list_account_orders(self) -> List[Dict[str, Any]]:
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/accounts/{self._wallet.address}/orders"
        response_data = await self._api_request("get", url=url, headers={"User-Agent": "hummingbot"})
        return response_data

    def wrap_eth(self, amount: float) -> str:
        return self._wallet.wrap_eth(amount)

    def unwrap_eth(self, amount: float) -> str:
        return self._wallet.unwrap_eth(amount)

    cdef OrderBook c_get_order_book(self, str symbol):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if symbol not in order_books:
            raise ValueError(f"No order book exists for '{symbol}'.")
        return order_books[symbol]

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()

        self._order_tracker_task = safe_ensure_future(self._order_book_tracker.start())
        self._status_polling_task = safe_ensure_future(self._status_polling_loop())
        if self._trading_required:
            tx_hashes = await self.wallet.current_backend.check_and_fix_approval_amounts(
                spender=self._wallet_spender_address
            )
            self._pending_approval_tx_hashes.update(tx_hashes)
            self._approval_tx_polling_task = safe_ensure_future(self._approval_tx_polling_loop())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._pending_approval_tx_hashes is not None:
            self._pending_approval_tx_hashes.clear()
        if self._approval_tx_polling_task is not None:
            self._approval_tx_polling_task.cancel()
        self._order_tracker_task = self._status_polling_task = self._approval_tx_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        if self._wallet.network_status is not NetworkStatus.CONNECTED:
            return NetworkStatus.NOT_CONNECTED

        try:
            await self._api_request("GET", f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/tokens",
                                    headers={"User-Agent": "hummingbot"})
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)

        self._tx_tracker.c_tick(timestamp)
        MarketBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self.c_check_and_remove_expired_orders()
        self._last_timestamp = timestamp

    cdef c_start_tracking_limit_order(self,
                                      str order_id,
                                      str exchange_order_id,
                                      str symbol,
                                      object order_type,
                                      bint is_coordinated,
                                      object trade_type,
                                      object price,
                                      object amount,
                                      int expires,
                                      object zero_ex_order):
        self._in_flight_limit_orders[order_id] = BambooRelayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            symbol=symbol,
            order_type=order_type,
            is_coordinated=is_coordinated,
            trade_type=trade_type,
            price=price,
            amount=amount,
            expires=expires,
            tx_hash=None,
            zero_ex_order=zero_ex_order
        )

    cdef c_start_tracking_market_order(self,
                                       str order_id,
                                       str symbol,
                                       object order_type,
                                       bint is_coordinated,
                                       object trade_type,
                                       object price,
                                       object amount,
                                       str tx_hash):
        self._in_flight_market_orders[tx_hash] = BambooRelayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=None,
            symbol=symbol,
            order_type=order_type,
            is_coordinated=is_coordinated,
            trade_type=trade_type,
            price=price,
            amount=amount,
            expires=0,
            tx_hash=tx_hash
        )

    cdef c_expire_order(self, str order_id):
        self._order_expiry_queue.append((self._current_timestamp + self.ORDER_EXPIRY_TIME, order_id))

    cdef c_check_and_remove_expired_orders(self):
        cdef:
            double current_timestamp = self._current_timestamp
            str order_id

        while len(self._order_expiry_queue) > 0 and self._order_expiry_queue[0][0] < current_timestamp:
            _, order_id = self._order_expiry_queue.popleft()
            self.c_stop_tracking_order(order_id)

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_limit_orders:
            del self._in_flight_limit_orders[order_id]
        elif order_id in self._in_flight_market_orders:
            del self._in_flight_market_orders[order_id]

    cdef object c_get_order_price_quantum(self, str symbol, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        decimals_quantum = trading_rule.min_quote_amount_increment
        if price > s_decimal_0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(price)) - trading_rule.max_price_significant_digits}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_get_order_size_quantum(self, str symbol, object amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        decimals_quantum = trading_rule.min_base_amount_increment

        if amount > s_decimal_0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(amount)) - trading_rule.max_price_significant_digits}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_quantize_order_amount(self, str symbol, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        global s_decimal_0
        quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, min(amount, trading_rule.max_order_size))

        # Check against min_order_size. If not passing the check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        return quantized_amount
