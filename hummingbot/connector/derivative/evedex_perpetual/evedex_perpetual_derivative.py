import asyncio
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_api_order_book_data_source import (
    EvedexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_user_stream_data_source import (
    EvedexPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_utils import (
    DEFAULT_FEES,
    order_status_to_hummingbot,
)
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class EvedexPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Hummingbot connector for EVEDEX perpetual futures exchange.

    EVEDEX is a derivatives exchange using:
    - EIP-712 typed data signing for order authentication
    - SIWE (Sign-In with Ethereum) + JWT for REST authentication
    - Centrifuge WebSocket protocol for market and user data streams
    - Single REST API domain: trading-api.evedex.com
    - Auth domain: auth-api.evedex.com
    """

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        evedex_private_key: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._private_key = evedex_private_key
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []

        # Instrument info cache
        self._instrument_info: Dict[str, Dict[str, Any]] = {}

        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[EvedexPerpetualAuth]:
        return self._auth

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> Optional[int]:
        return None

    @property
    def client_order_id_prefix(self) -> str:
        return "HBOT-"

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return "USD"

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return "USD"

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
            domain=self._domain,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return EvedexPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return EvedexPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_auth(self) -> EvedexPerpetualAuth:
        return EvedexPerpetualAuth(
            private_key=self._private_key,
            testnet=(self._domain == CONSTANTS.TESTNET_DOMAIN),
        )

    async def _make_network_check_request(self):
        """Ping instruments endpoint to verify connectivity."""
        import aiohttp
        base_url = web_utils.get_trade_base_url(self._domain)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}{CONSTANTS.INSTRUMENTS_URL}",
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise ConnectionError(f"Network check failed: HTTP {resp.status}")

    async def _make_trading_rules_request(self) -> Any:
        """Fetch all active instruments from EVEDEX."""
        import aiohttp
        base_url = web_utils.get_trade_base_url(self._domain)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}{CONSTANTS.INSTRUMENTS_URL}",
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                # Response is a list of instruments
                if isinstance(data, list):
                    return data
                return data.get("instruments", data.get("data", []))

    async def _make_trading_pairs_request(self) -> Any:
        return await self._make_trading_rules_request()

    def _build_siwe_message(self, address: str, nonce: str, chain_id: int) -> str:
        """Build a SIWE (Sign-In with Ethereum) message string."""
        issued_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return (
            f"evedex.com wants you to sign in with your Ethereum account:\n"
            f"{address}\n\n"
            f"Sign in to evedex.com\n\n"
            f"URI: https://evedex.com\n"
            f"Version: 1\n"
            f"Chain ID: {chain_id}\n"
            f"Nonce: {nonce}\n"
            f"Issued At: {issued_at}"
        )

    async def _authenticate(self):
        """SIWE login: get nonce → sign message → post to auth endpoint → store JWT."""
        import aiohttp
        from eth_account.messages import encode_defunct

        if self._auth.is_authenticated():
            return

        auth_url = web_utils.get_auth_base_url(self._domain)
        chain_id = web_utils.get_chain_id(self._domain)
        address = self._auth.address

        async with aiohttp.ClientSession() as session:
            # Step 1: Get nonce
            try:
                async with session.get(
                    f"{auth_url}{CONSTANTS.AUTH_NONCE_URL}",
                    params={"walletAddress": address},
                    headers={"Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    nonce_data = await resp.json()
                    nonce = nonce_data.get("nonce", nonce_data.get("data", {}).get("nonce", ""))
                    if not nonce:
                        self.logger().warning(f"EVEDEX: failed to get nonce: {nonce_data}")
                        return
            except Exception as e:
                self.logger().warning(f"EVEDEX nonce request failed: {e}")
                return

            # Step 2: Build and sign SIWE message
            message = self._build_siwe_message(address, nonce, chain_id)
            msg_obj = encode_defunct(text=message)
            signed = self._auth._account.sign_message(msg_obj)
            signature = signed.signature.hex()

            # Step 3: Submit SIWE sign-in
            payload = {
                "wallet": address,
                "message": message,
                "signature": signature,
                "nonce": nonce,
            }
            try:
                async with session.post(
                    f"{auth_url}{CONSTANTS.AUTH_SIGNIN_URL}",
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token = data.get("token", data.get("data", {}).get("token", ""))
                        user = data.get("user", data.get("data", {}).get("user", {}))
                        user_id = user.get("id", user.get("userId", address))
                        if token:
                            self._auth.set_jwt_token(token, str(user_id))
                            self.logger().info("EVEDEX authentication successful")
                        else:
                            self.logger().warning(f"EVEDEX auth: no token in response: {data}")
                    else:
                        body = await resp.text()
                        self.logger().warning(f"EVEDEX authentication failed: {resp.status} {body}")
            except Exception as e:
                self.logger().warning(f"EVEDEX sign-in request failed: {e}")

    async def _ensure_authenticated(self):
        """Re-authenticate if JWT is expired or not set."""
        if not self._auth.is_authenticated():
            await self._authenticate()

    async def _update_trading_rules(self):
        """Fetch and cache instrument information, build TradingRule objects."""
        instruments = await self._make_trading_rules_request()

        trading_rules_list = await self._format_trading_rules(instruments)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        # Cache instrument info by instrument_id
        for instr in instruments:
            instrument_id = instr.get("id", "")
            if instrument_id:
                self._instrument_info[instrument_id] = instr

    async def _initialize_trading_pair_symbol_map(self):
        """Build the trading pair <-> exchange symbol bidict."""
        instruments = await self._make_trading_pairs_request()
        mapping = bidict()
        for instr in instruments:
            instrument_id = instr.get("id", "")
            if instrument_id:
                trading_pair = web_utils.instrument_to_trading_pair(instrument_id)
                mapping[instrument_id] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, raw_instruments: List[Dict[str, Any]]) -> List[TradingRule]:
        """Convert raw instrument data to TradingRule objects."""
        result = []
        for instr in raw_instruments:
            instrument_id = instr.get("id", "")
            if not instrument_id:
                continue
            # Only active instruments
            if instr.get("marketState") not in ("OPEN", None):
                continue

            trading_pair = web_utils.instrument_to_trading_pair(instrument_id)

            min_qty = Decimal(str(instr.get("minQuantity", "0.001")))
            qty_increment = Decimal(str(instr.get("quantityIncrement", "0.001")))
            price_increment = Decimal(str(instr.get("priceIncrement", "0.1")))
            min_notional = Decimal(str(instr.get("minVolume", str(CONSTANTS.MIN_NOTIONAL_SIZE))))

            result.append(
                TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_qty,
                    min_price_increment=price_increment,
                    min_base_amount_increment=qty_increment,
                    min_notional_size=min_notional,
                    buy_order_collateral_token="USD",
                    sell_order_collateral_token="USD",
                )
            )
        return result

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:
        """Submit an order to EVEDEX via EIP-712 signed REST call."""
        await self._ensure_authenticated()

        import aiohttp
        instrument = web_utils.trading_pair_to_instrument(trading_pair)
        side = "buy" if trade_type == TradeType.BUY else "sell"
        instr_info = self._instrument_info.get(instrument, {})
        leverage = int(instr_info.get("maxLeverage", 10))
        leverage = min(leverage, 10)  # Default to 10x or max allowed

        trade_url = web_utils.get_trade_base_url(self._domain)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self._auth.get_auth_headers(),
        }

        if order_type == OrderType.MARKET:
            # Market order uses cashQuantity (USD value)
            cash_qty = float(amount) * float(price) if float(price) > 0 else float(amount)
            payload = self._auth.sign_market_order(
                order_id=order_id,
                instrument=instrument,
                side=side,
                leverage=leverage,
                cash_quantity=cash_qty,
                time_in_force="IOC",
            )
            url = f"{trade_url}{CONSTANTS.CREATE_MARKET_ORDER_URL}"
        else:
            # Limit order uses quantity + limitPrice
            payload = self._auth.sign_limit_order(
                order_id=order_id,
                instrument=instrument,
                side=side,
                leverage=leverage,
                quantity=float(amount),
                limit_price=float(price),
            )
            url = f"{trade_url}{CONSTANTS.CREATE_LIMIT_ORDER_URL}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if resp.status not in (200, 201):
                    error_msg = data.get("message", data.get("error", str(data)))
                    raise IOError(f"EVEDEX order placement failed [{resp.status}]: {error_msg}")

                # Response may be the order object directly or wrapped
                order_data = data.get("data", data)
                exchange_order_id = str(order_data.get("id", order_id))
                return exchange_order_id, time.time()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """Cancel an order by exchange order ID (DELETE request)."""
        await self._ensure_authenticated()

        import aiohttp
        trade_url = web_utils.get_trade_base_url(self._domain)
        exchange_order_id = tracked_order.exchange_order_id or order_id
        url = f"{trade_url}/api/order/{exchange_order_id}"

        headers = {
            "Accept": "application/json",
            **self._auth.get_auth_headers(),
        }

        async with aiohttp.ClientSession() as session:
            async with session.delete(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status not in (200, 204):
                    try:
                        data = await resp.json()
                        error_msg = data.get("message", data.get("error", str(data)))
                    except Exception:
                        error_msg = await resp.text()
                    if CONSTANTS.ORDER_NOT_EXIST_MESSAGE in error_msg.lower():
                        await self._order_tracker.process_order_not_found(order_id)
                    raise IOError(f"EVEDEX cancel failed [{resp.status}]: {error_msg}")
                return True

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """Fetch current status of an order via GET /api/order/{id}."""
        await self._ensure_authenticated()

        import aiohttp
        trade_url = web_utils.get_trade_base_url(self._domain)
        exchange_order_id = tracked_order.exchange_order_id or tracked_order.client_order_id
        url = f"{trade_url}/api/order/{exchange_order_id}"

        headers = {
            "Accept": "application/json",
            **self._auth.get_auth_headers(),
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise IOError(f"Order status request failed [{resp.status}]: {body}")

                data = await resp.json()
                order_data = data.get("data", data)
                status_str = order_data.get("status", "ACTIVE")
                new_state = CONSTANTS.ORDER_STATE.get(status_str.upper(), OrderState.OPEN)

                return OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=time.time(),
                    new_state=new_state,
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=exchange_order_id,
                )

    async def _update_order_status(self):
        """Poll status of all in-flight orders."""
        tracked_orders = list(self.in_flight_orders.values())
        for order in tracked_orders:
            if order.exchange_order_id:
                try:
                    order_update = await self._request_order_status(order)
                    self._order_tracker.process_order_update(order_update)
                except Exception as e:
                    self.logger().warning(f"Order status update failed for {order.client_order_id}: {e}")

    async def _update_lost_orders_status(self):
        pass  # Handled via _update_order_status

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """Fetch trade fills for an order (not available as separate endpoint — handled via WS)."""
        return []

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        """Fetch current mark/last prices for all instruments."""
        import aiohttp
        base_url = web_utils.get_trade_base_url(self._domain)
        result = []

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{base_url}{CONSTANTS.INSTRUMENTS_URL}",
                    headers={"Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    instruments = await resp.json()
                    if isinstance(instruments, list):
                        for instr in instruments:
                            instrument_id = instr.get("id", "")
                            price = instr.get("lastPrice") or instr.get("markPrice") or "0"
                            result.append({"symbol": instrument_id, "price": str(price)})
            except Exception:
                pass
        return result

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """Return last traded price for a single trading pair."""
        import aiohttp
        base_url = web_utils.get_trade_base_url(self._domain)
        instrument = web_utils.trading_pair_to_instrument(trading_pair)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}{CONSTANTS.INSTRUMENTS_URL}",
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                instruments = await resp.json()
                for instr in (instruments if isinstance(instruments, list) else []):
                    if instr.get("id", "").lower() == instrument.lower():
                        price = instr.get("lastPrice") or instr.get("markPrice") or 0
                        return float(price)
        return 0.0

    async def _update_trading_fees(self):
        """EVEDEX uses fixed fee schedule — no dynamic fetch needed."""
        pass

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
        is_maker = is_maker or (order_type == OrderType.LIMIT)
        return DeductedFromReturnsTradeFee(
            percent=DEFAULT_FEES.maker_percent_fee_decimal if is_maker
            else DEFAULT_FEES.taker_percent_fee_decimal
        )

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(cancelation_exception).lower()

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await asyncio.wait_for(self._user_stream_tracker.user_stream.get(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def _user_stream_event_listener(self):
        """Process user order/position/fill events from Centrifuge WebSocket."""
        async for event_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User stream event error: {e}", exc_info=True)

    async def _process_user_stream_event(self, event: Dict[str, Any]):
        """Route Centrifuge push events to appropriate handlers."""
        # Centrifuge push format: {"push": {"channel": "...", "pub": {"data": {...}}}}
        push = event.get("push", {})
        if not push:
            return

        channel = push.get("channel", "")
        pub = push.get("pub", {})
        data = pub.get("data", {})

        if not channel or not data:
            return

        # Strip prefix (e.g. "futures-perp:order-123" → "order-123")
        prefix = web_utils.get_ws_prefix(self._domain)
        channel_name = channel.replace(f"{prefix}:", "")

        user_id = self._auth.user_exchange_id or ""

        if channel_name.startswith("order-"):
            self._process_order_message(data)

        elif channel_name.startswith("orderFills-"):
            await self._process_fill_message(data)

        elif channel_name.startswith("position-"):
            await self._process_position_message(data)

        elif channel_name.startswith("funding-"):
            # Funding balance updates — not used for connector state
            pass

        elif channel_name.startswith("user-"):
            # General account updates
            pass

    def _process_order_message(self, order_data: Dict[str, Any]):
        """Handle an order update event from WebSocket."""
        exchange_order_id = str(order_data.get("id", ""))
        client_order_id = order_data.get("clientOrderId", "")

        # Try to find by exchange order ID if no client order ID
        if not client_order_id:
            tracked_order = self._order_tracker.fetch_order(exchange_order_id=exchange_order_id)
            if tracked_order:
                client_order_id = tracked_order.client_order_id

        status_str = order_data.get("status", "ACTIVE")
        new_state = CONSTANTS.ORDER_STATE.get(status_str.upper(), OrderState.OPEN)

        instrument_id = order_data.get("instrument", "")
        trading_pair = web_utils.instrument_to_trading_pair(instrument_id) if instrument_id else ""

        # Try to get trading pair from tracked order if not in event
        if not trading_pair and client_order_id:
            tracked = self._order_tracker.fetch_order(client_order_id=client_order_id)
            if tracked:
                trading_pair = tracked.trading_pair

        if trading_pair:
            order_update = OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=time.time(),
                new_state=new_state,
                client_order_id=client_order_id,
                exchange_order_id=exchange_order_id,
            )
            self._order_tracker.process_order_update(order_update)

    async def _process_fill_message(self, fill_data: Dict[str, Any]):
        """Handle a fill (trade execution) event from WebSocket."""
        exchange_order_id = str(fill_data.get("orderId", fill_data.get("order_id", "")))
        tracked_order = self._order_tracker.fetch_order(exchange_order_id=exchange_order_id)
        if not tracked_order:
            return

        fill_price = Decimal(str(fill_data.get("fillPrice", fill_data.get("price", "0"))))
        fill_qty = Decimal(str(fill_data.get("fillQuantity", fill_data.get("quantity", "0"))))
        fee_amount = Decimal(str(fill_data.get("fee", "0")))
        execution_id = str(fill_data.get("executionId", fill_data.get("id", str(time.time()))))

        trade_update = TradeUpdate(
            trade_id=execution_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fee=TradeFeeBase.new_perpetual_fee(
                fee_schema=DEFAULT_FEES,
                position_action=tracked_order.position,
                percent_token="USD",
                flat_fees=[TokenAmount(token="USD", amount=fee_amount)],
            ),
            fill_base_amount=fill_qty,
            fill_quote_amount=fill_qty * fill_price,
            fill_price=fill_price,
            fill_timestamp=time.time(),
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _process_position_message(self, position_data: Dict[str, Any]):
        """Update internal position tracking from WebSocket event."""
        instrument_id = position_data.get("instrument", "")
        if not instrument_id:
            return

        trading_pair = web_utils.instrument_to_trading_pair(instrument_id)
        qty_str = position_data.get("quantity", position_data.get("size", "0"))
        size = Decimal(str(qty_str))
        entry_price = Decimal(str(position_data.get("entryPrice", position_data.get("entry_price", "0"))))
        unrealized_pnl = Decimal(str(position_data.get("unrealisedPnl", position_data.get("unrealized_pnl", "0"))))
        side_str = position_data.get("side", "buy").lower()

        if side_str == "buy":
            position_side = PositionSide.LONG
        else:
            position_side = PositionSide.SHORT

        position = self._perpetual_trading.get_position(trading_pair, position_side)
        if position is not None:
            position.update_position(
                position_side=position_side,
                unrealized_pnl=unrealized_pnl,
                entry_price=entry_price,
                amount=abs(size),
            )

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_balances(self):
        """Fetch account balances from EVEDEX."""
        await self._ensure_authenticated()

        import aiohttp
        trade_url = web_utils.get_trade_base_url(self._domain)
        headers = {
            "Accept": "application/json",
            **self._auth.get_auth_headers(),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{trade_url}{CONSTANTS.USER_BALANCE_URL}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return
                    data = await resp.json()
                    # Response may be array or wrapped
                    balances = data if isinstance(data, list) else data.get("data", data.get("balances", []))
                    if isinstance(balances, list):
                        for bal in balances:
                            coin = bal.get("coin", bal.get("currency", "USD"))
                            total = Decimal(str(bal.get("balance", bal.get("total", "0"))))
                            available = Decimal(str(bal.get("availableBalance", bal.get("available", total))))
                            self._account_balances[coin] = total
                            self._account_available_balances[coin] = available
                    elif isinstance(balances, dict):
                        # Single balance object
                        coin = balances.get("coin", "USD")
                        total = Decimal(str(balances.get("balance", "0")))
                        available = Decimal(str(balances.get("availableBalance", total)))
                        self._account_balances[coin] = total
                        self._account_available_balances[coin] = available
        except Exception as e:
            self.logger().warning(f"Balance update failed: {e}")

    async def _update_positions(self):
        """Fetch current open positions from EVEDEX."""
        await self._ensure_authenticated()

        import aiohttp
        trade_url = web_utils.get_trade_base_url(self._domain)
        headers = {
            "Accept": "application/json",
            **self._auth.get_auth_headers(),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{trade_url}{CONSTANTS.POSITIONS_URL}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return
                    data = await resp.json()
                    positions = data if isinstance(data, list) else data.get("data", data.get("positions", []))
                    if isinstance(positions, list):
                        for pos_data in positions:
                            await self._process_position_message(pos_data)
        except Exception as e:
            self.logger().warning(f"Position update failed: {e}")

    async def _get_funding_info(self, trading_pair: str) -> FundingInfo:
        """Fetch funding rate from instruments endpoint."""
        import aiohttp
        base_url = web_utils.get_trade_base_url(self._domain)
        instrument = web_utils.trading_pair_to_instrument(trading_pair)

        index_price = Decimal("0")
        mark_price = Decimal("0")
        funding_rate = Decimal("0")
        next_funding_ts = int(time.time()) + 3600

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base_url}{CONSTANTS.INSTRUMENTS_URL}",
                    headers={"Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    instruments = await resp.json()
                    for instr in (instruments if isinstance(instruments, list) else []):
                        if instr.get("id", "").lower() == instrument.lower():
                            mark_price = Decimal(str(instr.get("markPrice", "0")))
                            index_price = Decimal(str(instr.get("indexPrice", mark_price)))
                            funding_rate = Decimal(str(instr.get("fundingRate", "0")))
                            break
        except Exception as e:
            self.logger().warning(f"Funding info fetch failed for {trading_pair}: {e}")

        return FundingInfo(
            trading_pair=trading_pair,
            index_price=index_price,
            mark_price=mark_price,
            next_funding_utc_timestamp=next_funding_ts,
            rate=funding_rate,
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List) -> None:
        mapping = bidict()
        for instr in exchange_info:
            instrument_id = instr.get("id", "")
            if instrument_id:
                trading_pair = web_utils.instrument_to_trading_pair(instrument_id)
                mapping[instrument_id] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = self._auth.generate_order_id()
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
        order_id = self._auth.generate_order_id()
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
