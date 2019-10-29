from async_timeout import timeout
import asyncio
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
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.market.market_base cimport MarketBase
from hummingbot.logger import HummingbotLogger

from hummingbot.market.stablecoinswap.stablecoinswap_order_book_tracker import StablecoinswapOrderBookTracker
from hummingbot.market.stablecoinswap.stablecoinswap_in_flight_order cimport StablecoinswapInFlightOrder
import hummingbot.market.stablecoinswap.stablecoinswap_contracts as stablecoinswap_contracts

im_logger = None
s_decimal_0 = Decimal(0)

cdef class StablecoinswapMarketTransactionTracker(TransactionTracker):
    cdef:
        StablecoinswapMarket _owner

    def __init__(self, owner: StablecoinswapMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)

cdef class StablecoinswapMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    FEE_UPDATE_INTERVAL = 60
    UPDATE_MARKET_ORDERS_INTERVAL = 10

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global im_logger
        if im_logger is None:
            im_logger = logging.getLogger(__name__)
        return im_logger

    def __init__(self,
                 wallet: Web3Wallet,
                 ethereum_rpc_url: str,
                 poll_interval: float = 5.0,
                 symbols: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._trading_required = trading_required
        self._tx_tracker = StablecoinswapMarketTransactionTracker(self)
        self._wallet = wallet
        self._w3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        self._oracle_cont = stablecoinswap_contracts.PriceOracle(self._w3)
        self._stl_cont = stablecoinswap_contracts.Stablecoinswap(
            self._w3, oracle_contract=self._oracle_cont)
        self._order_book_tracker = StablecoinswapOrderBookTracker(
            stl_contract=self._stl_cont, symbols=symbols)
        self._last_timestamp = 0
        self._last_update_market_order_timestamp = 0
        self._last_update_fee_timestamp = 0
        self._last_update_asset_info_timestamp = 0
        self._poll_interval = poll_interval
        self._poll_notifier = asyncio.Event()
        self._in_flight_orders = {}
        self._account_balances = {}
        self._pending_approval_tx_hashes = set()
        self._status_polling_task = None
        self._order_tracker_task = None
        self._approval_tx_polling_task = None
        self._contract_fees = None
        self._assets_decimals = {}
        self._wallet_spender_address = stablecoinswap_contracts.STABLECOINSWAP_ADDRESS

    @property
    def name(self) -> str:
        return "stablecoinswap"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def order_book_tracker(self) -> StablecoinswapOrderBookTracker:
        return self._order_book_tracker

    @property
    def wallet(self) -> Web3Wallet:
        return self._wallet

    @property
    def limit_orders(self) -> List[LimitOrder]:
        """There is no limit orders on Stablecoinswap."""
        return []

    @property
    def in_flight_orders(self) -> Dict[str, StablecoinswapInFlightOrder]:
        return self._in_flight_orders

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        return []

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 2 if self._trading_required else True,
            "token_approval": len(self._pending_approval_tx_hashes) == 0 if self._trading_required else True,
            "contract_fees": self._contract_fees is not None,
            "asset_decimals": len(self._assets_decimals) > 0
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: StablecoinswapInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    def _update_balances(self):
        self._account_balances = self.wallet.get_all_balances()
        self._account_available_balances = self._account_balances

    async def _update_asset_decimals(self):
        for symbol in self._order_book_tracker._symbols:
            base_token_name, quote_token_name = self.split_symbol(symbol)
            base_token = self._stl_cont.get_token(base_token_name)
            quote_token = self._stl_cont.get_token(quote_token_name)

            if base_token_name not in self._assets_decimals:
                self._assets_decimals[base_token_name] = await base_token.get_decimals()

            if quote_token_name not in self._assets_decimals:
                self._assets_decimals[quote_token_name] = await quote_token.get_decimals()

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()

        self._order_tracker_task = safe_ensure_future(self._order_book_tracker.start())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            tx_hashes = await self.wallet.current_backend.check_and_fix_approval_amounts(
                spender=self._wallet_spender_address
            )
            self._pending_approval_tx_hashes.update(tx_hashes)
            self._approval_tx_polling_task = safe_ensure_future(self._approval_tx_polling_loop())

        if len(self._assets_decimals) == 0:
            await self._update_asset_decimals()

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

        is_trading_allowed = self._stl_cont.is_trading_allowed()

        if is_trading_allowed is not True:
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

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        cdef:
            int gas_estimate = 181000  # approximate gas usage for Swap func
            double transaction_cost_eth

        transaction_cost_eth = self._wallet.gas_price * gas_estimate / 1e18

        return TradeFee(percent=self._contract_fees, flat_fees=[("ETH", transaction_cost_eth)])

    def get_tx_hash_receipt(self, tx_hash: str) -> Dict[str, Any]:
        return self._w3.eth.getTransactionReceipt(tx_hash)

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

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                self._update_balances()
                await safe_gather(
                    self._update_fee(),
                    self._update_market_order_status(),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg="Failed to fetch account updates on Stablecoinswap. Check network connection."
                )
                await asyncio.sleep(0.5)

    async def _update_fee(self):
        """Fetch contract fees."""
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_fee_timestamp <= self.FEE_UPDATE_INTERVAL:
            return

        self._contract_fees = self._stl_cont.get_fees()
        self._last_update_fee_timestamp = current_timestamp

    async def _update_market_order_status(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_market_order_timestamp <= self.UPDATE_MARKET_ORDERS_INTERVAL:
            return

        if len(self._in_flight_orders) > 0:
            tracked_market_orders = list(self._in_flight_orders.values())
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
                            tracked_market_order.trade_type,
                            OrderType.MARKET,
                            tracked_market_order.price,
                            tracked_market_order.amount,
                            TradeFee(0.0, [("ETH", gas_used)])
                        )
                    )

                    base_asset_token = self._stl_cont.get_token(tracked_market_order.base_asset)
                    quote_asset_token = self._stl_cont.get_token(tracked_market_order.quote_asset)
                    base_asset_decimals = await base_asset_token.get_decimals()
                    quote_asset_decimals = await quote_asset_token.get_decimals()

                    if tracked_market_order.trade_type is TradeType.BUY:
                        # retrieve executed amount from blockchain logs
                        tracked_market_order.executed_amount_quote = Web3.toInt(
                            hexstr=receipt.logs[0].data) / Decimal(f"1e{quote_asset_decimals}")
                        tracked_market_order.executed_amount_base = Web3.toInt(
                            hexstr=receipt.logs[1].data) / Decimal(f"1e{base_asset_decimals}")

                        # calculate fees
                        tracked_market_order.fee_paid = tracked_market_order. \
                            executed_amount_base * Decimal(tracked_market_order.fee_percent)

                        self.logger().info(f"The market buy order "
                                           f"{tracked_market_order.client_order_id} has completed according to "
                                           f"transaction hash {tracked_market_order.tx_hash}.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_market_order.client_order_id,
                                                                    tracked_market_order.base_asset,
                                                                    tracked_market_order.quote_asset,
                                                                    tracked_market_order.fee_asset,
                                                                    tracked_market_order.executed_amount_base,
                                                                    tracked_market_order.executed_amount_quote,
                                                                    tracked_market_order.fee_paid,
                                                                    OrderType.MARKET))
                    else:
                        # retrieve executed amount from blockchain logs
                        tracked_market_order.executed_amount_base = Web3.toInt(
                            hexstr=receipt.logs[0].data) / Decimal(f"1e{base_asset_decimals}")
                        tracked_market_order.executed_amount_quote = Web3.toInt(
                            hexstr=receipt.logs[1].data) / Decimal(f"1e{quote_asset_decimals}")

                        # calculate fees
                        tracked_market_order.fee_paid = tracked_market_order. \
                            executed_amount_quote * Decimal(tracked_market_order.fee_percent)

                        self.logger().info(f"The market sell order "
                                           f"{tracked_market_order.client_order_id} has completed according to "
                                           f"transaction hash {tracked_market_order.tx_hash}.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_market_order.client_order_id,
                                                                     tracked_market_order.base_asset,
                                                                     tracked_market_order.quote_asset,
                                                                     tracked_market_order.fee_asset,
                                                                     tracked_market_order.executed_amount_base,
                                                                     tracked_market_order.executed_amount_quote,
                                                                     tracked_market_order.fee_paid,
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

                self.c_stop_tracking_order(tracked_market_order.client_order_id)
        self._last_update_market_order_timestamp = current_timestamp

    cdef OrderBook c_get_order_book(self, str symbol):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if symbol not in order_books:
            raise ValueError(f"No order book exists for '{symbol}'.")
        return order_books[symbol]

    cdef object c_get_order_price_quantum(self, str symbol, object price):
        base_asset, quote_asset = self.split_symbol(symbol)
        base_asset_decimals = self._assets_decimals[base_asset]
        quote_asset_decimals = self._assets_decimals[quote_asset]

        decimals_quantum = Decimal(
            f"1e-{min(base_asset_decimals, quote_asset_decimals)}")
        return decimals_quantum

    cdef object c_get_order_size_quantum(self, str symbol, object amount):
        base_asset, quote_asset = self.split_symbol(symbol)
        base_asset_decimals = self._assets_decimals[base_asset]
        quote_asset_decimals = self._assets_decimals[quote_asset]

        decimals_quantum = Decimal(
            f"1e-{min(base_asset_decimals, quote_asset_decimals)}")
        return decimals_quantum

    cdef object c_quantize_order_amount(self, str symbol, object amount, object price = s_decimal_0):
        quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)

        if quantized_amount < 0:
            return s_decimal_0

        return quantized_amount

    cdef c_cancel(self, str symbol, str order_id):
        return order_id

    cdef str c_buy(self,
                   str symbol,
                   object amount,
                   object order_type = OrderType.MARKET,
                   object price = s_decimal_0,
                   dict kwargs = {}):

        if order_type is not OrderType.MARKET:
            raise NotImplementedError("Only market order can implemented")

        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"buy-{symbol}-{tracking_nonce}")

        safe_ensure_future(self.execute_buy(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_buy(self,
                          order_id: str,
                          symbol: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Decimal) -> str:
        if order_type is not OrderType.MARKET:
            raise NotImplementedError("Only market order can implemented")

        cdef:
            object q_amt = self.c_quantize_order_amount(symbol, amount)

        if q_amt <= 0:
            raise ValueError("Order amount is lower than or equal to 0")

        try:
            base_asset, quote_asset = self.split_symbol(symbol)
            base_asset_token = self._stl_cont.get_token(base_asset)
            quote_asset_token = self._stl_cont.get_token(quote_asset)
            base_asset_decimals = await base_asset_token.get_decimals()
            quote_asset_decimals = await quote_asset_token.get_decimals()
            current_price = self.get_price(symbol, True)
            price_including_fees = current_price * Decimal(1 + self._contract_fees)
            input_amount = int(q_amt * Decimal(f"1e{quote_asset_decimals}") * price_including_fees)
            min_output_amount = self._stl_cont.token_output_amount_after_fees(
                input_amount, quote_asset_token.address,
                base_asset_token.address)

            tx_hash = self._wallet.execute_transaction(
                self._stl_cont._contract.functions.swapTokens(
                    quote_asset_token.address, base_asset_token.address,
                    input_amount, min_output_amount, int(self._current_timestamp + 60 * 60))
            )

            self.c_start_tracking_order(order_id, symbol, TradeType.BUY,
                                        order_type, q_amt, s_decimal_0, tx_hash, base_asset,
                                        float(self._contract_fees))

            self.logger().info(f"Created market buy order for {q_amt} {symbol}.")
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     float(q_amt),
                                     0.0,
                                     order_id
                                 ))
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting buy order to Stablecoinswap for {amount} {symbol}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Stablecoinswap: {e}"
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp,
                                                         order_id,
                                                         order_type)
                                 )

    cdef str c_sell(self,
                    str symbol,
                    object amount,
                    object order_type = OrderType.MARKET,
                    object price = s_decimal_0,
                    dict kwargs = {}):

        if order_type is not OrderType.MARKET:
            raise NotImplementedError("Only market order can implemented")

        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")

        safe_ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           symbol: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Decimal) -> str:

        if order_type is not OrderType.MARKET:
            raise NotImplementedError("Only market order can implemented")

        cdef:
            object q_amt = self.c_quantize_order_amount(symbol, amount)

        if q_amt <= 0:
            raise ValueError("Order amount is lower than or equal to 0")

        try:
            base_asset, quote_asset = self.split_symbol(symbol)
            base_asset_token = self._stl_cont.get_token(base_asset)
            quote_asset_token = self._stl_cont.get_token(quote_asset)
            base_asset_decimals = await base_asset_token.get_decimals()
            quote_asset_decimals = await quote_asset_token.get_decimals()
            input_amount = int(q_amt * 10 ** base_asset_decimals)
            min_output_amount = self._stl_cont.token_output_amount_after_fees(
                input_amount, base_asset_token.address,
                quote_asset_token.address)

            tx_hash = self._wallet.execute_transaction(
                self._stl_cont._contract.functions.swapTokens(
                    base_asset_token.address, quote_asset_token.address,
                    input_amount, min_output_amount, int(self._current_timestamp + 60 * 60))
            )

            self.c_start_tracking_order(order_id, symbol, TradeType.SELL,
                                        order_type, q_amt, s_decimal_0, tx_hash, quote_asset,
                                        float(self._contract_fees))

            self.logger().info(f"Created market sell order for {q_amt} {symbol}.")
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     float(q_amt),
                                     0.0,
                                     order_id
                                 ))
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting sell order to Stablecoinswap for {amount} {symbol}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Stablecoinswap: {e}"
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp,
                                                         order_id,
                                                         order_type)
                                 )

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str symbol,
                                object trade_type,
                                object order_type,
                                object amount,
                                object price,
                                str tx_hash,
                                str fee_asset,
                                object fee_percent):
        self._in_flight_orders[client_order_id] = StablecoinswapInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=None,
            symbol=symbol,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            tx_hash=tx_hash,
            fee_asset=fee_asset,
            fee_percent=fee_percent
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]
