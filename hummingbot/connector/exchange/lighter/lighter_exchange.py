import asyncio
import hashlib
import json
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Callable, Dict, List, Optional, Set, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS, lighter_web_utils as web_utils
from hummingbot.connector.exchange.lighter.lighter_api_order_book_data_source import LighterAPIOrderBookDataSource
from hummingbot.connector.exchange.lighter.lighter_api_user_stream_data_source import LighterAPIUserStreamDataSource
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterExchange(ExchangePyBase):
    web_utils = web_utils
    # Keep REST reconciliations conservative when private stream is connected.
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 30.0
    _HEALTHY_PRIVATE_STREAM_POLL_INTERVAL = 30.0
    TICK_INTERVAL_LIMIT = 180.0
    BALANCE_SYNC_REQUIRED_TIMEOUT = 3.0
    _MARKET_ORDER_MAX_SLIPPAGE = Decimal("5")  # 5%
    _TRADE_HISTORY_TIME_DRIFT_BUFFER = 10.0  # seconds
    # Lighter on-chain cancel TX takes ~29 s to confirm.  Any CANCELED WS event for an
    # order younger than this threshold is almost certainly a subscription snapshot replay
    # (false cancel) rather than a real user-initiated cancellation.  555 ms is the
    # observed maximum false-cancel latency; 10 s gives a 18× safety margin well below
    # the 29 s minimum real-cancel latency.
    _CANCEL_MIN_ORDER_AGE_SECS: float = 10.0
    _ORDER_STATE = {
        "in-progress": OrderState.OPEN,
        "open": OrderState.OPEN,
        "pending": OrderState.PENDING_CREATE,
        "partially_filled": OrderState.PARTIALLY_FILLED,
        "partial_fill": OrderState.PARTIALLY_FILLED,
        "filled": OrderState.FILLED,
        "closed": OrderState.CANCELED,
        "done": OrderState.CANCELED,
        "cancelled": OrderState.CANCELED,
        "canceled": OrderState.CANCELED,
        "canceled-post-only": OrderState.CANCELED,
        "canceled-reduce-only": OrderState.CANCELED,
        "canceled-position-not-allowed": OrderState.CANCELED,
        "canceled-margin-not-allowed": OrderState.CANCELED,
        "canceled-too-much-slippage": OrderState.CANCELED,
        "canceled-not-enough-liquidity": OrderState.CANCELED,
        "canceled-self-trade": OrderState.CANCELED,
        "canceled-expired": OrderState.CANCELED,
        "canceled-oco": OrderState.CANCELED,
        "canceled-child": OrderState.CANCELED,
        "canceled-liquidation": OrderState.CANCELED,
        "canceled-invalid-balance": OrderState.CANCELED,
        "pending_cancel": OrderState.PENDING_CANCEL,
        "rejected": OrderState.FAILED,
        "failed": OrderState.FAILED,
        "expired": OrderState.FAILED,
    }

    @staticmethod
    def _is_expected_order_rejection(error_message: str) -> bool:
        normalized = (error_message or "").lower()
        expected_patterns = (
            "minimum notional",
            "minimum lot size",
            "invalid order base or quote amount",
            "below the minimum",
            "order amount",
            "order notional",
            "insufficient",
            "balance refresh",
            "stale-balance rejects",
        )
        return any(pattern in normalized for pattern in expected_patterns)

    def __init__(
        self,
        lighter_account_index: str = "",
        lighter_api_key_index: str = "",
        lighter_api_key_public_key: str = "",
        lighter_api_key_private_key: str = "",
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._api_key = lighter_api_key_private_key
        self._api_secret = lighter_api_key_index
        self._account_index = lighter_account_index
        self._api_key_index = lighter_api_key_index
        self._api_key_public_key = lighter_api_key_public_key
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []
        self._exchange_symbol_map = bidict()
        self._market_id_by_symbol: Dict[str, int] = {}
        self._size_decimals_by_symbol: Dict[str, int] = {}
        self._price_decimals_by_symbol: Dict[str, int] = {}
        self._signer_client_lock = asyncio.Lock()
        self._lighter_signer_client = None
        self._cached_auth_token: Optional[str] = None
        self._cached_auth_token_expiry_ts: float = 0.0
        self._order_history_last_poll_timestamp: Dict[str, float] = {}
        self._last_trades_poll_timestamp: float = 0.0
        self._last_private_stream_balance_sync_ts: float = 0.0
        self._last_unmatched_private_event_reconcile_ts: float = 0.0
        self._last_balance_update_timestamp: float = 0.0
        self._balance_refresh_required_since: float = 0.0
        self._last_ws_balance_update_ts: float = 0.0
        self._last_signed_tx_ts: float = 0.0
        self._cancel_in_flight_client_order_ids: Set[str] = set()
        initial_index = int(time.time() * 1000) * getattr(self, "_CLIENT_ORDER_INDEX_TIME_MULTIPLIER", 140)
        self._last_client_order_index: int = min(initial_index, getattr(self, "_CLIENT_ORDER_INDEX_MAX", (1 << 48) - 1) - 1_000_000)
        # Bidirectional mapping between Lighter's numeric client_order_index and hummingbot's
        # client_order_id (UUID string).  Required because WS events may update exchange_order_id
        # from the original client_order_index to the server-assigned order_id, breaking fill
        # matching in REST rescue polls that use ask_client_id / bid_client_id (= client_order_index).
        self._client_order_index_to_client_order_id: Dict[str, str] = {}  # str(coi) → hb UUID
        self._hb_order_id_to_client_order_index: Dict[str, int] = {}       # hb UUID → coi int
        # Reverse map: server-assigned order_index ("i" in WS) → client_order_index string.
        # Populated when a WS order update carries both "I" (COI) and "i" (server order_index)
        # so that compact account_trades fills (which only carry "i") can still be matched.
        self._server_order_index_to_client_order_index: Dict[str, str] = {}  # str(server_oi) → str(coi)
        # One-time startup flag: cancel untracked active orders left from previous sessions.
        self._startup_orphan_cleanup_done: bool = False
        # Counter for periodic runtime orphan cleanup (runs every 10 status-poll cycles ~2 min).
        self._runtime_orphan_poll_counter: int = 0
        # Dedup guard: tracks orders for which a fill fetch is currently in-flight.
        # Prevents concurrent /trades calls for the same order from bursting the rate limit.
        self._fill_fetch_in_progress: Set[str] = set()
        # Buffer for account_trades WS fill entries that arrived before account_all established
        # the client_order_index → client_order_id mapping (mirrors PERP's _pending_trade_entries).
        self._pending_spot_trade_entries: List[Tuple[float, Dict[str, Any]]] = []
        # Guard against stale account_all_assets WS events overwriting an optimistic balance
        # release made by _release_locked_balance_on_cancel.  Maps asset symbol → (available, ts)
        # where `available` is the value set by the optimistic release and `ts` is wall time.
        # _process_balance_message_from_account uses this to avoid reverting a fresh release.
        self._optimistic_balance_release: Dict[str, Tuple[Decimal, float]] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @staticmethod
    def _client_order_index_from_order_id(order_id: str) -> int:
        digest = hashlib.sha256(order_id.encode()).digest()
        # Lighter API enforces client_order_index <= 2^48-1 (281474976710655)
        return int.from_bytes(digest[:8], byteorder="big", signed=False) & ((1 << 48) - 1)

    @staticmethod
    def _is_int_string(value: str) -> bool:
        if value is None:
            return False
        try:
            int(str(value).strip())
            return True
        except Exception:
            return False

    def _get_signer_private_key(self) -> str:
        if self._api_key and not self._is_int_string(self._api_key) and self._is_hex_private_key(self._api_key):
            return self._api_key
        raise ValueError(
            "API private key is required for signed transactions. "
            "Enter your signing key via connect lighter."
        )

    @staticmethod
    def _is_hex_private_key(value: str) -> bool:
        """Return True only if value is a 64-char hex string (valid signer private key)."""
        if not value:
            return False
        key = value[2:] if value.lower().startswith("0x") else value
        return len(key) >= 64 and all(c in "0123456789abcdefABCDEF" for c in key)

    def _api_host_for_signer(self) -> str:
        rest_url = CONSTANTS.REST_URL if self.domain == CONSTANTS.DEFAULT_DOMAIN else CONSTANTS.TESTNET_REST_URL
        return rest_url.split("/api/v1")[0]

    def _sdk_rest_base_url(self) -> str:
        return self._api_host_for_signer()

    def _get_lighter_api_client(self):
        if getattr(self, "_lighter_api_client", None) is None:
            import lighter

            configuration = lighter.Configuration(host=self._sdk_rest_base_url())
            self._lighter_api_client = lighter.ApiClient(configuration=configuration)

        return self._lighter_api_client

    async def _close_lighter_api_client(self):
        api_client = getattr(self, "_lighter_api_client", None)
        if api_client is not None:
            await api_client.close()
            self._lighter_api_client = None

    async def _sdk_api_request(
        self,
        path_url: str,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        limit_id: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
        return_err: bool = False,
    ) -> Dict[str, Any]:
        api_client = self._get_lighter_api_client()
        request_headers = dict(headers or {})

        if data is not None and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"

        serialized_request = api_client.param_serialize(
            method=method.value,
            resource_path=f"/api/v1{path_url}",
            query_params=params,
            header_params=request_headers,
            body=data,
            _host=self._sdk_rest_base_url(),
        )

        throttler = getattr(self, "_throttler", None)
        limit_context = throttler.execute_task(limit_id=limit_id or path_url) if throttler is not None else None

        try:
            if limit_context is None:
                response = await api_client.call_api(*serialized_request)
            else:
                async with limit_context:
                    response = await api_client.call_api(*serialized_request)
            await response.read()
            raw_body = response.data.decode("utf-8") if response.data else ""
            payload: Any = json.loads(raw_body) if raw_body else {}
        except Exception as request_exception:
            if return_err:
                return {
                    "success": False,
                    "error": str(request_exception),
                    "code": getattr(request_exception, "status", None),
                }
            raise IOError(f"Error executing Lighter SDK request {method.value} {path_url}: {request_exception}")

        if not isinstance(payload, dict):
            payload = {"data": payload}

        payload.setdefault("code", getattr(response, "status", None))
        payload.setdefault("success", int(payload.get("code") or 0) < 400)

        if int(payload.get("code") or 0) >= 400 and not return_err:
            if int(payload.get("code") or 0) == 23000:
                # Server rate limit (Too Many Requests). Sleep before raising so that
                # the status-polling loop's immediate retry does not create a cascade of
                # back-to-back 429 errors. The base class re-schedules the next poll via
                # its normal interval after the exception propagates.
                await asyncio.sleep(3.0)
            raise IOError(f"Lighter SDK request failed for {method.value} {path_url}: {payload}")

        return payload

    def _get_api_key_index(self) -> int:
        api_key_index = getattr(self, "_api_key_index", "")
        if self._is_int_string(api_key_index):
            return int(api_key_index)
        raise ValueError(
            "API key index must be an integer. Enter it via connect lighter."
        )

    def _get_account_index(self) -> int:
        try:
            return int(str(self._account_index).strip())
        except Exception as e:
            raise ValueError("Lighter account index must be an integer string") from e

    @staticmethod
    def _is_ok_response(response: Dict[str, Any]) -> bool:
        if response.get("success") is True:
            return True
        code = response.get("code")
        try:
            return int(code) == 200
        except Exception:
            return False

    @staticmethod
    def _is_rate_limited_response(response: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(response, dict):
            return False

        code = response.get("code")
        if str(code) in {"23000", "429"}:
            return True

        message = str(response.get("message") or response.get("error") or "")
        return "too many requests" in message.lower()

    @classmethod
    def _is_rate_limited_exception(cls, request_error: Exception) -> bool:
        return cls._is_rate_limited_response({"message": str(request_error)})

    def _current_state_order_update(self, tracked_order: InFlightOrder) -> OrderUpdate:
        update_ts = getattr(self, "current_timestamp", None)
        if update_ts is None:
            update_ts = self._time()

        return OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_ts,
            new_state=getattr(tracked_order, "current_state", OrderState.OPEN),
        )

    def _account_query_params(self) -> Dict[str, Any]:
        return {
            "by": "index",
            "value": str(self._get_account_index()),
            "active_only": "true",
        }

    @staticmethod
    def _account_from_response(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = response.get("data")
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            return data[0]
        accounts = response.get("accounts")
        if isinstance(accounts, list) and len(accounts) > 0:
            return accounts[0]
        # Lighter API returns the account object directly (assets at top level)
        if "assets" in response or "collateral" in response or "available_balance" in response:
            return response
        return None

    def _get_lighter_signer_client(self):
        if self._lighter_signer_client is None:
            import lighter

            self._lighter_signer_client = lighter.signer_client.SignerClient(
                url=self._api_host_for_signer(),
                account_index=self._get_account_index(),
                api_private_keys={self._get_api_key_index(): self._get_signer_private_key()},
            )

        return self._lighter_signer_client

    def _get_lighter_auth_token(self) -> str:
        now = float(getattr(self, "current_timestamp", time.time()))
        cached_auth_token = getattr(self, "_cached_auth_token", None)
        cached_auth_token_expiry_ts = float(getattr(self, "_cached_auth_token_expiry_ts", 0.0) or 0.0)
        if cached_auth_token and now < cached_auth_token_expiry_ts:
            return cached_auth_token

        signer_client = self._get_lighter_signer_client()
        auth_token, error = signer_client.create_auth_token_with_expiry()
        if error is not None or not auth_token:
            raise IOError(f"Failed to generate Lighter auth token: {error}")

        self._cached_auth_token = auth_token
        # Refresh slightly before default 10-minute expiry.
        self._cached_auth_token_expiry_ts = now + 9 * 60
        return auth_token

    async def stop_network(self):
        await super().stop_network()
        await self._close_lighter_api_client()

    async def _refresh_market_metadata(self):
        response = await self._api_get(
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            return_err=True,
        )

        for market in response.get("order_books", []) or response.get("data", []):
            market_type = str(market.get("market_type") or "").lower()
            if market_type and market_type != "spot":
                continue

            symbol = market.get("symbol")
            if symbol is None:
                continue

            self._market_id_by_symbol[symbol] = int(market["market_id"])
            self._size_decimals_by_symbol[symbol] = int(market.get("supported_size_decimals", 0))
            self._price_decimals_by_symbol[symbol] = int(market.get("supported_price_decimals", 0))

    async def _get_market_spec(self, trading_pair: str) -> Tuple[int, int, int, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        if symbol not in self._market_id_by_symbol:
            await self._refresh_market_metadata()

        if symbol not in self._market_id_by_symbol:
            raise ValueError(f"Market metadata not found for symbol {symbol}")

        return (
            self._market_id_by_symbol[symbol],
            self._size_decimals_by_symbol.get(symbol, 0),
            self._price_decimals_by_symbol.get(symbol, 0),
            symbol,
        )

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> LighterAuth:
        account_identifier = self._api_key_public_key if self._api_key_public_key else self._account_index
        return LighterAuth(
            api_key=self.rest_api_key,
            api_secret=self._api_secret,
            account_identifier=account_identifier,
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        # Lighter applies lighter-weight costs when requests are authenticated with an API key.
        return CONSTANTS.RATE_LIMITS_TIER_2 if self.rest_api_key else CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    async def all_trading_pairs(self) -> List[str]:
        """
        Returns all active spot trading pairs available on the Lighter exchange.
        Uses the /orderBooks endpoint (same as _initialize_trading_pair_symbols_from_exchange_info)
        which is stable on both mainnet and testnet.
        """
        try:
            result = await self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)
            entries = result.get("data") or result.get("order_books") or []
            pairs = []
            for entry in entries:
                market_type = (entry.get("market_type") or "").lower()
                if market_type and market_type != "spot":
                    continue
                symbol = entry.get("symbol")
                if symbol:
                    pairs.append(self._hb_pair_from_symbol(symbol))
            return pairs
        except Exception:
            return []

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def rest_api_key(self) -> str:
        api_key = getattr(self, "_api_key", "")
        api_secret = getattr(self, "_api_secret", "")
        if self._is_int_string(api_key):
            return str(api_key)
        if self._is_int_string(api_secret):
            return str(api_secret)
        return api_key

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "not found" in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        error_text = str(cancelation_exception).lower()
        # Lighter API error code 5 = order not found / already cancelled.
        # Error can appear as JSON (double-quotes) or Python dict repr (single-quotes).
        if '"code":5' in error_text or "'code': 5" in error_text or '"code": 5' in error_text:
            return True
        # "order not found" literal embedded in exchange error messages.
        if "order not found" in error_text:
            return True
        return False

    @staticmethod
    def _hb_pair_from_symbol(symbol: str) -> str:
        if "/" in symbol:
            base, quote = symbol.split("/", 1)
            return combine_to_hb_trading_pair(base=base, quote=quote)
        if "-" in symbol:
            base, quote = symbol.split("-", 1)
            return combine_to_hb_trading_pair(base=base, quote=quote)
        return symbol

    # Lighter on-chain TX confirmation takes ~29 seconds. The HTTP body (signed TX) is
    # submitted in <100ms; the long wait is for sequencer inclusion. We apply a short
    # asyncio.wait_for timeout so that once the TX is submitted we return True immediately
    # and let the base class emit CANCELED. The order moves to cached_orders (fills within
    # the TTL are still processed). This prevents 90-second delays from a hung connection.
    _CANCEL_TX_OPTIMISTIC_TIMEOUT = 5.0  # seconds; body is sent before this fires

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        if tracked_order.exchange_order_id is None:
            return False

        market_id, _, _, _ = await self._get_market_spec(tracked_order.trading_pair)

        cancel_succeeded = False
        async with self._signer_client_lock:
            signer_client = self._get_lighter_signer_client()
            tx_response = None
            error = None
            for attempt in range(3):
                # Re-check after awaits in case order tracking clears the exchange id concurrently.
                exchange_order_id = tracked_order.exchange_order_id
                if exchange_order_id is None:
                    return False

                try:
                    _, tx_response, error = await asyncio.wait_for(
                        signer_client.cancel_order(
                            market_index=market_id,
                            order_index=int(exchange_order_id),
                            api_key_index=self._get_api_key_index(),
                        ),
                        timeout=self._CANCEL_TX_OPTIMISTIC_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    # Do not mark CANCELED optimistically on timeout. A timed-out HTTP await
                    # means TX submission may be in-flight, but exchange terminal state is not
                    # confirmed yet. Let _execute_order_cancel reconcile state first.
                    raise IOError(
                        f"Lighter spot cancel_order timed out for order {order_id} before confirmation"
                    )

                if error is None and self._response_code(tx_response) == 200:
                    cancel_succeeded = True
                    break  # release signer lock before REST fill-fetch

                if attempt < 2 and self._is_invalid_nonce_failure(error=error, response=tx_response):
                    # Nonce refresh may fail during transient DNS/network issues.
                    # Keep the existing signer client and retry instead of failing fast.
                    try:
                        signer_client = await self._refresh_signer_client_async()
                    except Exception as refresh_error:
                        self.logger().warning(
                            f"Failed to refresh signer client after invalid nonce for {order_id}: {refresh_error}. "
                            f"Retrying cancel with existing signer client."
                        )
                    await self._sleep(0.3)
                    continue
                break

        if cancel_succeeded:
            # Fetch fills OUTSIDE the signer lock: REST calls must not hold the signing lock.
            # Start with delay=0 — if the fill was already indexed (happened ≥9 s before cancel
            # submission), the immediate attempt finds it and emits OrderFilledEvent before
            # OrderCancelledEvent so strategy accounting stays correct.  The internal retry
            # logic of _fetch_and_apply_fills handles the case where REST has not indexed the
            # fill yet (retries at +8 s and +16 s).
            try:
                pre_cancel_fills = await self._all_trade_updates_for_order(tracked_order)
                for fill_update in pre_cancel_fills:
                    self._order_tracker.process_trade_update(fill_update)
                if pre_cancel_fills:
                    self.logger().info(
                        "[cancel] Found %d fill(s) for %s before marking CANCELED — cancel-fill race handled",
                        len(pre_cancel_fills),
                        tracked_order.client_order_id,
                    )
                else:
                    # No fills indexed yet. Start a background retry loop: _fetch_and_apply_fills
                    # will check immediately (delay=0) and then retry every 8 s as needed.
                    safe_ensure_future(self._fetch_and_apply_fills(tracked_order, delay=0.0))
            except Exception as fill_err:
                self.logger().debug(
                    "[cancel] Pre-cancel fill fetch failed for %s: %s",
                    tracked_order.client_order_id,
                    fill_err,
                )
                # Still schedule a background retry so fills are not permanently lost.
                safe_ensure_future(self._fetch_and_apply_fills(tracked_order, delay=8.0))
            optimistic_cancel_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self._current_timestamp_safely(),
                new_state=OrderState.CANCELED,
            )
            self._schedule_balance_sync_for_terminal_update(
                order_update=optimistic_cancel_update,
                tracked_order=tracked_order,
            )
            return True

        if error is not None:
            raise IOError(f"Lighter spot cancel_order signing/send failed: {error}")
        if tx_response is None or getattr(tx_response, "code", None) != 200:
            raise IOError(f"Lighter spot cancel_order failed: {tx_response}")

        return True

    async def _place_modify(self, tracked_order: InFlightOrder, amount: Decimal, price: Decimal) -> bool:
        """Modify existing order via signer client."""
        if tracked_order.exchange_order_id is None:
            return False

        market_id, size_decimals, price_decimals, _ = await self._get_market_spec(tracked_order.trading_pair)

        base_amount_scaled = int((amount * Decimal(f"1e{size_decimals}")).to_integral_value())
        price_scaled = int((price * Decimal(f"1e{price_decimals}")).to_integral_value())

        async with self._signer_client_lock:
            signer_client = self._get_lighter_signer_client()
            tx_response = None
            error = None
            for attempt in range(5):
                # Re-check after awaits in case order tracking clears the exchange id concurrently.
                exchange_order_id = tracked_order.exchange_order_id
                if exchange_order_id is None:
                    return False

                _, tx_response, error = await signer_client.modify_order(
                    market_index=market_id,
                    order_index=int(exchange_order_id),
                    base_amount=base_amount_scaled,
                    price=price_scaled,
                    api_key_index=self._get_api_key_index(),
                )
                if error is None and self._response_code(tx_response) == 200:
                    break
                if attempt < 4 and self._is_invalid_nonce_failure(error=error, response=tx_response):
                    signer_client = await self._refresh_signer_client_async()
                    await self._sleep(0.3)
                    continue
                break

        if error is not None:
            raise IOError(f"Lighter spot modify_order signing/send failed: {error}")
        if tx_response is None or getattr(tx_response, "code", None) != 200:
            raise IOError(f"Lighter spot modify_order failed: {tx_response}")

        return True

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            slippage = self._MARKET_ORDER_MAX_SLIPPAGE / Decimal("100")
            price = self.quantize_order_price(trading_pair, reference_price * (Decimal("1") + slippage))
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
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            slippage = self._MARKET_ORDER_MAX_SLIPPAGE / Decimal("100")
            price = self.quantize_order_price(trading_pair, reference_price * (Decimal("1") - slippage))
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

    async def _ensure_fresh_balance_snapshot_before_order(self, trade_type: TradeType):
        # Avoid submitting BUY orders with stale balances right after terminal
        # order updates (cancel/fill/failure), when local availability may lag.
        if trade_type != TradeType.BUY:
            return

        required_since = float(getattr(self, "_balance_refresh_required_since", 0.0) or 0.0)
        if required_since <= 0:
            return

        # A recent account_all_assets WS push is authoritative — treat it as a fresh REST snapshot.
        last_ws_balance_ts = float(getattr(self, "_last_ws_balance_update_ts", 0.0) or 0.0)
        if last_ws_balance_ts >= required_since:
            self._balance_refresh_required_since = 0.0
            return

        last_balance_ts = float(getattr(self, "_last_balance_update_timestamp", 0.0) or 0.0)
        if last_balance_ts >= required_since:
            return

        try:
            await asyncio.wait_for(
                self._update_balances(force_rest=True),
                timeout=self.BALANCE_SYNC_REQUIRED_TIMEOUT,
            )
        except Exception as balance_error:
            raise IOError(
                "Balance refresh is pending after a terminal order update. "
                "Skipping BUY order submission to avoid stale-balance rejects."
            ) from balance_error

        if float(getattr(self, "_last_balance_update_timestamp", 0.0) or 0.0) < required_since:
            raise IOError(
                "Balance refresh is still pending after a terminal order update. "
                "Skipping BUY order submission to avoid stale-balance rejects."
            )

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        # Guard moved here from _create_order so that start_tracking_order() in the base class
        # _create_order() always runs first.  This ensures that if the balance refresh fails
        # (e.g., 429 Too Many Requests), the base class _on_order_failure() is called and a
        # MarketOrderFailureEvent is emitted — clearing the order from the strategy and preventing
        # the "ghost order" cancel loop that occurred when the exception escaped _create_order
        # before start_tracking_order() was called.
        await self._ensure_fresh_balance_snapshot_before_order(trade_type=trade_type)
        if order_type not in self.supported_order_types():
            raise ValueError(f"Order type {order_type} is not supported by {self.name}.")

        market_id, size_decimals, price_decimals, _ = await self._get_market_spec(trading_pair)

        # Resolve effective price; for MARKET orders apply a slippage cap
        effective_price = price
        if order_type == OrderType.MARKET or effective_price is None or effective_price.is_nan():
            order_book = self.get_order_book(trading_pair)
            best_price = (
                Decimal(str(order_book.get_price(True)))
                if trade_type == TradeType.BUY
                else Decimal(str(order_book.get_price(False)))
            )
            if best_price is None or best_price.is_nan() or best_price <= 0:
                raise ValueError(
                    f"Unable to determine a valid execution price for {order_type.name} order on {trading_pair}."
                )
            slippage = self._MARKET_ORDER_MAX_SLIPPAGE / Decimal("100")
            if trade_type == TradeType.BUY:
                effective_price = best_price * (Decimal("1") + slippage)
            else:
                effective_price = best_price * (Decimal("1") - slippage)

        # Validate sufficient balance (skip for MARKET — price is already capped)
        if trade_type == TradeType.BUY and order_type != OrderType.MARKET:
            quote_asset = trading_pair.split("-")[-1]
            required_balance = amount * effective_price
            available_balances = getattr(self, "_account_available_balances", None)
            if available_balances is not None:
                available_balance = available_balances.get(quote_asset, Decimal("0"))
                if available_balance < required_balance:
                    raise IOError(
                        f"Insufficient {quote_asset} balance for {amount} {trading_pair.split('-')[0]} buy order. "
                        f"Required: {required_balance}, Available: {available_balance}"
                    )

        base_amount_scaled = int((amount * Decimal(f"1e{size_decimals}")).to_integral_value())
        price_scaled = int((effective_price * Decimal(f"1e{price_decimals}")).to_integral_value())

        signer_order_type = self._get_lighter_signer_client().ORDER_TYPE_LIMIT
        signer_tif = self._get_lighter_signer_client().ORDER_TIME_IN_FORCE_GOOD_TILL_TIME
        order_expiry = self._get_lighter_signer_client().DEFAULT_28_DAY_ORDER_EXPIRY
        if order_type == OrderType.MARKET:
            signer_order_type = self._get_lighter_signer_client().ORDER_TYPE_MARKET
            signer_tif = self._get_lighter_signer_client().ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL
            order_expiry = self._get_lighter_signer_client().DEFAULT_IOC_EXPIRY
        elif order_type == OrderType.LIMIT_MAKER:
            signer_tif = self._get_lighter_signer_client().ORDER_TIME_IN_FORCE_POST_ONLY

        async with self._signer_client_lock:
            signer_client = self._get_lighter_signer_client()
            client_order_index = self._allocate_client_order_index()
            tx_response = None
            error = None
            for attempt in range(5):
                _, tx_response, error = await signer_client.create_order(
                    market_index=market_id,
                    client_order_index=client_order_index,
                    base_amount=base_amount_scaled,
                    price=price_scaled,
                    is_ask=(trade_type == TradeType.SELL),
                    order_type=signer_order_type,
                    time_in_force=signer_tif,
                    reduce_only=False,
                    order_expiry=order_expiry,
                    api_key_index=self._get_api_key_index(),
                )
                if error is None and self._response_code(tx_response) == 200:
                    break
                if attempt < 4 and self._is_invalid_nonce_failure(error=error, response=tx_response):
                    signer_client = await self._refresh_signer_client_async()
                    client_order_index = self._allocate_client_order_index()
                    await self._sleep(0.3)
                    continue
                break

        if error is not None:
            raise IOError(f"Lighter spot create_order signing/send failed: {error}")
        if tx_response is None or self._response_code(tx_response) != 200:
            raise IOError(f"Lighter spot create_order failed: {tx_response}")

        # Record the bidirectional mapping so fill-matching works even after WS events update
        # exchange_order_id from this client_order_index to the server-assigned order_id.
        coi_str = str(client_order_index)
        if hasattr(self, "_client_order_index_to_client_order_id"):
            self._client_order_index_to_client_order_id[coi_str] = order_id
        if hasattr(self, "_hb_order_id_to_client_order_index"):
            self._hb_order_id_to_client_order_index[order_id] = client_order_index

        # Optimistically deduct the allocated balance so the strategy immediately sees the
        # correct available capital before the async REST/WS balance sync completes.
        # Mirrors _release_locked_balance_on_cancel in reverse (lock instead of unlock).
        self._lock_balance_on_order_creation(trading_pair, amount, effective_price, trade_type)

        # Refresh balance so locked/available display updates immediately after order placement.
        self._schedule_fast_balance_sync()

        return str(client_order_index), self.current_timestamp

    def _on_order_failure(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Optional[Decimal],
        exception: Exception,
        **kwargs,
    ):
        error_message = str(exception)
        if self._is_expected_order_rejection(error_message=error_message):
            self.logger().debug(
                "Order rejected by exchange (expected validation) for %s %s %s @ %s: %s",
                trade_type.name,
                amount,
                trading_pair,
                price,
                error_message,
            )
            self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair, exception=exception)
            return

        super()._on_order_failure(
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            trade_type=trade_type,
            order_type=order_type,
            price=price,
            exception=exception,
            **kwargs,
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
    ) -> AddedToCostTradeFee:
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order_side,
            percent_token=quote_currency,
            percent=Decimal("0"),
            flat_fees=[TokenAmount(token=quote_currency, amount=Decimal("0"))],
        )
        return fee

    async def _update_trading_fees(self):
        return

    def _get_poll_interval(self, timestamp: float) -> float:
        # Use a slower cadence while the private stream is healthy to avoid
        # redundant REST polling between strategy refresh cycles.
        if len(self.in_flight_orders) > 0:
            return (
                self._HEALTHY_PRIVATE_STREAM_POLL_INTERVAL
                if self._is_private_user_stream_healthy()
                else self.SHORT_POLL_INTERVAL
            )
        return super()._get_poll_interval(timestamp)

    async def _user_stream_event_listener(self):

        def _looks_like_fill(t: Dict[str, Any]) -> bool:
            """Return True if t appears to be a fill event worth buffering for replay."""
            return bool(
                (t.get("i") or t.get("h"))         # compact: server_order_index or trade hash
                and (t.get("p") or t.get("price"))  # price present
                and (t.get("a") or t.get("size") or t.get("amount"))  # amount present
            )

        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    continue

                # Determine whether this event came from the standalone account_trades channel.
                # Fills from account_trades that arrive before account_all establishes the
                # client_order_index → client_order_id mapping are buffered and replayed after
                # the order updates in the same or subsequent event processing cycle.
                # Mirrors the PERP connector's _pending_trade_entries pattern.
                _ev_channel = str(event_message.get("channel", ""))
                _ev_type = str(event_message.get("type", ""))
                _ev_type_name = _ev_type.split("/", 1)[1] if "/" in _ev_type else _ev_type
                _is_account_trades_event = (
                    _ev_channel.startswith(f"{CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL}:")
                    or _ev_channel.startswith(f"{CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL}/")
                    or _ev_channel == CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL
                    or _ev_type_name == CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL
                )
                # account_all_trades: SPOT real-time fill channel with full Trade JSON
                # (ask_client_id/bid_client_id = COI).  No auth required.  Enables O(1)
                # instant fill matching via _client_order_index_to_client_order_id map.
                _is_account_all_trades_event = (
                    _ev_channel.startswith(f"{CONSTANTS.WS_ACCOUNT_ALL_TRADES_CHANNEL}:")
                    or _ev_channel.startswith(f"{CONSTANTS.WS_ACCOUNT_ALL_TRADES_CHANNEL}/")
                    or _ev_channel == CONSTANTS.WS_ACCOUNT_ALL_TRADES_CHANNEL
                    or _ev_type_name == CONSTANTS.WS_ACCOUNT_ALL_TRADES_CHANNEL
                )
                _is_any_trades_channel_event = _is_account_trades_event or _is_account_all_trades_event
                # account_all_orders sends a history snapshot on subscribe (false-cancel source).
                # account_order_updates sends ONLY real-time events — no snapshot, no false cancels.
                _is_account_all_orders_event = (
                    _ev_channel.startswith(f"{CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL}:")
                    or _ev_channel.startswith(f"{CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL}/")
                    or _ev_channel == CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL
                    or _ev_type_name == CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL
                )

                account_data, trades, orders = self._extract_private_stream_payloads(event_message=event_message)
                has_assets_payload = self._account_payload_has_assets(account_data)

                if isinstance(account_data, dict):
                    self._process_balance_message_from_account(account_data)
                    if has_assets_payload:
                        # WS pushed a confirmed balance snapshot — treat as equivalent to a REST
                        # balance refresh so BUY orders are not blocked waiting for a poll.
                        now = self._current_timestamp_safely()
                        self._last_ws_balance_update_ts = now
                        self._last_balance_update_timestamp = now
                        if self._balance_refresh_required_since > 0 and now >= self._balance_refresh_required_since:
                            self._balance_refresh_required_since = 0.0

                unmatched_private_event = False
                # ── Orders FIRST (mirrors PERP connector pattern) ──────────────────────────
                # Processing orders before trades ensures that the COI→UUID and SOI→COI maps
                # are fully populated before fill matching is attempted.  Without this ordering,
                # account_all events that bundle a FILLED order state AND the fill details in
                # the same message would lose the fill: the trade loop would try to match via
                # server_order_index ("i") but the SOI→COI map wasn't populated yet, so the
                # fill would hit the `unmatched_private_event` path and be permanently lost.
                # PERP's _process_account_all_ws_event_message processes orders then trades;
                # this aligns SPOT with that architecture.
                for order_data in orders:
                    order_update = self._order_update_from_raw_message(order_data)
                    if order_update is not None:
                        # ── False-cancel guard ────────────────────────────────────────────────
                        # Lighter's account_all_orders channel dumps ALL historical orders on
                        # subscription (snapshot replay). On WS reconnect this can deliver an
                        # old CANCELED order whose client_order_index coincidentally matches a
                        # newly placed order — firing a false CANCELED event within milliseconds
                        # of creation.  A real cancel TX takes ~29 s on-chain, so any CANCELED
                        # event for an order younger than _CANCEL_MIN_ORDER_AGE_SECS is almost
                        # certainly a snapshot replay.  Suppress it and verify via REST instead.
                        # NOTE: account_order_updates does NOT send historical snapshots — only
                        # real-time events — so the guard must NOT apply to those events.
                        if order_update.new_state == OrderState.CANCELED and _is_account_all_orders_event:
                            _cancel_order_snap = (
                                self._order_tracker.all_updatable_orders.get(order_update.client_order_id)
                                or self._order_tracker.all_fillable_orders.get(order_update.client_order_id)
                            )
                            if _cancel_order_snap is not None:
                                _order_age = time.time() - float(_cancel_order_snap.creation_timestamp or 0)
                                if _order_age < self._CANCEL_MIN_ORDER_AGE_SECS:
                                    self.logger().debug(
                                        "[ws-cancel guard] Suppressing CANCELED WS event for %s "
                                        "(age=%.2fs < %.0fs — likely subscription snapshot replay). "
                                        "Scheduling REST verification.",
                                        order_update.client_order_id,
                                        _order_age,
                                        self._CANCEL_MIN_ORDER_AGE_SECS,
                                    )
                                    safe_ensure_future(self._verify_cancel_not_false(_cancel_order_snap))
                                    continue  # Do NOT pass this CANCELED event to process_order_update
                        # ── End false-cancel guard ────────────────────────────────────────────
                        # When FILLED arrives via WS, eagerly fetch fills in the background so
                        # they arrive before wait_until_completely_filled() times out (5 s).
                        # This eliminates the 23-second fill delay and also covers orders that
                        # are already in cached_orders (e.g. CANCELED before FILLED).
                        if order_update.new_state in (OrderState.FILLED, OrderState.CANCELED):
                            _ws_fill_order = (
                                self._order_tracker.all_fillable_orders.get(order_update.client_order_id)
                                or self._order_tracker.all_fillable_orders_by_exchange_order_id.get(
                                    order_update.exchange_order_id or ""
                                )
                            )
                            if _ws_fill_order is not None:
                                safe_ensure_future(self._fetch_and_apply_fills(_ws_fill_order))
                        # Optimistically free the locked balance immediately on cancel confirmation.
                        # The account_all_assets WS balance push may arrive 30+ seconds after the
                        # cancel WS event.  During that window the strategy would compute a stale
                        # (too small) order size from the still-locked balance.  By releasing the
                        # locked portion now the strategy can immediately place orders at the
                        # correct size.  The WS push will overwrite with the authoritative value.
                        if order_update.new_state == OrderState.CANCELED:
                            _cancel_snap = (
                                self._order_tracker.all_updatable_orders.get(order_update.client_order_id)
                                or self._order_tracker.all_fillable_orders.get(order_update.client_order_id)
                            )
                            if _cancel_snap is not None:
                                self._release_locked_balance_on_cancel(_cancel_snap)
                        # Optimistically update balance when a fill is confirmed.  The received
                        # quote (SELL) or base (BUY) may not arrive via WS/REST for seconds due
                        # to rate-limiting.  Using order.price as the approximation is correct
                        # for maker orders (exact fill price) and a safe estimate for takers.
                        elif order_update.new_state == OrderState.FILLED:
                            _fill_snap = (
                                self._order_tracker.all_fillable_orders.get(order_update.client_order_id)
                                or self._order_tracker.all_fillable_orders_by_exchange_order_id.get(
                                    order_update.exchange_order_id or ""
                                )
                            )
                            if _fill_snap is not None:
                                self._release_locked_balance_on_fill(_fill_snap)
                        self._order_tracker.process_order_update(order_update)
                        self._schedule_balance_sync_for_terminal_update(order_update=order_update)
                    else:
                        unmatched_private_event = True

                # After processing orders, replay any buffered account_trades fills that
                # previously couldn't be matched (COI/SOI maps are now current).
                # Mirrors PERP's _replay_pending_trade_entries() called from
                # _process_account_all_ws_event_message.
                if orders and getattr(self, "_pending_spot_trade_entries", []):
                    await self._replay_pending_spot_trade_entries()

                # ── Trades (after orders so COI/SOI maps are current) ──────────────────────
                for trade in trades:
                    trade_update = self._trade_update_from_raw_message(trade)
                    if trade_update is not None:
                        # Snapshot order state BEFORE applying fill to detect post-fill state.
                        _fill_order = self._order_tracker.all_fillable_orders.get(trade_update.client_order_id)
                        self._order_tracker.process_trade_update(trade_update)
                        if _fill_order is not None:
                            _order_state = getattr(_fill_order, "current_state", None)
                            if _order_state == OrderState.CANCELED:
                                # Cancel-fill race: order was CANCELED but fill arrived later
                                # via account_trades WS (10-40s lag).  The CANCELED event
                                # already freed locked collateral but didn't credit the received
                                # quote (USDC for SELL).  Apply the fill balance credit now —
                                # mirrors the _fetch_and_apply_fills REST retry path fix.
                                self._release_locked_balance_on_fill(_fill_order)
                                self.logger().info(
                                    "[cancel-fill race WS] Order %s was canceled but fill "
                                    "arrived via account_trades WS — applied fill balance "
                                    "credit immediately.",
                                    _fill_order.client_order_id,
                                )
                            elif not _fill_order.is_done:
                                # Mirror PERP connector: if fills now make the order fully
                                # filled, fire FILLED state immediately so
                                # BuyOrderCompletedEvent fires WITH correct fill amounts.
                                # Handles the case where account_trades arrives before the
                                # account_all FILLED order update.
                                try:
                                    _exec = _fill_order.executed_amount_base
                                    _total = Decimal(str(_fill_order.amount))
                                    if not _total.is_nan() and _total > 0 and _exec >= _total:
                                        self._order_tracker.process_order_update(OrderUpdate(
                                            trading_pair=_fill_order.trading_pair,
                                            update_timestamp=trade_update.fill_timestamp,
                                            new_state=OrderState.FILLED,
                                            client_order_id=_fill_order.client_order_id,
                                            exchange_order_id=_fill_order.exchange_order_id,
                                        ))
                                except Exception:
                                    pass
                    elif _is_any_trades_channel_event:
                        # Fill arrived from a dedicated trade channel (account_trades PERP or
                        # account_all_trades SPOT) but we can't match the order yet.
                        # Buffer for replay after the next order-update batch, mirrors PERP.
                        _spot_buf = getattr(self, "_pending_spot_trade_entries", None)
                        if _spot_buf is not None:
                            _spot_buf.append((time.time(), trade))
                    elif _looks_like_fill(trade):
                        # Unmatched fill from a non-account_trades channel (e.g. account_all
                        # bundled trade that arrived before the SOI→COI map was populated).
                        # Buffer for replay the same way as account_trades fills so the next
                        # order-update batch can resolve the match without falling back to REST.
                        _spot_buf = getattr(self, "_pending_spot_trade_entries", None)
                        if _spot_buf is not None:
                            _spot_buf.append((time.time(), trade))
                    else:
                        unmatched_private_event = True

                if unmatched_private_event:
                    self._schedule_unmatched_private_event_reconcile(min_interval_seconds=1.0)

                # Some private event payloads include order/trade changes but omit account assets.
                # Trigger a throttled balance refresh so locked/available values in status --live
                # reflect open/canceled orders without waiting for the next periodic poll.
                # Skip if account_all_assets already delivered a fresh WS balance snapshot recently
                # (within 2 s) — the WS push is authoritative and a REST call is redundant.
                if (
                    (not has_assets_payload)
                    and (len(trades) > 0 or len(orders) > 0)
                    and (self._current_timestamp_safely() - getattr(self, "_last_private_stream_balance_sync_ts", 0.0)) >= 1.0
                    and (self._current_timestamp_safely() - getattr(self, "_last_ws_balance_update_ts", 0.0)) >= 2.0
                ):
                    self._last_private_stream_balance_sync_ts = self._current_timestamp_safely()
                    safe_ensure_future(self._safe_update_balances_from_private_stream())
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _replay_pending_spot_trade_entries(self) -> None:
        """Replay account_trades fill entries buffered when the COI→UUID mapping wasn't yet established.

        Called after processing an account_all order-update batch that may have populated
        _server_order_index_to_client_order_index and _client_order_index_to_client_order_id.
        Mirrors PERP's _replay_pending_trade_entries pattern.

        Entries still unmatched after 5 seconds are escalated to reconciliation (REST status poll).
        """
        now = time.time()
        still_pending: List[Tuple[float, Dict[str, Any]]] = []
        for buffered_ts, trade_data in self._pending_spot_trade_entries:
            trade_update = self._trade_update_from_raw_message(trade_data)
            if trade_update is not None:
                _fill_order = self._order_tracker.all_fillable_orders.get(trade_update.client_order_id)
                self._order_tracker.process_trade_update(trade_update)
                if _fill_order is not None and not _fill_order.is_done:
                    try:
                        _total = Decimal(str(_fill_order.amount))
                        if not _total.is_nan() and _total > 0 and _fill_order.executed_amount_base >= _total:
                            self._order_tracker.process_order_update(OrderUpdate(
                                trading_pair=_fill_order.trading_pair,
                                update_timestamp=trade_update.fill_timestamp,
                                new_state=OrderState.FILLED,
                                client_order_id=_fill_order.client_order_id,
                                exchange_order_id=_fill_order.exchange_order_id,
                            ))
                    except Exception:
                        pass
                self.logger().debug(
                    "[replay-fill] Replayed buffered account_trades fill for %s (buffered for %.1fs)",
                    trade_update.client_order_id,
                    now - buffered_ts,
                )
            else:
                age = now - buffered_ts
                if age < 5.0:
                    still_pending.append((buffered_ts, trade_data))
                else:
                    # Stale unmatched fill — escalate to REST reconciliation
                    self.logger().debug(
                        "[replay-fill] Discarding stale buffered fill after %.1fs — scheduling reconciliation.",
                        age,
                    )
                    self._schedule_unmatched_private_event_reconcile(min_interval_seconds=0.0)
        self._pending_spot_trade_entries = still_pending

    async def _fetch_and_apply_fills(self, order: InFlightOrder, delay: float = 0.0, _retries_left: int = 7):
        """Fetch fills for *order* and apply them via process_trade_update.

        Called in the background when a FILLED state arrives via WebSocket so that
        fill details reach the tracker before wait_until_completely_filled() times out.
        Also handles orders already in cached_orders (e.g. cancelled then filled race).

        A dedup guard (_fill_fetch_in_progress) prevents multiple concurrent /trades
        requests for the same order from bursting the exchange rate limit.  If a fetch
        is already running when this coroutine is entered, it returns immediately.
        Pass *delay* > 0 to back off before retrying after a rate-limit failure.
        *_retries_left* controls how many additional 8-second retries are allowed when
        0 fills are found; the default of 7 gives a 56-second window (0+8*7 s).
        Lighter REST /trades indexing can lag up to ~40 s after on-chain match for
        simultaneous cancel-fill races, so multiple retries are needed.
        """
        order_id = order.client_order_id
        if order_id in self._fill_fetch_in_progress:
            return  # Another fetch is already running for this order
        self._fill_fetch_in_progress.add(order_id)
        try:
            if delay > 0:
                await asyncio.sleep(delay)
            fills = await self._all_trade_updates_for_order(order)
            for fill in fills:
                self._order_tracker.process_trade_update(fill)
            if fills:
                # Cancel-fill race recovery: if the order is in CANCELED state but fills were
                # found, the cancel TX was processed AFTER the fill had already matched on-chain.
                # The exchange emitted a CANCELED WS event (from account_all_orders) BEFORE the
                # fill arrived via account_trades, so _release_locked_balance_on_cancel ran and
                # freed the locked collateral but didn't credit the received quote (e.g. USDC
                # for a SELL fill).  Apply the fill balance credit now so the strategy's next
                # tick sees the correct available USDC without waiting for the next WS
                # account_all_assets push (which may take 30+ seconds).
                _order_current_state = getattr(order, "current_state", None)
                if _order_current_state == OrderState.CANCELED:
                    self._release_locked_balance_on_fill(order)
                    self.logger().info(
                        "[cancel-fill race] Order %s was canceled but fills found — "
                        "applied fill balance credit immediately (USDC credited, locked base corrected).",
                        order.client_order_id,
                    )
                self.logger().debug(
                    "[ws-fill] Applied %d fill(s) for order %s from eager REST fetch",
                    len(fills),
                    order.client_order_id,
                )
            elif _retries_left > 0:
                # No fills found — the REST /trades endpoint may not have indexed the fill yet.
                # Lighter REST indexing lags 2–40 s after on-chain match for cancel-fill races.
                # Schedule another retry (up to _retries_left more attempts, each 8 s apart).
                self.logger().debug(
                    "[ws-fill] No fills found for %s (retries_left=%d) — scheduling retry in 8s",
                    order.client_order_id,
                    _retries_left,
                )
                safe_ensure_future(self._fetch_and_apply_fills(order, delay=8.0, _retries_left=_retries_left - 1))
            else:
                self.logger().debug(
                    "[ws-fill] No fills found for %s after all retries — giving up",
                    order.client_order_id,
                )
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.logger().debug(
                "[ws-fill] Eager fill fetch failed for %s: %s",
                order.client_order_id,
                err,
            )
        finally:
            self._fill_fetch_in_progress.discard(order_id)

    async def _verify_cancel_not_false(self, order: InFlightOrder, delay: float = 2.0) -> None:
        """REST-verify an order whose WS CANCELED event was suppressed as a likely false cancel.

        Waits *delay* seconds (so the REST API reflects the latest sequencer state), then polls
        the order status once.  Three outcomes:

        * Order is truly CANCELED on the exchange → apply the CANCELED update now (late but correct).
        * Order is still OPEN → false cancel confirmed; do nothing.  The order continues to be
          tracked normally and will be cancelled/filled through the regular refresh cycle.
        * Request fails (e.g., 429 rate-limit) → log and do nothing; the periodic status poll
          will catch the real state within UPDATE_ORDER_STATUS_MIN_INTERVAL seconds.
        """
        try:
            await asyncio.sleep(delay)
            order_update = await self._request_order_status(order)
            if order_update.new_state == OrderState.CANCELED:
                self.logger().debug(
                    "[ws-cancel guard] REST confirmed CANCELED for %s — applying state.",
                    order.client_order_id,
                )
                _cancel_snap = self._order_tracker.all_fillable_orders.get(order.client_order_id)
                if _cancel_snap is not None:
                    self._release_locked_balance_on_cancel(_cancel_snap)
                self._order_tracker.process_order_update(order_update)
                self._schedule_balance_sync_for_terminal_update(order_update=order_update)
            else:
                self.logger().debug(
                    "[ws-cancel guard] REST confirmed %s is still %s — WS CANCELED was a false cancel "
                    "(subscription snapshot replay). Order tracking preserved.",
                    order.client_order_id,
                    order_update.new_state.name,
                )
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().debug(
                "[ws-cancel guard] REST verification failed for %s: %s — "
                "the next explicit reconcile or stale-stream fallback will reconcile.",
                order.client_order_id,
                ex,
            )

    def _current_timestamp_safely(self) -> float:
        try:
            return self.current_timestamp
        except Exception:
            return time.time()

    def _private_user_stream_last_recv_time(self) -> float:
        try:
            tracker = getattr(self, "_user_stream_tracker", None)
            if tracker is None:
                return 0.0

            last_recv_time = getattr(tracker, "last_recv_time", None)
            if last_recv_time is None:
                data_source = getattr(tracker, "data_source", None)
                last_recv_time = getattr(data_source, "last_recv_time", 0.0)

            return float(last_recv_time or 0.0)
        except Exception:
            return 0.0

    def _is_private_user_stream_healthy(self) -> bool:
        last_recv_time = self._private_user_stream_last_recv_time()
        if last_recv_time <= 0:
            return False
        return (self._current_timestamp_safely() - last_recv_time) < self.TICK_INTERVAL_LIMIT

    def _should_poll_balances_via_rest(self, force_rest: bool = False) -> bool:
        if force_rest:
            return True

        last_balance_ts = float(getattr(self, "_last_balance_update_timestamp", 0.0) or 0.0)
        last_ws_balance_ts = float(getattr(self, "_last_ws_balance_update_ts", 0.0) or 0.0)
        required_since = float(getattr(self, "_balance_refresh_required_since", 0.0) or 0.0)

        if required_since > max(last_balance_ts, last_ws_balance_ts):
            return True

        if last_balance_ts <= 0 and last_ws_balance_ts <= 0:
            return True

        return not self._is_private_user_stream_healthy()

    def _should_reconcile_orders_via_rest(self, force_rest_reconcile: bool = False) -> bool:
        if force_rest_reconcile:
            return True
        return not self._is_private_user_stream_healthy()

    async def _safe_update_balances_from_private_stream(self):
        try:
            await self._update_balances(force_rest=True)
        except asyncio.CancelledError:
            raise
        except Exception as balance_error:
            self.logger().debug(
                "Private-stream-triggered balance refresh failed: %s",
                balance_error,
            )

    def _schedule_unmatched_private_event_reconcile(self, min_interval_seconds: float = 1.0):
        now = self._current_timestamp_safely()
        if (now - getattr(self, "_last_unmatched_private_event_reconcile_ts", 0.0)) < min_interval_seconds:
            return
        self._last_unmatched_private_event_reconcile_ts = now
        safe_ensure_future(self._safe_reconcile_unmatched_private_event())

    async def _safe_reconcile_unmatched_private_event(self):
        try:
            await self._update_order_status(force_rest_reconcile=True)
        except asyncio.CancelledError:
            raise
        except Exception as reconcile_error:
            self.logger().debug(
                "Unmatched private-event reconcile failed: %s",
                reconcile_error,
            )

    def _lock_balance_on_order_creation(
        self,
        trading_pair: str,
        amount: Decimal,
        price: Decimal,
        trade_type: TradeType,
    ) -> None:
        """Optimistically deduct the allocated balance immediately when an order is submitted.

        The account_all_assets WS push and the fast REST sync are asynchronous — during
        the window before they complete, _account_available_balances still shows the
        pre-order value.  If the strategy evaluates balance in that window it may place a
        second order thinking it has more capital available than is actually locked.

        For a BUY order: deduct amount × price from the quote asset (e.g. USDC).
        For a SELL order: deduct amount from the base asset.

        This is the inverse of _release_locked_balance_on_cancel; both are best-effort
        and corrected by the authoritative REST/WS balance sync when it arrives.
        """
        try:
            base, quote = trading_pair.split("-", 1)
            if trade_type == TradeType.BUY:
                locked = amount * price
                if locked > 0 and quote in self._account_available_balances:
                    new_avail = max(Decimal("0"), self._account_available_balances[quote] - locked)
                    self._account_available_balances[quote] = new_avail
                    _opt_locks = getattr(self, "_optimistic_balance_lock", None)
                    if _opt_locks is None:
                        self._optimistic_balance_lock: Dict[str, Any] = {}
                        _opt_locks = self._optimistic_balance_lock
                    _opt_locks[quote] = (new_avail, time.time())
            elif trade_type == TradeType.SELL:
                if amount > 0 and base in self._account_available_balances:
                    new_avail = max(Decimal("0"), self._account_available_balances[base] - amount)
                    self._account_available_balances[base] = new_avail
                    _opt_locks = getattr(self, "_optimistic_balance_lock", None)
                    if _opt_locks is None:
                        self._optimistic_balance_lock: Dict[str, Any] = {}
                        _opt_locks = self._optimistic_balance_lock
                    _opt_locks[base] = (new_avail, time.time())
        except Exception:
            pass  # Best-effort; REST/WS sync will correct any imprecision

    def _release_locked_balance_on_cancel(self, order: "InFlightOrder") -> None:
        """Optimistically free the locked balance immediately when a cancel is confirmed.

        The account_all_assets WS balance push can arrive 30+ seconds after the cancel
        WS event.  During that window the strategy computes order sizes from the stale
        (still-locked) balance and ends up placing orders that are too small to meet
        minimum notional.  By releasing the unfilled locked portion now, the strategy
        immediately sees the correct available balance.

        The WS/REST balance push will overwrite _account_available_balances with the
        authoritative exchange value when it arrives, so any imprecision here is transient.
        """
        try:
            trading_pair = order.trading_pair
            base, quote = trading_pair.split("-", 1)
            amount = Decimal(str(order.amount))
            price = Decimal(str(order.price))
            executed = Decimal(str(getattr(order, "executed_amount_base", Decimal("0")) or "0"))
            remaining = max(Decimal("0"), amount - executed)

            if order.trade_type == TradeType.BUY:
                # Free the quote asset (e.g. USDC) locked for the unfilled portion.
                freed = remaining * price
                if freed > 0 and quote in self._account_available_balances:
                    new_avail = self._account_available_balances[quote] + freed
                    # Cap at total balance so we never report more than we have.
                    total = self._account_balances.get(quote, new_avail)
                    new_avail_capped = min(new_avail, total)
                    self._account_available_balances[quote] = new_avail_capped
                    # Record the optimistic release so _process_balance_message_from_account
                    # can guard against stale account_all_assets WS events (which still show
                    # the locked balance) arriving after the cancel was processed and
                    # overwriting the correctly-released available balance.
                    _opt = getattr(self, "_optimistic_balance_release", {})
                    _opt[quote] = (new_avail_capped, time.time())
                    self._optimistic_balance_release = _opt
            elif order.trade_type == TradeType.SELL:
                # Free the base asset (e.g. UNI) locked for the unfilled portion.
                if remaining > 0 and base in self._account_available_balances:
                    new_avail = self._account_available_balances[base] + remaining
                    total = self._account_balances.get(base, new_avail)
                    new_avail_capped = min(new_avail, total)
                    self._account_available_balances[base] = new_avail_capped
                    _opt = getattr(self, "_optimistic_balance_release", {})
                    _opt[base] = (new_avail_capped, time.time())
                    self._optimistic_balance_release = _opt
        except Exception:
            pass  # Best-effort; WS push will correct any imprecision

    def _release_locked_balance_on_fill(self, order: "InFlightOrder") -> None:
        """Optimistically update available balance immediately when a fill is confirmed.

        When a FILLED WS event arrives the exchange-side balance has already changed, but
        the account_all_assets WS push and the REST balance poll may be delayed (or
        rate-limited).  During that window the strategy computes order sizes from the
        pre-fill balance and places orders that are too small to meet minimum notional.

        For a SELL fill: quote (USDC) received = order.amount × order.price.
        For a BUY fill: base received = order.amount.

        This is best-effort; the authoritative WS/REST balance will overwrite these values.
        """
        try:
            trading_pair = order.trading_pair
            base, quote = trading_pair.split("-", 1)
            amount = Decimal(str(order.amount))
            price = Decimal(str(order.price))

            if order.trade_type == TradeType.SELL:
                # We sold base → received quote.
                received_quote = amount * price
                if received_quote > 0 and quote in self._account_available_balances:
                    self._account_available_balances[quote] = (
                        self._account_available_balances[quote] + received_quote
                    )
                    self._account_balances[quote] = self._account_balances.get(quote, Decimal("0")) + received_quote
                # Base was locked for the order; it's now spent.
                if base in self._account_balances:
                    self._account_balances[base] = max(Decimal("0"), self._account_balances[base] - amount)
                    # available was locked so net effect on available ≈ 0, just cap at new total
                    self._account_available_balances[base] = min(
                        self._account_available_balances.get(base, Decimal("0")),
                        self._account_balances[base],
                    )
            elif order.trade_type == TradeType.BUY:
                # We bought base → received base, spent quote (already locked).
                if base in self._account_available_balances:
                    self._account_available_balances[base] = (
                        self._account_available_balances[base] + amount
                    )
                    self._account_balances[base] = self._account_balances.get(base, Decimal("0")) + amount
                # Quote was locked; it's spent.
                spent_quote = amount * price
                if quote in self._account_balances:
                    self._account_balances[quote] = max(Decimal("0"), self._account_balances[quote] - spent_quote)
                    self._account_available_balances[quote] = min(
                        self._account_available_balances.get(quote, Decimal("0")),
                        self._account_balances[quote],
                    )
        except Exception:
            pass  # Best-effort; WS push will correct any imprecision

    def _schedule_fast_balance_sync(self, min_interval_seconds: float = 0.2):
        now = self._current_timestamp_safely()
        if (now - getattr(self, "_last_private_stream_balance_sync_ts", 0.0)) < min_interval_seconds:
            return
        self._last_private_stream_balance_sync_ts = now
        safe_ensure_future(self._safe_update_balances_from_private_stream())

    def _schedule_balance_sync_for_terminal_update(
        self,
        order_update: OrderUpdate,
        tracked_order: Optional[InFlightOrder] = None,
    ):
        # CANCELED and FILLED orders change exchange locked_balance → require fresh REST data.
        # FAILED orders that were rejected before submission don't change exchange state,
        # so don't block future BUY orders on a mandatory balance refresh.
        if order_update.new_state in {OrderState.CANCELED, OrderState.FILLED}:
            _ = tracked_order
            self._balance_refresh_required_since = max(
                self._balance_refresh_required_since,
                self._current_timestamp_safely(),
            )
            # Only trigger a REST balance poll when account_all_assets WS push has not
            # delivered a fresh snapshot recently (≤1 s).  The WS push is the primary source.
            if (self._current_timestamp_safely() - getattr(self, "_last_ws_balance_update_ts", 0.0)) >= 1.0:
                self._schedule_fast_balance_sync(min_interval_seconds=0.2)
        elif order_update.new_state == OrderState.FAILED:
            # Still do a fast sync (balance might have been reserved briefly) but
            # don't mark it as required so BUY orders aren't blocked if it fails.
            if (self._current_timestamp_safely() - getattr(self, "_last_ws_balance_update_ts", 0.0)) >= 2.0:
                self._schedule_fast_balance_sync(min_interval_seconds=1.0)

    @staticmethod
    def _account_payload_has_assets(account_data: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(account_data, dict):
            return False

        assets = account_data.get("assets")
        if isinstance(assets, list):
            return any(isinstance(asset, dict) for asset in assets)
        if isinstance(assets, dict):
            return any(isinstance(asset, dict) for asset in assets.values())
        return False

    @staticmethod
    def _extract_private_stream_payloads(event_message: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        account_data: Optional[Dict[str, Any]] = None
        trades: List[Dict[str, Any]] = []
        orders: List[Dict[str, Any]] = []

        message_type = str(event_message.get("type", ""))
        event_type_name = message_type.split("/", 1)[1] if "/" in message_type else message_type
        channel = str(event_message.get("channel", ""))
        payload = event_message.get("data")

        if isinstance(event_message.get("account"), dict):
            account_data = event_message.get("account")
        elif isinstance(payload, dict) and isinstance(payload.get("account"), dict):
            account_data = payload.get("account")
        elif event_type_name in {
            CONSTANTS.WS_ACCOUNT_ALL_CHANNEL,
            CONSTANTS.WS_ACCOUNT_INFO_CHANNEL,
        }:
            if isinstance(payload, dict):
                # Some environments wrap the payload in a "data" key.
                account_data = payload
            elif isinstance(event_message.get("assets"), (dict, list)):
                # Live account_all WS events put assets at the top level (no "data" wrapper).
                # Normalise into the same shape as the account_all_assets handler below.
                _assets_raw = event_message["assets"]
                if isinstance(_assets_raw, dict):
                    _assets_list = [a for a in _assets_raw.values() if isinstance(a, dict)]
                else:
                    _assets_list = [a for a in _assets_raw if isinstance(a, dict)]
                account_data = {"assets": _assets_list}
        elif event_type_name == CONSTANTS.WS_ACCOUNT_ALL_ASSETS_CHANNEL:
            assets_payload = None
            if isinstance(event_message.get("assets"), (dict, list)):
                assets_payload = event_message.get("assets")
            elif isinstance(payload, dict) and isinstance(payload.get("assets"), (dict, list)):
                assets_payload = payload.get("assets")

            if assets_payload is not None:
                if isinstance(assets_payload, dict):
                    assets_list = [asset for asset in assets_payload.values() if isinstance(asset, dict)]
                else:
                    assets_list = [asset for asset in assets_payload if isinstance(asset, dict)]
                account_data = {"assets": assets_list}

        # trades may be a flat list OR a dict keyed by market_id (e.g. account_all sends
        # {"market_id": Trade} or {"market_id": [Trade, ...]}).  Handle all variants.
        for _trades_src in (event_message, payload if isinstance(payload, dict) else {}):
            _tf = _trades_src.get("trades")
            if isinstance(_tf, list):
                trades.extend([t for t in _tf if isinstance(t, dict)])
            elif isinstance(_tf, dict):
                for _mkt_val in _tf.values():
                    if isinstance(_mkt_val, list):
                        trades.extend([t for t in _mkt_val if isinstance(t, dict)])
                    elif isinstance(_mkt_val, dict):
                        trades.append(_mkt_val)
        if isinstance(event_message.get("trade"), dict):
            trades.append(event_message.get("trade"))
        if isinstance(payload, dict) and isinstance(payload.get("trade"), dict):
            trades.append(payload.get("trade"))

        if event_type_name == CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL:
            if isinstance(payload, list):
                trades.extend([trade for trade in payload if isinstance(trade, dict)])
            elif isinstance(payload, dict) and "trades" not in payload:
                trades.append(payload)

        # orders may be a flat list OR a dict keyed by market_id (e.g. account_all_orders sends
        # {"market_id": [Order, ...]}).  Handle all variants.
        for _orders_src in (event_message, payload if isinstance(payload, dict) else {}):
            _of = _orders_src.get("orders")
            if isinstance(_of, list):
                orders.extend([o for o in _of if isinstance(o, dict)])
            elif isinstance(_of, dict):
                for _mkt_val in _of.values():
                    if isinstance(_mkt_val, list):
                        orders.extend([o for o in _mkt_val if isinstance(o, dict)])
                    elif isinstance(_mkt_val, dict):
                        orders.append(_mkt_val)
        if isinstance(event_message.get("order"), dict):
            orders.append(event_message.get("order"))
        if isinstance(payload, dict) and isinstance(payload.get("order"), dict):
            orders.append(payload.get("order"))

        if (
            event_type_name == CONSTANTS.WS_ACCOUNT_ORDER_UPDATES_CHANNEL
            or channel.startswith(f"{CONSTANTS.WS_ACCOUNT_ORDER_UPDATES_CHANNEL}:")
            or channel.startswith(f"{CONSTANTS.WS_ACCOUNT_ORDER_UPDATES_CHANNEL}/")
        ):
            if isinstance(payload, list):
                orders.extend([order for order in payload if isinstance(order, dict)])
            elif isinstance(payload, dict) and "orders" not in payload:
                orders.append(payload)

        if (
            event_type_name == CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL
            or channel.startswith(f"{CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL}:")
            or channel.startswith(f"{CONSTANTS.WS_ACCOUNT_ALL_ORDERS_CHANNEL}/")
        ):
            # Some environments send dedicated account_all_orders updates under a flat
            # `data` payload instead of the documented top-level `orders` map.
            if isinstance(payload, list):
                orders.extend([order for order in payload if isinstance(order, dict)])
            elif isinstance(payload, dict) and "orders" not in payload:
                orders.append(payload)

        # account_tx: txs is a list of Account_tx objects (each is an Order JSON, possibly
        # wrapped under an "order" key).  Extract as order updates for status + fill tracking.
        if (
            event_type_name == CONSTANTS.WS_ACCOUNT_TX_CHANNEL
            or channel.startswith(f"{CONSTANTS.WS_ACCOUNT_TX_CHANNEL}:")
            or channel.startswith(f"{CONSTANTS.WS_ACCOUNT_TX_CHANNEL}/")
        ):
            txs = event_message.get("txs", [])
            if not isinstance(txs, list) and isinstance(payload, dict):
                txs = payload.get("txs", [])
            if isinstance(txs, list):
                for tx in txs:
                    if isinstance(tx, dict):
                        order_obj = tx.get("order") if isinstance(tx.get("order"), dict) else tx
                        if isinstance(order_obj, dict):
                            orders.append(order_obj)

        return account_data, trades, orders

    def _state_from_raw_order_status(self, raw_status: str) -> OrderState:
        return self._ORDER_STATE.get(raw_status.lower(), OrderState.OPEN)

    def _process_balance_message_from_account(self, account_data: Dict[str, Any]):
        assets_payload = account_data.get("assets", [])
        if isinstance(assets_payload, dict):
            assets_iterable = [asset for asset in assets_payload.values() if isinstance(asset, dict)]
        else:
            assets_iterable = assets_payload

        ws_asset_names = set()
        for asset_entry in assets_iterable:
            asset_symbol = asset_entry.get("symbol")
            if asset_symbol is None:
                continue

            ws_asset_names.add(asset_symbol)
            total_balance = Decimal(str(asset_entry.get("balance") or "0"))
            locked_balance = Decimal(str(asset_entry.get("locked_balance") or "0"))
            available_balance = total_balance - locked_balance

            self._account_balances[asset_symbol] = total_balance

            # Guard against a stale account_all_assets WS event (which still carries the
            # locked balance from when the order was placed) arriving AFTER
            # _release_locked_balance_on_cancel has already optimistically freed that lock.
            # Such stale events would reduce available_balance back to the locked value,
            # causing the strategy to compute an undersized order (e.g. 1.21 UNI instead
            # of 3.8 UNI) and fail the minimum-notional check.
            # The guard allows the optimistic release to stand for up to 3 seconds.  Once a
            # WS event arrives showing locked_balance == 0 (confirming the cancel on-chain)
            # or 3 seconds elapse, the guard clears automatically.
            _opt_releases = getattr(self, "_optimistic_balance_release", {})
            _opt_entry = _opt_releases.get(asset_symbol)
            if _opt_entry is not None:
                _opt_avail, _opt_ts = _opt_entry
                if locked_balance > Decimal("0") and available_balance < _opt_avail and (time.time() - _opt_ts) < 3.0:
                    # WS event still shows a lock that we already released — skip the
                    # available-balance update but keep the total-balance update above.
                    continue
                else:
                    # Guard condition no longer applies — clear it.
                    _opt_releases.pop(asset_symbol, None)

            # Guard against a stale WS event undoing an optimistic order-placement lock.
            # After an order is placed, the exchange may not yet have added it to
            # locked_balance (ZK batch propagation lag, up to a few seconds).  A WS event
            # arriving in that window shows locked_balance == 0 and a too-high available —
            # skip overwriting the lock until the exchange catches up or 3 s elapse.
            _opt_locks = getattr(self, "_optimistic_balance_lock", {})
            _opt_lock_entry = _opt_locks.get(asset_symbol)
            if _opt_lock_entry is not None:
                _opt_locked_avail, _opt_lock_ts = _opt_lock_entry
                if locked_balance == Decimal("0") and available_balance > _opt_locked_avail and (time.time() - _opt_lock_ts) < 3.0:
                    # Exchange hasn't registered the new order yet — keep optimistic lock.
                    continue
                else:
                    _opt_locks.pop(asset_symbol, None)

            self._account_available_balances[asset_symbol] = available_balance

        # Remove assets that have gone to zero and are no longer in the WS payload.
        # Mirrors the cleanup done by the REST _update_balances to prevent ghost entries.
        # Only do this when the payload is a full snapshot (has more than one asset or
        # when the total local asset count is small) to avoid removing assets on partial updates.
        if len(ws_asset_names) > 0:
            for local_asset in list(self._account_balances.keys()):
                if local_asset not in ws_asset_names and self._account_balances.get(local_asset, Decimal("1")) == Decimal("0"):
                    self._account_balances.pop(local_asset, None)
                    self._account_available_balances.pop(local_asset, None)

        # For the spot connector, available balance is derived from per-asset wallet balances
        # (`balance - locked_balance`) rather than the account-level `available_balance` field.
        # This ensures allocated percentage calculations reflect the true per-asset balance.

    def _order_update_from_raw_message(self, order_data: Dict[str, Any]) -> Optional[OrderUpdate]:
        # exchange_order_id == str(client_order_index) in this connector.
        # Prefer client_order_id / client_order_index so order lookup succeeds.
        # Also handle compact WS format keys: "I" = client_order_index, "i" = server order_index.
        # From lighter-go cancel_order.go: cancel/modify Index field accepts either value,
        # so we keep exchange_order_id = client_order_index throughout the lifecycle.
        exchange_order_id = str(
            order_data.get("client_order_id")
            or order_data.get("client_order_index")
            or order_data.get("I")          # compact WS: client_order_index
            or order_data.get("order_id")
            or order_data.get("orderId")
            or order_data.get("order_index")
            or order_data.get("orderIndex")
            or order_data.get("i")          # compact WS: server order_index (lowest priority)
            or ""
        )
        # Populate server_order_index → client_order_index reverse map when both are available.
        # This allows compact account_trades fills (which carry only "i") to be matched even
        # when the WS trade event arrives before the order update updates exchange_order_id.
        _coi_raw = str(order_data.get("I") or order_data.get("client_order_index") or "")
        _soi_raw = str(order_data.get("i") or order_data.get("order_index") or order_data.get("orderIndex") or "")
        # Full-format events (account_all) use "order_id" (= SOI as string) together with
        # "client_order_index" or "client_order_id" (= COI).  Extract the SOI from "order_id"
        # when a COI field is also present so we can build the SOI→COI map even in non-compact
        # format where "i"/"order_index" may be absent.
        if not _soi_raw and _coi_raw:
            _soi_raw = str(order_data.get("order_id") or order_data.get("orderId") or "")
        if _coi_raw and _soi_raw and _coi_raw != _soi_raw:
            self._server_order_index_to_client_order_index[_soi_raw] = _coi_raw
        client_order_id = str(order_data.get("client_order_id") or order_data.get("clientOrderId") or "")
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if tracked_order is None and exchange_order_id:
            tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        # FALLBACK — compact format with I=null (SOI-only update).
        # The exchange sends account_all_orders compact events where "I" (client_order_index)
        # is null but "i" (server order_index), "s" (symbol), and "d" (direction) are present.
        # When the standard lookups fail because the order's exchange_order_id is the COI
        # (not the SOI), use the symbol+direction from the event to find the one active order
        # in that market/direction — the same heuristic the PERP connector uses via its
        # multi-path order matching.  Only safe when exactly ONE candidate remains after
        # filtering; with multiple open orders in the same direction, fall through to reconcile.
        if tracked_order is None and _soi_raw:
            _ev_symbol = str(order_data.get("s") or "")
            _ev_direction = str(order_data.get("d") or "")
            _ev_price_str = str(order_data.get("p") or order_data.get("ip") or "")
            _soi_map = getattr(self, "_server_order_index_to_client_order_index", {})
            candidates = [
                o for o in self._order_tracker.all_updatable_orders.values()
                if not o.is_done
            ]
            if _ev_symbol:
                candidates = [o for o in candidates if _ev_symbol in (o.trading_pair or "")]
            if _ev_direction:
                _expected_type = TradeType.BUY if _ev_direction == "bid" else TradeType.SELL
                candidates = [o for o in candidates if o.trade_type == _expected_type]
            if _ev_price_str:
                try:
                    _ev_price = Decimal(_ev_price_str)
                    candidates = [o for o in candidates if abs((o.price or Decimal("0")) - _ev_price) < Decimal("0.01")]
                except Exception:
                    pass
            if len(candidates) == 1:
                tracked_order = candidates[0]
                _effective_coi = str(tracked_order.exchange_order_id or "")
                if _effective_coi and _effective_coi != _soi_raw:
                    _soi_map[_soi_raw] = _effective_coi
                    self.logger().debug(
                        "[order-soi-fallback] SOI=%s → COI=%s for order %s "
                        "(matched via %s %s scan)",
                        _soi_raw,
                        _effective_coi,
                        tracked_order.client_order_id,
                        _ev_direction,
                        _ev_symbol,
                    )

        if tracked_order is None:
            return None

        # Whenever we found the tracked order, ensure the SOI→COI map is populated even
        # when "I" (client_order_index) was absent from the event.  This covers full-format
        # account_all events where order_id=SOI and client_order_index=COI are both present
        # (the earlier block handles it) as well as cases resolved by the fallback scan above.
        # Having the map populated ensures subsequent compact account_trades fills (I=null,
        # i=SOI) can be replayed and matched instantly once the order state is known.
        if _soi_raw and not _coi_raw:
            _effective_coi2 = str(tracked_order.exchange_order_id or "")
            if _effective_coi2 and _effective_coi2 != _soi_raw:
                getattr(self, "_server_order_index_to_client_order_index", {}).setdefault(
                    _soi_raw, _effective_coi2
                )

        # "os" is the compact field used by account_order_updates; "order_status"/"status" are
        # used by account_all_orders full-JSON format.  Check compact format last as fallback.
        raw_status = str(order_data.get("order_status") or order_data.get("status") or order_data.get("os") or "open")
        # "ut" (updated_at ms) is the compact timestamp in account_order_updates format.
        update_ts = float(order_data.get("updated_at") or order_data.get("created_at") or order_data.get("ut") or self.current_timestamp)
        if update_ts > 1e12:
            update_ts *= 1e-3
        if update_ts > 1e12:
            update_ts *= 1e-3

        return OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id or tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_ts,
            new_state=self._state_from_raw_order_status(raw_status),
        )

    def _trade_update_from_raw_message(self, trade_data: Dict[str, Any]) -> Optional[TradeUpdate]:
        if not isinstance(trade_data, dict):
            return None

        # Try to find the tracked order via ask_client_id / bid_client_id (REST API field names).
        # Also check _str suffixed variants used by the live account_all WS event format.
        # Fall back to legacy order_id fields used by older WS formats.
        # NilClientOrderIndex = 0 means "not set" — skip those to avoid spurious dict lookups.
        tracked_order = None
        for cid_field in ("ask_client_id_str", "bid_client_id_str", "ask_client_id", "bid_client_id", "ask_clientId", "bid_clientId"):
            candidate_id = str(trade_data.get(cid_field) or "")
            if candidate_id and candidate_id != "0":  # 0 = NilClientOrderIndex (unset)
                tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(candidate_id)
                if tracked_order is None:
                    # Fallback: WS may have updated exchange_order_id to server order_id; look up
                    # via the client_order_index → client_order_id map recorded at placement time.
                    _coi_map = getattr(self, "_client_order_index_to_client_order_id", {})
                    hb_coid = _coi_map.get(candidate_id)
                    if hb_coid:
                        tracked_order = self._order_tracker.all_fillable_orders.get(hb_coid)
                if tracked_order is not None:
                    break

        if tracked_order is None:
            # Legacy / compact WS format fallback.
            # Prefer the client_order_id string (HB UUID) first, then try REST-format order_id.
            # Also try the compact WS "i" field (server-assigned order_index): this is the
            # primary field in account_trades compact messages when ask/bid_client_id are absent.
            client_order_id = str(trade_data.get("client_order_id") or trade_data.get("clientOrderId") or "")
            tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)

            if tracked_order is None:
                exchange_order_id = str(trade_data.get("order_id") or trade_data.get("orderId") or "")
                if exchange_order_id:
                    tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

            if tracked_order is None:
                # Compact account_trades format: "I" (capital I) = client_order_index (COI).
                # This field is populated by the exchange in account_trades WS messages and
                # allows matching BEFORE the SOI mapping is established by account_all updates.
                # This is the PERP connector's Path 0 equivalent — O(1) lookup via COI map
                # populated at order placement time, eliminating the race condition.
                coi_from_I = str(trade_data.get("I") or "")
                if coi_from_I and coi_from_I != "0":
                    _coi_map = getattr(self, "_client_order_index_to_client_order_id", {})
                    hb_coid = _coi_map.get(coi_from_I)
                    if hb_coid:
                        tracked_order = self._order_tracker.all_fillable_orders.get(hb_coid)

            if tracked_order is None:
                # Compact account_trades format: "i" = server order_index.
                # Try direct lookup (works if the order update already updated exchange_order_id
                # from client_order_index to server_order_index via the order-update path).
                # Then try via the reverse map populated by _order_update_from_raw_message.
                server_oi = str(trade_data.get("i") or "")
                if server_oi:
                    tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(server_oi)
                    if tracked_order is None:
                        _soi_map = getattr(self, "_server_order_index_to_client_order_index", {})
                        coi_str = _soi_map.get(server_oi)
                        if coi_str:
                            _coi_map = getattr(self, "_client_order_index_to_client_order_id", {})
                            hb_coid = _coi_map.get(coi_str)
                            if hb_coid:
                                tracked_order = self._order_tracker.all_fillable_orders.get(hb_coid)

        if tracked_order is None:
            # Log key fields to help diagnose which matching path failed.  This is especially
            # useful for understanding why account_all bundled trades or account_trades compact
            # fills (I=null, i=SOI) can't be attributed to a tracked order.
            self.logger().debug(
                "[fill-unmatch] Could not match fill — "
                "bid_client_id=%s ask_client_id=%s I=%s i=%s trade_id=%s "
                "active_orders=%d soi_map_size=%d",
                trade_data.get("bid_client_id") or trade_data.get("bid_client_id_str"),
                trade_data.get("ask_client_id") or trade_data.get("ask_client_id_str"),
                trade_data.get("I"),
                trade_data.get("i"),
                trade_data.get("trade_id") or trade_data.get("h"),
                len(self._order_tracker.all_updatable_orders),
                len(getattr(self, "_server_order_index_to_client_order_index", {})),
            )
            return None

        fill_price = Decimal(str(trade_data.get("price") or trade_data.get("p") or "0"))
        # API field is 'size'; 'amount'/'a' kept as fallbacks for compact WS formats.
        fill_base_amount = Decimal(str(trade_data.get("size") or trade_data.get("amount") or trade_data.get("a") or "0"))

        # Determine taker/maker using is_maker_ask and order direction.
        is_ask = (tracked_order.trade_type == TradeType.SELL)
        is_maker_ask = trade_data.get("is_maker_ask", None)
        if is_maker_ask is not None:
            is_taker = (is_ask and not is_maker_ask) or (not is_ask and is_maker_ask)
        else:
            # Fallback for compact WS format.
            is_taker = trade_data.get("event_type") == "fulfill_taker"

        fill_timestamp = float(trade_data.get("timestamp") or trade_data.get("created_at") or trade_data.get("t") or self.current_timestamp)
        # REST API 'timestamp' is in seconds; milliseconds if > 1e12.
        if fill_timestamp > 1e12:
            fill_timestamp *= 1e-3

        # Use actual fee amount from WS message when available (mirrors perp connector approach).
        # Exchange WS messages carry taker_fee/maker_fee (rate in PPM) + usd_amount (USDC).
        # Actual fee = usd_amount * fee_rate_ppm / 1_000_000.  Falls back to schema estimate.
        _fee_schema = self.trade_fee_schema()
        _fee_percent = (
            _fee_schema.taker_percent_fee_decimal if is_taker else _fee_schema.maker_percent_fee_decimal
        )
        _fee_raw = trade_data.get("taker_fee") if is_taker else trade_data.get("maker_fee")
        _usd_amount_raw = trade_data.get("usd_amount") or trade_data.get("quote_amount")
        if _fee_raw is not None and _usd_amount_raw is not None:
            try:
                _actual_fee = Decimal(str(_usd_amount_raw)) * Decimal(str(_fee_raw)) / Decimal("1000000")
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=_fee_schema,
                    trade_type=tracked_order.trade_type,
                    percent_token=tracked_order.quote_asset,
                    flat_fees=[TokenAmount(amount=_actual_fee, token=tracked_order.quote_asset)],
                )
            except Exception:
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=_fee_schema,
                    trade_type=tracked_order.trade_type,
                    percent=_fee_percent,
                    percent_token=tracked_order.quote_asset,
                    flat_fees=[],
                )
        else:
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=_fee_schema,
                trade_type=tracked_order.trade_type,
                percent=_fee_percent,
                percent_token=tracked_order.quote_asset,
                flat_fees=[],
            )

        return TradeUpdate(
            trade_id=str(trade_data.get("trade_id_str") or trade_data.get("trade_id") or trade_data.get("history_id") or trade_data.get("id") or trade_data.get("h") or ""),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=fill_timestamp,
            fill_price=fill_price,
            fill_base_amount=fill_base_amount,
            fill_quote_amount=fill_price * fill_base_amount,
            fee=fee,
            is_taker=is_taker,
        )

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules = []
        entries = exchange_info_dict.get("order_books") or exchange_info_dict.get("data") or []
        for entry in entries:
            market_type = (entry.get("market_type") or "").lower()
            if market_type and market_type != "spot":
                continue

            symbol = entry.get("symbol")
            if symbol is None:
                continue

            hb_pair = self._hb_pair_from_symbol(symbol)
            amount_decimals = int(entry.get("supported_size_decimals", 4))
            price_decimals = int(entry.get("supported_price_decimals", 2))
            min_amount_increment = Decimal("1") / (Decimal("10") ** amount_decimals)
            min_price = Decimal("1") / (Decimal("10") ** price_decimals)
            min_order_size = Decimal(str(entry.get("min_base_amount") or "0")) or min_amount_increment
            min_notional = Decimal(str(entry.get("min_quote_amount") or "0"))

            rules.append(
                TradingRule(
                    trading_pair=hb_pair,
                    min_order_size=min_order_size,
                    min_price_increment=min_price,
                    min_base_amount_increment=min_amount_increment,
                    min_notional_size=min_notional,
                )
            )
        return rules

    async def start_network(self):
        # Fetch balances immediately so check_budget_available() in the strategy tick
        # sees real balances instead of zeros before the first polling interval fires.
        # Wrap in try-except so a transient network error on startup doesn't prevent
        # the WS and polling loop from starting; balance will be loaded on first poll.
        try:
            await self._update_balances(force_rest=True)
        except Exception as e:
            self.logger().warning(
                "Initial balance fetch failed; will retry in next polling cycle: %s", e
            )
        await super().start_network()

    async def _update_balances(self, force_rest: bool = False):
        if not self._should_poll_balances_via_rest(force_rest=force_rest):
            return

        response = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_INFO_PATH_URL,
            params=self._account_query_params(),
            is_auth_required=True,
            return_err=True,
            limit_id=CONSTANTS.GET_ACCOUNT_INFO_PATH_URL,
        )

        if not self._is_ok_response(response):
            if self._is_rate_limited_response(response):
                return
            code = response.get("code") if isinstance(response, dict) else ""
            msg = response.get("message") or response.get("error") or "" if isinstance(response, dict) else str(response)
            raise IOError(
                f"Cannot connect to Lighter: server returned code {code}. "
                f"{msg} — check your account index and API key index."
            )

        account_data = self._account_from_response(response)
        if not account_data:
            raise IOError(
                f"Cannot connect to Lighter: no account data returned. "
                f"Verify your account index is correct. Response: {response}"
            )

        remote_asset_names = set()
        for asset_entry in account_data.get("assets", []):
            asset_symbol = asset_entry.get("symbol")
            if asset_symbol is None:
                continue
            remote_asset_names.add(asset_symbol)

            total_balance = Decimal(str(asset_entry.get("balance") or "0"))
            locked_balance = Decimal(str(asset_entry.get("locked_balance") or "0"))
            available_balance = total_balance - locked_balance

            self._account_balances[asset_symbol] = total_balance

            # Guard against stale REST data overwriting an optimistic order-placement lock.
            # After an order is placed, the exchange may not yet have added it to
            # locked_balance (ZK batch propagation lag, up to a few seconds).  If so,
            # the REST response shows locked_balance == 0 and an inflated available —
            # skip overwriting the lock until the exchange catches up or 3 s elapse.
            _opt_locks = getattr(self, "_optimistic_balance_lock", {})
            _opt_lock_entry = _opt_locks.get(asset_symbol)
            if _opt_lock_entry is not None:
                _opt_locked_avail, _opt_lock_ts = _opt_lock_entry
                if locked_balance == Decimal("0") and available_balance > _opt_locked_avail and (time.time() - _opt_lock_ts) < 3.0:
                    # Exchange hasn't registered the new order yet — keep optimistic lock.
                    continue
                else:
                    _opt_locks.pop(asset_symbol, None)

            self._account_available_balances[asset_symbol] = available_balance

        # For the spot connector, keep the original per-asset available balance calculation
        # (`balance - locked_balance`) and ignore the top-level `available_balance` field.

        for local_asset in list(self._account_balances.keys()):
            if local_asset not in remote_asset_names:
                self._account_balances.pop(local_asset, None)
                self._account_available_balances.pop(local_asset, None)

        self._last_balance_update_timestamp = self._current_timestamp_safely()
        if self._balance_refresh_required_since > 0 and self._last_balance_update_timestamp >= self._balance_refresh_required_since:
            self._balance_refresh_required_since = 0.0

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        current_time = self.current_timestamp

        is_ask = (order.trade_type == TradeType.SELL)
        # Get the original lighter client_order_index.  WS events may have updated
        # exchange_order_id from the client_order_index to the server order_id, so always
        # prefer the recorded mapping and fall back to exchange_order_id only as a last resort.
        _hb_to_coi = getattr(self, "_hb_order_id_to_client_order_index", {})
        client_order_idx = _hb_to_coi.get(order.client_order_id)
        if client_order_idx is None:
            client_order_idx = int(str(order.exchange_order_id)) if self._is_int_string(str(order.exchange_order_id)) else None

        # If we cannot map the order to a valid client_order_index, do not scan global
        # account trades. Otherwise unrelated market fills can be attributed to this order.
        if client_order_idx is None:
            self._order_history_last_poll_timestamp[str(order.exchange_order_id)] = current_time
            return trade_updates

        client_order_idx_str = str(client_order_idx)
        candidate_order_indices: Set[int] = {client_order_idx}
        exchange_order_id_str = str(order.exchange_order_id or "")
        if self._is_int_string(exchange_order_id_str):
            candidate_order_indices.add(int(exchange_order_id_str))

        # Some /trades payloads only expose server order_index (order_id/order_index) and
        # omit ask_client_id/bid_client_id. Bridge server order_index -> client_order_index
        # from WS-derived mapping to keep fill recovery working after FILLED timeout paths.
        _soi_to_coi = getattr(self, "_server_order_index_to_client_order_index", {})
        for server_order_idx, mapped_coi in _soi_to_coi.items():
            if str(mapped_coi) == client_order_idx_str and self._is_int_string(str(server_order_idx)):
                candidate_order_indices.add(int(str(server_order_idx)))

        # exchange_order_id == str(client_order_index). The /trades filter 'order_index' refers to
        # the exchange-assigned sequential order_index, which differs from client_order_index.
        # Filter client-side using ask_client_id / bid_client_id instead.
        last_poll_ts = self._order_history_last_poll_timestamp.get(order.exchange_order_id, order.creation_timestamp)
        from_ts = max(0, int(last_poll_ts - self._TRADE_HISTORY_TIME_DRIFT_BUFFER))
        latest_matched_fill_ts: Optional[float] = None

        params = {
            "account_index": self._get_account_index(),
            "limit": 100,
            "sort_by": "timestamp",
            "from": from_ts,
        }

        while True:
            response = await self._api_get(
                path_url=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
                params=params,
                is_auth_required=True,
                limit_id=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
            )

            if not response.get("success") or not (response.get("trades") or response.get("data")):
                break

            for trade_message in response.get("trades") or response.get("data") or []:
                # Prefer explicit client order index fields when present.
                side_client_ids = [trade_message.get("ask_client_id"), trade_message.get("bid_client_id")]
                present_side_client_ids = [cid for cid in side_client_ids if cid is not None]
                if present_side_client_ids:
                    matched_side_client_id = False
                    for side_client_id in present_side_client_ids:
                        if self._is_int_string(str(side_client_id)) and int(str(side_client_id)) in candidate_order_indices:
                            matched_side_client_id = True
                            break
                    if not matched_side_client_id:
                        continue
                else:
                    # Fallback for payload variants that only include order_id/order_index.
                    raw_order_idx = trade_message.get("order_id") or trade_message.get("orderId") or trade_message.get("order_index")
                    if (
                        raw_order_idx is None
                        or not self._is_int_string(str(raw_order_idx))
                        or int(str(raw_order_idx)) not in candidate_order_indices
                    ):
                        continue

                # 'timestamp' is in seconds per the API spec.
                fill_timestamp = float(
                    trade_message.get("timestamp")
                    or trade_message.get("created_at")
                    or trade_message.get("t")
                    or 0
                )
                if fill_timestamp > 1e12:
                    fill_timestamp *= 1e-3

                fill_price = Decimal(str(trade_message.get("price") or "0"))
                # API field is 'size' (not 'amount').
                fill_base_amount = Decimal(str(trade_message.get("size") or "0"))

                # Determine taker side from is_maker_ask.
                is_maker_ask = trade_message.get("is_maker_ask", None)
                if is_maker_ask is not None:
                    is_taker = (is_ask and not is_maker_ask) or (not is_ask and is_maker_ask)
                else:
                    is_taker = trade_message.get("event_type") == "fulfill_taker"

                _fee_schema_h = self.trade_fee_schema()
                _fee_percent_h = (
                    _fee_schema_h.taker_percent_fee_decimal if is_taker else _fee_schema_h.maker_percent_fee_decimal
                )
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=_fee_schema_h,
                    trade_type=order.trade_type,
                    percent=_fee_percent_h,
                    percent_token=order.quote_asset,
                    flat_fees=[],
                )

                trade_updates.append(
                    TradeUpdate(
                        trade_id=str(trade_message.get("trade_id_str") or trade_message.get("trade_id") or trade_message.get("history_id") or trade_message.get("id") or ""),
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        trading_pair=order.trading_pair,
                        fill_timestamp=fill_timestamp,
                        fill_price=fill_price,
                        fill_base_amount=fill_base_amount,
                        fill_quote_amount=fill_price * fill_base_amount,
                        fee=fee,
                        is_taker=is_taker,
                    )
                )
                if latest_matched_fill_ts is None or fill_timestamp > latest_matched_fill_ts:
                    latest_matched_fill_ts = fill_timestamp

            # Pagination: API returns next_cursor (null when no more pages).
            if response.get("next_cursor"):
                params["cursor"] = response["next_cursor"]
            else:
                break

        # Only advance this order-specific cursor once at least one matching fill is seen.
        # Advancing on empty results can permanently skip late-indexed fills whose exchange
        # timestamp is older than the next request's `from` window.
        if latest_matched_fill_ts is not None:
            self._order_history_last_poll_timestamp[order.exchange_order_id] = max(
                current_time,
                latest_matched_fill_ts,
            )
        else:
            self._order_history_last_poll_timestamp[order.exchange_order_id] = last_poll_ts
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        params: Dict[str, Any] = {
            "limit": 100,
        }
        try:
            params["account_index"] = self._get_account_index()
        except Exception:
            # Unit tests may instantiate this class via __new__ without credentials configured.
            pass

        active_response = await self._api_get(
            path_url=CONSTANTS.GET_ACTIVE_ORDERS_PATH_URL,
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.GET_ACTIVE_ORDERS_PATH_URL,
            return_err=True,
        )

        response = active_response

        if not response.get("success"):
            if self._is_rate_limited_response(response):
                return self._current_state_order_update(tracked_order)
            raise IOError(f"Failed to fetch order status for {tracked_order.client_order_id}: {response}")

        rows = response.get("orders") or response.get("data") or []
        target_exchange_order_id = str(tracked_order.exchange_order_id or "")
        expected_symbol = tracked_order.trading_pair.replace("-", "/")

        has_order_id_fields = any(
            any(key in item for key in ("client_order_id", "client_order_index", "order_id", "order_index"))
            for item in rows
        )
        if target_exchange_order_id and has_order_id_fields:
            # The connector may track either client_order_index (initially) or the real exchange order_id
            # depending on where in the lifecycle the order is.
            rows = [
                item for item in rows
                if (
                    str(item.get("client_order_id") or item.get("client_order_index") or "") == target_exchange_order_id
                    or str(item.get("order_id") or item.get("order_index") or "") == target_exchange_order_id
                )
            ]

        if expected_symbol:
            # Guard against stale status contamination from different markets.
            rows = [
                item for item in rows
                if str(item.get("symbol") or "") in {"", expected_symbol, tracked_order.trading_pair}
            ]

        if len(rows) == 0:
            inactive_response = await self._api_get(
                path_url=CONSTANTS.GET_ORDER_HISTORY_PATH_URL,
                params=params,
                is_auth_required=True,
                limit_id=CONSTANTS.GET_ORDER_HISTORY_PATH_URL,
                return_err=True,
            )
            if not inactive_response.get("success"):
                if self._is_rate_limited_response(inactive_response):
                    return self._current_state_order_update(tracked_order)
                raise IOError(f"Failed to fetch order status for {tracked_order.client_order_id}: {inactive_response}")

            inactive_rows = inactive_response.get("orders") or inactive_response.get("data") or []
            has_inactive_id_fields = any(
                any(key in item for key in ("client_order_id", "client_order_index", "order_id", "order_index"))
                for item in inactive_rows
            )
            if target_exchange_order_id and has_inactive_id_fields:
                inactive_rows = [
                    item for item in inactive_rows
                    if str(item.get("client_order_id") or item.get("client_order_index") or "") == target_exchange_order_id
                    or str(item.get("order_id") or item.get("order_index") or "") == target_exchange_order_id
                ]

            if expected_symbol:
                inactive_rows = [
                    item for item in inactive_rows
                    if str(item.get("symbol") or "") in {"", expected_symbol, tracked_order.trading_pair}
                ]

            if len(inactive_rows) > 0:
                newest_inactive = max(inactive_rows, key=lambda item: item.get("updated_at") or item.get("created_at") or 0)
                raw_inactive_status = str(newest_inactive.get("status") or newest_inactive.get("order_status") or "closed").lower()
                new_state = self._state_from_raw_order_status(raw_inactive_status)
            else:
                new_state = getattr(tracked_order, "current_state", OrderState.OPEN)
            update_ts = getattr(self, "current_timestamp", None)
            if update_ts is None:
                update_ts = self._time()
            return OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=update_ts,
                new_state=new_state,
            )

        newest = max(rows, key=lambda item: item.get("updated_at") or item.get("created_at") or 0)
        raw_status = str(newest.get("status") or newest.get("order_status") or "open").lower()
        state = self._state_from_raw_order_status(raw_status)
        # updated_at / created_at may be in ms; divide if > 1e12.
        update_ts_raw = float(newest.get("updated_at") or newest.get("created_at") or self.current_timestamp)
        update_ts = update_ts_raw * 1e-3 if update_ts_raw > 1e12 else update_ts_raw

        return OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_ts,
            new_state=state,
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LighterAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LighterAPIUserStreamDataSource(
            connector=self,
            api_factory=self._web_assistants_factory,
            auth=self._auth,
            domain=self._domain,
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        entries = exchange_info.get("order_books") or exchange_info.get("data") or []
        mapping = bidict()
        for entry in entries:
            market_type = (entry.get("market_type") or "").lower()
            if market_type and market_type != "spot":
                continue
            symbol = entry.get("symbol")
            if symbol is None:
                continue
            hb_pair = self._hb_pair_from_symbol(symbol)
            mapping[symbol] = hb_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _api_request(
        self,
        path_url: str,
        overwrite_url: Optional[str] = None,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False,
        return_err: bool = False,
        limit_id: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        headers = dict(headers or {})
        params = dict(params or {})
        if is_auth_required:
            auth_token = ""
            try:
                auth_token = self._get_lighter_auth_token()
            except Exception:
                # Some unit tests instantiate the connector with __new__ and without signer setup.
                auth_token = ""

            if auth_token:
                headers.setdefault("Authorization", auth_token)
                params.setdefault("auth", auth_token)
                params.setdefault("authorization", auth_token)

        if is_auth_required:
            return await self._sdk_api_request(
                path_url=path_url,
                method=method,
                params=params,
                data=data,
                limit_id=limit_id,
                headers=headers,
                return_err=return_err,
            )

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = overwrite_url or await self._api_request_url(path_url=path_url, is_auth_required=is_auth_required)

        return await rest_assistant.execute_request(
            url=url,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            return_err=return_err,
            throttler_limit_id=limit_id or path_url,
            headers=headers,
        )

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        prices: Dict[str, float] = {}
        stats = await self._api_request(path_url=CONSTANTS.GET_PRICES_PATH_URL, method=RESTMethod.GET)
        entries = stats.get("order_book_stats") or stats.get("data") or []

        for entry in entries:
            symbol = entry.get("symbol")
            if symbol is None:
                continue
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
            except KeyError:
                continue
            if trading_pair in trading_pairs:
                last_price = entry.get("last_trade_price")
                if last_price is not None:
                    prices[trading_pair] = float(last_price)
        return prices

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_balances(),
            self._update_order_status(),
            self._update_lost_orders_status(),
        )
        await self._cleanup_startup_orphan_orders()
        # Periodic runtime orphan check: runs every 10 status-poll cycles (~2 min).
        # Catches orders false-cancelled locally mid-session that remain open on the exchange,
        # locking USDC balance and preventing correctly-sized orders from being placed.
        self._runtime_orphan_poll_counter += 1
        if self._runtime_orphan_poll_counter >= 10:
            self._runtime_orphan_poll_counter = 0
            await self._cleanup_runtime_orphan_orders()

    async def _update_order_fills_from_trades(self, force_rest_reconcile: bool = False):
        # Skip the bulk REST trade-history scan when the WS user stream is healthy.
        # The account_trades WS channel delivers fills in real-time; this REST endpoint
        # is redundant during normal operation and wastes rate-limit quota.
        # Fall back to REST polling only when WS has been silent for > TICK_INTERVAL_LIMIT,
        # unless a caller explicitly forces reconciliation.
        if self._is_private_user_stream_healthy() and not force_rest_reconcile:
            return

        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if long_interval_current_tick > long_interval_last_tick or (
            self.in_flight_orders and small_interval_current_tick > small_interval_last_tick
        ):
            # Build lookup: exchange_order_id (str) -> tracked order.
            order_by_exchange_id_map = {order.exchange_order_id: order for order in self._order_tracker.all_fillable_orders.values()}
            # Also build per-direction maps for ask/bid_client_id matching.
            ask_order_map = {eid: o for eid, o in order_by_exchange_id_map.items() if o.trade_type == TradeType.SELL}
            bid_order_map = {eid: o for eid, o in order_by_exchange_id_map.items() if o.trade_type == TradeType.BUY}
            # Augment maps with client_order_index entries so that ask/bid_client_id matching
            # works even after WS events have updated exchange_order_id to the server order_id.
            _coi_map = getattr(self, "_client_order_index_to_client_order_id", {})
            for coi_str, hb_coid in _coi_map.items():
                o = self._order_tracker.all_fillable_orders.get(hb_coid)
                if o is None:
                    continue
                if o.trade_type == TradeType.SELL:
                    ask_order_map.setdefault(coi_str, o)
                elif o.trade_type == TradeType.BUY:
                    bid_order_map.setdefault(coi_str, o)

            # Record the timestamp before the request so concurrent fills that arrive during
            # the request window are captured in the next polling cycle.
            query_from_ts = (
                max(0, int(self._last_trades_poll_timestamp - self._TRADE_HISTORY_TIME_DRIFT_BUFFER))
                if self._last_trades_poll_timestamp > 0
                else 0
            )
            self._last_trades_poll_timestamp = self.current_timestamp

            poll_params: Dict[str, Any] = {
                "account_index": self._get_account_index(),
                "limit": 100,
                "sort_by": "timestamp",
            }
            if query_from_ts > 0:
                poll_params["from"] = query_from_ts

            response = await self._api_get(
                path_url=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
                params=poll_params,
                is_auth_required=True,
                return_err=True,
                limit_id=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
            )
            response_failed = response.get("success") is False or (
                "code" in response and not self._is_ok_response(response)
            )
            if response_failed:
                if self._is_rate_limited_response(response):
                    return
                raise IOError(f"Failed to fetch trade history updates: {response}")
            # API returns 'trades' key; fall back to 'data' for test mocks.
            for trade in response.get("trades") or response.get("data") or []:
                # Match via ask_client_id / bid_client_id (= client_order_index = exchange_order_id).
                ask_cid = str(trade.get("ask_client_id") or "")
                bid_cid = str(trade.get("bid_client_id") or "")
                tracked_order = ask_order_map.get(ask_cid) or bid_order_map.get(bid_cid)
                if tracked_order is None:
                    # Order is no longer in the tracker (e.g., completed in a previous session or
                    # lost before fill was recorded). Apply the same "untracked fill" path that
                    # Hyperliquid uses: fire OrderFilledEvent directly after dedup check so the
                    # fill is persisted to the DB (TradeFill table) and shown in `history --status`.
                    exchange_trade_id = str(trade.get("trade_id_str") or trade.get("trade_id") or trade.get("history_id") or trade.get("id") or "")
                    if not exchange_trade_id:
                        continue
                    symbol = str(trade.get("symbol") or "")
                    if not symbol:
                        continue
                    try:
                        trading_pair = self._hb_pair_from_symbol(symbol)
                    except Exception:
                        continue
                    if trading_pair not in self.trading_pairs:
                        continue
                    # Determine which side belongs to this account.  bid_cid non-zero → BUY.
                    is_bid_side = bool(bid_cid and bid_cid != "0")
                    trade_type = TradeType.BUY if is_bid_side else TradeType.SELL
                    exchange_order_id = bid_cid if is_bid_side else ask_cid
                    if self.is_confirmed_new_order_filled_event(exchange_trade_id, exchange_order_id, trading_pair):
                        fill_timestamp_u = float(
                            trade.get("timestamp") or trade.get("created_at") or trade.get("t") or self.current_timestamp
                        )
                        if fill_timestamp_u > 1e12:
                            fill_timestamp_u *= 1e-3
                        fill_price_u = Decimal(str(trade.get("price") or "0"))
                        fill_base_u = Decimal(str(trade.get("size") or trade.get("amount") or "0"))
                        is_maker_ask_u = trade.get("is_maker_ask", None)
                        is_taker_u = (is_maker_ask_u is not None) and (
                            (trade_type == TradeType.SELL and not is_maker_ask_u)
                            or (trade_type == TradeType.BUY and is_maker_ask_u)
                        )
                        _fee_schema_u = self.trade_fee_schema()
                        _fee_percent_u = (
                            _fee_schema_u.taker_percent_fee_decimal if is_taker_u else _fee_schema_u.maker_percent_fee_decimal
                        )
                        quote_asset = trading_pair.split("-")[1] if "-" in trading_pair else ""
                        fee_u = TradeFeeBase.new_spot_fee(
                            fee_schema=_fee_schema_u,
                            trade_type=trade_type,
                            percent=_fee_percent_u,
                            percent_token=quote_asset,
                            flat_fees=[],
                        )
                        self._current_trade_fills.add(TradeFillOrderDetails(
                            market=self.display_name,
                            exchange_trade_id=exchange_trade_id,
                            symbol=trading_pair,
                        ))
                        self.logger().info(
                            "[untracked-fill] Recovered fill for untracked order %s "
                            "(exchange_order_id=%s, trade_id=%s): %s %s %s @ %s",
                            self._exchange_order_ids.get(exchange_order_id, "unknown"),
                            exchange_order_id,
                            exchange_trade_id,
                            trade_type.name,
                            fill_base_u,
                            trading_pair,
                            fill_price_u,
                        )
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=fill_timestamp_u,
                                order_id=self._exchange_order_ids.get(exchange_order_id, None),
                                trading_pair=trading_pair,
                                trade_type=trade_type,
                                order_type=OrderType.LIMIT,
                                price=fill_price_u,
                                amount=fill_base_u,
                                trade_fee=fee_u,
                                exchange_trade_id=exchange_trade_id,
                            ),
                        )
                    continue

                is_ask = (tracked_order.trade_type == TradeType.SELL)
                is_maker_ask = trade.get("is_maker_ask", None)
                is_taker = (is_maker_ask is not None) and ((is_ask and not is_maker_ask) or (not is_ask and is_maker_ask))

                fill_timestamp = float(
                    trade.get("timestamp")
                    or trade.get("created_at")
                    or trade.get("t")
                    or self.current_timestamp
                )
                if fill_timestamp > 1e12:
                    fill_timestamp *= 1e-3

                # Use actual fee amount from WS message when available (mirrors perp connector).
                _fee_schema_at = self.trade_fee_schema()
                _fee_percent_at = (
                    _fee_schema_at.taker_percent_fee_decimal if is_taker else _fee_schema_at.maker_percent_fee_decimal
                )
                _fee_raw_at = trade.get("taker_fee") if is_taker else trade.get("maker_fee")
                _usd_amount_at = trade.get("usd_amount") or trade.get("quote_amount")
                if _fee_raw_at is not None and _usd_amount_at is not None:
                    try:
                        _actual_fee_at = Decimal(str(_usd_amount_at)) * Decimal(str(_fee_raw_at)) / Decimal("1000000")
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=_fee_schema_at,
                            trade_type=tracked_order.trade_type,
                            percent_token=tracked_order.quote_asset,
                            flat_fees=[TokenAmount(amount=_actual_fee_at, token=tracked_order.quote_asset)],
                        )
                    except Exception:
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=_fee_schema_at,
                            trade_type=tracked_order.trade_type,
                            percent=_fee_percent_at,
                            percent_token=tracked_order.quote_asset,
                            flat_fees=[],
                        )
                else:
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=_fee_schema_at,
                        trade_type=tracked_order.trade_type,
                        percent=_fee_percent_at,
                        percent_token=tracked_order.quote_asset,
                        flat_fees=[],
                    )
                fill_price = Decimal(str(trade.get("price") or "0"))
                fill_base = Decimal(str(trade.get("size") or trade.get("amount") or "0"))
                trade_update = TradeUpdate(
                    trade_id=str(trade.get("trade_id_str") or trade.get("trade_id") or trade.get("history_id") or trade.get("id") or ""),
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                    trading_pair=tracked_order.trading_pair,
                    fee=fee,
                    fill_base_amount=fill_base,
                    fill_quote_amount=fill_price * fill_base,
                    fill_price=fill_price,
                    fill_timestamp=fill_timestamp,
                    is_taker=is_taker,
                )
                self._order_tracker.process_trade_update(trade_update)

    async def _cleanup_startup_orphan_orders(self) -> None:
        """One-time startup cleanup: cancel ALL untracked active SPOT orders from previous sessions.

        Untracked orders lock USDC/base-asset funds, causing the strategy to underestimate
        available balance and place smaller-than-minimum-notional orders. Cancelling them
        on first startup frees the locked funds and restores correct available balance.

        Runs ONCE after the first successful status poll cycle.
        """
        if self._startup_orphan_cleanup_done:
            return
        self._startup_orphan_cleanup_done = True

        known_exchange_ids: Set[str] = {
            str(o.exchange_order_id) for o in self.in_flight_orders.values()
        }
        known_client_order_indices: Set[str] = set(self._client_order_index_to_client_order_id.keys())

        try:
            params: Dict[str, Any] = {"limit": 200}
            try:
                params["account_index"] = self._get_account_index()
            except Exception:
                return

            response = await self._api_get(
                path_url=CONSTANTS.GET_ACTIVE_ORDERS_PATH_URL,
                params=params,
                is_auth_required=True,
                return_err=True,
            )
            if not (isinstance(response, dict) and response.get("success")):
                return

            rows = response.get("orders") or response.get("data") or []
            for row in rows:
                row_coi = str(row.get("client_order_id") or row.get("client_order_index") or "")
                row_oid = str(row.get("order_id") or row.get("order_index") or "")
                is_tracked = (
                    (row_coi and row_coi in known_exchange_ids)
                    or (row_coi and row_coi in known_client_order_indices)
                    or (row_oid and row_oid in known_exchange_ids)
                )
                if is_tracked:
                    continue

                cancel_index = row_coi or row_oid
                if not cancel_index or not self._is_int_string(cancel_index):
                    continue

                symbol = str(row.get("symbol") or row.get("market") or "")
                self.logger().info(
                    "[startup cleanup] Cancelling orphan SPOT order index=%s symbol=%s from a previous session.",
                    cancel_index,
                    symbol,
                )
                try:
                    hb_pair = self._hb_pair_from_symbol(symbol) if symbol else None
                    if hb_pair is None:
                        # Try to infer market_id from the symbol field
                        self.logger().warning(
                            "[startup cleanup] Cannot determine trading pair for orphan order %s; skipping.",
                            cancel_index,
                        )
                        continue
                    market_id, _, _, _ = await self._get_market_spec(hb_pair)
                    async with self._signer_client_lock:
                        signer_client = self._get_lighter_signer_client()
                        _, tx_response, error = await signer_client.cancel_order(
                            market_index=market_id,
                            order_index=int(cancel_index),
                            api_key_index=self._get_api_key_index(),
                        )
                    if error is not None:
                        self.logger().warning(
                            "[startup cleanup] Failed to cancel orphan SPOT order %s: %s", cancel_index, error
                        )
                    else:
                        self.logger().info(
                            "[startup cleanup] Cancelled orphan SPOT order %s for %s.",
                            cancel_index, symbol,
                        )
                except Exception as cancel_err:
                    self.logger().warning(
                        "[startup cleanup] Exception cancelling orphan SPOT order %s: %s",
                        cancel_index, cancel_err,
                    )

            # Schedule a balance refresh after cancelling orphan orders.
            self._schedule_fast_balance_sync(min_interval_seconds=0.0)
        except Exception as ex:
            self.logger().warning("[startup cleanup] SPOT orphan cleanup failed: %s", ex)

    async def _cleanup_runtime_orphan_orders(self) -> None:
        """Periodic runtime cleanup: cancel any active SPOT exchange order not tracked by this bot.

        Unlike ``_cleanup_startup_orphan_orders`` (which runs once at startup), this method
        runs every 10 status-poll cycles (~2 minutes) to catch orders that became orphaned
        *during* the session — for example when a WS snapshot replay fires a false CANCELED
        event locally while the exchange still holds the order open, locking the USDC balance
        and preventing the strategy from placing correctly-sized orders.
        """
        known_exchange_ids: Set[str] = {
            str(o.exchange_order_id) for o in self.in_flight_orders.values()
        }
        known_client_order_indices: Set[str] = set(self._client_order_index_to_client_order_id.keys())

        try:
            params: Dict[str, Any] = {"limit": 200}
            try:
                params["account_index"] = self._get_account_index()
            except Exception:
                return

            response = await self._api_get(
                path_url=CONSTANTS.GET_ACTIVE_ORDERS_PATH_URL,
                params=params,
                is_auth_required=True,
                return_err=True,
            )
            if not (isinstance(response, dict) and response.get("success")):
                return

            rows = response.get("orders") or response.get("data") or []
            orphans_found = 0
            for row in rows:
                row_coi = str(row.get("client_order_id") or row.get("client_order_index") or "")
                row_oid = str(row.get("order_id") or row.get("order_index") or "")
                is_tracked = (
                    (row_coi and row_coi in known_exchange_ids)
                    or (row_coi and row_coi in known_client_order_indices)
                    or (row_oid and row_oid in known_exchange_ids)
                )
                if is_tracked:
                    continue

                cancel_index = row_coi or row_oid
                if not cancel_index or not self._is_int_string(cancel_index):
                    continue

                orphans_found += 1
                symbol = str(row.get("symbol") or row.get("market") or "")
                self.logger().warning(
                    "[runtime orphan cleanup] Cancelling untracked SPOT order index=%s symbol=%s "
                    "(runtime orphan — likely from a WS false-cancel that dropped local tracking "
                    "while the exchange order remained open, locking balance).",
                    cancel_index,
                    symbol,
                )
                try:
                    hb_pair = self._hb_pair_from_symbol(symbol) if symbol else None
                    if hb_pair is None:
                        self.logger().warning(
                            "[runtime orphan cleanup] Cannot determine trading pair for orphan order %s; skipping.",
                            cancel_index,
                        )
                        continue
                    market_id, _, _, _ = await self._get_market_spec(hb_pair)
                    async with self._signer_client_lock:
                        signer_client = self._get_lighter_signer_client()
                        _, tx_response, error = await signer_client.cancel_order(
                            market_index=market_id,
                            order_index=int(cancel_index),
                            api_key_index=self._get_api_key_index(),
                        )
                    if error is not None:
                        self.logger().warning(
                            "[runtime orphan cleanup] Failed to cancel orphan SPOT order %s: %s",
                            cancel_index,
                            error,
                        )
                    else:
                        self.logger().info(
                            "[runtime orphan cleanup] Cancelled orphan SPOT order %s for %s.",
                            cancel_index,
                            symbol,
                        )
                except Exception as cancel_err:
                    self.logger().warning(
                        "[runtime orphan cleanup] Exception cancelling orphan SPOT order %s: %s",
                        cancel_index,
                        cancel_err,
                    )

            if orphans_found > 0:
                # Refresh balance so locked funds are freed in the strategy's next cycle.
                self._schedule_fast_balance_sync(min_interval_seconds=0.0)
        except Exception as ex:
            self.logger().warning("[runtime orphan cleanup] SPOT runtime orphan cleanup failed: %s", ex)

    async def _update_order_status(self, force_rest_reconcile: bool = False):
        await self._update_order_fills_from_trades(force_rest_reconcile=force_rest_reconcile)

        # Always scan cached orders for missed fills — catches cancel-fill races regardless
        # of whether the WS is healthy.  When the WS is healthy _update_order_fills_from_trades
        # is skipped above, so without this unconditional call, fills for orders that were
        # cancelled via a cancel-fill race would never be recovered during normal operation.
        await self._rescue_cached_order_fills()

        if not self._should_reconcile_orders_via_rest(force_rest_reconcile=force_rest_reconcile):
            return

        await self._update_orders()

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        for order in orders:
            try:
                trade_updates = await self._all_trade_updates_for_order(order)
                for trade_update in trade_updates:
                    self._order_tracker.process_trade_update(trade_update)
            except Exception as request_error:
                # Do not block status updates when trade history endpoint rejects optional params.
                self.logger().warning(f"Error updating fills for active order {order.client_order_id}: {request_error}")

    async def _update_orders(self):
        for tracked_order in list(self.in_flight_orders.values()):
            order_update = await self._request_order_status(tracked_order=tracked_order)
            if (
                isinstance(order_update, OrderUpdate)
                and order_update.new_state in (OrderState.FILLED, OrderState.CANCELED)
                and not tracked_order.is_done
                and tracked_order.executed_amount_base < tracked_order.amount
            ):
                # Rescue fill fetch: the bulk trade-history poll ran before the fill appeared on
                # the exchange REST API.  Fetch fills specifically for this order now so the
                # tracker has the fill data before wait_until_completely_filled() times out.
                # Also covers CANCELED: an order can be cancelled after a partial or full fill
                # (cancel-fill race) — we must recover those fills before the order is evicted.
                try:
                    # Apply the resolved server order_index BEFORE fetching fills so that
                    # _all_trade_updates_for_order uses the correct ask_id/bid_id for matching
                    # — not the stale client_order_index when I=null in WS events prevented
                    # the normal mapping update (mirrors the perp connector's approach).
                    resolved_eid = order_update.exchange_order_id
                    if (
                        resolved_eid
                        and resolved_eid != "None"
                        and resolved_eid != str(tracked_order.exchange_order_id)
                    ):
                        tracked_order.update_exchange_order_id(resolved_eid)
                    fill_updates = await self._all_trade_updates_for_order(tracked_order)
                    for fill_update in fill_updates:
                        self._order_tracker.process_trade_update(fill_update)
                    if fill_updates:
                        self.logger().debug(
                            "[_update_orders] Rescue fill fetch found %d fill(s) for %s (state=%s)",
                            len(fill_updates),
                            tracked_order.client_order_id,
                            order_update.new_state.name,
                        )
                except Exception as ex:
                    is_rate_limited = self._is_rate_limited_exception(ex)
                    if is_rate_limited:
                        self.logger().debug(
                            "[_update_orders] Rescue fill fetch deferred for %s due to rate limit: %s",
                            tracked_order.client_order_id,
                            ex,
                        )
                    else:
                        self.logger().warning(
                            "[_update_orders] Rescue fill fetch failed for %s: %s",
                            tracked_order.client_order_id,
                            ex,
                        )
                    # Schedule a delayed retry so fills are recorded once the rate limit clears,
                    # even though process_order_update below marks the order as done now.
                    # _fetch_and_apply_fills uses the dedup guard so only one retry runs at a time.
                    safe_ensure_future(self._fetch_and_apply_fills(tracked_order, delay=10.0 if is_rate_limited else 5.0))
            self._order_tracker.process_order_update(order_update)
            if isinstance(order_update, OrderUpdate):
                self._schedule_balance_sync_for_terminal_update(order_update=order_update, tracked_order=tracked_order)

    async def _rescue_cached_order_fills(self):
        """Scan recently-cached (recently-cancelled) orders that have no fills yet.

        Acts as a safety net for the cancel-fill race: if the exchange filled an order
        shortly after the bot marked it CANCELED (e.g. via a WS cancel event or REST
        cancel TX), this scan ensures fill events are emitted once the REST trade history
        catches up.  Only scans orders cancelled within the last 5 minutes with zero fills.
        """
        _RESCUE_WINDOW_SECS = 300.0  # 5 minutes
        _MAX_RESCUES_PER_CYCLE = 4    # cap burst — remaining orders rescued on next poll
        now = self.current_timestamp
        cached = self._order_tracker.cached_orders
        rescued_count = 0
        for order in list(cached.values()):
            if rescued_count >= _MAX_RESCUES_PER_CYCLE:
                break
            # Only bother with orders that have no registered fills yet.
            if order.executed_amount_base > 0:
                continue
            # Only scan recently-cancelled orders to limit API calls.
            age = now - order.last_update_timestamp
            if age > _RESCUE_WINDOW_SECS:
                continue
            # Skip if a fetch is already running for this order (dedup guard).
            if order.client_order_id in self._fill_fetch_in_progress:
                continue
            rescued_count += 1
            try:
                fills = await self._all_trade_updates_for_order(order)
                for fill in fills:
                    self._order_tracker.process_trade_update(fill)
                if fills:
                    # Apply fill balance credit for the cancel-fill race (cached CANCELED orders
                    # that were actually filled before the cancel TX was processed).
                    _order_state = getattr(order, "current_state", None)
                    if _order_state == OrderState.CANCELED:
                        self._release_locked_balance_on_fill(order)
                    self.logger().info(
                        "[rescue-cached] Found %d fill(s) for recently-cached order %s",
                        len(fills),
                        order.client_order_id,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.logger().debug(
                    "[rescue-cached] Fill fetch failed for cached order %s: %s",
                    order.client_order_id,
                    err,
                )

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise

    def _create_trade_fill_updates(self, inflight_order: InFlightOrder, fills_data: List[Dict[str, Any]]) -> List[TradeUpdate]:
        trade_updates: List[TradeUpdate] = []
        for fill_data in fills_data:
            fill_timestamp = float(
                fill_data.get("timestamp")
                or fill_data.get("created_at")
                or fill_data.get("t")
                or self.current_timestamp
            )
            if fill_timestamp > 1e12:
                fill_timestamp *= 1e-3
            trade_update = TradeUpdate(
                trade_id=str(fill_data.get("trade_id") or fill_data.get("id") or fill_data.get("h")),
                client_order_id=inflight_order.client_order_id,
                exchange_order_id=inflight_order.exchange_order_id,
                trading_pair=inflight_order.trading_pair,
                fill_timestamp=fill_timestamp,
                fill_price=Decimal(str(fill_data.get("price") or fill_data.get("p") or "0")),
                fill_base_amount=Decimal(str(fill_data.get("size") or fill_data.get("amount") or fill_data.get("a") or "0")),
                fill_quote_amount=Decimal(str(fill_data.get("quote_amount") or fill_data.get("q") or "0")),
                fee=self._get_fee(
                    base_currency=inflight_order.base_asset,
                    quote_currency=inflight_order.quote_asset,
                    order_type=inflight_order.order_type,
                    order_side=inflight_order.trade_type,
                    amount=inflight_order.amount,
                    price=inflight_order.price,
                ),
            )
            trade_updates.append(trade_update)
        return trade_updates

    async def _update_orders_with_error_handler(
        self,
        orders: List[InFlightOrder],
        fetch_updates: Callable,
        error_handler: Callable,
    ):
        for order in orders:
            try:
                updates = await fetch_updates(order)
                if isinstance(updates, OrderUpdate):
                    self._order_tracker.process_order_update(updates)
                elif isinstance(updates, list):
                    for update in updates:
                        if isinstance(update, TradeUpdate):
                            self._order_tracker.process_trade_update(update)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                await error_handler(order, request_error)

    async def _handle_update_error_for_active_order(self, order: InFlightOrder, request_error: Exception):
        self.logger().warning(f"Error updating active order {order.client_order_id}: {request_error}")

    async def _handle_update_error_for_lost_order(self, order: InFlightOrder, request_error: Exception):
        self.logger().warning(f"Error updating lost order {order.client_order_id}: {request_error}")

    async def _update_lost_orders(self):
        await self._update_orders_with_error_handler(
            orders=list(self._order_tracker.lost_orders.values()),
            fetch_updates=self._request_order_status,
            error_handler=self._handle_update_error_for_lost_order,
        )

    async def _cancel_lost_orders(self):
        for _, lost_order in self._order_tracker.lost_orders.items():
            await self._execute_order_cancel(order=lost_order)

    async def _execute_order_cancel(self, order: InFlightOrder) -> Optional[str]:
        """Reconcile order state on cancel errors to avoid stale active orders in TUI."""
        if order.client_order_id in self._cancel_in_flight_client_order_ids:
            self.logger().debug(
                "Skipping duplicate cancel attempt for %s because a previous cancel is still in-flight.",
                order.client_order_id,
            )
            return None

        self._cancel_in_flight_client_order_ids.add(order.client_order_id)
        try:
            # Use the base cancel/update flow so OrderState.CANCELED is emitted immediately
            # when cancel submission succeeds (`is_cancel_request_in_exchange_synchronous = True`).
            # Unit tests may provide lightweight order stubs without full fields.
            if hasattr(order, "trading_pair"):
                cancelled = await self._execute_order_cancel_and_process_update(order=order)
            else:
                cancelled = await self._place_cancel(order_id=order.client_order_id, tracked_order=order)
            if cancelled:
                return order.client_order_id
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self.logger().warning(
                f"Failed to cancel the order {order.client_order_id} because it does not have an exchange order id yet"
            )
            self.logger().warning(
                "Keeping order %s tracked after cancel timeout; scheduling reconciliation instead of not-found escalation.",
                order.client_order_id,
            )
            self._schedule_unmatched_private_event_reconcile()
        except IOError as ex:
            reconciled_state = await self._reconcile_order_state_after_cancel_error(
                order=order,
                error_message=str(ex),
            )
            if reconciled_state in {OrderState.CANCELED, OrderState.FILLED, OrderState.FAILED}:
                return order.client_order_id
            if self._is_order_not_found_during_cancelation_error(cancelation_exception=ex):
                self.logger().warning(
                    "Cancel returned not-found for %s but reconciliation was non-terminal. "
                    "Keeping order tracked until explicit terminal update arrives.",
                    order.client_order_id,
                )
                self._schedule_unmatched_private_event_reconcile()
            else:
                self.logger().error(f"Failed to cancel order {order.client_order_id}", exc_info=True)
        except Exception as ex:
            if self._is_order_not_found_during_cancelation_error(cancelation_exception=ex):
                reconciled_state = await self._reconcile_order_state_after_cancel_error(
                    order=order,
                    error_message=str(ex),
                )
                if reconciled_state in {OrderState.CANCELED, OrderState.FILLED, OrderState.FAILED}:
                    return order.client_order_id
            else:
                self.logger().error(f"Failed to cancel order {order.client_order_id}", exc_info=True)
        finally:
            self._cancel_in_flight_client_order_ids.discard(order.client_order_id)
        return None

    async def _reconcile_order_state_after_cancel_error(
        self,
        order: InFlightOrder,
        error_message: str,
    ) -> Optional[OrderState]:
        """Reconcile exchange state before deciding whether to keep tracking an order after cancel errors."""
        try:
            order_update = await self._request_order_status(order)
            self._order_tracker.process_order_update(order_update)
            self.logger().debug(
                "Cancel reconciliation for %s after error '%s' -> exchange state %s",
                order.client_order_id,
                error_message,
                order_update.new_state,
            )
            return order_update.new_state
        except Exception as status_error:
            self.logger().warning(
                "Cancel reconciliation for %s failed after error '%s': %s. "
                "Order remains tracked until a later WS/REST update confirms terminal state.",
                order.client_order_id,
                error_message,
                status_error,
            )
            return None

    async def _execute_orders_cancel(self, orders: List[InFlightOrder]) -> List[OrderUpdate]:
        results = []
        for order in orders:
            cancelled_order_id = await self._execute_order_cancel(order)
            if cancelled_order_id:
                results.append(
                    OrderUpdate(
                        client_order_id=cancelled_order_id,
                        trading_pair=order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.CANCELED,
                    )
                )
        return results

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        prices = await self.get_last_traded_prices(trading_pairs=[trading_pair])
        return prices[trading_pair]

    async def _create_order_fill_updates(self, order: InFlightOrder, exchange_order_id: str, fee: TradeFeeBase) -> List[TradeUpdate]:
        _ = exchange_order_id
        _ = fee
        return await self._all_trade_updates_for_order(order)

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        return 0, Decimal("0"), Decimal("0")

    async def _get_last_trade_price(self, trading_pair: str) -> float:
        return await self._get_last_traded_price(trading_pair)

    async def _get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs = await self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)
        return pairs.get("data", [])

    async def _request_order_fills(self, order: InFlightOrder) -> List[Dict[str, Any]]:
        if order.exchange_order_id is None:
            return []
        return await self._request_order_fills_by_exchange_order_id(order)

    async def _request_order_fills_from_trades_api(self, order: InFlightOrder) -> List[Dict[str, Any]]:
        if order.exchange_order_id is None or not self._is_int_string(str(order.exchange_order_id)):
            return []

        params = {
            "account_index": self._get_account_index(),
            "limit": 100,
            "sort_by": "timestamp",
        }
        params["order_index"] = int(str(order.exchange_order_id))

        response = await self._api_get(
            path_url=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
        )

        if not response.get("success"):
            return []
        return response.get("data") or []

    async def _request_order_fills_from_fills_api(self, order: InFlightOrder) -> List[Dict[str, Any]]:
        return await self._request_order_fills_from_trades_api(order)

    async def _request_order_fills_by_exchange_order_id(self, order: InFlightOrder) -> List[Dict[str, Any]]:
        fills = await self._request_order_fills_from_trades_api(order)
        target_exchange_order_id = str(order.exchange_order_id)
        filtered_fills = []
        for fill in fills:
            fill_exchange_order_id = str(fill.get("order_id") or fill.get("orderId") or "")
            if fill_exchange_order_id == target_exchange_order_id:
                filtered_fills.append(fill)
        return filtered_fills

    async def _request_order_fills_by_client_order_id(self, order: InFlightOrder) -> List[Dict[str, Any]]:
        fills = await self._request_order_fills_from_trades_api(order)
        filtered_fills = []
        for fill in fills:
            fill_client_order_id = str(fill.get("client_order_id") or fill.get("clientOrderId") or "")
            if fill_client_order_id == order.client_order_id:
                filtered_fills.append(fill)
        return filtered_fills

    async def _request_trade_updates(self, orders: List[InFlightOrder]) -> List[TradeUpdate]:
        trade_updates: List[TradeUpdate] = []
        for order in orders:
            trade_updates.extend(await self._all_trade_updates_for_order(order))
        return trade_updates

    async def _request_order_update(self, order: InFlightOrder) -> OrderUpdate:
        return await self._request_order_status(order)

    async def _request_trade_fills(self) -> List[TradeFillOrderDetails]:
        response = await self._api_get(
            path_url=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
            params={
                "account_index": self._get_account_index(),
                "limit": 100,
                "sort_by": "timestamp",
            },
            is_auth_required=True,
            limit_id=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
        )
        fills = response.get("data") or []
        return [
            TradeFillOrderDetails(
                market=self.name,
                exchange_trade_id=str(fill.get("trade_id_str") or fill.get("history_id") or fill.get("trade_id") or fill.get("id") or fill.get("h") or ""),
                symbol=str(fill.get("symbol") or ""),
            )
            for fill in fills
        ]

    def __getattr__(self, name: str):
        if name == "_signer_client_lock":
            lock = asyncio.Lock()
            setattr(self, name, lock)
            return lock
        if name == "_cancel_in_flight_client_order_ids":
            in_flight_set: Set[str] = set()
            setattr(self, name, in_flight_set)
            return in_flight_set
        if name == "_balance_refresh_required_since":
            setattr(self, name, 0.0)
            return 0.0
        if name == "_last_ws_balance_update_ts":
            setattr(self, name, 0.0)
            return 0.0
        if name == "_api_key_public_key":
            setattr(self, name, "")
            return ""
        if name == "_startup_orphan_cleanup_done":
            setattr(self, name, False)
            return False
        if name == "_runtime_orphan_poll_counter":
            setattr(self, name, 0)
            return 0
        raise AttributeError(f"{self.__class__.__name__!s} object has no attribute {name!r}")

    def _allocate_client_order_index(self) -> int:
        last_idx = getattr(self, "_last_client_order_index", 0)
        candidate = int(time.time() * 1000) * getattr(self, "_CLIENT_ORDER_INDEX_TIME_MULTIPLIER", 140)
        if candidate <= last_idx:
            candidate = last_idx + 1
        if candidate > getattr(self, "_CLIENT_ORDER_INDEX_MAX", (1 << 48) - 1):
            candidate = getattr(self, "_CLIENT_ORDER_INDEX_MAX", (1 << 48) - 1)
        self._last_client_order_index = candidate
        return candidate

    @staticmethod
    def _response_code(response: Any) -> Optional[int]:
        if response is None:
            return None
        if isinstance(response, dict):
            code = response.get("code")
        else:
            code = getattr(response, "code", None)
        try:
            return int(code)
        except Exception:
            return None

    def _is_invalid_nonce_failure(self, error: Optional[Any] = None, response: Optional[Any] = None) -> bool:
        if self._response_code(response) == 21104:
            return True
        if error is not None and "invalid nonce" in str(error).lower():
            return True
        if response is not None and "invalid nonce" in str(response).lower():
            return True
        return False

    def _refresh_signer_client(self):
        previous_signer_client = self._lighter_signer_client
        self._lighter_signer_client = None
        try:
            return self._get_lighter_signer_client()
        except Exception:
            # Preserve previous signer client to keep local nonce flow usable.
            self._lighter_signer_client = previous_signer_client
            raise

    async def _refresh_signer_client_async(self):
        """Reset and recreate the signer client in a thread executor to avoid blocking the event loop.

        SignerClient.__init__ calls get_nonce_from_api() synchronously — a blocking HTTP call to
        the Lighter network node.  If the node is slow or temporarily unreachable, calling this
        synchronously freezes the entire asyncio event loop (and therefore the strategy) for the
        duration of the TCP timeout (potentially minutes).

        Must be called after a nonce failure so the next signing attempt uses a fresh nonce.
        """
        previous_signer_client = self._lighter_signer_client
        self._lighter_signer_client = None
        loop = asyncio.get_event_loop()
        try:
            new_client = await loop.run_in_executor(None, self._get_lighter_signer_client)
            return new_client
        except Exception:
            self._lighter_signer_client = previous_signer_client
            raise
