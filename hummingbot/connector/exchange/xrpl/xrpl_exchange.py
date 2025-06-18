import asyncio
import math
import time
import uuid
from asyncio import Lock
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

from bidict import bidict

# XRPL Imports
from xrpl.asyncio.clients import AsyncWebsocketClient, Client, XRPLRequestFailureException
from xrpl.asyncio.transaction import sign, submit_and_wait as async_submit_and_wait
from xrpl.core.binarycodec import encode
from xrpl.models import (
    XRP,
    AccountInfo,
    AccountLines,
    AccountObjects,
    AccountTx,
    AMMDeposit,
    AMMInfo,
    AMMWithdraw,
    Currency,
    IssuedCurrency,
    Memo,
    OfferCancel,
    Request,
    SubmitOnly,
    Transaction,
)
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.response import Response, ResponseStatus
from xrpl.utils import (
    drops_to_xrp,
    get_balance_changes,
    get_order_book_changes,
    hex_to_str,
    ripple_time_to_posix,
    xrp_to_drops,
)
from xrpl.utils.txn_parser.utils.types import Balance
from xrpl.wallet import Wallet

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS, xrpl_web_utils
from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import XRPLAPIOrderBookDataSource
from hummingbot.connector.exchange.xrpl.xrpl_api_user_stream_data_source import XRPLAPIUserStreamDataSource
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_order_placement_strategy import OrderPlacementStrategyFactory
from hummingbot.connector.exchange.xrpl.xrpl_utils import (  # AddLiquidityRequest,; GetPoolInfoRequest,; QuoteLiquidityRequest,; RemoveLiquidityRequest,
    AddLiquidityResponse,
    PoolInfo,
    QuoteLiquidityResponse,
    RemoveLiquidityResponse,
    XRPLMarket,
    XRPLNodePool,
    _wait_for_final_transaction_outcome,
    autofill,
    convert_string_to_hex,
    get_token_from_changes,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule  # type: ignore
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class XRPLOrderTracker(ClientOrderTracker):
    TRADE_FILLS_WAIT_TIMEOUT = 20


class XrplExchange(ExchangePyBase):

    web_utils = xrpl_web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        xrpl_secret_key: str,
        wss_node_urls: list[str],
        max_request_per_minute: int,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        custom_markets: Optional[Dict[str, XRPLMarket]] = None,
    ):
        self._xrpl_secret_key = xrpl_secret_key

        self._node_pool = XRPLNodePool(
            node_urls=wss_node_urls,
            requests_per_10s=0.3 if isinstance(max_request_per_minute, str) else max_request_per_minute / 6,
            burst_tokens=25,  # Higher initial pool for startup and emergency operations
            max_burst_tokens=30,  # Allow accumulation for batch operations like mass cancellations
            proactive_switch_interval=100,
            cooldown=100,
        )
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._xrpl_auth: XRPLAuth = self.authenticator
        self._trading_pair_symbol_map: Optional[Mapping[str, str]] = None
        self._trading_pair_fee_rules: Dict[str, Dict[str, Any]] = {}
        self._xrpl_query_client_lock = asyncio.Lock()
        self._xrpl_place_order_client_lock = asyncio.Lock()
        self._xrpl_fetch_trades_client_lock = asyncio.Lock()
        self._nonce_creator = NonceCreator.for_milliseconds()
        self._custom_markets = custom_markets or {}
        self._last_clients_refresh_time = 0

        # Order state locking to prevent concurrent status updates
        self._order_status_locks: Dict[str, asyncio.Lock] = {}
        self._order_status_lock_manager_lock = asyncio.Lock()

        # Timing safeguards to prevent rapid consecutive updates
        self._order_last_update_timestamps: Dict[str, float] = {}
        self._min_update_interval_seconds = 0.5  # Minimum time between status updates for same order

        super().__init__(client_config_map)

    def _create_order_tracker(self) -> ClientOrderTracker:
        return XRPLOrderTracker(connector=self)

    @staticmethod
    def xrpl_order_type(order_type: OrderType) -> int:
        return CONSTANTS.XRPL_ORDER_TYPE[order_type]

    @staticmethod
    def to_hb_order_type(order_type: str) -> OrderType:
        return OrderType[order_type]

    @property
    def authenticator(self) -> XRPLAuth:
        return XRPLAuth(xrpl_secret_key=self._xrpl_secret_key)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return "Not Supported"

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return ""

    @property
    def trading_pairs_request_path(self):
        return ""

    @property
    def check_network_request_path(self):
        return ""

    @property
    def trading_pairs(self):
        return self._trading_pairs or []

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    async def _get_async_client(self):
        url = await self._node_pool.get_node()
        return AsyncWebsocketClient(url)

    @property
    def user_stream_client(self) -> AsyncWebsocketClient:
        # For user stream, always get a fresh client from the pool
        # This must be used in async context, so we return a coroutine
        raise NotImplementedError("Use await self._get_async_client() instead of user_stream_client property.")

    @property
    def order_book_data_client(self) -> AsyncWebsocketClient:
        # For order book, always get a fresh client from the pool
        # This must be used in async context, so we return a coroutine
        raise NotImplementedError("Use await self._get_async_client() instead of order_book_data_client property.")

    @property
    def auth(self) -> XRPLAuth:
        return self._xrpl_auth

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET, OrderType.AMM_SWAP]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # We do not use time synchronizer in XRPL connector
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: this will be important to implement in case that we request an order that is in memory but the update of it wasn't correct
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: this will be important to implement in case that we request an order that is in memory but the update of it wasn't correct
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:  # type: ignore
        pass

    def _create_order_book_data_source(self) -> XRPLAPIOrderBookDataSource:
        return XRPLAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs or [], connector=self, api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return XRPLAPIUserStreamDataSource(auth=self._xrpl_auth, connector=self)

    async def _get_order_status_lock(self, client_order_id: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific order to prevent concurrent status updates.

        :param client_order_id: The client order ID to get a lock for
        :return: An asyncio.Lock for the specified order
        """
        async with self._order_status_lock_manager_lock:
            if client_order_id not in self._order_status_locks:
                self._order_status_locks[client_order_id] = asyncio.Lock()
            return self._order_status_locks[client_order_id]

    async def _cleanup_order_status_lock(self, client_order_id: str):
        """
        Clean up the lock for a specific order after it's no longer needed.

        :param client_order_id: The client order ID to clean up the lock for
        """
        async with self._order_status_lock_manager_lock:
            if client_order_id in self._order_status_locks:
                del self._order_status_locks[client_order_id]
            if client_order_id in self._order_last_update_timestamps:
                del self._order_last_update_timestamps[client_order_id]

    def _can_update_order_status(self, client_order_id: str, force_update: bool = False) -> bool:
        """
        Check if enough time has passed since the last status update for this order.

        :param client_order_id: The client order ID to check
        :param force_update: If True, bypass the timing check
        :return: True if the order status can be updated, False otherwise
        """
        if force_update:
            return True

        current_time = time.time()
        last_update_time = self._order_last_update_timestamps.get(client_order_id, 0)

        return (current_time - last_update_time) >= self._min_update_interval_seconds

    def _record_order_status_update(self, client_order_id: str):
        """
        Record the timestamp of an order status update.

        :param client_order_id: The client order ID that was updated
        """
        self._order_last_update_timestamps[client_order_id] = time.time()

    async def _process_final_order_state(self, tracked_order: InFlightOrder, new_state: OrderState,
                                         update_timestamp: float, trade_update: Optional[TradeUpdate] = None):
        """
        Process order reaching a final state (FILLED, CANCELED, FAILED).
        This ensures proper order completion flow and cleanup.

        :param tracked_order: The order that reached a final state
        :param new_state: The final state (FILLED, CANCELED, or FAILED)
        :param update_timestamp: Timestamp of the state change
        :param trade_update: Optional trade update to process
        """
        # For FILLED orders, process trade updates FIRST so the completely_filled_event gets set
        # This is critical for the base class wait_until_completely_filled() mechanism
        if trade_update and new_state == OrderState.FILLED:
            self._order_tracker.process_trade_update(trade_update)

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
        )

        # Process the order update (this will call _trigger_order_completion -> stop_tracking_order)
        # For FILLED orders, this will wait for completely_filled_event before proceeding
        self._order_tracker.process_order_update(order_update)

        # Process trade updates for non-FILLED states or if no trade update was provided for FILLED
        if trade_update and new_state != OrderState.FILLED:
            self._order_tracker.process_trade_update(trade_update)

        # XRPL-specific cleanup
        await self._cleanup_order_status_lock(tracked_order.client_order_id)

        self.logger().info(f"Order {tracked_order.client_order_id} reached final state: {new_state.name}")

    async def _process_market_order_transaction(self, tracked_order: InFlightOrder, transaction: Dict, meta: Dict, event_message: Dict):
        """
        Process market order transaction from user stream events.

        :param tracked_order: The tracked order to process
        :param transaction: Transaction data from the event
        :param meta: Transaction metadata
        :param event_message: Complete event message
        """
        # Use order lock to prevent race conditions with cancellation
        order_lock = await self._get_order_status_lock(tracked_order.client_order_id)
        async with order_lock:
            # Double-check state after acquiring lock to prevent race conditions
            if tracked_order.current_state not in [OrderState.OPEN]:
                self.logger().debug(
                    f"Order {tracked_order.client_order_id} state changed to {tracked_order.current_state} while acquiring lock, skipping update"
                )
                return

            tx_status = meta.get("TransactionResult")
            if tx_status != "tesSUCCESS":
                self.logger().error(
                    f"Order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}) failed: {tx_status}, data: {event_message}"
                )
                new_order_state = OrderState.FAILED
            else:
                new_order_state = OrderState.FILLED

            # Enhanced logging for debugging race conditions
            self.logger().debug(
                f"[USER_STREAM_MARKET] Order {tracked_order.client_order_id} state transition: "
                f"{tracked_order.current_state.name} -> {new_order_state.name} "
                f"(tx_status: {tx_status})"
            )

            update_timestamp = time.time()
            trade_update = None

            if new_order_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED]:
                trade_update = await self.process_trade_fills(event_message, tracked_order)
                if trade_update is None:
                    self.logger().error(
                        f"Failed to process trade fills for order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}), order state: {new_order_state}, data: {event_message}"
                    )

            # Record the update timestamp
            self._record_order_status_update(tracked_order.client_order_id)

            # Process final state using centralized method (handles stop_tracking_order)
            if new_order_state in [OrderState.FILLED, OrderState.FAILED]:
                await self._process_final_order_state(tracked_order, new_order_state, update_timestamp, trade_update)
            else:
                # For non-final states, use regular order update
                order_update = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=update_timestamp,
                    new_state=new_order_state,
                )
                self._order_tracker.process_order_update(order_update=order_update)
                if trade_update:
                    self._order_tracker.process_trade_update(trade_update)

    async def _process_order_book_changes(self, order_book_changes: List[Any], transaction: Dict, event_message: Dict):
        """
        Process order book changes from user stream events.

        :param order_book_changes: List of order book changes
        :param transaction: Transaction data from the event
        :param event_message: Complete event message
        """
        # Handle state updates for orders
        for order_book_change in order_book_changes:
            if order_book_change["maker_account"] != self._xrpl_auth.get_account():
                self.logger().debug(
                    f"Order book change not for this account? {order_book_change['maker_account']}"
                )
                continue

            for offer_change in order_book_change["offer_changes"]:
                tracked_order = self.get_order_by_sequence(offer_change["sequence"])
                if tracked_order is None:
                    self.logger().debug(f"Tracked order not found for sequence '{offer_change['sequence']}'")
                    continue

                if tracked_order.current_state in [OrderState.PENDING_CREATE]:
                    continue

                # Check timing safeguards before acquiring lock (except for final states)
                is_final_state_change = offer_change["status"] in ["filled", "cancelled"]
                if not is_final_state_change and not self._can_update_order_status(
                    tracked_order.client_order_id
                ):
                    self.logger().debug(
                        f"Skipping order status update for {tracked_order.client_order_id} due to timing safeguard"
                    )
                    continue

                # Use order lock to prevent race conditions
                order_lock = await self._get_order_status_lock(tracked_order.client_order_id)
                async with order_lock:
                    # Check if order is in a final state to avoid duplicate updates
                    if tracked_order.current_state in [
                        OrderState.FILLED,
                        OrderState.CANCELED,
                        OrderState.FAILED,
                    ]:
                        self.logger().debug(
                            f"Order {tracked_order.client_order_id} already in final state {tracked_order.current_state}, skipping update"
                        )
                        continue

                    status = offer_change["status"]
                    if status == "filled":
                        new_order_state = OrderState.FILLED

                    elif status == "partially-filled":
                        new_order_state = OrderState.PARTIALLY_FILLED
                    elif status == "cancelled":
                        new_order_state = OrderState.CANCELED
                    else:
                        # Check if the transaction did cross any offers in the order book
                        taker_gets = offer_change.get("taker_gets")
                        taker_pays = offer_change.get("taker_pays")

                        tx_taker_gets = transaction.get("TakerGets")
                        tx_taker_pays = transaction.get("TakerPays")

                        if isinstance(tx_taker_gets, str):
                            tx_taker_gets = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_gets))}

                        if isinstance(tx_taker_pays, str):
                            tx_taker_pays = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_pays))}

                        # Use a small tolerance for comparing decimal values
                        tolerance = Decimal("0.00001")  # 0.001% tolerance

                        taker_gets_value = Decimal(taker_gets.get("value", "0") if taker_gets else "0")
                        tx_taker_gets_value = Decimal(tx_taker_gets.get("value", "0") if tx_taker_gets else "0")
                        taker_pays_value = Decimal(taker_pays.get("value", "0") if taker_pays else "0")
                        tx_taker_pays_value = Decimal(tx_taker_pays.get("value", "0") if tx_taker_pays else "0")

                        # Check if values differ by more than the tolerance
                        gets_diff = abs(
                            (taker_gets_value - tx_taker_gets_value) / tx_taker_gets_value
                            if tx_taker_gets_value
                            else 0
                        )
                        pays_diff = abs(
                            (taker_pays_value - tx_taker_pays_value) / tx_taker_pays_value
                            if tx_taker_pays_value
                            else 0
                        )

                        if gets_diff > tolerance or pays_diff > tolerance:
                            new_order_state = OrderState.PARTIALLY_FILLED
                        else:
                            new_order_state = OrderState.OPEN

                    self.logger().debug(
                        f"Order update for order '{tracked_order.client_order_id}' with sequence '{offer_change['sequence']}': '{new_order_state}'"
                    )
                    # Enhanced logging for debugging race conditions
                    self.logger().debug(
                        f"[USER_STREAM] Order {tracked_order.client_order_id} state transition: "
                        f"{tracked_order.current_state.name} -> {new_order_state.name} "
                        f"(sequence: {offer_change['sequence']}, status: {status})"
                    )

                    update_timestamp = time.time()
                    trade_update = None

                    # Record the update timestamp
                    self._record_order_status_update(tracked_order.client_order_id)

                    if new_order_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED]:
                        trade_update = await self.process_trade_fills(event_message, tracked_order)
                        if trade_update is None:
                            self.logger().error(
                                f"Failed to process trade fills for order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}), order state: {new_order_state}, data: {event_message}"
                            )

                    # Process final state using centralized method (handles stop_tracking_order)
                    if new_order_state in [OrderState.FILLED, OrderState.CANCELED, OrderState.FAILED]:
                        await self._process_final_order_state(tracked_order, new_order_state, update_timestamp, trade_update)
                    else:
                        # For non-final states, use regular order update
                        order_update = OrderUpdate(
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=tracked_order.exchange_order_id,
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=update_timestamp,
                            new_state=new_order_state,
                        )
                        self._order_tracker.process_order_update(order_update=order_update)
                        if trade_update:
                            self._order_tracker.process_trade_update(trade_update)

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> AddedToCostTradeFee:
        # TODO: Implement get fee, use the below implementation
        # is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        # trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        # if trading_pair in self._trading_fees:
        #     fees_data = self._trading_fees[trading_pair]
        #     fee_value = Decimal(fees_data["makerFeeRate"]) if is_maker else Decimal(fees_data["takerFeeRate"])
        #     fee = AddedToCostTradeFee(percent=fee_value)

        # TODO: Remove this fee implementation
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(  # type: ignore
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        **kwargs,
    ) -> tuple[str, float, Response | None]:
        """
        Places an order using the appropriate strategy based on order type.
        Returns a tuple of (exchange_order_id, transaction_time, response).
        """
        o_id = "UNKNOWN"
        transact_time = 0.0
        resp = None
        submit_response = None
        try:
            retry = 0
            verified = False
            submit_data = {}

            order = InFlightOrder(
                client_order_id=order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                creation_timestamp=self._time(),
            )

            strategy = OrderPlacementStrategyFactory.create_strategy(self, order)

            # Create the transaction
            request = await strategy.create_order_transaction()

            while retry < CONSTANTS.PLACE_ORDER_MAX_RETRY:
                async with await self._get_async_client() as client:
                    filled_tx = await self.tx_autofill(request, client)
                    signed_tx = self.tx_sign(filled_tx, self._xrpl_auth.get_wallet())
                    o_id = f"{signed_tx.sequence}-{signed_tx.last_ledger_sequence}"
                    submit_response = await self.tx_submit(signed_tx, client, fail_hard=True)
                    transact_time = time.time()
                    prelim_result = submit_response.result["engine_result"]

                    submit_data = {"transaction": signed_tx, "prelim_result": prelim_result}

                    self.logger().info(
                        f"Submitted order {order_id} ({o_id}): type={order_type}, "
                        f"pair={trading_pair}, amount={amount}, price={price}, "
                        f"prelim_result={prelim_result}, tx_hash={submit_response.result.get('tx_json', {}).get('hash', 'unknown')}"
                    )

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order_id,
                    exchange_order_id=str(o_id),
                    trading_pair=trading_pair,
                    update_timestamp=transact_time,
                    new_state=OrderState.PENDING_CREATE,
                )

                self._order_tracker.process_order_update(order_update)

                verified, resp = await self._verify_transaction_result(submit_data)

                if verified:
                    retry = CONSTANTS.PLACE_ORDER_MAX_RETRY
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        exchange_order_id=str(o_id),
                        trading_pair=trading_pair,
                        update_timestamp=transact_time,
                        new_state=OrderState.OPEN,
                    )

                    self._order_tracker.process_order_update(order_update)
                else:
                    retry += 1
                    self.logger().info(
                        f"Order {order_id} ({o_id}) placing failed with result {prelim_result}. "
                        f"Retrying in {CONSTANTS.PLACE_ORDER_RETRY_INTERVAL} seconds... "
                        f"(Attempt {retry}/{CONSTANTS.PLACE_ORDER_MAX_RETRY})"
                    )
                    await self._sleep(CONSTANTS.PLACE_ORDER_RETRY_INTERVAL)

            if resp is None:
                self.logger().error(
                    f"Failed to place order {order_id} ({o_id}), "
                    f"submit_data: {submit_data}, "
                    f"last_response: {submit_response.result if submit_response else 'None'}"
                )
                raise Exception(f"Failed to place order {order_id} ({o_id})")

            if not verified:
                self.logger().error(
                    f"Failed to verify transaction result for order {order_id} ({o_id}), "
                    f"submit_data: {submit_data}, "
                    f"last_response: {resp.result if resp else 'None'}"
                )
                raise Exception(f"Failed to verify transaction result for order {order_id} ({o_id})")

        except Exception as e:
            new_state = OrderState.FAILED
            order_update = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=time.time(),
                new_state=new_state,
                client_order_id=order_id,
            )
            self._order_tracker.process_order_update(order_update)
            self.logger().error(
                f"Order {o_id} ({order_id}) creation failed: {str(e)}, "
                f"type={order_type}, pair={trading_pair}, amount={amount}, price={price}"
            )
            raise Exception(f"Order {o_id} ({order_id}) creation failed: {e}")

        return o_id, transact_time, resp

    async def _place_order_and_process_update(self, order: InFlightOrder, **kwargs) -> str:
        self._node_pool.add_burst_tokens(5)
        async with self._xrpl_place_order_client_lock:
            exchange_order_id, update_timestamp, order_creation_resp = await self._place_order(
                order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                amount=order.amount,
                trade_type=order.trade_type,
                order_type=order.order_type,
                price=order.price,
                **kwargs,
            )

        order_update = await self._request_order_status(
            order,
            creation_tx_resp=order_creation_resp.to_dict().get("result") if order_creation_resp is not None else None,
        )

        self._order_tracker.process_order_update(order_update)

        if order_update.new_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED]:
            trade_update = await self.process_trade_fills(
                order_creation_resp.to_dict() if order_creation_resp is not None else None, order
            )
            if trade_update is not None:
                self._order_tracker.process_trade_update(trade_update)

                if order_update.new_state == OrderState.FILLED:
                    order.completely_filled_event.set()
            else:
                self.logger().error(
                    f"Failed to process trade fills for order {order.client_order_id} ({order.exchange_order_id}), order state: {order_update.new_state}, data: {order_creation_resp.to_dict() if order_creation_resp is not None else 'None'}"
                )

        return exchange_order_id

    async def _verify_transaction_result(
        self, submit_data: Optional[dict[str, Any]], try_count: int = 0
    ) -> tuple[bool, Optional[Response]]:
        if submit_data is None:
            self.logger().error("Failed to verify transaction result, submit_data is None")
            return False, None

        transaction: Optional[Transaction] = submit_data.get("transaction", None)
        prelim_result: Optional[str] = submit_data.get("prelim_result", None)

        if prelim_result is None:
            self.logger().error("Failed to verify transaction result, prelim_result is None")
            return False, None

        if transaction is None:
            self.logger().error("Failed to verify transaction result, transaction is None")
            return False, None

        if prelim_result not in ["tesSUCCESS", "tefPAST_SEQ", "terQUEUED"]:
            self.logger().error(
                f"Failed to verify transaction result, prelim_result: {prelim_result}, "
                f"tx_hash: {transaction.get_hash()}, sequence: {transaction.sequence}"
            )
            return False, None

        try:
            # await self._make_network_check_request()
            resp = await self.wait_for_final_transaction_outcome(transaction, prelim_result)
            self.logger().debug(
                f"Transaction verified successfully - hash: {transaction.get_hash()}, "
                f"sequence: {transaction.sequence}, result: {resp.result.get('meta', {}).get('TransactionResult', 'unknown')}"
            )
            return True, resp
        except (TimeoutError, asyncio.exceptions.TimeoutError):
            self.logger().debug(
                f"Verify transaction timeout error - hash: {transaction.get_hash()}, "
                f"sequence: {transaction.sequence}, attempt: {try_count + 1}/{CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY}"
            )
            if try_count < CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY:
                await self._sleep(CONSTANTS.VERIFY_TRANSACTION_RETRY_INTERVAL)
                return await self._verify_transaction_result(submit_data, try_count + 1)
            else:
                self.logger().error(
                    f"Max retries reached. Verify transaction failed due to timeout - "
                    f"hash: {transaction.get_hash()}, sequence: {transaction.sequence}"
                )
                return False, None

        except Exception as e:
            # If there is code 429, retry the request
            if "429" in str(e):
                self.logger().debug(
                    f"Verify transaction rate limited - hash: {transaction.get_hash()}, "
                    f"sequence: {transaction.sequence}, attempt: {try_count + 1}/{CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY}"
                )
                if try_count < CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY:
                    await self._sleep(CONSTANTS.VERIFY_TRANSACTION_RETRY_INTERVAL)
                    return await self._verify_transaction_result(submit_data, try_count + 1)
                else:
                    self.logger().error(
                        f"Max retries reached. Verify transaction failed with code 429 - "
                        f"hash: {transaction.get_hash()}, sequence: {transaction.sequence}"
                    )
                    return False, None

            self.logger().error(
                f"Submitted transaction failed: {e}, hash: {transaction.get_hash()}, sequence: {transaction.sequence}"
            )

            return False, None

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = tracked_order.exchange_order_id
        cancel_result = False
        cancel_data = {}
        submit_response = None

        if exchange_order_id is None:
            self.logger().error(f"Unable to cancel order {order_id}, it does not yet have exchange order id")
            return False, {}

        try:
            self._node_pool.add_burst_tokens(5)
            async with await self._get_async_client() as client:
                sequence, _ = exchange_order_id.split("-")
                memo = Memo(
                    memo_data=convert_string_to_hex(order_id, padding=False),
                )
                request = OfferCancel(account=self._xrpl_auth.get_account(), offer_sequence=int(sequence), memos=[memo])

                filled_tx = await self.tx_autofill(request, client)
                signed_tx = self.tx_sign(filled_tx, self._xrpl_auth.get_wallet())

                submit_response = await self.tx_submit(signed_tx, client, fail_hard=True)
                prelim_result = submit_response.result["engine_result"]

                self.logger().info(
                    f"Submitted cancel for order {order_id} ({exchange_order_id}): "
                    f"prelim_result={prelim_result}, tx_hash={submit_response.result.get('tx_json', {}).get('hash', 'unknown')}"
                )

            if prelim_result is None:
                raise Exception(f"prelim_result is None for {order_id} ({exchange_order_id}), data: {submit_response}")

            if prelim_result[0:3] == "tes":
                cancel_result = True
            elif prelim_result == "temBAD_SEQUENCE":
                cancel_result = True
            else:
                cancel_result = False
                self.logger().error(f"Order cancellation failed: {prelim_result}, data: {submit_response}")

            cancel_result = True
            cancel_data = {"transaction": signed_tx, "prelim_result": prelim_result}

        except Exception as e:
            self.logger().error(
                f"Order cancellation failed: {e}, order_id: {exchange_order_id}, submit_response: {submit_response}"
            )
            cancel_result = False
            cancel_data = {}

        return cancel_result, cancel_data

    async def _execute_order_cancel_and_process_update(self, order: InFlightOrder) -> bool:
        # Early exit if order is not being tracked and is already in a final state
        is_actively_tracked = order.client_order_id in self._order_tracker.active_orders
        if not is_actively_tracked and order.current_state in [OrderState.FILLED, OrderState.CANCELED, OrderState.FAILED]:
            self.logger().debug(f"Order {order.client_order_id} is not being tracked and already in final state {order.current_state}, cancellation not needed")
            return order.current_state == OrderState.CANCELED

        # Use order-specific lock to prevent concurrent status updates
        order_lock = await self._get_order_status_lock(order.client_order_id)

        async with self._xrpl_place_order_client_lock:
            async with order_lock:
                if not self.ready:
                    await self._sleep(3)

                # Double-check if order state changed after acquiring lock
                if not is_actively_tracked and order.current_state in [
                    OrderState.FILLED,
                    OrderState.CANCELED,
                    OrderState.FAILED,
                ]:
                    self.logger().debug(
                        f"Order {order.client_order_id} is no longer being tracked after acquiring lock and in final state {order.current_state}, cancellation not needed"
                    )
                    return order.current_state == OrderState.CANCELED

                # Check current order state before attempting cancellation
                current_state = order.current_state
                if current_state in [OrderState.FILLED, OrderState.CANCELED, OrderState.FAILED]:
                    self.logger().debug(
                        f"Order {order.client_order_id} is already in final state {current_state}, skipping cancellation"
                    )
                    return current_state == OrderState.CANCELED

                retry = 0
                submitted = False
                verified = False
                resp = None
                submit_data = {}

                update_timestamp = self.current_timestamp
                if update_timestamp is None or math.isnan(update_timestamp):
                    update_timestamp = self._time()

                # Mark order as pending cancellation
                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order.client_order_id,
                    trading_pair=order.trading_pair,
                    update_timestamp=update_timestamp,
                    new_state=OrderState.PENDING_CANCEL,
                )
                self._order_tracker.process_order_update(order_update)

                # Get fresh order status before attempting cancellation
                try:
                    fresh_order_update = await self._request_order_status(order)

                    # If order is filled/partially filled, process the fills and don't cancel
                    if fresh_order_update.new_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED]:
                        self.logger().debug(
                            f"Order {order.client_order_id} is {fresh_order_update.new_state.name}, processing fills instead of canceling"
                        )

                        trade_updates = await self._all_trade_updates_for_order(order)
                        first_trade_update = trade_updates[0] if len(trade_updates) > 0 else None

                        if fresh_order_update.new_state == OrderState.FILLED:
                            # Use centralized final state processing for filled orders
                            await self._process_final_order_state(
                                order, OrderState.FILLED, fresh_order_update.update_timestamp, first_trade_update
                            )
                            # Process any remaining trade updates
                            for trade_update in trade_updates[1:]:
                                self._order_tracker.process_trade_update(trade_update)
                        else:
                            # For partially filled, use regular order update
                            self._order_tracker.process_order_update(fresh_order_update)
                            for trade_update in trade_updates:
                                self._order_tracker.process_trade_update(trade_update)

                        return False  # Cancellation not needed/successful

                    # If order is already canceled, return success
                    elif fresh_order_update.new_state == OrderState.CANCELED:
                        self.logger().debug(f"Order {order.client_order_id} already canceled")
                        # Use centralized final state processing for already cancelled orders
                        await self._process_final_order_state(
                            order, OrderState.CANCELED, fresh_order_update.update_timestamp
                        )
                        return True

                except Exception as status_check_error:
                    self.logger().warning(
                        f"Failed to check order status before cancellation for {order.client_order_id}: {status_check_error}"
                    )

                # Proceed with cancellation attempt
                while retry < CONSTANTS.CANCEL_MAX_RETRY:
                    submitted, submit_data = await self._place_cancel(order.client_order_id, order)
                    verified, resp = await self._verify_transaction_result(submit_data)

                    if submitted and verified:
                        retry = CONSTANTS.CANCEL_MAX_RETRY
                    else:
                        retry += 1
                        self.logger().info(
                            f"Order cancellation failed. Retrying in {CONSTANTS.CANCEL_RETRY_INTERVAL} seconds..."
                        )
                        await self._sleep(CONSTANTS.CANCEL_RETRY_INTERVAL)

                if submitted and verified:
                    if resp is None:
                        self.logger().error(
                            f"Failed to cancel order {order.client_order_id} ({order.exchange_order_id}), data: {order}, submit_data: {submit_data}"
                        )
                        return False

                    meta = resp.result.get("meta", {})
                    # Handle case where exchange_order_id might be None
                    if order.exchange_order_id is None:
                        self.logger().error(
                            f"Cannot process cancel for order {order.client_order_id} with None exchange_order_id"
                        )
                        return False

                    sequence, ledger_index = order.exchange_order_id.split("-")
                    changes_array = get_order_book_changes(meta)
                    changes_array = [
                        x for x in changes_array if x.get("maker_account") == self._xrpl_auth.get_account()
                    ]
                    status = "UNKNOWN"

                    for offer_change in changes_array:
                        changes = offer_change.get("offer_changes", [])

                        for found_tx in changes:
                            if int(found_tx.get("sequence")) == int(sequence):
                                status = found_tx.get("status")
                                break

                    if len(changes_array) == 0:
                        status = "cancelled"

                    if status == "cancelled":
                        # Enhanced logging for debugging race conditions
                        self.logger().debug(
                            f"[CANCELLATION] Order {order.client_order_id} successfully canceled "
                            f"(previous state: {order.current_state.name})"
                        )

                        # Use centralized final state processing for successful cancellation
                        await self._process_final_order_state(order, OrderState.CANCELED, self._time())
                        return True
                    else:
                        # Check if order was actually filled during cancellation attempt
                        try:
                            final_status_check = await self._request_order_status(order)
                            if final_status_check.new_state == OrderState.FILLED:
                                # Enhanced logging for debugging race conditions
                                self.logger().debug(
                                    f"[CANCELLATION_RACE_CONDITION] Order {order.client_order_id} was filled during cancellation attempt "
                                    f"(previous state: {order.current_state.name} -> {final_status_check.new_state.name})"
                                )
                                trade_updates = await self._all_trade_updates_for_order(order)
                                first_trade_update = trade_updates[0] if len(trade_updates) > 0 else None
                                # Use centralized final state processing for filled during cancellation
                                await self._process_final_order_state(
                                    order, OrderState.FILLED, final_status_check.update_timestamp, first_trade_update
                                )
                                # Process any remaining trade updates
                                for trade_update in trade_updates[1:]:
                                    self._order_tracker.process_trade_update(trade_update)
                                return False  # Cancellation not successful because order filled
                        except Exception as final_check_error:
                            self.logger().warning(
                                f"Failed final status check for order {order.client_order_id}: {final_check_error}"
                            )

                        await self._order_tracker.process_order_not_found(order.client_order_id)
                        await self._cleanup_order_status_lock(order.client_order_id)
                        return False

                await self._order_tracker.process_order_not_found(order.client_order_id)
                await self._cleanup_order_status_lock(order.client_order_id)
                return False

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        return await super().cancel_all(CONSTANTS.CANCEL_ALL_TIMEOUT)

    def _format_trading_rules(self, trading_rules_info: Dict[str, Any]) -> List[TradingRule]:  # type: ignore
        trading_rules = []
        for trading_pair, trading_pair_info in trading_rules_info.items():
            base_tick_size = trading_pair_info["base_tick_size"]
            quote_tick_size = trading_pair_info["quote_tick_size"]
            minimum_order_size = trading_pair_info["minimum_order_size"]

            trading_rule = TradingRule(
                trading_pair=trading_pair,
                min_order_size=Decimal(minimum_order_size),
                min_price_increment=Decimal(f"1e-{quote_tick_size}"),
                min_quote_amount_increment=Decimal(f"1e-{quote_tick_size}"),
                min_base_amount_increment=Decimal(f"1e-{base_tick_size}"),
                min_notional_size=Decimal(f"1e-{quote_tick_size}"),
            )

            trading_rules.append(trading_rule)

        return trading_rules

    def _format_trading_pair_fee_rules(self, trading_rules_info: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        trading_pair_fee_rules = []

        for trading_pair, trading_pair_info in trading_rules_info.items():
            base_token = trading_pair.split("-")[0]
            quote_token = trading_pair.split("-")[1]
            amm_pool_info: PoolInfo | None = trading_pair_info.get("amm_pool_info", None)

            if amm_pool_info is not None:
                amm_pool_fee = amm_pool_info.fee_pct / Decimal("100")
            else:
                amm_pool_fee = Decimal("0")

            trading_pair_fee_rules.append(
                {
                    "trading_pair": trading_pair,
                    "base_token": base_token,
                    "quote_token": quote_token,
                    "base_transfer_rate": trading_pair_info["base_transfer_rate"],
                    "quote_transfer_rate": trading_pair_info["quote_transfer_rate"],
                    "amm_pool_fee": amm_pool_fee,
                }
            )

        return trading_pair_fee_rules

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        # TODO: Move fee update logic to this method
        pass

    def get_order_by_sequence(self, sequence) -> Optional[InFlightOrder]:
        for client_order_id, order in self._order_tracker.all_fillable_orders.items():
            if order.exchange_order_id is None:
                return None

            if int(order.exchange_order_id.split("-")[0]) == int(sequence):
                return order

        return None

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                transaction = event_message.get("transaction", None)

                if transaction is None:
                    transaction = event_message.get("tx", None)

                if transaction is None:
                    transaction = event_message.get("tx_json", None)

                meta = event_message.get("meta")

                if transaction is None or meta is None:
                    self.logger().debug(f"Received event message without transaction or meta: {event_message}")
                    continue

                self.logger().debug(
                    f"Handling TransactionType: {transaction.get('TransactionType')}, Hash: {event_message.get('hash')} OfferSequence: {transaction.get('OfferSequence')}, Sequence: {transaction.get('Sequence')}"
                )

                balance_changes = get_balance_changes(meta)
                order_book_changes = get_order_book_changes(meta)

                # Check if this is market order, if it is, check if it has been filled or failed
                tx_sequence = transaction.get("Sequence")
                tracked_order = self.get_order_by_sequence(tx_sequence)

                if (
                    tracked_order is not None
                    and tracked_order.order_type in [OrderType.MARKET, OrderType.AMM_SWAP]
                    and tracked_order.current_state in [OrderState.OPEN]
                ):
                    await self._process_market_order_transaction(tracked_order, transaction, meta, event_message)

                # Handle order book changes for limit orders and other order types
                await self._process_order_book_changes(order_book_changes, transaction, event_message)

                # Handle balance changes
                for balance_change in balance_changes:
                    if balance_change["account"] == self._xrpl_auth.get_account():
                        for balance in balance_change["balances"]:
                            currency = balance["currency"]
                            value = Decimal(balance["value"])

                            # Convert hex currency code to string if needed
                            if len(currency) > 3:
                                try:
                                    currency = hex_to_str(currency).strip("\x00").upper()
                                except UnicodeDecodeError:
                                    # Do nothing since this is a non-hex string
                                    pass

                            # For XRP, update both total and available balances
                            if currency == "XRP":
                                if self._account_balances is None:
                                    self._account_balances = {}
                                if self._account_available_balances is None:
                                    self._account_available_balances = {}

                                # Update total balance
                                current_total = self._account_balances.get(currency, Decimal("0"))
                                self._account_balances[currency] = current_total + value

                                # Update available balance (assuming the change affects available balance equally)
                                current_available = self._account_available_balances.get(currency, Decimal("0"))
                                self._account_available_balances[currency] = current_available + value
                            else:
                                # For other tokens, we need to get the token symbol
                                token_symbol = self.get_token_symbol_from_all_markets(
                                    currency, balance_change["account"]
                                )
                                if token_symbol is not None:
                                    if self._account_balances is None:
                                        self._account_balances = {}
                                    if self._account_available_balances is None:
                                        self._account_available_balances = {}

                                    # Update total balance
                                    current_total = self._account_balances.get(token_symbol, Decimal("0"))
                                    self._account_balances[token_symbol] = current_total + value

                                    # Update available balance (assuming the change affects available balance equally)
                                    current_available = self._account_available_balances.get(token_symbol, Decimal("0"))
                                    self._account_available_balances[token_symbol] = current_available + value

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        if order.exchange_order_id is None:
            return []

        _, ledger_index = order.exchange_order_id.split("-")

        transactions = await self._fetch_account_transactions(int(ledger_index), is_forward=True)

        trade_fills = []

        for transaction in transactions:
            tx = transaction.get("tx") or transaction.get("transaction") or transaction.get("tx_json")

            if tx is None:
                self.logger().debug(f"Transaction not found for order {order.client_order_id}, data: {transaction}")
                continue

            tx_type = tx.get("TransactionType", None)

            if tx_type is None or tx_type not in ["OfferCreate", "Payment"]:
                self.logger().debug(
                    f"Skipping transaction with type {tx_type} for order {order.client_order_id} ({order.exchange_order_id})"
                )
                continue

            trade_update = await self.process_trade_fills(transaction, order)
            if trade_update is not None:
                trade_fills.append(trade_update)

        return trade_fills

    async def process_trade_fills(self, data: Optional[Dict[str, Any]], order: InFlightOrder) -> Optional[TradeUpdate]:
        base_currency, quote_currency = self.get_currencies_from_trading_pair(order.trading_pair)

        # raise if data is None
        if data is None:
            self.logger().error(f"Data is None for order {order.client_order_id}")
            raise ValueError(f"Data is None for order {order.client_order_id}")

        # raise if exchange_order_id is None
        if order.exchange_order_id is None:
            self.logger().error(f"Exchange order ID is None for order {order.client_order_id}")
            raise ValueError(f"Exchange order ID is None for order {order.client_order_id}")

        sequence, ledger_index = order.exchange_order_id.split("-")
        fee_rules = self._trading_pair_fee_rules.get(order.trading_pair)

        if fee_rules is None:
            await self._update_trading_rules()
            fee_rules = self._trading_pair_fee_rules.get(order.trading_pair)

            if fee_rules is None:
                self.logger().error(
                    f"Fee rules not found for order {order.client_order_id} ({order.exchange_order_id}), "
                    f"trading_pair: {order.trading_pair}"
                )
                raise ValueError(f"Fee rules not found for order {order.client_order_id}")

        if "result" in data:
            data_result = data.get("result", {})
            meta = data_result.get("meta", {})

            tx = data_result.get("tx_json") or data_result.get("transaction")
            if tx is not None:
                tx["hash"] = data_result.get("hash")
            else:
                tx = data_result
        else:
            meta = data.get("meta", {})
            tx = data.get("tx") or data.get("transaction") or data.get("tx_json") or {}

            if "hash" in data:
                tx["hash"] = data.get("hash")

        if not isinstance(tx, dict):
            self.logger().error(
                f"Transaction not found for order {order.client_order_id} ({order.exchange_order_id}), "
                f"data: {data}, tx: {tx}"
            )
            return None

        if tx.get("TransactionType") not in ["OfferCreate", "Payment"]:
            self.logger().debug(
                f"Skipping non-trade transaction type {tx.get('TransactionType')} for order "
                f"{order.client_order_id} ({order.exchange_order_id})"
            )
            return None

        if tx.get("hash") is None:
            self.logger().error(
                f"Transaction hash is None for order {order.client_order_id} ({order.exchange_order_id}), "
                f"data: {data}, tx: {tx}"
            )
            return None

        offer_changes = get_order_book_changes(meta)
        balance_changes = get_balance_changes(meta)

        # Filter out change that is not from this account
        offer_changes = [x for x in offer_changes if x.get("maker_account") == self._xrpl_auth.get_account()]
        balance_changes = [x for x in balance_changes if x.get("account") == self._xrpl_auth.get_account()]

        tx_sequence = tx.get("Sequence")

        if tx_sequence is None:
            self.logger().error(
                f"Transaction sequence is None for order {order.client_order_id} ({order.exchange_order_id}), "
                f"tx_hash: {tx.get('hash')}"
            )
            raise ValueError(f"Transaction sequence is None for order {order.client_order_id}")

        if int(tx_sequence) == int(sequence):
            # check status of the transaction
            tx_status = meta.get("TransactionResult")
            if tx_status != "tesSUCCESS":
                self.logger().error(
                    f"Order {order.client_order_id} ({order.exchange_order_id}) failed: {tx_status}, "
                    f"tx_hash: {tx.get('hash')}, data: {data}"
                )
                return None

            # If this order is market order or there is no offer changes, this order has been filled
            if order.order_type in [OrderType.MARKET, OrderType.AMM_SWAP] or len(offer_changes) == 0:
                # check if there is any balance changes
                if len(balance_changes) == 0:
                    self.logger().error(
                        f"Order {order.client_order_id} ({order.exchange_order_id}) has no balance changes, "
                        f"tx_hash: {tx.get('hash')}, data: {data}"
                    )
                    return None

                for balance_change in balance_changes:
                    changes = balance_change.get("balances", [])
                    base_change = get_token_from_changes(changes, token=base_currency.currency) or {}
                    quote_change = get_token_from_changes(changes, token=quote_currency.currency) or {}

                    if order.trade_type is TradeType.BUY:
                        fee_token = fee_rules.get("quote_token")
                        fee_rate = fee_rules.get("quote_transfer_rate")
                    else:
                        fee_token = fee_rules.get("base_token")
                        fee_rate = fee_rules.get("base_transfer_rate")

                    if order.order_type == OrderType.AMM_SWAP:
                        fee_rate = fee_rules.get("amm_pool_fee")

                    if fee_token is None or fee_rate is None:
                        raise ValueError(f"Fee token or fee rate is None for order {order.client_order_id}")

                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=fee_token.upper(),
                        percent=Decimal(fee_rate),
                    )

                    tx_hash = tx.get("hash", None)
                    base_value = base_change.get("value", None)
                    quote_value = quote_change.get("value", None)
                    tx_date = tx.get("date", None)

                    if tx_hash is None or tx_date is None:
                        raise ValueError(
                            f"Missing required transaction data for order {order.client_order_id}, changes: {changes}, tx: {tx}, base_change: {base_change}, quote_change: {quote_change}"
                        )

                    if base_value is None or quote_value is None:
                        self.logger().debug(
                            f"Skipping trade update for order {order.client_order_id} ({order.exchange_order_id}) due to missing base or quote value, base_change: {base_change}, quote_change: {quote_change}"
                        )
                        return None

                    # Calculate fill price with validation
                    base_decimal = abs(Decimal(base_value))
                    if base_decimal == Decimal("0"):
                        raise ValueError(f"Base amount cannot be zero for order {order.client_order_id}")

                    trade_update = TradeUpdate(
                        trade_id=tx_hash,
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        trading_pair=order.trading_pair,
                        fee=fee,
                        fill_base_amount=abs(Decimal(base_value)),
                        fill_quote_amount=abs(Decimal(quote_value)),
                        fill_price=abs(Decimal(quote_value)) / base_decimal,
                        fill_timestamp=ripple_time_to_posix(tx_date),
                    )

                    return trade_update
            else:
                # This is a limit order, check if the limit order did cross any offers in the order book
                for offer_change in offer_changes:
                    changes = offer_change.get("offer_changes", [])

                    for change in changes:
                        status = change.get("status")
                        if status not in ["filled", "partially-filled"]:
                            continue

                        if int(change.get("sequence")) == int(sequence):
                            self.logger().debug(f"Processing offer change with sequence {sequence}")
                            taker_gets = change.get("taker_gets")
                            taker_pays = change.get("taker_pays")

                            # Validate taker_gets and taker_pays
                            if taker_gets is None or taker_pays is None:
                                self.logger().debug(
                                    f"Missing taker_gets or taker_pays for order {order.client_order_id}"
                                )
                                continue

                            tx_taker_gets = tx.get("TakerGets")
                            tx_taker_pays = tx.get("TakerPays")

                            # Validate tx_taker_gets and tx_taker_pays
                            if tx_taker_gets is None or tx_taker_pays is None:
                                self.logger().debug(
                                    f"Missing tx_taker_gets or tx_taker_pays for order {order.client_order_id}"
                                )
                                continue

                            self.logger().debug(
                                f"Original tx_taker_gets: {tx_taker_gets}, tx_taker_pays: {tx_taker_pays}"
                            )
                            if isinstance(tx_taker_gets, str):
                                tx_taker_gets = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_gets))}

                            if isinstance(tx_taker_pays, str):
                                tx_taker_pays = {"currency": "XRP", "value": str(drops_to_xrp(tx_taker_pays))}
                            self.logger().debug(
                                f"Processed tx_taker_gets: {tx_taker_gets}, tx_taker_pays: {tx_taker_pays}"
                            )

                            # Check if values exist before comparing
                            taker_gets_value = taker_gets.get("value", "0")
                            taker_pays_value = taker_pays.get("value", "0")
                            tx_taker_gets_value = tx_taker_gets.get("value", "0")
                            tx_taker_pays_value = tx_taker_pays.get("value", "0")

                            self.logger().debug(
                                f"Comparing values - taker_gets: {taker_gets_value}, tx_taker_gets: {tx_taker_gets_value}, "
                                f"taker_pays: {taker_pays_value}, tx_taker_pays: {tx_taker_pays_value}"
                            )

                            if (
                                taker_gets_value is not None
                                and tx_taker_gets_value is not None
                                and taker_pays_value is not None
                                and tx_taker_pays_value is not None
                            ):
                                # Convert values to Decimal for precise comparison
                                taker_gets_decimal = Decimal(taker_gets_value)
                                tx_taker_gets_decimal = Decimal(tx_taker_gets_value)
                                taker_pays_decimal = Decimal(taker_pays_value)
                                tx_taker_pays_decimal = Decimal(tx_taker_pays_value)

                                # Calculate relative differences
                                gets_diff = abs(
                                    (taker_gets_decimal - tx_taker_gets_decimal) / tx_taker_gets_decimal
                                    if tx_taker_gets_decimal != 0
                                    else 0
                                )
                                pays_diff = abs(
                                    (taker_pays_decimal - tx_taker_pays_decimal) / tx_taker_pays_decimal
                                    if tx_taker_pays_decimal != 0
                                    else 0
                                )

                                # Use a small tolerance (0.0001 or 0.01%) to account for rounding errors
                                tolerance = Decimal("0.0001")

                                if gets_diff > tolerance or pays_diff > tolerance:
                                    diff_taker_gets_value = abs(taker_gets_decimal - tx_taker_gets_decimal)
                                    diff_taker_pays_value = abs(taker_pays_decimal - tx_taker_pays_decimal)
                                    self.logger().debug(
                                        f"Calculated diffs - gets: {diff_taker_gets_value}, pays: {diff_taker_pays_value}"
                                    )

                                    diff_taker_gets = Balance(
                                        currency=taker_gets.get("currency"),
                                        value=str(diff_taker_gets_value),
                                    )

                                    diff_taker_pays = Balance(
                                        currency=taker_pays.get("currency"),
                                        value=str(diff_taker_pays_value),
                                    )

                                    self.logger().debug(
                                        f"Looking for base currency: {base_currency.currency}, quote currency: {quote_currency.currency}"
                                    )
                                    base_change = get_token_from_changes(
                                        token_changes=[diff_taker_gets, diff_taker_pays], token=base_currency.currency
                                    )
                                    quote_change = get_token_from_changes(
                                        token_changes=[diff_taker_gets, diff_taker_pays], token=quote_currency.currency
                                    )
                                    self.logger().debug(
                                        f"Found base_change: {base_change}, quote_change: {quote_change}"
                                    )

                                    # Validate base_change and quote_change
                                    if base_change is None or quote_change is None:
                                        self.logger().debug(
                                            f"Missing base_change or quote_change for order {order.client_order_id}"
                                        )
                                        continue

                                    if order.trade_type is TradeType.BUY:
                                        fee_token = fee_rules.get("quote_token")
                                        fee_rate = fee_rules.get("quote_transfer_rate")
                                    else:
                                        fee_token = fee_rules.get("base_token")
                                        fee_rate = fee_rules.get("base_transfer_rate")

                                    if order.order_type == OrderType.AMM_SWAP:
                                        fee_rate = fee_rules.get("amm_pool_fee")

                                    self.logger().debug(f"Fee details - token: {fee_token}, rate: {fee_rate}")

                                    # Validate fee_token and fee_rate
                                    if fee_token is None or fee_rate is None:
                                        self.logger().debug(
                                            f"Missing fee_token or fee_rate for order {order.client_order_id}"
                                        )
                                        continue

                                    fee = TradeFeeBase.new_spot_fee(
                                        fee_schema=self.trade_fee_schema(),
                                        trade_type=order.trade_type,
                                        percent_token=fee_token.upper(),
                                        percent=Decimal(fee_rate),
                                    )

                                    # Validate transaction hash and date
                                    tx_hash = tx.get("hash")
                                    tx_date = tx.get("date")
                                    if tx_hash is None or tx_date is None:
                                        self.logger().debug(
                                            f"Missing tx_hash or tx_date for order {order.client_order_id}"
                                        )
                                        continue
                                    self.logger().debug(f"Transaction details - hash: {tx_hash}, date: {tx_date}")

                                    # Validate base and quote values
                                    base_value = base_change.get("value")
                                    quote_value = quote_change.get("value")
                                    if base_value is None or quote_value is None:
                                        self.logger().debug(
                                            f"Missing base_value or quote_value for order {order.client_order_id}"
                                        )
                                        continue
                                    self.logger().debug(f"Trade values - base: {base_value}, quote: {quote_value}")

                                    # Ensure base amount is not zero to avoid division by zero
                                    base_decimal = abs(Decimal(base_value))
                                    if base_decimal == Decimal("0"):
                                        self.logger().debug(f"Base amount is zero for order {order.client_order_id}")
                                        continue

                                    fill_price = abs(Decimal(quote_value)) / base_decimal
                                    self.logger().debug(f"Calculated fill price: {fill_price}")

                                    trade_update = TradeUpdate(
                                        trade_id=tx_hash,
                                        client_order_id=order.client_order_id,
                                        exchange_order_id=order.exchange_order_id,
                                        trading_pair=order.trading_pair,
                                        fee=fee,
                                        fill_base_amount=abs(Decimal(base_value)),
                                        fill_quote_amount=abs(Decimal(quote_value)),
                                        fill_price=fill_price,
                                        fill_timestamp=ripple_time_to_posix(tx_date),
                                    )
                                    self.logger().debug(
                                        f"Created trade update for order {order.client_order_id}: {trade_update}"
                                    )

                                    return trade_update
        else:
            # Find if offer changes are related to this order
            for offer_change in offer_changes:
                changes = offer_change.get("offer_changes", [])

                for change in changes:
                    if int(change.get("sequence")) == int(sequence):
                        taker_gets = change.get("taker_gets")
                        taker_pays = change.get("taker_pays")

                        base_change = get_token_from_changes(
                            token_changes=[taker_gets, taker_pays], token=base_currency.currency
                        )
                        quote_change = get_token_from_changes(
                            token_changes=[taker_gets, taker_pays], token=quote_currency.currency
                        )

                        # Validate base and quote change data
                        if base_change is None or not isinstance(base_change, dict):
                            self.logger().debug(f"Invalid base change data for order {order.client_order_id}")
                            continue

                        if quote_change is None or not isinstance(quote_change, dict):
                            self.logger().debug(f"Invalid quote change data for order {order.client_order_id}")
                            continue

                        base_value = base_change.get("value")
                        quote_value = quote_change.get("value")

                        if base_value is None or quote_value is None:
                            self.logger().debug(f"Missing base_value or quote_value for order {order.client_order_id}")
                            continue

                        # Validate fee data
                        if order.trade_type is TradeType.BUY:
                            fee_token = fee_rules.get("quote_token")
                            fee_rate = fee_rules.get("quote_transfer_rate")
                        else:
                            fee_token = fee_rules.get("base_token")
                            fee_rate = fee_rules.get("base_transfer_rate")

                        if order.order_type == OrderType.AMM_SWAP:
                            fee_rate = fee_rules.get("amm_pool_fee")

                        if fee_token is None or fee_rate is None:
                            self.logger().debug(f"Fee token or fee rate is None for order {order.client_order_id}")
                            continue

                        # Validate transaction hash and date
                        tx_hash = tx.get("hash")
                        tx_date = tx.get("date")

                        if tx_hash is None:
                            self.logger().debug(f"Transaction hash is missing for order {order.client_order_id}")
                            continue

                        if tx_date is None:
                            self.logger().debug(f"Transaction date is missing for order {order.client_order_id}")
                            continue

                        # Ensure base amount is not zero to avoid division by zero
                        base_decimal = abs(Decimal(base_value))
                        if base_decimal == Decimal("0"):
                            self.logger().debug(f"Base amount is zero for order {order.client_order_id}")
                            continue

                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=order.trade_type,
                            percent_token=fee_token.upper(),
                            percent=Decimal(str(fee_rate)),
                        )

                        fill_price = abs(Decimal(quote_value)) / base_decimal

                        trade_update = TradeUpdate(
                            trade_id=str(tx_hash),
                            client_order_id=order.client_order_id,
                            exchange_order_id=order.exchange_order_id,
                            trading_pair=order.trading_pair,
                            fee=fee,
                            fill_base_amount=abs(Decimal(base_value)),
                            fill_quote_amount=abs(Decimal(quote_value)),
                            fill_price=fill_price,
                            fill_timestamp=ripple_time_to_posix(int(tx_date)),
                        )

                        return trade_update

        return None

    async def _request_order_status(
        self, tracked_order: InFlightOrder, creation_tx_resp: Optional[Dict] = None
    ) -> OrderUpdate:
        # await self._make_network_check_request()
        new_order_state = tracked_order.current_state
        latest_status = "UNKNOWN"

        if tracked_order.exchange_order_id is None:
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=new_order_state,
            )

            return order_update

        sequence, ledger_index = tracked_order.exchange_order_id.split("-")
        found_creation_tx = None
        found_creation_meta = None
        found_txs = []
        history_transactions = await self._fetch_account_transactions(int(ledger_index))

        # Find the creation_transaction
        if creation_tx_resp is None:
            transactions = history_transactions
        else:
            transactions = [creation_tx_resp]

        for transaction in transactions:
            if "result" in transaction:
                data_result = transaction.get("result", {})
                meta = data_result.get("meta", {})
                tx = data_result
            else:
                meta = transaction.get("meta", {})
                tx = (
                    transaction.get("tx") or transaction.get("transaction") or transaction.get("tx_json") or transaction
                )

            if tx is not None and tx.get("Sequence", 0) == int(sequence):
                found_creation_tx = tx
                found_creation_meta = meta

            found_txs.append(
                {
                    "meta": meta,
                    "tx": tx,
                    "sequence": tx.get("Sequence", 0),
                    "ledger_index": tx.get("ledger_index", 0),
                }
            )

        if found_creation_meta is None or found_creation_tx is None:
            current_state = tracked_order.current_state
            if current_state is OrderState.PENDING_CREATE or current_state is OrderState.PENDING_CANCEL:
                if time.time() - tracked_order.last_update_timestamp > CONSTANTS.PENDING_ORDER_STATUS_CHECK_TIMEOUT:
                    new_order_state = OrderState.FAILED
                    self.logger().info(f"History transactions: {history_transactions}")
                    self.logger().info(f"Creation tx resp: {creation_tx_resp}")
                    self.logger().error(
                        f"Order status not found for order {tracked_order.client_order_id} ({sequence}), tx history: {transactions}"
                    )
                else:
                    new_order_state = current_state
            else:
                new_order_state = current_state

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=new_order_state,
            )

            return order_update

        # Process order by found_meta and found_tx
        if tracked_order.order_type in [OrderType.MARKET, OrderType.AMM_SWAP]:
            tx_status = found_creation_meta.get("TransactionResult")
            update_timestamp = time.time()
            if tx_status != "tesSUCCESS":
                new_order_state = OrderState.FAILED
                self.logger().error(
                    f"Order {tracked_order.client_order_id} ({tracked_order.exchange_order_id}) failed: {tx_status}, meta: {found_creation_meta}, tx: {found_creation_tx}"
                )
            else:
                new_order_state = OrderState.FILLED

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=update_timestamp,
                new_state=new_order_state,
            )

            return order_update
        else:
            # TODO: we should iterate through the history transactions to find the latest order status
            found = False

            for tx in found_txs:
                meta = tx.get("meta", {})

                changes_array = get_order_book_changes(meta)
                # Filter out change that is not from this account
                changes_array = [x for x in changes_array if x.get("maker_account") == self._xrpl_auth.get_account()]

                for offer_change in changes_array:
                    changes = offer_change.get("offer_changes", [])

                    for found_tx in changes:
                        if int(found_tx.get("sequence")) == int(sequence):
                            latest_status = found_tx.get("status")
                            found = True
                            break

            if found is False:
                # TODO: Only make this check if this is a at order creation
                # No offer created, this look like the order has been consumed without creating any offer object
                # Check if there is any balance changes
                balance_changes = get_balance_changes(found_creation_meta)

                # Filter by account
                balance_changes = [x for x in balance_changes if x.get("account") == self._xrpl_auth.get_account()]

                # If there is balance change for the account, this order has been filled
                if len(balance_changes) > 0:
                    new_order_state = OrderState.FILLED
                else:
                    new_order_state = OrderState.FAILED
            elif latest_status == "filled":
                new_order_state = OrderState.FILLED
            elif latest_status == "partially-filled":
                new_order_state = OrderState.PARTIALLY_FILLED
            elif latest_status == "cancelled":
                new_order_state = OrderState.CANCELED
            elif latest_status == "created":
                new_order_state = OrderState.OPEN

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=new_order_state,
            )

            return order_update

    async def _update_orders_with_error_handler(self, orders: List[InFlightOrder], error_handler: Callable):
        for order in orders:
            # Use order lock to prevent race conditions with real-time updates
            order_lock = await self._get_order_status_lock(order.client_order_id)

            try:
                async with order_lock:
                    # Skip if order is already in final state to prevent unnecessary updates
                    if order.current_state in [OrderState.FILLED, OrderState.CANCELED, OrderState.FAILED]:
                        if order.current_state == OrderState.FILLED:
                            order.completely_filled_event.set()
                            # Clean up lock for completed order
                            await self._cleanup_order_status_lock(order.client_order_id)
                        elif order.current_state == OrderState.CANCELED:
                            # Clean up lock for canceled order
                            await self._cleanup_order_status_lock(order.client_order_id)
                        elif order.current_state == OrderState.FAILED:
                            # Clean up lock for failed order
                            await self._cleanup_order_status_lock(order.client_order_id)
                        continue

                    # Check timing safeguards for periodic updates (be more lenient than real-time updates)
                    if not self._can_update_order_status(order.client_order_id, force_update=True):
                        continue

                    order_update = await self._request_order_status(tracked_order=order)

                    # Only process update if the new state is different or represents progress
                    if order_update.new_state != order.current_state or order_update.new_state in [
                        OrderState.FILLED,
                        OrderState.PARTIALLY_FILLED,
                        OrderState.CANCELED,
                    ]:

                        # Enhanced logging for debugging race conditions
                        self.logger().debug(
                            f"[PERIODIC_UPDATE] Order {order.client_order_id} state transition: "
                            f"{order.current_state.name} -> {order_update.new_state.name}"
                        )

                        self._order_tracker.process_order_update(order_update)

                        # Record the update timestamp
                        self._record_order_status_update(order.client_order_id)

                        if order_update.new_state in [OrderState.FILLED, OrderState.PARTIALLY_FILLED]:
                            trade_updates = await self._all_trade_updates_for_order(order)
                            if len(trade_updates) > 0:
                                for trade_update in trade_updates:
                                    self._order_tracker.process_trade_update(trade_update)

                            if order_update.new_state == OrderState.FILLED:
                                order.completely_filled_event.set()
                                # Clean up lock for completed order
                                await self._cleanup_order_status_lock(order.client_order_id)
                            elif order_update.new_state == OrderState.CANCELED:
                                # Clean up lock for canceled order
                                await self._cleanup_order_status_lock(order.client_order_id)

            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                await error_handler(order, request_error)

    async def _fetch_account_transactions(self, ledger_index: int, is_forward: bool = False) -> list:
        """
        Fetches account transactions from the XRPL ledger.

        :param ledger_index: The ledger index to start fetching transactions from.
        :param is_forward: If True, fetches transactions in forward order, otherwise in reverse order.
        :return: A list of transactions.
        """
        try:
            async with self._xrpl_fetch_trades_client_lock:
                return_transactions = []
                marker = None
                fetching_transactions = True

                while fetching_transactions:
                    request = AccountTx(
                        account=self._xrpl_auth.get_account(),
                        ledger_index_min=int(ledger_index) - CONSTANTS.LEDGER_OFFSET,
                        forward=is_forward,
                        marker=marker,
                    )

                    try:
                        response = await self.request_with_retry(request, 1, self._xrpl_query_client_lock, 1)
                        result = response.result
                        if result is not None:
                            transactions = result.get("transactions", [])
                            return_transactions.extend(transactions)
                            marker = result.get("marker", None)
                            if marker is None:
                                fetching_transactions = False
                        else:
                            fetching_transactions = False
                    except (ConnectionError, TimeoutError) as e:
                        self.logger().warning(f"ConnectionError or TimeoutError encountered: {e}")
                        await self._sleep(CONSTANTS.REQUEST_RETRY_INTERVAL)

        except Exception as e:
            self.logger().error(f"Failed to fetch account transactions: {e}")
            return_transactions = []

        return return_transactions

    async def _update_balances(self):
        self._node_pool.add_burst_tokens(4)

        account_address = self._xrpl_auth.get_account()

        account_info = await self.request_with_retry(
            AccountInfo(account=account_address, ledger_index="validated"),
            5,
            self._xrpl_query_client_lock,
            1,
        )

        objects = await self.request_with_retry(
            AccountObjects(
                account=account_address,
            ),
            5,
            self._xrpl_query_client_lock,
            1,
        )

        open_offers = [x for x in objects.result.get("account_objects", []) if x.get("LedgerEntryType") == "Offer"]

        account_lines = await self.request_with_retry(
            AccountLines(
                account=account_address,
            ),
            5,
            self._xrpl_query_client_lock,
            1,
        )

        if account_lines is not None:
            balances = account_lines.result.get("lines", [])
        else:
            balances = []

        xrp_balance = account_info.result.get("account_data", {}).get("Balance", "0")
        total_xrp = drops_to_xrp(xrp_balance)
        total_ledger_objects = len(objects.result.get("account_objects", []))
        available_xrp = total_xrp - CONSTANTS.WALLET_RESERVE - total_ledger_objects * CONSTANTS.LEDGER_OBJECT_RESERVE

        # Always set XRP balance from latest account_info
        account_balances = {
            "XRP": Decimal(total_xrp),
        }

        # If balances is not empty, update token balances as usual
        if len(balances) > 0:
            for balance in balances:
                currency = balance.get("currency")
                if len(currency) > 3:
                    try:
                        currency = hex_to_str(currency)
                    except UnicodeDecodeError:
                        # Do nothing since this is a non-hex string
                        pass

                token = currency.strip("\x00").upper()
                token_issuer = balance.get("account")
                token_symbol = self.get_token_symbol_from_all_markets(token, token_issuer)

                amount = balance.get("balance")

                if token_symbol is None:
                    continue

                account_balances[token_symbol] = abs(Decimal(amount))
        # If balances is empty, fallback to previous token balances (but not XRP)
        elif self._account_balances is not None:
            for token, amount in self._account_balances.items():
                if token != "XRP":
                    account_balances[token] = amount

        account_available_balances = account_balances.copy()
        account_available_balances["XRP"] = Decimal(available_xrp)

        for offer in open_offers:
            taker_gets = offer.get("TakerGets")
            taker_gets_funded = offer.get("taker_gets_funded", None)

            if taker_gets_funded is not None:
                if isinstance(taker_gets_funded, dict):
                    token = taker_gets_funded.get("currency", "")
                    token_issuer = taker_gets_funded.get("issuer", "")
                    if token and len(token) > 3:
                        token = hex_to_str(token).strip("\x00").upper()
                    token_symbol = self.get_token_symbol_from_all_markets(token or "", token_issuer or "")
                    amount = Decimal(taker_gets_funded.get("value", "0"))
                else:
                    amount = drops_to_xrp(taker_gets_funded)
                    token_symbol = "XRP"
            else:
                if isinstance(taker_gets, dict):
                    token = taker_gets.get("currency", "")
                    token_issuer = taker_gets.get("issuer", "")
                    if token and len(token) > 3:
                        token = hex_to_str(token).strip("\x00").upper()
                    token_symbol = self.get_token_symbol_from_all_markets(token or "", token_issuer or "")
                    amount = Decimal(taker_gets.get("value", "0"))
                else:
                    amount = drops_to_xrp(taker_gets)
                    token_symbol = "XRP"

            if token_symbol is None:
                continue

            account_available_balances[token_symbol] -= amount

        # Clear existing dictionaries to prevent reference retention
        if self._account_balances is not None:
            self._account_balances.clear()
            self._account_balances.update(account_balances)
        else:
            self._account_balances = account_balances

        if self._account_available_balances is not None:
            self._account_available_balances.clear()
            self._account_available_balances.update(account_available_balances)
        else:
            self._account_available_balances = account_available_balances

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, XRPLMarket]):
        markets = exchange_info
        mapping_symbol = bidict()

        for market, _ in markets.items():
            self.logger().debug(f"Processing market {market}")
            mapping_symbol[market.upper()] = market.upper()
        self._set_trading_pair_symbol_map(mapping_symbol)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        # NOTE: We are querying both the order book and the AMM pool to get the last traded price
        last_traded_price = float(0)
        last_traded_price_timestamp = 0

        order_book = self.order_books.get(trading_pair)
        data_source: XRPLAPIOrderBookDataSource = self.order_book_tracker.data_source

        if order_book is not None:
            order_book_last_trade_price = order_book.last_trade_price
            last_traded_price = (
                order_book_last_trade_price
                if order_book_last_trade_price is not None and not math.isnan(order_book_last_trade_price)
                else float(0)
            )
            last_traded_price_timestamp = data_source.last_parsed_order_book_timestamp.get(trading_pair, 0)

        if (math.isnan(last_traded_price) or last_traded_price == 0) and order_book is not None:
            best_bid = order_book.get_price(is_buy=True)
            best_ask = order_book.get_price(is_buy=False)

            is_best_bid_valid = best_bid is not None and not math.isnan(best_bid)
            is_best_ask_valid = best_ask is not None and not math.isnan(best_ask)

            if is_best_bid_valid and is_best_ask_valid:
                last_traded_price = (best_bid + best_ask) / 2
                last_traded_price_timestamp = data_source.last_parsed_order_book_timestamp.get(trading_pair, 0)
            else:
                last_traded_price = float(0)
                last_traded_price_timestamp = 0
        amm_pool_price, amm_pool_last_tx_timestamp = await self.get_price_from_amm_pool(trading_pair)

        if not math.isnan(amm_pool_price):
            if amm_pool_last_tx_timestamp > last_traded_price_timestamp:
                last_traded_price = amm_pool_price
            elif math.isnan(last_traded_price):
                last_traded_price = amm_pool_price
        return last_traded_price

    async def _get_best_price(self, trading_pair: str, is_buy: bool) -> float:
        best_price = float(0)

        order_book = self.order_books.get(trading_pair)

        if order_book is not None:
            best_price = order_book.get_price(is_buy)

        amm_pool_price, amm_pool_last_tx_timestamp = await self.get_price_from_amm_pool(trading_pair)

        if not math.isnan(amm_pool_price):
            if is_buy:
                best_price = min(best_price, amm_pool_price) if not math.isnan(best_price) else amm_pool_price
            else:
                best_price = max(best_price, amm_pool_price) if not math.isnan(best_price) else amm_pool_price
        return best_price

    async def get_price_from_amm_pool(self, trading_pair: str) -> Tuple[float, int]:
        base_token, quote_token = self.get_currencies_from_trading_pair(trading_pair)
        tx_timestamp = 0
        price = float(0)

        try:
            resp: Response = await self.request_with_retry(
                AMMInfo(
                    asset=base_token,
                    asset2=quote_token,
                ),
                3,
                self._xrpl_query_client_lock,
                1,
            )
        except Exception as e:
            self.logger().error(f"Error fetching AMM pool info for {trading_pair}: {e}")
            return price, tx_timestamp

        amm_pool_info = resp.result.get("amm", None)

        if amm_pool_info is None:
            return price, tx_timestamp

        try:
            tx_resp: Response = await self.request_with_retry(
                AccountTx(
                    account=resp.result.get("amm", {}).get("account"),
                    limit=1,
                ),
                3,
                self._xrpl_query_client_lock,
                1,
            )

            tx = tx_resp.result.get("transactions", [{}])[0]
            tx_timestamp = ripple_time_to_posix(tx.get("tx_json", {}).get("date", 0))
        except Exception as e:
            self.logger().error(f"Error fetching AMM pool transaction info for {trading_pair}: {e}")
            return price, tx_timestamp

        amount = amm_pool_info.get("amount")  # type: ignore
        amount2 = amm_pool_info.get("amount2")  # type: ignore

        # Check if we have valid amounts
        if amount is None or amount2 is None:
            return price, tx_timestamp
        if isinstance(amount, str):
            base_amount = drops_to_xrp(amount)
        else:
            base_amount = Decimal(amount.get("value", "0"))

        # Convert quote amount (amount2) if it's XRP
        if isinstance(amount2, str):
            quote_amount = drops_to_xrp(amount2)
        else:
            # For issued currencies, amount2 is a dictionary with a 'value' field
            quote_amount = Decimal(amount2.get("value", "0"))

        # Calculate price as quote/base
        if base_amount == 0:
            return price, tx_timestamp

        price = float(quote_amount / base_amount)

        self.logger().debug(f"AMM pool price for {trading_pair}: {price}")
        self.logger().debug(f"AMM pool transaction timestamp for {trading_pair}: {tx_timestamp}")
        return price, tx_timestamp

    def buy(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        random_uuid = str(uuid.uuid4())[:6]
        prefix = f"{self.client_order_id_prefix}-{self._nonce_creator.get_tracking_nonce()}-{random_uuid}-"
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=prefix,
            max_id_len=self.client_order_id_max_length,
        )

        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        random_uuid = str(uuid.uuid4())[:6]
        prefix = f"{self.client_order_id_prefix}-{self._nonce_creator.get_tracking_nonce()}-{random_uuid}-"
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=prefix,
            max_id_len=self.client_order_id_max_length,
        )
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return order_id

    async def _update_trading_rules(self):
        trading_rules_info = await self._make_trading_rules_request()
        trading_rules_list = self._format_trading_rules(trading_rules_info)
        trading_pair_fee_rules = self._format_trading_pair_fee_rules(trading_rules_info)
        self._trading_rules.clear()
        self._trading_pair_fee_rules.clear()

        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        for trading_pair_fee_rule in trading_pair_fee_rules:
            self._trading_pair_fee_rules[trading_pair_fee_rule["trading_pair"]] = trading_pair_fee_rule

        exchange_info = self._make_xrpl_trading_pairs_request()

        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = self._make_xrpl_trading_pairs_request()
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception as e:
            self.logger().exception(f"There was an error requesting exchange info: {e}")

    async def _make_network_check_request(self):
        self._node_pool.add_burst_tokens(1)
        client = await self._get_async_client()
        try:
            await client.open()
        finally:
            # Ensure client is always closed to prevent memory leak
            await client.close()

    async def _make_trading_rules_request(self) -> Dict[str, Any]:
        zeroTransferRate = 1000000000
        trading_rules_info = {}

        if self._trading_pairs is None:
            raise ValueError("Trading pairs list cannot be None")

        for trading_pair in self._trading_pairs:
            base_currency, quote_currency = self.get_currencies_from_trading_pair(trading_pair)

            if base_currency.currency == XRP().currency:
                baseTickSize = 6  # XRP has 6 decimal places
                baseTransferRate = 0  # XRP has no transfer fee
            else:
                # Ensure base_currency is IssuedCurrency before accessing issuer
                if not isinstance(base_currency, IssuedCurrency):
                    raise ValueError(f"Expected IssuedCurrency but got {type(base_currency)}")

                base_info = await self.request_with_retry(
                    AccountInfo(account=base_currency.issuer, ledger_index="validated"),
                    3,
                    self._xrpl_query_client_lock,
                    1,
                )

                if base_info.status == ResponseStatus.ERROR:
                    error_message = base_info.result.get("error_message")
                    raise ValueError(f"Base currency {base_currency} not found in ledger: {error_message}")

                baseTickSize = base_info.result.get("account_data", {}).get("TickSize", 15)
                rawTransferRate = base_info.result.get("account_data", {}).get("TransferRate", zeroTransferRate)
                baseTransferRate = float(rawTransferRate / zeroTransferRate) - 1

            if quote_currency.currency == XRP().currency:
                quoteTickSize = 6  # XRP has 6 decimal places
                quoteTransferRate = 0  # XRP has no transfer fee
            else:
                # Ensure quote_currency is IssuedCurrency before accessing issuer
                if not isinstance(quote_currency, IssuedCurrency):
                    raise ValueError(f"Expected IssuedCurrency but got {type(quote_currency)}")

                quote_info = await self.request_with_retry(
                    AccountInfo(account=quote_currency.issuer, ledger_index="validated"),
                    3,
                    self._xrpl_query_client_lock,
                    1,
                )

                if quote_info.status == ResponseStatus.ERROR:
                    error_message = quote_info.result.get("error_message")
                    raise ValueError(f"Quote currency {quote_currency} not found in ledger: {error_message}")

                quoteTickSize = quote_info.result.get("account_data", {}).get("TickSize", 15)
                rawTransferRate = quote_info.result.get("account_data", {}).get("TransferRate", zeroTransferRate)
                quoteTransferRate = float(rawTransferRate / zeroTransferRate) - 1

            smallestTickSize = min(baseTickSize, quoteTickSize)
            minimumOrderSize = float(10) ** -smallestTickSize

            # Get fee from AMM Pool if available
            amm_pool_info = await self.amm_get_pool_info(trading_pair=trading_pair)

            trading_rules_info[trading_pair] = {
                "base_currency": base_currency,
                "quote_currency": quote_currency,
                "base_tick_size": baseTickSize,
                "quote_tick_size": quoteTickSize,
                "base_transfer_rate": baseTransferRate,
                "quote_transfer_rate": quoteTransferRate,
                "minimum_order_size": minimumOrderSize,
                "amm_pool_info": amm_pool_info,
            }

        return trading_rules_info

    def _make_xrpl_trading_pairs_request(self) -> Dict[str, XRPLMarket]:
        # Load default markets
        markets = CONSTANTS.MARKETS
        loaded_markets: Dict[str, XRPLMarket] = {}

        # Load each market into XRPLMarket
        for k, v in markets.items():
            loaded_markets[k] = XRPLMarket(
                base=v["base"],
                base_issuer=v["base_issuer"],
                quote=v["quote"],
                quote_issuer=v["quote_issuer"],
                trading_pair_symbol=k,
            )

        # Merge default markets with custom markets
        loaded_markets.update(self._custom_markets)

        return loaded_markets

    def get_currencies_from_trading_pair(
        self, trading_pair: str
    ) -> (Tuple)[Union[IssuedCurrency, XRP], Union[IssuedCurrency, XRP]]:
        # Find market in the markets list
        all_markets = self._make_xrpl_trading_pairs_request()
        market = all_markets.get(trading_pair, None)

        if market is None:
            raise ValueError(f"Market {trading_pair} not found in markets list")

        # Get all info
        base = market.base
        base_issuer = market.base_issuer
        quote = market.quote
        quote_issuer = market.quote_issuer

        if base == "XRP":
            base_currency = XRP()
        else:
            formatted_base = convert_string_to_hex(base)
            base_currency = IssuedCurrency(currency=formatted_base, issuer=base_issuer)

        if quote == "XRP":
            quote_currency = XRP()
        else:
            formatted_quote = convert_string_to_hex(quote)
            quote_currency = IssuedCurrency(currency=formatted_quote, issuer=quote_issuer)

        return base_currency, quote_currency

    async def tx_autofill(
        self, transaction: Transaction, client: Client, signers_count: Optional[int] = None
    ) -> Transaction:
        return await autofill(transaction, client, signers_count)

    def tx_sign(
        self,
        transaction: Transaction,
        wallet: Wallet,
        multisign: bool = False,
    ) -> Transaction:
        return sign(transaction, wallet, multisign)

    async def tx_submit(
        self,
        transaction: Transaction,
        client: Client,
        *,
        fail_hard: bool = False,
    ) -> Response:
        transaction_blob = encode(transaction.to_xrpl())
        response = await client._request_impl(
            SubmitOnly(tx_blob=transaction_blob, fail_hard=fail_hard), timeout=CONSTANTS.REQUEST_TIMEOUT
        )
        if response.is_successful():
            return response

        raise XRPLRequestFailureException(response.result)

    async def wait_for_final_transaction_outcome(self, transaction, prelim_result) -> Response:
        async with await self._get_async_client() as client:
            resp = await _wait_for_final_transaction_outcome(
                transaction.get_hash(), client, prelim_result, transaction.last_ledger_sequence
            )
        return resp

    async def request_with_retry(
        self,
        request: Request,
        max_retries: int = 3,
        lock: Optional[Lock] = None,
        delay_time: float = 0.0,
    ) -> Response:
        # Use proper context manager to prevent memory leaks
        client = await self._get_async_client()
        try:
            # Configure client before using in context manager
            await client.open()
            if hasattr(client, "_websocket") and client._websocket is not None:
                client._websocket.max_size = CONSTANTS.WEBSOCKET_MAX_SIZE_BYTES
                client._websocket.ping_timeout = CONSTANTS.WEBSOCKET_CONNECTION_TIMEOUT

            # Use context manager properly - client is already opened
            if lock is not None:
                async with lock:
                    resp = await client.request(request)
            else:
                resp = await client.request(request)

            await self._sleep(delay_time)
            return resp

        except Exception as e:
            # If timeout error or connection error, mark node as bad
            if isinstance(e, (TimeoutError, ConnectionError)):
                self.logger().error(f"Node {client.url} is bad, marking as bad")
                self._node_pool.mark_bad_node(client.url)

            if max_retries > 0:
                await self._sleep(CONSTANTS.REQUEST_RETRY_INTERVAL)
                return await self.request_with_retry(request, max_retries - 1, lock, delay_time)
            else:
                self.logger().error(f"Max retries reached. Request {request} failed: {e}", exc_info=True)
                raise e
        finally:
            # Ensure client is always closed to prevent memory leak
            await client.close()

    def get_token_symbol_from_all_markets(self, code: str, issuer: str) -> Optional[str]:
        all_markets = self._make_xrpl_trading_pairs_request()
        for market in all_markets.values():
            token_symbol = market.get_token_symbol(code, issuer)

            if token_symbol is not None:
                return token_symbol.upper()

        return None

    # AMM functions
    async def amm_get_pool_info(
        self, pool_address: Optional[str] = None, trading_pair: Optional[str] = None
    ) -> Optional[PoolInfo]:
        """
        Get information about a specific AMM liquidity pool

        :param pool_address: The address of the AMM pool
        :param trading_pair: The trading pair to get the pool info for
        :param network: Optional network specification
        :return: Pool information
        """
        if pool_address is not None:
            resp: Response = await self.request_with_retry(
                AMMInfo(
                    amm_account=pool_address,
                ),
                3,
                self._xrpl_query_client_lock,
                1,
            )
        elif trading_pair is not None:
            base_token, quote_token = self.get_currencies_from_trading_pair(trading_pair)
            resp: Response = await self.request_with_retry(
                AMMInfo(
                    asset=base_token,
                    asset2=quote_token,
                ),
                3,
                self._xrpl_query_client_lock,
                1,
            )
        else:
            self.logger().error("No pool_address or trading_pair provided")
            return None

        # Process the response and convert to our PoolInfo model
        amm_pool_info = resp.result.get("amm", {})

        # Extract pool address
        extracted_pool_address = amm_pool_info.get("account", None)

        if extracted_pool_address is None:
            self.logger().debug(f"No AMM pool info found for {trading_pair if trading_pair else pool_address}")
            return None

        # Extract amounts
        amount1: Any = amm_pool_info.get("amount", None)
        amount2: Any = amm_pool_info.get("amount2", None)
        lp_token: Any = amm_pool_info.get("lp_token", None)

        if amount1 is None or amount2 is None or lp_token is None:
            self.logger().error(f"Missing amounts or lp_token for {trading_pair if trading_pair else pool_address}")
            return None

        # Convert to decimals based on token type
        if isinstance(amount1, str):
            base_amount = drops_to_xrp(amount1)
        else:
            base_amount = Decimal(amount1.get("value", "0"))

        if isinstance(amount2, str):
            quote_amount = drops_to_xrp(amount2)
        else:
            quote_amount = Decimal(amount2.get("value", "0"))

        lp_token_amount = Decimal(lp_token.get("value", "0")) if lp_token else Decimal("0")

        # Calculate price
        price = quote_amount / base_amount if base_amount > 0 else Decimal("0")

        # Get fee percentage
        fee_pct = Decimal(amm_pool_info.get("trading_fee", "0")) / Decimal(
            "1000"
        )  # XRPL expresses fees in basis points

        base_token_address: Currency = (
            IssuedCurrency(currency=amount1.get("currency"), issuer=amount1.get("issuer"))
            if not isinstance(amount1, str)
            else XRP()
        )
        quote_token_address: Currency = (
            IssuedCurrency(currency=amount2.get("currency"), issuer=amount2.get("issuer"))
            if not isinstance(amount2, str)
            else XRP()
        )
        lp_token_addess: Currency = IssuedCurrency(currency=lp_token.get("currency"), issuer=lp_token.get("issuer"))

        return PoolInfo(
            address=extracted_pool_address,
            base_token_address=base_token_address,
            quote_token_address=quote_token_address,
            lp_token_address=lp_token_addess,
            fee_pct=fee_pct,
            price=price,
            base_token_amount=base_amount,
            quote_token_amount=quote_amount,
            lp_token_amount=lp_token_amount,
            pool_type="XRPL-AMM",
        )

    async def amm_quote_add_liquidity(
        self,
        pool_address: str,
        base_token_amount: Decimal,
        quote_token_amount: Decimal,
        slippage_pct: Decimal = Decimal("0"),
        network: Optional[str] = None,
    ) -> Optional[QuoteLiquidityResponse]:
        """
        Get a quote for adding liquidity to an AMM pool

        :param pool_address: The address of the AMM pool
        :param base_token_amount: Amount of base token to add
        :param quote_token_amount: Amount of quote token to add
        :param slippage_pct: Optional slippage percentage
        :param network: Optional network specification
        :return: Quote for adding liquidity
        """
        # Get current pool state
        pool_info = await self.amm_get_pool_info(pool_address, network)

        if pool_info is None:
            self.logger().error(f"No pool info found for {pool_address}")
            return None

        # Calculate the optimal amounts based on current pool ratio
        current_ratio = (
            pool_info.quote_token_amount / pool_info.base_token_amount
            if pool_info.base_token_amount > 0
            else Decimal("0")
        )

        # Calculate maximum amounts based on provided amounts
        if base_token_amount * current_ratio > quote_token_amount:
            # Base limited
            base_limited = True
            quote_token_amount_required = base_token_amount * current_ratio
            quote_token_amount_max = quote_token_amount_required * (Decimal("1") + (slippage_pct))
            return QuoteLiquidityResponse(
                base_limited=base_limited,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount_required,
                base_token_amount_max=base_token_amount,
                quote_token_amount_max=quote_token_amount_max,
            )
        else:
            # Quote limited
            base_limited = False
            base_token_amount_required = quote_token_amount / current_ratio
            base_token_amount_max = base_token_amount_required * (Decimal("1") + (slippage_pct))
            return QuoteLiquidityResponse(
                base_limited=base_limited,
                base_token_amount=base_token_amount_required,
                quote_token_amount=quote_token_amount,
                base_token_amount_max=base_token_amount_max,
                quote_token_amount_max=quote_token_amount,
            )

    async def amm_add_liquidity(
        self,
        pool_address: str,
        wallet_address: str,
        base_token_amount: Decimal,
        quote_token_amount: Decimal,
        slippage_pct: Decimal = Decimal("0"),
        network: Optional[str] = None,
    ) -> Optional[AddLiquidityResponse]:
        """
        Add liquidity to an AMM pool

        :param pool_address: The address of the AMM pool
        :param wallet_address: The address of the wallet to use
        :param base_token_amount: Amount of base token to add
        :param quote_token_amount: Amount of quote token to add
        :param slippage_pct: Optional slippage percentage
        :param network: Optional network specification
        :return: Result of adding liquidity
        """
        # Get pool info to determine token types
        pool_info = await self.amm_get_pool_info(pool_address, network)

        if pool_info is None:
            self.logger().error(f"No pool info found for {pool_address}")
            return None

        # Get quote to determine optimal amounts
        quote = await self.amm_quote_add_liquidity(
            pool_address=pool_address,
            base_token_amount=base_token_amount,
            quote_token_amount=quote_token_amount,
            slippage_pct=slippage_pct,
            network=network,
        )

        if quote is None:
            self.logger().error(f"No quote found for {pool_address}")
            return None

        # Convert amounts based on token types (XRP vs. issued token)
        if isinstance(pool_info.base_token_address, XRP):
            base_amount = xrp_to_drops(quote.base_token_amount)
        else:
            base_value_amount = str(Decimal(quote.base_token_amount).quantize(Decimal("0.000001"), rounding=ROUND_DOWN))
            base_amount = IssuedCurrencyAmount(
                currency=pool_info.base_token_address.currency,
                issuer=pool_info.base_token_address.issuer,
                value=base_value_amount,
            )

        if isinstance(pool_info.quote_token_address, XRP):
            quote_amount = xrp_to_drops(quote.quote_token_amount)
        else:
            quote_value_amount = str(
                Decimal(quote.quote_token_amount).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
            )
            quote_amount = IssuedCurrencyAmount(
                currency=pool_info.quote_token_address.currency,
                issuer=pool_info.quote_token_address.issuer,
                value=quote_value_amount,
            )

        # Create memo
        memo_text = f"HBOT-Add-Liquidity:{pool_address}:{base_token_amount:.5f}({pool_info.base_token_address.currency}):{quote_token_amount:.5f}({pool_info.quote_token_address.currency})"
        memo = Memo(
            memo_data=convert_string_to_hex(memo_text, padding=False),
        )

        # Create AMMDeposit transaction
        account = self._xrpl_auth.get_account()
        deposit_transaction = AMMDeposit(
            account=account,
            asset=pool_info.base_token_address,
            asset2=pool_info.quote_token_address,
            amount=base_amount,
            amount2=quote_amount,
            lp_token_out=None,
            flags=1048576,
            memos=[memo],
        )

        # Sign and submit transaction
        tx_result = await self._submit_transaction(deposit_transaction)

        # Get balance changes
        tx_metadata = tx_result.result.get("meta", {})
        balance_changes = get_balance_changes(tx_metadata)

        base_token_amount_added = Decimal("0")
        quote_token_amount_added = Decimal("0")

        # Find balance changes by wallet address
        for change in balance_changes:
            if change.get("account") == wallet_address:
                # Check if the change is for the LP token
                balances = change.get("balances", [])
                for balance in balances:
                    if balance.get("currency") == pool_info.base_token_address.currency:
                        # Extract the base token amount removed
                        base_token_amount_added = abs(Decimal(balance.get("value")))
                    elif balance.get("currency") == pool_info.quote_token_address.currency:
                        # Extract the quote token amount removed
                        quote_token_amount_added = abs(Decimal(balance.get("value")))

        # Extract fee
        fee = drops_to_xrp(tx_result.result.get("tx_json", {}).get("Fee", "0"))

        return AddLiquidityResponse(
            signature=tx_result.result.get("tx_json", {}).get("hash", ""),
            fee=fee,
            base_token_amount_added=base_token_amount_added,
            quote_token_amount_added=quote_token_amount_added,
        )

    async def amm_remove_liquidity(
        self, pool_address: str, wallet_address: str, percentage_to_remove: Decimal, network: Optional[str] = None
    ) -> Optional[RemoveLiquidityResponse]:
        """
        Remove liquidity from an AMM pool

        :param pool_address: The address of the AMM pool
        :param wallet_address: The address of the wallet to use
        :param percentage_to_remove: Percentage of liquidity to remove (0-100)
        :param network: Optional network specification
        :return: Result of removing liquidity
        """
        # Get current pool info
        pool_info = await self.amm_get_pool_info(pool_address, network)

        if pool_info is None:
            self.logger().error(f"No pool info found for {pool_address}")
            return None

        # Get user's LP tokens for this pool
        account = self._xrpl_auth.get_account()
        resp = await self.request_with_retry(
            AccountObjects(
                account=account,
            ),
            3,
            self._xrpl_query_client_lock,
            1,
        )

        account_objects = resp.result.get("account_objects", [])

        # Filter for currency that matches lp token issuer
        lp_tokens = [
            obj for obj in account_objects if obj.get("Balance").get("currency") == pool_info.lp_token_address.currency
        ]

        lp_token_amount = lp_tokens.pop(0).get("Balance").get("value")

        if not lp_token_amount:
            raise ValueError(f"No LP tokens found for pool {pool_address}")
        #
        # Calculate amount to withdraw based on percentage
        withdraw_amount = abs(Decimal(lp_token_amount) * (percentage_to_remove / Decimal("100"))).quantize(
            Decimal("0.000001"), rounding=ROUND_DOWN
        )

        if percentage_to_remove >= Decimal("100"):
            withdraw_flag = 0x00020000
            lp_token_to_withdraw = None
        else:
            withdraw_flag = 0x00010000
            lp_token_to_withdraw = IssuedCurrencyAmount(
                currency=pool_info.lp_token_address.currency,
                issuer=pool_info.lp_token_address.issuer,
                value=str(withdraw_amount),
            )

        # Create memo
        memo_text = f"HBOT-Remove-Liquidity:{pool_address}:{percentage_to_remove}"
        memo = Memo(
            memo_data=convert_string_to_hex(memo_text, padding=False),
        )

        # Create AMMWithdraw transaction
        withdraw_transaction = AMMWithdraw(
            account=wallet_address,
            asset=pool_info.base_token_address,
            asset2=pool_info.quote_token_address,
            lp_token_in=lp_token_to_withdraw,
            flags=withdraw_flag,
            memos=[memo],
        )

        self.logger().debug(f"AMMWithdraw transaction: {withdraw_transaction}")

        # Sign and submit transaction
        tx_result = await self._submit_transaction(withdraw_transaction)
        tx_metadata = tx_result.result.get("meta", {})
        balance_changes = get_balance_changes(tx_metadata)

        base_token_amount_removed = Decimal("0")
        quote_token_amount_removed = Decimal("0")

        # Find balance changes by wallet address
        for change in balance_changes:
            if change.get("account") == wallet_address:
                # Check if the change is for the LP token
                balances = change.get("balances", [])
                for balance in balances:
                    if balance.get("currency") == pool_info.base_token_address.currency:
                        # Extract the base token amount removed
                        base_token_amount_removed = Decimal(balance.get("value", "0"))
                    elif balance.get("currency") == pool_info.quote_token_address.currency:
                        # Extract the quote token amount removed
                        quote_token_amount_removed = Decimal(balance.get("value", "0"))

        # Extract fee
        fee = drops_to_xrp(tx_result.result.get("tx_json", {}).get("Fee", "0"))

        return RemoveLiquidityResponse(
            signature=tx_result.result.get("tx_json", {}).get("hash", ""),
            fee=fee,
            base_token_amount_removed=base_token_amount_removed,
            quote_token_amount_removed=quote_token_amount_removed,
        )

    async def amm_get_balance(self, pool_address: str, wallet_address: str) -> Dict[str, Any]:
        """
        Get the balance of an AMM pool for a specific wallet address

        :param pool_address: The address of the AMM pool
        :param wallet_address: The address of the wallet to check
        :return: A dictionary containing the balance information
        """
        # Use the XRPL AccountLines query
        resp: Response = await self.request_with_retry(
            AccountLines(
                account=wallet_address,
                peer=pool_address,
            ),
            3,
            self._xrpl_query_client_lock,
            1,
        )

        # Process the response and extract balance information
        lines = resp.result.get("lines", [])

        # Get AMM Pool info
        pool_info: PoolInfo | None = await self.amm_get_pool_info(pool_address)

        if pool_info is None:
            self.logger().error(f"No pool info found for {pool_address}")
            return {
                "base_token_lp_amount": Decimal("0"),
                "base_token_address": None,
                "quote_token_lp_amount": Decimal("0"),
                "quote_token_address": None,
                "lp_token_amount": Decimal("0"),
                "lp_token_amount_pct": Decimal("0"),
            }

        lp_token_balance = None
        for line in lines:
            if line.get("account") == pool_address:
                lp_token_balance = {
                    "balance": line.get("balance"),
                    "currency": line.get("currency"),
                    "issuer": line.get("account"),
                }
                break

        if lp_token_balance is None:
            return {
                "base_token_lp_amount": Decimal("0"),
                "base_token_address": pool_info.base_token_address,
                "quote_token_lp_amount": Decimal("0"),
                "quote_token_address": pool_info.quote_token_address,
                "lp_token_amount": Decimal("0"),
                "lp_token_amount_pct": Decimal("0"),
            }

        lp_token_amount = Decimal(lp_token_balance.get("balance", "0"))
        lp_token_amount_pct = (
            lp_token_amount / pool_info.lp_token_amount if pool_info.lp_token_amount > 0 else Decimal("0")
        )
        base_token_lp_amount = pool_info.base_token_amount * lp_token_amount_pct
        quote_token_lp_amount = pool_info.quote_token_amount * lp_token_amount_pct

        balance_info = {
            "base_token_lp_amount": base_token_lp_amount,
            "base_token_address": pool_info.base_token_address,
            "quote_token_lp_amount": quote_token_lp_amount,
            "quote_token_address": pool_info.quote_token_address,
            "lp_token_amount": lp_token_amount,
            "lp_token_amount_pct": lp_token_amount_pct * Decimal("100"),
        }

        return balance_info

    # Helper method for transaction submission using reliable submission method
    async def _submit_transaction(self, transaction):
        """Helper method to submit a transaction and wait for result"""

        # Submit transaction with retry logic
        retry_count = 0
        max_retries = CONSTANTS.PLACE_ORDER_MAX_RETRY
        submit_result = None

        while retry_count < max_retries:
            try:
                async with self._xrpl_place_order_client_lock:
                    async with await self._get_async_client() as client:
                        # Autofill transaction details
                        filled_tx = await self.tx_autofill(transaction, client)

                        # Sign transaction
                        wallet = self._xrpl_auth.get_wallet()
                        signed_tx = sign(filled_tx, wallet)

                        submit_result = await async_submit_and_wait(
                            signed_tx, client, wallet, autofill=False, fail_hard=True
                        )

                if submit_result.status == ResponseStatus.SUCCESS:
                    break

                self.logger().warning(f"Transaction attempt {retry_count + 1} failed: {submit_result.result}")
                retry_count += 1

                if retry_count < max_retries:
                    await self._sleep(CONSTANTS.PLACE_ORDER_RETRY_INTERVAL)

            except Exception as e:
                self.logger().error(f"Error during transaction submission: {str(e)}")
                retry_count += 1

                if retry_count < max_retries:
                    await self._sleep(CONSTANTS.PLACE_ORDER_RETRY_INTERVAL)

        if submit_result is None or submit_result.status != ResponseStatus.SUCCESS:
            raise ValueError(
                f"Transaction failed after {max_retries} attempts: {submit_result.result if submit_result else 'No result'}"
            )

        return submit_result
