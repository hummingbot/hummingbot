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
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bamboo_relay.bamboo_relay_api_order_book_data_source import BambooRelayAPIOrderBookDataSource
from hummingbot.market.bamboo_relay.bamboo_relay_order_book_tracker import BambooRelayOrderBookTracker
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import (
    MarketBase,
    OrderType,
    NaN
)
from hummingbot.market.utils import (
    zrx_order_to_json,
    json_to_zrx_order
)
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.wallet.ethereum.zero_ex.zero_ex_custom_utils import fix_signature
from hummingbot.wallet.ethereum.zero_ex.zero_ex_exchange import ZeroExExchange
from hummingbot.wallet.ethereum.zero_ex.zero_ex_coordinator import ZeroExCoordinator

brm_logger = None
s_decimal_0 = Decimal(0)

ZERO_EX_MAINNET_ERC20_PROXY = "0x2240dab907db71e64d3e0dba4800c83b5c502d4e"
ZERO_EX_MAINNET_EXCHANGE_ADDRESS = "0x4f833a24e1f95d70f028921e27040ca56e09ab0b"
ZERO_EX_MAINNET_COORDINATOR_ADDRESS = "0x25aae5b981ce6683cc5aeea1855d927e0b59066f"
ZERO_EX_MAINNET_COORDINATOR_REGISTRY_ADDRESS = "0x45797531b873fd5e519477a070a955764c1a5b07"

ZERO_EX_ROPSTEN_ERC20_PROXY = "0xb1408f4c245a23c31b98d2c626777d4c0d766caa"
ZERO_EX_ROPSTEN_EXCHANGE_ADDRESS = "0x4530c0483a1633c7a1c97d2c53721caff2caaaaf"
ZERO_EX_ROPSTEN_COORDINATOR_ADDRESS = "0x25aae5b981ce6683cc5aeea1855d927e0b59066f"
ZERO_EX_ROPSTEN_COORDINATOR_REGISTRY_ADDRESS = "0x403cc23e88c17c4652fb904784d1af640a6722d9"

ZERO_EX_RINKEBY_ERC20_PROXY = "0x2f5ae4f6106e89b4147651688a92256885c5f410"
ZERO_EX_RINKEBY_EXCHANGE_ADDRESS = "0xbce0b5f6eb618c565c3e5f5cd69652bbc279f44e"
ZERO_EX_RINKEBY_COORDINATOR_ADDRESS = "0x25aae5b981ce6683cc5aeea1855d927e0b59066f"
ZERO_EX_RINKEBY_COORDINATOR_REGISTRY_ADDRESS = "0x1084b6a398e47907bae43fec3ff4b677db6e4fee"

ZERO_EX_KOVAN_ERC20_PROXY = "0xf1ec01d6236d3cd881a0bf0130ea25fe4234003e"
ZERO_EX_KOVAN_EXCHANGE_ADDRESS = "0x35dd2932454449b14cee11a94d3674a936d5d7b2"
ZERO_EX_KOVAN_COORDINATOR_ADDRESS = "0x25aae5b981ce6683cc5aeea1855d927e0b59066f"
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


cdef class TradingRule:
    cdef:
        public str symbol
        public double min_order_size            # Calculated min base token size based on last trade price
        public double max_order_size            # Calculated max base token size
        public int price_precision              # Maximum precision allowed for the market. Example: 7 (decimal places)
        public int price_decimals               # Max amount of decimals in base token (price)
        public int amount_decimals              # Max amount of decimals in quote token (amount)

    @classmethod
    def parse_exchange_info(cls, markets: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list retval = []
        for market in markets:
            try:
                symbol = market["id"]
                retval.append(TradingRule(symbol,
                                          float(market["minOrderSize"]),
                                          float(market["maxOrderSize"]),
                                          market["quoteIncrement"],
                                          market["quoteTokenDecimals"],
                                          market["baseTokenDecimals"]))
            except Exception:
                BambooRelayMarket.logger().error(f"Error parsing the symbol {symbol}. Skipping.", exc_info=True)
        return retval

    def __init__(self,
                 symbol: str,
                 min_order_size: float,
                 max_order_size: float,
                 price_precision: int,
                 price_decimals: int,
                 amount_decimals: int):
        self.symbol = symbol
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size
        self.price_precision = price_precision
        self.price_decimals = price_decimals
        self.amount_decimals = amount_decimals

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', min_order_size={self.min_order_size}, " \
               f"max_order_size={self.max_order_size}, price_precision={self.price_precision}, "\
               f"price_decimals={self.price_decimals}, amount_decimals={self.amount_decimals}"


cdef class InFlightOrder:
    cdef:
        public str client_order_id
        public str exchange_order_id,
        public str tx_hash,
        public str symbol
        public bint is_buy
        public object order_type
        public bint is_coordinated
        public object amount
        public object price
        public int expires
        public object executed_amount
        public object available_amount
        public object quote_asset_amount
        public object gas_fee_amount
        public str last_state
        public object zero_ex_order

    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 tx_hash: str,
                 symbol: str,
                 is_buy: bool,
                 order_type: OrderType,
                 is_coordinated: bool,
                 amount: Decimal,
                 price: Decimal,
                 expires: int = None,
                 zero_ex_order: ZeroExOrder = None):
        self.client_order_id = client_order_id
        self.exchange_order_id = exchange_order_id
        self.tx_hash = tx_hash
        self.symbol = symbol
        self.is_buy = is_buy
        self.order_type = order_type
        self.is_coordinated = is_coordinated
        self.amount = amount # initial amount (constant)
        self.available_amount = amount
        self.price = price
        self.expires = expires
        self.executed_amount = s_decimal_0
        self.quote_asset_amount = s_decimal_0
        self.gas_fee_amount = s_decimal_0
        self.last_state = "OPEN"
        self.zero_ex_order = zero_ex_order

    def __repr__(self) -> str:
        return f"InFlightOrder(client_order_id='{self.client_order_id}', exchange_order_id='{self.exchange_order_id}', " \
               f"tx_hash='{self.tx_hash}', symbol='{self.symbol}', is_buy={self.is_buy}, order_type={self.order_type}, " \
               f"is_coordinated={self.is_coordinated}, amount={self.amount}, available_amount={self.available_amount}, " \
               f"price={self.price}, executed_amount={self.executed_amount}, quote_asset_amount={self.quote_asset_amount}, "\
               f"gas_fee_amount={self.gas_fee_amount}, last_state='{self.last_state}', zero_ex_order='{self.zero_ex_order}')"

    @property
    def is_done(self) -> bool:
        return self.available_amount == s_decimal_0

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CANCELED", "CANCELLED"}

    @property
    def is_expired(self) -> bool:
        return self.last_state in {"EXPIRED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"UNFUNDED"}

    @property
    def base_asset(self) -> str:
        return self.symbol.split('-')[0]

    @property
    def quote_asset(self) -> str:
        return self.symbol.split('-')[1]

    def to_json(self) -> Dict[str, any]:
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "tx_hash": self.tx_hash,
            "symbol": self.symbol,
            "is_buy": self.is_buy,
            "order_type": self.order_type.name,
            "is_coordinated": self.is_coordinated,
            "amount": str(self.amount),
            "price": str(self.price),
            "expires": self.expires,
            "executed_amount": str(self.executed_amount),
            "available_amount": str(self.available_amount),
            "quote_asset_amount": str(self.quote_asset_amount),
            "gas_fee_amount": str(self.gas_fee_amount),
            "last_state": self.last_state,
            "zero_ex_order": zrx_order_to_json(self.zero_ex_order)
        }

    @classmethod
    def from_json(cls, data: Dict[str, any]) -> "InFlightOrder":
        cdef:
            InFlightOrder retval = InFlightOrder(
                data["client_order_id"],
                data["exchange_order_id"],
                data["tx_hash"],
                data["symbol"],
                data["is_buy"],
                getattr(OrderType, data["order_type"]),
                bool(data["is_coordinated"]),
                Decimal(data["amount"]),
                Decimal(data["price"]),
                data["expires"],
                zero_ex_order=json_to_zrx_order(data["zero_ex_order"])
            )
        retval.available_amount = Decimal(data["available_amount"])
        retval.executed_amount = Decimal(data["executed_amount"])
        retval.quote_asset_amount = Decimal(data["quote_asset_amount"])
        retval.gas_fee_amount = Decimal(data["gas_fee_amount"])
        retval.last_state = data["last_state"]
        return retval

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
                 chain: EthereumChain = EthereumChain.MAIN_NET,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                    OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None,
                 use_coordinator: Optional[bool] = True,
                 pre_emptive_soft_cancels: Optional[bool] = True):
        cdef:
            str coordinator_address
            str coordinator_registry_address
        super().__init__()
        self._order_book_tracker = BambooRelayOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                               symbols=symbols,
                                                               chain=chain)
        self._account_balances = {}
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_failed_limit_order_timestamp = 0
        self._last_update_limit_order_timestamp = 0
        self._last_update_market_order_timestamp = 0
        self._last_update_trading_rules_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_limit_orders = {} # limit orders are off chain
        self._in_flight_market_orders = {} # market orders are on chain
        self._in_flight_pending_limit_orders = OrderedDict() # in the case that an order needs to be cancelled before its been accepted
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
        self._chain = chain
        self._wallet = wallet
        self._use_coordinator = use_coordinator
        self._pre_emptive_soft_cancels = pre_emptive_soft_cancels
        self._latest_salt = -1
        if chain is EthereumChain.MAIN_NET:
            self._api_prefix = "main/0x"
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_EXCHANGE_ADDRESS)
            coordinator_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_MAINNET_ERC20_PROXY)
        elif chain is EthereumChain.ROPSTEN:
            self._api_prefix = "ropsten/0x"
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_EXCHANGE_ADDRESS)
            coordinator_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_ROPSTEN_ERC20_PROXY)
        elif chain is EthereumChain.RINKEBY:
            self._api_prefix = "rinkeby/0x"
            self._exchange_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_EXCHANGE_ADDRESS)
            coordinator_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_COORDINATOR_ADDRESS)
            coordinator_registry_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_COORDINATOR_REGISTRY_ADDRESS)
            self._wallet_spender_address = Web3.toChecksumAddress(ZERO_EX_RINKEBY_ERC20_PROXY)
        elif chain is EthereumChain.KOVAN:
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
                                              wallet,
                                              chain)

    @property
    def name(self) -> str:
        return "bamboo_relay"

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
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_limit_orders(self) -> Dict[str, InFlightOrder]:
        return self._in_flight_limit_orders

    @property
    def in_flight_market_orders(self) -> Dict[str, InFlightOrder]:
        return self._in_flight_market_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            list retval = []
            InFlightOrder typed_in_flight_order
            str base_currency
            str quote_currency
            set expiring_order_ids = set([order_id for _, order_id in self._order_expiry_queue])

        for in_flight_order in self._in_flight_limit_orders.values():
            typed_in_flight_order = in_flight_order
            if typed_in_flight_order.order_type is not OrderType.LIMIT:
                continue
            if typed_in_flight_order.client_order_id in expiring_order_ids:
                continue
            base_currency, quote_currency = in_flight_order.symbol.split("-")
            retval.append(LimitOrder(
                typed_in_flight_order.client_order_id,
                typed_in_flight_order.symbol,
                typed_in_flight_order.is_buy,
                base_currency,
                quote_currency,
                Decimal(in_flight_order.price),
                Decimal(in_flight_order.amount)
            ))
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
        self._in_flight_market_orders.update({
            key: InFlightOrder.from_json(value)
            for key, value in saved_states["market_orders"].items()
        })
        self._in_flight_limit_orders.update({
            key: InFlightOrder.from_json(value)
            for key, value in saved_states["limit_orders"].items()
        })

    async def get_active_exchange_markets(self):
        return await BambooRelayAPIOrderBookDataSource.get_active_exchange_markets()

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                self._update_balances()
                await asyncio.gather(
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
                          object order_side,
                          double amount,
                          double price):
        cdef:
            int gas_estimate = 130000 # approximate gas used for 0x market orders
            double transaction_cost_eth

        # there are no fees for makers on Bamboo Relay
        if order_type is OrderType.LIMIT:
            return TradeFee(percent=0.0)
        # only fee for takers is gas cost of transaction
        transaction_cost_eth = self._wallet.gas_price * gas_estimate / 1e18
        return TradeFee(percent=0.0, flat_fees=[("ETH", transaction_cost_eth)])

    def _update_balances(self):
        self._account_balances = self.wallet.get_all_balances()

    async def list_market(self) -> Dict[str, Any]:
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/markets?include=base"
        return await self._api_request(http_method="get", url=url, headers={"User-Agent":"hummingbot"})

    async def _update_trading_rules(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_trading_rules_timestamp > self.UPDATE_RULES_INTERVAL or len(self._trading_rules) < 1:
            markets = await self.list_market()
            trading_rules_list = TradingRule.parse_exchange_info(markets)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule
            self._last_update_trading_rules_timestamp = current_timestamp

    async def get_account_orders(self) -> List[Dict[str, Any]]:
        list_account_orders_url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/accounts/{self._wallet.address}/orders"
        return await self._api_request(http_method="get", url=list_account_orders_url, headers={"User-Agent":"hummingbot"})

    async def get_order(self, order_hash: str) -> Dict[str, Any]:
        order_url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/orders/{order_hash}"
        return await self._api_request("get", url=order_url, headers={"User-Agent":"hummingbot"})

    async def _get_order_updates(self, tracked_limit_orders: List[InFlightOrder]) -> List[Dict[str, Any]]:
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

        res_order_updates = await asyncio.gather(*tasks, return_exceptions=True)

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
                order_executed_amount = Decimal(tracked_limit_order.available_amount) - order_remaining_base_token_amount
                total_executed_amount = Decimal(tracked_limit_order.amount) - order_remaining_base_token_amount

                tracked_limit_order.last_state = order_state
                tracked_limit_order.executed_amount = total_executed_amount
                tracked_limit_order.available_amount = order_remaining_base_token_amount
                tracked_limit_order.quote_asset_amount = order_remaining_quote_token_amount
                if order_executed_amount > 0:
                    self.logger().info(f"Filled {order_executed_amount} out of {tracked_limit_order.amount} of the "
                        f"limit order {tracked_limit_order.client_order_id}.")
                    self.c_trigger_event(
                        self.MARKET_ORDER_FILLED_EVENT_TAG,
                        OrderFilledEvent(
                            self._current_timestamp,
                            tracked_limit_order.client_order_id,
                            tracked_limit_order.symbol,
                            TradeType.BUY if tracked_limit_order.is_buy else TradeType.SELL,
                            OrderType.LIMIT,
                            tracked_limit_order.price,
                            order_executed_amount,
                            TradeFee(0.0) # no fee for limit order fills
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
                    self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has failed"
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
                    if tracked_limit_order.is_buy:
                        self.logger().info(f"The limit buy order {tracked_limit_order.client_order_id}"
                                           f"has completed according to order status API.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_limit_order.client_order_id,
                                                                    tracked_limit_order.base_asset,
                                                                    tracked_limit_order.quote_asset,
                                                                    tracked_limit_order.quote_asset,
                                                                    float(tracked_limit_order.executed_amount),
                                                                    float(tracked_limit_order.quote_asset_amount),
                                                                    float(tracked_limit_order.gas_fee_amount),
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
                                                                     float(tracked_limit_order.executed_amount),
                                                                     float(tracked_limit_order.quote_asset_amount),
                                                                     float(tracked_limit_order.gas_fee_amount),
                                                                     OrderType.LIMIT))
                elif self._pre_emptive_soft_cancels and (
                     tracked_limit_order.is_coordinated and
                     not tracked_limit_order.is_cancelled and 
                     not tracked_limit_order.is_expired and 
                     not tracked_limit_order.is_failure and
                     not tracked_limit_order.is_done and
                     tracked_limit_order.expires <= current_timestamp + self.PRE_EMPTIVE_SOFT_CANCEL_TIME):
                        if tracked_limit_order.is_buy:
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
                    gas_used = float(receipt.get("gasUsed", 0.0))
                    self.c_trigger_event(
                        self.MARKET_ORDER_FILLED_EVENT_TAG,
                        OrderFilledEvent(
                            self._current_timestamp,
                            tracked_market_order.client_order_id,
                            tracked_market_order.symbol,
                            TradeType.BUY if tracked_market_order.is_buy else TradeType.SELL,
                            OrderType.MARKET,
                            tracked_market_order.price,
                            tracked_market_order.amount,
                            TradeFee(0.0, [("ETH", gas_used)])
                        )
                    )
                    if tracked_market_order.is_buy:
                        self.logger().info(f"The market buy order "
                                           f"{tracked_market_order.client_order_id} has completed according to "
                                           f"transaction hash {tracked_market_order.tx_hash}.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_market_order.client_order_id,
                                                                    tracked_market_order.base_asset,
                                                                    tracked_market_order.quote_asset,
                                                                    tracked_market_order.quote_asset,
                                                                    float(tracked_market_order.amount),
                                                                    float(tracked_market_order.quote_asset_amount),
                                                                    float(tracked_market_order.gas_fee_amount),
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
                                                                     float(tracked_market_order.amount),
                                                                     float(tracked_market_order.quote_asset_amount),
                                                                     float(tracked_market_order.gas_fee_amount),
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

    async def request_signed_market_orders(self, symbol: str, side: TradeType, amount: str) -> Dict[str, Any]:
        if side is TradeType.BUY:
            order_type = "BUY"
        elif side is TradeType.SELL:
            order_type = "SELL"
        else:
            raise ValueError("Invalid side. Aborting.")
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/markets/{symbol}/order/market"
        data = {
            "type": order_type,
            "quantity": amount
        }
        response_data = await self._api_request(http_method="post", url=url, data=data, headers={"User-Agent":"hummingbot"})
        return response_data

    async def request_unsigned_limit_order(self, 
                                           symbol: str, 
                                           side: TradeType, 
                                           is_coordinated: bool, 
                                           amount: str, 
                                           price: str, 
                                           expires: int) -> Dict[str, Any]:
        if side is TradeType.BUY:
            order_type = "BUY"
        elif side is TradeType.SELL:
            order_type = "SELL"
        else:
            raise ValueError("Invalid side. Aborting.")
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/markets/{symbol}/order/limit"
        data = {
            "type": order_type,
            "useCoordinator": is_coordinated,
            "quantity": amount,
            "price": price,
            "expiration": expires
        }
        return await self._api_request(http_method="post", url=url, data=data, headers={"User-Agent":"hummingbot"})

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
                                  side: TradeType,
                                  amount: Decimal) -> Tuple[float, str]:
        if side is not TradeType.BUY and side is not TradeType.SELL:
                raise ValueError("Invalid side. Aborting.")

        response = await self.request_signed_market_orders(symbol=symbol,
                                                           side=side,
                                                           amount=str(amount))
        signed_market_orders = response["orders"]
        average_price = float(response["averagePrice"])
        is_coordinated = bool(response["isCoordinated"])
        trading_rules = self.trading_rules.get(symbol)
        max_base_amount_with_decimals = Decimal(amount) * Decimal(f"1e{trading_rules.amount_decimals}")

        tx_hash = ""
        total_base_quantity = Decimal(response["totalBaseQuantity"])
        total_quote_quantity = Decimal(response["totalQuoteQuantity"])
        total_base_amount = Decimal(response["totalBaseAmount"])
        total_quote_amount = Decimal(response["totalQuoteAmount"])

        # Sanity check
        if total_base_quantity > Decimal(amount):
            print("API Returned too large a quantity")
            raise ValueError(f"API returned incorrect values for market order")

        # Single orders to use fillOrder, multiple to use batchFill
        if len(signed_market_orders) == 1:
            signed_market_order = signed_market_orders[0]
            signature = signed_market_order["signature"]
            del signed_market_order["signature"]
            order = jsdict_order_to_struct(signed_market_order)

            # Sanity check on rates returned
            if side is TradeType.BUY:
                calculated_maker_amount = math.floor((total_base_amount * Decimal(signed_market_order["takerAssetAmount"])) / 
                                                 Decimal(signed_market_order["takerAssetAmount"]))
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

            if side is TradeType.BUY:
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
                if target_taker_amount < new_total_taker_asset_fill_amount:
                    taker_asset_fill_amounts.append(taker_fill_amount)
                    total_maker_asset_fill_amount = total_maker_asset_fill_amount + maker_fill_amount
                    total_taker_asset_fill_amount = new_total_taker_asset_fill_amount
                else:
                    # calculate
                    remaining_taker_amount = target_taker_amount - total_taker_asset_fill_amount
                    taker_asset_fill_amounts.append(remaining_taker_amount)
                    order_maker_fill_amount = math.floor((remaining_taker_amount * Decimal(order["makerAssetAmount"])) / 
                                                     Decimal(order["takerAssetAmount"]))
                    total_maker_asset_fill_amount = total_maker_asset_fill_amount + order_maker_fill_amount
                    total_taker_asset_fill_amount = remaining_taker_amount
                    break

            # Sanity check on rates returned
            if side is TradeType.BUY and total_maker_asset_fill_amount > max_base_amount_with_decimals:
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
                                 side: TradeType,
                                 is_coordinated: bool,
                                 amount: Decimal,
                                 price: str,
                                 expires: int) -> Tuple[str, ZeroExOrder]:
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/orders"
        unsigned_limit_order = await self.request_unsigned_limit_order(symbol=symbol,
                                                                       side=side,
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
            await self._api_request(http_method="post", url=url, data=signed_limit_order, headers={"User-Agent":"hummingbot"})
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
            asyncio.ensure_future(self.cancel_order(client_order_id))
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
        asyncio.ensure_future(self.cancel_order(client_order_id))

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
                            order_side: TradeType,
                            symbol: str,
                            amount: float,
                            price: float,
                            expires: int) -> str:
        cdef:
            str q_price
            object q_amt = self.c_quantize_order_amount(symbol, amount)
            TradingRule trading_rule = self._trading_rules[symbol]
            bint is_buy = order_side is TradeType.BUY
            str order_side_desc = "buy" if is_buy else "sell"
            str type_str = "limit" if order_type is OrderType.LIMIT else "market"
        try:
            if float(q_amt) < trading_rule.min_order_size:
                raise ValueError(f"{order_side_desc.capitalize()} order amount {q_amt} is lower than the "
                                 f"minimum order size {trading_rule.min_order_size}")
            if float(q_amt) > trading_rule.max_order_size:
                raise ValueError(f"{order_side_desc.capitalize()} order amount {q_amt} is greater than the "
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
                                                                                     side=order_side,
                                                                                     is_coordinated=self._use_coordinator,
                                                                                     amount=q_amt,
                                                                                     price=q_price,
                                                                                     expires=expires)
                    self.c_start_tracking_limit_order(order_id=order_id,
                                                      exchange_order_id=exchange_order_id,
                                                      symbol=symbol,
                                                      is_buy=is_buy,
                                                      order_type= order_type,
                                                      is_coordinated=self._use_coordinator,
                                                      amount=Decimal(q_amt),
                                                      price=Decimal(q_price),
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
                                                                                    side=order_side,
                                                                                    amount=q_amt)
                q_price = str(self.c_quantize_order_price(symbol, avg_price))
                self.c_start_tracking_market_order(order_id=order_id,
                                                   tx_hash=tx_hash,
                                                   symbol=symbol,
                                                   is_buy=is_buy,
                                                   order_type= order_type,
                                                   is_coordinated=is_coordinated,
                                                   expires=expires,
                                                   amount=Decimal(q_amt),
                                                   price=Decimal(q_price))
            if is_buy:
                self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                     BuyOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         symbol,
                                         float(q_amt),
                                         float(q_price),
                                         order_id
                                     ))
            else:
                self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                    SellOrderCreatedEvent(
                                        self._current_timestamp,
                                        order_type,
                                        symbol,
                                        float(q_amt),
                                        float(q_price),
                                        order_id
                                    ))
            return order_id
        except Exception:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {type_str} {order_side_desc} order to Bamboo Relay for {str(q_amt)} {symbol}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit {order_side_desc} order to Bamboo Relay. "
                                f"Check Ethereum wallet and network connection."
            )
            self.c_trigger_event(
                self.MARKET_ORDER_FAILURE_EVENT_TAG,
                MarketOrderFailureEvent(self._current_timestamp, order_id, order_type)
            )

    cdef str c_buy(self,
                   str symbol,
                   double amount,
                   object order_type = OrderType.MARKET,
                   double price = NaN,
                   dict kargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"buy-{symbol}-{tracking_nonce}")
            double current_timestamp = self._current_timestamp
        expires = kargs.get("expiration_ts", None)
        if expires is not None:
            expires = int(expires)
        else:
            expires = int(current_timestamp + 1200)
        if order_type is OrderType.LIMIT:
            # Don't spam the server endpoint if a order placement failed recently
            if current_timestamp - self._last_failed_limit_order_timestamp <= self.ORDER_CREATION_BACKOFF_TIME:
                raise
            # Record the in-flight limit order placement.
            self._in_flight_pending_limit_orders[order_id] = self._current_timestamp
        asyncio.ensure_future(self.execute_trade(order_id=order_id,
                                                 order_type=order_type,
                                                 order_side=TradeType.BUY,
                                                 symbol=symbol,
                                                 amount=amount,
                                                 price=price,
                                                 expires=expires))
        return order_id

    cdef str c_sell(self,
                    str symbol,
                    double amount,
                    object order_type = OrderType.MARKET,
                    double price = NaN,
                    dict kargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")
            double current_timestamp = self._current_timestamp
        expires = kargs.get("expiration_ts", None)
        if expires is not None:
            expires = int(expires)
        else:
            expires = int(current_timestamp + 1200)
        if order_type is OrderType.LIMIT:
            # Don't spam the server endpoint if a order placement failed recently
            if current_timestamp - self._last_failed_limit_order_timestamp <= self.ORDER_CREATION_BACKOFF_TIME:
                raise
            # Record the in-flight limit order placement.
            self._in_flight_pending_limit_orders[order_id] = self._current_timestamp
        asyncio.ensure_future(self.execute_trade(order_id=order_id,
                                                 order_type=order_type,
                                                 order_side=TradeType.SELL,
                                                 symbol=symbol,
                                                 amount=amount,
                                                 price=price,
                                                 expires=expires))
        return order_id

    async def cancel_order(self, client_order_id: str) -> Dict[str, Any]:
        cdef:
            InFlightOrder order = self._in_flight_limit_orders.get(client_order_id)

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

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    def get_balance(self, currency: str) -> float:
        return self.c_get_balance(currency)

    def get_price(self, symbol: str, is_buy: bool) -> float:
        return self.c_get_price(symbol, is_buy)

    def get_tx_hash_receipt(self, tx_hash: str) -> Dict[str, Any]:
        return self._w3.eth.getTransactionReceipt(tx_hash)

    async def list_account_orders(self) -> List[Dict[str, Any]]:
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/accounts/{self._wallet.address}/orders"
        response_data = await self._api_request("get", url=url, headers={"User-Agent":"hummingbot"})
        return response_data

    def wrap_eth(self, amount: float) -> str:
        return self._wallet.wrap_eth(amount)

    def unwrap_eth(self, amount: float) -> str:
        return self._wallet.unwrap_eth(amount)

    cdef double c_get_balance(self, str currency) except? -1:
        return float(self._account_balances.get(currency, 0.0))

    cdef double c_get_available_balance(self, str currency) except? -1:
        return float(self._account_balances.get(currency, 0.0))

    cdef OrderBook c_get_order_book(self, str symbol):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if symbol not in order_books:
            raise ValueError(f"No order book exists for '{symbol}'.")
        return order_books[symbol]

    cdef double c_get_price(self, str symbol, bint is_buy) except? -1:
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)

        return order_book.c_get_price(is_buy)

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()

        self._order_tracker_task = asyncio.ensure_future(self._order_book_tracker.start())
        self._status_polling_task = asyncio.ensure_future(self._status_polling_loop())
        tx_hashes = await self.wallet.current_backend.check_and_fix_approval_amounts(
            spender=self._wallet_spender_address
        )
        self._pending_approval_tx_hashes.update(tx_hashes)
        self._approval_tx_polling_task = asyncio.ensure_future(self._approval_tx_polling_loop())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
            self._status_polling_task.cancel()
            self._pending_approval_tx_hashes.clear()
            self._approval_tx_polling_task.cancel()
        self._order_tracker_task = self._status_polling_task = self._approval_tx_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        if self._wallet.network_status is not NetworkStatus.CONNECTED:
            return NetworkStatus.NOT_CONNECTED

        try:
            await self._api_request("GET", f"{BAMBOO_RELAY_REST_ENDPOINT}{self._api_prefix}/tokens", headers={"User-Agent":"hummingbot"})
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
                                      bint is_buy,
                                      object order_type,
                                      bint is_coordinated,
                                      object amount,
                                      object price,
                                      int expires,
                                      object zero_ex_order):
        self._in_flight_limit_orders[order_id] = InFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            tx_hash=None,
            symbol=symbol,
            is_buy=is_buy,
            order_type=order_type,
            is_coordinated=is_coordinated,
            amount=amount,
            price=price,
            expires=expires,
            zero_ex_order=zero_ex_order
        )

    cdef c_start_tracking_market_order(self,
                                       str order_id,
                                       str tx_hash,
                                       str symbol,
                                       bint is_buy,
                                       object order_type,
                                       bint is_coordinated,
                                       object amount,
                                       object price,
                                       int expires):
        self._in_flight_market_orders[tx_hash] = InFlightOrder(
            client_order_id=order_id,
            exchange_order_id=None,
            tx_hash=tx_hash,
            symbol=symbol,
            is_buy=is_buy,
            order_type=order_type,
            is_coordinated=is_coordinated,
            amount=amount,
            price=price,
            expires=expires
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

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        decimals_quantum = Decimal(f"1e-{trading_rule.price_decimals}")
        if price > 0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(price)) - trading_rule.price_precision}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_get_order_size_quantum(self, str symbol, double amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        decimals_quantum = Decimal(f"1e-{trading_rule.amount_decimals}")

        if amount > 0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(amount)) - trading_rule.price_precision}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_quantize_order_amount(self, str symbol, double amount, double price=0.0):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        global s_decimal_0
        quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, min(amount, trading_rule.max_order_size))

        # Check against min_order_size. If not passing the check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        return quantized_amount
