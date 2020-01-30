import aiohttp
import asyncio
from cachetools import TTLCache
import logging
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

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.market.kyber.kyber_api_order_book_data_source import KyberAPIOrderBookDataSource
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
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
from hummingbot.market.kyber.kyber_order_book_tracker import KyberOrderBookTracker
from hummingbot.market.kyber.kyber_in_flight_order cimport KyberInFlightOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


s_logger = None
s_decimal_0 = Decimal(0)

cdef class KyberMarketTransactionTracker(TransactionTracker):
    cdef:
        KyberMarket _owner

    def __init__(self, owner: KyberMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class KyberMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    KYBER_MAINNET_REST_ENDPOINT = "https://api.kyber.network"
    KYBER_MAINNET_PROXY = "0x818e6fecd516ecc3849daf6845e3ec868087b755"
    KYBER_ROPSTEN_REST_ENDPOINT = "https://ropsten-api.kyber.network"
    KYBER_ROPSTEN_PROXY = "0x818e6fecd516ecc3849daf6845e3ec868087b755"
    CURRENCIES = "/currencies"
    MARKET = "/market"
    QUOTE = "/quote_amount"
    TRADE_DATA = "/trade_data"
    API_CALL_TIMEOUT = 10.0
    HOURLY_INTERVAL = 60 * 60
    MINIMUM_ORDER_SIZE = 1000  # wei token
    KYBER_SLIPPAGE = 0.03  # 3 % slippage
    KYBER_BUY_SLIPPAGE = Decimal(1 + KYBER_SLIPPAGE)
    KYBER_SELL_SLIPPAGE = Decimal(1 - KYBER_SLIPPAGE)
    UPDATE_ORDER_STATUS_INTERVAL = 10.0

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
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._order_book_tracker = KyberOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                         trading_pairs=trading_pairs,
                                                         chain=wallet.chain)
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._assets_info = {}
        self._last_timestamp = 0
        self._last_update_order_timestamp = 0
        self._last_update_asset_info_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._tx_tracker = KyberMarketTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        self._pending_approval_tx_hashes = set()
        self._status_polling_task = None
        self._order_tracker_task = None
        self._approval_tx_polling_task = None
        self._wallet = wallet
        self._shared_client = None
        self._api_response_records = TTLCache(60000, ttl=600.0)
        if wallet.chain is EthereumChain.MAIN_NET:
            self._api_endpoint = self.KYBER_MAINNET_REST_ENDPOINT
            self._wallet_spender_address = Web3.toChecksumAddress(self.KYBER_MAINNET_PROXY)
        elif wallet.chain is EthereumChain.ROPSTEN:
            self._api_endpoint = self.KYBER_ROPSTEN_REST_ENDPOINT
            self._wallet_spender_address = Web3.toChecksumAddress(self.KYBER_ROPSTEN_PROXY)

    @property
    def name(self) -> str:
        return "kyber"

    @property
    def status_dict(self):
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "order_books_initialized": self._order_book_tracker.ready,
            "asset_info": len(self._assets_info) > 0,
            "token_approval": len(self._pending_approval_tx_hashes) == 0 if self._trading_required else True,
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def name(self) -> str:
        return "kyber"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def wallet(self) -> Web3Wallet:
        return self._wallet

    @property
    def in_flight_orders(self) -> Dict[str, KyberInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            list retval = []
        return retval

    @property
    def expiring_orders(self) -> List[LimitOrder]:
        return []

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

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
        if KyberMarket.split_trading_pair(exchange_trading_pair) is None:
            return None
        # IDEX uses QUOTE_BASE (USDT_BTC)
        quote_asset, base_asset = exchange_trading_pair.split("_")
        return f"{base_asset}-{quote_asset}"

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
        assets = hb_trading_pair.split("-")
        assets.reverse()
        return "_".join(assets)

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: KyberInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self):
        return await KyberAPIOrderBookDataSource.get_active_exchange_markets(self._api_endpoint)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                self._update_balances()
                await safe_gather(
                    self._update_asset_info(),
                    self._update_order_status()
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Kyber Status Polling Loop Error: {e}")
                self.logger().network(
                    "Unexpected error while fetching account and status updates.",
                    exc_info=True,
                    app_warning_msg=f"Failed to fetch account updates on Kyber. Check network connection."
                )

    # Kyber doesn't support limit order so available balance is same as total balance
    def _update_balances(self):
        self._account_balances = self.wallet.get_all_balances().copy()
        self._account_available_balances = self._account_balances.copy()

    async def _update_asset_info(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_asset_info_timestamp > self.HOURLY_INTERVAL or len(self._assets_info) == 0:

            url = f"{self._api_endpoint}{self.CURRENCIES}"
            response_data = await self._api_request('get', url=url)
            asset_info = {}
            for info in response_data["data"]:
                asset_info[info["symbol"]] = info

            self._assets_info = asset_info
            self._last_update_asset_info_timestamp = current_timestamp

    def get_asset_address(self, trading_pair: str):
        base_asset, quote_asset = self.split_trading_pair(trading_pair)
        base_address = self._assets_info[base_asset]["address"]
        quote_address = self._assets_info[quote_asset]["address"]
        return base_address, quote_address

    async def _update_order_status(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if not (current_timestamp - self._last_update_order_timestamp > self.UPDATE_ORDER_STATUS_INTERVAL and len(self._in_flight_orders) > 0):
            return

        tracked_orders = list(self._in_flight_orders.values())
        for tracked_order in tracked_orders:
            receipt = self._w3.eth.getTransactionReceipt(tracked_order.tx_hash)
            if receipt is None:
                continue
            if receipt["status"] == 0:
                err_msg = (f"Order {tracked_order.client_order_id} has failed "
                           f"according to transaction hash {tracked_order.tx_hash}.")
                self.logger().network(err_msg, app_warning_msg=err_msg)
                self.c_trigger_event(
                    self.MARKET_ORDER_FAILURE_EVENT_TAG,
                    MarketOrderFailureEvent(self._current_timestamp,
                                            tracked_order.client_order_id,
                                            tracked_order.order_type)
                )
            elif receipt["status"] == 1:
                gas_used = Decimal(receipt.get("gasUsed", 0.0))
                self.c_trigger_event(
                    self.MARKET_ORDER_FILLED_EVENT_TAG,
                    OrderFilledEvent(
                        self._current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        tracked_order.price,
                        tracked_order.amount,
                        TradeFee(s_decimal_0, [("ETH", gas_used)]),
                        tracked_order.tx_hash  # Use tx hash for market order validation
                    )
                )

                base_asset, quote_asset = self.split_trading_pair(tracked_order.trading_pair)
                if tracked_order.trade_type is TradeType.BUY:
                    trade_price = Decimal(self.c_get_price(tracked_order.trading_pair, True))
                    quote_amount = tracked_order.amount * trade_price

                    self.logger().info(f"Buy order {tracked_order.client_order_id} has completed "
                                       f"according to transaction hash {tracked_order.tx_hash}.")
                    self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                         BuyOrderCompletedEvent(self._current_timestamp,
                                                                tracked_order.client_order_id,
                                                                base_asset,
                                                                quote_asset,
                                                                quote_asset,
                                                                tracked_order.amount,
                                                                quote_amount,
                                                                0,
                                                                tracked_order.order_type))
                else:
                    trade_price = Decimal(self.c_get_price(tracked_order.trading_pair, False))
                    quote_amount = tracked_order.amount * trade_price

                    self.logger().info(f"Sell order {tracked_order.client_order_id} has completed "
                                       f"according to transaction hash {tracked_order.tx_hash}.")
                    self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                         SellOrderCompletedEvent(self._current_timestamp,
                                                                 tracked_order.client_order_id,
                                                                 base_asset,
                                                                 quote_asset,
                                                                 quote_asset,
                                                                 tracked_order.amount,
                                                                 quote_amount,
                                                                 0,
                                                                 tracked_order.order_type))
            else:
                err_msg = (f"Unrecognized transaction status for market order "
                           f"{tracked_order.client_order_id}. Check transaction hash "
                           f"{tracked_order.tx_hash} for more details.")
                self.logger().network(err_msg, app_warning_msg=err_msg)
                self.c_trigger_event(
                    self.MARKET_ORDER_FAILURE_EVENT_TAG,
                    MarketOrderFailureEvent(self._current_timestamp,
                                            tracked_order.client_order_id,
                                            tracked_order.order_type)
                )
            self.c_stop_tracking_order(tracked_order.client_order_id)
        self._last_update_order_timestamp = current_timestamp

    async def _approval_tx_polling_loop(self):
        while len(self._pending_approval_tx_hashes) > 0:
            try:
                if len(self._pending_approval_tx_hashes) > 0:
                    for tx_hash in list(self._pending_approval_tx_hashes):
                        receipt = self._w3.eth.getTransactionReceipt(tx_hash)
                        if receipt is not None:
                            self._pending_approval_tx_hashes.remove(tx_hash)
            except Exception as e:
                self.logger().error(f"Kyber Approval Transaction Polling Loop Error: {e}")
                self.logger().network(
                    "Unexpected error while fetching approval transactions.",
                    exc_info=True,
                    app_warning_msg="Could not get token approval status. "
                                    "Check Ethereum wallet and network connection."
                )
            finally:
                await asyncio.sleep(1.0)

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
        async with client.request(http_method,
                                  url=url,
                                  timeout=self.API_CALL_TIMEOUT,
                                  data=data,
                                  params=params,
                                  headers=headers) as response:
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
            content = await response.text()
            data = await response.json()

            # Keep an auto-expired record of the response and the request URL for debugging and logging purpose.
            self._api_response_records[url] = response

            return data

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        cdef:
            int gas_estimate = 300000  # approximate gas used for KYBER market orders
            double transaction_cost_eth

        transaction_cost_eth = self._wallet.gas_price * gas_estimate / 1e18
        return TradeFee(percent=s_decimal_0,
                        flat_fees=[("ETH", Decimal(transaction_cost_eth))])

    async def get_quote_amount(self, amount: str, trading_pair: str, side: str) -> str:
        # Get minimum destination amount
        url = f"{self._api_endpoint}{self.QUOTE}"
        base_address, quote_address = self.get_asset_address(trading_pair)
        params = {
            "base": base_address,
            "quote": quote_address,
            "base_amount": amount,
            "type": side
        }
        response_data = await self._api_request('get', url=url, params=params)
        quote_amount = Decimal(response_data["data"])

        if side == "buy":
            quote_amount = str(quote_amount * self.KYBER_BUY_SLIPPAGE)
        else:
            quote_amount = str(quote_amount * self.KYBER_SELL_SLIPPAGE)

        return quote_amount

    async def generate_unsigned_order(self, amount: str, trading_pair: str, side: str) -> Dict[str, Any]:
        quote_amount = await self.get_quote_amount(amount, trading_pair, side)

        url = f"{self._api_endpoint}{self.TRADE_DATA}"
        base_address, quote_address = self.get_asset_address(trading_pair)
        params = {
            "user_address": self._wallet.address,
            "nonce": self._wallet.current_backend.nonce,
            "gas_price": "medium"
        }
        if side == "buy":
            params["src_id"] = quote_address
            params["dst_id"] = base_address
            params["src_qty"] = quote_amount
            params["min_dst_qty"] = amount
        else:
            params["src_id"] = base_address
            params["dst_id"] = quote_address
            params["src_qty"] = amount
            params["min_dst_qty"] = quote_amount

        response_data = await self._api_request('get', url=url, params=params)

        unsigned_order = response_data["data"][0]
        unsigned_order["gas"] = unsigned_order["gasLimit"]
        del unsigned_order["gasLimit"]

        return unsigned_order

    async def place_order(self, amount: Decimal, price: Decimal, side: str, trading_pair: str, order_type: OrderType,
                          expires: int = 0) -> str:
        unsigned_order = await self.generate_unsigned_order(str(amount), trading_pair, side)

        signed_transaction = self._wallet.current_backend.account.signTransaction(unsigned_order)
        tx_hash = signed_transaction.hash.hex()
        self._wallet.current_backend.schedule_eth_transaction(signed_transaction, self._wallet.gas_price)

        return tx_hash

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        return {}

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
            # q_price and q_amt will be used for tracking, will use given price and amount for order
            object q_price = self.c_quantize_order_price(trading_pair, price)
            object q_amt = self.c_quantize_order_amount(trading_pair, amount)

        if order_type is OrderType.LIMIT:
            raise NotImplementedError("Kyber DEX doesn't support limit order option")

        try:
            self.logger().debug(f"Placing {order_type} buy order of {q_amt} {trading_pair}")
            tx_hash = await self.place_order(amount=amount,
                                             price=price,
                                             side="buy",
                                             trading_pair=trading_pair,
                                             order_type=order_type)

            self.c_start_tracking_order(order_id, trading_pair, TradeType.BUY, order_type, q_amt, q_price, tx_hash)
            self.logger().info(f"Created {order_type} buy order {tx_hash} for {q_amt} {trading_pair}.")

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
            self.logger().error(f"Error submitting buy order to Kyber for {amount} {trading_pair}: {str(e)}")
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting buy order to Kyber for {amount} {trading_pair}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Kyber. "
                                f"Check Ethereum wallet and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(
                                     self._current_timestamp,
                                     order_id,
                                     order_type
                                 ))

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
            # q_price and q_amt will be used for tracking, will use given price and amount for order
            object q_price = self.c_quantize_order_price(trading_pair, price)
            object q_amt = self.c_quantize_order_amount(trading_pair, amount)

        if order_type is OrderType.LIMIT:
            raise NotImplementedError("Kyber DEX doesn't support limit order option")

        try:
            self.logger().debug(f"Placing {order_type} sell order of {q_amt} {trading_pair}")
            tx_hash = await self.place_order(amount=amount,
                                             price=price,
                                             side="sell",
                                             trading_pair=trading_pair,
                                             order_type=order_type)

            self.c_start_tracking_order(order_id, trading_pair, TradeType.SELL, order_type, q_amt, q_price, tx_hash)
            self.logger().info(f"Created {order_type} sell order {tx_hash} for {q_amt} {trading_pair}.")

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
            self.logger().error(f"Error submitting sell order to Kyber for {amount} {trading_pair}: {str(e)}")
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting sell order to Kyber for {amount} {trading_pair}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Kyber. "
                                f"Check Ethereum wallet and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(
                                     self._current_timestamp,
                                     order_id,
                                     order_type)
                                 )

    cdef c_cancel(self, str trading_pair, str client_order_id):
        # Kyber API doesn't provide cancel order option.
        # Also it is not possible to cancel transaction once it is broadcasted to nodes
        return

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return failed_cancellations

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

        url = f"{self._api_endpoint}{self.MARKET}"
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
        self._last_timestamp = timestamp

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str trading_pair,
                                object trade_type,
                                object order_type,
                                object amount,
                                object price,
                                str tx_hash):
        self._in_flight_orders[client_order_id] = KyberInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            trade_type=trade_type,
            order_type=order_type,
            amount=amount,
            price=price,
            tx_hash=tx_hash
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            quote_asset = self.split_trading_pair(trading_pair)[1]
            quote_asset_decimals = self._assets_info[quote_asset]["decimals"]
        decimals_quantum = Decimal(f"1e-{quote_asset_decimals}")
        return decimals_quantum

    cdef object c_get_order_size_quantum(self, str trading_pair, object amount):
        cdef:
            base_asset = self.split_trading_pair(trading_pair)[0]
            base_asset_decimals = self._assets_info[base_asset]["decimals"]
        decimals_quantum = Decimal(f"1e-{base_asset_decimals}")
        return decimals_quantum

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        quantized_amount = MarketBase.c_quantize_order_amount(self, trading_pair, amount)
        decimals_quantum = self.c_get_order_size_quantum(trading_pair, amount)
        # Check against MINIMUM_ORDER_SIZE return 0 if less than minimum.
        if quantized_amount < (self.MINIMUM_ORDER_SIZE * decimals_quantum):
            return s_decimal_0
        return quantized_amount
