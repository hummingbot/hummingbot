import asyncio
import hashlib
import json
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Callable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS, lighter_web_utils as web_utils
from hummingbot.connector.exchange.lighter.lighter_api_order_book_data_source import LighterAPIOrderBookDataSource
from hummingbot.connector.exchange.lighter.lighter_api_user_stream_data_source import LighterAPIUserStreamDataSource
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterExchange(ExchangePyBase):
    web_utils = web_utils
    _ORDER_STATE = {
        "in-progress": OrderState.OPEN,
        "open": OrderState.OPEN,
        "pending": OrderState.PENDING_CREATE,
        "partially_filled": OrderState.PARTIALLY_FILLED,
        "partial_fill": OrderState.PARTIALLY_FILLED,
        "filled": OrderState.FILLED,
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
        self._last_signed_tx_ts: float = 0.0
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
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
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

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        if tracked_order.exchange_order_id is None:
            return False

        market_id, _, _, _ = await self._get_market_spec(tracked_order.trading_pair)

        async with self._signer_client_lock:
            signer_client = self._refresh_signer_client()
            tx_response = None
            error = None
            for attempt in range(5):
                # Re-check after awaits in case order tracking clears the exchange id concurrently.
                exchange_order_id = tracked_order.exchange_order_id
                if exchange_order_id is None:
                    return False

                _, tx_response, error = await signer_client.cancel_order(
                    market_index=market_id,
                    order_index=int(exchange_order_id),
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
            signer_client = self._refresh_signer_client()
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
        # Validate sufficient balance before placing order
        if trade_type == TradeType.BUY:
            quote_asset = trading_pair.split("-")[-1]
            required_balance = amount * price
            available_balances = getattr(self, "_account_available_balances", None)
            if available_balances is not None:
                available_balance = available_balances.get(quote_asset, Decimal("0"))
                if available_balance < required_balance:
                    raise IOError(
                        f"Insufficient {quote_asset} balance for {amount} {trading_pair.split('-')[0]} buy order. "
                        f"Required: {required_balance}, Available: {available_balance}"
                    )

        if order_type not in self.supported_order_types():
            raise ValueError(f"Order type {order_type} is not supported by {self.name}.")

        market_id, size_decimals, price_decimals, _ = await self._get_market_spec(trading_pair)

        base_amount_scaled = int((amount * Decimal(f"1e{size_decimals}")).to_integral_value())
        price_scaled = int((price * Decimal(f"1e{price_decimals}")).to_integral_value())

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
            signer_client = self._refresh_signer_client()
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

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    continue

                account_data = event_message.get("account") or event_message.get("data")
                if isinstance(account_data, dict):
                    self._process_balance_message_from_account(account_data)

                for trade in event_message.get("trades", []):
                    trade_update = self._trade_update_from_raw_message(trade)
                    if trade_update is not None:
                        self._order_tracker.process_trade_update(trade_update)

                for order_data in event_message.get("orders", []):
                    order_update = self._order_update_from_raw_message(order_data)
                    if order_update is not None:
                        self._order_tracker.process_order_update(order_update)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _state_from_raw_order_status(self, raw_status: str) -> OrderState:
        return self._ORDER_STATE.get(raw_status.lower(), OrderState.OPEN)

    def _process_balance_message_from_account(self, account_data: Dict[str, Any]):
        for asset_entry in account_data.get("assets", []):
            asset_symbol = asset_entry.get("symbol")
            if asset_symbol is None:
                continue

            total_balance = Decimal(str(asset_entry.get("balance") or "0"))
            locked_balance = Decimal(str(asset_entry.get("locked_balance") or "0"))
            available_balance = total_balance - locked_balance

            self._account_balances[asset_symbol] = total_balance
            self._account_available_balances[asset_symbol] = available_balance

        # Same override as _update_balances: use top-level available_balance for USDC,
        # and total_balance for non-USDC assets to avoid cross-margin lock inflation.
        ws_top_level = Decimal(str(account_data.get("available_balance") or "0"))
        if ws_top_level > Decimal("0"):
            ws_usdc_avail = self._account_available_balances.get("USDC", Decimal("0"))
            if ws_top_level > ws_usdc_avail:
                self._account_available_balances["USDC"] = ws_top_level
        for _ws_asset in list(self._account_available_balances.keys()):
            if _ws_asset == "USDC":
                continue
            _ws_total = self._account_balances.get(_ws_asset, Decimal("0"))
            if _ws_total > self._account_available_balances[_ws_asset]:
                self._account_available_balances[_ws_asset] = _ws_total

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

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=tracked_order.trade_type,
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

        # Lighter unified accounts: locked_balance includes cross-margin commitments, not just
        # active order locks. For USDC, use the top-level available_balance when it is higher.
        # For non-USDC assets (ETH etc.), use total_balance as available since the exchange
        # enforces actual collateral requirements at order placement time.
        top_level_available = Decimal(str(account_data.get("available_balance") or "0"))
        if top_level_available > Decimal("0"):
            usdc_per_asset_available = self._account_available_balances.get("USDC", Decimal("0"))
            if top_level_available > usdc_per_asset_available:
                self._account_available_balances["USDC"] = top_level_available
        for _asset_symbol in list(self._account_available_balances.keys()):
            if _asset_symbol == "USDC":
                continue
            _total = self._account_balances.get(_asset_symbol, Decimal("0"))
            if _total > self._account_available_balances[_asset_symbol]:
                self._account_available_balances[_asset_symbol] = _total

        for local_asset in list(self._account_balances.keys()):
            if local_asset not in remote_asset_names:
                self._account_balances.pop(local_asset, None)
                self._account_available_balances.pop(local_asset, None)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        current_time = self.current_timestamp

        # exchange_order_id == str(client_order_index). The /trades filter 'order_index' refers to
        # the exchange-assigned sequential order_index, which differs from client_order_index.
        # Filter client-side using ask_client_id / bid_client_id instead.
        params = {
            "account_index": self._get_account_index(),
            "limit": 100,
            "sort_by": "timestamp",
        }

        is_ask = (order.trade_type == TradeType.SELL)
        client_order_idx = int(str(order.exchange_order_id)) if self._is_int_string(str(order.exchange_order_id)) else None

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
                if client_order_idx is not None:
                    side_client_id = trade_message.get("ask_client_id" if is_ask else "bid_client_id")
                    if side_client_id is None or int(side_client_id) != client_order_idx:
                        continue

                # 'timestamp' is in seconds per the API spec.
                fill_timestamp = float(trade_message.get("timestamp") or 0)
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
                    is_taker = False

                # Fee tick-to-USD conversion requires market config; omit flat fee for now.
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=order.quote_asset,
                    flat_fees=[],
                )

                trade_updates.append(
                    TradeUpdate(
                        trade_id=str(trade_message.get("trade_id") or trade_message.get("id") or ""),
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

        response = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_HISTORY_PATH_URL,
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.GET_ORDER_HISTORY_PATH_URL,
        )

        if not response.get("success"):
            raise IOError(f"Failed to fetch order status for {tracked_order.client_order_id}: {response}")

        rows = response.get("orders") or response.get("data") or []
        target_exchange_order_id = str(tracked_order.exchange_order_id or "")
        # exchange_order_id == str(client_order_index). Match via client_order_id (string of
        # client_order_index) or client_order_index (int). Do NOT compare against order_id which
        # is the string of the exchange-assigned sequential order_index.
        has_client_id_field = any(("client_order_id" in item) or ("client_order_index" in item) for item in rows)
        if target_exchange_order_id and has_client_id_field:
            rows = [
                item for item in rows
                if str(item.get("client_order_id") or item.get("client_order_index") or "") == target_exchange_order_id
            ]

        if len(rows) == 0:
            active_response = await self._api_get(
                path_url=CONSTANTS.GET_ACTIVE_ORDERS_PATH_URL,
                params=params,
                is_auth_required=True,
                limit_id=CONSTANTS.GET_ACTIVE_ORDERS_PATH_URL,
                return_err=True,
            )
            active_rows = active_response.get("orders") or active_response.get("data") or []
            if target_exchange_order_id:
                active_rows = [
                    item for item in active_rows
                    if str(item.get("client_order_id") or item.get("client_order_index") or "") == target_exchange_order_id
                    or str(item.get("order_id") or item.get("order_index") or "") == target_exchange_order_id
                ]

            # If not found in inactive and not found in active, treat as closed/canceled.
            new_state = OrderState.OPEN if len(active_rows) > 0 else OrderState.CANCELED
            return OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
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
        await asyncio.gather(
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

            response = await self._api_get(path_url=CONSTANTS.GET_TRADE_HISTORY_PATH_URL, is_auth_required=True, limit_id=CONSTANTS.GET_TRADE_HISTORY_PATH_URL)
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

                fill_timestamp = float(trade.get("timestamp") or self.current_timestamp)
                if fill_timestamp > 1e12:
                    fill_timestamp *= 1e-3

                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=tracked_order.trade_type,
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
        await self._update_orders_fills(orders=list(self.in_flight_orders.values()))
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
            self._order_tracker.process_order_update(order_update)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise

    def _create_trade_fill_updates(self, inflight_order: InFlightOrder, fills_data: List[Dict[str, Any]]) -> List[TradeUpdate]:
        trade_updates: List[TradeUpdate] = []
        for fill_data in fills_data:
            trade_update = TradeUpdate(
                trade_id=str(fill_data.get("trade_id") or fill_data.get("id") or fill_data.get("h")),
                client_order_id=inflight_order.client_order_id,
                exchange_order_id=inflight_order.exchange_order_id,
                trading_pair=inflight_order.trading_pair,
                fill_timestamp=float(fill_data.get("timestamp") or fill_data.get("t") or self.current_timestamp),
                fill_price=Decimal(str(fill_data.get("price") or fill_data.get("p") or "0")),
                fill_base_amount=Decimal(str(fill_data.get("amount") or fill_data.get("a") or "0")),
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

    async def _execute_order_cancel(self, order: InFlightOrder) -> str:
        cancelled = await self._place_cancel(order_id=order.client_order_id, tracked_order=order)
        if cancelled:
            return order.client_order_id
        return ""

    async def _execute_orders_cancel(self, orders: List[InFlightOrder]) -> List[OrderUpdate]:
        results = []
        for order in orders:
            cancelled_order_id = await self._execute_order_cancel(order)
            if cancelled_order_id != "":
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
        params = {
            "account_index": self._get_account_index(),
            "limit": 100,
            "sort_by": "timestamp",
        }
        if order.exchange_order_id is not None and self._is_int_string(str(order.exchange_order_id)):
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
        self._lighter_signer_client = None
        return self._get_lighter_signer_client()
