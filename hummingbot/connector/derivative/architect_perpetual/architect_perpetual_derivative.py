import asyncio
import time
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_api_order_book_data_source import (
    ArchitectPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_user_stream_data_source import (
    ArchitectPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_utils import (
    DEFAULT_FEES,
    order_status_to_hummingbot,
)
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class ArchitectPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Hummingbot connector for Architect perpetual futures.

    Architect is an institutional trading platform aggregating multiple venues
    (Binance, CME, etc.) with a gRPC API wrapped by the architect-py SDK.

    Key differences from other connectors:
    - Uses architect-py AsyncClient instead of raw REST/WebSocket
    - No custom auth class — SDK handles JWT token lifecycle
    - Symbols: "{BASE}-{QUOTE} {VENUE} Perpetual" e.g. "BTC-USDT BINANCE Perpetual"
    - Paper trading support via paper_trading=True flag
    """

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        architect_api_key: str,
        architect_api_secret: str,
        architect_execution_venue: str = CONSTANTS.DEFAULT_EXECUTION_VENUE,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = architect_api_key
        self._api_secret = architect_api_secret
        self._execution_venue = architect_execution_venue
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []

        # architect-py AsyncClient (initialized in _authenticate)
        self._client = None
        self._trading_account: Optional[str] = None

        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self):
        return None  # architect-py handles auth internally

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> Optional[int]:
        return 10  # Architect tag field: max 10 ASCII chars

    @property
    def client_order_id_prefix(self) -> str:
        return "HBOT"

    @property
    def trading_rules_request_path(self) -> str:
        return "list_symbols"

    @property
    def trading_pairs_request_path(self) -> str:
        return "list_symbols"

    @property
    def check_network_request_path(self) -> str:
        return "list_symbols"

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
        # Quote currency is the collateral (e.g. USDT in BTC-USDT)
        parts = trading_pair.split("-")
        return parts[1] if len(parts) == 2 else "USDT"

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        parts = trading_pair.split("-")
        return parts[1] if len(parts) == 2 else "USDT"

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(domain=self._domain)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ArchitectPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ArchitectPerpetualUserStreamDataSource(
            connector=self,
            domain=self._domain,
        )

    def _create_auth(self):
        return None  # No Hummingbot auth class needed; architect-py handles it

    async def _authenticate(self):
        """Initialize the architect-py AsyncClient with API credentials."""
        if self._client is not None:
            return
        try:
            from architect_py import AsyncClient
            self._client = await AsyncClient.connect(
                endpoint=CONSTANTS.GRPC_ENDPOINT,
                api_key=self._api_key,
                api_secret=self._api_secret,
                paper_trading=web_utils.is_paper_trading(self._domain),
            )
            # Fetch default trading account
            accounts = await self._client.list_accounts()
            if accounts:
                self._trading_account = accounts[0].account
                self.logger().info(f"Architect connected. Account: {self._trading_account}")
            else:
                self.logger().warning("Architect: no accounts found")
        except Exception as e:
            self.logger().error(f"Architect authentication failed: {e}")
            self._client = None

    async def _make_network_check_request(self):
        """Verify connectivity by listing symbols."""
        if self._client is None:
            await self._authenticate()
        if self._client is None:
            raise ConnectionError("Architect client not connected")
        await self._client.list_symbols()

    async def _make_trading_rules_request(self) -> Any:
        """Fetch perpetual symbols for the configured execution venue."""
        if self._client is None:
            await self._authenticate()
        if self._client is None:
            return []
        try:
            all_symbols = await self._client.list_symbols()
            # Filter to perpetuals on our venue
            perps = [
                s for s in all_symbols
                if CONSTANTS.PERPETUAL_SYMBOL_SUFFIX in s and self._execution_venue in s
            ]
            return perps
        except Exception as e:
            self.logger().warning(f"Failed to list symbols: {e}")
            return []

    async def _make_trading_pairs_request(self) -> Any:
        return await self._make_trading_rules_request()

    async def _update_trading_rules(self):
        symbols = await self._make_trading_rules_request()
        trading_rules_list = await self._format_trading_rules(symbols)
        self._trading_rules.clear()
        for rule in trading_rules_list:
            self._trading_rules[rule.trading_pair] = rule

    async def _initialize_trading_pair_symbol_map(self):
        symbols = await self._make_trading_pairs_request()
        mapping = bidict()
        for symbol in symbols:
            trading_pair = web_utils.architect_symbol_to_trading_pair(symbol)
            mapping[symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, symbols: List[str]) -> List[TradingRule]:
        """Build TradingRule objects from Architect symbol list."""
        result = []
        if self._client is None:
            return result
        for symbol in symbols:
            try:
                trading_pair = web_utils.architect_symbol_to_trading_pair(symbol)
                parts = trading_pair.split("-")
                quote = parts[1] if len(parts) == 2 else "USDT"

                # Try to get execution info for min sizes
                try:
                    exec_info = await self._client.get_execution_info(
                        symbol=symbol,
                        execution_venue=self._execution_venue,
                    )
                    min_qty = Decimal(str(exec_info.min_order_quantity or "0.001"))
                    qty_step = Decimal(str(exec_info.step_size or "0.001"))
                    tick_size = Decimal(str(exec_info.tick_size or "0.01"))
                except Exception:
                    min_qty = Decimal("0.001")
                    qty_step = Decimal("0.001")
                    tick_size = Decimal("0.01")

                result.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_qty,
                        min_price_increment=tick_size,
                        min_base_amount_increment=qty_step,
                        min_notional_size=Decimal(str(CONSTANTS.MIN_NOTIONAL_SIZE)),
                        buy_order_collateral_token=quote,
                        sell_order_collateral_token=quote,
                    )
                )
            except Exception as e:
                self.logger().warning(f"Failed to build trading rule for {symbol}: {e}")
        return result

    def _generate_order_tag(self, order_id: str) -> str:
        """Architect tag: max 10 ASCII graphic chars."""
        # Use last 10 chars of order_id (hex portion)
        tag = order_id.replace("-", "")[-10:]
        return tag[:10]

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
        """Place an order via architect-py."""
        if self._client is None:
            await self._authenticate()

        from architect_py.common_types.order_dir import OrderDir
        from architect_py.grpc.models.definitions import OrderType as ArchOrderType
        from architect_py.common_types.time_in_force import TimeInForce

        symbol = web_utils.trading_pair_to_architect_symbol(trading_pair, self._execution_venue)
        direction = OrderDir.BUY if trade_type == TradeType.BUY else OrderDir.SELL
        tag = self._generate_order_tag(order_id)

        if order_type == OrderType.MARKET:
            arch_order_type = ArchOrderType.MARKET
            limit_price = None
            tif = TimeInForce.IOC
        elif order_type == OrderType.LIMIT_MAKER:
            arch_order_type = ArchOrderType.LIMIT
            limit_price = price
            tif = TimeInForce.GTC
        else:
            arch_order_type = ArchOrderType.LIMIT
            limit_price = price
            tif = TimeInForce.GTC

        order = await self._client.place_order(
            symbol=symbol,
            execution_venue=self._execution_venue,
            dir=direction,
            quantity=amount,
            limit_price=limit_price,
            order_type=arch_order_type,
            time_in_force=tif,
            account=self._trading_account,
            post_only=(order_type == OrderType.LIMIT_MAKER),
            tag=tag,
        )

        exchange_order_id = str(order.id)
        return exchange_order_id, time.time()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """Cancel an order via architect-py."""
        if self._client is None:
            await self._authenticate()

        exchange_order_id = tracked_order.exchange_order_id or order_id
        try:
            await self._client.cancel_order(order_id=exchange_order_id)
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if CONSTANTS.ORDER_NOT_EXIST_MESSAGE in error_msg or "not found" in error_msg:
                await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f"Architect cancel failed: {e}")

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """Fetch current order status via architect-py."""
        if self._client is None:
            await self._authenticate()

        exchange_order_id = tracked_order.exchange_order_id or tracked_order.client_order_id
        order = await self._client.get_order(order_id=exchange_order_id)

        if order is None:
            raise IOError(f"Order {exchange_order_id} not found")

        status_str = order.o.value if hasattr(order.o, 'value') else str(order.o)
        new_state = order_status_to_hummingbot(status_str)

        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=time.time(),
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
        )

    async def _update_order_status(self):
        tracked_orders = list(self.in_flight_orders.values())
        for order in tracked_orders:
            if order.exchange_order_id:
                try:
                    order_update = await self._request_order_status(order)
                    self._order_tracker.process_order_update(order_update)
                except Exception as e:
                    self.logger().warning(f"Order status update failed for {order.client_order_id}: {e}")

    async def _update_lost_orders_status(self):
        pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """Fetch historical fills for an order."""
        if self._client is None:
            return []
        results = []
        try:
            fills_response = await self._client.get_fills(order_id=order.exchange_order_id)
            fills = fills_response.fills if hasattr(fills_response, 'fills') else []
            for fill in fills:
                fill_price = Decimal(str(fill.p))
                fill_qty = Decimal(str(fill.q))
                fee_amount = Decimal(str(fill.f or 0)) if hasattr(fill, 'f') else Decimal("0")
                quote = self.get_buy_collateral_token(order.trading_pair)

                trade_update = TradeUpdate(
                    trade_id=str(fill.id),
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=TradeFeeBase.new_perpetual_fee(
                        fee_schema=DEFAULT_FEES,
                        position_action=order.position,
                        percent_token=quote,
                        flat_fees=[TokenAmount(token=quote, amount=fee_amount)],
                    ),
                    fill_base_amount=fill_qty,
                    fill_quote_amount=fill_qty * fill_price,
                    fill_price=fill_price,
                    fill_timestamp=float(fill.ts) if hasattr(fill, 'ts') else time.time(),
                )
                results.append(trade_update)
        except Exception as e:
            self.logger().warning(f"Failed to fetch fills for {order.client_order_id}: {e}")
        return results

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        if self._client is None:
            return []
        result = []
        for trading_pair in self._trading_pairs:
            symbol = web_utils.trading_pair_to_architect_symbol(trading_pair, self._execution_venue)
            try:
                ticker = await self._client.get_ticker(symbol=symbol, venue=self._execution_venue)
                price = str(ticker.p or ticker.mp or 0)
                result.append({"symbol": symbol, "price": price})
            except Exception:
                pass
        return result

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        if self._client is None:
            return 0.0
        symbol = web_utils.trading_pair_to_architect_symbol(trading_pair, self._execution_venue)
        try:
            ticker = await self._client.get_ticker(symbol=symbol, venue=self._execution_venue)
            return float(ticker.p or ticker.mp or 0)
        except Exception:
            return 0.0

    async def _update_trading_fees(self):
        pass  # Architect uses fixed fees per venue tier

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
        return DeductedFromReturnsTradeFee(
            percent=DEFAULT_FEES.maker_percent_fee_decimal if is_maker
            else DEFAULT_FEES.taker_percent_fee_decimal
        )

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "not found" in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "not found" in str(cancelation_exception).lower()

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await asyncio.wait_for(self._user_stream_tracker.user_stream.get(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User stream event error: {e}", exc_info=True)

    async def _process_user_stream_event(self, event: Dict[str, Any]):
        """Route architect-py orderflow events to appropriate handlers."""
        event_type = event.get("type", "")
        data = event.get("data")

        if data is None:
            return

        if event_type == "TaggedOrderAck":
            # Order acknowledged by exchange
            exchange_order_id = str(data.eid or data.id)
            order_id = str(data.id)
            tracked = self._order_tracker.fetch_order(exchange_order_id=order_id)
            if tracked:
                order_update = OrderUpdate(
                    trading_pair=tracked.trading_pair,
                    update_timestamp=time.time(),
                    new_state=OrderState.OPEN,
                    client_order_id=tracked.client_order_id,
                    exchange_order_id=exchange_order_id,
                )
                self._order_tracker.process_order_update(order_update)

        elif event_type in ("TaggedOrderOut", "ReconciledOut"):
            # Order fully filled
            order_id = str(data.id)
            tracked = self._order_tracker.fetch_order(exchange_order_id=order_id)
            if tracked:
                order_update = OrderUpdate(
                    trading_pair=tracked.trading_pair,
                    update_timestamp=time.time(),
                    new_state=OrderState.FILLED,
                    client_order_id=tracked.client_order_id,
                    exchange_order_id=order_id,
                )
                self._order_tracker.process_order_update(order_update)

        elif event_type == "TaggedOrderCanceled":
            order_id = str(data.id)
            tracked = self._order_tracker.fetch_order(exchange_order_id=order_id)
            if tracked:
                order_update = OrderUpdate(
                    trading_pair=tracked.trading_pair,
                    update_timestamp=time.time(),
                    new_state=OrderState.CANCELED,
                    client_order_id=tracked.client_order_id,
                    exchange_order_id=order_id,
                )
                self._order_tracker.process_order_update(order_update)

        elif event_type == "TaggedOrderReject":
            order_id = str(data.id)
            tracked = self._order_tracker.fetch_order(exchange_order_id=order_id)
            if tracked:
                order_update = OrderUpdate(
                    trading_pair=tracked.trading_pair,
                    update_timestamp=time.time(),
                    new_state=OrderState.FAILED,
                    client_order_id=tracked.client_order_id,
                    exchange_order_id=order_id,
                )
                self._order_tracker.process_order_update(order_update)

        elif event_type == "TaggedFill":
            await self._process_fill_event(data)

    async def _process_fill_event(self, fill_data):
        """Handle a fill event from the orderflow stream."""
        order_id = str(fill_data.oid) if hasattr(fill_data, 'oid') else ""
        tracked = self._order_tracker.fetch_order(exchange_order_id=order_id)
        if not tracked:
            return

        fill_price = Decimal(str(fill_data.p))
        fill_qty = Decimal(str(fill_data.q))
        fill_id = str(fill_data.id) if hasattr(fill_data, 'id') else str(time.time())
        fee_amount = Decimal(str(fill_data.f or 0)) if hasattr(fill_data, 'f') else Decimal("0")
        fee_unit = str(fill_data.fu) if hasattr(fill_data, 'fu') and fill_data.fu else "USDT"
        quote = self.get_buy_collateral_token(tracked.trading_pair)

        trade_update = TradeUpdate(
            trade_id=fill_id,
            client_order_id=tracked.client_order_id,
            exchange_order_id=order_id,
            trading_pair=tracked.trading_pair,
            fee=TradeFeeBase.new_perpetual_fee(
                fee_schema=DEFAULT_FEES,
                position_action=tracked.position,
                percent_token=quote,
                flat_fees=[TokenAmount(token=fee_unit, amount=fee_amount)],
            ),
            fill_base_amount=fill_qty,
            fill_quote_amount=fill_qty * fill_price,
            fill_price=fill_price,
            fill_timestamp=float(fill_data.ts) if hasattr(fill_data, 'ts') else time.time(),
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_balances(self):
        """Fetch account balances from Architect."""
        if self._client is None or not self._trading_account:
            return
        try:
            summary = await self._client.get_account_summary(account=self._trading_account)
            # summary.balances: dict of {symbol: quantity}
            if hasattr(summary, 'balances') and summary.balances:
                for token, qty in summary.balances.items():
                    token_name = web_utils.architect_symbol_to_trading_pair(token) if " " in token else token
                    total = Decimal(str(qty))
                    self._account_balances[token_name] = total
                    # Use available_margin as proxy for available balance
                    self._account_available_balances[token_name] = total

            # Set USDT available from equity/available_margin
            if hasattr(summary, 'available_margin') and summary.available_margin is not None:
                quote = "USDT"
                avail = Decimal(str(summary.available_margin))
                self._account_available_balances[quote] = avail
            if hasattr(summary, 'equity') and summary.equity is not None:
                quote = "USDT"
                total = Decimal(str(summary.equity))
                self._account_balances[quote] = total
        except Exception as e:
            self.logger().warning(f"Balance update failed: {e}")

    async def _update_positions(self):
        """Fetch open positions from Architect."""
        if self._client is None or not self._trading_account:
            return
        try:
            positions = await self._client.get_positions_summary(accounts=[self._trading_account])
            for pos in positions:
                symbol = str(pos.symbol)
                if not web_utils.is_perpetual_symbol(symbol):
                    continue
                trading_pair = web_utils.architect_symbol_to_trading_pair(symbol)
                qty = Decimal(str(pos.quantity or 0))
                entry_price = Decimal(str(pos.avg_cost_basis or 0))
                unrealized_pnl = Decimal(str(pos.unrealized_pnl or 0))

                from architect_py.common_types.order_dir import OrderDir
                dir_val = pos.direction
                if hasattr(dir_val, 'value'):
                    dir_val = dir_val.value
                is_long = str(dir_val).upper() in ("BUY", "LONG")
                position_side = PositionSide.LONG if is_long else PositionSide.SHORT

                position = self._perpetual_trading.get_position(trading_pair, position_side)
                if position is not None:
                    position.update_position(
                        position_side=position_side,
                        unrealized_pnl=unrealized_pnl,
                        entry_price=entry_price,
                        amount=abs(qty),
                    )
        except Exception as e:
            self.logger().warning(f"Position update failed: {e}")

    async def _get_funding_info(self, trading_pair: str) -> FundingInfo:
        """Fetch funding rate from Architect ticker."""
        if self._client is None:
            return FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal("0"),
                mark_price=Decimal("0"),
                next_funding_utc_timestamp=int(time.time()) + 3600,
                rate=Decimal("0"),
            )

        symbol = web_utils.trading_pair_to_architect_symbol(trading_pair, self._execution_venue)
        try:
            ticker = await self._client.get_ticker(symbol=symbol, venue=self._execution_venue)
            # ticker fields: 'mp' = mark_price, 'ip' = index_price, 'fr' = funding_rate, 'ft' = funding_time
            mark_price = Decimal(str(ticker.mp or ticker.p or 0))
            index_price = Decimal(str(ticker.ip or mark_price))
            funding_rate = Decimal(str(ticker.fr or 0))
            next_funding = int(ticker.ft) if hasattr(ticker, 'ft') and ticker.ft else int(time.time()) + 3600
            return FundingInfo(
                trading_pair=trading_pair,
                index_price=index_price,
                mark_price=mark_price,
                next_funding_utc_timestamp=next_funding,
                rate=funding_rate,
            )
        except Exception as e:
            self.logger().warning(f"Funding info failed for {trading_pair}: {e}")
            return FundingInfo(
                trading_pair=trading_pair,
                index_price=Decimal("0"),
                mark_price=Decimal("0"),
                next_funding_utc_timestamp=int(time.time()) + 3600,
                rate=Decimal("0"),
            )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List) -> None:
        mapping = bidict()
        for symbol in exchange_info:
            if isinstance(symbol, str):
                trading_pair = web_utils.architect_symbol_to_trading_pair(symbol)
                mapping[symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = f"HBOT{uuid.uuid4().hex[:6]}"
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
        order_id = f"HBOT{uuid.uuid4().hex[:6]}"
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
