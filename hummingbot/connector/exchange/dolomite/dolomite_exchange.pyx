import aiohttp
import asyncio
import binascii
import json
import time
import uuid
import traceback
from typing import (
    Any,
    Dict,
    List,
    Optional
)
import math
import logging
from decimal import *
from libc.stdint cimport int64_t
from web3 import Web3
from web3.exceptions import TransactionNotFound
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.connector.exchange.dolomite.dolomite_order_book_tracker import DolomiteOrderBookTracker
from hummingbot.connector.exchange.dolomite.dolomite_api_order_book_data_source import DolomiteAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
)
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    MarketOrderFailureEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    TradeType,
    OrderType,
    TradeFee,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.dolomite.dolomite_in_flight_order cimport DolomiteInFlightOrder
from hummingbot.connector.exchange.dolomite.dolomite_util cimport(
    DolomiteTradingRule,
)
from hummingbot.connector.exchange.dolomite.dolomite_util import (
    unpad,
    sha3,
    DolomiteExchangeRates,
    DolomiteExchangeInfo
)
from hummingbot.core.utils.estimate_fee import estimate_fee

s_logger = None
s_decimal_0 = Decimal(0)


def num_d(amount):
    return abs(Decimal(amount).normalize().as_tuple().exponent)


def round_d(amount, n):
    if n < 1:
        return Decimal(int(amount))
    else:
        quantum = Decimal('0.' + ('0' * (n - 1)) + '1')
        return Decimal(str(amount)).quantize(quantum, rounding=ROUND_HALF_DOWN).normalize()


def now():
    return int(time.time()) * 1000


BUY_ORDER_COMPLETED_EVENT = MarketEvent.BuyOrderCompleted.value
SELL_ORDER_COMPLETED_EVENT = MarketEvent.SellOrderCompleted.value
ORDER_CANCELLED_EVENT = MarketEvent.OrderCancelled.value
ORDER_EXPIRED_EVENT = MarketEvent.OrderExpired.value
ORDER_FILLED_EVENT = MarketEvent.OrderFilled.value
ORDER_FAILURE_EVENT = MarketEvent.OrderFailure.value
BUY_ORDER_CREATED_EVENT = MarketEvent.BuyOrderCreated.value
SELL_ORDER_CREATED_EVENT = MarketEvent.SellOrderCreated.value
API_CALL_TIMEOUT = 10.0

# ==========================================================


MAINNET_API_REST_ENDPOINT = "https://exchange-api.dolomite.io"
MAINNET_WS_ENDPOINT = "wss://exchange-api.dolomite.io/ws-connect"

TESTNET_API_REST_ENDPOINT = "https://exchange-api-test.dolomite.io"
TESTNET_WS_ENDPOINT = "wss://exchange-api-test.dolomite.io/ws-connect"

EXCHANGE_INFO_ROUTE = "/v1/info"
MARKETS_ROUTE = "/v1/markets?hydrate_all=true"
PORTFOLIO_ROUTE = "/v1/addresses/:address/portfolio"
FEE_REBATE_ROUTE = "/v1/addresses/:address/rebates"
ACCOUNT_INFO_ROUTE = "/v1/addresses/:address/info"
EXCHANGE_RATES_ROUTE = "/v1/tokens/rates/latest"
HASH_ORDER_ROUTE = "/v1/orders/hash"
CREATE_ORDER_ROUTE = "/v1/orders/create"
CANCEL_ORDER_ROUTE = "/v1/orders/:order_id/cancel"
GET_ORDERS_BY_ADDR_ROUTE = "/v1/orders/addresses/:address"
GET_ORDER_ROUTE = "/v1/orders/:order_id"
GET_ORDER_FILLS_ROUTE = "/v1/orders/:order_id/fills"
MAXIMUM_FILL_COUNT = 16

cdef class DolomiteExchangeTransactionTracker(TransactionTracker):
    cdef:
        DolomiteExchange _owner

    def __init__(self, owner: DolomiteExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)

cdef class DolomiteExchange(ExchangeBase):
    # This causes it to hang when starting network
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 wallet: Web3Wallet,
                 ethereum_rpc_url: str,
                 poll_interval: float = 10.0,
                 trading_pairs: Optional[List[str]] = None,
                 isTestNet: bool = False,
                 trading_required: bool = True):

        super().__init__()

        self.API_REST_ENDPOINT = TESTNET_API_REST_ENDPOINT if isTestNet else MAINNET_API_REST_ENDPOINT
        self.WS_ENDPOINT = TESTNET_WS_ENDPOINT if isTestNet else MAINNET_WS_ENDPOINT
        self._order_book_tracker = DolomiteOrderBookTracker(
            OrderBookTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=trading_pairs,
            rest_api_url=self.API_REST_ENDPOINT,
            websocket_url=self.WS_ENDPOINT
        )
        self._tx_tracker = DolomiteExchangeTransactionTracker(self)
        self._trading_required = trading_required
        self._wallet = wallet
        self._web3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._poll_interval = poll_interval
        self._shared_client = None
        self._polling_update_task = None

        # State
        self._account_balances = {}
        self._account_available_balances = {}
        self._trading_rules = {}
        self._exchange_info = None
        self._exchange_rates = None
        self._pending_approval_tx_hashes = set()
        self._in_flight_orders = {}

    @property
    def name(self) -> str:
        return "dolomite"

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": len(self._order_book_tracker.order_books) > 0,
            "account_balances": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True,
            "token_approval": len(self._pending_approval_tx_hashes) == 0 if self._trading_required else True,
        }

    # ----------------------------------------
    # Markets & Order Books

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef dict order_books = self._order_book_tracker.order_books
        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            list retval = []
            DolomiteInFlightOrder dolomite_flight_order

        for in_flight_order in self._in_flight_orders.values():
            dolomite_flight_order = in_flight_order
            if dolomite_flight_order.order_type is OrderType.LIMIT:
                retval.append(dolomite_flight_order.to_limit_order())
        return retval

    @property
    def in_flight_orders(self) -> Dict[str, DolomiteInFlightOrder]:
        return self._in_flight_orders

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await DolomiteAPIOrderBookDataSource.get_active_exchange_markets()

    # ----------------------------------------
    # Account Balances

    cdef object c_get_balance(self, str currency):
        return self._account_balances[currency]

    cdef object c_get_available_balance(self, str currency):
        return self._account_available_balances[currency]

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances

    # ==========================================================
    # Order Submission
    # ----------------------------------------------------------

    async def place_order(self, client_order_id, trading_pair, order_side, amount, order_type, price):
        try:
            trading_rule = self._trading_rules[trading_pair]
            exchange_info = self._exchange_info

            # Check order type support
            if order_type == OrderType.LIMIT and trading_rule.supports_limit_orders is False:
                raise ValueError("LIMIT orders are not supported")
            elif order_type == OrderType.MARKET and trading_rule.supports_market_orders is False:
                raise ValueError("MARKET orders are not supported")

            # Calculate amounts and get token info
            primary_token = trading_rule.primary_token
            secondary_token = trading_rule.secondary_token
            fee_token = trading_rule.primary_token if order_side is TradeType.BUY else trading_rule.secondary_token

            if price is None or math.isnan(price) or price == 0.0:
                price = None
                primary_amount = self.c_quantize_order_amount(trading_pair, Decimal(amount))
            else:
                price = self.c_quantize_order_price(trading_pair, Decimal(price))
                primary_amount = self.c_quantize_order_amount(trading_pair, Decimal(amount), price)

            (__,
             secondary_amount,
             fee_amount,
             num_taker_matches,
             fee_per_fill,
             network_fee_premium
             ) = self.calculate_order_fill_and_fee(trading_pair, order_type, order_side, primary_amount, price)

            if price is None:
                price = self.c_quantize_order_price(trading_pair, secondary_amount / primary_amount)

            # Check order size limitations
            minimum_order_size = trading_rule.min_order_size
            maximum_order_size = trading_rule.max_order_size

            if secondary_amount < minimum_order_size:
                raise ValueError(f"Order size of {secondary_amount} {secondary_token.ticker} "
                                 f"is below order minimum of {round(minimum_order_size, 2)} {secondary_token.ticker}")
            elif secondary_amount > maximum_order_size:
                raise ValueError(f"Order size of {secondary_amount} {secondary_token.ticker} "
                                 f"is greater than order maximum of {round(maximum_order_size, 2)} {secondary_token.ticker}")

            # Get order hash for signing
            dual_auth_wallet = self._web3.eth.account.create()
            dual_auth_address = str(dual_auth_wallet.address)
            dual_auth_private_key = str(binascii.hexlify(dual_auth_wallet.privateKey).decode("utf-8"))

            unsigned_order = {
                "owner_address": self._wallet.address,
                "market": f"{primary_token.contract_address}-{secondary_token.contract_address}",
                "order_type": order_type.name,
                "order_side": order_side.name,
                "primary_padded_amount": primary_token.pad(primary_amount),
                "secondary_padded_amount": secondary_token.pad(secondary_amount),
                "fee_token_address": fee_token.contract_address,
                "fee_padded_amount": fee_token.pad(fee_amount),
                "base_taker_gas_fee_padded_amount": fee_token.pad(fee_per_fill),
                "taker_gas_fee_premium_padded_amount": fee_token.pad(network_fee_premium),
                "max_number_of_taker_matches": num_taker_matches,
                "creation_timestamp": (int(time.time()) - 300) * 1000,
                # 5 minutes earlier to avoid issue with block times
                "fee_collecting_wallet_address": exchange_info.fee_collecting_wallet_address,
                "auth_address": dual_auth_address,
                "auth_private_key": dual_auth_private_key,
                "wallet_split_percentage": 0,
                "order_recipient_address": None,
                "expiration_timestamp": None,
                "dependent_transaction_hash": None,
                "extra_data": None,
                "order_hash": None,
                "ecdsa_multi_hash_signature": None
            }

            order_hash_response = await self.api_request("POST", HASH_ORDER_ROUTE, data=unsigned_order)
            order_hash = order_hash_response["data"]["order_hash"]

            # Sign order hash
            signature = self._wallet.current_backend.sign_hash(hexstr=order_hash)
            algo = "0041"
            r = signature[2:66]
            s = signature[66:130]
            v = signature[130:132]
            multihash_signature = f"0x{algo}{v}{r}{s}"

            # Submit order
            signed_order = unsigned_order.copy()
            signed_order["order_hash"] = order_hash
            signed_order["ecdsa_multi_hash_signature"] = multihash_signature

            creation_response = await self.api_request("POST", CREATE_ORDER_ROUTE, data=signed_order)
            dolomite_order = creation_response["data"]
            in_flight_order = DolomiteInFlightOrder.from_dolomite_order(dolomite_order, client_order_id, self)

            # Begin tracking order
            self.start_tracking(in_flight_order)
            self.logger().info(
                f"Created {in_flight_order.description} order {client_order_id} for {primary_amount} {primary_token.ticker}.")

            if order_side is TradeType.BUY:
                buy_event = BuyOrderCreatedEvent(now(), order_type, trading_pair, Decimal(primary_amount),
                                                 Decimal(price),
                                                 client_order_id)
                self.c_trigger_event(BUY_ORDER_CREATED_EVENT, buy_event)
            else:
                sell_event = SellOrderCreatedEvent(now(), order_type, trading_pair, Decimal(primary_amount),
                                                   Decimal(price),
                                                   client_order_id)
                self.c_trigger_event(SELL_ORDER_CREATED_EVENT, sell_event)

        except Exception as e:
            order_type_str = order_type.name.lower()
            order_side_str = order_side.name.lower()

            self.logger().warn(f"Error submitting {order_side_str} {order_type_str} order to Dolomite for "
                               f"{primary_amount} {primary_token.ticker} at {price} {secondary_token.ticker}.")
            self.logger().info(e)
            traceback.print_exc()

            self.stop_tracking(client_order_id)
            self.c_trigger_event(ORDER_FAILURE_EVENT, MarketOrderFailureEvent(now(), client_order_id, order_type))

    cdef str c_buy(self, str trading_pair, object amount, object order_type = OrderType.MARKET, object price = 0.0,
                   dict kwargs = {}):
        cdef str client_order_id = str(uuid.uuid1())[:8]
        safe_ensure_future(self.place_order(client_order_id, trading_pair, TradeType.BUY, amount, order_type, price))
        return client_order_id

    cdef str c_sell(self, str trading_pair, object amount, object order_type = OrderType.MARKET, object price = 0.0,
                    dict kwargs = {}):
        cdef str client_order_id = str(uuid.uuid1())[:8]
        safe_ensure_future(self.place_order(client_order_id, trading_pair, TradeType.SELL, amount, order_type, price))
        return client_order_id

    # ----------------------------------------
    # Cancellation

    async def cancel_order(self, client_order_id: str):
        in_flight_order = self._in_flight_orders.get(client_order_id)
        cancellation_event = OrderCancelledEvent(now(), client_order_id)

        if in_flight_order is None:
            self.c_trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)
            return

        try:
            (timestamp, signature) = self._sign_timestamp()

            cancellation_payload = {
                "owner_address": self._wallet.address,
                "ecdsa_signature": signature,
                "cancellation_timestamp": timestamp
            }

            cancel_route = CANCEL_ORDER_ROUTE.replace(':order_id', in_flight_order.exchange_order_id)
            await self.api_request("POST", cancel_route, data=cancellation_payload)

            self.logger().info(f"Successfully cancelled order {client_order_id}")
            self.stop_tracking(client_order_id)
            self.c_trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)

        except Exception as e:
            self.logger().info(f"Failed to cancel order {client_order_id}")
            self.logger().debug(e)

    cdef c_cancel(self, str trading_pair, str client_order_id):
        safe_ensure_future(self.cancel_order(client_order_id))

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        results = []
        cancellation_queue = self._in_flight_orders.copy()
        for order_id, in_flight in cancellation_queue.iteritems():
            try:
                await self.cancel_order(order_id)
                results.append(CancellationResult(order_id=order_id, success=True))
            except Exception:
                results.append(CancellationResult(order_id=order_id, success=False))
        return results

    # ----------------------------------------
    # Estimation

    def calculate_order_fill_and_fee(self,
                                     trading_pair: str,
                                     order_type: OrderType,
                                     order_side: TradeType,
                                     amount: Decimal,
                                     price: Decimal = None) -> (TradeFee, Decimal, Decimal, int, Decimal, Decimal):
        """
        Returns (_, <fill_amount>, <fee_amount>, <taker_fill_count>, <base_fee_per_fill>, <network_fee_premium>)
        """
        order_book = self.c_get_order_book(trading_pair)
        exchange_info = self._exchange_info
        trading_rule = self._trading_rules[trading_pair]
        maker_fee_percentage = Decimal(exchange_info.maker_fee_percentage)
        taker_fee_percentage = Decimal(exchange_info.taker_fee_percentage)

        if order_type is OrderType.LIMIT:
            secondary_amount = self.c_quantize_order_amount(trading_pair, amount * price)
            service_fee = max(Decimal(maker_fee_percentage) * secondary_amount, s_decimal_0)
            return TradeFee(percent=maker_fee_percentage), secondary_amount, service_fee, 0, s_decimal_0, s_decimal_0

        else:
            if order_side is TradeType.BUY:
                filled_rows = order_book.simulate_buy(Decimal(amount))
            else:
                filled_rows = order_book.simulate_sell(Decimal(amount))

            fill_count = 0 if len(filled_rows) == 0 else MAXIMUM_FILL_COUNT

            if fill_count == 0:
                raise ValueError(
                    "Unfillable MARKET order: {order_side} of {amount} {trading_rule.secondary_token.ticker}")

            book_query = order_book.get_quote_volume_for_base_amount(order_side is TradeType.BUY, Decimal(amount))
            fill_amount_secondary = self.c_quantize_order_amount(trading_pair, Decimal(book_query.result_volume))

            fee_token = trading_rule.primary_token if order_side is TradeType.BUY else trading_rule.secondary_token
            fee_per_fill = exchange_info.per_fill_fee_registry[fee_token.ticker]
            network_fee_premium = exchange_info.spot_trading_fee_premium_registry[fee_token.ticker]
            network_fee = (fee_per_fill * Decimal(fill_count)) + network_fee_premium

            secondary_ticker = trading_rule.secondary_token.ticker
            service_fee_in_secondary = Decimal(taker_fee_percentage) * fill_amount_secondary
            service_fee = self._exchange_rates.convert(service_fee_in_secondary, secondary_ticker, fee_token.ticker)
            fee_amount = self.c_quantize_order_amount(trading_pair, max(service_fee + network_fee, s_decimal_0))

            trade_fee = TradeFee(percent=taker_fee_percentage, flat_fees=[(fee_token.ticker, Decimal(network_fee))])
            return trade_fee, fill_amount_secondary, fee_amount, fill_count, fee_per_fill, network_fee_premium

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        """
        cdef:
            tuple order_fill_and_fee_result = self.calculate_order_fill_and_fee(
                trading_pair=f"{base_currency}-{quote_currency}",
                order_type=order_type,
                order_side=order_side,
                amount=Decimal(amount),
                price=(None if price is None else Decimal(price)))
        return order_fill_and_fee_result[0]
        """
        is_maker = order_type is OrderType.LIMIT
        return estimate_fee("dolomite", is_maker)

    cdef object c_get_price(self, str trading_pair, bint is_buy):
        cdef OrderBook order_book = self.c_get_order_book(trading_pair)
        return Decimal(order_book.c_get_price(is_buy))

    # ==========================================================
    # Runtime
    # ----------------------------------------------------------

    async def start_network(self):
        await self.stop_network()
        self._order_book_tracker.start()
        self._polling_update_task = safe_ensure_future(self._polling_update())

        if self._trading_required:
            exchange_info = await self.api_request("GET", EXCHANGE_INFO_ROUTE)
            spender_address = exchange_info["data"]["loopring_delegate_address"]
            tx_hashes = await self._wallet.current_backend.check_and_fix_approval_amounts(spender=spender_address)
            self._pending_approval_tx_hashes.update(tx_hashes)

    async def stop_network(self):
        self._order_book_tracker.stop()
        self._pending_approval_tx_hashes.clear()
        self._polling_update_task = None

    async def check_network(self) -> NetworkStatus:
        if self._wallet.network_status is not NetworkStatus.CONNECTED:
            return NetworkStatus.NOT_CONNECTED
        try:
            await self.api_request("GET", EXCHANGE_INFO_ROUTE)
            try:
                await self.api_request("GET", ACCOUNT_INFO_ROUTE.replace(':address', self._wallet.address))
            except Exception:
                self.logger().warning(f"No Dolomite account for {self._wallet.address}.")
                self.logger().warning(f"Create an account on the exchange at https://dolomite.io by either: ")
                self.logger().warning(f"1) submitting a trade if you are located OUTSIDE the US or 2) creating an account if you are located WITHIN the US")
                return NetworkStatus.NOT_CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    # ----------------------------------------
    # State Management

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        for order_id, in_flight_json in saved_states.iteritems():
            self._in_flight_orders[order_id] = DolomiteInFlightOrder.from_json(in_flight_json, self)

    def start_tracking(self, in_flight_order):
        self._in_flight_orders[in_flight_order.client_order_id] = in_flight_order

    def stop_tracking(self, client_order_id):
        if client_order_id in self._in_flight_orders:
            del self._in_flight_orders[client_order_id]

    # ----------------------------------------
    # Polling Updates

    async def _polling_update(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await asyncio.gather(
                    self._update_balances(),
                    self._update_trading_rules(),
                    self._update_order_status(),
                    self._update_pending_approvals()
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().warn("Failed to fetch updates on Dolomite. Check network connection.")
                self.logger().info(e)

    async def _update_balances(self):
        balances_route = PORTFOLIO_ROUTE.replace(':address', self._wallet.address)
        fee_rebates_route = FEE_REBATE_ROUTE.replace(':address', self._wallet.address)
        balances_response = await self.api_request("GET", balances_route)
        fee_rebates_response = await self.api_request("GET", fee_rebates_route)

        balances = balances_response["data"]
        fee_rebates = fee_rebates_response["data"]
        available_balances = balances.copy()

        # Add fee rebate balance to token balance so profitibility is properly calculated
        for ticker, balance_info in balances.iteritems():
            if ticker in fee_rebates.keys():
                balances[ticker] = unpad(balance_info["balance"]) + unpad(fee_rebates[ticker])
            else:
                balances[ticker] = unpad(balance_info["balance"])

        for ticker, balance_info in available_balances.iteritems():
            available_balances[ticker] = unpad(balance_info["balance"]) - unpad(balance_info["committed"])

        self._account_balances = balances
        self._account_available_balances = available_balances

    async def _update_trading_rules(self):
        markets, exchange_info, account_info, raw_rates = await asyncio.gather(
            self.api_request("GET", MARKETS_ROUTE),
            self.api_request("GET", EXCHANGE_INFO_ROUTE),
            self.api_request("GET", ACCOUNT_INFO_ROUTE.replace(':address', self._wallet.address)),
            self.api_request("GET", EXCHANGE_RATES_ROUTE)
        )

        exchange_info = DolomiteExchangeInfo.from_json(exchange_info["data"])
        exchange_rates = DolomiteExchangeRates(raw_rates["data"])
        account_info = account_info["data"]
        token_registry = markets["global_objects"]["tokens"]
        trading_rules = dict([(market["market"], market) for market in markets["data"]])

        for trading_pair, market in trading_rules.iteritems():
            trading_rules[trading_pair] = DolomiteTradingRule.build(trading_pair, market, exchange_info, account_info,
                                                                    exchange_rates, token_registry)

        self._exchange_info = exchange_info
        self._exchange_rates = exchange_rates
        self._trading_rules = trading_rules

    async def _update_order_status(self):
        tracked_orders = self._in_flight_orders.copy()

        for client_order_id, tracked_order in tracked_orders.iteritems():
            dolomite_order_id = tracked_order.exchange_order_id

            try:
                dolomite_order_request = await self.api_request("GET",
                                                                GET_ORDER_ROUTE.replace(":order_id", dolomite_order_id))
                dolomite_order = dolomite_order_request["data"]
            except Exception:
                self.logger().warn(f"Failed to fetch tracked Dolomite order {tracked_order.identifier} from api")
                continue

            (primary_ticker, secondary_ticker) = self.split_trading_pair(dolomite_order["market"])

            try:
                get_order_fills_route = GET_ORDER_FILLS_ROUTE.replace(':order_id', dolomite_order_id)
                dolomite_order_fills_response = await self.api_request("GET", get_order_fills_route)
                dolomite_order_fills = dolomite_order_fills_response["data"]

                fill_events = tracked_order.apply_update(dolomite_order, dolomite_order_fills,
                                                         self._exchange_info, self._exchange_rates)

                # Track order fills
                for fill_event in fill_events:
                    self.logger().info(f"Filled {fill_event.amount} out of {tracked_order.amount} {primary_ticker} "
                                       f"of the {tracked_order.description} order {client_order_id}.")
                    self.c_trigger_event(ORDER_FILLED_EVENT, fill_event)

                # Track order state changes
                if tracked_order.is_done:
                    self.logger().info(f"The {tracked_order.description} order {client_order_id} has been FILLED.")
                    self.stop_tracking(client_order_id)

                    if tracked_order.trade_type is TradeType.BUY:
                        buy_complete_event = BuyOrderCompletedEvent(
                            timestamp=now(),
                            order_id=client_order_id,
                            order_type=tracked_order.order_type,
                            base_asset=primary_ticker,
                            quote_asset=secondary_ticker,
                            fee_asset=tracked_order.fee_asset,
                            base_asset_amount=Decimal(tracked_order.executed_amount_base),
                            quote_asset_amount=Decimal(tracked_order.executed_amount_quote),
                            fee_amount=Decimal(tracked_order.fee_paid))
                        self.c_trigger_event(BUY_ORDER_COMPLETED_EVENT, buy_complete_event)
                    else:
                        sell_complete_event = SellOrderCompletedEvent(
                            timestamp=now(),
                            order_id=client_order_id,
                            order_type=tracked_order.order_type,
                            base_asset=primary_ticker,
                            quote_asset=secondary_ticker,
                            fee_asset=tracked_order.fee_asset,
                            base_asset_amount=Decimal(tracked_order.executed_amount_base),
                            quote_asset_amount=Decimal(tracked_order.executed_amount_quote),
                            fee_amount=Decimal(tracked_order.fee_paid))
                        self.c_trigger_event(SELL_ORDER_COMPLETED_EVENT, sell_complete_event)

                elif tracked_order.is_cancelled:
                    self.logger().info(f"The {tracked_order.description} order {client_order_id} has been CANCELLED.")
                    self.stop_tracking(client_order_id)
                    self.c_trigger_event(ORDER_CANCELLED_EVENT, OrderCancelledEvent(now(), client_order_id))

                elif tracked_order.is_expired:
                    self.logger().info(f"The {tracked_order.description} order {client_order_id} has EXPIRED.")
                    self.stop_tracking(client_order_id)
                    self.c_trigger_event(ORDER_EXPIRED_EVENT, OrderExpiredEvent(now(), client_order_id))

                elif tracked_order.is_failure:
                    self.logger().warn(f"The {tracked_order.description} order {client_order_id} has FAILED. "
                                       f"This can occur when on-chain settlement fails and the order cannot be placed again")
                    self.stop_tracking(client_order_id)
                    self.c_trigger_event(ORDER_FAILURE_EVENT,
                                         MarketOrderFailureEvent(now(), client_order_id, tracked_order.order_type))

            except Exception as e:
                self.logger().warn(f"Failed to update Dolomite order {tracked_order.identifier}")
                self.logger().debug(e)

    async def _update_pending_approvals(self):
        if len(self._pending_approval_tx_hashes) > 0:
            try:
                for tx_hash in list(self._pending_approval_tx_hashes):
                    try:
                        receipt = self._web3.eth.getTransactionReceipt(tx_hash)
                        self._pending_approval_tx_hashes.remove(tx_hash)
                    except TransactionNotFound:
                        pass
            except Exception as e:
                self.logger().warn("Could not get token approval status. Check Ethereum wallet and network connection.")
                self.logger().debug(e)

    # ==========================================================
    # Miscellaneous
    # ----------------------------------------------------------

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        return Decimal(f"1e-{self._trading_rules[trading_pair].price_decimal_places}")

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        return Decimal(f"1e-{self._trading_rules[trading_pair].amount_decimal_places}")

    cdef object c_quantize_order_price(self, str trading_pair, object price):
        return round_d(price, self._trading_rules[trading_pair].price_decimal_places)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price = 0.0):
        return round_d(amount, self._trading_rules[trading_pair].amount_decimal_places)

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t> (self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t> (timestamp / self._poll_interval)

        self._tx_tracker.c_tick(timestamp)
        ExchangeBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def _sign_timestamp(self):
        timestamp = now()
        timestamp_hash = sha3(str(timestamp).encode("utf-8"))
        signature = self._wallet.current_backend.sign_hash(hexstr=timestamp_hash)
        signature = {
            "r": signature[0:66],
            "s": "0x" + signature[66:130],
            "v": int(signature[130:132], 16)
        }
        return timestamp, signature

    async def api_request(self, http_method: str, url: str, data: Optional[Dict[str, Any]] = None,
                          params: Optional[Dict[str, Any]] = None,
                          headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:

        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()

        if data is not None and http_method == "POST":
            data = json.dumps(data).encode('utf8')
            headers = {"Content-Type": "application/json"}

        full_url = f"{self.API_REST_ENDPOINT}{url}"
        async with self._shared_client.request(http_method, url=full_url,
                                               timeout=API_CALL_TIMEOUT,
                                               data=data, params=params, headers=headers) as response:
            if response.status != 200:
                self.logger().info(f"Issue with Dolomite API {http_method} to {url}, response: ")
                self.logger().info(await response.text())
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
            data = await response.json()
            return data

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
