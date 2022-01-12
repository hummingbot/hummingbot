import asyncio
import json
import logging
import time
import warnings
from collections import defaultdict
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

from dateutil.parser import parse as dateparse

from dydx3.errors import DydxApiError
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth import DydxPerpetualAuth
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper import DydxPerpetualClientWrapper
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_fill_report import DydxPerpetualFillReport
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_in_flight_order import DydxPerpetualInFlightOrder
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book_tracker import \
    DydxPerpetualOrderBookTracker
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_position import DydxPerpetualPosition
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_tracker import \
    DydxPerpetualUserStreamTracker
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_utils import build_api_factory
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import (BuyOrderCompletedEvent, BuyOrderCreatedEvent, FundingInfo,
                                          FundingPaymentCompletedEvent, MarketEvent, MarketOrderFailureEvent,
                                          OrderCancelledEvent, OrderExpiredEvent, OrderFilledEvent, OrderType,
                                          PositionAction, PositionMode, PositionSide, SellOrderCompletedEvent,
                                          SellOrderCreatedEvent, TradeType)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.logger import HummingbotLogger

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")


def now():
    return int(time.time()) * 1000


BUY_ORDER_COMPLETED_EVENT = MarketEvent.BuyOrderCompleted
SELL_ORDER_COMPLETED_EVENT = MarketEvent.SellOrderCompleted
ORDER_CANCELLED_EVENT = MarketEvent.OrderCancelled
ORDER_EXPIRED_EVENT = MarketEvent.OrderExpired
ORDER_FILLED_EVENT = MarketEvent.OrderFilled
ORDER_FAILURE_EVENT = MarketEvent.OrderFailure
MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG = MarketEvent.FundingPaymentCompleted
BUY_ORDER_CREATED_EVENT = MarketEvent.BuyOrderCreated
SELL_ORDER_CREATED_EVENT = MarketEvent.SellOrderCreated
API_CALL_TIMEOUT = 10.0

# ==========================================================
UNRECOGNIZED_ORDER_DEBOUCE = 60  # seconds


class LatchingEventResponder(EventListener):
    def __init__(self, callback: any, num_expected: int):
        super().__init__()
        self._callback = callback
        self._completed = asyncio.Event()
        self._num_remaining = num_expected

    def __call__(self, arg: any):
        if self._callback(arg):
            self._reduce()

    def _reduce(self):
        self._num_remaining -= 1
        if self._num_remaining <= 0:
            self._completed.set()

    async def wait_for_completion(self, timeout: float):
        try:
            await asyncio.wait_for(self._completed.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        return self._completed.is_set()

    def cancel_one(self):
        self._reduce()


class DydxPerpetualDerivativeTransactionTracker(TransactionTracker):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    def did_timeout_tx(self, tx_id: str):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.did_timeout_tx(tx_id)


class DydxPerpetualDerivative(ExchangeBase, PerpetualTrading):
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(
        self,
        dydx_perpetual_api_key: str,
        dydx_perpetual_api_secret: str,
        dydx_perpetual_passphrase: str,
        dydx_perpetual_account_number: int,
        dydx_perpetual_ethereum_address: str,
        dydx_perpetual_stark_private_key: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):

        ExchangeBase.__init__(self)
        PerpetualTrading.__init__(self)
        self._real_time_balance_update = True
        self._api_factory = build_api_factory()
        self._order_book_tracker = DydxPerpetualOrderBookTracker(
            trading_pairs=trading_pairs,
            api_factory=self._api_factory,
        )
        self._tx_tracker = DydxPerpetualDerivativeTransactionTracker(self)
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_poll_timestamp = 0
        self._polling_update_task = None
        self._budget_checker = PerpetualBudgetChecker(self)

        self.dydx_client: DydxPerpetualClientWrapper = DydxPerpetualClientWrapper(
            api_key=dydx_perpetual_api_key,
            api_secret=dydx_perpetual_api_secret,
            passphrase=dydx_perpetual_passphrase,
            account_number=dydx_perpetual_account_number,
            stark_private_key=dydx_perpetual_stark_private_key,
            ethereum_address=dydx_perpetual_ethereum_address,
        )
        # State
        self._dydx_auth = DydxPerpetualAuth(self.dydx_client)
        self._user_stream_tracker = DydxPerpetualUserStreamTracker(
            dydx_auth=self._dydx_auth, api_factory=self._api_factory
        )
        self._user_stream_event_listener_task = None
        self._user_stream_tracker_task = None
        self._lock = asyncio.Lock()
        self._trading_rules = {}
        self._in_flight_orders = {}
        self._trading_pairs = trading_pairs
        self._fee_rules = {}
        self._reserved_balances = {}
        self._unclaimed_fills = defaultdict(set)
        self._in_flight_orders_by_exchange_id = {}
        self._orders_pending_ack = set()
        self._position_mode = PositionMode.ONEWAY
        self._margin_fractions = {}
        self._trading_pair_last_funding_payment_ts: Dict[str, float] = {}

    @property
    def name(self) -> str:
        return "dydx_perpetual"

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": len(self._order_book_tracker.order_books) > 0,
            "account_balances": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True,
            "funding_info_available": len(self._funding_info) > 0 if self._trading_required else True,
            "user_stream_tracker_ready": self._user_stream_tracker.data_source.last_recv_time > 0
            if self._trading_required
            else True,
        }

    # ----------------------------------------
    # Markets & Order Books

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    def get_order_book(self, trading_pair: str):
        order_books = self._order_book_tracker.order_books
        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    @property
    def limit_orders(self) -> List[LimitOrder]:
        retval = []

        for in_flight_order in self._in_flight_orders.values():
            dydx_flight_order = in_flight_order
            if dydx_flight_order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]:
                retval.append(dydx_flight_order.to_limit_order())
        return retval

    @property
    def budget_checker(self) -> PerpetualBudgetChecker:
        return self._budget_checker

    # ----------------------------------------
    # Account Balances

    def get_balance(self, currency: str):
        return self._account_balances.get(currency, Decimal(0))

    def get_available_balance(self, currency: str):
        return self._account_available_balances.get(currency, Decimal(0))

    # ==========================================================
    # Order Submission
    # ----------------------------------------------------------

    @property
    def in_flight_orders(self) -> Dict[str, DydxPerpetualInFlightOrder]:
        return self._in_flight_orders

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _set_exchange_id(self, in_flight_order, exchange_order_id):
        in_flight_order.update_exchange_order_id(exchange_order_id)
        self._in_flight_orders_by_exchange_id[exchange_order_id] = in_flight_order

    def _claim_fills(self, in_flight_order, exchange_order_id):
        updated_with_fills = False

        # Claim any fill reports for this order that came in while we awaited this exchange id
        if exchange_order_id in self._unclaimed_fills:
            for fill in self._unclaimed_fills[exchange_order_id]:
                in_flight_order.register_fill(fill.id, fill.amount, fill.price, fill.fee)
                if self.position_key(in_flight_order.trading_pair) in self._account_positions:
                    position = self._account_positions[in_flight_order.trading_pair]
                    position.update_from_fill(in_flight_order, fill.price, fill.amount, self.get_balance("USD"))
                    updated_with_fills = True
                else:
                    self._account_positions[
                        self.position_key(in_flight_order.trading_pair)
                    ] = DydxPerpetualPosition.from_dydx_fill(
                        in_flight_order, fill.amount, fill.price, self.get_balance("USD")
                    )

            del self._unclaimed_fills[exchange_order_id]

        self._orders_pending_ack.discard(in_flight_order.client_order_id)
        if len(self._orders_pending_ack) == 0:
            # We are no longer waiting on any exchange order ids, so all uncalimed fills can be discarded
            self._unclaimed_fills.clear()

        if updated_with_fills:
            self._update_account_positions()

    async def place_order(
        self,
        client_order_id: str,
        trading_pair: str,
        amount: Decimal,
        is_buy: bool,
        order_type: OrderType,
        price: Decimal,
        limit_fee: Decimal,
        expiration: int,
    ) -> Dict[str, Any]:

        order_side = "BUY" if is_buy else "SELL"
        post_only = False
        if order_type is OrderType.LIMIT_MAKER:
            post_only = True
        dydx_order_type = "LIMIT" if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else "MARKET"

        return await self.dydx_client.place_order(
            market=trading_pair,
            side=order_side,
            amount=str(amount),
            price=str(price),
            order_type=dydx_order_type,
            postOnly=post_only,
            clientId=client_order_id,
            limit_fee=str(limit_fee),
            expiration=expiration,
        )

    async def execute_order(
        self, order_side, client_order_id, trading_pair, amount, order_type, position_action, price
    ):
        """
        Completes the common tasks from execute_buy and execute_sell.  Quantizes the order's amount and price, and
        validates the order against the trading rules before placing this order.
        """
        if position_action not in [PositionAction.OPEN, PositionAction.CLOSE]:
            raise ValueError("Specify either OPEN_POSITION or CLOSE_POSITION position_action.")
        # Quantize order
        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        # Check trading rules
        if order_type.is_limit_type():
            trading_rule = self._trading_rules[trading_pair]
            if amount < trading_rule.min_order_size:
                amount = s_decimal_0
        elif order_type == OrderType.MARKET:
            trading_rule = self._trading_rules[trading_pair]
        if order_type.is_limit_type() and trading_rule.supports_limit_orders is False:
            raise ValueError("LIMIT orders are not supported")
        elif order_type == OrderType.MARKET and trading_rule.supports_market_orders is False:
            raise ValueError("MARKET orders are not supported")

        if amount < trading_rule.min_order_size:
            raise ValueError(
                f"Order amount({str(amount)}) is less than the minimum allowable amount({str(trading_rule.min_order_size)})"
            )
        if amount > trading_rule.max_order_size:
            raise ValueError(
                f"Order amount({str(amount)}) is greater than the maximum allowable amount({str(trading_rule.max_order_size)})"
            )
        if amount * price < trading_rule.min_notional_size:
            raise ValueError(
                f"Order notional value({str(amount * price)}) is less than the minimum allowable notional value for an order ({str(trading_rule.min_notional_size)})"
            )

        try:
            created_at: int = int(self.time_now_s())
            self.start_tracking_order(
                order_side,
                client_order_id,
                order_type,
                created_at,
                None,
                trading_pair,
                price,
                amount,
                self._leverage[trading_pair],
                position_action.name,
            )
            expiration = created_at + 600
            limit_fee = 0.015
            try:
                creation_response = await self.place_order(
                    client_order_id,
                    trading_pair,
                    amount,
                    order_side is TradeType.BUY,
                    order_type,
                    price,
                    limit_fee,
                    expiration,
                )
            except asyncio.TimeoutError:
                # We timed out while placing this order. We may have successfully submitted the order, or we may have had connection
                # issues that prevented the submission from taking place.

                # Note that if this order is live and we never recieved the exchange_order_id, we have no way of re-linking with this order
                # TODO: we can use the /v2/orders endpoint to get a list of orders that match the parameters of the lost orders and that will contain
                # the clientId that we have set. This can resync orders, but wouldn't be a garuntee of finding them in the list and would require a fair amout
                # of work in handling this re-syncing process
                # This would be somthing like
                # self._lost_orders.append(client_order_id) # add this here
                # ...
                # some polling loop:
                #   get_orders()
                #   see if any lost orders are in the returned orders and set the exchange id if so
                # ...

                # TODO: ensure this is the right exception from place_order with our wrapped library call...
                return

            # Verify the response from the exchange
            if "order" not in creation_response.keys():
                raise Exception(creation_response["errors"][0]["msg"])

            order = creation_response["order"]
            status = order["status"]
            if status not in ["PENDING", "OPEN"]:
                raise Exception(status)

            dydx_order_id = order["id"]

            in_flight_order = self._in_flight_orders.get(client_order_id)
            if in_flight_order is not None:
                self._set_exchange_id(in_flight_order, dydx_order_id)
                self._claim_fills(in_flight_order, dydx_order_id)

                # Begin tracking order
                self.logger().info(
                    f"Created {in_flight_order.description} order {client_order_id} for {amount} {trading_pair}."
                )
            else:
                self.logger().info(f"Created order {client_order_id} for {amount} {trading_pair}.")

        except Exception as e:
            self.logger().warning(
                f"Error submitting {order_side.name} {order_type.name} order to dydx for "
                f"{amount} {trading_pair} at {price}."
            )
            self.logger().info(e, exc_info=True)

            # Stop tracking this order
            self.stop_tracking_order(client_order_id)
            self.trigger_event(ORDER_FAILURE_EVENT, MarketOrderFailureEvent(now(), client_order_id, order_type))

    async def execute_buy(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        position_action: PositionAction,
        price: Optional[Decimal] = Decimal("NaN"),
    ):
        try:
            await self.execute_order(TradeType.BUY, order_id, trading_pair, amount, order_type, position_action, price)
            self.trigger_event(
                BUY_ORDER_CREATED_EVENT,
                BuyOrderCreatedEvent(now(), order_type, trading_pair, Decimal(amount), Decimal(price), order_id),
            )

            # Issue any other events (fills) for this order that arrived while waiting for the exchange id
            tracked_order = self.in_flight_orders.get(order_id)
            if tracked_order is not None:
                self._issue_order_events(tracked_order)
        except ValueError as e:
            # never tracked, so no need to stop tracking
            self.trigger_event(ORDER_FAILURE_EVENT, MarketOrderFailureEvent(now(), order_id, order_type))
            self.logger().warning(f"Failed to place {order_id} on dydx. {str(e)}")

    async def execute_sell(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        position_action: PositionAction,
        price: Optional[Decimal] = Decimal("NaN"),
    ):
        try:
            await self.execute_order(TradeType.SELL, order_id, trading_pair, amount, order_type, position_action, price)
            self.trigger_event(
                SELL_ORDER_CREATED_EVENT,
                SellOrderCreatedEvent(now(), order_type, trading_pair, Decimal(amount), Decimal(price), order_id),
            )

            # Issue any other events (fills) for this order that arrived while waiting for the exchange id
            tracked_order = self.in_flight_orders.get(order_id)
            if tracked_order is not None:
                self._issue_order_events(tracked_order)
        except ValueError as e:
            # never tracked, so no need to stop tracking
            self.trigger_event(ORDER_FAILURE_EVENT, MarketOrderFailureEvent(now(), order_id, order_type))
            self.logger().warning(f"Failed to place {order_id} on dydx. {str(e)}")

    # ----------------------------------------
    # Cancellation

    async def cancel_order(self, client_order_id: str):
        in_flight_order = self._in_flight_orders.get(client_order_id)
        cancellation_event = OrderCancelledEvent(now(), client_order_id)
        exchange_order_id = in_flight_order.exchange_order_id

        if in_flight_order is None:
            self.logger().warning("Cancelled an untracked order {client_order_id}")
            self.trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)
            return False

        try:
            if exchange_order_id is None:
                # Note, we have no way of canceling an order or querying for information about the order
                # without an exchange_order_id
                if in_flight_order.created_at < (int(self.time_now_s()) - UNRECOGNIZED_ORDER_DEBOUCE):
                    # We'll just have to assume that this order doesn't exist
                    self.stop_tracking_order(in_flight_order.client_order_id)
                    self.trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)
                    return False
                else:
                    raise Exception(f"order {client_order_id} has no exchange id")
            await self.dydx_client.cancel_order(exchange_order_id)
            return True

        except DydxApiError as e:
            if f"Order with specified id: {exchange_order_id} could not be found" in str(e):
                if in_flight_order.created_at < (int(self.time_now_s()) - UNRECOGNIZED_ORDER_DEBOUCE):
                    # Order didn't exist on exchange, mark this as canceled
                    self.stop_tracking_order(in_flight_order.client_order_id)
                    self.trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)
                    return False
                else:
                    raise Exception(
                        f"order {client_order_id} does not yet exist on the exchange and could not be cancelled."
                    )
            elif "is already canceled" in str(e):
                self.stop_tracking_order(in_flight_order.client_order_id)
                self.trigger_event(ORDER_CANCELLED_EVENT, cancellation_event)
                return False
            elif "is already filled" in str(e):
                response = await self.dydx_client.get_order(exchange_order_id)
                order_status = response["order"]
                in_flight_order.update(order_status)
                self._issue_order_events(in_flight_order)
                self.stop_tracking_order(in_flight_order.client_order_id)
                return False
            else:
                self.logger().warning(f"Unable to cancel order {exchange_order_id}: {str(e)}")
                return False
        except Exception as e:
            self.logger().warning(f"Failed to cancel order {client_order_id}")
            self.logger().info(e)
            return False

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        cancellation_queue = self._in_flight_orders.copy()
        if len(cancellation_queue) == 0:
            return []

        order_status = {o.client_order_id: o.is_done for o in cancellation_queue.values()}

        def set_cancellation_status(oce: OrderCancelledEvent):
            if oce.order_id in order_status:
                order_status[oce.order_id] = True
                return True
            return False

        cancel_verifier = LatchingEventResponder(set_cancellation_status, len(cancellation_queue))
        self.add_listener(ORDER_CANCELLED_EVENT, cancel_verifier)

        for order_id, in_flight in cancellation_queue.items():
            try:
                if order_status[order_id]:
                    cancel_verifier.cancel_one()
                elif not await self.cancel_order(order_id):
                    # this order did not exist on the exchange
                    cancel_verifier.cancel_one()
                    order_status[order_id] = True
            except Exception:
                cancel_verifier.cancel_one()
                order_status[order_id] = True

        await cancel_verifier.wait_for_completion(timeout_seconds)
        self.remove_listener(ORDER_CANCELLED_EVENT, cancel_verifier)

        return [CancellationResult(order_id=order_id, success=success) for order_id, success in order_status.items()]

    def get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_0,
        is_maker: Optional[bool] = None,
    ):
        warnings.warn(
            "The 'estimate_fee' method is deprecated, use 'build_trade_fee' and 'build_perpetual_trade_fee' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise DeprecationWarning(
            "The 'estimate_fee' method is deprecated, use 'build_trade_fee' and 'build_perpetual_trade_fee' instead."
        )

    # ==========================================================
    # Runtime
    # ----------------------------------------------------------

    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)

    def stop(self, clock: Clock):
        super().stop(clock)

    async def start_network(self):
        await self.stop_network()
        self._order_book_tracker.start()
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

            self._trading_pair_last_funding_payment_ts.update(
                {trading_pair: self.time_now_s() for trading_pair in self._trading_pairs}
            )

    def _stop_network(self):
        self._last_poll_timestamp = 0
        self._poll_notifier.clear()

        self._order_book_tracker.stop()
        if self._polling_update_task is not None:
            self._polling_update_task.cancel()
            self._polling_update_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self.dydx_client.get_server_time()
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    # ----------------------------------------
    # State Management

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {key: value.to_json() for key, value in self._in_flight_orders.items()}

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        for order_id, in_flight_repr in saved_states.items():
            in_flight_json: Dict[str, Any] = json.loads(in_flight_repr)
            order = DydxPerpetualInFlightOrder.from_json(in_flight_json)
            if not order.is_done:
                self._in_flight_orders[order_id] = order

    def start_tracking_order(
        self,
        order_side: TradeType,
        client_order_id: str,
        order_type: OrderType,
        created_at: int,
        hash: str,
        trading_pair: str,
        price: Decimal,
        amount: Decimal,
        leverage: int,
        position: str,
    ):
        in_flight_order = DydxPerpetualInFlightOrder.from_dydx_order(
            order_side, client_order_id, order_type, created_at, None, trading_pair, price, amount, leverage, position
        )
        self._in_flight_orders[in_flight_order.client_order_id] = in_flight_order
        self._orders_pending_ack.add(client_order_id)

        old_reserved = self._reserved_balances.get(in_flight_order.reserved_asset, Decimal(0))
        new_reserved = old_reserved + in_flight_order.reserved_balance
        self._reserved_balances[in_flight_order.reserved_asset] = new_reserved
        self._account_available_balances[in_flight_order.reserved_asset] = max(
            self._account_balances.get(in_flight_order.reserved_asset, Decimal(0)) - new_reserved, Decimal(0)
        )

    def stop_tracking_order(self, client_order_id: str):
        in_flight_order = self._in_flight_orders.get(client_order_id)
        if in_flight_order is not None:
            old_reserved = self._reserved_balances.get(in_flight_order.reserved_asset, Decimal(0))
            new_reserved = max(old_reserved - in_flight_order.reserved_balance, Decimal(0))
            self._reserved_balances[in_flight_order.reserved_asset] = new_reserved
            self._account_available_balances[in_flight_order.reserved_asset] = max(
                self._account_balances.get(in_flight_order.reserved_asset, Decimal(0)) - new_reserved, Decimal(0)
            )
            if (
                in_flight_order.exchange_order_id is not None
                and in_flight_order.exchange_order_id in self._in_flight_orders_by_exchange_id
            ):
                del self._in_flight_orders_by_exchange_id[in_flight_order.exchange_order_id]
            if client_order_id in self._in_flight_orders:
                del self._in_flight_orders[client_order_id]
            if client_order_id in self._orders_pending_ack:
                self._orders_pending_ack.remove(client_order_id)

    def get_order_by_exchange_id(self, exchange_order_id: str):
        if exchange_order_id in self._in_flight_orders_by_exchange_id:
            return self._in_flight_orders_by_exchange_id[exchange_order_id]

        for o in self._in_flight_orders.values():
            if o.exchange_order_id == exchange_order_id:
                return o

        return None

    # ----------------------------------------
    # updates to orders and balances

    def _issue_order_events(self, tracked_order: DydxPerpetualInFlightOrder):
        issuable_events: List[MarketEvent] = tracked_order.get_issuable_events()

        # Issue relevent events
        for (market_event, new_amount, new_price, new_fee) in issuable_events:
            if market_event == MarketEvent.OrderCancelled:
                self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}")
                self.stop_tracking_order(tracked_order.client_order_id)
                self.trigger_event(
                    ORDER_CANCELLED_EVENT, OrderCancelledEvent(self.current_timestamp, tracked_order.client_order_id)
                )
            elif market_event == MarketEvent.OrderFilled:
                self.trigger_event(
                    ORDER_FILLED_EVENT,
                    OrderFilledEvent(
                        self.current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        new_price,
                        new_amount,
                        AddedToCostTradeFee(flat_fees=[TokenAmount(tracked_order.fee_asset, new_fee)]),
                        tracked_order.client_order_id,
                        self._leverage[tracked_order.trading_pair],
                        tracked_order.position,
                    ),
                )
            elif market_event == MarketEvent.OrderExpired:
                self.logger().info(
                    f"The market order {tracked_order.client_order_id} has expired according to " f"order status API."
                )
                self.stop_tracking_order(tracked_order.client_order_id)
                self.trigger_event(
                    ORDER_EXPIRED_EVENT, OrderExpiredEvent(self.current_timestamp, tracked_order.client_order_id)
                )
            elif market_event == MarketEvent.OrderFailure:
                self.logger().info(
                    f"The market order {tracked_order.client_order_id} has failed according to " f"order status API."
                )
                self.stop_tracking_order(tracked_order.client_order_id)
                self.trigger_event(
                    ORDER_FAILURE_EVENT,
                    MarketOrderFailureEvent(
                        self.current_timestamp, tracked_order.client_order_id, tracked_order.order_type
                    ),
                )
            elif market_event == MarketEvent.BuyOrderCompleted:
                self.logger().info(
                    f"The market buy order {tracked_order.client_order_id} has completed " f"according to user stream."
                )
                self.stop_tracking_order(tracked_order.client_order_id)
                self.trigger_event(
                    BUY_ORDER_COMPLETED_EVENT,
                    BuyOrderCompletedEvent(
                        self.current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.base_asset,
                        tracked_order.quote_asset,
                        tracked_order.fee_asset,
                        tracked_order.executed_amount_base,
                        tracked_order.executed_amount_quote,
                        tracked_order.fee_paid,
                        tracked_order.order_type,
                    ),
                )
            elif market_event == MarketEvent.SellOrderCompleted:
                self.logger().info(
                    f"The market sell order {tracked_order.client_order_id} has completed " f"according to user stream."
                )
                self.stop_tracking_order(tracked_order.client_order_id)
                self.trigger_event(
                    SELL_ORDER_COMPLETED_EVENT,
                    SellOrderCompletedEvent(
                        self.current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.base_asset,
                        tracked_order.quote_asset,
                        tracked_order.fee_asset,
                        tracked_order.executed_amount_base,
                        tracked_order.executed_amount_quote,
                        tracked_order.fee_paid,
                        tracked_order.order_type,
                    ),
                )

    async def _update_funding_rates(self):
        try:
            response = await self.dydx_client.get_markets()
            markets_info = response["markets"]
            for trading_pair in self._trading_pairs:
                self._funding_info[trading_pair] = FundingInfo(
                    trading_pair,
                    Decimal(markets_info[trading_pair]["indexPrice"]),
                    Decimal(markets_info[trading_pair]["oraclePrice"]),
                    dateparse(markets_info[trading_pair]["nextFundingAt"]).timestamp(),
                    Decimal(markets_info[trading_pair]["nextFundingRate"]),
                )
        except DydxApiError as e:
            if e.status_code == 429:
                self.logger().network(
                    log_msg="Rate-limit error.",
                    app_warning_msg="Could not fetch funding rates due to API rate limits.",
                    exc_info=True,
                )
            else:
                self.logger().network(
                    log_msg="dYdX API error.",
                    exc_info=True,
                    app_warning_msg="Could not fetch funding rates. Check API key and network connection.",
                )
        except Exception:
            self.logger().network(
                log_msg="Unknown error.",
                exc_info=True,
                app_warning_msg="Could not fetch funding rates. Check API key and network connection.",
            )

    def get_funding_info(self, trading_pair):
        return self._funding_info[trading_pair]

    def set_hedge_mode(self, position_mode: PositionMode):
        # dydx only allows one-way futures
        pass

    async def _set_balances(self, updates, is_snapshot=False):
        try:
            async with self._lock:
                quote = "USD"
                self._account_balances[quote] = Decimal(updates["equity"])
                self._account_available_balances[quote] = Decimal(updates["freeCollateral"])
            for position in self._account_positions.values():
                position.update_from_balance(Decimal(updates["equity"]))
        except Exception as e:
            self.logger().error(f"Could not set balance {repr(e)}", exc_info=True)

    # ----------------------------------------
    # User stream updates

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from dydx. Check API key and network connection.",
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event: Dict[str, Any] = event_message
                data: Dict[str, Any] = event["contents"]
                if "account" in data:
                    await self._set_balances(data["account"], is_snapshot=False)
                    if "openPositions" in data["account"]:
                        open_positions = data["account"]["openPositions"]
                        for market, position in open_positions.items():
                            position_key = self.position_key(market)
                            if position_key not in self._account_positions and market in self._trading_pairs:
                                self._create_position_from_rest_pos_item(position)
                if "accounts" in data:
                    for account in data["accounts"]:
                        quote = "USD"
                        self._account_available_balances[quote] = Decimal(account["quoteBalance"])
                if "orders" in data:
                    for order in data["orders"]:
                        exchange_order_id: str = order["id"]

                        tracked_order: DydxPerpetualInFlightOrder = self.get_order_by_exchange_id(exchange_order_id)

                        if tracked_order is None:
                            self.logger().debug(f"Unrecognized order ID from user stream: {exchange_order_id}.")
                            self.logger().debug(f"Event: {event_message}")
                            continue

                        # update the tracked order
                        tracked_order.update(order)
                        self._issue_order_events(tracked_order)
                if "fills" in data:
                    fills = data["fills"]
                    for fill in fills:
                        exchange_order_id: str = fill["orderId"]
                        id = fill["id"]
                        amount = Decimal(fill["size"])
                        price = Decimal(fill["price"])
                        fee_paid = Decimal(fill["fee"])
                        tracked_order: DydxPerpetualInFlightOrder = self.get_order_by_exchange_id(exchange_order_id)
                        if tracked_order is not None:
                            tracked_order.register_fill(id, amount, price, fee_paid)
                            pos_key = self.position_key(tracked_order.trading_pair)
                            if pos_key in self._account_positions:
                                position = self._account_positions[pos_key]
                                position.update_from_fill(
                                    tracked_order, price, amount, self.get_available_balance("USD")
                                )
                                await self._update_account_positions()
                            else:
                                self._account_positions[pos_key] = DydxPerpetualPosition.from_dydx_fill(
                                    tracked_order, amount, price, self.get_available_balance("USD")
                                )
                            self._issue_order_events(tracked_order)
                        else:
                            if len(self._orders_pending_ack) > 0:
                                self._unclaimed_fills[exchange_order_id].add(
                                    DydxPerpetualFillReport(id, amount, price, fee_paid)
                                )
                if "positions" in data:
                    # this is hit when a position is closed
                    positions = data["positions"]
                    for position in positions:
                        if position["market"] not in self._trading_pairs:
                            continue
                        pos_key = self.position_key(position["market"])
                        if pos_key in self._account_positions:
                            self._account_positions[pos_key].update_position(
                                position_side=PositionSide[position["side"]],
                                unrealized_pnl=position.get("unrealizedPnl"),
                                entry_price=position.get("entryPrice"),
                                amount=position.get("size"),
                                status=position.get("status"),
                            )
                            if not self._account_positions[pos_key].is_open:
                                del self._account_positions[pos_key]
                if "fundingPayments" in data:
                    if event["type"] != "subscribed":  # Only subsequent funding payments
                        for funding_payment in data["fundingPayments"]:
                            if funding_payment["market"] not in self._trading_pairs:
                                continue
                            ts = dateparse(funding_payment["effectiveAt"]).timestamp()
                            funding_rate: Decimal = Decimal(funding_payment["rate"])
                            trading_pair: str = funding_payment["market"]
                            payment: Decimal = Decimal(funding_payment["payment"])
                            action: str = "paid" if payment < s_decimal_0 else "received"

                            self.logger().info(f"Funding payment of {payment} {action} on {trading_pair} market")
                            self.trigger_event(
                                MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG,
                                FundingPaymentCompletedEvent(
                                    timestamp=ts,
                                    market=self.name,
                                    funding_rate=funding_rate,
                                    trading_pair=trading_pair,
                                    amount=payment,
                                ),
                            )
                            self._trading_pair_last_funding_payment_ts[trading_pair] = ts
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    # ----------------------------------------
    # Polling Updates

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await self._update_balances()  # needs to complete before updating positions
                await safe_gather(
                    self._update_account_positions(),
                    self._update_trading_rules(),
                    self._update_order_status(),
                    self._update_funding_rates(),
                    self._update_funding_payments(),
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().warning("Failed to fetch updates on dydx. Check network connection.")
                self.logger().warning(e)

    async def _update_account_positions(self):
        account_info = await self.dydx_client.get_account()
        current_positions = account_info["account"]

        for market, position in current_positions["openPositions"].items():
            market = position["market"]
            pos_key = self.position_key(market)
            if pos_key in self._account_positions:
                tracked_position: DydxPerpetualPosition = self._account_positions[pos_key]
                tracked_position.update_position(
                    position_side=PositionSide[position["side"]],
                    unrealized_pnl=position.get("unrealizedPnl"),
                    entry_price=position.get("entryPrice"),
                    amount=position.get("size"),
                    status=position.get("status"),
                )
                tracked_position.update_from_balance(Decimal(current_positions["equity"]))
                if not tracked_position.is_open:
                    del self._account_positions[pos_key]
            elif market in self._trading_pairs:
                self._create_position_from_rest_pos_item(position)
        positions_to_delete = []
        for position_str in self._account_positions:
            if position_str not in current_positions["openPositions"]:
                positions_to_delete.append(position_str)
        for account_position in positions_to_delete:
            del self._account_positions[account_position]

    def _create_position_from_rest_pos_item(self, rest_pos_item: Dict[str, str]):
        market = rest_pos_item["market"]
        position_key = self.position_key(market)
        entry_price: Decimal = Decimal(rest_pos_item["entryPrice"])
        amount: Decimal = Decimal(rest_pos_item["size"])
        total_quote: Decimal = entry_price * amount
        leverage: Decimal = total_quote / self.get_balance("USD")
        self._account_positions[position_key] = DydxPerpetualPosition(
            trading_pair=market,
            position_side=PositionSide[rest_pos_item["side"]],
            unrealized_pnl=Decimal(rest_pos_item["unrealizedPnl"]),
            entry_price=entry_price,
            amount=amount,
            leverage=leverage,
        )

    async def _update_balances(self):
        current_balances = await self.dydx_client.get_my_balances()
        await self._set_balances(current_balances["account"], True)

    async def _update_trading_rules(self):
        markets_info = (await self.dydx_client.get_markets())["markets"]
        for market_name in markets_info:
            market = markets_info[market_name]
            try:
                collateral_token = market["quoteAsset"]  # all contracts settled in USDC
                self._trading_rules[market_name] = TradingRule(
                    trading_pair=market_name,
                    min_order_size=Decimal(market["minOrderSize"]),
                    min_price_increment=Decimal(market["tickSize"]),
                    min_base_amount_increment=Decimal(market["stepSize"]),
                    min_notional_size=Decimal(market["minOrderSize"]) * Decimal(market["tickSize"]),
                    supports_limit_orders=True,
                    supports_market_orders=True,
                    buy_order_collateral_token=collateral_token,
                    sell_order_collateral_token=collateral_token,
                )
                self._margin_fractions[market_name] = {
                    "initial": Decimal(market["initialMarginFraction"]),
                    "maintenance": Decimal(market["maintenanceMarginFraction"]),
                }
            except Exception as e:
                self.logger().warning("Error updating trading rules")
                self.logger().warning(str(e))

    async def _update_order_status(self):
        tracked_orders = self._in_flight_orders.copy()
        for client_order_id, tracked_order in tracked_orders.items():
            dydx_order_id = tracked_order.exchange_order_id
            if dydx_order_id is None:
                # This order is still pending acknowledgement from the exchange
                if tracked_order.created_at < (int(self.time_now_s()) - UNRECOGNIZED_ORDER_DEBOUCE):
                    # this order should have a dydx_order_id at this point. If it doesn't, we should cancel it
                    # as we won't be able to poll for updates
                    try:
                        self.cancel_order(client_order_id)
                    except Exception:
                        pass
                continue

            dydx_order_request = None
            try:
                dydx_order_request = await self.dydx_client.get_order(dydx_order_id)
                data = dydx_order_request["order"]
            except Exception:
                self.logger().warning(
                    f"Failed to fetch tracked dydx order "
                    f"{client_order_id}({tracked_order.exchange_order_id}) from api "
                    f"(code: {dydx_order_request['resultInfo']['code'] if dydx_order_request is not None else 'None'})"
                )

                # check if this error is because the api cliams to be unaware of this order. If so, and this order
                # is reasonably old, mark the orde as cancelled
                if "could not be found" in str(dydx_order_request["msg"]):
                    if tracked_order.created_at < (int(self.time_now_s()) - UNRECOGNIZED_ORDER_DEBOUCE):
                        try:
                            self.cancel_order(client_order_id)
                        except Exception:
                            pass
                continue

            try:
                tracked_order.update(data)
                if not tracked_order.fills_covered():
                    # We're missing fill reports for this order, so poll for them as well
                    await self._update_fills(tracked_order)
                self._issue_order_events(tracked_order)
            except Exception as e:
                self.logger().warning(f"Failed to update dydx order {tracked_order.exchange_order_id}")
                self.logger().warning(e)
                self.logger().exception("")

    async def _update_fills(self, tracked_order: DydxPerpetualInFlightOrder):
        try:
            data = await self.dydx_client.get_fills(tracked_order.exchange_order_id)
            for fill in data["fills"]:
                if fill["orderId"] == tracked_order.exchange_order_id:
                    id = fill["id"]
                    amount = Decimal(fill["size"])
                    price = Decimal(fill["price"])
                    fee_paid = Decimal(fill["fee"])
                    tracked_order.register_fill(id, amount, price, fee_paid)
                    pos_key = self.position_key(tracked_order.trading_pair)
                    if pos_key in self._account_positions:
                        position = self._account_positions[pos_key]
                        position.update_from_fill(tracked_order, price, amount, self.get_available_balance("USD"))
                    else:
                        self._account_positions[pos_key] = DydxPerpetualPosition.from_dydx_fill(
                            tracked_order, amount, price, self.get_available_balance("USD")
                        )
            if len(data["fills"]) > 0:
                await self._update_account_positions()

        except DydxApiError as e:
            self.logger().warning(
                f"Unable to poll for fills for order {tracked_order.client_order_id}"
                f"(tracked_order.exchange_order_id): {e.status} {e.msg}"
            )
        except KeyError:
            self.logger().warning(
                f"Unable to poll for fills for order {tracked_order.client_order_id}"
                f"(tracked_order.exchange_order_id): unexpected response data {data}"
            )

    async def _update_funding_payments(self):
        for trading_pair in self._trading_pairs:
            try:

                response = await self.dydx_client.get_funding_payments(market=trading_pair, before_ts=self.time_now_s())
                funding_payments = response["fundingPayments"]
                for funding_payment in funding_payments:
                    ts = dateparse(funding_payment["effectiveAt"]).timestamp()
                    if ts <= self._trading_pair_last_funding_payment_ts[trading_pair]:
                        break  # Any subsequent funding payments would have a ts < last_funding_payment_ts
                    funding_rate: Decimal = Decimal(funding_payment["rate"])
                    trading_pair: str = funding_payment["market"]
                    payment: Decimal = Decimal(funding_payment["payment"])
                    action: str = "paid" if payment < s_decimal_0 else "received"

                    self.logger().info(f"Funding payment of {payment} {action} on {trading_pair} market")
                    self.trigger_event(
                        MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG,
                        FundingPaymentCompletedEvent(
                            timestamp=ts,
                            market=self.name,
                            funding_rate=funding_rate,
                            trading_pair=trading_pair,
                            amount=payment,
                        ),
                    )
                    self._trading_pair_last_funding_payment_ts[trading_pair] = ts
            except DydxApiError as e:
                self.logger().warning(f"Unable to poll for funding payments {trading_pair}. ({e})")

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        safe_ensure_future(self._set_leverage(trading_pair, leverage))

    async def _set_leverage(self, trading_pair: str, leverage: int = 1):
        markets = await self.dydx_client.get_markets()
        markets_info = markets["markets"]

        self._margin_fractions[trading_pair] = {
            "initial": Decimal(markets_info[trading_pair]["initialMarginFraction"]),
            "maintenance": Decimal(markets_info[trading_pair]["maintenanceMarginFraction"]),
        }

        max_leverage = int(Decimal("1") / self._margin_fractions[trading_pair]["initial"])
        if leverage > max_leverage:
            self._leverage[trading_pair] = max_leverage
            self.logger().warning(f"Leverage has been reduced to {max_leverage}")
        else:
            self._leverage[trading_pair] = leverage
        # the margins of dydx are a property of the margins. they determine the
        # size of orders allowable.

    async def _get_position_mode(self):
        self._position_mode = PositionMode.ONEWAY

        return self._position_mode

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def set_position_mode(self, position_mode: PositionMode):
        self._position_mode = PositionMode.ONEWAY

    # ==========================================================
    # Miscellaneous
    # ----------------------------------------------------------

    def get_order_price_quantum(self, trading_pair: str, price: Decimal):
        return self._trading_rules[trading_pair].min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal):
        return self._trading_rules[trading_pair].min_base_amount_increment

    def quantize_order_price(self, trading_pair: str, price: Decimal):
        return price.quantize(self.get_order_price_quantum(trading_pair, price))

    def quantize_order_amount(self, trading_pair: str, amount: Decimal, price: Decimal = Decimal("0")):
        quantized_amount = amount.quantize(self.get_order_size_quantum(trading_pair, amount))

        rules = self._trading_rules[trading_pair]

        if quantized_amount < rules.min_order_size:
            return s_decimal_0

        if price > 0 and price * quantized_amount < rules.min_notional_size:
            return s_decimal_0

        return quantized_amount

    def time_now_s(self) -> float:
        return time.time()

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = self.time_now_s()
        poll_interval = (
            self.SHORT_POLL_INTERVAL
            if now - self._user_stream_tracker.last_recv_time > 60.0
            else self.LONG_POLL_INTERVAL
        )
        last_tick = int(self._last_poll_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_poll_timestamp = timestamp

    def buy(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        tracking_nonce = get_tracking_nonce()
        client_order_id: str = str(f"buy-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(
            self.execute_buy(client_order_id, trading_pair, amount, order_type, kwargs["position_action"], price)
        )
        return client_order_id

    def sell(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        tracking_nonce = get_tracking_nonce()
        client_order_id: str = str(f"sell-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(
            self.execute_sell(client_order_id, trading_pair, amount, order_type, kwargs["position_action"], price)
        )
        return client_order_id

    def cancel(self, trading_pair: str, client_order_id: str):
        return safe_ensure_future(self.cancel_order(client_order_id))

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token
