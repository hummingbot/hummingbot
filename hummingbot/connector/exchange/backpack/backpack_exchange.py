import asyncio
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.backpack import (
    backpack_constants as CONSTANTS,
    backpack_web_utils as web_utils,
)
from hummingbot.connector.exchange.backpack.backpack_api_order_book_data_source import (
    BackpackAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source import (
    BackpackAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BackpackExchange(ExchangePyBase):
    """
    Backpack Exchange connector for spot trading.

    Implements the ExchangePyBase interface for connecting to Backpack Exchange.
    """

    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    web_utils = web_utils

    def __init__(
        self,
        backpack_api_key: str,
        backpack_api_secret: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        """
        Initialize the Backpack Exchange connector.

        Args:
            backpack_api_key: API public key (base64 encoded ED25519 public key)
            backpack_api_secret: API secret key (base64 or hex encoded ED25519 private key)
            trading_pairs: List of trading pairs to trade
            trading_required: Whether trading functionality is required
            domain: Exchange domain (mainnet or testnet)
        """
        self._backpack_api_key = backpack_api_key
        self._backpack_api_secret = backpack_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trade_history_timestamp = None
        self._last_trades_poll_timestamp = 1.0
        self._client_order_id_nonce_provider = NonceCreator.for_microseconds()

        super().__init__()
        self.real_time_balance_update = False

    @property
    def name(self) -> str:
        """Return the exchange name."""
        return self._domain

    @property
    def authenticator(self) -> Optional[BackpackAuth]:
        """Return the authenticator for API calls."""
        if self._trading_required:
            return BackpackAuth(
                api_key=self._backpack_api_key,
                api_secret=self._backpack_api_secret,
            )
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        """Return the rate limit rules for the exchange."""
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        """Return the domain."""
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        """Return the maximum client order ID length."""
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        """Return the client order ID prefix."""
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        """Return the path for trading rules request."""
        return CONSTANTS.MARKETS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        """Return the path for trading pairs request."""
        return CONSTANTS.MARKETS_URL

    @property
    def check_network_request_path(self) -> str:
        """Return the path for network check request."""
        return CONSTANTS.STATUS_URL

    @property
    def trading_pairs(self):
        """Return the trading pairs."""
        return self._trading_pairs

    def _new_numeric_client_order_id(self) -> str:
        client_id = get_new_numeric_client_order_id(
            nonce_creator=self._client_order_id_nonce_provider,
            max_id_bit_count=32,
        )
        return str(client_id)

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = self._new_numeric_client_order_id()
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
        order_id = self._new_numeric_client_order_id()
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

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        """Return whether cancel requests are synchronous."""
        return True

    @property
    def is_trading_required(self) -> bool:
        """Return whether trading is required."""
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        """Return supported order types."""
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        """Check if the exception is related to time synchronization."""
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        """Create the web assistants factory."""
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        """Create the order book data source."""
        return BackpackAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        """Create the user stream data source."""
        return BackpackAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _make_network_check_request(self):
        """Make a network check request."""
        await self._api_get(path_url=self.check_network_request_path)

    async def _make_trading_rules_request(self) -> Any:
        """Make a request for trading rules."""
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        """Make a request for trading pairs."""
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path)
        return exchange_info

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        """Check if the order was not found during status update."""
        message = str(status_update_exception)
        return (
            CONSTANTS.ORDER_NOT_EXIST_MESSAGE in message
            or CONSTANTS.UNKNOWN_ORDER_MESSAGE in message
        )

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        """Check if the order was not found during cancellation."""
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    async def _status_polling_loop_fetch_updates(self):
        """Fetch updates in the status polling loop."""
        await safe_gather(
            self._update_order_status(),
            self._update_balances(),
        )

    async def _update_trading_rules(self):
        """Update trading rules from the exchange."""
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _initialize_trading_pair_symbol_map(self):
        """Initialize the trading pair symbol map."""
        try:
            exchange_info = await self._api_get(path_url=self.trading_pairs_request_path)
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        """
        Initialize trading pair symbols from exchange info.

        Backpack returns a list of markets:
        [
            {
                "symbol": "BTC_USDC",
                "baseSymbol": "BTC",
                "quoteSymbol": "USDC",
                ...
            },
            ...
        ]
        """
        mapping = bidict()

        for market in exchange_info:
            symbol = market.get("symbol", "")
            base_symbol = market.get("baseSymbol", "")
            quote_symbol = market.get("quoteSymbol", "")

            # Skip perpetual and derivative markets for spot connector
            if "_PERP" in symbol or "_IPERP" in symbol or "_DATED" in symbol:
                continue

            if base_symbol and quote_symbol:
                trading_pair = combine_to_hb_trading_pair(base_symbol, quote_symbol)
                mapping[symbol] = trading_pair

        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, exchange_info: List[Dict[str, Any]]) -> List[TradingRule]:
        """
        Format trading rules from exchange info.

        Args:
            exchange_info: List of market info from /api/v1/markets

        Returns:
            List of TradingRule objects
        """
        trading_rules = []

        for market in exchange_info:
            try:
                symbol = market.get("symbol", "")
                base_symbol = market.get("baseSymbol", "")
                quote_symbol = market.get("quoteSymbol", "")

                # Skip perpetual and derivative markets
                if "_PERP" in symbol or "_IPERP" in symbol or "_DATED" in symbol:
                    continue

                if not base_symbol or not quote_symbol:
                    self.logger().error(f"Error parsing trading rule for {market}. Skipping.")
                    continue

                trading_pair = combine_to_hb_trading_pair(base_symbol, quote_symbol)

                # Parse trading rule parameters (Backpack exposes filters nested under "filters")
                filters = market.get("filters", {}) if isinstance(market.get("filters"), dict) else {}
                price_filter = filters.get("price", {}) if isinstance(filters.get("price"), dict) else {}
                quantity_filter = filters.get("quantity", {}) if isinstance(filters.get("quantity"), dict) else {}

                min_order_size = Decimal(str(quantity_filter.get("minQuantity", market.get("minOrderSize", "0.00001"))))
                tick_size = Decimal(str(price_filter.get("tickSize", market.get("tickSize", "0.01"))))
                step_size = Decimal(str(quantity_filter.get("stepSize", market.get("stepSize", "0.00001"))))

                min_notional = Decimal(str(market.get("minNotional", price_filter.get("minNotional", "0"))))
                if min_notional == 0:
                    min_price = Decimal(str(price_filter.get("minPrice", "0")))
                    if min_price > 0 and min_order_size > 0:
                        min_notional = min_price * min_order_size

                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=tick_size,
                        min_base_amount_increment=step_size,
                        min_notional_size=min_notional,
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing trading rule for {market}. Skipping.")

        return trading_rules

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
        """Get the trading fee for an order."""
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _update_trading_fees(self):
        """Update trading fees from the exchange."""
        pass

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
        """
        Place an order on the exchange.

        Args:
            order_id: Client order ID
            trading_pair: Trading pair
            amount: Order amount
            trade_type: BUY or SELL
            order_type: LIMIT, LIMIT_MAKER, or MARKET
            price: Order price

        Returns:
            Tuple of (exchange_order_id, timestamp)
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        # Determine order side
        side = CONSTANTS.ORDER_SIDE_BID if trade_type == TradeType.BUY else CONSTANTS.ORDER_SIDE_ASK

        # Determine order type and time in force
        if order_type == OrderType.LIMIT:
            backpack_order_type = "Limit"
            time_in_force = "GTC"
        elif order_type == OrderType.LIMIT_MAKER:
            backpack_order_type = "Limit"
            time_in_force = "GTC"  # Backpack may support PostOnly
        elif order_type == OrderType.MARKET:
            backpack_order_type = "Market"
            time_in_force = "IOC"
        else:
            backpack_order_type = "Limit"
            time_in_force = "GTC"

        api_params = {
            "symbol": symbol,
            "side": side,
            "orderType": backpack_order_type,
            "quantity": str(amount),
            "clientId": int(order_id),
        }

        # Add price for limit orders
        if order_type != OrderType.MARKET:
            api_params["price"] = str(price)
            api_params["timeInForce"] = time_in_force

        # Post only for limit maker
        if order_type == OrderType.LIMIT_MAKER:
            api_params["postOnly"] = True

        order_result = await self._api_post(
            path_url=CONSTANTS.ORDER_URL,
            data=api_params,
            is_auth_required=True,
        )

        # Parse response
        if "error" in order_result or order_result.get("status") == "error":
            error_msg = order_result.get("error", order_result.get("message", "Unknown error"))
            raise IOError(f"Error submitting order {order_id}: {error_msg}")

        exchange_order_id = str(order_result.get("id", order_result.get("orderId", "")))
        timestamp = self.current_timestamp

        return exchange_order_id, timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancel an order on the exchange.

        Args:
            order_id: Client order ID
            tracked_order: The tracked order to cancel

        Returns:
            True if cancelled successfully
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        api_params = {
            "symbol": symbol,
            "clientId": int(order_id),
        }

        # Backpack expects either clientId or orderId (not both). Use clientId for consistency.

        # Backpack expects a JSON payload for cancel requests
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_URL,
            data=api_params,
            is_auth_required=True,
        )

        if "error" in cancel_result:
            error_msg = cancel_result.get("error", "Unknown error")
            raise IOError(f"Error cancelling order {order_id}: {error_msg}")

        return True

    async def _update_balances(self):
        """Update account balances from the exchange."""
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.BALANCE_URL,
            is_auth_required=True,
        )

        # Backpack returns balances as a dict: {"BTC": {"available": "1.0", "locked": "0.5"}, ...}
        if isinstance(account_info, dict):
            for asset_name, balance_data in account_info.items():
                if isinstance(balance_data, dict):
                    available = Decimal(str(balance_data.get("available", "0")))
                    locked = Decimal(str(balance_data.get("locked", "0")))
                    total = available + locked

                    self._account_available_balances[asset_name] = available
                    self._account_balances[asset_name] = total
                    remote_asset_names.add(asset_name)

        # Remove assets no longer in the account
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        """Iterate over user stream events."""
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Backpack. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listen for user stream events.

        Processes order updates and fill events from the WebSocket.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    raise ValueError("Invalid user stream event format")

                stream = event_message.get("stream", "")
                data = event_message.get("data", event_message)
                if not isinstance(data, dict):
                    continue

                event_type = data.get("e", "")

                # Handle order updates and fills
                if event_type == "orderFill":
                    await self._process_trade_message(data)
                    await self._process_order_update(data)
                elif event_type.startswith("order") or stream.startswith("account.orderUpdate"):
                    await self._process_order_update(data)
                elif stream.startswith("account.fill") or "fill" in stream:
                    await self._process_trade_message(data)

                # Handle position updates (for future perpetual support)
                elif stream.startswith("account.position"):
                    pass  # Handled in perpetual connector

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.",
                    exc_info=True,
                )
                await self._sleep(5.0)

    async def _process_order_update(self, order_data: Dict[str, Any]):
        """
        Process an order update from the WebSocket.

        Args:
            order_data: Order update data
        """
        client_order_id = str(order_data.get("clientId", order_data.get("clientOrderId", order_data.get("c", ""))))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if not tracked_order:
            exchange_order_id = str(order_data.get("id", order_data.get("orderId", order_data.get("i", ""))))
            if exchange_order_id:
                for order in self._order_tracker.all_updatable_orders.values():
                    if order.exchange_order_id == exchange_order_id:
                        tracked_order = order
                        client_order_id = order.client_order_id
                        break
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        # Map Backpack order status to Hummingbot OrderState
        status = order_data.get("status", order_data.get("orderStatus", order_data.get("X", "")))
        new_state = CONSTANTS.ORDER_STATE.get(status)
        if new_state is None and order_data.get("e") == "orderFill":
            new_state = OrderState.PARTIALLY_FILLED

        if new_state is None:
            self.logger().warning(f"Unknown order status: {status}")
            return

        exchange_order_id = str(order_data.get("id", order_data.get("orderId", order_data.get("i", ""))))
        update_timestamp = order_data.get("updatedAt", order_data.get("timestamp", order_data.get("T", order_data.get("E", 0))))
        update_timestamp = self._safe_timestamp_to_seconds(update_timestamp)

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _process_trade_message(self, trade_data: Dict[str, Any]):
        """
        Process a trade/fill message from the WebSocket.

        Args:
            trade_data: Trade data
        """
        client_order_id = str(trade_data.get("clientId", trade_data.get("clientOrderId", trade_data.get("c", ""))))
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if tracked_order is None:
            exchange_order_id = str(trade_data.get("orderId", trade_data.get("id", trade_data.get("i", ""))))
            if exchange_order_id:
                for order in self._order_tracker.all_fillable_orders.values():
                    if order.exchange_order_id == exchange_order_id:
                        tracked_order = order
                        client_order_id = order.client_order_id
                        break
        if tracked_order is None:
            return

        # Parse trade details
        fee_asset = trade_data.get("feeSymbol", trade_data.get("feeCurrency", trade_data.get("N", tracked_order.quote_asset)))
        fee_amount = Decimal(str(trade_data.get("fee", trade_data.get("n", "0"))))

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=tracked_order.trade_type,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
        )

        fill_price = Decimal(str(trade_data.get("price", trade_data.get("px", trade_data.get("L", "0")))))
        fill_amount = Decimal(str(trade_data.get("quantity", trade_data.get("sz", trade_data.get("l", "0")))))
        is_maker = trade_data.get("m")

        trade_update = TradeUpdate(
            trade_id=str(trade_data.get("tradeId", trade_data.get("id", trade_data.get("t", "")))),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade_data.get("orderId", trade_data.get("i", ""))),
            trading_pair=tracked_order.trading_pair,
            fee=fee,
            fill_base_amount=fill_amount,
            fill_quote_amount=fill_price * fill_amount,
            fill_price=fill_price,
            fill_timestamp=self._safe_timestamp_to_seconds(
                trade_data.get("timestamp", trade_data.get("T", trade_data.get("E", 0)))
            ),
            is_taker=(not is_maker) if is_maker is not None else True,
        )
        self._order_tracker.process_trade_update(trade_update)

    @staticmethod
    def _safe_timestamp_to_seconds(timestamp: Any) -> float:
        try:
            ts = float(timestamp)
        except Exception:
            return 0
        if ts > 1e14:  # microseconds
            return ts / 1e6
        if ts > 1e12:  # milliseconds
            return ts / 1000.0
        return ts

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Request order status from the exchange.

        Args:
            tracked_order: The tracked order to get status for

        Returns:
            OrderUpdate with current order status
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        params = {
            "symbol": symbol,
        }

        if tracked_order.exchange_order_id:
            params["orderId"] = tracked_order.exchange_order_id
        else:
            params["clientId"] = int(tracked_order.client_order_id)

        order_info = await self._api_get(
            path_url=CONSTANTS.ORDER_URL,
            params=params,
            is_auth_required=True,
        )
        if isinstance(order_info, dict) and "error" in order_info:
            raise IOError(order_info.get("error", "Unknown error"))

        status = order_info.get("status", order_info.get("orderStatus", ""))
        new_state = CONSTANTS.ORDER_STATE.get(status)

        update_timestamp = float(order_info.get("updatedAt", order_info.get("createdAt", 0)))
        if update_timestamp > 1e12:
            update_timestamp = update_timestamp / 1000.0

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_info.get("id", order_info.get("orderId", ""))),
        )
        return order_update

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        Get the last traded price for a trading pair.

        Args:
            trading_pair: The trading pair

        Returns:
            Last traded price as float
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        ticker_data = await self._api_get(
            path_url=CONSTANTS.TICKER_URL,
            params={"symbol": symbol},
        )

        price = float(ticker_data.get("lastPrice", ticker_data.get("lastPx", 0)))
        return price

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        """Get prices for all trading pairs."""
        result = []

        tickers = await self._api_get(path_url=CONSTANTS.TICKERS_URL)

        for ticker in tickers:
            symbol = ticker.get("symbol", "")
            price = ticker.get("lastPrice", ticker.get("lastPx", "0"))
            result.append({"symbol": symbol, "price": str(price)})

        return result

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Get all trade updates for an order.

        Args:
            order: The order to get trades for

        Returns:
            List of TradeUpdate objects
        """
        trade_updates = []

        if order.exchange_order_id is None:
            return trade_updates

        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)

        try:
            fills = await self._api_get(
                path_url=CONSTANTS.FILLS_URL,
                params={
                    "symbol": symbol,
                    "orderId": order.exchange_order_id,
                },
                is_auth_required=True,
            )

            for fill in fills:
                fee_asset = fill.get("feeSymbol", fill.get("feeCurrency", ""))
                fee_amount = Decimal(str(fill.get("fee", "0")))

                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=fee_asset,
                    flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
                )

                fill_price = Decimal(str(fill.get("price", "0")))
                fill_amount = Decimal(str(fill.get("quantity", "0")))

                trade_update = TradeUpdate(
                    trade_id=str(fill.get("tradeId", fill.get("id", ""))),
                    client_order_id=order.client_order_id,
                    exchange_order_id=str(order.exchange_order_id),
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=fill_amount,
                    fill_quote_amount=fill_price * fill_amount,
                    fill_price=fill_price,
                    fill_timestamp=float(fill.get("timestamp", 0)) / 1000.0,
                )
                trade_updates.append(trade_update)

        except Exception as e:
            self.logger().warning(f"Error fetching fills for order {order.client_order_id}: {e}")

        return trade_updates
