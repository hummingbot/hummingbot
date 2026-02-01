import asyncio
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.weex import weex_constants as CONSTANTS, weex_utils, weex_web_utils as web_utils
from hummingbot.connector.exchange.weex.weex_api_order_book_data_source import WeexAPIOrderBookDataSource
from hummingbot.connector.exchange.weex.weex_api_user_stream_data_source import WeexAPIUserStreamDataSource
from hummingbot.connector.exchange.weex.weex_auth import WeexAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class WeexExchange(ExchangePyBase):
    # WEEX has VERY strict rate limits with dual-tier enforcement:
    # - 500 weight per 10 seconds (documented)
    # - ~50 weight per 1 second (burst limit, discovered in testing)
    #
    # CRITICAL: With 8 orders, parallel REST polling creates bursts:
    #   8 orders × (5 weight fills + 2 weight status) = 56 weight burst → EXCEEDS 50/second limit
    #
    # SOLUTION: Rely on WebSockets for real-time updates, disable REST polling
    # WebSocket channels (orders, fills, account) provide instant updates with zero API weight
    UPDATE_ORDER_STATUS_MIN_INTERVAL = float('inf')  # DISABLED - use WebSocket order updates only
    SHORT_POLL_INTERVAL = 300.0  # Balance reconciliation every 5 minutes (fallback only)
    LONG_POLL_INTERVAL = 300.0  # Keep at 5 minutes
    DISABLE_REST_ORDER_POLLING = True

    web_utils = web_utils

    def __init__(self,
                 weex_api_key: str,
                 weex_api_secret: str,
                 weex_api_passphrase: str = "",
                 balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
                 rate_limits_share_pct: Decimal = Decimal("100"),
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = weex_api_key
        self.secret_key = weex_api_secret
        self.api_passphrase = weex_api_passphrase
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_weex_timestamp = 1.0
        super().__init__(balance_asset_limit, rate_limits_share_pct)
        self._disable_rest_order_polling = self._get_disable_rest_order_polling()
        # DEBUG: Log initialization
        self.logger().info(f"[WEEX_DEBUG] WeexExchange.__init__() completed. trading_pairs={trading_pairs}, trading_required={trading_required}")

    @classmethod
    def _get_disable_rest_order_polling(cls) -> bool:
        env_value = os.getenv("WEEX_DISABLE_REST_ORDER_POLLING")
        if env_value is None:
            return cls.DISABLE_REST_ORDER_POLLING
        return env_value.strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def weex_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(weex_type: str) -> OrderType:
        return OrderType[weex_type]

    @property
    def authenticator(self):
        return WeexAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            passphrase=self.api_passphrase,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "weex"
        else:
            return f"weex_{self._domain}"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.TRADING_PAIRS_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_user_stream_initialized(self):
        """
        Override to handle WEEX's behavior: private WebSocket doesn't send unsolicited messages.
        If the user stream tracker is running and we have a connected websocket, consider it initialized.
        """
        if not self.is_trading_required:
            return True
        # Check if user stream tracker task exists and is not done (still running)
        if self._user_stream_tracker_task is not None and not self._user_stream_tracker_task.done():
            return True
        return False

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKERS_PATH_URL)
        return pairs_prices.get("data", []) if isinstance(pairs_prices, dict) else pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception).lower()
        return (
            "timestamp" in error_description
            or "access-timestamp" in error_description
            or "time" in error_description and "invalid" in error_description
        )

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        msg = str(status_update_exception).lower()
        return "order not found" in msg or "order does not exist" in msg or "order not exist" in msg

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        msg = str(cancelation_exception).lower()
        return "order not found" in msg or "order does not exist" in msg or "order not exist" in msg

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            domain=self._domain,   # harmless if absorbed
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return WeexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return WeexAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
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
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        order_result = None
        amount_str = f"{amount:f}"
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        order_type_str = "limit" if order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER) else "market"
        api_params = {
            "symbol": symbol,
            "side": side_str,
            "orderType": order_type_str,
            "quantity": amount_str,
            "clientOrderId": order_id,
        }
        if order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER):
            api_params["price"] = f"{price:f}"
            api_params["force"] = (
                CONSTANTS.FORCE_POST_ONLY if order_type is OrderType.LIMIT_MAKER else CONSTANTS.FORCE_NORMAL
            )

        try:
            order_result = await self._api_post(
                path_url=CONSTANTS.CREATE_ORDER_PATH_URL,
                data=api_params,
                is_auth_required=True,
                limit_id=CONSTANTS.CREATE_ORDER_LIMIT_ID)
            order_data = order_result.get("data", {}) if isinstance(order_result, dict) else {}
            o_id = str(order_data.get("orderId"))
            transact_time = float(order_result.get("requestTime", self._time_synchronizer.time() * 1e3)) * 1e-3
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = ("status is 503" in error_description
                                    and "Unknown error, please check your request or try again later." in error_description)
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = self._time_synchronizer.time()
            else:
                raise
        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "symbol": symbol,
            "clientOrderId": order_id,
        }
        if tracked_order.exchange_order_id is not None:
            api_params["orderId"] = tracked_order.exchange_order_id
        cancel_response = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.CANCEL_ORDER_LIMIT_ID)

        cancel_data = cancel_response.get("data", {}) if isinstance(cancel_response, dict) else {}
        if cancel_data.get("result") is True:
            return True
        return False

    def batch_order_create(self, orders_to_create: List[Union[MarketOrder, LimitOrder]]) -> List[Union[MarketOrder, LimitOrder]]:
        """
        Issues a batch order creation as a single API request. This is significantly more efficient
        than individual order placement for WEEX due to rate limiting:
        - Individual: 8 orders × 5 weight = 40 weight
        - Batch: 1 request × 10 weight = 10 weight (75% reduction)

        Note: WEEX batch orders must all be for the same symbol.

        :param orders_to_create: A list of LimitOrder or MarketOrder objects. The order IDs can be blank.
        :returns: A list of the same order objects with generated client order IDs.
        """
        orders_with_ids_to_create = []
        for order in orders_to_create:
            client_order_id = get_new_client_order_id(
                is_buy=order.is_buy,
                trading_pair=order.trading_pair,
                hbot_order_id_prefix=self.client_order_id_prefix,
                max_id_len=self.client_order_id_max_length,
            )
            orders_with_ids_to_create.append(order.copy_with_id(client_order_id=client_order_id))
        safe_ensure_future(self._execute_batch_order_create(orders_to_create=orders_with_ids_to_create))
        return orders_with_ids_to_create

    async def _execute_batch_order_create(self, orders_to_create: List[Union[MarketOrder, LimitOrder]]):
        """
        Execute batch order creation - validate orders, make API call, process results.
        Per WEEX API: POST /api/v2/trade/batch-orders with {"symbol": "...", "orderList": [...]}
        Response: {"data": {"resultList": [{"orderId": ..., "clientOrderId": ...}]}}
        """
        if len(orders_to_create) == 0:
            return

        # Track orders first (using standard start_tracking_order)
        inflight_orders_to_create = []
        for order in orders_to_create:
            trading_rule = self._trading_rules[order.trading_pair]
            quantized_price = self.quantize_order_price(order.trading_pair, order.price)
            quantized_amount = self.quantize_order_amount(order.trading_pair, order.quantity)
            order_type_enum = order.order_type()

            # Validate order before tracking
            if order_type_enum not in self.supported_order_types():
                self.logger().error(f"{order_type_enum} is not in the list of supported order types")
                self._update_order_after_failure(
                    order_id=order.client_order_id,
                    trading_pair=order.trading_pair,
                    exception=ValueError(f"{order_type_enum} is not in the list of supported order types"))
                continue
            elif quantized_amount < trading_rule.min_order_size:
                self._update_order_after_failure(
                    order_id=order.client_order_id,
                    trading_pair=order.trading_pair,
                    exception=ValueError(f"Order amount {order.quantity} is lower than minimum order size {trading_rule.min_order_size}"))
                continue
            elif quantized_price * quantized_amount < trading_rule.min_notional_size:
                self._update_order_after_failure(
                    order_id=order.client_order_id,
                    trading_pair=order.trading_pair,
                    exception=ValueError(f"Order notional {quantized_price * quantized_amount} is lower than minimum notional size {trading_rule.min_notional_size}"))
                continue

            # Start tracking the order
            self.start_tracking_order(
                order_id=order.client_order_id,
                exchange_order_id=None,
                trading_pair=order.trading_pair,
                order_type=order_type_enum,
                trade_type=TradeType.BUY if order.is_buy else TradeType.SELL,
                price=quantized_price,
                amount=quantized_amount,
            )
            inflight_order = self._order_tracker.active_orders[order.client_order_id]
            inflight_orders_to_create.append(inflight_order)

        if len(inflight_orders_to_create) == 0:
            return

        # Group orders by symbol (WEEX batch orders must be for single symbol)
        orders_by_symbol = {}
        for order in inflight_orders_to_create:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order)

        # Process each symbol separately
        for symbol, symbol_orders in orders_by_symbol.items():
            # Build batch request payload
            order_list = []
            for order in symbol_orders:
                order_type_str = "limit" if order.order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER) else "market"
                side_str = CONSTANTS.SIDE_BUY if order.trade_type == TradeType.BUY else CONSTANTS.SIDE_SELL

                order_params = {
                    "side": side_str,
                    "orderType": order_type_str,
                    "quantity": f"{order.amount:f}",
                    "clientOrderId": order.client_order_id,
                }

                if order.order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER):
                    order_params["price"] = f"{order.price:f}"
                    order_params["force"] = (
                        CONSTANTS.FORCE_POST_ONLY if order.order_type is OrderType.LIMIT_MAKER
                        else CONSTANTS.FORCE_NORMAL
                    )

                order_list.append(order_params)

            # Make single batch API call per symbol
            try:
                batch_result = await self._api_post(
                    path_url=CONSTANTS.BATCH_ORDERS_PATH_URL,
                    data={"symbol": symbol, "orderList": order_list},
                    is_auth_required=True,
                    limit_id=CONSTANTS.BATCH_ORDERS_LIMIT_ID
                )

                # Process results - WEEX returns {"data": {"resultList": [...]}}
                result_data = batch_result.get("data", {}) if isinstance(batch_result, dict) else {}
                result_list = result_data.get("resultList", [])

                # Map results back to orders by clientOrderId
                client_order_id_to_order = {order.client_order_id: order for order in symbol_orders}

                # Process results (all successful if in resultList)
                for result_item in result_list:
                    client_order_id = result_item.get("clientOrderId")
                    if client_order_id in client_order_id_to_order:
                        order = client_order_id_to_order[client_order_id]
                        exchange_order_id = str(result_item.get("orderId", ""))
                        # Create OrderUpdate to mark order as OPEN with exchange ID
                        order_update = OrderUpdate(
                            client_order_id=client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=order.trading_pair,
                            update_timestamp=self.current_timestamp,
                            new_state=OrderState.OPEN,
                        )
                        self._order_tracker.process_order_update(order_update)
                        self.logger().info(
                            f"Batch order created successfully: {client_order_id} "
                            f"(exchange ID: {exchange_order_id})"
                        )

                # Check if any orders weren't in the result (failed)
                result_client_ids = {item.get("clientOrderId") for item in result_list}
                for client_order_id, order in client_order_id_to_order.items():
                    if client_order_id not in result_client_ids:
                        self._update_order_after_failure(
                            order_id=client_order_id,
                            trading_pair=order.trading_pair,
                            exception=IOError("Order not in batch result")
                        )
                        self.logger().warning(
                            f"Batch order creation failed for {client_order_id}: not in result"
                        )

            except Exception as ex:
                self.logger().error(f"Batch order create failed with exception: {str(ex)}", exc_info=True)
                # Mark all orders for this symbol as failed
                for order in symbol_orders:
                    self._update_order_after_failure(
                        order_id=order.client_order_id,
                        trading_pair=order.trading_pair,
                        exception=ex
                    )

    def batch_order_cancel(self, orders_to_cancel: List[LimitOrder]):
        """
        Issues a batch order cancelation as a single API request. More efficient than individual cancels:
        - Individual: 8 cancels × 3 weight = 24 weight
        - Batch: 1 request × 10 weight = 10 weight (58% reduction)

        :param orders_to_cancel: A list of the orders to cancel.
        """
        safe_ensure_future(coro=self._execute_batch_cancel(orders_to_cancel=orders_to_cancel))

    async def _execute_batch_cancel(self, orders_to_cancel: List[LimitOrder]) -> List[CancellationResult]:
        """
        Execute batch order cancelation - make API call, process results.
        Per WEEX API: POST /api/v2/trade/cancel-batch-orders with {\"symbol\": \"...\", \"clientOids\": [...]}
        Response: {\"data\": {\"successList\": [...], \"failureList\": [{\"orderId\": ..., \"errMsg\": ...}]}}
        """
        if len(orders_to_cancel) == 0:
            return []

        results = []

        # Group orders by symbol (WEEX batch cancel must be for single symbol)
        orders_by_symbol = {}
        for order in orders_to_cancel:
            tracked_order = self._order_tracker.fetch_order(client_order_id=order.client_order_id)
            if tracked_order is not None:
                symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append((order, tracked_order))

        # Process each symbol separately
        for symbol, symbol_orders in orders_by_symbol.items():
            # Build lists of client order IDs and order IDs
            client_oids = []
            order_ids = []
            client_to_order_map = {}

            for order, tracked_order in symbol_orders:
                client_oids.append(order.client_order_id)
                client_to_order_map[order.client_order_id] = order
                if tracked_order.exchange_order_id:
                    order_ids.append(tracked_order.exchange_order_id)

            # Make single batch API call per symbol
            try:
                # WEEX API accepts either clientOids or orderIds
                request_data = {"symbol": symbol}
                if client_oids:
                    request_data["clientOids"] = client_oids
                if order_ids:
                    request_data["orderIds"] = order_ids

                batch_result = await self._api_post(
                    path_url=CONSTANTS.BATCH_CANCEL_ORDERS_PATH_URL,
                    data=request_data,
                    is_auth_required=True,
                    limit_id=CONSTANTS.BATCH_CANCEL_ORDERS_LIMIT_ID
                )

                # Process results - WEEX returns {"data": {"successList": [...], "failureList": [...]}}
                result_data = batch_result.get("data", {}) if isinstance(batch_result, dict) else {}
                success_list = result_data.get("successList", [])
                failure_list = result_data.get("failureList", [])

                # Process successful cancellations (successList contains order IDs as strings)
                for order_id_str in success_list:
                    # Try to match by exchange order ID or client order ID
                    matched_client_id = None
                    for client_id, order in client_to_order_map.items():
                        tracked = self._order_tracker.fetch_order(client_order_id=client_id)
                        if tracked and (str(tracked.exchange_order_id) == order_id_str or client_id == order_id_str):
                            matched_client_id = client_id
                            break

                    if matched_client_id:
                        results.append(CancellationResult(matched_client_id, True))
                        self.logger().info(f"Batch order canceled successfully: {matched_client_id}")

                # Process failed cancellations
                for failure_item in failure_list:
                    # failureList items have orderId and/or clientOid and errMsg
                    order_id = failure_item.get("orderId", "")
                    client_oid = failure_item.get("clientOid", "")
                    error_msg = failure_item.get("errMsg", "Unknown error")

                    # Try to find the client order ID
                    matched_client_id = client_oid if client_oid in client_to_order_map else None
                    if not matched_client_id and order_id:
                        for client_id in client_to_order_map:
                            tracked = self._order_tracker.fetch_order(client_order_id=client_id)
                            if tracked and str(tracked.exchange_order_id) == order_id:
                                matched_client_id = client_id
                                break

                    if matched_client_id:
                        results.append(CancellationResult(matched_client_id, False))
                        self.logger().warning(f"Batch order cancelation failed for {matched_client_id}: {error_msg}")

            except Exception as ex:
                self.logger().error(f"Batch order cancel failed for symbol {symbol}: {str(ex)}", exc_info=True)
                # All cancellations for this symbol failed
                for order, _ in symbol_orders:
                    results.append(CancellationResult(order.client_order_id, False))

        return results

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        self.logger().info(f"[WEEX_DEBUG] _format_trading_rules() called with {len(exchange_info_dict.get('data', []))} trading pairs")
        rules: List[TradingRule] = []

        for item in exchange_info_dict.get("data", []):
            if not item.get("enableTrade", False):
                continue

            symbol = item["symbol"]
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol)

            rules.append(
                TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=Decimal(item["minTradeAmount"]),
                    min_price_increment=Decimal(item["tickSize"]),
                    min_base_amount_increment=Decimal(item["stepSize"]),
                    min_notional_size=Decimal("0"),  # WEEX did not provide min notional in this payload
                )
            )

        self.logger().info(f"[WEEX_DEBUG] _format_trading_rules() returning {len(rules)} trading rules")
        return rules

    async def _status_polling_loop_fetch_updates(self):
        if self._disable_rest_order_polling:
            return
        await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        self.logger().info("[WEEX_DEBUG] _update_trading_fees() called")
        self._trade_fee_schema = weex_utils.DEFAULT_FEES
        self.logger().info("[WEEX_DEBUG] _update_trading_fees() completed")

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    continue

                if event_message.get("event") != "payload":
                    if event_message.get("event") == "subscribe":
                        self.logger().info(f"[WEEX_DEBUG] WebSocket subscription: {event_message.get('channel')}")
                    continue

                channel = event_message.get("channel", "")
                data = event_message.get("data")
                self.logger().info(f"[WEEX_DEBUG] WebSocket payload: channel='{channel}', data={data}, full msg={event_message}")
                if data is None:
                    continue

                payloads = data if isinstance(data, list) else [data]

                if channel.startswith("account"):
                    for balance_entry in payloads:
                        asset_name = balance_entry.get("coinName") or balance_entry.get("coin") or balance_entry.get("currency")
                        if asset_name is None:
                            continue
                        free_balance = Decimal(str(balance_entry.get("available", "0")))
                        frozen_balance = Decimal(str(balance_entry.get("frozen", "0")))
                        total_balance = free_balance + frozen_balance
                        self._account_available_balances[asset_name] = free_balance
                        self._account_balances[asset_name] = total_balance

                elif channel.startswith("fill"):
                    for fill in payloads:
                        client_order_id = (
                            fill.get("clientOrderId")
                            or fill.get("clientOid")
                            or fill.get("clientOrderID")
                        )
                        if client_order_id is None:
                            continue

                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        if tracked_order is None:
                            continue

                        fee_amount = Decimal(str(fill.get("fillFee") or fill.get("fee") or fill.get("fees") or "0"))
                        fee_token = fill.get("feeCoin") or fill.get("quoteCoin") or fill.get("feeAsset")
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=fee_token,
                            flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)] if fee_token else [],
                        )

                        trade_update = TradeUpdate(
                            trade_id=str(fill.get("fillId") or fill.get("tradeId") or fill.get("id")),
                            client_order_id=client_order_id,
                            exchange_order_id=str(fill.get("orderId")),
                            trading_pair=tracked_order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(str(fill.get("fillQuantity") or fill.get("size") or fill.get("quantity") or "0")),
                            fill_quote_amount=Decimal(str(fill.get("fillTotalAmount") or fill.get("value") or "0")),
                            fill_price=Decimal(str(fill.get("fillPrice") or fill.get("price") or "0")),
                            fill_timestamp=float(fill.get("cTime") or fill.get("time") or self.current_timestamp) * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)

                elif channel.startswith("orders"):
                    self.logger().info(f"[WEEX_DEBUG] Processing orders channel with {len(payloads)} payload(s)")
                    for order_update in payloads:
                        client_order_id = (
                            order_update.get("clientOrderId")
                            or order_update.get("clientOid")
                            or order_update.get("clientOrderID")
                        )
                        self.logger().info(f"[WEEX_DEBUG] Order update: clientOrderId={client_order_id}, status={order_update.get('status')}, orderId={order_update.get('orderId')}")
                        if client_order_id is None:
                            continue

                        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                        if tracked_order is None:
                            self.logger().info(f"[WEEX_DEBUG] Order {client_order_id} not found in all_updatable_orders. Active orders: {list(self._order_tracker.active_orders.keys())}")
                            continue

                        new_state = CONSTANTS.ORDER_STATE.get(order_update.get("status", "PENDING"), OrderState.PENDING_CREATE)
                        update_time = (
                            order_update.get("uTime")
                            or order_update.get("updateTime")
                            or order_update.get("cTime")
                            or order_update.get("time")
                            or self.current_timestamp * 1e3
                        )
                        self.logger().info(f"[WEEX_DEBUG] Updating order {client_order_id} to state {new_state}")

                        order_update_obj = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=float(update_time) * 1e-3,
                            new_state=new_state,
                            client_order_id=client_order_id,
                            exchange_order_id=str(order_update.get("orderId")),
                        )
                        self._order_tracker.process_order_update(order_update=order_update_obj)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)
    #     """
    #     This functions runs in background continuously processing the events received from the exchange by the user
    #     stream data source. It keeps reading events from the queue until the task is interrupted.
    #     The events received are balance updates, order updates and trade events.
    #     """
    #     async for event_message in self._iter_user_event_queue():
    #         try:
    #             event_type = event_message.get("e")
    #             # Refer to https://github.com/weex-exchange/weex-official-api-docs/blob/master/user-data-stream.md
    #             # As per the order update section in Weex the ID of the order being canceled is under the "C" key
    #             if event_type == "executionReport":
    #                 execution_type = event_message.get("x")
    #                 if execution_type != "CANCELED":
    #                     client_order_id = event_message.get("c")
    #                 else:
    #                     client_order_id = event_message.get("C")

    #                 if execution_type == "TRADE":
    #                     tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
    #                     if tracked_order is not None:
    #                         fee = TradeFeeBase.new_spot_fee(
    #                             fee_schema=self.trade_fee_schema(),
    #                             trade_type=tracked_order.trade_type,
    #                             percent_token=event_message["N"],
    #                             flat_fees=[TokenAmount(amount=Decimal(event_message["n"]), token=event_message["N"])]
    #                         )
    #                         trade_update = TradeUpdate(
    #                             trade_id=str(event_message["t"]),
    #                             client_order_id=client_order_id,
    #                             exchange_order_id=str(event_message["i"]),
    #                             trading_pair=tracked_order.trading_pair,
    #                             fee=fee,
    #                             fill_base_amount=Decimal(event_message["l"]),
    #                             fill_quote_amount=Decimal(event_message["l"]) * Decimal(event_message["L"]),
    #                             fill_price=Decimal(event_message["L"]),
    #                             fill_timestamp=event_message["T"] * 1e-3,
    #                         )
    #                         self._order_tracker.process_trade_update(trade_update)

    #                 tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
    #                 if tracked_order is not None:
    #                     order_update = OrderUpdate(
    #                         trading_pair=tracked_order.trading_pair,
    #                         update_timestamp=event_message["E"] * 1e-3,
    #                         new_state=CONSTANTS.ORDER_STATE[event_message["X"]],
    #                         client_order_id=client_order_id,
    #                         exchange_order_id=str(event_message["i"]),
    #                     )
    #                     self._order_tracker.process_order_update(order_update=order_update)

    #             elif event_type == "outboundAccountPosition":
    #                 balances = event_message["B"]
    #                 for balance_entry in balances:
    #                     asset_name = balance_entry["a"]
    #                     free_balance = Decimal(balance_entry["f"])
    #                     total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
    #                     self._account_available_balances[asset_name] = free_balance
    #                     self._account_balances[asset_name] = total_balance

    #         except asyncio.CancelledError:
    #             raise
    #         except Exception:
    #             self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
    #             await self._sleep(5.0)

    async def _update_order_fills_from_trades(self):
        if not self.in_flight_orders:
            return

        tracked_orders = list(self._order_tracker.all_fillable_orders.values())
        if not tracked_orders:
            return

        tasks = [self._all_trade_updates_for_order(order) for order in tracked_orders]
        results = await safe_gather(*tasks, return_exceptions=True)

        for updates in results:
            if isinstance(updates, Exception):
                continue
            for trade_update in updates:
                self._order_tracker.process_trade_update(trade_update)
    #     """
    #     This is intended to be a backup measure to get filled events with trade ID for orders,
    #     in case Weex's user stream events are not working.
    #     NOTE: It is not required to copy this functionality in other connectors.
    #     This is separated from _update_order_status which only updates the order status without producing filled
    #     events, since Weex's get order endpoint does not return trade IDs.
    #     The minimum poll interval for order status is 10 seconds.
    #     """
    #     small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
    #     small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
    #     long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
    #     long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

    #     if (long_interval_current_tick > long_interval_last_tick
    #             or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
    #         query_time = int(self._last_trades_poll_weex_timestamp * 1e3)
    #         self._last_trades_poll_weex_timestamp = self._time_synchronizer.time()
    #         order_by_exchange_id_map = {}
    #         for order in self._order_tracker.all_fillable_orders.values():
    #             order_by_exchange_id_map[order.exchange_order_id] = order

    #         tasks = []
    #         trading_pairs = self.trading_pairs
    #         for trading_pair in trading_pairs:
    #             params = {
    #                 "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
    #             }
    #             if self._last_poll_timestamp > 0:
    #                 params["startTime"] = query_time
    #             tasks.append(self._api_get(
    #                 path_url=CONSTANTS.MY_TRADES_PATH_URL,
    #                 params=params,
    #                 is_auth_required=True))

    #         self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")
    #         results = await safe_gather(*tasks, return_exceptions=True)

    #         for trades, trading_pair in zip(results, trading_pairs):

    #             if isinstance(trades, Exception):
    #                 self.logger().network(
    #                     f"Error fetching trades update for the order {trading_pair}: {trades}.",
    #                     app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
    #                 )
    #                 continue
    #             for trade in trades:
    #                 exchange_order_id = str(trade["orderId"])
    #                 if exchange_order_id in order_by_exchange_id_map:
    #                     # This is a fill for a tracked order
    #                     tracked_order = order_by_exchange_id_map[exchange_order_id]
    #                     fee = TradeFeeBase.new_spot_fee(
    #                         fee_schema=self.trade_fee_schema(),
    #                         trade_type=tracked_order.trade_type,
    #                         percent_token=trade["commissionAsset"],
    #                         flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
    #                     )
    #                     trade_update = TradeUpdate(
    #                         trade_id=str(trade["id"]),
    #                         client_order_id=tracked_order.client_order_id,
    #                         exchange_order_id=exchange_order_id,
    #                         trading_pair=trading_pair,
    #                         fee=fee,
    #                         fill_base_amount=Decimal(trade["qty"]),
    #                         fill_quote_amount=Decimal(trade["quoteQty"]),
    #                         fill_price=Decimal(trade["price"]),
    #                         fill_timestamp=trade["time"] * 1e-3,
    #                     )
    #                     self._order_tracker.process_trade_update(trade_update)
    #                 elif self.is_confirmed_new_order_filled_event(str(trade["id"]), exchange_order_id, trading_pair):
    #                     # This is a fill of an order registered in the DB but not tracked any more
    #                     self._current_trade_fills.add(TradeFillOrderDetails(
    #                         market=self.display_name,
    #                         exchange_trade_id=str(trade["id"]),
    #                         symbol=trading_pair))
    #                     self.trigger_event(
    #                         MarketEvent.OrderFilled,
    #                         OrderFilledEvent(
    #                             timestamp=float(trade["time"]) * 1e-3,
    #                             order_id=self._exchange_order_ids.get(str(trade["orderId"]), None),
    #                             trading_pair=trading_pair,
    #                             trade_type=TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
    #                             order_type=OrderType.LIMIT_MAKER if trade["isMaker"] else OrderType.LIMIT,
    #                             price=Decimal(trade["price"]),
    #                             amount=Decimal(trade["qty"]),
    #                             trade_fee=DeductedFromReturnsTradeFee(
    #                                 flat_fees=[
    #                                     TokenAmount(
    #                                         trade["commissionAsset"],
    #                                         Decimal(trade["commission"])
    #                                     )
    #                                 ]
    #                             ),
    #                             exchange_trade_id=str(trade["id"])
    #                         ))
    #                     self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        if self._disable_rest_order_polling:
            return []

        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_post(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                data={
                    "symbol": trading_pair,
                    "orderId": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_LIMIT_ID)

            fills_data = all_fills_response.get("data", {}) if isinstance(all_fills_response, dict) else {}
            fills_list = fills_data.get("fillsOrderResultList", []) if isinstance(fills_data, dict) else []

            for trade in fills_list:
                exchange_order_id = str(trade.get("orderId"))
                fee_amount = Decimal(trade.get("fees", "0"))
                fee_token = trade.get("quoteCoin")
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=fee_token,
                    flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)] if fee_token else []
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade.get("fillId")),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade.get("fillQuantity", "0")),
                    fill_quote_amount=Decimal(trade.get("fillTotalAmount", "0")),
                    fill_price=Decimal(trade.get("fillPrice", "0")),
                    fill_timestamp=float(trade.get("cTime", 0)) * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_response = await self._api_post(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
            data={
                "clientOrderId": tracked_order.client_order_id
            },
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_STATUS_LIMIT_ID)

        data = updated_order_response.get("data") if isinstance(updated_order_response, dict) else None
        if isinstance(data, list) and len(data) > 0:
            updated_order_data = data[0]
        elif isinstance(data, dict):
            updated_order_data = data
        else:
            updated_order_data = {}

        new_state = CONSTANTS.ORDER_STATE[updated_order_data.get("status", "PENDING")]
        update_time = (
            updated_order_data.get("uTime")
            or updated_order_data.get("updateTime")
            or updated_order_response.get("requestTime", 0)
        )

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data.get("orderId")),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(update_time) * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        self.logger().info("[WEEX_DEBUG] _update_balances() called")
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        self.logger().info(f"[WEEX_DEBUG] Fetching account info from {CONSTANTS.ACCOUNTS_PATH_URL}")
        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.ACCOUNTS_LIMIT_ID)
        self.logger().info(f"[WEEX_DEBUG] Account info received: {len(account_info.get('data', []))} entries")

        balances = account_info["data"]
        for balance_entry in balances:
            asset_name = balance_entry["coinName"]
            free_balance = Decimal(balance_entry["available"])
            total_balance = Decimal(balance_entry["available"]) + Decimal(balance_entry["frozen"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        self.logger().info(f"[WEEX_DEBUG] Updated {len(remote_asset_names)} balances: {list(remote_asset_names)}")

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

        self.logger().info("[WEEX_DEBUG] _update_balances() completed")

    KNOWN_QUOTES = ("USDT", "USDC", "BTC", "ETH", "EUR", "TRY", "BRL")

    @staticmethod
    def weex_symbol_to_hb_pair(symbol: str) -> str:
        # BTCUSDT_SPBL -> BTCUSDT
        core = symbol[:-5]  # drop "_SPBL"
        for q in WeexExchange.KNOWN_QUOTES:
            if core.endswith(q) and len(core) > len(q):
                base = core[:-len(q)]
                quote = q
                return f"{base}-{quote}"
        raise ValueError(f"Cannot infer quote from WEEX symbol: {symbol}")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        self.logger().info("[WEEX_DEBUG] _initialize_trading_pair_symbols_from_exchange_info() called")
        mapping = bidict()
        for item in exchange_info.get("data", []):
            symbol = item["symbol"]
            hb_pair = combine_to_hb_trading_pair(base=item["baseCoin"], quote=item["quoteCoin"])
            mapping[symbol] = hb_pair
        self.logger().info(f"[WEEX_DEBUG] Created {len(mapping)} trading pair mappings")
        self._set_trading_pair_symbol_map(mapping)
        self.logger().info("[WEEX_DEBUG] Trading pair symbol map set")

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            limit_id=CONSTANTS.TICKER_PRICE_CHANGE_LIMIT_ID,
            params=params
        )

        return float(resp_json["data"]["lastPrice"])
