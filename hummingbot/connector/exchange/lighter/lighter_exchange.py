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
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterExchange(ExchangePyBase):
    web_utils = web_utils
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    BALANCE_SYNC_REQUIRED_TIMEOUT = 3.0
    _MARKET_ORDER_MAX_SLIPPAGE = Decimal("5")  # 5%
    _TRADE_HISTORY_TIME_DRIFT_BUFFER = 10.0  # seconds
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
        self._last_signed_tx_ts: float = 0.0
        self._cancel_in_flight_client_order_ids: Set[str] = set()
        initial_index = int(time.time() * 1000) * getattr(self, "_CLIENT_ORDER_INDEX_TIME_MULTIPLIER", 140)
        self._last_client_order_index: int = min(initial_index, getattr(self, "_CLIENT_ORDER_INDEX_MAX", (1 << 48) - 1) - 1_000_000)
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

    def _account_query_params(self) -> Dict[str, Any]:
        return {
            "by": "index",
            "value": str(self._get_account_index()),
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
        return '"code":5' in error_text or "failed to cancel order" in error_text

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
                if attempt < 2 and self._is_invalid_nonce_failure(error=error, response=tx_response):
                    # Nonce refresh may fail during transient DNS/network issues.
                    # Keep the existing signer client and retry instead of failing fast.
                    try:
                        signer_client = self._refresh_signer_client()
                    except Exception as refresh_error:
                        self.logger().warning(
                            f"Failed to refresh signer client after invalid nonce for {order_id}: {refresh_error}. "
                            f"Retrying cancel with existing signer client."
                        )
                    await self._sleep(0.3)
                    continue
                break

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
                    signer_client = self._refresh_signer_client()
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

        last_balance_ts = float(getattr(self, "_last_balance_update_timestamp", 0.0) or 0.0)
        if last_balance_ts >= required_since:
            return

        try:
            await asyncio.wait_for(self._update_balances(), timeout=self.BALANCE_SYNC_REQUIRED_TIMEOUT)
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

    async def _create_order(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        **kwargs,
    ):
        await self._ensure_fresh_balance_snapshot_before_order(trade_type=trade_type)
        await super()._create_order(
            trade_type=trade_type,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs,
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
                    signer_client = self._refresh_signer_client()
                    client_order_index = self._allocate_client_order_index()
                    await self._sleep(0.3)
                    continue
                break

        if error is not None:
            raise IOError(f"Lighter spot create_order signing/send failed: {error}")
        if tx_response is None or self._response_code(tx_response) != 200:
            raise IOError(f"Lighter spot create_order failed: {tx_response}")

        return str(client_order_index), self.current_timestamp

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
        # Keep status polling fast whenever there are active orders so manual
        # exchange-side cancellations are reflected in status --live quickly.
        if len(self.in_flight_orders) > 0:
            return self.SHORT_POLL_INTERVAL
        return super()._get_poll_interval(timestamp)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    continue

                account_data, trades, orders = self._extract_private_stream_payloads(event_message=event_message)
                has_assets_payload = self._account_payload_has_assets(account_data)

                if isinstance(account_data, dict):
                    self._process_balance_message_from_account(account_data)

                unmatched_private_event = False
                for trade in trades:
                    trade_update = self._trade_update_from_raw_message(trade)
                    if trade_update is not None:
                        self._order_tracker.process_trade_update(trade_update)
                    else:
                        unmatched_private_event = True

                for order_data in orders:
                    order_update = self._order_update_from_raw_message(order_data)
                    if order_update is not None:
                        self._order_tracker.process_order_update(order_update)
                        self._schedule_balance_sync_for_terminal_update(order_update=order_update)
                    else:
                        unmatched_private_event = True

                if unmatched_private_event:
                    self._schedule_unmatched_private_event_reconcile(min_interval_seconds=1.0)

                # Some private event payloads include order/trade changes but omit account assets.
                # Trigger a throttled balance refresh so locked/available values in status --live
                # reflect open/canceled orders without waiting for the next periodic poll.
                if (
                    (not has_assets_payload)
                    and (len(trades) > 0 or len(orders) > 0)
                    and (self._current_timestamp_safely() - getattr(self, "_last_private_stream_balance_sync_ts", 0.0)) >= 1.0
                ):
                    self._last_private_stream_balance_sync_ts = self._current_timestamp_safely()
                    safe_ensure_future(self._safe_update_balances_from_private_stream())
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _current_timestamp_safely(self) -> float:
        try:
            return self.current_timestamp
        except Exception:
            return time.time()

    async def _safe_update_balances_from_private_stream(self):
        try:
            await self._update_balances()
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
            await self._update_order_status()
        except asyncio.CancelledError:
            raise
        except Exception as reconcile_error:
            self.logger().debug(
                "Unmatched private-event reconcile failed: %s",
                reconcile_error,
            )

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
        if order_update.new_state in {OrderState.CANCELED, OrderState.FILLED, OrderState.FAILED}:
            _ = tracked_order
            self._balance_refresh_required_since = max(
                self._balance_refresh_required_since,
                self._current_timestamp_safely(),
            )
            self._schedule_fast_balance_sync(min_interval_seconds=0.2)

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
        } and isinstance(payload, dict):
            account_data = payload
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

        if isinstance(event_message.get("trades"), list):
            trades.extend([trade for trade in event_message.get("trades", []) if isinstance(trade, dict)])
        if isinstance(event_message.get("trade"), dict):
            trades.append(event_message.get("trade"))
        if isinstance(payload, dict) and isinstance(payload.get("trades"), list):
            trades.extend([trade for trade in payload.get("trades", []) if isinstance(trade, dict)])
        if isinstance(payload, dict) and isinstance(payload.get("trade"), dict):
            trades.append(payload.get("trade"))

        if event_type_name == CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL:
            if isinstance(payload, list):
                trades.extend([trade for trade in payload if isinstance(trade, dict)])
            elif isinstance(payload, dict) and "trades" not in payload:
                trades.append(payload)

        if isinstance(event_message.get("orders"), list):
            orders.extend([order for order in event_message.get("orders", []) if isinstance(order, dict)])
        if isinstance(event_message.get("order"), dict):
            orders.append(event_message.get("order"))
        if isinstance(payload, dict) and isinstance(payload.get("orders"), list):
            orders.extend([order for order in payload.get("orders", []) if isinstance(order, dict)])
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

        return account_data, trades, orders

    def _state_from_raw_order_status(self, raw_status: str) -> OrderState:
        return self._ORDER_STATE.get(raw_status.lower(), OrderState.OPEN)

    def _process_balance_message_from_account(self, account_data: Dict[str, Any]):
        assets_payload = account_data.get("assets", [])
        if isinstance(assets_payload, dict):
            assets_iterable = [asset for asset in assets_payload.values() if isinstance(asset, dict)]
        else:
            assets_iterable = assets_payload

        for asset_entry in assets_iterable:
            asset_symbol = asset_entry.get("symbol")
            if asset_symbol is None:
                continue

            total_balance = Decimal(str(asset_entry.get("balance") or "0"))
            locked_balance = Decimal(str(asset_entry.get("locked_balance") or "0"))
            available_balance = total_balance - locked_balance

            self._account_balances[asset_symbol] = total_balance
            self._account_available_balances[asset_symbol] = available_balance

        # For the spot connector, available balance is derived from per-asset wallet balances
        # (`balance - locked_balance`) rather than the account-level `available_balance` field.
        # This ensures allocated percentage calculations reflect the true per-asset balance.

    def _order_update_from_raw_message(self, order_data: Dict[str, Any]) -> Optional[OrderUpdate]:
        # exchange_order_id == str(client_order_index) in this connector.
        # Prefer client_order_id / client_order_index so order lookup succeeds.
        exchange_order_id = str(
            order_data.get("client_order_id")
            or order_data.get("client_order_index")
            or order_data.get("order_id")
            or order_data.get("orderId")
            or order_data.get("order_index")
            or order_data.get("orderIndex")
            or ""
        )
        client_order_id = str(order_data.get("client_order_id") or order_data.get("clientOrderId") or "")
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if tracked_order is None and exchange_order_id:
            tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
        if tracked_order is None:
            return None

        raw_status = str(order_data.get("order_status") or order_data.get("status") or "open")
        update_ts = float(order_data.get("updated_at") or order_data.get("created_at") or self.current_timestamp)
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
        # Fall back to legacy order_id fields used by older WS formats.
        tracked_order = None
        for cid_field in ("ask_client_id", "bid_client_id", "ask_clientId", "bid_clientId"):
            candidate_id = str(trade_data.get(cid_field) or "")
            if candidate_id:
                tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(candidate_id)
                if tracked_order is not None:
                    break

        if tracked_order is None:
            # Legacy / compact WS format fallback
            exchange_order_id = str(trade_data.get("order_id") or trade_data.get("orderId") or "")
            client_order_id = str(trade_data.get("client_order_id") or trade_data.get("clientOrderId") or "")
            tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
            if tracked_order is None and exchange_order_id:
                tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        if tracked_order is None:
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

        _fee_schema = self.trade_fee_schema()
        _fee_percent = (
            _fee_schema.taker_percent_fee_decimal if is_taker else _fee_schema.maker_percent_fee_decimal
        )
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=_fee_schema,
            trade_type=tracked_order.trade_type,
            percent=_fee_percent,
            percent_token=tracked_order.quote_asset,
            flat_fees=[],
        )

        return TradeUpdate(
            trade_id=str(trade_data.get("trade_id") or trade_data.get("history_id") or trade_data.get("id") or trade_data.get("h") or ""),
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
        await self._update_balances()
        await super().start_network()

    async def _update_balances(self):
        response = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_INFO_PATH_URL,
            params=self._account_query_params(),
            is_auth_required=True,
            return_err=True,
            limit_id=CONSTANTS.GET_ACCOUNT_INFO_PATH_URL,
        )

        if not self._is_ok_response(response):
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
        client_order_idx = int(str(order.exchange_order_id)) if self._is_int_string(str(order.exchange_order_id)) else None

        # If we cannot map the order to a valid client_order_index, do not scan global
        # account trades. Otherwise unrelated market fills can be attributed to this order.
        if client_order_idx is None:
            self._order_history_last_poll_timestamp[str(order.exchange_order_id)] = current_time
            return trade_updates

        # exchange_order_id == str(client_order_index). The /trades filter 'order_index' refers to
        # the exchange-assigned sequential order_index, which differs from client_order_index.
        # Filter client-side using ask_client_id / bid_client_id instead.
        last_poll_ts = self._order_history_last_poll_timestamp.get(order.exchange_order_id, order.creation_timestamp)
        from_ts = max(0, int(last_poll_ts - self._TRADE_HISTORY_TIME_DRIFT_BUFFER))

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
                # Match our order via ask_client_id / bid_client_id (= client_order_index).
                side_client_id = trade_message.get("ask_client_id" if is_ask else "bid_client_id")
                if side_client_id is not None:
                    if int(side_client_id) != client_order_idx:
                        continue
                else:
                    # Fallback for payload variants that only include order_id/order_index.
                    raw_order_idx = trade_message.get("order_id") or trade_message.get("orderId") or trade_message.get("order_index")
                    if raw_order_idx is None or not self._is_int_string(str(raw_order_idx)) or int(str(raw_order_idx)) != client_order_idx:
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
                        trade_id=str(trade_message.get("trade_id") or trade_message.get("history_id") or trade_message.get("id") or ""),
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

            # Pagination: API returns next_cursor (null when no more pages).
            if response.get("next_cursor"):
                params["cursor"] = response["next_cursor"]
            else:
                break

        self._order_history_last_poll_timestamp[order.exchange_order_id] = current_time
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
            )
            if not inactive_response.get("success"):
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
        if is_auth_required and self.rest_api_key:
            headers["X-Api-Key"] = self.rest_api_key

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

    async def _update_order_fills_from_trades(self):
        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if long_interval_current_tick > long_interval_last_tick or (
            self.in_flight_orders and small_interval_current_tick > small_interval_last_tick
        ):
            # Build lookup: client_order_index (str) -> tracked order.
            order_by_exchange_id_map = {order.exchange_order_id: order for order in self._order_tracker.all_fillable_orders.values()}
            # Also build per-direction maps for ask/bid_client_id matching.
            ask_order_map = {eid: o for eid, o in order_by_exchange_id_map.items() if o.trade_type == TradeType.SELL}
            bid_order_map = {eid: o for eid, o in order_by_exchange_id_map.items() if o.trade_type == TradeType.BUY}

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
                limit_id=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
            )
            # API returns 'trades' key; fall back to 'data' for test mocks.
            for trade in response.get("trades") or response.get("data") or []:
                # Match via ask_client_id / bid_client_id (= client_order_index = exchange_order_id).
                ask_cid = str(trade.get("ask_client_id") or "")
                bid_cid = str(trade.get("bid_client_id") or "")
                tracked_order = ask_order_map.get(ask_cid) or bid_order_map.get(bid_cid)
                if tracked_order is None:
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

                _fee_schema_at = self.trade_fee_schema()
                _fee_percent_at = (
                    _fee_schema_at.taker_percent_fee_decimal if is_taker else _fee_schema_at.maker_percent_fee_decimal
                )
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
                    trade_id=str(trade.get("trade_id") or trade.get("id") or ""),
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

    async def _update_order_status(self):
        await self._update_order_fills_from_trades()
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
                and order_update.new_state == OrderState.FILLED
                and not tracked_order.is_done
                and tracked_order.executed_amount_base < tracked_order.amount
            ):
                # Rescue fill fetch: the bulk trade-history poll ran before the fill appeared on
                # the exchange REST API.  Fetch fills specifically for this order now so the
                # tracker has the fill data before wait_until_completely_filled() times out.
                try:
                    fill_updates = await self._all_trade_updates_for_order(tracked_order)
                    for fill_update in fill_updates:
                        self._order_tracker.process_trade_update(fill_update)
                    if fill_updates:
                        self.logger().info(
                            "[_update_orders] Rescue fill fetch found %d fill(s) for %s",
                            len(fill_updates),
                            tracked_order.client_order_id,
                        )
                except Exception as ex:
                    self.logger().warning(
                        "[_update_orders] Rescue fill fetch failed for %s: %s",
                        tracked_order.client_order_id,
                        ex,
                    )
            self._order_tracker.process_order_update(order_update)
            if isinstance(order_update, OrderUpdate):
                self._schedule_balance_sync_for_terminal_update(order_update=order_update, tracked_order=tracked_order)

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
            self.logger().info(
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
                exchange_trade_id=str(fill.get("history_id") or fill.get("trade_id") or fill.get("id") or fill.get("h") or ""),
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
        if name == "_api_key_public_key":
            setattr(self, name, "")
            return ""
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
