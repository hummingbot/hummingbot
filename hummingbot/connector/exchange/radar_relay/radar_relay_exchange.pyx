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
from web3.exceptions import TransactionNotFound
from zero_ex.order_utils import (
    generate_order_hash_hex,
    Order as ZeroExOrder
)
from zero_ex.contract_wrappers.order_conversions import jsdict_to_order

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
    TradeFee
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import OrderType
from hummingbot.connector.exchange.radar_relay.radar_relay_api_order_book_data_source import RadarRelayAPIOrderBookDataSource
from hummingbot.connector.exchange.radar_relay.radar_relay_in_flight_order cimport RadarRelayInFlightOrder
from hummingbot.connector.exchange.radar_relay.radar_relay_order_book_tracker import RadarRelayOrderBookTracker
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.wallet.ethereum.zero_ex.zero_ex_custom_utils_v3 import fix_signature
from hummingbot.wallet.ethereum.zero_ex.zero_ex_exchange_v3 import ZeroExExchange
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

rrm_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("NaN")

ZERO_EX_MAINNET_ERC20_PROXY = "0x95E6F48254609A6ee006F7D493c8e5fB97094ceF"
ZERO_EX_MAINNET_EXCHANGE_ADDRESS = "0x61935CbDd02287B511119DDb11Aeb42F1593b7Ef"
RADAR_RELAY_REST_ENDPOINT = "https://api.radarrelay.com/v3"


cdef class RadarRelayTransactionTracker(TransactionTracker):
    cdef:
        RadarRelayExchange _owner

    def __init__(self, owner: RadarRelayExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class RadarRelayExchange(ExchangeBase):
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
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
                 ethereum_rpc_url: str,
                 poll_interval: float = 5.0,
                 wallet_spender_address: str = ZERO_EX_MAINNET_ERC20_PROXY,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._trading_required = trading_required
        self._order_book_tracker = RadarRelayOrderBookTracker(trading_pairs=trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_update_limit_order_timestamp = 0
        self._last_update_market_order_timestamp = 0
        self._last_update_trading_rules_timestamp = 0
        self._last_update_available_balance_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_limit_orders = {}  # limit orders are off chain
        self._in_flight_market_orders = {}  # market orders are on chain
        self._order_expiry_queue = deque()
        self._tx_tracker = RadarRelayTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        self._provider = Web3.HTTPProvider(ethereum_rpc_url)
        self._trading_rules = {}
        self._pending_approval_tx_hashes = set()
        self._status_polling_task = None
        self._approval_tx_polling_task = None
        self._wallet = wallet
        self._wallet_spender_address = wallet_spender_address
        self._exchange = ZeroExExchange(self._w3, ZERO_EX_MAINNET_EXCHANGE_ADDRESS, wallet)
        self._latest_salt = -1

    @property
    def name(self) -> str:
        return "radar_relay"

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
        return "radar_relay"

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
    def in_flight_limit_orders(self) -> Dict[str, RadarRelayInFlightOrder]:
        return self._in_flight_limit_orders

    @property
    def in_flight_market_orders(self) -> Dict[str, RadarRelayInFlightOrder]:
        return self._in_flight_market_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            list retval = []
            RadarRelayInFlightOrder typed_in_flight_order
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

    @property
    def in_flight_orders(self) -> Dict[str, RadarRelayInFlightOrder]:
        return {**self._in_flight_limit_orders, **self._in_flight_market_orders}

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_market_orders.update({
            key: RadarRelayInFlightOrder.from_json(value)
            for key, value in saved_states["market_orders"].items()
        })
        self._in_flight_limit_orders.update({
            key: RadarRelayInFlightOrder.from_json(value)
            for key, value in saved_states["limit_orders"].items()
        })

    async def get_active_exchange_markets(self):
        return await RadarRelayAPIOrderBookDataSource.get_active_exchange_markets()

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
                    app_warning_msg="Failed to fetch account updates on Radar Relay. Check network connection."
                )
                await asyncio.sleep(0.5)

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object trade_type,
                          object amount,
                          object price):
        """
        cdef:
            int gas_estimate = 130000  # approximate gas used for 0x market orders
            double transaction_cost_eth

        # there are no fees for makers on Radar Relay
        if order_type is OrderType.LIMIT:
            return TradeFee(percent=Decimal(0.0))
        # only fee for takers is gas cost of transaction
        transaction_cost_eth = self._wallet.gas_price * gas_estimate / 1e18
        return TradeFee(percent=Decimal(0.0), flat_fees=[("ETH", transaction_cost_eth)])
        """
        is_maker = order_type is OrderType.LIMIT
        return estimate_fee("radar_relay", is_maker)

    def _update_balances(self):
        self._account_balances = self.wallet.get_all_balances().copy()

    def _update_available_balances(self):
        cdef:
            double current_timestamp = self._current_timestamp

        # Retrieve account balance from wallet.
        self._account_balances = self.wallet.get_all_balances().copy()

        # Calculate available balance
        if current_timestamp - self._last_update_available_balance_timestamp > 10.0:

            if len(self._in_flight_limit_orders) >= 0:
                locked_balances = {}
                total_balances = self._account_balances

                for order in self._in_flight_limit_orders.values():
                    # Orders that are done, cancelled or expired don't deduct from the available balance
                    if (not order.is_cancelled and
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

                for currency, balance in total_balances.items():
                    self._account_available_balances[currency] = \
                        Decimal(total_balances[currency]) - locked_balances.get(currency, s_decimal_0)
            else:
                self._account_available_balances = self._account_balances.copy()

            self._last_update_available_balance_timestamp = current_timestamp

    async def list_market(self) -> Dict[str, Any]:
        url = f"{RADAR_RELAY_REST_ENDPOINT}/markets?include=base"
        return await self._api_request(http_method="get", url=url)

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
                                          min_base_amount_increment=Decimal(f"1e-{market['baseTokenDecimals']}")))
            except Exception:
                self.logger().error(f"Error parsing the trading_pair {trading_pair}. Skipping.", exc_info=True)
        return retval

    async def get_account_orders(self) -> List[Dict[str, Any]]:
        list_account_orders_url = f"{RADAR_RELAY_REST_ENDPOINT}/accounts/{self._wallet.address}/orders"
        return await self._api_request(http_method="get", url=list_account_orders_url)

    async def get_order(self, order_hash: str) -> Dict[str, Any]:
        order_url = f"{RADAR_RELAY_REST_ENDPOINT}/orders/{order_hash}"
        return await self._api_request("get", url=order_url)

    async def _get_order_updates(self, tracked_limit_orders: List[RadarRelayInFlightOrder]) -> List[Dict[str, Any]]:
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
                order_executed_amount_base = tracked_limit_order.available_amount_base - order_remaining_base_token_amount
                total_executed_amount_base = tracked_limit_order.amount - order_remaining_base_token_amount

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
                            tracked_limit_order.trading_pair,
                            tracked_limit_order.trade_type,
                            OrderType.LIMIT,
                            tracked_limit_order.price,
                            order_executed_amount_base,
                            TradeFee(0.0),  # no fee for limit order fills
                            tracked_limit_order.exchange_order_id,  # Use order hash for limit order validation
                        )
                    )

                # do not retrigger order events if order was already in that state previously
                if not previous_is_cancelled and tracked_limit_order.is_cancelled:
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
                            tracked_market_order.trading_pair,
                            tracked_market_order.trade_type,
                            OrderType.MARKET,
                            tracked_market_order.price,
                            tracked_market_order.amount,
                            TradeFee(0.0, [("ETH", gas_used)]),
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
                           headers: Optional[Dict[str, str]] = None,
                           json: int = 0) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as client:
            async with (
                    client.request(http_method,
                                   url=url,
                                   timeout=self.API_CALL_TIMEOUT,
                                   data=data,
                                   headers=headers) if json==0 else
                    client.request(http_method,
                                   url=url,
                                   timeout=self.API_CALL_TIMEOUT,
                                   json=data,
                                   headers=headers)) as response:
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

    async def request_signed_market_orders(self, trading_pair: str, trade_type: TradeType, amount: str) -> Dict[str, Any]:
        if trade_type is TradeType.BUY:
            order_type = "BUY"
        elif trade_type is TradeType.SELL:
            order_type = "SELL"
        else:
            raise ValueError("Invalid trade_type. Aborting.")
        url = f"{RADAR_RELAY_REST_ENDPOINT}/markets/{trading_pair}/order/market"
        data = {
            "type": order_type,
            "quantity": amount
        }
        response_data = await self._api_request(http_method="post", url=url, data=data)
        return response_data

    async def request_unsigned_limit_order(self, trading_pair: str, trade_type: TradeType, amount: str, price: str, expires: int)\
            -> Dict[str, Any]:
        if trade_type is TradeType.BUY:
            order_type = "BUY"
        elif trade_type is TradeType.SELL:
            order_type = "SELL"
        else:
            raise ValueError("Invalid trade_type. Aborting.")
        url = f"{RADAR_RELAY_REST_ENDPOINT}/markets/{trading_pair}/order/limit"
        data = {
            "type": order_type,
            "quantity": amount,
            "price": price,
            "expiration": expires
        }
        return await self._api_request(http_method="post", url=url, data=data)

    def get_order_hash_hex(self, unsigned_order: Dict[str, Any]) -> str:
        order_struct = jsdict_to_order(unsigned_order)
        order_hash_hex = generate_order_hash_hex(order=order_struct,
                                                 exchange_address=ZERO_EX_MAINNET_EXCHANGE_ADDRESS.lower(),
                                                 chain_id=1)
        return order_hash_hex

    def get_zero_ex_signature(self, order_hash_hex: str) -> str:
        signature = self._wallet.current_backend.sign_hash(hexstr=order_hash_hex)
        fixed_signature = fix_signature(self._provider, self._wallet.address, order_hash_hex, signature)
        return fixed_signature

    async def submit_market_order(self,
                                  trading_pair: str,
                                  trade_type: TradeType,
                                  amount: Decimal) -> Tuple[float, str]:
        response = await self.request_signed_market_orders(trading_pair=trading_pair,
                                                           trade_type=trade_type,
                                                           amount=str(amount))
        signed_market_orders = response["orders"]
        average_price = Decimal(response["averagePrice"])
        base_asset_increment = self.trading_rules.get(trading_pair).min_base_amount_increment
        base_asset_decimals = -int(math.ceil(math.log10(base_asset_increment)))
        amt_with_decimals = amount * Decimal(f"1e{base_asset_decimals}")

        signatures = []
        orders = []
        for order in signed_market_orders:
            signatures.append(order["signature"])
            del order["signature"]
            order["makerAddress"] = Web3.toChecksumAddress(order["makerAddress"])
            order["senderAddress"] = Web3.toChecksumAddress(order["senderAddress"])
            order["exchangeAddress"] = Web3.toChecksumAddress(order["exchangeAddress"])
            order["feeRecipientAddress"] = Web3.toChecksumAddress(order["feeRecipientAddress"])
            orders.append(jsdict_to_order(order))
        tx_hash = ""
        if trade_type is TradeType.BUY:
            tx_hash, protocol_fee = self._exchange.market_buy_orders(orders, amt_with_decimals, signatures)
        elif trade_type is TradeType.SELL:
            tx_hash, protocol_fee = self._exchange.market_sell_orders(orders, amt_with_decimals, signatures)
        else:
            raise ValueError("Invalid trade_type. Aborting.")
        return average_price, tx_hash

    async def submit_limit_order(self,
                                 trading_pair: str,
                                 trade_type: TradeType,
                                 amount: Decimal,
                                 price: Decimal,
                                 expires: int) -> Tuple[str, ZeroExOrder]:
        url = f"{RADAR_RELAY_REST_ENDPOINT}/orders"
        unsigned_limit_order = await self.request_unsigned_limit_order(trading_pair=trading_pair,
                                                                       trade_type=trade_type,
                                                                       amount=f"{amount:f}",
                                                                       price=f"{price:f}",
                                                                       expires=expires)
        unsigned_limit_order["makerAddress"] = self._wallet.address
        order_hash_hex = self.get_order_hash_hex(unsigned_limit_order)
        signed_limit_order = copy.deepcopy(unsigned_limit_order)
        signature = self.get_zero_ex_signature(order_hash_hex)
        signed_limit_order["signature"] = signature
        await self._api_request(http_method="post", url=url, data=signed_limit_order, headers={"Content-Type": "application/json"}, json=1)
        self._latest_salt = int(unsigned_limit_order["salt"])
        order_hash = self._w3.toHex(hexstr=order_hash_hex)
        del unsigned_limit_order["signature"]
        zero_ex_order = jsdict_to_order(unsigned_limit_order)
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
                app_warning_msg=f"Failed to cancel orders on Radar Relay. "
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
            TradingRule trading_rule = self._trading_rules[trading_pair]
            str trade_type_desc = trade_type.name.lower()
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
                                                                                     amount=q_amt,
                                                                                     price=q_price,
                                                                                     expires=expires)
                    self.c_start_tracking_limit_order(order_id=order_id,
                                                      exchange_order_id=exchange_order_id,
                                                      trading_pair=trading_pair,
                                                      order_type=order_type,
                                                      trade_type=trade_type,
                                                      price=q_price,
                                                      amount=q_amt,
                                                      zero_ex_order=zero_ex_order)
            elif order_type is OrderType.MARKET:
                avg_price, tx_hash = await self.submit_market_order(trading_pair=trading_pair,
                                                                    trade_type=trade_type,
                                                                    amount=q_amt)
                q_price = str(self.c_quantize_order_price(trading_pair, Decimal(avg_price)))
                self.c_start_tracking_market_order(order_id=order_id,
                                                   trading_pair=trading_pair,
                                                   order_type=order_type,
                                                   trade_type=trade_type,
                                                   price=q_price,
                                                   amount=q_amt,
                                                   tx_hash=tx_hash)
            if trade_type is TradeType.BUY:
                self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                     BuyOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         trading_pair,
                                         q_amt,
                                         q_price,
                                         order_id
                                     ))
            else:
                self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                     SellOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         trading_pair,
                                         q_amt,
                                         q_price,
                                         order_id
                                     ))

            return order_id
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type_desc} order to Radar Relay for {str(q_amt)} {trading_pair}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit {trade_type_desc} order to Radar Relay. "
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
        expires = kwargs.get("expiration_ts", None)
        if expires is not None:
            expires = int(expires)
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
        expires = kwargs.get("expiration_ts", None)
        if expires is not None:
            expires = int(expires)
        safe_ensure_future(self.execute_trade(order_id=order_id,
                                              order_type=order_type,
                                              trade_type=TradeType.SELL,
                                              trading_pair=trading_pair,
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

    cdef c_cancel(self, str trading_pair, str client_order_id):
        safe_ensure_future(self.cancel_order(client_order_id))

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def get_tx_hash_receipt(self, tx_hash: str) -> Dict[str, Any]:
        try:
            tx_hash_receipt = self._w3.eth.getTransactionReceipt(tx_hash)
            return tx_hash_receipt
        except TransactionNotFound:
            return None

    async def list_account_orders(self) -> List[Dict[str, Any]]:
        url = f"{RADAR_RELAY_REST_ENDPOINT}/accounts/{self._wallet.address}/orders"
        response_data = await self._api_request("get", url=url)
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
            await self._api_request("GET", f"{RADAR_RELAY_REST_ENDPOINT}/tokens")
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
                                      object trade_type,
                                      object price,
                                      object amount,
                                      object zero_ex_order):
        self._in_flight_limit_orders[order_id] = RadarRelayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            tx_hash=None,
            zero_ex_order=zero_ex_order
        )

    cdef c_start_tracking_market_order(self,
                                       str order_id,
                                       str trading_pair,
                                       object order_type,
                                       object trade_type,
                                       object price,
                                       object amount,
                                       str tx_hash):
        self._in_flight_market_orders[tx_hash] = RadarRelayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
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

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        decimals_quantum = trading_rule.min_quote_amount_increment
        if price > 0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(price)) - trading_rule.max_price_significant_digits}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_get_order_size_quantum(self, str trading_pair, object amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        decimals_quantum = trading_rule.min_base_amount_increment

        if amount > 0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(amount)) - trading_rule.max_price_significant_digits}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        global s_decimal_0
        quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, min(amount, trading_rule.max_order_size))

        # Check against min_order_size. If not passing the csheck, return 0.
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
