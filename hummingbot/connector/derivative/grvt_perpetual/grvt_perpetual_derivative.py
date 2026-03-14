import asyncio
import json
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GrvtPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_user_stream_data_source import (
    GrvtPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import (
    DEFAULT_FEES,
    grvt_order_status_to_hummingbot,
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
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GrvtPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Hummingbot connector for GRVT perpetual futures exchange.

    GRVT is a derivatives exchange using:
    - EIP-712 typed data signing for orders
    - Cookie-based REST authentication
    - WebSocket streams for market and user data
    - Three API domains: market-data, trades, edge
    """

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        grvt_api_key: str,
        grvt_private_key: str,
        grvt_trading_account_id: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = grvt_api_key
        self._private_key = grvt_private_key
        self._trading_account_id = grvt_trading_account_id
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
    def authenticator(self) -> Optional[GrvtPerpetualAuth]:
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
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return "USDT"

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return "USDT"

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
            domain=self._domain,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GrvtPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GrvtPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_auth(self) -> GrvtPerpetualAuth:
        return GrvtPerpetualAuth(
            api_key=self._api_key,
            private_key=self._private_key,
            trading_account_id=self._trading_account_id,
            testnet=(self._domain == CONSTANTS.TESTNET_DOMAIN),
        )

    async def _make_network_check_request(self):
        """Ping market data endpoint to verify connectivity."""
        import aiohttp
        base_url = web_utils.get_market_data_url(self._domain)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}{CONSTANTS.INSTRUMENTS_URL}",
                json={"is_active": True},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise ConnectionError(f"Network check failed: HTTP {resp.status}")

    async def _make_trading_rules_request(self) -> Any:
        """Fetch all active instruments from GRVT."""
        import aiohttp
        base_url = web_utils.get_market_data_url(self._domain)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}{CONSTANTS.INSTRUMENTS_URL}",
                json={"is_active": True},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                return data.get("result", [])

    async def _make_trading_pairs_request(self) -> Any:
        return await self._make_trading_rules_request()

    async def _authenticate(self):
        """Login with API key to get session cookie."""
        import aiohttp
        edge_url = web_utils.get_edge_url(self._domain)
        payload = self._auth.get_login_payload()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{edge_url}{CONSTANTS.AUTH_URL}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    # Extract cookie from response
                    cookie_header = resp.headers.get("Set-Cookie", "")
                    if cookie_header:
                        cookie_val = cookie_header.split(";")[0]
                        self._auth.set_session_cookie(cookie_val)
                        self.logger().info("GRVT authentication successful")
                else:
                    body = await resp.text()
                    self.logger().warning(f"GRVT authentication failed: {resp.status} {body}")

    async def _update_trading_rules(self):
        """Fetch and cache instrument information, build TradingRule objects."""
        instruments = await self._make_trading_rules_request()

        trading_rules_list = await self._format_trading_rules(instruments)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        # Cache instrument info for use in order signing
        for instr in instruments:
            instrument = instr.get("instrument", "")
            if instrument:
                self._instrument_info[instrument] = instr

    async def _initialize_trading_pair_symbol_map(self):
        """Build the trading pair <-> exchange symbol bidict."""
        instruments = await self._make_trading_pairs_request()
        mapping = bidict()
        for instr in instruments:
            instrument = instr.get("instrument", "")
            trading_pair = web_utils.instrument_to_trading_pair(instrument)
            if instrument:
                mapping[instrument] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, raw_instruments: List[Dict[str, Any]]) -> List[TradingRule]:
        """Convert raw instrument data to TradingRule objects."""
        result = []
        for instr in raw_instruments:
            instrument = instr.get("instrument", "")
            if not instrument or instr.get("kind") != "PERPETUAL":
                continue
            trading_pair = web_utils.instrument_to_trading_pair(instrument)
            tick_size = Decimal(str(instr.get("tick_size", "0.01")))
            min_size = Decimal(str(instr.get("min_size", "0.001")))

            result.append(
                TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_size,
                    min_price_increment=tick_size,
                    min_base_amount_increment=min_size,
                    min_notional_size=Decimal(str(CONSTANTS.MIN_NOTIONAL_SIZE)),
                    buy_order_collateral_token="USDT",
                    sell_order_collateral_token="USDT",
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
        """Submit an order to GRVT via EIP-712 signed REST call."""
        instrument = web_utils.trading_pair_to_instrument(trading_pair)
        instr_info = self._instrument_info.get(instrument, {})

        base_decimals = instr_info.get("base_decimals", 9)
        is_buy = trade_type == TradeType.BUY
        is_market = order_type == OrderType.MARKET

        # Build order leg
        asset_id = int(instr_info.get("instrument_hash", "0x0"), 16) if instr_info.get("instrument_hash") else 0

        price_int = self._auth.price_to_int(float(price)) if not is_market else 0
        size_int = self._auth.size_to_int(float(amount), base_decimals)

        leg = {
            "assetID": asset_id,
            "contractSize": size_int,
            "limitPrice": price_int,
            "isBuyingContract": is_buy,
        }

        # Determine time-in-force
        if is_market:
            tif = 3  # IOC
        elif order_type == OrderType.LIMIT_MAKER:
            tif = 1  # GTT (post-only)
        else:
            tif = 1  # GTT default

        expiration_ns = web_utils.get_expiration_ns(seconds_from_now=86400)

        signed_payload = self._auth.sign_order(
            sub_account_id=self._auth.trading_account_id,
            is_market=is_market,
            time_in_force=tif,
            post_only=(order_type == OrderType.LIMIT_MAKER),
            reduce_only=(position_action == PositionAction.CLOSE),
            legs=[leg],
            expiration_ns=expiration_ns,
        )

        # Add client metadata
        signed_payload["metadata"] = {"client_order_id": order_id}

        import aiohttp
        trade_url = web_utils.get_trade_data_url(self._domain)

        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            if self._auth._session_cookie:
                headers["Cookie"] = self._auth._session_cookie

            async with session.post(
                f"{trade_url}{CONSTANTS.CREATE_ORDER_URL}",
                json=signed_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    error_msg = data.get("message", str(data))
                    raise IOError(f"GRVT order placement failed: {error_msg}")

                result = data.get("result", {})
                exchange_order_id = result.get("order_id", order_id)
                return exchange_order_id, time.time()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """Cancel an order by exchange order ID."""
        import aiohttp
        trade_url = web_utils.get_trade_data_url(self._domain)

        payload = {
            "sub_account_id": str(self._auth.trading_account_id),
            "order_id": tracked_order.exchange_order_id or order_id,
        }

        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            if self._auth._session_cookie:
                headers["Cookie"] = self._auth._session_cookie

            async with session.post(
                f"{trade_url}{CONSTANTS.CANCEL_ORDER_URL}",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    error_msg = data.get("message", str(data))
                    if CONSTANTS.ORDER_NOT_EXIST_MESSAGE in error_msg.lower():
                        await self._order_tracker.process_order_not_found(order_id)
                    raise IOError(f"GRVT cancel failed: {error_msg}")
                return True

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """Fetch current status of an order."""
        import aiohttp
        trade_url = web_utils.get_trade_data_url(self._domain)
        payload = {
            "sub_account_id": str(self._auth.trading_account_id),
            "order_id": tracked_order.exchange_order_id,
        }

        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            if self._auth._session_cookie:
                headers["Cookie"] = self._auth._session_cookie

            async with session.post(
                f"{trade_url}{CONSTANTS.GET_ORDER_URL}",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise IOError(f"Order status request failed: {data}")

                order_data = data.get("result", {})
                grvt_status = order_data.get("status", "OPEN")
                new_state = grvt_order_status_to_hummingbot(grvt_status)

                return OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=time.time(),
                    new_state=new_state,
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
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
        pass  # Implemented via _update_order_status

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """Fetch trade fills for an order."""
        import aiohttp
        trade_url = web_utils.get_trade_data_url(self._domain)
        payload = {
            "sub_account_id": str(self._auth.trading_account_id),
            "order_id": order.exchange_order_id,
            "limit": 50,
        }

        results = []
        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            if self._auth._session_cookie:
                headers["Cookie"] = self._auth._session_cookie

            async with session.post(
                f"{trade_url}{CONSTANTS.GET_FILL_HISTORY_URL}",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                fills = data.get("result", [])

        for fill in fills:
            fee_amount = Decimal(str(fill.get("fee", "0")))
            fee_token = fill.get("fee_currency", "USDT")
            trade_update = TradeUpdate(
                trade_id=str(fill.get("fill_id", "")),
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                fee=TradeFeeBase.new_perpetual_fee(
                    fee_schema=DEFAULT_FEES,
                    position_action=order.position,
                    percent_token=fee_token,
                    flat_fees=[TokenAmount(token=fee_token, amount=fee_amount)],
                ),
                fill_base_amount=Decimal(str(fill.get("size", "0"))),
                fill_quote_amount=Decimal(str(fill.get("size", "0"))) * Decimal(str(fill.get("price", "0"))),
                fill_price=Decimal(str(fill.get("price", "0"))),
                fill_timestamp=float(fill.get("event_time", time.time() * 1e9)) / 1e9,
            )
            results.append(trade_update)
        return results

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        """Fetch current mark/last prices for all tracked trading pairs."""
        import aiohttp
        market_url = web_utils.get_market_data_url(self._domain)
        result = []

        async with aiohttp.ClientSession() as session:
            for trading_pair in self._trading_pairs:
                instrument = web_utils.trading_pair_to_instrument(trading_pair)
                try:
                    async with session.post(
                        f"{market_url}{CONSTANTS.TICKER_URL}",
                        json={"instrument": instrument},
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=8),
                    ) as resp:
                        data = await resp.json()
                        ticker = data.get("result", {})
                        result.append({
                            "symbol": instrument,
                            "price": str(ticker.get("mark_price") or ticker.get("last_price") or "0"),
                        })
                except Exception:
                    pass
        return result

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """Return last traded price for a single trading pair."""
        import aiohttp
        market_url = web_utils.get_market_data_url(self._domain)
        instrument = web_utils.trading_pair_to_instrument(trading_pair)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{market_url}{CONSTANTS.TICKER_URL}",
                json={"instrument": instrument},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
                ticker = data.get("result", {})
                price = ticker.get("last_price") or ticker.get("mark_price") or "0"
                return float(price)

    async def _update_trading_fees(self):
        """GRVT uses fixed fee schedule — no dynamic fetch needed."""
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
        is_maker = is_maker or (order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER))
        return DeductedFromReturnsTradeFee(percent=DEFAULT_FEES.maker_percent_fee_decimal if is_maker
                                          else DEFAULT_FEES.taker_percent_fee_decimal)

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
        """Process user order/position/fill events from WebSocket."""
        async for event_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User stream event error: {e}", exc_info=True)

    async def _process_user_stream_event(self, event: Dict[str, Any]):
        """Route user stream events to appropriate handlers."""
        stream = event.get("stream", "")

        if "order" in stream:
            result = event.get("result", {})
            if isinstance(result, list):
                for order_data in result:
                    self._process_order_message(order_data)
            elif isinstance(result, dict):
                self._process_order_message(result)

        elif "fill" in stream:
            result = event.get("result", {})
            fills = result if isinstance(result, list) else [result]
            for fill in fills:
                await self._process_fill_message(fill)

        elif "position" in stream:
            result = event.get("result", {})
            positions = result if isinstance(result, list) else [result]
            for pos in positions:
                await self._process_position_message(pos)

    def _process_order_message(self, order_data: Dict[str, Any]):
        """Handle an order update event."""
        exchange_order_id = str(order_data.get("order_id", ""))
        client_order_id = order_data.get("metadata", {}).get("client_order_id", "")

        if not client_order_id:
            tracked_order = self._order_tracker.fetch_order(exchange_order_id=exchange_order_id)
            if tracked_order:
                client_order_id = tracked_order.client_order_id

        grvt_status = order_data.get("status", "OPEN")
        new_state = grvt_order_status_to_hummingbot(grvt_status)

        order_update = OrderUpdate(
            trading_pair=web_utils.instrument_to_trading_pair(order_data.get("instrument", "")),
            update_timestamp=float(order_data.get("event_time", time.time() * 1e9)) / 1e9,
            new_state=new_state,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
        )
        self._order_tracker.process_order_update(order_update)

    async def _process_fill_message(self, fill_data: Dict[str, Any]):
        """Handle a fill (trade execution) event."""
        exchange_order_id = str(fill_data.get("order_id", ""))
        tracked_order = self._order_tracker.fetch_order(exchange_order_id=exchange_order_id)
        if not tracked_order:
            return

        fee_amount = Decimal(str(fill_data.get("fee", "0")))
        fee_token = fill_data.get("fee_currency", "USDT")
        fill_price = Decimal(str(fill_data.get("price", "0")))
        fill_size = Decimal(str(fill_data.get("size", "0")))

        trade_update = TradeUpdate(
            trade_id=str(fill_data.get("fill_id", "")),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fee=TradeFeeBase.new_perpetual_fee(
                fee_schema=DEFAULT_FEES,
                position_action=tracked_order.position,
                percent_token=fee_token,
                flat_fees=[TokenAmount(token=fee_token, amount=fee_amount)],
            ),
            fill_base_amount=fill_size,
            fill_quote_amount=fill_size * fill_price,
            fill_price=fill_price,
            fill_timestamp=float(fill_data.get("event_time", time.time() * 1e9)) / 1e9,
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _process_position_message(self, position_data: Dict[str, Any]):
        """Update internal position tracking from WebSocket event."""
        instrument = position_data.get("instrument", "")
        trading_pair = web_utils.instrument_to_trading_pair(instrument)
        size = Decimal(str(position_data.get("size", "0")))
        entry_price = Decimal(str(position_data.get("entry_price", "0")))
        unrealized_pnl = Decimal(str(position_data.get("unrealized_pnl", "0")))

        is_long = size > Decimal("0")
        position_side = PositionSide.LONG if is_long else PositionSide.SHORT

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
        """Fetch account balances from GRVT."""
        import aiohttp
        trade_url = web_utils.get_trade_data_url(self._domain)
        payload = {"sub_account_id": str(self._auth.trading_account_id)}

        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            if self._auth._session_cookie:
                headers["Cookie"] = self._auth._session_cookie

            try:
                async with session.post(
                    f"{trade_url}{CONSTANTS.GET_ACCOUNT_SUMMARY_URL}",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        return
                    account = data.get("result", {})
                    balances = account.get("spot_balances", [])
                    for bal in balances:
                        token = bal.get("currency", "USDT")
                        total = Decimal(str(bal.get("total_value", "0")))
                        available = Decimal(str(bal.get("available", "0")))
                        self._account_balances[token] = total
                        self._account_available_balances[token] = available
            except Exception as e:
                self.logger().warning(f"Balance update failed: {e}")

    async def _update_positions(self):
        """Fetch current open positions from GRVT."""
        import aiohttp
        trade_url = web_utils.get_trade_data_url(self._domain)
        payload = {"sub_account_id": str(self._auth.trading_account_id)}

        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            if self._auth._session_cookie:
                headers["Cookie"] = self._auth._session_cookie

            try:
                async with session.post(
                    f"{trade_url}{CONSTANTS.GET_POSITIONS_URL}",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        return
                    positions = data.get("result", [])
                    for pos_data in positions:
                        await self._process_position_message(pos_data)
            except Exception as e:
                self.logger().warning(f"Position update failed: {e}")

    async def _get_funding_info(self, trading_pair: str) -> FundingInfo:
        """Fetch funding rate and related data."""
        import aiohttp
        market_url = web_utils.get_market_data_url(self._domain)
        instrument = web_utils.trading_pair_to_instrument(trading_pair)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{market_url}{CONSTANTS.FUNDING_RATE_URL}",
                json={"instrument": instrument},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
                funding = data.get("result", {})

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{market_url}{CONSTANTS.TICKER_URL}",
                json={"instrument": instrument},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                ticker_data = await resp.json()
                ticker = ticker_data.get("result", {})

        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(ticker.get("index_price", "0"))),
            mark_price=Decimal(str(ticker.get("mark_price", "0"))),
            next_funding_utc_timestamp=int(funding.get("next_funding_time", time.time() + 3600)),
            rate=Decimal(str(funding.get("funding_rate", "0"))),
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List) -> None:
        mapping = bidict()
        for instr in exchange_info:
            instrument = instr.get("instrument", "")
            if instrument and instr.get("kind") == "PERPETUAL":
                trading_pair = web_utils.instrument_to_trading_pair(instrument)
                mapping[instrument] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = self.get_order_id(trading_pair)
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
        order_id = self.get_order_id(trading_pair)
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

    def get_order_id(self, trading_pair: str) -> str:
        import random
        return f"{self.client_order_id_prefix}{trading_pair}-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
