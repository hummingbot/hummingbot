import aiohttp
import asyncio
from async_timeout import timeout
from cachetools import TTLCache
from collections import (
    defaultdict,
    deque,
    OrderedDict
)
import logging
import math
import time
from typing import (
    Any,
    Dict,
    List,
    Optional
)
from decimal import Decimal
from libc.stdint cimport int64_t
from web3 import Web3

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.market.ddex.ddex_api_order_book_data_source import DDEXAPIOrderBookDataSource
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
    TradeFee,
)
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.ddex.ddex_order_book_tracker import DDEXOrderBookTracker
from hummingbot.market.ddex.ddex_in_flight_order cimport DDEXInFlightOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.market.market_base import s_decimal_NaN
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

s_logger = None
s_decimal_0 = Decimal(0)
HYDRO_MAINNET_PROXY = "0x74622073a4821dbfd046E9AA2ccF691341A076e1"


cdef class DDEXMarketTransactionTracker(TransactionTracker):
    cdef:
        DDEXMarket _owner

    def __init__(self, owner: DDEXMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class DDEXMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    API_CALL_TIMEOUT = 10.0
    DDEX_REST_ENDPOINT = "https://api.ddex.io/v3"
    UPDATE_TRADE_FEES_INTERVAL = 60 * 60
    ORDER_EXPIRY_TIME = 15 * 60.0
    CANCEL_EXPIRY_TIME = 60.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 wallet: Web3Wallet,
                 ethereum_rpc_url: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 wallet_spender_address: str = HYDRO_MAINNET_PROXY,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._order_book_tracker = DDEXOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                        trading_pairs=trading_pairs)
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_update_order_timestamp = 0
        self._last_update_trade_fills_timestamp = 0
        self._last_update_available_balance_timestamp = 0
        self._last_update_trading_rules_timestamp = 0
        self._last_update_trade_fees_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._in_flight_cancels = OrderedDict()
        self._order_expiry_queue = deque()
        self._tx_tracker = DDEXMarketTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        self._withdraw_rules = {}
        self._trading_rules = {}
        self._pending_approval_tx_hashes = set()
        self._status_polling_task = None
        self._order_tracker_task = None
        self._approval_tx_polling_task = None
        self._wallet = wallet
        self._wallet_spender_address = wallet_spender_address
        self._shared_client = None
        self._maker_trade_fee = s_decimal_NaN
        self._taker_trade_fee = s_decimal_NaN
        self._gas_fee_weth = s_decimal_NaN
        self._gas_fee_usd = s_decimal_NaN
        self._api_response_records = TTLCache(60000, ttl=600.0)

    @property
    def name(self) -> str:
        return "ddex"

    @property
    def status_dict(self):
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "account_available_balance": len(self._account_available_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "order_books_initialized": self._order_book_tracker.ready,
            "token_approval": len(self._pending_approval_tx_hashes) == 0 if self._trading_required else True,
            "maker_trade_fee_initialized": not math.isnan(self._maker_trade_fee),
            "taker_trade_fee_initialized": not math.isnan(self._taker_trade_fee),
            "gas_fee_weth_initialized": not math.isnan(self._gas_fee_weth),
            "gas_fee_usd_initilaized": not math.isnan(self._gas_fee_usd)
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def name(self) -> str:
        return "ddex"

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
    def in_flight_orders(self) -> Dict[str, DDEXInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            list retval = []
            DDEXInFlightOrder typed_in_flight_order

        for in_flight_order in self._in_flight_orders.values():
            typed_in_flight_order = in_flight_order
            if ((typed_in_flight_order.order_type is not OrderType.LIMIT) or
                    typed_in_flight_order.is_done):
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

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: DDEXInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self):
        return await DDEXAPIOrderBookDataSource.get_active_exchange_markets()

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                self._update_balances()
                await safe_gather(
                    self._update_available_balances(),
                    self._update_trading_rules(),
                    self._update_order_fills_from_trades(),
                    self._update_order_status(),
                    self._update_trade_fees()
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account and status updates.",
                    exc_info=True,
                    app_warning_msg=f"Failed to fetch account updates on DDEX. Check network connection."
                )

    def _update_balances(self):
        self._account_balances = self.wallet.get_all_balances().copy()

    async def _update_available_balances(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_available_balance_timestamp > 10.0:
            locked_balances = await self.list_locked_balances()
            total_balances = self.get_all_balances()

            for currency, balance in total_balances.items():
                self._account_available_balances[currency] = \
                    Decimal(total_balances[currency]) - locked_balances.get(currency, s_decimal_0)
            self._last_update_available_balance_timestamp = current_timestamp

    async def _update_trading_rules(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_trading_rules_timestamp > 60.0 or len(self._trading_rules) < 1:
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
                min_price_increment = Decimal(f"1e-{market['priceDecimals']}")
                min_base_amount_increment = Decimal(f"1e-{market['amountDecimals']}")
                retval.append(TradingRule(trading_pair,
                                          min_order_size=Decimal(market["minOrderSize"]),
                                          max_price_significant_digits=Decimal(market["pricePrecision"]),
                                          min_price_increment=min_price_increment,
                                          min_base_amount_increment=min_base_amount_increment,
                                          supports_limit_orders="limit" in market["supportedOrderTypes"],
                                          supports_market_orders="market" in market["supportedOrderTypes"]))
            except Exception:
                self.logger().error(f"Error parsing the trading_pair {trading_pair}. Skipping.", exc_info=True)
        return retval

    async def _update_order_fills_from_trades(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if not (current_timestamp - self._last_update_trade_fills_timestamp > 10.0 and len(self._in_flight_orders) > 0):
            return

        trading_pairs_to_order_map = defaultdict(lambda: {})
        for o in self._in_flight_orders.values():
            trading_pairs_to_order_map[o.trading_pair][o.exchange_order_id] = o
        trading_pairs = list(trading_pairs_to_order_map.keys())
        tasks = [self.list_account_trades(trading_pair) for trading_pair in trading_pairs]
        results = await safe_gather(*tasks, return_exceptions=True)
        for trades, trading_pair in zip(results, trading_pairs):
            order_map = trading_pairs_to_order_map[trading_pair]
            if isinstance(trades, Exception):
                self.logger().network(
                    f"Error fetching trades update for the order {trading_pair}: {trades}.",
                    app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                )
                continue
            for trade in trades:
                maker_order_id = str(trade["makerOrderId"])
                taker_order_id = str(trade["takerOrderId"])
                if maker_order_id in order_map or taker_order_id in order_map:
                    order_id = maker_order_id if maker_order_id in order_map else taker_order_id
                    tracked_order = order_map[order_id]
                    applied_trade = order_map[order_id].update_with_trade_update(trade)
                    if applied_trade:
                        client_order_id = tracked_order.client_order_id
                        fill_size = Decimal(trade["amount"])
                        execute_price = Decimal(trade["price"])
                        order_type_description = (
                            ("market" if tracked_order.order_type == OrderType.MARKET else "limit") + " " +
                            ("buy" if tracked_order.trade_type is TradeType.BUY else "sell")
                        )
                        order_filled_event = OrderFilledEvent(self._current_timestamp,
                                                              client_order_id,
                                                              tracked_order.trading_pair,
                                                              tracked_order.trade_type,
                                                              tracked_order.order_type,
                                                              execute_price,
                                                              fill_size,
                                                              self.c_get_fee(tracked_order.base_asset,
                                                                             tracked_order.quote_asset,
                                                                             tracked_order.order_type,
                                                                             tracked_order.trade_type,
                                                                             execute_price,
                                                                             fill_size),
                                                              exchange_trade_id=trade["transactionId"])
                        self.logger().info(f"Filled {fill_size} out of {tracked_order.amount} of the "
                                           f"{order_type_description} order {client_order_id}.")
                        self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)
        self._last_update_trade_fills_timestamp = current_timestamp

    async def _update_order_status(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if not (current_timestamp - self._last_update_order_timestamp > 10.0 and len(self._in_flight_orders) > 0):
            return

        tracked_orders = list(self._in_flight_orders.values())
        tasks = [self.get_order(o.exchange_order_id)
                 for o in tracked_orders
                 if o.exchange_order_id is not None]
        results = await safe_gather(*tasks, return_exceptions=True)

        for order_update, tracked_order in zip(results, tracked_orders):
            if isinstance(order_update, Exception):
                self.logger().network(
                    f"Error fetching status update for the order {tracked_order.client_order_id}: "
                    f"{order_update}.",
                    app_warning_msg=f"Failed to fetch status update for the order {tracked_order.client_order_id}. "
                                    f"Check Ethereum wallet and network connection."
                )
                continue

            # Check the exchange order ID against the expected value.
            exchange_order_id = order_update["id"]
            if exchange_order_id != tracked_order.exchange_order_id:
                self.logger().network(f"Incorrect exchange order id '{exchange_order_id}' returned from get order "
                                      f"request for '{tracked_order.exchange_order_id}'. Ignoring.")

                # Capture the incorrect request / response conversation for submitting to DDEX.
                request_url = f"{self.DDEX_REST_ENDPOINT}/orders/{tracked_order.exchange_order_id}"
                response = self._api_response_records.get(request_url)

                if response is not None:
                    self.logger().network(f"Captured erroneous order update request/response. "
                                          f"Request URL={response.real_url}, "
                                          f"Request headers={response.request_info.headers}, "
                                          f"Response headers={response.headers}, "
                                          f"Response data={repr(response._body)}, "
                                          f"Decoded order update={order_update}.")
                else:
                    self.logger().network(f"Failed to capture the erroneous request/response for getting the order update "
                                          f"of the order {tracked_order.exchange_order_id}.")

                continue

            previous_is_done = tracked_order.is_done
            is_market_buy = order_update["side"] == "buy" and order_update["type"] == "market"

            # Update the tracked order
            client_order_id = tracked_order.client_order_id
            order_type_description = (("market" if tracked_order.order_type == OrderType.MARKET else "limit") +
                                      " " +
                                      ("buy" if tracked_order.trade_type is TradeType.BUY else "sell"))
            order_type = OrderType.MARKET if tracked_order.order_type == OrderType.MARKET else OrderType.LIMIT
            previous_is_done = tracked_order.is_done
            tracked_order.last_state = order_update["status"]
            tracked_order.executed_amount_base = Decimal(order_update["confirmedAmount"])
            tracked_order.available_amount_base = Decimal(order_update["availableAmount"])
            tracked_order.pending_amount_base = Decimal(order_update["pendingAmount"])
            tracked_order.executed_amount_quote = tracked_order.executed_amount_base * Decimal(order_update["price"])
            tracked_order.gas_fee_amount = Decimal(order_update["gasFeeAmount"])
            if not previous_is_done and tracked_order.is_done:
                executed_amount_base = tracked_order.executed_amount_base
                executed_amount_quote = tracked_order.executed_amount_quote
                if not tracked_order.is_cancelled:
                    if tracked_order.trade_type is TradeType.BUY:
                        self.logger().info(f"The {order_type_description} order {client_order_id} has "
                                           f"completed according to order status API.")
                        is_market_buy = order_update["side"] == "buy" and order_update["type"] == "market"
                        if is_market_buy:
                            # DDEX return price data in "price" rather than "averagePrice" for market orders sometimes
                            # using the following logic to account for both cases
                            average_price = Decimal(order_update.get("averagePrice", 0))
                            price = Decimal(order_update.get("price", 0))
                            execute_price = price if average_price == s_decimal_0 else average_price
                            # Special rules for market buy orders, in which all reported amounts are in quote asset.
                            executed_amount_base = tracked_order.executed_amount_base / execute_price
                            executed_amount_quote = tracked_order.executed_amount_base

                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    tracked_order.quote_asset,
                                                                    executed_amount_base,
                                                                    executed_amount_quote,
                                                                    tracked_order.gas_fee_amount,
                                                                    order_type))
                    else:
                        self.logger().info(f"The {order_type_description} order {client_order_id} has "
                                           f"completed according to order status API.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_order.client_order_id,
                                                                     tracked_order.base_asset,
                                                                     tracked_order.quote_asset,
                                                                     tracked_order.quote_asset,
                                                                     executed_amount_base,
                                                                     executed_amount_quote,
                                                                     tracked_order.gas_fee_amount,
                                                                     order_type))
                else:
                    if (self._in_flight_cancels.get(client_order_id, 0) > self._current_timestamp - self.CANCEL_EXPIRY_TIME):
                        # This cancel was originated from this connector, and the cancel event should have been
                        # emitted in the cancel_order() call already.
                        del self._in_flight_cancels[client_order_id]
                    else:
                        # This cancel was originated externally.
                        self.logger().info(f"The {order_type_description} order {client_order_id} has been cancelled.")
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(self._current_timestamp, client_order_id))
                self.c_expire_order(tracked_order.client_order_id)

        self._last_update_order_timestamp = current_timestamp

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

    def _generate_auth_headers(self) -> Dict:
        message = "HYDRO-AUTHENTICATION@%s" % (int(time.time() * 1000),)
        signature = self.wallet.current_backend.sign_hash(text=message)
        auth = "%s#%s#%s" % (self.wallet.address.lower(), message, signature)
        headers = {"Hydro-Authentication": auth}
        return headers

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           http_method: str,
                           url: str,
                           data: Optional[Dict[str, Any]] = None,
                           params: Optional[Dict[str, Any]] = None,
                           headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        client = await self._http_client()
        async with client.request(http_method, url=url, timeout=self.API_CALL_TIMEOUT, data=data, params=params,
                                  headers=headers) as response:
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
            content = await response.text()
            data = await response.json()
            if data["status"] is not 0:
                raise IOError(f"Request to {url} has failed", data)

            # Keep an auto-expired record of the response and the request URL for debugging and logging purpose.
            self._api_response_records[url] = response

            return data

    async def _update_trade_fees(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_trade_fees_timestamp > self.UPDATE_TRADE_FEES_INTERVAL or \
                self._gas_fee_usd == s_decimal_NaN:

            calc_fee_url = f"{self.DDEX_REST_ENDPOINT}/fees"
            params = {
                "amount": "1",
                "marketId": "HOT-WETH",
                "price": "1",
            }
            res = await self._api_request(http_method="get", url=calc_fee_url, params=params)
            # maker / taker trade fees are same regardless of pair
            self._maker_trade_fee = Decimal(res["data"]["asMakerFeeRate"])
            self._taker_trade_fee = Decimal(res["data"]["asTakerFeeRate"])
            # gas fee from api is in quote token amount
            self._gas_fee_weth = Decimal(res["data"]["gasFeeAmount"])
            params = {
                "amount": "1",
                "marketId": "WETH-SAI",
                "price": "1",
            }
            res = await self._api_request(http_method="get", url=calc_fee_url, params=params)
            # DDEX charges same gas fee for both DAI and TUSD
            self._gas_fee_usd = Decimal(res["data"]["gasFeeAmount"])
            self._last_update_trade_fees_timestamp = current_timestamp

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        cdef:
            object gas_fee = Decimal(0)
            object percent

        # DDEX only quotes with WETH or stable coins
        if quote_currency == "WETH":
            gas_fee = self._gas_fee_weth
        elif quote_currency in ["SAI", "DAI", "TUSD", "USDC", "PAX", "USDT"]:
            gas_fee = self._gas_fee_usd
        else:
            self.logger().warning(
                f"Unrecognized quote token asset - {quote_currency}. Assuming gas fee is in stable coin units."
            )
            gas_fee = self._gas_fee_usd
        percent = self._maker_trade_fee if order_type is OrderType.LIMIT else self._taker_trade_fee
        return TradeFee(percent, flat_fees=[(quote_currency, gas_fee)])

    async def build_unsigned_order(self, amount: Decimal, price: Decimal, side: str, trading_pair: str, order_type: OrderType,
                                   expires: int) -> Dict[str, Any]:
        url = "%s/orders/build" % (self.DDEX_REST_ENDPOINT,)
        headers = self._generate_auth_headers()
        data = {
            "amount": f"{amount:f}",
            "price": f"{price:f}" if price != s_decimal_NaN else "0",
            "side": side,
            "marketId": trading_pair,
            "orderType": "market" if order_type is OrderType.MARKET else "limit",
            "expires": expires
        }

        response_data = await self._api_request('post', url=url, data=data, headers=headers)
        return response_data["data"]["order"]

    async def place_order(self, amount: Decimal, price: Decimal, side: str, trading_pair: str, order_type: OrderType,
                          expires: int = 0) -> Dict[str, Any]:
        unsigned_order = await self.build_unsigned_order(trading_pair=trading_pair, amount=amount, price=price, side=side,
                                                         order_type=order_type, expires=expires)
        order_id = unsigned_order["id"]
        signature = self.wallet.current_backend.sign_hash(hexstr=order_id)

        url = "%s/orders" % (self.DDEX_REST_ENDPOINT,)
        data = {"orderId": order_id, "signature": signature}

        response_data = await self._api_request('post', url=url, data=data, headers=self._generate_auth_headers())
        return response_data["data"]["order"]

    async def cancel_order(self, client_order_id: str) -> Dict[str, Any]:
        cdef:
            DDEXInFlightOrder order = self.in_flight_orders.get(client_order_id)

        if not order:
            self.logger().info(f"Failed to cancel order {client_order_id}. Order not found in tracked orders.")
            if client_order_id in self._in_flight_cancels:
                del self._in_flight_cancels[client_order_id]
            return {}

        exchange_order_id = await order.get_exchange_order_id()
        url = "%s/orders/%s" % (self.DDEX_REST_ENDPOINT, exchange_order_id)
        response_data = await self._api_request('delete', url=url, headers=self._generate_auth_headers())
        if isinstance(response_data, dict) and response_data.get("desc") == "success":
            self.logger().info(f"Successfully cancelled order {exchange_order_id}.")

            # Notify listeners.
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, client_order_id))

        response_data["client_order_id"] = client_order_id
        return response_data

    async def list_orders(self) -> Dict[str, Any]:
        url = "%s/orders?status=all" % (self.DDEX_REST_ENDPOINT,)
        response_data = await self._api_request('get', url=url, headers=self._generate_auth_headers())
        return response_data["data"]["orders"]

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        url = "%s/orders/%s" % (self.DDEX_REST_ENDPOINT, order_id)
        response_data = await self._api_request('get', url, headers=self._generate_auth_headers())
        return response_data["data"]["order"]

    async def list_account_trades(self, trading_pair: str) -> Dict[str, Any]:
        url = "%s/markets/%s/trades/mine" % (self.DDEX_REST_ENDPOINT, trading_pair)
        response_data = await self._api_request('get', url, headers=self._generate_auth_headers())
        return response_data["data"]["trades"]

    async def list_locked_balances(self) -> Dict[str, Decimal]:
        url = "%s/account/lockedBalances" % (self.DDEX_REST_ENDPOINT,)
        response_data = await self._api_request('get', url=url, headers=self._generate_auth_headers())
        self.logger().debug(f"list locked balances: {response_data}")
        locked_balance_list = response_data["data"]["lockedBalances"]
        locked_balance_dict = {}
        for locked_balance in locked_balance_list:
            trading_pair = locked_balance["symbol"]
            if self.wallet.erc20_tokens.get(trading_pair):
                try:
                    decimals = await self.wallet.erc20_tokens[trading_pair].get_decimals()
                    locked_balance_dict[trading_pair] = Decimal(locked_balance["amount"]) / Decimal(f"1e{decimals}")
                except Exception as e:
                    self.logger().error(f"Error getting decimals value for ERC20 token '{trading_pair}'.", exc_info=True)
        return locked_balance_dict

    async def get_market(self, trading_pair: str) -> Dict[str, Any]:
        url = "%s/markets/%s" % (self.DDEX_REST_ENDPOINT, trading_pair)
        response_data = await self._api_request('get', url=url)
        return response_data["data"]["market"]

    async def list_market(self) -> Dict[str, Any]:
        url = "%s/markets" % (self.DDEX_REST_ENDPOINT,)
        response_data = await self._api_request('get', url=url)
        return response_data["data"]["markets"]

    async def get_ticker(self, trading_pair: str) -> Dict[str, Any]:
        url = "%s/markets/%s/ticker" % (self.DDEX_REST_ENDPOINT, trading_pair)
        response_data = await self._api_request('get', url=url)
        return response_data["data"]["ticker"]

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.MARKET, object price=s_decimal_0,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_buy(self, order_id: str, trading_pair: str, amount: Decimal, order_type: OrderType,
                          price: Decimal) -> str:
        cdef:
            object q_price = self.c_quantize_order_price(trading_pair, price)
            object q_amt = self.c_quantize_order_amount(trading_pair, amount)
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quote_amount

        # Convert the amount to quote tokens amount, for market buy orders, as required by DDEX order API.
        if order_type is OrderType.MARKET:
            quote_amount = self.c_get_quote_volume_for_base_amount(trading_pair, True, amount).result_volume
            # Quantize according to price rules, not base token amount rules.
            q_amt = self.c_quantize_order_amount(trading_pair, quote_amount)

        try:
            if order_type is OrderType.LIMIT:
                if q_amt < trading_rule.min_order_size:
                    raise ValueError(f"Buy order amount {amount} is lower than the minimum order size")
            else:
                if amount < trading_rule.min_order_size:
                    raise ValueError(f"Buy order amount {amount} is lower than the minimum order size")

            if order_type is OrderType.LIMIT and trading_rule.supports_limit_orders is False:
                raise ValueError(f"Limit order is not supported for trading pair {trading_pair}")
            if order_type is OrderType.MARKET and trading_rule.supports_market_orders is False:
                raise ValueError(f"Market order is not supported for trading pair {trading_pair}")

            self.c_start_tracking_order(order_id, trading_pair, TradeType.BUY, order_type, q_amt, q_price)
            self.logger().debug(f"buying {q_amt} {trading_pair} at {q_price}, order type = {order_type}.")
            order_result = await self.place_order(amount=q_amt, price=q_price, side="buy", trading_pair=trading_pair,
                                                  order_type=order_type)
            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {exchange_order_id} for "
                                   f"{q_amt} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
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
                f"Error submitting buy order to DDEX for {amount} {trading_pair}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to DDEX. "
                                f"Check Ethereum wallet and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp,
                                                         order_id,
                                                         order_type)
                                 )

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.MARKET, object price=s_decimal_0,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self, order_id: str, trading_pair: str, amount: Decimal, order_type: OrderType,
                           price: Decimal) -> str:
        cdef:
            object q_price = self.c_quantize_order_price(trading_pair, price)
            object q_amt = self.c_quantize_order_amount(trading_pair, amount)
            TradingRule trading_rule = self._trading_rules[trading_pair]

        try:
            if q_amt < trading_rule.min_order_size:
                raise ValueError(f"Sell order amount {amount} is lower than the minimum order size ")
            if order_type is OrderType.LIMIT and trading_rule.supports_limit_orders is False:
                raise ValueError(f"Limit order is not supported for trading pair {trading_pair}")
            if order_type is OrderType.MARKET and trading_rule.supports_market_orders is False:
                raise ValueError(f"Market order is not supported for trading pair {trading_pair}")

            self.c_start_tracking_order(order_id, trading_pair, TradeType.SELL, order_type, q_amt, q_price)
            order_result = await self.place_order(amount=q_amt, price=q_price, side="sell", trading_pair=trading_pair,
                                                  order_type=order_type)
            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {exchange_order_id} for "
                                   f"{q_amt} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
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
                f"Error submitting sell order to DDEX for {amount} {trading_pair}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to DDEX. "
                                f"Check Ethereum wallet and network connection."
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
        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
        tasks = [self.cancel_order(o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, Exception):
                        continue
                    if isinstance(cr, dict) and cr.get("status") == 0:
                        client_order_id = cr.get("client_order_id")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception as e:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg=f"Failed to cancel orders on DDEX. Check Ethereum wallet and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

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
            self._status_polling_task.cancel()
            self._pending_approval_tx_hashes.clear()
            self._approval_tx_polling_task.cancel()
        self._order_tracker_task = self._status_polling_task = self._approval_tx_polling_task = None

    async def stop_network(self):
        self._stop_network()
        if self._shared_client is not None:
            await self._shared_client.close()
            self._shared_client = None

    async def check_network(self) -> NetworkStatus:
        if self._wallet.network_status is not NetworkStatus.CONNECTED:
            return NetworkStatus.NOT_CONNECTED

        url = f"{self.DDEX_REST_ENDPOINT}/markets/tickers"
        try:
            await self._api_request("GET", url)
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
        self._in_flight_orders[client_order_id] = DDEXInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
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
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        decimals_quantum = trading_rule.min_price_increment
        if price.is_finite() and price > s_decimal_0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(price)) - trading_rule.max_price_significant_digits}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_get_order_size_quantum(self, str trading_pair, object amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        decimals_quantum = trading_rule.min_base_amount_increment
        return decimals_quantum

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=Decimal(0)):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        quantized_amount = MarketBase.c_quantize_order_amount(self, trading_pair, amount)
        # Check against min_order_size and. If not passing the check, return 0.
        if quantized_amount < MarketBase.c_quantize_order_amount(self, trading_pair, trading_rule.min_order_size):
            return s_decimal_0
        return quantized_amount
