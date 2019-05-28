import aiohttp
import asyncio
from async_timeout import timeout
from collections import deque
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
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.market.bamboo_relay.bamboo_relay_api_order_book_data_source import BambooRelayAPIOrderBookDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import (
  OrderType,
  NaN
)
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.market.bamboo_relay.bamboo_relay_order_book_tracker import BambooRelayOrderBookTracker
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
from zero_ex.order_utils import (
    generate_order_hash_hex,
    jsdict_order_to_struct,
    Order
)
from hummingbot.wallet.ethereum.zero_ex.zero_ex_custom_utils import fix_signature
from hummingbot.wallet.ethereum.zero_ex.zero_ex_exchange import ZeroExExchange

rrm_logger = None
s_decimal_0 = Decimal(0)

ZERO_EX_MAINNET_ERC20_PROXY = "0x2240Dab907db71e64d3E0dbA4800c83B5C502d4E"
ZERO_EX_MAINNET_EXCHANGE_ADDRESS = "0x4F833a24e1f95D70F028921e27040Ca56E09AB0b"
BAMBOO_RELAY_REST_ENDPOINT = "https://rest.bamboorelay.com/main/0x"


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
        public object amount
        public object price
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
                 amount: Decimal,
                 price: Decimal,
                 zero_ex_order: Order = None):
        self.client_order_id = client_order_id
        self.exchange_order_id = exchange_order_id
        self.tx_hash = tx_hash
        self.symbol = symbol
        self.is_buy = is_buy
        self.order_type = order_type
        self.amount = amount # initial amount (constant)
        self.available_amount = amount
        self.price = price
        self.executed_amount = s_decimal_0
        self.quote_asset_amount = s_decimal_0
        self.gas_fee_amount = s_decimal_0
        self.last_state = "OPEN"
        self.zero_ex_order = zero_ex_order

    def __repr__(self) -> str:
        return f"InFlightOrder(client_order_id='{self.client_order_id}', exchange_order_id='{self.exchange_order_id}', " \
               f"tx_hash='{self.tx_hash}', symbol='{self.symbol}', is_buy={self.is_buy}, order_type={self.order_type}, " \
               f"amount={self.amount}, available_amount={self.available_amount} price={self.price}, " \
               f"executed_amount={self.executed_amount}, quote_asset_amount={self.quote_asset_amount}, "\
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
    ORDER_EXPIRY_TIME = 60.0 * 15
    UPDATE_RULES_INTERVAL = 60.0
    UPDATE_OPEN_LIMIT_ORDERS_INTERVAL = 10.0
    UPDATE_MARKET_ORDERS_INTERVAL = 10.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global rrm_logger
        if rrm_logger is None:
            rrm_logger = logging.getLogger(__name__)
        return rrm_logger

    def __init__(self,
                 wallet: Web3Wallet,
                 web3_url: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                    OrderBookTrackerDataSourceType.EXCHANGE_API,
                 wallet_spender_address: str = ZERO_EX_MAINNET_ERC20_PROXY,
                 symbols: Optional[List[str]] = None):
        super().__init__()
        self._order_book_tracker = BambooRelayOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                              symbols=symbols)
        self._account_balances = {}
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_update_limit_order_timestamp = 0
        self._last_update_market_order_timestamp = 0
        self._last_update_trading_rules_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_limit_orders = {} # limit orders are off chain
        self._in_flight_market_orders = {} # market orders are on chain
        self._order_expiry_queue = deque()
        self._tx_tracker = BambooRelayTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(web3_url))
        self._provider = Web3.HTTPProvider(web3_url)
        self._withdraw_rules = {}
        self._trading_rules = {}
        self._pending_approval_tx_hashes = set()
        self._status_polling_task = None
        self._order_tracker_task = None
        self._approval_tx_polling_task = None
        self._wallet = wallet
        self._wallet_spender_address = wallet_spender_address
        self._exchange = ZeroExExchange(self._w3, ZERO_EX_MAINNET_EXCHANGE_ADDRESS, wallet)
        self._latest_salt = -1

    @property
    def name(self) -> str:
        return "bamboo_relay"

    @property
    def ready(self) -> bool:
        return len(self._account_balances) > 0 \
               and len(self._trading_rules) > 0 \
               and len(self._order_book_tracker.order_books) > 0 \
               and len(self._pending_approval_tx_hashes) == 0

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

        for in_flight_order in self._in_flight_limit_orders:
            typed_in_flight_order = in_flight_order
            if typed_in_flight_order.order_type is not OrderType.LIMIT:
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
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}/markets?include=base"
        return await self._api_request(http_method="get", url=url)

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
        list_account_orders_url = f"{BAMBOO_RELAY_REST_ENDPOINT}/accounts/{self._wallet.address}/orders"
        return await self._api_request(http_method="get", url=list_account_orders_url)

    async def get_order(self, order_hash: str) -> Dict[str, Any]:
        order_url = f"{BAMBOO_RELAY_REST_ENDPOINT}/orders/{order_hash}"
        return await self._api_request("get", url=order_url)

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
                            order_executed_amount
                        )
                    )

                # do not retrigger order events if order was already in that state previously
                if not previous_is_cancelled and tracked_limit_order.is_cancelled:
                    self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has cancelled according "
                                       f"to order status API.")
                    self.c_trigger_event(
                        self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                        OrderCancelledEvent(self._current_timestamp, tracked_limit_order.client_order_id)
                    )
                    self.c_expire_order(tracked_limit_order.client_order_id)
                elif not previous_is_expired and tracked_limit_order.is_expired:
                    self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has expired according "
                                       f"to order status API.")
                    self.c_trigger_event(
                        self.MARKET_ORDER_EXPIRED_EVENT_TAG,
                        OrderExpiredEvent(self._current_timestamp, tracked_limit_order.client_order_id)
                    )
                    self.c_expire_order(tracked_limit_order.client_order_id)
                elif not previous_is_failure and tracked_limit_order.is_failure:
                    self.logger().info(f"The limit order {tracked_limit_order.client_order_id} has failed"
                                       f"according to order status API.")
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(self._current_timestamp,
                                                      tracked_limit_order.client_order_id,
                                                      OrderType.LIMIT)
                    )
                    self.c_expire_order(tracked_limit_order.client_order_id)
                elif not previous_is_done and tracked_limit_order.is_done:
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
                    self.c_expire_order(tracked_limit_order.client_order_id)
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
                                      data=data,
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
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}/markets/{symbol}/order/market"
        data = {
            "type": order_type,
            "quantity": amount
        }
        response_data = await self._api_request(http_method="post", url=url, data=data)
        return response_data

    async def request_unsigned_limit_order(self, symbol: str, side: TradeType, amount: str, price: str, expires: int)\
            -> Dict[str, Any]:
        if side is TradeType.BUY:
            order_type = "BUY"
        elif side is TradeType.SELL:
            order_type = "SELL"
        else:
            raise ValueError("Invalid side. Aborting.")
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}/markets/{symbol}/order/limit"
        data = {
            "type": order_type,
            "quantity": amount,
            "price": price,
            "expiration": expires
        }
        return await self._api_request(http_method="post", url=url, data=data)

    def get_order_hash_hex(self, unsigned_order: Dict[str, Any]) -> str:
        order_struct = jsdict_order_to_struct(unsigned_order)
        order_hash_hex = generate_order_hash_hex(order=order_struct,
                                                 exchange_address=ZERO_EX_MAINNET_EXCHANGE_ADDRESS.lower())
        return order_hash_hex

    def get_zero_ex_signature(self, order_hash_hex: str) -> str:
        signature = self._wallet.current_backend.sign_hash(hexstr=order_hash_hex)
        fixed_signature = fix_signature(self._provider, self._wallet.address, order_hash_hex, signature)
        return fixed_signature

    async def submit_market_order(self,
                                  symbol: str,
                                  side: TradeType,
                                  amount: Decimal) -> Tuple[float, str]:
        response = await self.request_signed_market_orders(symbol=symbol,
                                                           side=side,
                                                           amount=str(amount))
        signed_market_orders = response["orders"]
        average_price = float(response["averagePrice"])
        base_asset_decimals = self.trading_rules.get(symbol).amount_decimals
        amt_with_decimals = Decimal(amount) * Decimal(f"1e{base_asset_decimals}")

        signatures = []
        orders = []
        for order in signed_market_orders:
            signatures.append(order["signature"])
            del order["signature"]
            orders.append(jsdict_order_to_struct(order))
        tx_hash = ""
        if side is TradeType.BUY:
            tx_hash = self._exchange.market_buy_orders(orders, amt_with_decimals, signatures)
        elif side is TradeType.SELL:
            tx_hash = self._exchange.market_sell_orders(orders, amt_with_decimals, signatures)
        else:
            raise ValueError("Invalid side. Aborting.")
        return average_price, tx_hash

    async def submit_limit_order(self,
                                 symbol: str,
                                 side: TradeType,
                                 amount: Decimal,
                                 price: str,
                                 expires: int) -> Tuple[str, Order]:
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}/orders"
        unsigned_limit_order = await self.request_unsigned_limit_order(symbol=symbol,
                                                                       side=side,
                                                                       amount=str(amount),
                                                                       price=price,
                                                                       expires=expires)
        unsigned_limit_order["makerAddress"] = self._wallet.address.lower()
        order_hash_hex = self.get_order_hash_hex(unsigned_limit_order)
        signed_limit_order = copy.deepcopy(unsigned_limit_order)
        signature = self.get_zero_ex_signature(order_hash_hex)
        signed_limit_order["signature"] = signature
        await self._api_request(http_method="post", url=url, data=signed_limit_order)
        self._latest_salt = int(unsigned_limit_order["salt"])
        order_hash = self._w3.toHex(hexstr=order_hash_hex)
        del unsigned_limit_order["signature"]
        zero_ex_order = jsdict_order_to_struct(unsigned_limit_order)
        return order_hash, zero_ex_order

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_order_ids = [o.client_order_id
                                for o in self._in_flight_limit_orders.values()
                                if not (o.is_done or o.is_cancelled or o.is_expired or o.is_failure)]
        if self._latest_salt == -1 or len(incomplete_order_ids) == 0:
            return []

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
                                                                                     amount=q_amt,
                                                                                     price=q_price,
                                                                                     expires=expires)
                    self.c_start_tracking_limit_order(order_id=order_id,
                                                      exchange_order_id=exchange_order_id,
                                                      symbol=symbol,
                                                      is_buy=is_buy,
                                                      order_type= order_type,
                                                      amount=Decimal(q_amt),
                                                      price=Decimal(q_price),
                                                      expires=expires,
                                                      zero_ex_order=zero_ex_order)
            elif order_type is OrderType.MARKET:
                avg_price, tx_hash = await self.submit_market_order(symbol=symbol,
                                                                    side=order_side,
                                                                    amount=q_amt)
                q_price = str(self.c_quantize_order_price(symbol, avg_price))
                self.c_start_tracking_market_order(order_id=order_id,
                                                   tx_hash=tx_hash,
                                                   symbol=symbol,
                                                   is_buy=is_buy,
                                                   order_type= order_type,
                                                   amount=Decimal(q_amt),
                                                   price=Decimal(q_price))
            if is_buy:
                self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                     BuyOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         symbol,
                                         Decimal(q_amt),
                                         Decimal(q_price),
                                         order_id
                                     ))
            else:
                self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                    SellOrderCreatedEvent(
                                        self._current_timestamp,
                                        order_type,
                                        symbol,
                                        Decimal(q_amt),
                                        Decimal(q_price),
                                        order_id
                                    ))

            return order_id
        except Exception:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {order_side_desc} order to Bamboo Relay for {str(q_amt)} {symbol}.",
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
        expires = kargs.get("expiration_ts", None)
        if expires is not None:
            expires = int(expires)
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
        expires = kargs.get("expiration_ts", None)
        if expires is not None:
            expires = int(expires)
        asyncio.ensure_future(self.execute_trade(order_id=order_id,
                                                 order_type=order_type,
                                                 order_side=TradeType.SELL,
                                                 symbol=symbol,
                                                 amount=amount,
                                                 price=price,
                                                 expires=expires))
        return order_id

    async def cancel_order(self, client_order_id: str) -> Dict[str, Any]:
        order = self._in_flight_limit_orders.get(client_order_id)
        if not order:
            self.logger().info(f"Failed to cancel order {client_order_id}. Order not found in tracked orders.")
            return
        return self._exchange.cancel_order(order.zero_ex_order)

    cdef c_cancel(self, str symbol, str client_order_id):
        asyncio.ensure_future(self.cancel_order(client_order_id))

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    def get_balance(self, currency: str) -> float:
        return self.c_get_balance(currency)

    def get_price(self, symbol: str, is_buy: bool) -> float:
        return self.c_get_price(symbol, is_buy)

    def get_tx_hash_receipt(self, tx_hash: str) -> Dict[str, Any]:
        return self._w3.eth.getTransactionReceipt(tx_hash)

    async def list_account_orders(self) -> List[Dict[str, Any]]:
        url = f"{BAMBOO_RELAY_REST_ENDPOINT}/accounts/{self._wallet.address}/orders"
        response_data = await self._api_request("get", url=url)
        return response_data

    def wrap_eth(self, amount: float) -> str:
        return self._wallet.wrap_eth(amount)

    def unwrap_eth(self, amount: float) -> str:
        return self._wallet.unwrap_eth(amount)

    cdef double c_get_balance(self, str currency) except? -1:
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
            await self._api_request("GET", f"{BAMBOO_RELAY_REST_ENDPOINT}/tokens")
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
            amount=amount,
            price=price,
            zero_ex_order=zero_ex_order
        )

    cdef c_start_tracking_market_order(self,
                                       str order_id,
                                       str tx_hash,
                                       str symbol,
                                       bint is_buy,
                                       object order_type,
                                       object amount,
                                       object price):
        self._in_flight_market_orders[tx_hash] = InFlightOrder(
            client_order_id=order_id,
            exchange_order_id=None,
            tx_hash=tx_hash,
            symbol=symbol,
            is_buy=is_buy,
            order_type=order_type,
            amount=amount,
            price=price
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

    cdef object c_quantize_order_amount(self, str symbol, double amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        global s_decimal_0
        quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, min(amount, trading_rule.max_order_size))

        # Check against min_order_size. If not passing the check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        return quantized_amount
