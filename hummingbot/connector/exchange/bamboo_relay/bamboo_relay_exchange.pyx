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
from decimal import (
    ROUND_FLOOR,
    Decimal
)
from eth_utils import remove_0x_prefix
from libc.stdint cimport int64_t
from web3 import Web3
from web3.exceptions import TransactionNotFound

from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
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
    TradeFee,
    ZeroExFillEvent
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_api_order_book_data_source import BambooRelayAPIOrderBookDataSource
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_in_flight_order cimport BambooRelayInFlightOrder
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_order_book_tracker import BambooRelayOrderBookTracker
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import OrderType
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.wallet.ethereum.zero_ex.zero_ex_custom_utils_v3 import (
    fix_signature,
    generate_order_hash_hex,
    jsdict_order_to_struct,
    Order as ZeroExOrder
)
from hummingbot.wallet.ethereum.zero_ex.zero_ex_exchange_v3 import ZeroExExchange
from hummingbot.wallet.ethereum.zero_ex.zero_ex_coordinator_v3 import ZeroExCoordinator
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_constants import (
    BAMBOO_RELAY_REST_ENDPOINT,
    BAMBOO_RELAY_TEST_ENDPOINT,
    ZERO_EX_MAINNET_ERC20_PROXY,
    ZERO_EX_MAINNET_EXCHANGE_ADDRESS,
    ZERO_EX_MAINNET_COORDINATOR_ADDRESS,
    ZERO_EX_MAINNET_COORDINATOR_REGISTRY_ADDRESS,
    ZERO_EX_ROPSTEN_ERC20_PROXY,
    ZERO_EX_ROPSTEN_EXCHANGE_ADDRESS,
    ZERO_EX_ROPSTEN_COORDINATOR_ADDRESS,
    ZERO_EX_ROPSTEN_COORDINATOR_REGISTRY_ADDRESS,
    ZERO_EX_RINKEBY_ERC20_PROXY,
    ZERO_EX_RINKEBY_EXCHANGE_ADDRESS,
    ZERO_EX_RINKEBY_COORDINATOR_ADDRESS,
    ZERO_EX_RINKEBY_COORDINATOR_REGISTRY_ADDRESS,
    ZERO_EX_KOVAN_ERC20_PROXY,
    ZERO_EX_KOVAN_EXCHANGE_ADDRESS,
    ZERO_EX_KOVAN_COORDINATOR_ADDRESS,
    ZERO_EX_KOVAN_COORDINATOR_REGISTRY_ADDRESS,
    ZERO_EX_TEST_ERC20_PROXY,
    ZERO_EX_TEST_EXCHANGE_ADDRESS,
    ZERO_EX_TEST_COORDINATOR_ADDRESS,
    ZERO_EX_TEST_COORDINATOR_REGISTRY_ADDRESS,
    BAMBOO_RELAY_MAINNET_FEE_RECIPIENT_ADDRESS,
    BAMBOO_RELAY_ROPSTEN_FEE_RECIPIENT_ADDRESS,
    BAMBOO_RELAY_RINKEBY_FEE_RECIPIENT_ADDRESS,
    BAMBOO_RELAY_KOVAN_FEE_RECIPIENT_ADDRESS,
    BAMBOO_RELAY_TEST_FEE_RECIPIENT_ADDRESS
)
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

brm_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("NaN")

cdef class BambooRelayTransactionTracker(TransactionTracker):
    cdef:
        BambooRelayExchange _owner

    def __init__(self, owner: BambooRelayExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class BambooRelayExchange(ExchangeBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
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
                 trading_pairs: Optional[List[str]] = None,
                 use_coordinator: Optional[bool] = True,
                 pre_emptive_soft_cancels: Optional[bool] = True,
                 trading_required: bool = True):
        cdef:
            str coordinator_address
            str coordinator_registry_address
            int chain_id
        super().__init__()
        self._trading_required = trading_required
        self._order_book_tracker = BambooRelayOrderBookTracker(trading_pairs=trading_pairs,
                                                               chain=wallet.chain)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_failed_limit_order_timestamp = 0
        self._last_update_limit_order_timestamp = 0
        self._last_update_market_order_timestamp = 0
        self._last_update_trading_rules_timestamp = 0
        self._last_update_available_balance_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_limit_orders = {}   # limit orders are off chain
        self._in_flight_market_orders = {}  # market orders are on chain
        self._in_flight_pending_limit_orders = OrderedDict()  # in the case that an order needs to be cancelled before its been accepted
        self._in_flight_cancels = OrderedDict()
        self._in_flight_pending_cancels = OrderedDict()
        self._filled_order_hashes = []      # To prevent market filling trying to overfill an inflight market order that's pending
        self._order_expiry_queue = deque()
        self._tx_tracker = BambooRelayTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        self._provider = Web3.HTTPProvider(ethereum_rpc_url)
        self._trading_rules = {}
        self._pending_approval_tx_hashes = set()
        self._status_polling_task = None
        self._approval_tx_polling_task = None
        self._wallet = wallet
        self._use_coordinator = use_coordinator
        self._pre_emptive_soft_cancels = pre_emptive_soft_cancels
        self._latest_salt = -1
        if wallet.chain is EthereumChain.MAIN_NET:
            self._chain_id = 1
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "main/0x"
            self._fee_recipient_address =BAMBOO_RELAY_MAINNET_FEE_RECIPIENT_ADDRESS
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_EXCHANGE_ADDRESS)
            self._coordinator_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_ERC20_PROXY)
        elif wallet.chain is EthereumChain.ROPSTEN:
            self._chain_id = 3
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "ropsten/0x"
            self._fee_recipient_address =BAMBOO_RELAY_ROPSTEN_FEE_RECIPIENT_ADDRESS
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_EXCHANGE_ADDRESS)
            self._coordinator_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_ERC20_PROXY)
        elif wallet.chain is EthereumChain.RINKEBY:
            self._chain_id = 4
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "rinkeby/0x"
            self._fee_recipient_address = BAMBOO_RELAY_RINKEBY_FEE_RECIPIENT_ADDRESS
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_EXCHANGE_ADDRESS)
            self._coordinator_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_ERC20_PROXY)
        elif wallet.chain is EthereumChain.KOVAN:
            self._chain_id = 42
            self._api_endpoint = BAMBOO_RELAY_REST_ENDPOINT
            self._api_prefix = "kovan/0x"
            self._fee_recipient_address = BAMBOO_RELAY_KOVAN_FEE_RECIPIENT_ADDRESS
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_KOVAN_EXCHANGE_ADDRESS)
            self._coordinator_address = Web3.toChecksumAddress(ZERO_EX_KOVAN_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_KOVAN_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_KOVAN_ERC20_PROXY)
        elif wallet.chain is EthereumChain.ZEROEX_TEST:
            self._chain_id = 1337
            self._api_endpoint = BAMBOO_RELAY_TEST_ENDPOINT
            self._api_prefix = "testrpc/0x"
            self._fee_recipient_address = BAMBOO_RELAY_TEST_FEE_RECIPIENT_ADDRESS
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_TEST_EXCHANGE_ADDRESS)
            self._coordinator_address = Web3.toChecksumAddress(ZERO_EX_TEST_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_TEST_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_TEST_ERC20_PROXY)
        self._exchange = ZeroExExchange(self._w3, self._exchange_address, wallet)
        self._coordinator = ZeroExCoordinator(self._provider,
                                              self._w3,
                                              self._exchange_address,
                                              self._coordinator_address,
                                              coordinator_registry_address,
                                              wallet,
                                              self._chain_id)

    @property
    def name(self) -> str:
        return "bamboo_relay"

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "account_available_balance": len(self._account_available_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True,
            "token_approval": len(self._pending_approval_tx_hashes) == 0 if self._trading_required else True
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def name(self) -> str:
        return "bamboo_relay"

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
            # Skip orders that are or have been cancelled but are still being tracked
            if (typed_in_flight_order.order_type is not OrderType.LIMIT or
                    typed_in_flight_order.client_order_id in expiring_order_ids or
                    typed_in_flight_order.client_order_id in self._in_flight_cancels or
                    typed_in_flight_order.client_order_id in self._in_flight_pending_cancels or
                    typed_in_flight_order.has_been_cancelled):
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

    @property
    def in_flight_orders(self) -> Dict[str, BambooRelayInFlightOrder]:
        return {**self.in_flight_limit_orders, **self.in_flight_market_orders}

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

            # if completed/cancelled orders are restored they should become untracked
            if len(self._in_flight_limit_orders) >= 0:
                for order in list(self._in_flight_limit_orders.values()):
                    if (order.is_cancelled or
                            order.has_been_cancelled or
                            order.is_expired or
                            order.is_failure or
                            order.is_done or
                            order.expires < self._current_timestamp):
                        del self._in_flight_limit_orders[order.client_order_id]
        except Exception:
            self.logger().error(f"Error restoring tracking states.", exc_info=True)

    async def get_active_exchange_markets(self):
        return await BambooRelayAPIOrderBookDataSource.get_active_exchange_markets(self._api_endpoint, self._api_prefix)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                self._update_balances()
                self._update_available_balances()
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
            int base_coordinator_cost = 116000      # coordinator uses a fixed additional amount of gas
            int order_gas_cost = 150000
            double protocol_fee
            double transaction_cost_eth
            bint is_coordinated = False
            list valid_orders

        """
        # there are no fees for makers on Bamboo Relay
        if order_type is OrderType.LIMIT:
            return TradeFee(percent=s_decimal_0)

        # fees for taker are protocol fee, transaction fee and order taker fees
        valid_orders = self.c_get_orders_for_amount_price(trading_pair=base_currency + "-" + quote_currency,
                                                          trade_type=trade_type,
                                                          amount=amount,
                                                          price=Decimal(price))     # market base has this as a `float`

        for order in valid_orders:
            if order["isCoordinated"]:
                is_coordinated = True
                break

        if is_coordinated:
            transaction_cost_eth = self._wallet.gas_price * (len(valid_orders) * order_gas_cost + base_coordinator_cost) / 1e18
        else:
            transaction_cost_eth = self._wallet.gas_price * len(valid_orders) * order_gas_cost / 1e18

        protocol_fee = ZERO_EX_PROTOCOL_FEE_MULTIPLIER * len(valid_orders) * self._wallet.gas_price / 1e18

        return TradeFee(percent=s_decimal_0, flat_fees=[("ETH", protocol_fee),
                                                        ("ETH", transaction_cost_eth)])
        """
        is_maker = order_type is OrderType.LIMIT
        return estimate_fee("bamboo_relay", is_maker)

    def _update_balances(self):
        self._account_balances = self.wallet.get_all_balances().copy()

    def _update_available_balances(self):
        cdef:
            double current_timestamp = self._current_timestamp
            BambooRelayInFlightOrder order
            object amount
            str currency
            list pair_split
            dict locked_balances = {}

        # Retrieve account balance from wallet
        self._account_balances = self.wallet.get_all_balances().copy()

        # Calculate available balance
        if current_timestamp - self._last_update_available_balance_timestamp > 10.0:

            if len(self._in_flight_limit_orders) >= 0:
                total_balances = self._account_balances

                for order in self._in_flight_limit_orders.values():
                    # Orders that are done, cancelled or expired don't deduct from the available balance
                    if (not order.is_cancelled and
                            not order.has_been_cancelled and
                            not order.is_expired and
                            not order.is_failure and
                            not order.is_done):
                        pair_split = order.trading_pair.split("-")
                        if order.trade_type is TradeType.BUY:
                            currency = pair_split[1]
                            amount = Decimal(order.amount * order.price)
                        else:
                            currency = pair_split[0]
                            amount = Decimal(order.amount)
                        locked_balances[currency] = locked_balances.get(currency, s_decimal_0) + amount

                for order in self._in_flight_market_orders.values():
                    # Market orders are only tracked for their transaction duration
                    pair_split = order.trading_pair.split("-")
                    if order.trade_type is TradeType.BUY:
                        currency = pair_split[1]
                        amount = Decimal(order.amount * order.price)
                    else:
                        currency = pair_split[0]
                        amount = Decimal(order.amount)
                    locked_balances[currency] = locked_balances.get(currency, s_decimal_0) + amount

                for currency, balance in total_balances.items():
                    self._account_available_balances[currency] = \
                        Decimal(total_balances[currency]) - locked_balances.get(currency, s_decimal_0)
            else:
                self._account_available_balances = self._account_balances.copy()

            self._last_update_available_balance_timestamp = current_timestamp

    async def list_market(self) -> Dict[str, Any]:
        url = f"{self._api_endpoint}{self._api_prefix}/markets?perPage=1000&include=base"
        return await self._api_request(http_method="get", url=url, headers={"User-Agent": "hummingbot"})

    async def _update_trading_rules(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_trading_rules_timestamp > self.UPDATE_RULES_INTERVAL or len(self._trading_rules) < 1:
            markets = await self.list_market()
            trading_rules_list = self._format_trading_rules(markets)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule
            self._last_update_trading_rules_timestamp = current_timestamp

    def _format_trading_rules(self, markets: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list retval = []
        for market in markets:
            try:
                trading_pair = market["id"]
                retval.append(TradingRule(trading_pair,
                                          min_order_size=Decimal(market["minOrderSize"]),
                                          max_order_size=Decimal(market["maxOrderSize"]),
                                          max_price_significant_digits=Decimal(market['quoteIncrement']),
                                          min_price_increment=Decimal(f"1e-{market['quoteTokenDecimals']}"),
                                          min_base_amount_increment=Decimal(f"1e-{market['baseTokenDecimals']}"),
                                          min_quote_amount_increment=Decimal(f"1e-{market['quoteTokenDecimals']}")))
            except Exception:
                self.logger().error(f"Error parsing the trading_pair {trading_pair}. Skipping.", exc_info=True)
        return retval

    async def get_account_orders(self) -> List[Dict[str, Any]]:
        return await self._api_request(http_method="get",
                                       url=f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/accounts/{self._wallet.address.lower()}/orders",
                                       headers={"User-Agent": "hummingbot"})

    async def get_orders(self, order_hashes: List[str]) -> Dict[str, Dict[str, Any]]:
        return await self._api_request("post",
                                       url=f"{self._api_endpoint}{self._api_prefix}/orders/hashes",
                                       data=order_hashes,
                                       headers={"User-Agent": "hummingbot"})

    async def _get_order_updates(self, tracked_limit_orders: List[BambooRelayInFlightOrder]) -> List[Dict[str, Any]]:
        cdef:
            BambooRelayInFlightOrder tracked_limit_order
            list account_orders_list = []
            list order_updates = []
            list hashes = []
            dict hash_index = {}
            dict account_orders_map = {}

        # Fetch cached account endpoint
        account_orders_list = await self.get_account_orders()
        for account_order in account_orders_list:
            account_orders_map[account_order["orderHash"]] = account_order

        for i, tracked_order in enumerate(tracked_limit_orders):
            order_hash = tracked_order.exchange_order_id
            if order_hash not in account_orders_map:
                hashes.append(tracked_order.exchange_order_id)
                hash_index[order_hash] = i
                order_updates.append(None)
            else:
                order_updates.append(account_orders_map[order_hash])

        if len(hashes):
            # Grab all of the orders details at once by hash
            orders = await self.get_orders(hashes)
            for hash in orders:
                order_updates[hash_index[hash]] = orders[hash]

        return order_updates

    # Single order update, i.e. via RPC logs instead of market API
    def _update_single_limit_order(self, fill_event: ZeroExFillEvent):
        cdef:
            double current_timestamp = self._current_timestamp
            object order_remaining_base_token_amount
            object order_filled_base_token_amount
            object order_filled_quote_token_amount
            int base_asset_decimals
            int quote_asset_decimals
            BambooRelayInFlightOrder tracked_limit_order

        tracked_limit_orders = list(self._in_flight_limit_orders.values())

        for tracked_limit_order in tracked_limit_orders:
            if tracked_limit_order.exchange_order_id == fill_event.order_hash:
                previous_is_done = tracked_limit_order.is_done

                if not previous_is_done:
                    order_remaining_base_token_amount = tracked_limit_order.available_amount_base

                    trading_pair_rules = self.trading_rules.get(tracked_limit_order.trading_pair)
                    base_asset_decimals = -int(math.ceil(math.log10(float(trading_pair_rules.min_base_amount_increment))))
                    quote_asset_decimals = -int(math.ceil(math.log10(float(trading_pair_rules.min_quote_amount_increment))))

                    order_filled_base_token_amount = s_decimal_0
                    order_filled_quote_token_amount = s_decimal_0

                    # Each update has a list of fills, we only process these once
                    if fill_event.tx_hash not in tracked_limit_order.recorded_fills:
                        if tracked_limit_order.trade_type is TradeType.BUY:
                            order_filled_base_token_amount = fill_event.taker_asset_filled_amount / Decimal(f"1e{base_asset_decimals}")
                            order_filled_quote_token_amount = fill_event.maker_asset_filled_amount / Decimal(f"1e{quote_asset_decimals}")
                        else:
                            order_filled_base_token_amount = fill_event.maker_asset_filled_amount / Decimal(f"1e{base_asset_decimals}")
                            order_filled_quote_token_amount = fill_event.taker_asset_filled_amount / Decimal(f"1e{quote_asset_decimals}")

                        if order_filled_base_token_amount > 0:
                            tracked_limit_order.recorded_fills.append(fill_event.tx_hash)

                    tracked_limit_order.available_amount_base = order_remaining_base_token_amount - order_filled_base_token_amount

                    if tracked_limit_order.available_amount_base < 0:
                        tracked_limit_order.available_amount_base = 0

                    if order_filled_base_token_amount > 0:
                        tracked_limit_order.executed_amount_base = tracked_limit_order.executed_amount_base + order_filled_base_token_amount
                        tracked_limit_order.executed_amount_quote = tracked_limit_order.executed_amount_quote + order_filled_quote_token_amount
                        self.logger().info(f"Filled {order_filled_base_token_amount} out of {tracked_limit_order.amount} of the "
                                           f"limit order {tracked_limit_order.client_order_id} according to the RPC transaction logs.")
                        self.c_trigger_event(
                            self.MARKET_ORDER_FILLED_EVENT_TAG,
                            OrderFilledEvent(
                                current_timestamp,
                                tracked_limit_order.client_order_id,
                                tracked_limit_order.trading_pair,
                                tracked_limit_order.trade_type,
                                OrderType.LIMIT,
                                tracked_limit_order.price,
                                order_filled_base_token_amount,
                                TradeFee(0.0),  # no fee for limit order fills
                                tracked_limit_order.exchange_order_id,  # Use order hash for limit order validation
                            )
                        )
                    if tracked_limit_order.available_amount_base == 0:
                        tracked_limit_order.last_state = "FILLED"
                        self.c_expire_order(tracked_limit_order.client_order_id, 60)
                        # Remove from log tracking
                        safe_ensure_future(self._wallet.current_backend.zeroex_fill_watcher.unwatch_order_hash(tracked_limit_order.exchange_order_id))
                        if tracked_limit_order.trade_type is TradeType.BUY:
                            self.logger().info(f"The limit buy order {tracked_limit_order.client_order_id} "
                                               f"has completed according to the RPC transaction logs.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(current_timestamp,
                                                                        tracked_limit_order.client_order_id,
                                                                        tracked_limit_order.base_asset,
                                                                        tracked_limit_order.quote_asset,
                                                                        tracked_limit_order.quote_asset,
                                                                        tracked_limit_order.executed_amount_base,
                                                                        tracked_limit_order.executed_amount_quote,
                                                                        tracked_limit_order.protocol_fee_amount,
                                                                        OrderType.LIMIT))
                        else:
                            self.logger().info(f"The limit sell order {tracked_limit_order.client_order_id} "
                                               f"has completed according to the RPC transaction logs.")
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(current_timestamp,
                                                                         tracked_limit_order.client_order_id,
                                                                         tracked_limit_order.base_asset,
                                                                         tracked_limit_order.quote_asset,
                                                                         tracked_limit_order.quote_asset,
                                                                         tracked_limit_order.executed_amount_base,
                                                                         tracked_limit_order.executed_amount_quote,
                                                                         tracked_limit_order.protocol_fee_amount,
                                                                         OrderType.LIMIT))
                return

    async def _update_limit_order_status(self):
        cdef:
            double current_timestamp = self._current_timestamp
            int order_timestamp_diff
            object order_remaining_base_token_amount
            object fill_base_token_amount
            object order_filled_base_token_amount
            object order_filled_quote_token_amount
            object previous_amount_available

        if current_timestamp - self._last_update_limit_order_timestamp <= self.UPDATE_OPEN_LIMIT_ORDERS_INTERVAL:
            return

        cdef:
            BambooRelayInFlightOrder tracked_limit_order

        if len(self._in_flight_limit_orders) > 0:
            tracked_limit_orders = list(self._in_flight_limit_orders.values())
            order_updates = await self._get_order_updates(tracked_limit_orders)
            # Every limit order update happens on this tick, so use the current timestamp
            current_timestamp = self._current_timestamp
            for order_update, tracked_limit_order in zip(order_updates, tracked_limit_orders):
                if order_update is None:
                    # 404 handling
                    if not tracked_limit_order.is_cancelled and not tracked_limit_order.has_been_cancelled:
                        self.logger().info(f"The limit order {tracked_limit_order.client_order_id} could not be found "
                                           f"according to order status API. Removing from tracking.")
                        # soft cancel this order if we are using the coordinator just to be safe
                        if tracked_limit_order.is_coordinated:
                            self.c_cancel("", tracked_limit_order.client_order_id)
                        self.c_expire_order(tracked_limit_order.client_order_id, 10)
                        self.c_trigger_event(
                            self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                            OrderCancelledEvent(current_timestamp, tracked_limit_order.client_order_id)
                        )
                        tracked_limit_order.last_state = "CANCELED"
                    continue
                previous_is_done = tracked_limit_order.is_done
                previous_is_cancelled = tracked_limit_order.is_cancelled
                previous_is_failure = tracked_limit_order.is_failure
                previous_is_expired = tracked_limit_order.is_expired
                order_state = order_update["state"]

                order_remaining_base_token_amount = Decimal(order_update["remainingBaseTokenAmount"])

                order_filled_base_token_amount = s_decimal_0
                order_filled_quote_token_amount = s_decimal_0

                # Each update has a list of fills, we only process these once
                for fill in order_update["fills"]:
                    if not fill["transactionHash"] in tracked_limit_order.recorded_fills:
                        fill_base_token_amount = Decimal(fill["filledBaseTokenAmount"])
                        # Pending fills have a 0 blocknumer, pending status, or 0 fill amount
                        if fill_base_token_amount > 0 and fill["blockNumber"] > 0 and fill["status"] == "COMPLETED":
                            order_filled_base_token_amount += fill_base_token_amount
                            order_filled_quote_token_amount += Decimal(fill["filledQuoteTokenAmount"])
                            tracked_limit_order.recorded_fills.append(fill["transactionHash"])

                previous_amount_available = tracked_limit_order.available_amount_base

                tracked_limit_order.last_state = order_state
                tracked_limit_order.available_amount_base = order_remaining_base_token_amount

                if order_filled_base_token_amount > 0:
                    tracked_limit_order.executed_amount_base = tracked_limit_order.executed_amount_base + order_filled_base_token_amount
                    tracked_limit_order.executed_amount_quote = tracked_limit_order.executed_amount_quote + order_filled_quote_token_amount
                    self.logger().info(f"Filled {order_filled_base_token_amount} out of {tracked_limit_order.amount} of the "
                                       f"limit order {tracked_limit_order.client_order_id} according to order status API.")
                    self.c_trigger_event(
                        self.MARKET_ORDER_FILLED_EVENT_TAG,
                        OrderFilledEvent(
                            current_timestamp,
                            tracked_limit_order.client_order_id,
                            tracked_limit_order.trading_pair,
                            tracked_limit_order.trade_type,
                            OrderType.LIMIT,
                            tracked_limit_order.price,
                            order_filled_base_token_amount,
                            TradeFee(0.0),  # no fee for limit order fills
                            tracked_limit_order.exchange_order_id,  # Use order hash for limit order validation
                        )
                    )
                elif order_remaining_base_token_amount < (previous_amount_available + order_filled_base_token_amount):
                    # i.e. user was running a bot on Bamboo and Radar, or two instances of the bot at the same time
                    self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has had it's available amount "
                                       f"reduced to {order_remaining_base_token_amount} according to order status API.")

                # Has been soft cancelled already according to the Coordinator Server or
                # a mined Cancel transaction was completed
                if tracked_limit_order.has_been_cancelled:
                    continue

                # do not retrigger order events if order was already in that state previously
                if not previous_is_cancelled and tracked_limit_order.is_cancelled:
                    if (self._in_flight_cancels.get(tracked_limit_order.client_order_id, 0) >
                            current_timestamp - self.CANCEL_EXPIRY_TIME):
                        # This cancel was originated from this connector, and the cancel event should have been
                        # emitted in the cancel_order() call already.
                        del self._in_flight_cancels[tracked_limit_order.client_order_id]
                    else:
                        self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has cancelled according "
                                           f"to order status API.")
                        if tracked_limit_order.is_coordinated:
                            # Maximum fill time for a coordinated order is 90 seconds or the order expiry
                            order_timestamp_diff = abs(tracked_limit_order.expires - int(current_timestamp))
                            self.c_expire_order(tracked_limit_order.client_order_id, min(order_timestamp_diff, 130))
                        else:
                            self.c_expire_order(tracked_limit_order.client_order_id, 10)
                        self.c_trigger_event(
                            self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                            OrderCancelledEvent(current_timestamp, tracked_limit_order.client_order_id)
                        )
                elif not previous_is_expired and tracked_limit_order.is_expired:
                    self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has expired according "
                                       f"to order status API.")
                    if tracked_limit_order.is_coordinated:
                        # Maximum fill time for a coordinated order is 90 seconds or the order expiry
                        order_timestamp_diff = abs(tracked_limit_order.expires - int(current_timestamp))
                        self.c_expire_order(tracked_limit_order.client_order_id, min(order_timestamp_diff, 130))
                    else:
                        self.c_expire_order(tracked_limit_order.client_order_id, 30)
                    self.c_trigger_event(
                        self.MARKET_ORDER_EXPIRED_EVENT_TAG,
                        OrderExpiredEvent(current_timestamp, tracked_limit_order.client_order_id)
                    )
                elif not previous_is_failure and tracked_limit_order.is_failure:
                    self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has failed "
                                       f"according to order status API.")
                    self.c_expire_order(tracked_limit_order.client_order_id, 30)
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(current_timestamp,
                                                tracked_limit_order.client_order_id,
                                                OrderType.LIMIT)
                    )
                elif not previous_is_done and tracked_limit_order.is_done:
                    self.c_expire_order(tracked_limit_order.client_order_id, 60)
                    # Remove from log tracking
                    await self._wallet.current_backend.zeroex_fill_watcher.unwatch_order_hash(tracked_limit_order.exchange_order_id)
                    if tracked_limit_order.trade_type is TradeType.BUY:
                        self.logger().info(f"The limit buy order {tracked_limit_order.client_order_id} "
                                           f"has completed according to order status API.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(current_timestamp,
                                                                    tracked_limit_order.client_order_id,
                                                                    tracked_limit_order.base_asset,
                                                                    tracked_limit_order.quote_asset,
                                                                    tracked_limit_order.quote_asset,
                                                                    tracked_limit_order.executed_amount_base,
                                                                    tracked_limit_order.executed_amount_quote,
                                                                    tracked_limit_order.protocol_fee_amount,
                                                                    OrderType.LIMIT))
                    else:
                        self.logger().info(f"The limit sell order {tracked_limit_order.client_order_id} "
                                           f"has completed according to order status API.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(current_timestamp,
                                                                     tracked_limit_order.client_order_id,
                                                                     tracked_limit_order.base_asset,
                                                                     tracked_limit_order.quote_asset,
                                                                     tracked_limit_order.quote_asset,
                                                                     tracked_limit_order.executed_amount_base,
                                                                     tracked_limit_order.executed_amount_quote,
                                                                     tracked_limit_order.protocol_fee_amount,
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
                # Receipt exists and has been mined
                if receipt is None or receipt["blockNumber"] is None:
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
                    gas_used = float(receipt.get("gasUsed", 0.0))
                    self.c_trigger_event(
                        self.MARKET_ORDER_FILLED_EVENT_TAG,
                        OrderFilledEvent(
                            self._current_timestamp,
                            tracked_market_order.client_order_id,
                            tracked_market_order.trading_pair,
                            tracked_market_order.trade_type,
                            OrderType.MARKET,
                            tracked_market_order.price,
                            tracked_market_order.amount,
                            TradeFee(0.0, [("ETH", gas_used), ("ETH", tracked_market_order.protocol_fee_amount)]),
                            tracked_market_order.tx_hash  # Use tx hash for market order validation
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
                                                                    tracked_market_order.protocol_fee_amount,
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
                                                                     tracked_market_order.protocol_fee_amount,
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
                        try:
                            receipt = self._w3.eth.getTransactionReceipt(tx_hash)
                            self._pending_approval_tx_hashes.remove(tx_hash)
                        except TransactionNotFound:
                            pass
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

    def get_order_hash_hex(self, unsigned_order: Dict[str, Any]) -> str:
        order_struct = jsdict_order_to_struct(unsigned_order)
        order_hash_hex = "0x" + generate_order_hash_hex(
            order=order_struct,
            exchange_address=self._exchange_address.lower(),
            chain_id=unsigned_order["chainId"]
        )
        return order_hash_hex

    def get_zero_ex_signature(self, order_hash_hex: str) -> str:
        signature = self._wallet.current_backend.sign_hash(hexstr=order_hash_hex)
        fixed_signature = fix_signature(self._provider,
                                        self._wallet.address,
                                        order_hash_hex,
                                        signature,
                                        self._chain_id)
        return fixed_signature

    cdef list c_get_orders_for_amount_price(self,
                                            str trading_pair,
                                            object trade_type,
                                            object amount,
                                            object price):
        cdef:
            object amount_filled = s_decimal_0
            object active_orders
            object current_item
            object current_price
            list found_orders = []
            list found_hashes = []

        active_orders = self._order_book_tracker.get_active_order_tracker(trading_pair=trading_pair)

        try:
            if trade_type is TradeType.BUY:
                active_asks = active_orders.active_asks
                ask_keys = sorted(active_asks.keys())
                for current_price in ask_keys:
                    # Market orders don't care about price
                    if not price.is_nan() and current_price > price:
                        raise StopIteration
                    if current_price not in active_asks:
                        continue
                    for order_hash in active_asks[current_price]:
                        if order_hash in self._filled_order_hashes or order_hash in found_hashes:
                            continue
                        order = active_asks[current_price][order_hash]
                        amount_filled += Decimal(order["remainingBaseTokenAmount"])
                        found_orders.append(order)
                        found_hashes.append(order_hash)
                        if amount_filled >= amount:
                            raise StopIteration
            if trade_type is TradeType.SELL:
                active_bids = active_orders.active_bids
                bid_keys = sorted(active_bids.keys(), reverse=True)
                for current_price in bid_keys:
                    # Market orders don't care about price
                    if not price.is_nan() and current_price < price:
                        raise StopIteration
                    if current_price not in active_bids:
                        continue
                    for order_hash in active_bids[current_price]:
                        if order_hash in self._filled_order_hashes or order_hash in found_hashes:
                            continue
                        order = active_bids[current_price][order_hash]
                        amount_filled += Decimal(order["remainingBaseTokenAmount"])
                        found_orders.append(order)
                        found_hashes.append(order_hash)
                        if amount_filled >= amount:
                            raise StopIteration
        except StopIteration:
            pass

        return found_orders

    async def submit_market_order(self,
                                  trading_pair: str,
                                  trade_type: TradeType,
                                  amount: Decimal,
                                  price: Decimal) -> Tuple[Decimal, Decimal, str, int, bool]:
        if trade_type is not TradeType.BUY and trade_type is not TradeType.SELL:
            raise ValueError("Invalid trade_type. Aborting.")

        valid_orders = self.c_get_orders_for_amount_price(trading_pair=trading_pair,
                                                          trade_type=trade_type,
                                                          amount=amount,
                                                          price=Decimal(price))

        if len(valid_orders) == 0:
            raise ValueError(f"No valid orders found for amount {amount} and price {price}.")

        # Skip API use orderbook
        total_base_token_amount = s_decimal_0
        total_quote_token_amount = s_decimal_0
        taker_asset_fill_amount = s_decimal_0
        calculated_price = s_decimal_0
        trading_pair_rules = self.trading_rules.get(trading_pair)
        base_asset_increment = trading_pair_rules.min_base_amount_increment
        base_asset_decimals = -int(math.ceil(math.log10(float(base_asset_increment))))
        max_base_amount_with_decimals = Decimal(amount) * Decimal(f"1e{base_asset_decimals}")
        quote_asset_increment = trading_pair_rules.min_quote_amount_increment
        quote_asset_decimals = -int(math.ceil(math.log10(float(quote_asset_increment))))
        is_coordinated = False
        tx_hash = ""
        protocol_fee = s_decimal_0

        # Single fill logic
        if len(valid_orders) == 1:
            apiOrder = valid_orders[0]
            signed_market_order = apiOrder["zeroExOrder"]
            signature = signed_market_order["signature"]
            is_coordinated = apiOrder["isCoordinated"]
            order = jsdict_order_to_struct(signed_market_order)
            remaining_base_token_amount = Decimal(apiOrder["remainingBaseTokenAmount"])
            remaining_quote_token_amount = Decimal(apiOrder["remainingQuoteTokenAmount"])
            calculated_price = remaining_base_token_amount / remaining_quote_token_amount

            if not price.is_nan() and calculated_price > price:
                raise ValueError(f"Incorrect values for market order, price {calculated_price} is "
                                 f"worse than requested price {price}")

            # Sanity check on rates returned
            if trade_type is TradeType.BUY:
                if amount > remaining_base_token_amount:
                    total_base_token_amount = remaining_base_token_amount
                    total_quote_token_amount = remaining_quote_token_amount
                    taker_asset_fill_amount = (remaining_quote_token_amount * Decimal(f"1e{quote_asset_decimals}")).to_integral_exact(rounding=ROUND_FLOOR)
                else:
                    total_base_token_amount = amount
                    total_quote_token_amount = amount * calculated_price
                    taker_asset_fill_amount = (total_quote_token_amount * Decimal(f"1e{quote_asset_decimals}")).to_integral_exact(rounding=ROUND_FLOOR)
            else:
                if amount > remaining_base_token_amount:
                    total_base_token_amount = remaining_base_token_amount
                    total_quote_token_amount = remaining_quote_token_amount
                    taker_asset_fill_amount = (remaining_base_token_amount * Decimal(f"1e{base_asset_decimals}")).to_integral_exact(rounding=ROUND_FLOOR)
                else:
                    total_base_token_amount = amount
                    total_quote_token_amount = amount * calculated_price
                    taker_asset_fill_amount = max_base_amount_with_decimals.to_integral_exact(rounding=ROUND_FLOOR)
            if amount >= remaining_base_token_amount:
                self._filled_order_hashes.append(apiOrder["orderHash"])

            if is_coordinated:
                tx_hash, protocol_fee = await self._coordinator.fill_order(order, taker_asset_fill_amount, signature)
            else:
                tx_hash, protocol_fee = self._exchange.fill_order(order, taker_asset_fill_amount, signature)

            return total_base_token_amount, calculated_price, tx_hash, protocol_fee, is_coordinated

        taker_asset_fill_amounts: List[Decimal] = []
        signatures: List[str] = []
        orders: List[ZeroExOrder] = []

        # Else it's a multi fill
        for apiOrder in valid_orders:
            signed_market_order = apiOrder["zeroExOrder"]
            signatures.append(signed_market_order["signature"])
            orders.append(jsdict_order_to_struct(signed_market_order))
            is_coordinated = is_coordinated or apiOrder["isCoordinated"]
            order = jsdict_order_to_struct(signed_market_order)

            remaining_base_token_amount = Decimal(apiOrder["remainingBaseTokenAmount"])
            remaining_quote_token_amount = Decimal(apiOrder["remainingQuoteTokenAmount"])

            # This would overfill the last order
            if remaining_base_token_amount + total_base_token_amount > amount:
                order_price = remaining_quote_token_amount / remaining_base_token_amount
                remaining_base_token_amount = amount - total_base_token_amount
                remaining_quote_token_amount = remaining_base_token_amount * order_price
            else:
                self._filled_order_hashes.append(apiOrder["orderHash"])

            if trade_type is TradeType.BUY:
                taker_asset_fill_amounts.append((remaining_quote_token_amount * Decimal(f"1e{quote_asset_decimals}")).to_integral_exact(rounding=ROUND_FLOOR))
            else:
                taker_asset_fill_amounts.append((remaining_base_token_amount * Decimal(f"1e{base_asset_decimals}")).to_integral_exact(rounding=ROUND_FLOOR))

            total_base_token_amount += remaining_base_token_amount
            total_quote_token_amount += remaining_quote_token_amount

            if total_base_token_amount >= amount:
                break

        calculated_price = total_base_token_amount / total_quote_token_amount

        # Sanity check on rates returned
        if total_base_token_amount > amount:
            raise ValueError(f"API returned incorrect values for market order, total maker amount {total_base_token_amount} "
                             f"is greater than requested amount {amount}")
        elif not price.is_nan() and calculated_price > price:
            raise ValueError(f"Incorrect values for market order, price {calculated_price} is "
                             f"worse than requested price {price}")

        if is_coordinated:
            tx_hash, protocol_fee = await self._coordinator.batch_fill_orders(orders, taker_asset_fill_amounts, signatures)
        else:
            tx_hash, protocol_fee = self._exchange.batch_fill_orders(orders, taker_asset_fill_amounts, signatures)

        return total_base_token_amount, calculated_price, tx_hash, protocol_fee, is_coordinated

    async def submit_limit_order(self,
                                 trading_pair: str,
                                 trade_type: TradeType,
                                 is_coordinated: bool,
                                 amount: Decimal,
                                 price: Decimal,
                                 expires: int) -> Tuple[str, ZeroExOrder]:
        # It's faster to generate fresh orders client-side
        latest_salt = self._latest_salt

        if latest_salt < 0:
            latest_salt = int(math.floor(time.time()))
        else:
            latest_salt = latest_salt + 1

        trading_pair_rules = self.trading_rules.get(trading_pair)
        base_asset_increment = trading_pair_rules.min_base_amount_increment
        base_asset_decimals = -int(math.ceil(math.log10(float(base_asset_increment))))
        base_amount_with_decimals = Decimal(amount) * Decimal(f"1e{base_asset_decimals}")

        quote_asset_increment = trading_pair_rules.min_quote_amount_increment
        quote_asset_decimals = -int(math.ceil(math.log10(float(quote_asset_increment))))
        quote_amount = amount * price
        quote_amount_with_decimals = Decimal(quote_amount) * Decimal(f"1e{quote_asset_decimals}")

        maker_asset_amount = 0
        taker_asset_amount = 0
        maker_asset_data = ""
        taker_asset_data = ""

        pair_split = trading_pair.split("-")

        tokens = self._wallet.erc20_tokens
        base_token_asset_data = "0xf47261b0000000000000000000000000" + remove_0x_prefix(tokens[pair_split[0]].address.lower())
        quote_token_asset_data = "0xf47261b0000000000000000000000000" + remove_0x_prefix(tokens[pair_split[1]].address.lower())

        if trade_type is TradeType.BUY:
            maker_asset_amount = int(quote_amount_with_decimals)
            taker_asset_amount = int(base_amount_with_decimals)
            maker_asset_data = quote_token_asset_data
            taker_asset_data = base_token_asset_data
        else:
            maker_asset_amount = int(base_amount_with_decimals)
            taker_asset_amount = int(quote_amount_with_decimals)
            maker_asset_data = base_token_asset_data
            taker_asset_data = quote_token_asset_data

        null_address = "0x0000000000000000000000000000000000000000"

        unsigned_limit_order = {
            'chainId': self._chain_id,
            'exchangeAddress': self._exchange_address.lower(),
            'makerAddress': self._wallet.address.lower(),
            'takerAddress': null_address,
            'feeRecipientAddress': self._fee_recipient_address,
            'senderAddress': self._coordinator_address.lower() if self._use_coordinator else null_address,
            'makerAssetAmount': str(maker_asset_amount),
            'takerAssetAmount': str(taker_asset_amount),
            'makerFee': '0',
            'takerFee': '0',
            'expirationTimeSeconds': str(expires),
            'salt': str(latest_salt),
            'makerAssetData': maker_asset_data,
            'takerAssetData': taker_asset_data,
            'makerFeeAssetData': maker_asset_data,
            'takerFeeAssetData': maker_asset_data
        }

        order_hash_hex = self.get_order_hash_hex(unsigned_limit_order)
        signed_limit_order = copy.deepcopy(unsigned_limit_order)
        signature = self.get_zero_ex_signature(order_hash_hex)
        signed_limit_order["signature"] = signature
        try:
            await self._api_request(http_method="post",
                                    url=f"{self._api_endpoint}{self._api_prefix}/orders",
                                    data=signed_limit_order,
                                    headers={"User-Agent": "hummingbot"})
            self._latest_salt = latest_salt
            order_hash = self._w3.toHex(hexstr=order_hash_hex)
            zero_ex_order = jsdict_order_to_struct(unsigned_limit_order)
            return order_hash, zero_ex_order
        except Exception as ex:
            self._last_failed_limit_order_timestamp = self._current_timestamp
            raise ex

    cdef c_cancel(self, str trading_pair, str client_order_id):
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
        cdef:
            int order_timestamp_diff
            double current_timestamp

        in_flight_limit_orders = self._in_flight_limit_orders.values()
        incomplete_order_ids = []
        incomplete_orders = []
        has_coordinated_order = False

        for order in in_flight_limit_orders:
            if not (order.is_done or
                    order.is_cancelled or
                    order.is_expired or
                    order.is_failure or
                    order.has_been_cancelled or
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

                # if the market is force stopped then _current_timestamp is NaN
                current_timestamp = math.isnan(self._current_timestamp) if time.time() else self._current_timestamp
                # Flag
                order_ids = ""
                for order in incomplete_orders:
                    order.has_been_cancelled = True
                    # Maximum fill time for a coordinated order is 90 seconds or the order expiry
                    order_timestamp_diff = abs(order.expires - int(current_timestamp))
                    self.c_expire_order(order.client_order_id, min(order_timestamp_diff, 130))
                    self.c_trigger_event(
                        self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                        OrderCancelledEvent(current_timestamp, order.client_order_id)
                    )
                    order_ids = order_ids + order.client_order_id + " "

                self.logger().info(f"The limit orders {order_ids}have been soft cancelled according "
                                   f"to the Coordinator server.")

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
                    while receipt is None or receipt["blockNumber"] is None:
                        receipt = self.get_tx_hash_receipt(tx_hash)
                        # Receipt exists and has been mined
                        if receipt is None or receipt["blockNumber"] is None:
                            await asyncio.sleep(6.0)
                            continue
                        if receipt["status"] == 0:
                            return [CancellationResult(oid, False) for oid in incomplete_order_ids]
                        elif receipt["status"] == 1:
                            order_ids = ""
                            # if the market is force stopped then _current_timestamp is NaN
                            current_timestamp = math.isnan(self._current_timestamp) if time.time() else self._current_timestamp
                            for order in incomplete_orders:
                                order.has_been_cancelled = True
                                self.c_expire_order(order.client_order_id, 10)
                                self.c_trigger_event(
                                    self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                    OrderCancelledEvent(current_timestamp, order.client_order_id)
                                )
                                order_ids = order_ids + order.client_order_id + " "

                            self.logger().info(f"The limit orders {order_ids}have been hard cancelled according "
                                               f"to transaction hash {tx_hash}.")

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
                            trading_pair: str,
                            amount: Decimal,
                            price: Decimal,
                            expires: int) -> str:
        cdef:
            object q_price
            object q_amt = self.c_quantize_order_amount(trading_pair, amount)
            object amount_to_fill = q_amt
            TradingRule trading_rule = self._trading_rules[trading_pair]
            str trade_type_desc = trade_type.name.lower()
            str type_str = order_type.name.lower()
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
                    q_price = self.c_quantize_order_price(trading_pair, price)
                    exchange_order_id, zero_ex_order = await self.submit_limit_order(trading_pair=trading_pair,
                                                                                     trade_type=trade_type,
                                                                                     is_coordinated=self._use_coordinator,
                                                                                     amount=q_amt,
                                                                                     price=q_price,
                                                                                     expires=expires)
                    self.c_start_tracking_limit_order(order_id=order_id,
                                                      exchange_order_id=exchange_order_id,
                                                      trading_pair=trading_pair,
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
                (amount_to_fill,
                 avg_price,
                 tx_hash,
                 protocol_fee,
                 is_coordinated) = await self.submit_market_order(trading_pair=trading_pair,
                                                                  trade_type=trade_type,
                                                                  amount=q_amt,
                                                                  price=price)
                q_price = self.c_quantize_order_price(trading_pair, Decimal(avg_price))
                self.c_start_tracking_market_order(order_id=order_id,
                                                   trading_pair=trading_pair,
                                                   order_type=order_type,
                                                   is_coordinated=is_coordinated,
                                                   trade_type=trade_type,
                                                   price=q_price,
                                                   amount=amount_to_fill,
                                                   protocol_fee_amount=protocol_fee / Decimal(1e18),
                                                   tx_hash=tx_hash)
            # Market events not market orders
            if trade_type is TradeType.BUY:
                self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                     BuyOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         trading_pair,
                                         amount_to_fill,
                                         q_price,
                                         order_id
                                     ))
            else:
                self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                     SellOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         trading_pair,
                                         amount_to_fill,
                                         q_price,
                                         order_id
                                     ))
            return order_id
        except Exception:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {type_str} {trade_type_desc} order to Bamboo Relay for {str(q_amt)} {trading_pair}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit {type_str} {trade_type_desc} order to Bamboo Relay. "
                                f"Check Ethereum wallet and network connection."
            )
            self.c_trigger_event(
                self.MARKET_ORDER_FAILURE_EVENT_TAG,
                MarketOrderFailureEvent(self._current_timestamp, order_id, order_type)
            )

    cdef str c_buy(self,
                   str trading_pair,
                   object amount,
                   object order_type=OrderType.MARKET,
                   object price=s_decimal_NaN,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")
            double current_timestamp = self._current_timestamp
        expires = kwargs.get("expiration_ts", None)
        if expires is not None and not math.isnan(expires):
            expires = int(expires)
        else:
            expires = int(current_timestamp) + 120
        if order_type is OrderType.LIMIT:
            # Don't spam the server endpoint if a order placement failed recently
            if current_timestamp - self._last_failed_limit_order_timestamp <= self.ORDER_CREATION_BACKOFF_TIME:
                raise
            # Record the in-flight limit order placement.
            self._in_flight_pending_limit_orders[order_id] = self._current_timestamp
        safe_ensure_future(self.execute_trade(order_id=order_id,
                                              order_type=order_type,
                                              trade_type=TradeType.BUY,
                                              trading_pair=trading_pair,
                                              amount=amount,
                                              price=price,
                                              expires=expires))
        return order_id

    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.MARKET,
                    object price=s_decimal_NaN,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")
            double current_timestamp = self._current_timestamp
        expires = kwargs.get("expiration_ts", None)
        if expires is not None and not math.isnan(expires):
            expires = int(expires)
        else:
            expires = int(current_timestamp) + 120
        if order_type is OrderType.LIMIT:
            # Don't spam the server endpoint if a order placement failed recently
            if current_timestamp - self._last_failed_limit_order_timestamp <= self.ORDER_CREATION_BACKOFF_TIME:
                raise
            # Record the in-flight limit order placement.
            self._in_flight_pending_limit_orders[order_id] = self._current_timestamp
        safe_ensure_future(self.execute_trade(order_id=order_id,
                                              order_type=order_type,
                                              trade_type=TradeType.SELL,
                                              trading_pair=trading_pair,
                                              amount=amount,
                                              price=price,
                                              expires=expires))
        return order_id

    async def cancel_order(self, client_order_id: str) -> CancellationResult:
        cdef:
            BambooRelayInFlightOrder order = self._in_flight_limit_orders.get(client_order_id)
            int order_timestamp_diff
            double current_timestamp

        if not order:
            self.logger().info(f"Failed to cancel order {client_order_id}. Order not found in tracked orders.")
            if client_order_id in self._in_flight_cancels:
                del self._in_flight_cancels[client_order_id]
            return {}

        # Previously cancelled
        if order.is_cancelled or order.has_been_cancelled:
            if client_order_id in self._in_flight_cancels:
                del self._in_flight_cancels[client_order_id]
            return {}

        if order.is_coordinated:
            await self._coordinator.soft_cancel_order(order.zero_ex_order)

            # Flag it
            order.has_been_cancelled = True

            self.logger().info(f"The limit order {order.client_order_id} has been soft cancelled according "
                               f"to the Coordinator server.")
            # Maximum fill time for a coordinated order is 90 seconds or the order expiry
            current_timestamp = math.isnan(self._current_timestamp) if time.time() else self._current_timestamp
            order_timestamp_diff = abs(order.expires - int(current_timestamp))
            self.c_expire_order(order.client_order_id, min(order_timestamp_diff, 130))
            self.c_trigger_event(
                self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                OrderCancelledEvent(current_timestamp, order.client_order_id)
            )

            return CancellationResult(client_order_id, True)
        else:
            tx_hash = self._exchange.cancel_order(order.zero_ex_order)

            receipt = None
            try:
                while receipt is None or receipt["blockNumber"] is None:
                    receipt = self.get_tx_hash_receipt(tx_hash)
                    if receipt is None or receipt["blockNumber"] is None:
                        await asyncio.sleep(6.0)
                        continue
                    if receipt["status"] == 0:
                        return CancellationResult(client_order_id, False)
                    elif receipt["status"] == 1:
                        # Flag
                        order.has_been_cancelled = True
                        current_timestamp = math.isnan(self._current_timestamp) if time.time() else self._current_timestamp
                        self.logger().info(f"The limit order {order.client_order_id} has been hard cancelled according "
                                           f"to transaction hash {tx_hash}.")
                        self.c_expire_order(order.client_order_id, 10)
                        self.c_trigger_event(
                            self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                            OrderCancelledEvent(current_timestamp, order.client_order_id)
                        )

                        return CancellationResult(client_order_id, True)
            except Exception:
                self.logger().network(
                    f"Unexpected error cancelling order.",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel order on Bamboo Relay. "
                                    f"Check Ethereum wallet and network connection."
                )

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def get_tx_hash_receipt(self, tx_hash: str) -> Dict[str, Any]:
        try:
            tx_hash_receipt = self._w3.eth.getTransactionReceipt(tx_hash)
            return tx_hash_receipt
        except TransactionNotFound:
            return None

    async def list_account_orders(self) -> List[Dict[str, Any]]:
        url = f"{self._api_endpoint}{self._api_prefix}/accounts/{self._wallet.address.lower()}/orders"
        response_data = await self._api_request("get", url=url, headers={"User-Agent": "hummingbot"})
        return response_data

    def wrap_eth(self, amount: float) -> str:
        return self._wallet.wrap_eth(amount)

    def unwrap_eth(self, amount: float) -> str:
        return self._wallet.unwrap_eth(amount)

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    async def start_network(self):
        self._stop_network()
        self._order_book_tracker.start()
        self._status_polling_task = safe_ensure_future(self._status_polling_loop())
        if self._trading_required:
            tx_hashes = await self.wallet.current_backend.check_and_fix_approval_amounts(
                spender=self._wallet_spender_address
            )
            self._pending_approval_tx_hashes.update(tx_hashes)
            self._approval_tx_polling_task = safe_ensure_future(self._approval_tx_polling_loop())

    def _stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._pending_approval_tx_hashes is not None:
            self._pending_approval_tx_hashes.clear()
        if self._approval_tx_polling_task is not None:
            self._approval_tx_polling_task.cancel()
        self._status_polling_task = self._approval_tx_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        if self._wallet.network_status is not NetworkStatus.CONNECTED:
            return NetworkStatus.NOT_CONNECTED

        try:
            await self._api_request("GET", f"{self._api_endpoint}{self._api_prefix}/tokens",
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
        ExchangeBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self.c_check_and_remove_expired_orders()
        self._last_timestamp = timestamp

    cdef c_start_tracking_limit_order(self,
                                      str order_id,
                                      str exchange_order_id,
                                      str trading_pair,
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
            trading_pair=trading_pair,
            order_type=order_type,
            is_coordinated=is_coordinated,
            trade_type=trade_type,
            price=price,
            amount=amount,
            expires=expires,
            tx_hash=None,
            zero_ex_order=zero_ex_order
        )
        # Watch for Fill events for this order hash
        safe_ensure_future(self._wallet.current_backend.zeroex_fill_watcher.watch_order_hash(exchange_order_id, self._update_single_limit_order))

    cdef c_start_tracking_market_order(self,
                                       str order_id,
                                       str trading_pair,
                                       object order_type,
                                       bint is_coordinated,
                                       object trade_type,
                                       object price,
                                       object amount,
                                       str tx_hash,
                                       object protocol_fee_amount):
        self._in_flight_market_orders[tx_hash] = BambooRelayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            is_coordinated=is_coordinated,
            trade_type=trade_type,
            price=price,
            amount=amount,
            expires=0,
            tx_hash=tx_hash,
            protocol_fee_amount=protocol_fee_amount
        )

    cdef c_expire_order(self, str order_id, int seconds):
        self._order_expiry_queue.append((self._current_timestamp + seconds, order_id))

    cdef c_check_and_remove_expired_orders(self):
        cdef:
            double current_timestamp = self._current_timestamp
            str order_id

        while len(self._order_expiry_queue) > 0 and self._order_expiry_queue[0][0] < current_timestamp:
            _, order_id = self._order_expiry_queue.popleft()
            self.c_stop_tracking_order(order_id)

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_limit_orders:
            # Unwatch this order hash from Fill events
            safe_ensure_future(self._wallet.current_backend.zeroex_fill_watcher.unwatch_order_hash(self._in_flight_limit_orders[order_id].exchange_order_id))
            del self._in_flight_limit_orders[order_id]
        elif order_id in self._in_flight_market_orders:
            del self._in_flight_market_orders[order_id]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        decimals_quantum = trading_rule.min_quote_amount_increment
        if price.is_finite() and price > s_decimal_0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(price)) - trading_rule.max_price_significant_digits}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_get_order_size_quantum(self, str trading_pair, object amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        decimals_quantum = trading_rule.min_base_amount_increment

        if amount.is_finite() and amount > s_decimal_0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(amount)) - trading_rule.max_price_significant_digits}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        global s_decimal_0
        quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, min(amount, trading_rule.max_order_size))

        # Check against min_order_size. If not passing the check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        return quantized_amount

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
