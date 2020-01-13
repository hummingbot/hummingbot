import aiohttp
from async_timeout import timeout
import asyncio
from cachetools import TTLCache
from collections import (
    deque,
    OrderedDict
)
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)
from web3 import Web3

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    MarketOrderFailureEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    TradeType,
    OrderType,
    TradeFee
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import s_decimal_NaN
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.market.idex.idex_active_order_tracker import IDEXActiveOrderTracker
from hummingbot.market.idex.idex_api_order_book_data_source import IDEXAPIOrderBookDataSource
from hummingbot.market.idex.idex_order_book_tracker import IDEXOrderBookTracker
from hummingbot.market.idex.idex_utils import generate_vrs
from hummingbot.market.idex.idex_in_flight_order cimport IDEXInFlightOrder
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

im_logger = None
s_decimal_0 = Decimal(0)
NaN = float("nan")


cdef class IDEXMarketTransactionTracker(TransactionTracker):
    cdef:
        IDEXMarket _owner

    def __init__(self, owner: IDEXMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class IDEXMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    IDEX_REST_ENDPOINT = "https://api.idex.market"
    IDEX_MAKER_PERCENT_FEE = Decimal("0.001")
    IDEX_TAKER_PERCENT_FEE = Decimal("0.002")
    API_CALL_TIMEOUT = 10.0
    TRADE_API_CALL_TIMEOUT = 60
    UPDATE_HOURLY_INTERVAL = 60 * 60
    UPDATE_ORDER_TRACKING_INTERVAL = 10
    UPDATE_BALANCES_INTERVAL = 5
    ORDER_EXPIRY_TIME = 15 * 60.0
    CANCEL_EXPIRY_TIME = 60.0
    MINIMUM_LIMIT_ORDER_LIFESPAN = 15

    MINIMUM_MAKER_ORDER_SIZE_ETH = Decimal("0.15")
    MINIMUM_TAKER_ORDER_SIZE_ETH = Decimal("0.05")
    # MINIMUM_TAKER_ORDER_SIZE_ETH is currently not used;
    # Hummingbot's architecture makes it difficult to implement different maker/taker min sizes

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global im_logger
        if im_logger is None:
            im_logger = logging.getLogger(__name__)
        return im_logger

    def __init__(self,
                 idex_api_key: str,
                 wallet: Web3Wallet,
                 ethereum_rpc_url: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._idex_api_key = idex_api_key
        self._order_book_tracker = IDEXOrderBookTracker(idex_api_key=idex_api_key,
                                                        data_source_type=order_book_tracker_data_source_type,
                                                        trading_pairs=trading_pairs)
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_update_balances_timestamp = 0
        self._last_update_order_timestamp = 0
        self._last_update_asset_info_timestamp = 0
        self._last_update_contract_address_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._in_flight_cancels = OrderedDict()
        self._order_expiry_queue = deque()
        self._order_expiry_set = set()
        self._tx_tracker = IDEXMarketTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        self._status_polling_task = None
        self._order_tracker_task = None
        self._wallet = wallet
        self._shared_client = None
        self._api_response_records = TTLCache(60000, ttl=600.0)
        self._assets_info = {}
        self._contract_address = None
        self._async_scheduler = AsyncCallScheduler(call_interval=1.0)
        self._last_nonce = 0

    @staticmethod
    def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
        try:
            quote_asset, base_asset = trading_pair.split('_')
            return base_asset, quote_asset
        # Exceptions are now logged as warnings in trading pair fetcher
        except Exception:
            return None

    @staticmethod
    def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
        if IDEXMarket.split_trading_pair(exchange_trading_pair) is None:
            return None
        # IDEX uses QUOTE_BASE (USDT_BTC)
        quote_asset, base_asset = exchange_trading_pair.split("_")
        return f"{base_asset}-{quote_asset}"

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
        assets = hb_trading_pair.split("-")
        assets.reverse()
        return "_".join(assets)

    @property
    def status_dict(self):
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "order_books_initialized": self._order_book_tracker.ready,
            "asset_info": len(self._assets_info) > 0,
            "contract_address": self._contract_address is not None
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def name(self) -> str:
        return "idex"

    @property
    def active_order_trackers(self) -> Dict[str, IDEXActiveOrderTracker]:
        return self._order_book_tracker._active_order_trackers

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def wallet(self) -> Web3Wallet:
        return self._wallet

    @property
    def in_flight_orders(self) -> Dict[str, IDEXInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            list retval = []
            IDEXInFlightOrder typed_in_flight_order
            set expiring_order_ids = set([order_id for _, order_id in self._order_expiry_queue])

        for in_flight_order in self._in_flight_orders.values():
            typed_in_flight_order = in_flight_order
            if ((typed_in_flight_order.order_type is not OrderType.LIMIT) or
                    typed_in_flight_order.is_done):
                continue
            if typed_in_flight_order.client_order_id in expiring_order_ids:
                continue
            retval.append(typed_in_flight_order.to_limit_order())

        return retval

    @property
    def expiring_orders(self) -> List[LimitOrder]:
        return [self._in_flight_orders[order_id].to_limit_order()
                for _, order_id
                in self._order_expiry_queue]

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    @property
    def nonce(self) -> int:
        next_nonce = int(time.time() * 1e3)

        if self._last_nonce >= next_nonce:
            next_nonce = self._last_nonce + 1

        self._last_nonce = next_nonce
        return next_nonce

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: IDEXInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self):
        return await IDEXAPIOrderBookDataSource.get_active_exchange_markets()

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                    self._update_asset_info(),
                    self._update_contract_address()
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"IDEX Status Polling Loop Error: {e}")
                self.logger().network(
                    "Unexpected error while fetching account and status updates.",
                    exc_info=True,
                    app_warning_msg=f"Failed to fetch account updates on IDEX. Check network connection."
                )

    async def _update_balances(self):
        cdef:
            double current_timestamp = self._current_timestamp
        if current_timestamp - self._last_update_balances_timestamp > self.UPDATE_BALANCES_INTERVAL or len(self._account_balances) > 0:
            available_balances, total_balances = await self.get_idex_balances()
            self._account_available_balances = available_balances
            self._account_balances = total_balances
            self._last_update_balances_timestamp = current_timestamp

    async def _update_asset_info(self):
        """
        Asset info contains asset's address and decimals
        {
            "ETH": {
            "decimals": 18,
            "address": "0x0000000000000000000000000000000000000000",
            "name": "Ether"
            },
            "REP": {
            "decimals": 8,
            "address": "0xc853ba17650d32daba343294998ea4e33e7a48b9",
            "name": "Reputation"
            },
            ...
        }
        """
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_asset_info_timestamp > self.UPDATE_HOURLY_INTERVAL or len(self._assets_info) == 0:
            currencies = await self.get_currencies()
            self._assets_info = currencies
            self._last_update_asset_info_timestamp = current_timestamp

    async def _update_contract_address(self):
        """
        contract address used for depositing, withdrawing, and posting orders
        """
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_contract_address_timestamp > self.UPDATE_HOURLY_INTERVAL or self._contract_address is None:
            contract_address = await self.get_idex_contract_address()
            self._contract_address = contract_address
            self._last_update_contract_address_timestamp = current_timestamp

    async def _update_order_status(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if not (current_timestamp - self._last_update_order_timestamp > self.UPDATE_ORDER_TRACKING_INTERVAL and len(self._in_flight_orders) > 0):
            return

        tracked_orders = list(self._in_flight_orders.values())
        tasks = [self.get_order(o.exchange_order_id)
                 for o in tracked_orders
                 if o.exchange_order_id is not None]
        results = await safe_gather(*tasks, return_exceptions=True)

        for order_update, tracked_limit_order in zip(results, tracked_orders):
            if isinstance(order_update, Exception):
                self.logger().network(
                    f"Error fetching status update for the order {tracked_limit_order.client_order_id}: "
                    f"{order_update}.",
                    app_warning_msg=f"Failed to fetch status update for the order {tracked_limit_order.client_order_id}. "
                                    f"Check Ethereum wallet and network connection."
                )
                continue

            previous_is_done = tracked_limit_order.is_done
            previous_is_cancelled = tracked_limit_order.is_cancelled

            # calculated executed amount relative to last update on this order
            order_executed_amount = Decimal(tracked_limit_order.available_amount_base) - Decimal(order_update["amount"])

            tracked_limit_order.last_state = order_update["status"]
            tracked_limit_order.executed_amount_base = Decimal(order_update["filled"])
            tracked_limit_order.available_amount_base = Decimal(order_update["amount"])
            tracked_limit_order.executed_amount_quote = Decimal(order_update["total"])
            if order_executed_amount > s_decimal_0:
                self.logger().info(f"Filled {order_executed_amount} out of {tracked_limit_order.amount} of the "
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
                        order_executed_amount,
                        self.c_get_fee(
                            tracked_limit_order.base_asset,
                            tracked_limit_order.quote_asset,
                            OrderType.LIMIT,
                            tracked_limit_order.trade_type,
                            Decimal(order_executed_amount),
                            Decimal(tracked_limit_order.price)
                        ),
                        exchange_trade_id=tracked_limit_order.exchange_order_id,
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
        self._last_update_order_timestamp = current_timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           http_method: str,
                           url: str,
                           data: Optional[Dict[str, Any]] = None,
                           params: Optional[Dict[str, Any]] = None,
                           headers: Optional[Dict[str, str]] = None,
                           json: Any = None) -> Dict[str, Any]:
        client = await self._http_client()
        default_headers = {"API-Key": self._idex_api_key, "User-Agent": "hummingbot"}
        headers_with_ua = {**headers, **default_headers} if headers else default_headers
        async with client.request(http_method,
                                  url=url,
                                  timeout=self.API_CALL_TIMEOUT,
                                  data=data,
                                  params=params,
                                  headers=headers_with_ua,
                                  json=json) as response:
            data = await response.json()
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status} - {data}")
            # Keep an auto-expired record of the response and the request URL for debugging and logging purpose.
            self._api_response_records[url] = response
            return data

    async def _sequential_api_request(self,
                                      http_method: str,
                                      url: str,
                                      data: Optional[Dict[str, Any]] = None,
                                      params: Optional[Dict[str, Any]] = None,
                                      headers: Optional[Dict[str, str]] = None,
                                      json: Any = None) -> Dict[str, Any]:
        """
        All trade execution calls (limit orders, market orders, cancels) on IDEX require
        incrementing nonce value. These api requests need to executed in order hence we use
        the async scheduler class to queue these tasks.
        """
        async with timeout(self.TRADE_API_CALL_TIMEOUT):
            coro = self._api_request(
                http_method,
                url,
                data,
                params,
                headers,
                json

            )
            return await self._async_scheduler.schedule_async_call(
                coro,
                self.TRADE_API_CALL_TIMEOUT,
                "IDEX API call failed. Timeout error."
            )

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        cdef:
            int gas_estimate = 140000  # approximate gas used for IDEX market orders
            double transaction_cost_eth

        if order_type is OrderType.LIMIT:
            return TradeFee(percent=Decimal(self.IDEX_MAKER_PERCENT_FEE))
        transaction_cost_eth = self._wallet.gas_price * gas_estimate / 1e18
        return TradeFee(percent=Decimal(self.IDEX_TAKER_PERCENT_FEE),
                        flat_fees=[("ETH", Decimal(transaction_cost_eth))])

    def _generate_limit_order(self,
                              trading_pair: str,
                              amount: Decimal,
                              price: Decimal,
                              side: str) -> Dict[str, Any]:
        amount_base = amount
        amount_quote = amount_base * price
        quote_asset, base_asset = trading_pair.split("_")
        base_asset_info = self._assets_info[base_asset]
        quote_asset_info = self._assets_info[quote_asset]
        amount_base_with_decimals = int(amount_base * Decimal(f"1e{base_asset_info['decimals']}"))
        amount_quote_with_decimals = int(amount_quote * Decimal(f"1e{quote_asset_info['decimals']}"))
        nonce = self.nonce

        if (quote_asset == "ETH" and amount_quote < self.MINIMUM_MAKER_ORDER_SIZE_ETH) or \
                (base_asset == "ETH" and amount_base < self.MINIMUM_MAKER_ORDER_SIZE_ETH):
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size value ({self.MINIMUM_MAKER_ORDER_SIZE_ETH} ETH)")

        if side == "buy":
            amount_buy = amount_base_with_decimals
            amount_sell = amount_quote_with_decimals
            token_buy = base_asset_info["address"]
            token_sell = quote_asset_info["address"]
        else:
            amount_buy = amount_quote_with_decimals
            amount_sell = amount_base_with_decimals
            token_buy = quote_asset_info["address"]
            token_sell = base_asset_info["address"]

        hash_data = [
            ["contractAddress", self._contract_address, "address"],
            ["tokenBuy", token_buy, "address"],
            ["amountBuy", amount_buy, "uint256"],
            ["tokenSell", token_sell, "address"],
            ["amountSell", amount_sell, "uint256"],
            ["expires", 100000, "uint256"],  # expires does nothing but is required according to IDEX documentation
            ["nonce", nonce, "uint256"],
            ["address", self._wallet.address.lower(), "address"]
        ]
        vrs = generate_vrs(hash_data, self.wallet.private_key)
        return {
            "contractAddress": self._contract_address,
            "tokenBuy": token_buy,
            "amountBuy": amount_buy,
            "tokenSell": token_sell,
            "amountSell": amount_sell,
            "expires": 100000,
            "nonce": nonce,
            "address": self._wallet.address.lower(),
            "v": vrs["v"],
            "r": vrs["r"],
            "s": vrs["s"]
        }

    def _generate_cancel_order(self, order_hash: str) -> Dict[str, Any]:
        nonce = self.nonce
        hash_data = [
            ["orderHash", order_hash, "address"],
            ["nonce", nonce, "uint256"]
        ]
        vrs = generate_vrs(hash_data, self.wallet.private_key)
        return {
            "orderHash": order_hash,
            "address": self._wallet.address,
            "nonce": nonce,
            "v": vrs["v"],
            "r": vrs["r"],
            "s": vrs["s"]
        }

    def _generate_buy_market_order(self,
                                   amount: Decimal,
                                   limit_orders_to_fill: List[Dict[str, Any]],
                                   trading_pair: str) -> List[Dict[str, Any]]:
        market_orders = []
        base_asset, quote_asset = self.split_trading_pair(trading_pair)
        base_asset_decimals = self._assets_info[base_asset]["decimals"]
        desired_amount_base = Decimal(amount) * Decimal(f"1e{base_asset_decimals}")
        total_amount_quote = s_decimal_0
        nonce = self.nonce

        for o in limit_orders_to_fill:
            o_available_amount_base_sell = Decimal(o["amountSell"])
            o_price = o["price"]  # this value is already a Decimal type
            if o_available_amount_base_sell < desired_amount_base:
                amount_quote = o_price * o_available_amount_base_sell
                desired_amount_base -= o_available_amount_base_sell
            else:
                amount_quote = o_price * desired_amount_base
                desired_amount_base = s_decimal_0
            total_amount_quote += amount_quote

            hash_data = [
                ["orderHash", o["orderHash"], "address"],
                ["amount", int(amount_quote), "uint256"],
                ["address", self._wallet.address, "address"],
                ["nonce", nonce, "uint256"]
            ]
            vrs = generate_vrs(hash_data, self.wallet.private_key)
            market_orders.append({
                "amount": str(int(amount_quote)),  # amount is required to be a string (IDEX API bug)
                "orderHash": o["orderHash"],
                "address": self._wallet.address,
                "nonce": nonce,
                "v": vrs["v"],
                "r": vrs["r"],
                "s": vrs["s"]
            })

        if quote_asset == "ETH" and total_amount_quote < self.MINIMUM_MAKER_ORDER_SIZE_ETH:
            raise ValueError(f"Buy market order amount {amount} is lower than the minimum order size value ({self.MINIMUM_MAKER_ORDER_SIZE_ETH} ETH)")

        return market_orders

    def _generate_sell_market_order(self,
                                    amount: Decimal,
                                    limit_orders_to_fill: List[Dict[str, Any]],
                                    trading_pair: str) -> List[Dict[str, Any]]:
        market_orders = []
        base_asset, quote_asset = self.split_trading_pair(trading_pair)
        base_asset_decimals = self._assets_info[base_asset]["decimals"]
        quote_asset_decimals = self._assets_info[quote_asset]["decimals"]
        desired_amount_base = amount * Decimal(f"1e{base_asset_decimals}")
        total_amount_quote = s_decimal_0
        nonce = self.nonce

        for o in limit_orders_to_fill:
            o_amount_buy = Decimal(o["amountBuy"])
            o_price = o["price"]  # this value is already a Decimal type
            if o_amount_buy < desired_amount_base:
                amount_base = o_amount_buy
                desired_amount_base -= o_amount_buy
            else:
                amount_base = desired_amount_base
                desired_amount_base = s_decimal_0
            total_amount_quote += amount_base * o_price

            hash_data = [
                ["orderHash", o["orderHash"], "address"],
                ["amount", int(amount_base), "uint256"],
                ["address", self._wallet.address, "address"],
                ["nonce", nonce, "uint256"]
            ]
            vrs = generate_vrs(hash_data, self.wallet.private_key)
            market_orders.append({
                "amount": str(int(amount_base)),  # amount is required to be a string; IDEX API bug
                "orderHash": o["orderHash"],
                "address": self._wallet.address,
                "nonce": nonce,
                "v": vrs["v"],
                "r": vrs["r"],
                "s": vrs["s"]
            })

        if quote_asset == "ETH" and total_amount_quote / Decimal(f"1e{quote_asset_decimals}") < self.MINIMUM_MAKER_ORDER_SIZE_ETH:
            raise ValueError(f"Sell market order amount {amount} is lower than the minimum order size value ({self.MINIMUM_MAKER_ORDER_SIZE_ETH} ETH)")

        return market_orders

    async def cancel_order(self, client_order_id: str) -> Dict[str, Any]:
        order = self.in_flight_orders.get(client_order_id)
        created_timestamp = await order.get_created_timestamp()
        if time.time() - created_timestamp < self.MINIMUM_LIMIT_ORDER_LIFESPAN:
            await asyncio.sleep(self.MINIMUM_LIMIT_ORDER_LIFESPAN - (time.time() - created_timestamp))
        if not order:
            self.logger().info(f"Failed to cancel order {client_order_id}. Order not found in tracked orders.")
            if client_order_id in self._in_flight_cancels:
                del self._in_flight_cancels[client_order_id]
            return {}

        exchange_order_id = await order.get_exchange_order_id()
        cancel_order_request = self._generate_cancel_order(exchange_order_id)

        response_data = await self.post_cancel_order(cancel_order_request)
        if isinstance(response_data, dict) and response_data.get("success"):
            self.logger().info(f"Successfully cancelled order {exchange_order_id}.")
            self.c_expire_order(client_order_id)
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, client_order_id))
        return response_data

    async def post_market_order(self, market_order_request: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        url = f"{self.IDEX_REST_ENDPOINT}/trade"
        response_data = await self._sequential_api_request("post", url=url, json=market_order_request)
        return response_data

    async def post_cancel_order(self, cancel_order_request: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.IDEX_REST_ENDPOINT}/cancel"
        response_data = await self._sequential_api_request("post", url=url, data=cancel_order_request)
        return response_data

    async def post_limit_order(self, limit_order_request: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.IDEX_REST_ENDPOINT}/order"
        response_data = await self._sequential_api_request("post", url=url, data=limit_order_request)
        return response_data

    async def get_idex_contract_address(self) -> str:
        url = f"{self.IDEX_REST_ENDPOINT}/returnContractAddress"
        response_data = await self._api_request("get", url=url)
        return response_data["address"]

    async def get_order(self, order_hash: str) -> Dict[str, Any]:
        url = f"{self.IDEX_REST_ENDPOINT}/returnOrderStatus"
        response_data = await self._api_request("get", url=url, params={"orderHash": order_hash})
        return response_data

    async def get_currencies(self) -> Dict[str, Dict[str, Any]]:
        url = f"{self.IDEX_REST_ENDPOINT}/returnCurrencies"
        response_data = await self._api_request("get", url=url)
        return response_data

    async def get_idex_balances(self) -> Tuple[Dict[str, Decimal], Dict[str, Decimal]]:
        url = f"{self.IDEX_REST_ENDPOINT}/returnCompleteBalances"
        response_data = await self._api_request("get", url=url, params={"address": self._wallet.address})
        available_balances = {}
        total_balances = {}
        for asset, value in response_data.items():
            available_balances[asset] = Decimal(value["available"])
            total_balances[asset] = Decimal(value["available"]) + Decimal(value["onOrders"])
        return available_balances, total_balances

    cdef str c_buy(self,
                   str trading_pair,
                   object amount,
                   object order_type=OrderType.MARKET,
                   object price=s_decimal_0,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Decimal) -> str:
        cdef:
            object q_amt = self.c_quantize_order_amount(trading_pair, amount)
            object q_price = (self.c_quantize_order_price(trading_pair, price)
                              if order_type is OrderType.LIMIT
                              else s_decimal_0)

        try:
            self.c_start_tracking_order(order_id, trading_pair, TradeType.BUY, order_type, q_amt, q_price)
            if order_type is OrderType.LIMIT:
                limit_order = self._generate_limit_order(trading_pair=trading_pair,
                                                         amount=q_amt,
                                                         price=q_price,
                                                         side="buy")
                order_result = await self.post_limit_order(limit_order)
                tracked_order = self._in_flight_orders.get(order_id)
                if tracked_order is not None:
                    exchange_order_id = order_result["orderHash"]
                    self.logger().info(f"Created limit buy order {exchange_order_id} for "
                                       f"{q_amt} {trading_pair}.")
                    tracked_order.update_exchange_order_id(exchange_order_id)
                    tracked_order.update_created_timestamp(time.time())
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
                best_limit_orders = (self._order_book_tracker
                                     ._active_order_trackers[trading_pair]
                                     .get_best_limit_orders(is_buy=True, amount=q_amt))
                signed_market_orders = self._generate_buy_market_order(q_amt, best_limit_orders, trading_pair)
                completed_orders = await self.post_market_order(signed_market_orders)
                self.logger().info(f"Created market buy order for {q_amt} {trading_pair}.")
                self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                     BuyOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         trading_pair,
                                         q_amt,
                                         Decimal(0.0),
                                         order_id
                                     ))
                fill_quote_amount = sum([Decimal(completed_order["amount"]) for completed_order in completed_orders])
                fill_base_amount = sum([Decimal(completed_order["total"]) for completed_order in completed_orders])
                avg_fill_price = fill_quote_amount / fill_base_amount
                tracked_order = self._in_flight_orders.get(order_id)
                if tracked_order is not None:
                    self.logger().info(f"The market buy order {order_id} has completed according to trade API.")
                    self.c_stop_tracking_order(order_id)
                    self.c_trigger_event(
                        self.MARKET_ORDER_FILLED_EVENT_TAG,
                        OrderFilledEvent(
                            self._current_timestamp,
                            tracked_order.client_order_id,
                            tracked_order.trading_pair,
                            TradeType.BUY,
                            OrderType.MARKET,
                            avg_fill_price,
                            fill_base_amount,
                            self.c_get_fee(
                                tracked_order.base_asset,
                                tracked_order.quote_asset,
                                OrderType.MARKET,
                                TradeType.BUY,
                                Decimal(fill_base_amount),
                                Decimal(tracked_order.price)
                            ),
                            tracked_order.exchange_order_id,
                        )
                    )
                    self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                         BuyOrderCompletedEvent(timestamp=self._current_timestamp,
                                                                order_id=order_id,
                                                                base_asset=tracked_order.base_asset,
                                                                quote_asset=tracked_order.quote_asset,
                                                                fee_asset=tracked_order.quote_asset,
                                                                base_asset_amount=fill_base_amount,
                                                                quote_asset_amount=fill_quote_amount,
                                                                fee_amount=fill_quote_amount * self.IDEX_TAKER_PERCENT_FEE,
                                                                order_type=OrderType.MARKET))
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting buy order to IDEX for {amount} {trading_pair}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to IDEX: {e}"
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp,
                                                         order_id,
                                                         order_type)
                                 )

    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.MARKET,
                    object price=s_decimal_0,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Decimal) -> str:
        cdef:
            object q_amt = self.c_quantize_order_amount(trading_pair, amount)
            object q_price = (self.c_quantize_order_price(trading_pair, price)
                              if order_type is OrderType.LIMIT
                              else s_decimal_0)
        try:
            self.c_start_tracking_order(order_id, trading_pair, TradeType.SELL, order_type, q_amt, q_price)
            if order_type is OrderType.LIMIT:
                limit_order = self._generate_limit_order(trading_pair=trading_pair,
                                                         amount=q_amt,
                                                         price=q_price,
                                                         side="sell")
                order_result = await self.post_limit_order(limit_order)
                tracked_order = self._in_flight_orders.get(order_id)
                if tracked_order is not None:
                    exchange_order_id = order_result["orderHash"]
                    self.logger().info(f"Created limit sell order {exchange_order_id} for "
                                       f"{q_amt} {trading_pair}.")
                    tracked_order.update_exchange_order_id(exchange_order_id)
                    tracked_order.update_created_timestamp(time.time())
                self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                     SellOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         trading_pair,
                                         q_amt,
                                         q_price,
                                         order_id
                                     ))
            else:
                best_limit_orders = (self._order_book_tracker
                                     ._active_order_trackers[trading_pair]
                                     .get_best_limit_orders(is_buy=False, amount=q_amt))
                signed_market_orders = self._generate_sell_market_order(q_amt, best_limit_orders, trading_pair)
                completed_orders = await self.post_market_order(signed_market_orders)
                self.logger().info(f"Created market sell order for {q_amt} {trading_pair}.")
                self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                     SellOrderCreatedEvent(
                                         self._current_timestamp,
                                         order_type,
                                         trading_pair,
                                         q_amt,
                                         Decimal("0"),
                                         order_id
                                     ))
                fill_quote_amount = sum([Decimal(completed_order["amount"]) for completed_order in completed_orders])
                fill_base_amount = sum([Decimal(completed_order["total"]) for completed_order in completed_orders])
                avg_fill_price = fill_quote_amount / fill_base_amount
                tracked_order = self._in_flight_orders.get(order_id)
                if tracked_order is not None:
                    self.logger().info(f"The market sell order {order_id} has completed according to trade API.")
                    self.c_stop_tracking_order(order_id)
                    self.c_trigger_event(
                        self.MARKET_ORDER_FILLED_EVENT_TAG,
                        OrderFilledEvent(
                            self._current_timestamp,
                            tracked_order.client_order_id,
                            tracked_order.trading_pair,
                            TradeType.SELL,
                            OrderType.MARKET,
                            avg_fill_price,
                            fill_base_amount,
                            self.c_get_fee(
                                tracked_order.base_asset,
                                tracked_order.quote_asset,
                                OrderType.MARKET,
                                TradeType.SELL,
                                Decimal(fill_base_amount),
                                Decimal(tracked_order.price)
                            ),
                            tracked_order.exchange_order_id,
                        )
                    )
                    self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                         SellOrderCompletedEvent(timestamp=self._current_timestamp,
                                                                 order_id=order_id,
                                                                 base_asset=tracked_order.base_asset,
                                                                 quote_asset=tracked_order.quote_asset,
                                                                 fee_asset=tracked_order.quote_asset,
                                                                 base_asset_amount=fill_base_amount,
                                                                 quote_asset_amount=fill_quote_amount,
                                                                 fee_amount=fill_quote_amount * self.IDEX_TAKER_PERCENT_FEE,
                                                                 order_type=OrderType.MARKET))

        except Exception as e:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting sell order to IDEX for {amount} {trading_pair}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to IDEX: {e}"
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp,
                                                         order_id,
                                                         order_type)
                                 )
    cdef c_cancel(self, str trading_pair, str client_order_id):
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
        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done and o.client_order_id not in self._order_expiry_set]
        client_order_ids = [o.client_order_id for o in incomplete_orders]
        order_id_set = set(client_order_ids)
        tasks = [self.cancel_order(i) for i in client_order_ids]
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cid, cr in zip(client_order_ids, cancellation_results):
                    if isinstance(cr, Exception):
                        continue
                    if isinstance(cr, dict) and cr.get("success") == 1:
                        order_id_set.remove(cid)
                        successful_cancellations.append(CancellationResult(cid, True))
        except Exception as e:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg=f"Failed to cancel orders on IDEX. Check Ethereum wallet and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()
        self._order_tracker_task = safe_ensure_future(self._order_book_tracker.start())
        self._status_polling_task = safe_ensure_future(self._status_polling_loop())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
            self._status_polling_task.cancel()
        self._order_tracker_task = self._status_polling_task = None

    async def stop_network(self):
        self._stop_network()
        if self._shared_client is not None:
            await self._shared_client.close()
            self._shared_client = None

    async def check_network(self) -> NetworkStatus:
        if self._wallet.network_status is not NetworkStatus.CONNECTED:
            return NetworkStatus.NOT_CONNECTED

        url = f"{self.IDEX_REST_ENDPOINT}/returnContractAddress"
        try:
            await self._api_request("get", url)
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

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str trading_pair,
                                object trade_type,
                                object order_type,
                                object amount,
                                object price):
        self._in_flight_orders[client_order_id] = IDEXInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    cdef c_expire_order(self, str order_id):
        if order_id not in self._order_expiry_set:
            self._order_expiry_queue.append((self._current_timestamp + self.ORDER_EXPIRY_TIME, order_id))
            self._order_expiry_set.add(order_id)

    cdef c_check_and_remove_expired_orders(self):
        cdef:
            double current_timestamp = self._current_timestamp
            str order_id

        while len(self._order_expiry_queue) > 0 and self._order_expiry_queue[0][0] < current_timestamp:
            _, order_id = self._order_expiry_queue.popleft()
            self._order_expiry_set.remove(order_id)
            self.c_stop_tracking_order(order_id)

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            quote_asset = trading_pair.split("_")[0]
            quote_asset_decimals = self._assets_info[quote_asset]["decimals"]
        decimals_quantum = Decimal(f"1e-{quote_asset_decimals}")
        return decimals_quantum

    cdef object c_get_order_size_quantum(self, str trading_pair, object amount):
        cdef:
            base_asset = trading_pair.split("_")[1]
            base_asset_decimals = self._assets_info[base_asset]["decimals"]
        decimals_quantum = Decimal(f"1e-{base_asset_decimals}")
        return decimals_quantum

    def quantize_order_amount(self, trading_pair: str, amount: Decimal, price: Decimal = s_decimal_NaN) -> Decimal:
        return self.c_quantize_order_amount(trading_pair, amount, price)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        quantized_amount = MarketBase.c_quantize_order_amount(self, trading_pair, amount)
        base_asset, quote_asset = self.split_trading_pair(trading_pair)

        # Check against MINIMUM_MAKER_ORDER_SIZE_ETH return 0 if less than minimum.
        if base_asset == "ETH" and quantized_amount < self.MINIMUM_MAKER_ORDER_SIZE_ETH:
            return s_decimal_0
        elif quote_asset == "ETH":
            # Price is not passed in for market orders so price needs to be checked via the order book
            actual_price = Decimal(price or self.get_price(trading_pair, True))  # Since order side is unknown use higher price (buy)
            amount_quote = quantized_amount * actual_price
            if amount_quote < self.MINIMUM_MAKER_ORDER_SIZE_ETH:
                return s_decimal_0
        return quantized_amount
