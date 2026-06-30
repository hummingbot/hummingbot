import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_api_order_book_data_source import GeminiAPIOrderBookDataSource
from hummingbot.connector.exchange.gemini.gemini_api_user_stream_data_source import GeminiAPIUserStreamDataSource
from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class GeminiWSTransportError(ConnectionError):
    """The WS request was not executed by the exchange (connect failure, send failure,
    or an error ack such as 401/429/500). The request can safely be retried over REST."""


class GeminiWSAmbiguousResponseError(GeminiWSTransportError):
    """The WS request was sent but never answered (ack timeout, or disconnect while
    waiting). The exchange may or may not have executed it — a blind retry could
    duplicate an order, so callers must reconcile before retrying."""


class GeminiWSRejectionError(IOError):
    """The exchange answered the WS request with a definitive rejection.
    Retrying over REST would produce the same rejection."""


class GeminiExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 gemini_api_key: str,
                 gemini_api_secret: str,
                 balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
                 rate_limits_share_pct: Decimal = Decimal("100"),
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 ):
        self.api_key = gemini_api_key
        self.secret_key = gemini_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        # Dedicated authenticated websocket for order entry (order.place / order.cancel).
        # Requests are correlated to their {id, status, ...} acks through futures keyed
        # by request id; any failure on this socket falls back to the REST endpoints.
        self._trade_ws: Optional[WSAssistant] = None
        self._trade_ws_listener_task: Optional[asyncio.Task] = None
        self._trade_ws_maintenance_task: Optional[asyncio.Task] = None
        self._trade_ws_pending_requests: Dict[str, asyncio.Future] = {}
        self._trade_ws_request_id: int = 0
        self._trade_ws_lock = asyncio.Lock()
        self._trade_ws_stopped: bool = False
        self._trade_ws_last_connect_failure: float = 0.0
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def authenticator(self):
        return GeminiAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return ""

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def status_dict(self) -> Dict[str, bool]:
        # Gate readiness on the order-entry websocket actually being connected, so
        # strategies cannot start creating/cancelling orders before the WS path is
        # usable (the maintenance loop establishes it during start_network).
        status = super().status_dict
        status["trade_websocket_connected"] = (not self.is_trading_required
                                               or self._trade_ws is not None)
        return status

    def supported_order_types(self):
        # MARKET is emulated as an immediate-or-cancel "exchange limit" priced
        # aggressively through the book (Gemini has no native market order type).
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        # Gemini doesn't have a bulk ticker endpoint, so we return an empty list
        # and rely on individual ticker calls via _get_last_traded_price
        return []

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_str = str(request_exception)
        return "InvalidNonce" in error_str or "not within" in error_str

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        # Clear stale offset samples before re-syncing so one fresh fetch replaces drifted values
        self._time_synchronizer.clear_time_offset_ms_samples()
        await super()._update_time_synchronizer(pass_on_non_cancelled_error=pass_on_non_cancelled_error)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        error_str = str(cancelation_exception)
        return (CONSTANTS.ORDER_NOT_FOUND_ERROR in error_str
                or CONSTANTS.WS_ORDER_NOT_FOUND_MESSAGE in error_str.lower())

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GeminiAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GeminiAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        # Honor caller-provided is_maker when given. Otherwise treat both LIMIT and
        # LIMIT_MAKER as maker orders (PMM uses LIMIT_MAKER) so we don't misclassify
        # post-only orders as takers.
        if is_maker is None:
            is_maker = order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER)
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        if order_type is OrderType.MARKET:
            # Gemini has no native market order; emulate it with an immediate-or-cancel
            # "exchange limit" priced aggressively through the book. This always goes over
            # REST (the documented path for the immediate-or-cancel option) rather than the
            # maker-oriented order-entry websocket.
            return await self._place_order_via_rest(
                order_id=order_id,
                symbol=symbol,
                amount=amount,
                trade_type=trade_type,
                order_type=order_type,
                price=self._market_order_price(
                    trading_pair=trading_pair, trade_type=trade_type, amount=amount, price=price))

        try:
            return await self._place_order_via_ws(
                order_id=order_id,
                symbol=symbol,
                amount=amount,
                trade_type=trade_type,
                order_type=order_type,
                price=price)
        except asyncio.CancelledError:
            raise
        except GeminiWSRejectionError:
            # The exchange examined and rejected the order (e.g. insufficient funds,
            # invalid params). REST would reject it identically — do not retry.
            raise
        except GeminiWSAmbiguousResponseError as ws_error:
            # The order.place request was sent but never answered — the order may be
            # live on the exchange. A blind REST retry could double the position, so
            # first ask REST whether an order with this client order id exists.
            self.logger().warning(
                f"No response to the websocket placement of order {order_id} ({ws_error}). "
                f"Reconciling over REST before retrying.")
            order_status = await self._get_order_via_rest_by_client_id(order_id)
            if order_status is not None:
                return str(order_status["order_id"]), order_status.get("timestampms", 0) * 1e-3
            # The exchange has no order with this client id — safe to place over REST.
        except GeminiWSTransportError as ws_error:
            self.logger().warning(
                f"Failed to place order {order_id} via websocket ({ws_error}). Falling back to REST.")

        return await self._place_order_via_rest(
            order_id=order_id,
            symbol=symbol,
            amount=amount,
            trade_type=trade_type,
            order_type=order_type,
            price=price)

    async def _place_order_via_ws(self,
                                  order_id: str,
                                  symbol: str,
                                  amount: Decimal,
                                  trade_type: TradeType,
                                  order_type: OrderType,
                                  price: Decimal) -> Tuple[str, float]:
        params = {
            "symbol": symbol,
            "side": CONSTANTS.WS_SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.WS_SIDE_SELL,
            # The connector only places limit orders (see supported_order_types);
            # maker-or-cancel is expressed through timeInForce on the WS API.
            "type": CONSTANTS.WS_ORDER_TYPE_LIMIT,
            "timeInForce": (CONSTANTS.WS_TIME_IN_FORCE_MOC
                            if order_type is OrderType.LIMIT_MAKER
                            else CONSTANTS.WS_TIME_IN_FORCE_GTC),
            "price": f"{price:f}",
            "quantity": f"{amount:f}",
            "clientOrderId": order_id,
        }

        response = await self._trade_ws_request(
            method=CONSTANTS.WS_METHOD_ORDER_PLACE,
            params=params,
            throttler_limit_id=CONSTANTS.WS_ORDER_PLACE_LIMIT_ID)
        self._raise_for_ws_error(response)
        transact_time = self._time()

        # Per Gemini engineering, the order.place ack intentionally carries no order
        # payload and is NOT proof of placement — the orders@account order event is the
        # sole source of truth. Probe the result anyway (cheap future-proofing), then
        # resolve the id from the order event, with REST status as the backstop.
        exchange_order_id = self._extract_exchange_order_id(response.get("result"))
        if exchange_order_id is None:
            exchange_order_id = await self._resolve_acked_order_exchange_id(order_id)

        return str(exchange_order_id), transact_time

    async def _resolve_acked_order_exchange_id(self, order_id: str) -> str:
        """Resolves the exchange order id after an order.place ack. Primary source: the
        orders@account order event on the user stream (it carries the id in "i").
        Backstop if the user stream lags: REST order status by client order id.

        Raises GeminiWSTransportError when both agree the order does not exist — per
        Gemini, an ack without an order event does not mean placed, so the request is
        treated as not executed and _place_order retries over REST. Raises IOError when
        the order's existence could not be established either way, because a REST
        re-placement could then duplicate a live order."""
        # all_orders (not active_orders): an aggressively priced order can fill and reach
        # a terminal state — leaving active_orders — before the ack coroutine resumes.
        tracked_order = self._order_tracker.all_orders.get(order_id)
        if tracked_order is not None:
            try:
                return await tracked_order.get_exchange_order_id()
            except asyncio.TimeoutError:
                pass  # user stream lagging or reconnecting — reconcile over REST below

        try:
            order_status = await self._get_order_via_rest_by_client_id(order_id)
        except asyncio.CancelledError:
            raise
        except Exception as status_error:
            raise IOError(
                f"Order {order_id} received an order.place ack but its existence could not "
                f"be confirmed by an order event, and REST reconciliation failed: {status_error}")
        if order_status is not None and order_status.get("order_id") is not None:
            return str(order_status["order_id"])

        raise GeminiWSTransportError(
            f"Order {order_id} received an order.place ack but no order event arrived and "
            f"REST reports no such order — treating the placement as not executed.")

    async def _get_order_via_rest_by_client_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Looks an order up over REST by its client order id (supported by
        /v1/order/status as an alternative to order_id). Returns None when the
        exchange reports that no such order exists."""
        try:
            return await self._api_post(
                path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
                data={
                    "request": CONSTANTS.ORDER_STATUS_PATH_URL,
                    "client_order_id": order_id,
                },
                is_auth_required=True)
        except asyncio.CancelledError:
            raise
        except Exception as status_error:
            if self._is_order_not_found_during_status_update_error(status_error):
                return None
            raise

    def _market_order_price(self,
                            trading_pair: str,
                            trade_type: TradeType,
                            amount: Decimal,
                            price: Decimal) -> Decimal:
        """Builds the aggressive limit price for an emulated market order: the price that
        would fill the whole `amount` through the book, padded by MARKET_ORDER_SLIPPAGE so
        the immediate-or-cancel order still sweeps the liquidity if the book shifts. The
        order executes at the resting book prices — this is only the protective bound."""
        is_buy = trade_type is TradeType.BUY
        reference_price = self._reference_price_for_market_order(
            trading_pair=trading_pair, is_buy=is_buy, amount=amount, fallback_price=price)
        slippage_factor = (Decimal("1") + CONSTANTS.MARKET_ORDER_SLIPPAGE
                           if is_buy else Decimal("1") - CONSTANTS.MARKET_ORDER_SLIPPAGE)
        aggressive_price = reference_price * slippage_factor
        if is_buy:
            # Gemini reserves amount * limit_price for a buy limit, but the strategy sized the
            # order against the (un-padded) market price — so the padded limit, and even the
            # full-depth sweep reference, can exceed the reserved quote and get a near-all-in
            # market buy rejected for insufficient funds. Cap the limit at the price the
            # available quote can fund so the immediate-or-cancel fills what it can afford (at
            # the cheaper resting prices) instead of being rejected. min() only ever lowers the
            # limit, so an ample balance leaves the aggressive price untouched.
            affordable_price = self._affordable_buy_limit_price(trading_pair, amount)
            if affordable_price is not None:
                aggressive_price = min(aggressive_price, affordable_price)
        quantized = self.quantize_order_price(trading_pair, aggressive_price)
        if quantized <= Decimal("0"):
            # The slippage buffer rounded a low-priced asset's sell limit down to zero;
            # fall back to the (positive) reference so the order still has a valid price.
            quantized = self.quantize_order_price(trading_pair, reference_price)
        return quantized

    def _affordable_buy_limit_price(self, trading_pair: str, amount: Decimal) -> Optional[Decimal]:
        """Highest per-unit quote price the available quote balance can cover for `amount`
        base, used to keep an emulated market buy's protective limit fundable. Returns None
        when the amount or the tracked quote balance is unusable, leaving the limit uncapped."""
        if amount <= Decimal("0"):
            return None
        _, quote = split_hb_trading_pair(trading_pair)
        available_quote = self._account_available_balances.get(quote)
        if available_quote is None or available_quote <= Decimal("0"):
            return None
        return available_quote / amount

    def _reference_price_for_market_order(self,
                                          trading_pair: str,
                                          is_buy: bool,
                                          amount: Decimal,
                                          fallback_price: Decimal) -> Decimal:
        """Resolves a positive reference price for a market order, preferring the price
        that fills `amount` through the book, then the top of book, then a caller-supplied
        price. Raises ValueError if none is usable (e.g. the order book is not yet tracked)."""
        candidates: List[Optional[Decimal]] = []
        try:
            volume_query = self.get_price_for_volume(trading_pair, is_buy, amount)
            if volume_query is not None:
                candidates.append(Decimal(str(volume_query.result_price)))
        except Exception:
            pass
        try:
            candidates.append(self.get_price(trading_pair, is_buy))
        except Exception:
            pass
        candidates.append(fallback_price)
        for candidate in candidates:
            if candidate is not None and not candidate.is_nan() and candidate > Decimal("0"):
                return candidate
        raise ValueError(
            f"Cannot determine a market price for {trading_pair}: the order book is "
            f"unavailable and no valid fallback price was provided.")

    async def _place_order_via_rest(self,
                                    order_id: str,
                                    symbol: str,
                                    amount: Decimal,
                                    trade_type: TradeType,
                                    order_type: OrderType,
                                    price: Decimal) -> Tuple[str, float]:
        side = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL

        # Gemini has no native "exchange market" order type — every order, including an
        # emulated MARKET, is an "exchange limit". A MARKET order carries the aggressive
        # price computed by _market_order_price and the immediate-or-cancel option below.
        gemini_order_type = CONSTANTS.ORDER_TYPE_LIMIT

        api_params = {
            "request": CONSTANTS.NEW_ORDER_PATH_URL,
            "symbol": symbol,
            "amount": f"{amount:f}",
            "side": side,
            "type": gemini_order_type,
            "price": f"{price:f}",
            "client_order_id": order_id,
        }

        if order_type == OrderType.LIMIT_MAKER:
            api_params["options"] = [CONSTANTS.ORDER_OPTION_MAKER_OR_CANCEL]
        elif order_type == OrderType.MARKET:
            api_params["options"] = [CONSTANTS.ORDER_OPTION_IMMEDIATE_OR_CANCEL]

        order_result = await self._api_post(
            path_url=CONSTANTS.NEW_ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True)

        o_id = str(order_result["order_id"])
        transact_time = order_result.get("timestampms", 0) * 1e-3

        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        if tracked_order.exchange_order_id is None:
            await tracked_order.get_exchange_order_id()

        try:
            return await self._place_cancel_via_ws(exchange_order_id=tracked_order.exchange_order_id)
        except asyncio.CancelledError:
            raise
        except GeminiWSRejectionError:
            # Definitive answer (e.g. "order not found or already filled") — the
            # not-found predicates inspect the message; REST would not differ.
            raise
        except GeminiWSTransportError as ws_error:
            self.logger().warning(
                f"Failed to cancel order {order_id} via websocket ({ws_error}). Falling back to REST.")

        api_params = {
            "request": CONSTANTS.CANCEL_ORDER_PATH_URL,
            "order_id": int(tracked_order.exchange_order_id),
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True)
        if cancel_result.get("is_cancelled", False):
            return True
        return False

    async def _place_cancel_via_ws(self, exchange_order_id: str) -> bool:
        response = await self._trade_ws_request(
            method=CONSTANTS.WS_METHOD_ORDER_CANCEL,
            params={"orderId": str(exchange_order_id)},
            throttler_limit_id=CONSTANTS.WS_ORDER_CANCEL_LIMIT_ID)
        self._raise_for_ws_error(response)
        return True

    @staticmethod
    def _raise_for_ws_error(response: Dict[str, Any]):
        """Classifies a WS {id, status, result|error} ack. A 400 answer is a definitive
        rejection (invalid params, insufficient funds) that REST would repeat. Any other
        non-200 (401 auth, 429 rate limit, 500 internal) means the request was not
        executed and may be retried over REST, whose auth and rate limits are separate."""
        status = response.get("status")
        if status == 200:
            return
        error = response.get("error") or {}
        message = (f"Gemini WS request failed with status {status}: "
                   f"code={error.get('code')} msg={error.get('msg', '')}")
        if status == 400:
            raise GeminiWSRejectionError(message)
        raise GeminiWSTransportError(message)

    @staticmethod
    def _extract_exchange_order_id(result: Any) -> Optional[str]:
        """Per Gemini engineering the order.place ack intentionally carries no order
        payload, so this normally returns None; the probe is kept as future-proofing
        should the result ever gain order-id fields. The generic "id" key is
        deliberately NOT probed — a result echoing the request id under "id" would
        otherwise be mistaken for the exchange order id and poison every later cancel
        and status poll for the order."""
        candidates = [result]
        if isinstance(result, dict) and isinstance(result.get("order"), dict):
            candidates.append(result["order"])
        for candidate in candidates:
            if isinstance(candidate, dict):
                for key in ("orderId", "order_id", "i"):
                    value = candidate.get(key)
                    if value not in (None, ""):
                        return str(value)
        return None

    async def _trade_ws_request(self,
                                method: str,
                                params: Dict[str, Any],
                                throttler_limit_id: str) -> Dict[str, Any]:
        """Sends a {id, method, params} request on the trade websocket and waits for
        the ack with the matching id. Raises GeminiWSTransportError for any failure
        in which the request was not answered (connect, send, timeout, disconnect)."""
        try:
            ws = await self._connected_trade_ws()
        except asyncio.CancelledError:
            raise
        except Exception as connection_error:
            raise GeminiWSTransportError(
                f"Could not connect to the Gemini trade websocket: {connection_error}")

        self._trade_ws_request_id += 1
        request_id = str(self._trade_ws_request_id)
        response_future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._trade_ws_pending_requests[request_id] = response_future

        try:
            payload = {"id": request_id, "method": method, "params": params}
            async with self._throttler.execute_task(limit_id=throttler_limit_id):
                await ws.send(WSJSONRequest(payload=payload))
            response = await asyncio.wait_for(
                response_future, timeout=CONSTANTS.WS_ORDER_REQUEST_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except GeminiWSTransportError:
            raise
        except asyncio.TimeoutError:
            # The request reached the wire but was never answered — the exchange may
            # have executed it. Signal ambiguity so _place_order reconciles instead of
            # blindly re-placing over REST.
            raise GeminiWSAmbiguousResponseError(
                f"Timed out waiting {CONSTANTS.WS_ORDER_REQUEST_TIMEOUT}s for the response to "
                f"the {method} websocket request.")
        except Exception as send_error:
            raise GeminiWSTransportError(
                f"Failed to send the {method} websocket request: {send_error}")
        finally:
            self._trade_ws_pending_requests.pop(request_id, None)

        return response

    async def _connected_trade_ws(self) -> WSAssistant:
        async with self._trade_ws_lock:
            if self._trade_ws_stopped:
                raise GeminiWSTransportError(
                    "The connector is stopped — not opening a trade websocket.")
            if self._trade_ws is None:
                if self._time() - self._trade_ws_last_connect_failure < CONSTANTS.WS_CONNECT_COOLDOWN:
                    # Fail fast so queued order requests go straight to REST instead of
                    # serially re-attempting the handshake while holding the lock.
                    raise GeminiWSTransportError(
                        "The trade websocket failed to connect recently — deferring to REST "
                        "until the cooldown expires.")
                ws: Optional[WSAssistant] = None
                try:
                    ws = await self._web_assistants_factory.get_ws_assistant()
                    # Time-boxed: this runs under the trade WS lock, and an un-bounded
                    # handshake would head-of-line block every placement and cancel.
                    await asyncio.wait_for(
                        ws.connect(
                            ws_url=web_utils.wss_url(),
                            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
                            ws_headers=self._auth.get_ws_auth_headers(),
                        ),
                        timeout=CONSTANTS.WS_CONNECT_TIMEOUT)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self._trade_ws_last_connect_failure = self._time()
                    if ws is not None:
                        await self._safe_ws_disconnect(ws)
                    raise
                if self._trade_ws_stopped:
                    # stop_network ran while the handshake was in flight
                    await self._safe_ws_disconnect(ws)
                    raise GeminiWSTransportError(
                        "The connector was stopped while the trade websocket was connecting.")
                self._trade_ws = ws
                self._trade_ws_listener_task = safe_ensure_future(self._trade_ws_listener(ws))
            return self._trade_ws

    @staticmethod
    async def _safe_ws_disconnect(ws: WSAssistant):
        try:
            await ws.disconnect()
        except Exception:
            pass

    async def _trade_ws_listener(self, ws: WSAssistant):
        """Routes {id, status, ...} acks from the trade websocket to the futures of
        their pending requests. Any termination resets the connection so the next
        order request reconnects lazily."""
        try:
            async for ws_response in ws.iter_messages():
                data = ws_response.data
                if not isinstance(data, dict):
                    continue
                response_future = self._trade_ws_pending_requests.get(str(data.get("id", "")))
                if response_future is not None and not response_future.done():
                    response_future.set_result(data)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().warning("Unexpected error in the Gemini trade websocket listener.",
                                  exc_info=True)
        finally:
            await self._reset_trade_ws(ws)

    async def _reset_trade_ws(self, ws: Optional[WSAssistant]):
        if ws is None:
            return
        async with self._trade_ws_lock:
            if self._trade_ws is not ws:
                return
            self._trade_ws = None
            listener_task = self._trade_ws_listener_task
            self._trade_ws_listener_task = None
            for response_future in self._trade_ws_pending_requests.values():
                if not response_future.done():
                    # The requests were already sent on the dying socket, so their
                    # outcome is unknown — fail them as ambiguous, not retriable.
                    response_future.set_exception(GeminiWSAmbiguousResponseError(
                        "The trade websocket disconnected before a response was received."))
            self._trade_ws_pending_requests.clear()
            if listener_task is not None and listener_task is not asyncio.current_task():
                listener_task.cancel()
        await self._safe_ws_disconnect(ws)

    async def _trade_ws_maintenance_loop(self):
        """Eagerly connects the trade websocket and keeps it connected, so order entry
        never pays the handshake on the order path and `status_dict` reflects the real
        state of the order-entry rail. _connected_trade_ws is a no-op when connected
        and enforces its own cooldown after failures."""
        while True:
            try:
                await self._connected_trade_ws()
            except asyncio.CancelledError:
                raise
            except GeminiWSTransportError:
                pass  # expected while stopped or cooling down after a failed connect
            except Exception:
                self.logger().warning(
                    "Failed to (re)connect the Gemini trade websocket. Will keep retrying; "
                    "orders fall back to REST meanwhile.", exc_info=True)
            await self._sleep(CONSTANTS.WS_MAINTENANCE_INTERVAL)

    async def start_network(self):
        # ExchangePyBase.start_network's FIRST statement is `await self.stop_network()`,
        # which dispatches to our override and sets _trade_ws_stopped. The trade-WS
        # flags must therefore be cleared AFTER the base start — clearing them before
        # would leave the connector permanently "stopped" for the trade websocket.
        await super().start_network()
        self._trade_ws_stopped = False
        self._trade_ws_last_connect_failure = 0.0
        if self.is_trading_required and self._trade_ws_maintenance_task is None:
            self._trade_ws_maintenance_task = safe_ensure_future(self._trade_ws_maintenance_loop())

    async def stop_network(self):
        # Set the flag first: a connect that is mid-handshake when this runs re-checks
        # it before installing the socket, and later requests refuse to reconnect.
        self._trade_ws_stopped = True
        if self._trade_ws_maintenance_task is not None:
            self._trade_ws_maintenance_task.cancel()
            self._trade_ws_maintenance_task = None
        await super().stop_network()
        await self._reset_trade_ws(self._trade_ws)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Gemini's /v1/symbols returns a list of symbol strings.
        We need to fetch details for each symbol individually.
        """
        retval = []
        # exchange_info_dict is the response from /v1/symbols, which is a list of symbol strings
        symbols = exchange_info_dict if isinstance(exchange_info_dict, list) else []

        for symbol in symbols:
            try:
                # Check if this symbol maps to one of our trading pairs
                try:
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol)
                except KeyError:
                    continue

                # The symbol map contains every Gemini symbol (~300+). Fetch the
                # per-symbol details only for the configured pairs — sweeping them all
                # would burn ~3x Gemini's whole public budget (120 req/min) per update.
                if self._trading_pairs and trading_pair not in self._trading_pairs:
                    continue

                rest_assistant = await self._web_assistants_factory.get_rest_assistant()
                details = await rest_assistant.execute_request(
                    url=web_utils.public_rest_url(
                        path_url=CONSTANTS.SYMBOL_DETAILS_PATH_URL.format(symbol)),
                    method=RESTMethod.GET,
                    throttler_limit_id=CONSTANTS.SYMBOL_DETAILS_PATH_URL,
                )

                min_order_size = Decimal(str(details.get("min_order_size", "0.00001")))
                tick_size = Decimal(str(details.get("tick_size", "1e-8")))
                quote_increment = Decimal(str(details.get("quote_increment", "0.01")))

                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=quote_increment,
                        min_base_amount_increment=tick_size,
                        min_notional_size=min_order_size * quote_increment,
                    ))
            except Exception:
                self.logger().exception(f"Error parsing trading pair rule for {symbol}. Skipping.")
        return retval

    async def _status_polling_loop_fetch_updates(self):
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        pass

    async def _user_stream_event_listener(self):
        """
        Processes events from the Gemini Fast API user stream.
        Handles order updates and balance updates.

        Gemini Fast API message formats:
        - Order events: {"E": <ns>, "s": "BTCUSD", "i": <id>, "c": <client_id>,
                         "S": "BUY", "o": "LIMIT", "X": "NEW", "p": "1.00",
                         "q": "0.001", "z": "0", "T": <ns>}
        - Balance updates: {"e": "balanceUpdate", "E": <ms>, "B": [{"a": "USD", "f": "207.39"}]}
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e")

                if "X" in event_message:
                    # Order event — identified by presence of "X" (order status) field
                    order_status = event_message.get("X", "")
                    client_order_id = event_message.get("c", "")

                    # When a fill occurs, extract fill details from WS event fields.
                    # Per Gemini Fast API docs:
                    #   Z = CUMULATIVE executed base quantity for the order
                    #   L = price of the most recent execution (last fill price)
                    #   t = trade ID for the most recent execution
                    # Because `update_with_trade_update` accumulates `fill_base_amount`,
                    # we must convert the cumulative `Z` into a per-fill delta by
                    # subtracting what we've already tracked for this order. We also
                    # require a stable `t` to safely dedupe duplicate/stale events.
                    if order_status in ("PARTIALLY_FILLED", "FILLED"):
                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        trade_id_raw = event_message.get("t")
                        if tracked_order is not None and trade_id_raw not in (None, ""):
                            cumulative_z = Decimal(str(event_message.get("Z", "0")))
                            prior_filled = tracked_order.executed_amount_base
                            fill_amount = max(Decimal("0"), cumulative_z - prior_filled)
                            if fill_amount > Decimal("0"):
                                fill_price = Decimal(str(event_message["L"]))
                                trade_id = str(trade_id_raw)
                                is_maker = tracked_order.order_type in (
                                    OrderType.LIMIT, OrderType.LIMIT_MAKER)
                                fee = DeductedFromReturnsTradeFee(
                                    percent=self.estimate_fee_pct(is_maker=is_maker))
                                trade_update = TradeUpdate(
                                    trade_id=trade_id,
                                    client_order_id=client_order_id,
                                    exchange_order_id=str(event_message.get("i", "")),
                                    trading_pair=tracked_order.trading_pair,
                                    fee=fee,
                                    fill_base_amount=fill_amount,
                                    fill_quote_amount=fill_amount * fill_price,
                                    fill_price=fill_price,
                                    fill_timestamp=CONSTANTS.convert_timestamp_to_seconds(
                                        event_message.get("E", 0)),
                                )
                                self._order_tracker.process_trade_update(trade_update)

                    # Process order status update
                    tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if tracked_order is not None and order_status in CONSTANTS.ORDER_STATE:
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=CONSTANTS.convert_timestamp_to_seconds(
                                event_message.get("E", 0)),
                            new_state=CONSTANTS.ORDER_STATE[order_status],
                            client_order_id=client_order_id,
                            exchange_order_id=str(event_message.get("i", "")),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == CONSTANTS.WS_EVENT_BALANCE_UPDATE:
                    # Balance update: {"e": "balanceUpdate", "B": [{"a": "USD", "f": "207.39"}]}
                    for balance_entry in event_message.get("B", []):
                        asset_name = balance_entry.get("a", "")
                        if not asset_name:
                            continue
                        available = Decimal(str(balance_entry.get("f", "0")))
                        if available <= Decimal("0"):
                            # Mirror _update_balances: drop non-positive dust instead of
                            # tracking a negative/zero balance for the asset.
                            self._account_available_balances.pop(asset_name, None)
                            self._account_balances.pop(asset_name, None)
                        else:
                            self._account_available_balances[asset_name] = available
                            self._account_balances[asset_name] = available

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            try:
                all_fills_response = await self._api_post(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    data={
                        "request": CONSTANTS.MY_TRADES_PATH_URL,
                        "symbol": symbol,
                        "limit_trades": 500,
                    },
                    is_auth_required=True,
                    limit_id=CONSTANTS.MY_TRADES_PATH_URL)

                for trade in all_fills_response:
                    if str(trade.get("order_id", "")) == order.exchange_order_id:
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=order.trade_type,
                            percent_token=trade.get("fee_currency", ""),
                            flat_fees=[TokenAmount(
                                amount=Decimal(str(trade.get("fee_amount", "0"))),
                                token=trade.get("fee_currency", "")
                            )]
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade["tid"]),
                            client_order_id=order.client_order_id,
                            exchange_order_id=str(trade["order_id"]),
                            trading_pair=order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(str(trade["amount"])),
                            fill_quote_amount=Decimal(str(trade["amount"])) * Decimal(str(trade["price"])),
                            fill_price=Decimal(str(trade["price"])),
                            fill_timestamp=trade["timestampms"] * 1e-3,
                        )
                        trade_updates.append(trade_update)
            except Exception:
                self.logger().exception(f"Error fetching trades for order {order.client_order_id}")

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        if tracked_order.exchange_order_id is None:
            await tracked_order.get_exchange_order_id()
        updated_order_data = await self._api_post(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
            data={
                "request": CONSTANTS.ORDER_STATUS_PATH_URL,
                "order_id": int(tracked_order.exchange_order_id),
            },
            is_auth_required=True)

        # Determine the order state from the response
        if updated_order_data.get("is_cancelled", False):
            new_state = CONSTANTS.ORDER_STATE["cancelled"]
        elif updated_order_data.get("is_live", False):
            new_state = CONSTANTS.ORDER_STATE["live"]
        elif Decimal(str(updated_order_data.get("remaining_amount", "0"))) == Decimal("0"):
            new_state = CONSTANTS.ORDER_STATE["closed"]
        else:
            new_state = CONSTANTS.ORDER_STATE.get("live")

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["order_id"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_order_data.get("timestampms", 0) * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        try:
            account_info = await self._api_post(
                path_url=CONSTANTS.BALANCES_PATH_URL,
                data={
                    "request": CONSTANTS.BALANCES_PATH_URL,
                },
                is_auth_required=True)
        except Exception as e:
            if CONSTANTS.MISSING_ACCOUNTS_ERROR in str(e):
                # The key is a Master API key, which requires an "account" on every
                # payload. Hummingbot uses account-scoped keys, so guide the user instead
                # of surfacing the opaque "Expected a JSON payload with accounts" error.
                message = ("Gemini rejected the request because the API key is a Master API key. "
                           "Hummingbot requires an account-scoped (primary) API key: create one "
                           "under your Gemini account's API settings (not a Master key) and reconnect.")
                self.logger().error(message)
                raise IOError(message) from e
            self.logger().error(f"Error fetching Gemini balances: {e}", exc_info=True)
            raise

        for balance_entry in account_info:
            asset_name = balance_entry["currency"]
            # Skip derivative/contract currencies (e.g. "GEMI-BTC2602180800-HI70000")
            # as they contain hyphens that break hummingbot's trading pair parsing
            if "-" in asset_name:
                continue
            available_balance = Decimal(str(balance_entry["available"]))
            total_balance = Decimal(str(balance_entry["amount"]))
            # Gemini can report sub-cent negative dust (e.g. USD "-0.0020" from a fee on
            # unsettled funds). It is not a tradeable holding, so skip non-positive totals
            # rather than surfacing a confusing negative in the balance view and feeding a
            # negative figure into budget checks.
            if total_balance <= Decimal("0"):
                continue
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        # exchange_info is the response from /v1/symbols — a list of symbol strings like ["btcusd", "ethusd"]
        symbols = exchange_info if isinstance(exchange_info, list) else []
        for symbol in symbols:
            try:
                # Gemini symbols are lowercase concatenated, e.g., "btcusd"
                # We need to split them into base and quote currencies
                base, quote = self._split_gemini_symbol(symbol)
                if base and quote:
                    hb_pair = combine_to_hb_trading_pair(base=base.upper(), quote=quote.upper())
                    mapping[symbol] = hb_pair
            except Exception:
                self.logger().debug(f"Could not parse symbol {symbol}, skipping.")
        self._set_trading_pair_symbol_map(mapping)

    @staticmethod
    def _split_gemini_symbol(symbol: str) -> Tuple[str, str]:
        """
        Splits a Gemini symbol like 'btcusd' into ('btc', 'usd').
        Gemini uses well-known currency codes. Common quote currencies are:
        usd, btc, eth, gbp, eur, sgd, gusd, dai, usdt
        """
        symbol = symbol.lower()
        # Try known quote currencies (longest first to avoid ambiguity)
        known_quotes = ["gusd", "usdt", "usdc", "dai", "sgd", "gbp", "eur", "usd", "btc", "eth"]
        for quote in known_quotes:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base = symbol[:-len(quote)]
                return base, quote
        return "", ""

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PATH_URL.format(symbol),
            # the formatted path is not a registered limit id — without this the
            # throttler raises on the unknown id and the call bypasses the public budget
            limit_id=CONSTANTS.TICKER_PATH_URL,
        )

        return float(resp_json.get("close", resp_json.get("last", 0)))
