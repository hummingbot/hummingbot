import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.kalqix import (
    kalqix_constants as CONSTANTS,
    kalqix_utils as utils,
    kalqix_web_utils as web_utils,
)
from hummingbot.connector.exchange.kalqix.kalqix_api_order_book_data_source import KalqixAPIOrderBookDataSource
from hummingbot.connector.exchange.kalqix.kalqix_api_user_stream_data_source import (
    EVENT_ORDER_UPDATE,
    EVENT_TRADE,
    KalqixAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.kalqix.kalqix_auth import KalqixAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class KalqixExchange(ExchangePyBase):
    """KalqiX spot connector.

    REST-only — overrides Hummingbot's WS-driven user-stream pattern in
    the data source classes. Polling cadences live in
    `kalqix_constants.py`.

    Auth is two-layered (see `kalqix_auth.py`): the `KalqixAuth` instance
    appends HMAC headers to every REST request. State-changing requests
    (place + cancel) additionally carry a BIP-340 Schnorr signature over
    the action's canonical payload, signed with the agent-wallet private
    key. Building that signed payload is this class's responsibility —
    the auth class only handles the transport layer.
    """

    # Default polling cadence for the framework's status loop; overridden
    # by our user-stream poller for the per-order status updates.
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(
        self,
        kalqix_api_key: str,
        kalqix_api_secret: str,
        kalqix_agent_index: int,
        kalqix_agent_private_key: str,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.api_key = kalqix_api_key
        self.api_secret = kalqix_api_secret
        self.agent_index = int(kalqix_agent_index)
        self.agent_private_key = kalqix_agent_private_key
        self._domain = domain
        self._trading_required = trading_required
        # Normalize to a list — Hummingbot's bootstrap paths can hand us
        # `None` (e.g. before the user picks pairs in the CLI). Iteration
        # sites in the data sources also defend with `or []`, but
        # normalizing here keeps the property's return type honest.
        self._trading_pairs = trading_pairs if trading_pairs is not None else []
        # base_decimals, quote_decimals per trading pair — populated
        # from the /v1/markets response during _format_trading_rules and
        # used to scale Decimal price/quantity → base-unit integer
        # strings for the wire.
        self._market_decimals: Dict[str, Tuple[int, int]] = {}
        # Last-seen status + remaining_quantity per client_order_id, used
        # by _user_stream_event_listener to detect transitions across
        # successive open-order polls.
        self._last_seen_order_state: Dict[str, Dict[str, Any]] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)
        # The user-stream poll surfaces only order + trade events; balances are
        # refreshed by the framework's periodic REST balance poll, not pushed.
        # Declaring this False keeps the framework from expecting balance deltas
        # on the event stream.
        self._real_time_balance_update = False

    # ------------------------------------------------------------------
    # Identity / config
    # ------------------------------------------------------------------

    @property
    def authenticator(self) -> KalqixAuth:
        return KalqixAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            agent_index=self.agent_index,
            agent_private_key=self.agent_private_key,
            time_provider=self._time_synchronizer,
        )

    @property
    def name(self) -> str:
        return "kalqix" if self._domain == "com" else f"kalqix_{self._domain}"

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
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        # `_place_cancel` polls GET /orders/{id} right after the DELETE and only
        # returns True once the order is confirmed cancelled (or accepted for
        # cancellation), so by the time it returns the outcome is known and the
        # framework can finalize the cancel immediately. The open-orders poll
        # cannot report cancellations (a cancelled order leaves that feed), so
        # this confirmation has to happen here rather than via the user stream.
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        # LIMIT_MAKER (post-only) is not supported yet.
        return [OrderType.LIMIT, OrderType.MARKET]

    # ------------------------------------------------------------------
    # Hummingbot framework hooks
    # ------------------------------------------------------------------

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return KalqixAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return KalqixAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        # Conservative defaults; real fees come back on each order
        # response as `maker_fee_ppm` / `taker_fee_ppm`. Strategies that
        # need exact post-trade fees should read those from fill events.
        is_maker = is_maker if is_maker is not None else False
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # KalqiX rejects requests with `timestamp` outside ±5min as
        # `INVALID_TIMESTAMP`. Trigger a resync.
        return "INVALID_TIMESTAMP" in str(request_exception)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE in str(cancelation_exception)

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    async def _place_order(
        self,
        order_id: str,            # Hummingbot's client_order_id
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        ticker_body = utils.convert_to_exchange_ticker_body(trading_pair)
        side = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        type_str = CONSTANTS.ORDER_TYPE_LIMIT if order_type is OrderType.LIMIT else CONSTANTS.ORDER_TYPE_MARKET
        timestamp_ms = int(self._time_synchronizer.time() * 1e3)

        base_decimals, quote_decimals = self._decimals_for_pair(trading_pair)
        amount_base = str(int(amount * (10 ** base_decimals)))
        price_base = (
            str(int(price * (10 ** quote_decimals)))
            if order_type is OrderType.LIMIT
            else "0"
        )

        # Canonical payload for the BIP-340 Schnorr signature. client_order_id
        # is deliberately NOT in here — it's a tag, not a security boundary.
        signing_payload: Dict[str, Any] = {
            "action": "PLACE_ORDER",
            "agent_index": self.agent_index,
            "expires_at": 0,
            "order_type": type_str,
            "side": side,
            "ticker": ticker_body,
            "time_in_force": CONSTANTS.TIME_IN_FORCE_GTC,
            "timestamp": timestamp_ms,
        }
        if order_type is OrderType.LIMIT:
            signing_payload["price"] = price_base
            signing_payload["quantity"] = amount_base
        else:
            # MARKET — KalqiX accepts `quantity` for SELL and either
            # `quantity` or `quote_quantity` for BUY. Pass `quantity` for
            # both; market BUY in quote currency is not currently exposed
            # via Hummingbot's standard order interface.
            signing_payload["quantity"] = amount_base

        signature = self._auth.sign_payload(signing_payload)

        body: Dict[str, Any] = {
            **signing_payload,
            "signature": signature,
            "client_order_id": order_id,
        }

        response = await self._api_post(
            path_url=CONSTANTS.ORDERS_PATH_URL,
            data=body,
            is_auth_required=True,
        )

        # 201 → { order_id, client_order_id }. Use server order_id as
        # exchange_order_id; transact_time approximated by request
        # timestamp since KalqiX doesn't return a server timestamp on
        # placement.
        exchange_order_id = str(response["order_id"])
        return exchange_order_id, self._time_synchronizer.time()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        # order_id here is Hummingbot's client_order_id; we need the
        # exchange_order_id (server UUID) for the cancel path. The
        # framework populates `tracked_order.exchange_order_id` from the
        # _place_order return value above.
        exchange_order_id = tracked_order.exchange_order_id
        if exchange_order_id is None:
            # Place response hasn't arrived yet — defer; the framework
            # will retry on the next status poll.
            return False

        timestamp_ms = int(self._time_synchronizer.time() * 1e3)
        signing_payload: Dict[str, Any] = {
            "action": "CANCEL_ORDER",
            "agent_index": self.agent_index,
            "order_id": exchange_order_id,
            "timestamp": timestamp_ms,
        }
        signature = self._auth.sign_payload(signing_payload)

        params = {
            "agent_index": self.agent_index,
            "signature": signature,
            "timestamp": timestamp_ms,
        }

        try:
            await self._api_delete(
                path_url=CONSTANTS.ORDER_BY_ID_PATH_URL.format(id=exchange_order_id),
                params=params,
                is_auth_required=True,
                limit_id=CONSTANTS.ORDER_BY_ID_PATH_URL,
            )
        except IOError as error:
            # The server enqueues cancellation requests and rejects duplicates
            # with `400 "Your cancellation request is already received."` while
            # the engine processes the first one. The cancel IS in flight, so
            # fall through and confirm the terminal state below rather than
            # treating it as an error.
            if "already received" not in str(error).lower():
                raise

        # KalqiX settles the cancel asynchronously but quickly. Poll the
        # single-order endpoint to learn the real outcome before reporting back.
        return await self._confirm_cancellation(exchange_order_id)

    async def _confirm_cancellation(self, exchange_order_id: str) -> bool:
        """Poll GET /orders/{id} until the order reaches a terminal state.

        Returns True if the order is cancelled (or accepted for cancellation),
        False if it actually FILLED — so a fill that raced the cancel is never
        silently dropped (the framework keeps tracking it and the fill is
        reported through the user-trade poll). KalqiX returns the order object
        directly with a `status` field; `CANCELLATION_REQUESTED` is the
        transient pre-terminal state.
        """
        for _ in range(CONSTANTS.CANCEL_CONFIRM_MAX_POLLS):
            try:
                order = await self._api_get(
                    path_url=CONSTANTS.ORDER_BY_ID_PATH_URL.format(id=exchange_order_id),
                    is_auth_required=True,
                    limit_id=CONSTANTS.ORDER_BY_ID_PATH_URL,
                )
            except IOError:
                # Transient lookup failure — the DELETE was accepted, so stop
                # polling and let the framework finalize the cancel.
                break
            status = order.get("status")
            if status == "FILLED":
                return False
            if status in ("CANCELLED", "EXPIRED", "EXPIRED_IN_MATCH"):
                return True
            # CANCELLATION_REQUESTED / still resting — wait briefly and recheck.
            await self._sleep(CONSTANTS.CANCEL_CONFIRM_DELAY)
        # Accepted for cancellation but not yet terminal; the engine will
        # finalize it. Report success so the framework stops re-issuing.
        return True

    # ------------------------------------------------------------------
    # Trading rules + symbol mapping
    # ------------------------------------------------------------------

    async def _format_trading_rules(self, exchange_info_dict: Any) -> List[TradingRule]:
        """Parse `/v1/markets` response into TradingRule objects.

        KalqiX returns:
        - `tick_size`, `step_size` — already-formatted human-readable strings
          (e.g. `"0.01"`, `"0.00001"`). Use directly.
        - `min_quantity`, `min_trade_size` — base-unit integers WITH a
          `_formatted` human-readable string alongside; use the `_formatted`
          variant directly.
        """
        markets = exchange_info_dict if isinstance(exchange_info_dict, list) else exchange_info_dict.get("data", [])
        rules: List[TradingRule] = []
        for market in filter(utils.is_exchange_information_valid, markets):
            try:
                trading_pair = utils.convert_from_exchange_trading_pair(market["ticker"])
                self._market_decimals[trading_pair] = (
                    int(market["base_asset_decimals"]),
                    int(market["quote_asset_decimals"]),
                )
                rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(market.get("min_quantity_formatted", "0"))),
                        min_price_increment=Decimal(str(market.get("tick_size", "0"))),
                        min_base_amount_increment=Decimal(str(market.get("step_size", "0"))),
                        min_notional_size=Decimal(str(market.get("min_trade_size_formatted", "0"))),
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing market rule {market.get('ticker')}; skipping.")
        return rules

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Any):
        markets = exchange_info if isinstance(exchange_info, list) else exchange_info.get("data", [])
        mapping = bidict()
        for market in filter(utils.is_exchange_information_valid, markets):
            try:
                ticker = market["ticker"]  # `BTC/USDC`
                hb_pair = combine_to_hb_trading_pair(
                    base=market["base_asset"], quote=market["quote_asset"]
                )
                # On-wire symbol when going IN to the exchange (body form).
                mapping[ticker] = hb_pair
            except Exception:
                self.logger().exception(
                    f"Error building symbol map entry for {market.get('ticker')}; skipping."
                )
        self._set_trading_pair_symbol_map(mapping)

    # ------------------------------------------------------------------
    # Status, fills, balances
    # ------------------------------------------------------------------

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        # Prefer lookup by client_order_id (won't 404 if exchange_order_id
        # hasn't propagated yet). Returns paginated shape with 0 or 1
        # entries.
        response = await self._api_get(
            path_url=CONSTANTS.ORDERS_PATH_URL,
            params={"client_order_id": tracked_order.client_order_id},
            is_auth_required=True,
        )
        data = response.get("data") or []
        if not data:
            raise IOError(
                f"{CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE}: no order for "
                f"client_order_id={tracked_order.client_order_id}"
            )
        order = data[0]
        return self._order_update_from_kalqix_order(tracked_order, order)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        if order.exchange_order_id is None:
            return []
        path = CONSTANTS.ORDER_TRADES_PATH_URL.format(id=order.exchange_order_id)
        page_size = CONSTANTS.TRADES_MAX_PAGE_SIZE

        # Walk pages until the server returns an empty/short page (= end of
        # data) or we hit MAX_PAGES_PER_POLL (= defensive cap; logs and
        # returns what we have so a runaway response can't burn the
        # rate-limit bucket forever). Server clamps page_size at
        # TRADES_MAX_PAGE_SIZE — asking for more silently caps, so we use
        # the constant directly and treat a < page_size response as the
        # signal we've reached the end.
        collected: List[Dict[str, Any]] = []
        for page_idx in range(CONSTANTS.MAX_PAGES_PER_POLL):
            response = await self._api_get(
                path_url=path,
                params={"page": page_idx, "page_size": page_size},
                is_auth_required=True,
                limit_id=CONSTANTS.ORDER_TRADES_PATH_URL,
            )
            batch = response.get("data") or []
            if not batch:
                break
            collected.extend(batch)
            if len(batch) < page_size:
                break
        else:
            self.logger().warning(
                f"_all_trade_updates_for_order: hit MAX_PAGES_PER_POLL "
                f"({CONSTANTS.MAX_PAGES_PER_POLL}) for order "
                f"{order.exchange_order_id}; some fills may be missing on "
                f"this poll cycle (next poll will re-walk)."
            )

        # Deterministic order: oldest -> newest by timestamp, tie-break by
        # trade_id (string compare). The server doesn't guarantee any
        # particular ordering across pages.
        collected.sort(key=lambda t: (int(t.get("timestamp", 0)), str(t.get("trade_id", ""))))

        trade_updates: List[TradeUpdate] = []
        for trade in collected:
            fee_amount = Decimal(str(trade.get("fee_formatted", "0")))
            fee_token = order.quote_asset  # KalqiX fees are denominated in the quote
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=order.trade_type,
                flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)],
            )
            trade_updates.append(
                TradeUpdate(
                    trade_id=str(trade["trade_id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(str(trade["quantity_formatted"])),
                    fill_quote_amount=Decimal(str(trade["price_formatted"])) * Decimal(str(trade["quantity_formatted"])),
                    fill_price=Decimal(str(trade["price_formatted"])),
                    # Trade `timestamp` is microseconds since epoch;
                    # Hummingbot's fill_timestamp is seconds.
                    fill_timestamp=int(trade["timestamp"]) * 1e-6,
                )
            )
        return trade_updates

    async def _update_balances(self):
        """`/v1/positions` returns `{ data: [{ asset, available_formatted,
        locked_formatted, total_formatted, ... }, ...] }`."""
        response = await self._api_get(
            path_url=CONSTANTS.POSITIONS_PATH_URL,
            is_auth_required=True,
        )
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        for position in response.get("data") or []:
            asset = position["asset"]
            available = Decimal(str(position.get("available_formatted", "0")))
            total = Decimal(str(position.get("total_formatted", "0")))
            self._account_available_balances[asset] = available
            self._account_balances[asset] = total
            remote_asset_names.add(asset)
        # Clean up any locally-cached assets the server no longer reports.
        for asset in local_asset_names - remote_asset_names:
            self._account_available_balances.pop(asset, None)
            self._account_balances.pop(asset, None)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        ticker_url = utils.convert_to_exchange_ticker_path(trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.MARKET_PRICE_PATH_URL.format(ticker=ticker_url),
            params={},
            limit_id=CONSTANTS.MARKET_PRICE_PATH_URL,
        )
        return float(response.get("price_formatted") or response.get("price") or 0)

    async def _update_trading_fees(self):
        # KalqiX returns fees on each market via `/v1/markets`; we use
        # DEFAULT_FEES as a fallback and read per-order ppm fields from
        # the order response when needed. No active sync required.
        pass

    # ------------------------------------------------------------------
    # User-stream event handling
    # ------------------------------------------------------------------

    async def _user_stream_event_listener(self):
        """Consumes synthetic events from the user-stream data source's
        REST poller. Two event types (see kalqix_api_user_stream_data_source):

        - `ORDER_UPDATE`: full order doc. We detect transitions by
          comparing against `_last_seen_order_state` and emit OrderUpdate
          + a TradeUpdate-shaped event when remaining_quantity drops.
        - `TRADE`: full trade doc. Direct passthrough to
          `_order_tracker.process_trade_update`.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("event_type")
                if event_type == EVENT_ORDER_UPDATE:
                    await self._handle_order_update_event(event_message["order"])
                elif event_type == EVENT_TRADE:
                    await self._handle_trade_event(event_message["trade"])
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(1.0)

    async def _handle_order_update_event(self, order: Dict[str, Any]):
        client_order_id = order.get("client_order_id")
        if client_order_id is None:
            return  # placed outside Hummingbot — not tracked here
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if tracked_order is None:
            return

        new_state = CONSTANTS.ORDER_STATE.get(order.get("status"))
        if new_state is None:
            return

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self._time_synchronizer.time(),
            new_state=new_state,
            client_order_id=client_order_id,
            exchange_order_id=str(order.get("order_id")),
        )
        self._order_tracker.process_order_update(order_update=order_update)
        self._last_seen_order_state[client_order_id] = {
            "status": order.get("status"),
            "remaining_quantity": order.get("remaining_quantity"),
        }

    async def _handle_trade_event(self, trade: Dict[str, Any]):
        # Trade event from /v1/users/{wallet}/trades. The endpoint
        # returns the maker + taker order IDs and the role for the
        # authenticated user. Map to a TradeUpdate if the trade belongs
        # to one of our tracked orders.
        maker_id = trade.get("maker_order_id")
        taker_id = trade.get("taker_order_id")
        candidate_exchange_ids = {maker_id, taker_id} - {None}
        tracked_order = None
        for ex_id in candidate_exchange_ids:
            for order in self._order_tracker.all_fillable_orders.values():
                if order.exchange_order_id == ex_id:
                    tracked_order = order
                    break
            if tracked_order:
                break
        if tracked_order is None:
            return

        fee_amount = Decimal(str(trade.get("fee_formatted", "0")))
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=tracked_order.trade_type,
            flat_fees=[TokenAmount(amount=fee_amount, token=tracked_order.quote_asset)],
        )
        fill_qty = Decimal(str(trade["quantity_formatted"]))
        fill_price = Decimal(str(trade["price_formatted"]))
        trade_update = TradeUpdate(
            trade_id=str(trade["trade_id"]),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fee=fee,
            fill_base_amount=fill_qty,
            fill_quote_amount=fill_qty * fill_price,
            fill_price=fill_price,
            # Trade `timestamp` is microseconds since epoch;
            # Hummingbot's fill_timestamp is seconds.
            fill_timestamp=int(trade["timestamp"]) * 1e-6,
        )
        self._order_tracker.process_trade_update(trade_update)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _decimals_for_pair(self, trading_pair: str) -> Tuple[int, int]:
        decimals = self._market_decimals.get(trading_pair)
        if decimals is None:
            raise ValueError(
                f"Decimals not cached for {trading_pair}; trading rules must be "
                f"loaded (call _update_trading_rules) before placing orders."
            )
        return decimals

    def _order_update_from_kalqix_order(
        self,
        tracked_order: InFlightOrder,
        order: Dict[str, Any],
    ) -> OrderUpdate:
        new_state = CONSTANTS.ORDER_STATE.get(order["status"], tracked_order.current_state)
        return OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order["order_id"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self._time_synchronizer.time(),
            new_state=new_state,
        )
