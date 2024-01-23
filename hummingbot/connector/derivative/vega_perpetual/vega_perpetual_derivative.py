import asyncio
import json
import math
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.derivative.vega_perpetual import (
    vega_perpetual_constants as CONSTANTS,
    vega_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_api_order_book_data_source import (
    VegaPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_auth import VegaPerpetualAuth
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_data import Asset, Market, VegaTimeInForce
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_user_stream_data_source import (
    VegaPerpetualUserStreamDataSource,
)
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, aiohttp
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

logger = None


class VegaPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            vega_perpetual_public_key: str = None,
            vega_perpetual_seed_phrase: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.vega_perpetual_public_key = vega_perpetual_public_key
        self.vega_perpetual_seed_phrase = vega_perpetual_seed_phrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._assets_by_id = {}
        self._id_by_hb_pair = {}
        self._exchange_info = {}
        self._locked_balances = {}
        self._exchange_order_id_to_hb_order_id = {}
        self._has_updated_throttler = False
        self._best_connection_endpoint = ""
        self._is_connected = True
        self._order_cancel_attempts = {}

        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        if self._domain == CONSTANTS.TESTNET_DOMAIN:
            return CONSTANTS.TESTNET_DOMAIN
        return CONSTANTS.EXCHANGE_NAME  # pragma no cover

    @property
    def authenticator(self) -> VegaPerpetualAuth:
        return VegaPerpetualAuth(self.vega_perpetual_public_key, self.vega_perpetual_seed_phrase, self.domain)

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS  # pragma no cover

    @property
    def domain(self) -> str:
        return self._domain  # pragma no cover

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN  # pragma no cover

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.BROKER_ID  # pragma no cover

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL  # pragma no cover

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL  # pragma no cover

    @property
    def symbols_request_path(self) -> str:
        return CONSTANTS.SYMBOLS_URL  # pragma no cover

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_URL  # pragma no cover

    @property
    def check_blockchain_request_path(self) -> str:
        return CONSTANTS.SERVER_TIME_PATH_URL  # pragma no cover

    @property
    def trading_pairs(self):
        return self._trading_pairs  # pragma no cover

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False  # pragma no cover

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required  # pragma no cover

    @property
    def funding_fee_poll_interval(self) -> int:
        funding_intervals = []
        for trading_pair in self.trading_pairs:
            market_id = self._market_id_from_hb_pair(trading_pair=trading_pair)
            m: Market = self._exchange_info.get(market_id)
            if m is not None and m.funding_fee_interval is not None:
                funding_intervals.append(m.funding_fee_interval)
        if len(funding_intervals) > 0:
            return min(funding_intervals)
        # Default to 10 minutes
        return 600

    async def connection_base(self) -> None:
        # This function makes requests to all Vega endpoints to determine lowest latency.
        endpoints = CONSTANTS.PERPETUAL_API_ENDPOINTS
        if self._domain == CONSTANTS.TESTNET_DOMAIN:
            endpoints = CONSTANTS.TESTNET_API_ENDPOINTS
        result = await self.lowest_latency_result(endpoints=endpoints)
        self._is_connected = True
        self._best_connection_endpoint = result

    async def lowest_latency_result(self, endpoints: List[str]) -> str:
        results: List[Dict[str, Decimal]] = []
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        for connection in endpoints:
            try:
                url = f"{connection}api/v2{self.check_network_request_path}"
                _start_time = time.time_ns()
                request = RESTRequest(
                    method=RESTMethod.GET,
                    url=url,
                    params=None,
                    data=None,
                    throttler_limit_id=CONSTANTS.ALL_URLS
                )
                await rest_assistant.call(request=request, timeout=3.0)
                _end_time = time.time_ns()
                _request_latency = _end_time - _start_time
                # Check to ensure we have a match
                _time_ms = Decimal(_request_latency)
                results.append({"connection": connection, "latency": _time_ms})
            except Exception as e:
                self.logger().debug(f"Unable to fetch and match for endpoint {connection} {e}")
        if len(results) > 0:
            # Sort the results
            sorted_result = sorted(results, key=lambda x: x['latency'])
            # Return the connection endpoint with the best response time
            self.logger().info(f"Connected to Vega Protocol endpoint: {sorted_result[0]['connection']}")
            return sorted_result[0]["connection"]
        else:
            raise IOError("Unable to reach any endpoint for Vega Protocol, check configuration and try again.")

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    async def _make_blockchain_check_request(self):
        try:
            response = await self._api_request(path_url=self.check_blockchain_request_path,
                                               return_err=True)
        except Exception as e:
            self.logger().warning(e)
            return False
        current_block_time = None if response is None else response.get("timestamp", None)
        if current_block_time is None:
            self.logger().error("Unable to fetch blockchain time, stopping network")
            return False
        # NOTE: Checking to see if block time is significantly behind
        current_time_ns = time.time_ns()
        time_diff = float((current_time_ns - (float(current_block_time))) * 1e-9)
        # NOTE: Check for 1 minute difference
        if time_diff > float(60):
            self.logger().error("Block time is > 60 seconds behind, stopping network")
            return False
        return True

    # NOTE: Overridden this function to do additional key and block checking
    async def check_network(self) -> NetworkStatus:
        """
        Checks connectivity with the exchange using the API
        """
        if not self._user_stream_tracker._data_source._ws_connected:
            return NetworkStatus.NOT_CONNECTED
        if not self._orderbook_ds._ws_connected:
            return NetworkStatus.NOT_CONNECTED
        if not self._is_connected:
            return NetworkStatus.STOPPED
        try:
            if await self._make_blockchain_check_request():
                await self._make_network_check_request()
            else:
                return NetworkStatus.STOPPED
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def start_network(self):
        """
        start_network is called from hb when the network is available.
        This is used for initialization of the connector.
        NOTE: this is NOT called when the connector is used to get balance or similar, a new instance is used
        """
        await self.connection_base()
        if not self.authenticator.confirm_pub_key_matches_generated():
            self.logger().error("The generated key doesn't match the public key you provided, review your connection and try again.")
        await self._populate_symbols()
        await self._populate_exchange_info()
        await super().start_network()

    async def stop_network(self):
        await self.cancel_all(10.0)
        await self._sleep(1.0)
        await safe_gather(
            self._update_all_balances(),
            self._update_order_status(),
        )
        await super().stop_network()

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.ONEWAY]  # pragma no cover

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        """
        get_buy_collateral_token is called from hb to get the name of the token used for collateral when buying
        :return the name of the token used for collateral when buying
        """
        market_id = self._market_id_from_hb_pair(trading_pair=trading_pair)

        m: Market = self._exchange_info.get(market_id)
        return m.buy_collateral_token.hb_name

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        """
        get_sell_collateral_token is called from hb to get the name of the token used for collateral when selling
        :return the name of the token used for collateral when selling
        """
        market_id = self._market_id_from_hb_pair(trading_pair=trading_pair)
        m: Market = self._exchange_info.get(market_id)
        return m.sell_collateral_token.hb_name

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        """
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related
        """
        return False  # pragma no cover

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str("Order not found") in str(status_update_exception)  # pragma no cover

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str("error code 60") in str(cancelation_exception)  # pragma no cover

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return VegaPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return VegaPerpetualUserStreamDataSource(
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or False
        fee = build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )
        return fee

    async def _update_trading_fees(self):  # pragma: no cover
        """
        Fees are assessed on trade execution across, infrasturcture, lp, and maker fees with discounts applied
        """
        pass

    async def _update_throttler(self, limit: int, time_interval: float) -> None:
        from_headers_rate_limit = [RateLimit(limit_id=str(CONSTANTS.ALL_URLS), limit=int(limit), time_interval=float(time_interval))]
        self._throttler.set_rate_limits(rate_limits=from_headers_rate_limit)
        self.logger().debug("updated rate limits")
        self._has_updated_throttler = True

    async def _status_polling_loop_fetch_updates(self):  # pragma: no cover
        await safe_gather(
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )
        self._do_housekeeping()

    async def _execute_order_cancel_and_process_update(self, order: InFlightOrder) -> bool:
        # Modification to handle failed orders, we're still trying to process for cancel.
        if order.current_state == OrderState.FAILED:
            update_timestamp = self.current_timestamp
            if update_timestamp is None or math.isnan(update_timestamp):
                update_timestamp = self._time()
            order_update: OrderUpdate = OrderUpdate(
                exchange_order_id=order.exchange_order_id,
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=update_timestamp,
                new_state=OrderState.FAILED,
            )
            # NOTE: This is a failed order, we need to attempt an update within the system
            await self._order_tracker.process_order_update(order_update)
            # NOTE: Unclear which of these is the best to handle this event
            self._order_tracker._trigger_order_completion(order, order_update)
            # NOTE: The order has failed, we need to purge it from the orders available to cancel
            if order.client_order_id in self._order_tracker._cached_orders:
                del self._order_tracker._cached_orders[order.client_order_id]
            self.logger().debug("Attempting to cancel a failed order, unable to do so.")
            return False

        if order.current_state in [OrderState.PENDING_CANCEL, OrderState.PENDING_CREATE]:
            # NOTE: Have a counter and then check, vs checking each time to reduce calls..
            order_update = await self._request_order_status(order, None, False)
            if order_update is not None and order_update.new_state is not None and order_update.new_state != order.current_state:
                await self._order_tracker.process_order_update(order_update)
                if order_update.new_state not in [OrderState.OPEN, OrderState.PARTIALLY_FILLED, OrderState.CREATED]:
                    # We have a new state, however it's invalid and we shouldn't proceeed
                    return False
            else:
                if order_update is None:
                    # Process our not found, and increment
                    await self._order_tracker.process_order_not_found(order.client_order_id)
                    self.logger().debug(f"Process order not found for {order.client_order_id}")
                self.logger().debug(f"Attempting to cancel a pending order {order.client_order_id}, unable to do so.")
                return False

        cancelled = await self._place_cancel(order.client_order_id, order)
        if cancelled:
            update_timestamp = self.current_timestamp
            if update_timestamp is None or math.isnan(update_timestamp):
                update_timestamp = self._time()
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=update_timestamp,
                new_state=(OrderState.CANCELED
                           if self.is_cancel_request_in_exchange_synchronous
                           else OrderState.PENDING_CANCEL),
            )
            self._order_tracker.process_order_update(order_update)
        return cancelled

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        market_id = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        if tracked_order.current_state == OrderState.FAILED:
            self.logger().debug(f"Order {tracked_order.current_state} for {order_id}")
            return False

        if tracked_order.current_state not in [OrderState.OPEN, OrderState.PARTIALLY_FILLED, OrderState.CREATED]:
            self.logger().debug(f"Not canceling order due to state {tracked_order.current_state} for {order_id}")
            return False

        cancel_payload = {
            "order_id": tracked_order.exchange_order_id,
            "market_id": market_id
        }
        transaction = await self._auth.sign_payload(cancel_payload, "order_cancellation")
        data = json.dumps({"tx": str(transaction.decode("utf-8")), "type": "TYPE_SYNC"})
        try:
            response = await self._api_post(
                path_url=CONSTANTS.TRANSACTION_POST_URL,
                full_append=False,
                data=data,
                return_err=True
            )
            if not response.get("success", False) or ("code" in response and response["code"] != 0):
                if "code" in response:
                    if int(response["code"]) == 60:
                        self.logger().debug('Unable to submit cancel to blockchain')
                        raise IOError('Unable to submit cancel to blockchain error code 60')
                    if int(response["code"]) == 89:
                        self._is_connected = False
                        raise IOError(f"Failed to submit transaction as too many transactions have been submitted to the blockchain, disconnecting. {response}")
                    if int(response["code"]) == 70:
                        raise IOError(f"Blockchain failed to process transaction will retry. {response}")
                self.logger().debug(f"Failed transaction submission for cancel of {order_id} with {response}")
                return False

            return True
        except asyncio.CancelledError as cancelled_error:
            self.logger().debug(f"Timeout hit when attempting to cancel order {cancelled_error}")
            return False

    async def _place_order_and_process_update(self, order: InFlightOrder, **kwargs) -> str:
        exchange_order_id, update_timestamp = await self._place_order(
            order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            amount=order.amount,
            trade_type=order.trade_type,
            order_type=order.order_type,
            price=order.price,
            **kwargs,
        )

        # NOTE: Attempt to query the block in the event it has passed through.
        order_update: OrderUpdate = await self._request_order_status(tracked_order=order, is_lost_order=False)
        if order_update is None:
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=update_timestamp,
                # NOTE: Since this is submitted to the blockchain for processing, we've got a pending status until update.
                new_state=OrderState.PENDING_CREATE,
            )

        self._order_tracker.process_order_update(order_update)

        return exchange_order_id

    async def _place_order(
            self,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            trade_type: TradeType,
            order_type: OrderType,
            price: Optional[Decimal] = s_decimal_NaN,
            position_action: PositionAction = PositionAction.NIL,
            **kwargs,
    ) -> Tuple[str, float]:
        # Defaults
        reduce_only: bool = False
        post_only: bool = False
        # Fetch our market for details
        market_id: str = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        m: Market = self._exchange_info.get(market_id)

        # NOTE: See https://docs.vega.xyz/testnet/api/grpc/vega/commands/v1/commands.proto#ordersubmission
        size: int = int(amount * m.quantity_quantum)
        side: int = CONSTANTS.HummingbotToVegaIntSide[trade_type]
        # NOTE: There is an opportunity to change Time In Force
        time_in_force: int = int(VegaTimeInForce.TIME_IN_FORCE_GTC.value)
        _order_type: int = CONSTANTS.HummingbotToVegaIntOrderType[order_type]

        if order_type != OrderType.MARKET:
            price: str = str(int(price * m.price_quantum))
        if order_type == OrderType.LIMIT_MAKER:
            post_only = True
        # NOTE: Market orders only support FOK or IOC
        if order_type == OrderType.MARKET:
            time_in_force: int = int(VegaTimeInForce.TIME_IN_FORCE_IOC.value)
        # NOTE: This is created by hummingbot and added to our order to be able to reference on
        reference_id: str = order_id

        if position_action == PositionAction.CLOSE:
            # NOTE: This is a stub for a reduce only, currently unused (depends on Time In Force)
            # reduce_only = True
            pass

        order_payload = {
            "market_id": market_id,
            "size": size,
            # "price": price,
            "side": side,
            "time_in_force": time_in_force,
            "type": _order_type,
            "reference": reference_id,
            # "post_only": post_only,
            # "reduce_only": reduce_only
            # NOTE: Unused params
            # "pegged_order": None,
            # "expires_at": None,
            # "iceberg_opts": None
        }
        if order_type != OrderType.MARKET:
            order_payload["price"] = price
            order_payload["post_only"] = post_only
            order_payload["reduce_only"] = reduce_only

        # Setup for Sync
        transaction = await self._auth.sign_payload(order_payload, "order_submission")
        data = json.dumps({"tx": str(transaction.decode("utf-8")), "type": "TYPE_SYNC"})

        response = await self._api_post(
            path_url=CONSTANTS.TRANSACTION_POST_URL,
            full_append=False,
            data=data,
            return_err=True
        )

        if not response.get("success", False):
            raise IOError(f"Failed transaction submission for {order_id} with {response}")

        if "code" in response and int(response["code"]) != 0:
            if int(response["code"]) == 89:
                self._is_connected = False
                raise IOError(f"Failed to submit transaction as too many transactions have been submitted to the blockchain, disconnecting. {response}")
            if int(response["code"]) == 70:
                raise IOError(f"Blockchain failed to process transaction will retry. {response}")
            raise IOError(f"Failed transaction submission for {order_id} with {response}.")

        return None, time.time()

    async def _get_client_order_id_from_exchange_order_id(self, exchange_order_id: str):
        if exchange_order_id in self._exchange_order_id_to_hb_order_id:
            return self._exchange_order_id_to_hb_order_id.get(exchange_order_id)

        # wait for exchange order id
        tracked_orders: List[InFlightOrder] = list(self._order_tracker._in_flight_orders.values())
        for order in tracked_orders:
            if order.exchange_order_id is None:
                _hb_order_id_to_exchange_order_id = {v: k for k, v in self._exchange_order_id_to_hb_order_id.items()}
                # NOTE: Attempt to update with our current state information, if not wait for update
                if order.client_order_id in _hb_order_id_to_exchange_order_id.keys():
                    _exchange_order_id = _hb_order_id_to_exchange_order_id[order.client_order_id]
                    order.update_exchange_order_id(_exchange_order_id)
                else:
                    try:
                        await order.get_exchange_order_id()
                    except Exception as e:
                        self.logger().info(f"Unable to locate order {order.client_order_id} on exchange. Pending update from blockchain {e}")
        track_order: List[InFlightOrder] = [o for o in tracked_orders if exchange_order_id == o.exchange_order_id]
        # if this is none request using the exchange order id
        if len(track_order) == 0 or track_order[0] is None:
            order_update: OrderUpdate = await self._request_order_status(exchange_order_id=exchange_order_id, is_lost_order=False)
            # NOTE: Untracked order
            if order_update is None:
                self.logger().debug(f"Received untracked order with exchange order id of {exchange_order_id}")
                return None
            client_order_id = order_update.client_order_id
        else:
            client_order_id = track_order[0].client_order_id

        if client_order_id is not None or client_order_id:
            self._exchange_order_id_to_hb_order_id[exchange_order_id] = client_order_id

        return client_order_id

    async def _process_user_trade(self, trade: Dict[str, Any]):

        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        *** WebSocket ***
        """
        trade_update = await self._get_hb_update_from_trade(trade)
        if trade_update is not None:
            self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[Optional[TradeUpdate]]:
        tracked_order = order
        trade_updates = []
        exchange_order_id = tracked_order.exchange_order_id

        if exchange_order_id is None:
            _hb_order_id_to_exchange_order_id = {v: k for k, v in self._exchange_order_id_to_hb_order_id.items()}
            if tracked_order.client_order_id in _hb_order_id_to_exchange_order_id.keys():
                exchange_order_id = _hb_order_id_to_exchange_order_id[tracked_order.client_order_id]
            else:
                # Override to return if we can't get an exchange order id and the state is failed
                if tracked_order.current_state == OrderState.FAILED:
                    return trade_updates

        try:
            # If exchange order id is STILL none, we'll try to use hummingbot's fetch
            if exchange_order_id is None:
                exchange_order_id = await tracked_order.get_exchange_order_id()
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.TRADE_LIST_URL,
                params={
                    "partyIds": self.vega_perpetual_public_key,
                    "orderIds": exchange_order_id,
                }
            )
            if "trades" not in all_fills_response:
                return trade_updates

            trades_for_order = all_fills_response["trades"]["edges"]
            for trade in trades_for_order:
                _trade = trade.get("node")

                trade_update = await self._get_hb_update_from_trade(_trade)
                if trade_update is not None:
                    trade_updates.append(trade_update)

        except asyncio.TimeoutError:
            self.logger().debug(f"Timeout when waiting for exchange order id got {exchange_order_id}.")

        return trade_updates

    async def _get_hb_update_from_trade(self, trade: Dict[str, Any]) -> TradeUpdate:
        """
        returns a HB TradeUpdate from the vega trade data
        Used in _all_trade_updates_for_order as well as _process_user_trade
        """
        trade_id = trade.get("id")

        # We don't know if we're the buyer or seller, so we need to check
        aggressor = trade.get("aggressor")
        fees = trade.get("buyerFee")
        if "infrastructureFee" in fees and Decimal(fees["infrastructureFee"]) == s_decimal_0:
            fees = trade.get("sellerFee")
        exchange_order_id = trade.get("buyOrder")
        is_taker = True if (aggressor == 1 or aggressor == 'BUY_SIDE') else False

        # we are the seller if our key matches the seller key
        if trade.get("seller") == self.vega_perpetual_public_key:
            fees = trade.get("sellerFee")
            if "infrastructureFee" in fees and Decimal(fees["infrastructureFee"]) == s_decimal_0:
                fees = trade.get("buyerFee")
            exchange_order_id = trade.get("sellOrder")
            is_taker = True if (aggressor == 2 or aggressor == 'SELL_SIDE') else False

        # Get our client id and tracked_order from it
        client_order_id = await self._get_client_order_id_from_exchange_order_id(exchange_order_id)

        # NOTE: untracked order processed
        if client_order_id is None:
            return None

        tracked_order: InFlightOrder = self._order_tracker.all_fillable_orders.get(client_order_id, None)
        if tracked_order is None:
            self.logger().debug(f"Ignoring trade message with id {id}: not in in_flight_orders.")
            return None

        m: Market = self._exchange_info.get(trade["marketId"])
        a: Asset = self._assets_by_id.get(m.quote_asset_id)
        fee_asset = tracked_order.quote_asset
        total_fees_paid = web_utils.calculate_fees(fees, a.quantum, is_taker)

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=tracked_order.position,
            flat_fees=[TokenAmount(amount=total_fees_paid, token=fee_asset)]
        )

        _size_traded = Decimal(trade["size"]) / m.quantity_quantum
        _base_price_traded = Decimal(trade["price"]) / m.price_quantum

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=web_utils.hb_time_from_vega(trade.get("timestamp")),
            fill_price=_base_price_traded,
            fill_base_amount=_size_traded,
            fill_quote_amount=_size_traded * _base_price_traded,
            fee=fee,
            is_taker=is_taker,
        )

        return trade_update

    async def _request_order_status(self, tracked_order: Optional[InFlightOrder] = None, exchange_order_id: Optional[str] = None, is_lost_order: Optional[bool] = True) -> Optional[OrderUpdate]:
        if tracked_order:
            exchange_order_id = tracked_order.exchange_order_id

        if exchange_order_id is None:
            reference = tracked_order.client_order_id
            params = {
                "filter.reference": reference
            }
            orders_data = await self._api_get(
                path_url=CONSTANTS.ORDER_LIST_URL,
                params=params,
                return_err=True
            )
        else:
            orders_data = await self._api_get(
                path_url=f"{CONSTANTS.ORDER_URL}/{exchange_order_id}",
                return_err=True
            )

        if "code" in orders_data and orders_data.get("code", 0) != 0:
            if orders_data.get("code") == 70:
                self.logger().debug(f"Order not found {orders_data}")
                raise IOError("Order not found")
            if tracked_order is not None:
                self.logger().debug(f"unable to locate order {orders_data.get('message')}")
                raise IOError("Order not found")
            else:
                self.logger().debug(f"unable to locate order in our inflight orders {orders_data.get('message')}")

        # Multiple orders
        if "orders" in orders_data:
            for order in orders_data["orders"]["edges"]:
                _order = order.get("node", None)
                if _order is not None:
                    # NOTE: We process the order data into an order update and return the order update
                    return await self._process_user_order(order=_order, is_rest=True)
        # Single order
        elif "order" in orders_data:
            _order = orders_data["order"]
            if _order is not None:
                return await self._process_user_order(order=_order, is_rest=True)
        if not is_lost_order:
            return None
        else:
            raise IOError("Order not found")

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Vega. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Wait for new messages from _user_stream_tracker.user_stream queue and processes them according to their
        message channels. The respective UserStreamDataSource queues these messages.
        """
        async for event_message in self._iter_user_event_queue():
            if "error" in event_message:
                self.logger().error("Unexpected data in user stream")
                return
            if "result" not in event_message:
                self.logger().error("Unexpected data in user stream")
                return

            try:
                if "snapshot" in event_message["result"]:
                    data = event_message["result"]["snapshot"]
                elif "updates" in event_message["result"]:
                    data = event_message["result"]["updates"]
                elif "trades" in event_message["result"]:
                    data = event_message["result"]

                else:
                    # NOTE: issue with unknown format
                    return

                match event_message["channel_id"]:
                    case "orders":
                        if "orders" in data:
                            for order in data["orders"]:
                                await self._process_user_order(order)
                    case "positions":
                        if "positions" in data:
                            for position in data["positions"]:
                                await self._process_user_position(position)
                    case "trades":
                        for trade in data["trades"]:
                            await self._process_user_trade(trade)
                    case "account":
                        for account in data["accounts"]:
                            await self._process_user_account(account)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)
                await self._sleep(5.0)

    async def _process_user_order(self, order: Dict[str, Any], is_rest: bool = False) -> Optional[OrderUpdate]:
        """
        Updates in-flight order and triggers cancelation or failure event if needed.

        :param order: The order response from web socket API

        """

        exchange_order_id = order.get("id")
        client_order_id = order.get("reference")
        tracked_order: Optional[InFlightOrder] = self._order_tracker.all_fillable_orders.get(client_order_id, None)
        order_status = order.get("status")
        mapped_status = CONSTANTS.VegaIntOrderStatusToHummingbot[order_status] if isinstance(order_status, int) else CONSTANTS.VegaStringOrderStatusToHummingbot[order_status]
        if not tracked_order:
            if mapped_status not in [OrderState.CANCELED, OrderState.FAILED]:
                self.logger().debug(f"Ignoring order message with id {exchange_order_id}: not in our orders. Client ID: {client_order_id}")
            return None

        _hb_state = mapped_status
        misc_updates: Optional[Dict] = None
        if "reason" in order and _hb_state == OrderState.FAILED:
            misc_updates = {
                # Check to see if we have string or integer
                "error": order["reason"] if len(order["reason"]) > 6 else CONSTANTS.VegaOrderError[order["reason"]]
            }

        # Updates the exchange_order_id ONLY here
        tracked_order.update_exchange_order_id(exchange_order_id)

        # Mapping for order_id provider by Vega to the client_oid for easy lookup / reference
        if exchange_order_id not in self._exchange_order_id_to_hb_order_id:
            self._exchange_order_id_to_hb_order_id[exchange_order_id] = client_order_id

        updated_at = web_utils.hb_time_from_vega(order["createdAt"] if "createdAt" in order else order["updatedAt"])
        order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_at,
            new_state=_hb_state,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            misc_updates=misc_updates
        )

        if is_rest:
            return order_update

        self._order_tracker.process_order_update(order_update=order_update)

    async def _process_user_position(self, position: Dict[str, Any]):
        """
        Updates position from a server position event message.

        This is called both from the websocket as well as the rest call

        :param position: A single position event message payload
        """
        marketId = position["marketId"]
        m: Market = self._exchange_info.get(marketId)
        if m is None or m.hb_trading_pair is None:
            self.logger().debug(f"Ignoring position message with id {marketId}: not in our markets.")
            return

        open_volume = Decimal(position.get("openVolume", "0.0"))
        position_side = PositionSide.LONG if open_volume > s_decimal_0 else PositionSide.SHORT
        amount = open_volume / m.quantity_quantum
        unrealized_pnl = Decimal(position.get("unrealisedPnl")) / m.price_quantum
        entry_price = Decimal(position["averageEntryPrice"]) / m.price_quantum

        # Calculate position leverage
        leverage = Decimal("1.0")
        try:
            if m.hb_quote_name in self._account_balances:
                # NOTE: Abs used here as position can be negative (short)
                position_calculated_leverage = (entry_price * abs(amount)) / self._account_balances[m.hb_quote_name]
                # NOTE: Ensures leverage is always one...
                leverage = round(max(leverage, position_calculated_leverage), 1)
        except Exception as e:
            self.logger().debug(f"Issue calculating leverage for position: {e}")

        _position: Position = self._perpetual_trading.get_position(m.hb_trading_pair, position_side)
        pos_key = self._perpetual_trading.position_key(m.hb_trading_pair, position_side)
        if _position is None:
            if amount == s_decimal_0:
                # do not add positions without amount
                return

            # add this position
            _position = Position(
                trading_pair=m.hb_trading_pair,
                position_side=position_side,
                unrealized_pnl=unrealized_pnl,
                entry_price=entry_price,
                amount=amount,
                leverage=leverage
            )
            self._perpetual_trading.set_position(pos_key, _position)
            return

        # we have a position, so update or remove
        pos_key = self._perpetual_trading.position_key(m.hb_trading_pair, position_side)
        if amount == s_decimal_0:
            # no amount means we have closed this position
            self._perpetual_trading.remove_position(pos_key)
        else:
            _position.update_position(leverage=leverage,
                                      unrealized_pnl=unrealized_pnl,
                                      entry_price=entry_price,
                                      position_side=position_side,
                                      amount=amount)

    async def _process_user_account(self, account: Dict[str, Any]):
        """
        _process_user_account handles each account from the account ws stream
        """

        a: Asset = self._assets_by_id.get(account.get("asset"))
        balance = Decimal(account.get("balance"))

        account_type = web_utils.get_account_type(account.get("type"))

        if account_type and (account_type in ["ACCOUNT_TYPE_GENERAL", "ACCOUNT_TYPE_MARGIN"]):
            locked_balance = s_decimal_0
            available_balance = s_decimal_0
            if account_type == "ACCOUNT_TYPE_MARGIN":
                self._locked_balances[a.id] = balance / a.quantum
            if account_type == "ACCOUNT_TYPE_GENERAL":
                self._account_available_balances[a.hb_name] = balance / a.quantum

            # NOTE: Case 1 - we actually do have a locked balance for this ASSET ID let's use that instead of 0.
            # This case is interesting in that if you don't hit the ACCOUNT_TYPE_MARGIN FIRST, then you may not
            # have this value set
            if a.id in self._locked_balances:
                locked_balance = self._locked_balances[a.id]
            # NOTE: Case 2 - we actually do have an available balance for this ASSET NAME let's use that instead
            # of 0. This case again like the above is if you don't hit ACCOUNT_TYPE_GENERAL FIRST, then you may
            # not have this value set.
            if a.hb_name in self._account_available_balances:
                available_balance = self._account_available_balances[a.hb_name]

            self._account_balances[a.hb_name] = locked_balance + available_balance

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange
        """
        return_val: list = []
        m: Market
        for key, m in exchange_info_dict.items():
            return_val.append(
                TradingRule(
                    m.hb_trading_pair,
                    min_order_size=m.min_order_size,
                    min_price_increment=m.min_price_increment,
                    min_base_amount_increment=m.min_base_amount_increment,
                    min_notional_size=m.min_notional,
                    buy_order_collateral_token=m.buy_collateral_token.hb_name,
                    sell_order_collateral_token=m.sell_collateral_token.hb_name,
                )
            )

        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        # This is called for us to do what ever we want to do with the exchange info
        # after the web request
        mapping = bidict()

        m: Market
        for key, m in exchange_info.items():

            if m.hb_trading_pair in mapping.inverse:
                continue
            else:
                mapping[m.id] = m.hb_trading_pair

        if len(mapping) == 0:
            raise ValueError("No symbols found for exchange.")

        # this sets the mapping up in the base class
        # so we can use the default implementation of the trading_pair_associated_to_exchange_symbol and vice versa
        self._set_trading_pair_symbol_map(mapping)

    #  def _resolve_trading_pair_symbols_duplicate(mapping: bidict, m: Market):
    # NOTE: This is a stub for a duplicate trading pair
    #     mapping[m.id] = m.hb_trading_pair

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        market_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        m: Market = self._exchange_info.get(market_id)
        response = await self._api_get(
            path_url=f"{CONSTANTS.TICKER_PRICE_URL}/{market_id}/{CONSTANTS.RECENT_SUFFIX}"
        )
        price = s_decimal_0
        if "marketData" in response:
            price = float(Decimal(response["marketData"].get("lastTradedPrice")) / m.price_quantum)
        return price

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        if not self.authenticator.is_valid:
            raise IOError('Invalid key and mnemonic, check values and try again')
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        await self._populate_symbols()
        await self._update_positions()
        params = {
            "filter.partyIds": self.vega_perpetual_public_key
        }

        account_info = await self._api_get(path_url=CONSTANTS.ACCOUNT_INFO_URL,
                                           params=params,
                                           )
        _assets = account_info.get("accounts")
        for asset in _assets["edges"]:
            _asset = asset["node"]
            asset_id = _asset["asset"]

            a: Asset = self._assets_by_id.get(asset_id)
            asset_name = a.hb_name
            await self._process_user_account(_asset)
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        if not self._exchange_info:
            await self._populate_exchange_info()

        market_ids = []

        for trading_pair in self.trading_pairs:
            market_id = self._market_id_from_hb_pair(trading_pair=trading_pair)
            market_ids.append(market_id)

        params = {
            "filter.partyIds": self.vega_perpetual_public_key,
            "filter.marketIds": market_ids,
        }

        positions = await self._api_get(path_url=CONSTANTS.POSITION_LIST_URL,
                                        params=params,
                                        return_err=True
                                        )
        _positions = positions.get("positions", None)

        if _positions is not None:
            for position in _positions["edges"]:
                _position = position["node"]
                await self._process_user_position(_position)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        # NOTE: This is default to ONEWAY as there is nothing available on current version of Vega
        return self._position_mode

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        # NOTE: There is no setting to add for markets on current version of Vega
        msg = ""
        success = True
        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        success = True
        msg = ""
        market_id: str = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        m: Market = self._exchange_info.get(market_id)

        risk_factor_data = await self._api_get(
            path_url=f"{CONSTANTS.MARKET_DATA_URL}/{market_id}/risk/factors",
            return_err=True
        )

        if "riskFactor" in risk_factor_data and m.linear_slippage_factor is not None:
            risk_factors = risk_factor_data["riskFactor"]
            max_leverage = int(Decimal("1") / (max(Decimal(risk_factors["long"]), Decimal(risk_factors["short"])) + m.linear_slippage_factor))
            if leverage > max_leverage:
                self._perpetual_trading.set_leverage(trading_pair=trading_pair, leverage=max_leverage)
                self.logger().warning(f"Exceeded max leverage allowed. Leverage for {trading_pair} has been reduced to {max_leverage}")
            else:
                self._perpetual_trading.set_leverage(trading_pair=trading_pair, leverage=leverage)
                self.logger().info(f"Leverage for {trading_pair} successfully set to {leverage}.")
        else:
            self._perpetual_trading.set_leverage(trading_pair=trading_pair, leverage=1)
            self.logger().warning(f"Missing risk details. Leverage for {trading_pair} has been reduced to {1}")
        return success, msg

    async def _execute_set_leverage(self, trading_pair: str, leverage: int):
        try:
            await self._set_trading_pair_leverage(trading_pair, leverage)
        except Exception:
            self.logger().network(f"Error setting leverage {leverage} for {trading_pair}")

    async def _process_funding_payments(self, market_id: str, funding_payments_data: Optional[Dict[str, Any]]) -> Tuple[int, Decimal, Decimal]:
        """
        Function filters through the entire collection of funding payments for only the trading pair, if exits
        returns the timestamp of the payment and the rate.
        """
        # NOTE: These are default to ignore funding payment.
        timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")

        if "fundingPayments" not in funding_payments_data:
            return timestamp, funding_rate, payment

        funding_payments = funding_payments_data["fundingPayments"]["edges"]

        most_recent_funding_payment = {
            "timestamp": timestamp,
            "funding_rate": funding_rate,
            "payment": payment,
            "funding_period_sequence_id": 0
        }
        for funding_payment in funding_payments:
            funding_payment_data = funding_payment["node"]
            _market_id = funding_payment_data.get("marketId")
            if _market_id != market_id:
                continue

            funding_period_sequence_id = funding_payment_data.get("fundingPeriodSeq")
            m: Market = self._exchange_info.get(market_id)
            a: Asset = self._assets_by_id.get(m.quote_asset_id)
            time_paid = funding_payment_data.get("timestamp")
            quanity_paid = funding_payment_data.get("amount")

            payment = Decimal(quanity_paid) / a.quantum
            timestamp = web_utils.hb_time_from_vega(time_paid)

            if most_recent_funding_payment["timestamp"] < timestamp:
                most_recent_funding_payment = {
                    "timestamp": timestamp,
                    "payment": payment,
                    "funding_period_sequence_id": funding_period_sequence_id,
                    "funding_rate": funding_rate
                }
        timestamp = most_recent_funding_payment["timestamp"]
        payment = most_recent_funding_payment["payment"]
        funding_period_sequence_id = most_recent_funding_payment["funding_period_sequence_id"]

        if timestamp != 0:
            current_time = time.time_ns()
            look_back_time = self.funding_fee_poll_interval * 1e+9 * 2

            # Fetches 2 periods back in nanoseconds
            historical_funding_rates_data = await self._api_get(
                path_url=f"{CONSTANTS.FUNDING_RATE_URL}/{market_id}",
                params={"dateRange.startTimestamp": int(current_time - look_back_time)},
                return_err=True
            )
            if "code" in historical_funding_rates_data:
                self.logger().debug(f"Error fetching historical funding rates {historical_funding_rates_data}")

            if "fundingPeriods" in historical_funding_rates_data:
                historical_funding_rates = historical_funding_rates_data["fundingPeriods"]["edges"]
                for historical_funding_rate in historical_funding_rates:
                    historical_funding_rate_data = historical_funding_rate.get("node")
                    funding_rate = historical_funding_rate_data.get("fundingRate")
                    rate_sequence_id = historical_funding_rate_data.get("seq")
                    if funding_period_sequence_id == rate_sequence_id:
                        most_recent_funding_payment["funding_rate"] = Decimal(funding_rate)
                        break
        funding_rate = most_recent_funding_payment["funding_rate"]

        return timestamp, funding_rate, payment

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        """
        Returns a tuple of the latest funding payment timestamp, funding rate, and payment amount.
        If no payment exists, return (0, -1, -1)
        """
        # NOTE: https://docs.vega.xyz/testnet/api/rest/data-v2/trading-data-service-list-funding-payments
        params = {
            "partyId": self.vega_perpetual_public_key,
        }
        funding_payments = await self._api_request(
            path_url=CONSTANTS.FUNDING_PAYMENTS_URL,
            params=params
        )
        trading_pair_market_id = self._market_id_from_hb_pair(trading_pair=trading_pair)

        timestamp, funding_rate, payment = await self._process_funding_payments(market_id=trading_pair_market_id, funding_payments_data=funding_payments)

        return timestamp, funding_rate, payment

    async def _map_exchange_info(self, exchange_info: Dict[str, Any]) -> Any:
        if len(exchange_info["markets"]["edges"]) == 0:
            return self._exchange_info

        _exchange_info = {}
        # reset our maps
        self._id_by_hb_pair = {}

        await self._populate_symbols()
        for symbol_data in exchange_info["markets"]["edges"]:

            # full node with all the info
            node = symbol_data["node"]

            if node["state"] != "STATE_ACTIVE":
                continue

            # tradableInstrument contains the instrument and the margininfo etc
            tradable_inst = node["tradableInstrument"]

            # the actual instrument
            instrument = tradable_inst["instrument"]

            if "perpetual" not in instrument:
                # we only care about perpetual markets
                continue

            m = Market()
            # our trading pair in human readable format
            m.name = instrument["name"]
            m.symbol = instrument["code"]

            # the symbol id (number)
            m.id = node["id"]
            m.status = node["state"]

            m.quote: Asset = self._assets_by_id.get(instrument["perpetual"]["settlementAsset"])

            m.quote_asset_id = instrument["perpetual"]["settlementAsset"]
            m.funding_fee_interval = int(instrument["perpetual"]["dataSourceSpecForSettlementSchedule"]["data"]["internal"]["timeTrigger"]["triggers"][0]["every"])

            linear_slippage_factor = node.get("linearSlippageFactor", None)
            m.linear_slippage_factor = Decimal(linear_slippage_factor) if linear_slippage_factor is not None else linear_slippage_factor

            decimal_places = Decimal(node["decimalPlaces"])
            position_decimal_places = Decimal(node["positionDecimalPlaces"])

            m.min_order_size = Decimal(1 / 10 ** position_decimal_places)
            m.min_price_increment = Decimal(1 / 10 ** decimal_places)
            m.min_base_amount_increment = Decimal(1 / 10 ** position_decimal_places)
            # NOTE: Used for rounding automagically
            m.max_price_significant_digits = decimal_places
            m.min_notional = Decimal(1 / 10 ** position_decimal_places) * Decimal(1 / 10 ** decimal_places)
            # NOTE: One general account can be utilised by every market with that settlement asset
            m.buy_collateral_token = m.quote
            m.sell_collateral_token = m.quote

            market_fees = node["fees"]["factors"]
            m.maker_fee = market_fees["makerFee"]
            m.liquidity_fee = market_fees["liquidityFee"]
            m.infrastructure_fee = market_fees["infrastructureFee"]

            m.price_quantum = Decimal(10 ** decimal_places)
            m.quantity_quantum = Decimal(10 ** position_decimal_places)

            # get our base and quote symbol names. These have the format of base:BTC and quote:USD
            # NOTE: some of these have ticker: like tesla.
            # NOTE: Overriding this with the instrument code not the base, even if the instrument is composed with an asset,
            # technically an instrument is a synthetic asset (outside of some options where you actually do settle with receipt
            # of asset)
            m.base_name = m.symbol
            # NOTE: This cleans up any parsing issues from Hummingbot, but may lead to a confusing result if metadata is not included
            m.hb_base_name = m.symbol.replace("-", "").replace("/", "").replace(".", "").upper()

            # if "metadata" in instrument:
            #     if "tags" in instrument["metadata"]:
            #         if len(instrument["metadata"]["tags"]) > 0:
            #             m.base_name = self._get_base(instrument["metadata"]["tags"])
            #             m.hb_base_name = m.base_name.upper()

            m.quote_name = m.quote.symbol
            m.hb_quote_name = m.quote.hb_name.upper()
            if not m.base_name or not m.quote_name:
                self.logger().warning(f"Skipping Market {m.name} as critical data is missing")
                continue

            m.hb_trading_pair = combine_to_hb_trading_pair(m.hb_base_name, m.hb_quote_name)

            _exchange_info[m.id] = m
            if m.hb_trading_pair in self._id_by_hb_pair:
                # if we have a duplicate, make our trading pair be the id-quote name.
                # not user friendly, but?
                m.hb_trading_pair = combine_to_hb_trading_pair(m.id, m.hb_quote_name)

            self._id_by_hb_pair[m.hb_trading_pair] = m.id

        return _exchange_info

    def _get_base(self, tags: List[str]) -> str:
        for tag in tags:
            if "base:" in tag:
                return tag.replace("base:", "")
            # NOTE: This is for actual stocks.
            elif "ticker:" in tag:
                return tag.replace("ticker:", "")
        return ""

    def _get_quote(self, tags: List[str]) -> str:
        for tag in tags:
            if "quote:" in tag:
                return tag.replace("quote:", "")
        return ""

    async def _make_trading_rules_request(self) -> Any:
        # Assess if we have exchange info already, if not request it
        if not self._exchange_info:
            exchange_info = await self._populate_exchange_info()
            self._exchange_info = exchange_info
        return self._exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        # Assess if we have exchange info already, if not request it
        if not self._exchange_info:
            exchange_info = await self._populate_exchange_info()
            self._exchange_info = exchange_info
        return self._exchange_info

    async def _populate_exchange_info(self):
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path)

        self._exchange_info = await self._map_exchange_info(exchange_info=exchange_info)
        return self._exchange_info

    async def _populate_symbols(self):

        # dont repopulate
        if len(self._assets_by_id) > 0:
            return

        # get all the symbols from the exchange
        # assets -> edges
        symbol_info = await self._api_get(path_url=self.symbols_request_path)

        symbol_info = symbol_info["assets"]
        for symbol in symbol_info["edges"]:
            node = symbol["node"]
            enabled_status = node.get("status")

            if enabled_status != "STATUS_ENABLED":
                continue

            name = node["details"]["name"]
            symbol = node["details"]["symbol"]

            hb_name = symbol.replace("-", "")
            # NOTE: HB expects all name's to be upper case
            hb_name = hb_name.upper()
            quantum = Decimal(10 ** Decimal(node["details"]["decimals"]))
            asset = Asset(id=node["id"], name=name, symbol=symbol, hb_name=hb_name, quantum=quantum)

            self._assets_by_id[node["id"]] = asset

    async def _api_request(
            self,
            path_url,
            full_append: bool = True,  # false for raw requests
            is_block_explorer: bool = False,
            method: RESTMethod = RESTMethod.GET,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            is_auth_required: bool = False,
            return_err: bool = False,
            api_version: str = CONSTANTS.API_VERSION,
            limit_id: Optional[str] = None,
            **kwargs,
    ) -> Dict[str, Any]:
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        # If we have yet to start network, process it and accept just the base connection.
        if self._best_connection_endpoint == "":
            # This handles the initial request without lagging the entire bot.
            self._best_connection_endpoint = CONSTANTS.PERPETUAL_BASE_URL if self._domain == "vega_perpetual" else CONSTANTS.TESTNET_BASE_URL
        url = web_utils._rest_url(path_url, self._best_connection_endpoint, api_version)
        if not full_append:
            # we want to use the short url which doesnt have api and version
            url = web_utils._short_url(path_url, self._best_connection_endpoint)
        if is_block_explorer:
            url = web_utils.explorer_url(path_url, self.domain)

        try:
            async with self._throttler.execute_task(limit_id=CONSTANTS.ALL_URLS):
                request = RESTRequest(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    is_auth_required=is_auth_required,
                    throttler_limit_id=CONSTANTS.ALL_URLS
                )
                response = await rest_assistant.call(request=request)

                if not self._has_updated_throttler:
                    rate_limit = int(response.headers.get("Ratelimit-Limit"))
                    rate_limit_time_interval = int(response.headers.get("Ratelimit-Reset"))
                    await self._update_throttler(rate_limit, rate_limit_time_interval)

                if response.status != 200:
                    if return_err:
                        error_response = await response.json()
                        return error_response
                    else:
                        error_response = await response.text()
                        raise IOError(f"Error executing request {method.name} {path_url}. "
                                      f"HTTP status is {response.status}. "
                                      f"Error: {error_response}")
                self._is_connected = True
                return await response.json()
        except IOError as request_exception:
            raise request_exception
        except aiohttp.ClientConnectionError as connection_exception:
            self.logger().warning(connection_exception)
            self._is_connected = False
            raise connection_exception
        except Exception as e:
            self._is_connected = False
            raise e

    def _market_id_from_hb_pair(self, trading_pair: str) -> str:
        return self._id_by_hb_pair.get(trading_pair, "")

    def _do_housekeeping(self):
        """
        Clean up our maps and other data that we may be holding on to
        """

        map_copy = self._exchange_order_id_to_hb_order_id.copy()
        for exchange_id, client_id in map_copy.items():
            if client_id not in self._order_tracker.all_fillable_orders:
                # do our cleanup
                del self._exchange_order_id_to_hb_order_id[exchange_id]
