import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.lmex import lmex_constants as CONSTANTS
from hummingbot.connector.exchange.lmex import lmex_web_utils as web_utils
from hummingbot.connector.exchange.lmex.lmex_api_order_book_data_source import LmexAPIOrderBookDataSource
from hummingbot.connector.exchange.lmex.lmex_api_user_stream_data_source import (
    EVENT_TYPE_BALANCE_UPDATE,
    EVENT_TYPE_ORDER_UPDATE,
    EVENT_TYPE_TRADE_UPDATE,
    LmexAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.lmex.lmex_auth import LmexAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


# Map LMEX numeric status codes to Hummingbot OrderState
_LMEX_STATUS_TO_ORDER_STATE: Dict[int, OrderState] = {
    CONSTANTS.ORDER_STATUS_INSERTED: OrderState.OPEN,
    CONSTANTS.ORDER_STATUS_FULLY_TRANSACTED: OrderState.FILLED,
    CONSTANTS.ORDER_STATUS_PARTIALLY_TRANSACTED: OrderState.PARTIALLY_FILLED,
    CONSTANTS.ORDER_STATUS_CANCELLED: OrderState.CANCELED,
    CONSTANTS.ORDER_STATUS_REFUNDED: OrderState.CANCELED,
    CONSTANTS.ORDER_STATUS_INSUFFICIENT_BALANCE: OrderState.FAILED,
    CONSTANTS.ORDER_STATUS_TRIGGER_INSERTED: OrderState.OPEN,
    CONSTANTS.ORDER_STATUS_TRIGGER_ACTIVATED: OrderState.OPEN,
    CONSTANTS.ORDER_STATUS_REJECTED: OrderState.FAILED,
    CONSTANTS.ORDER_STATUS_NOT_FOUND: OrderState.FAILED,
    CONSTANTS.ORDER_STATUS_REQUEST_FAILED: OrderState.FAILED,
    CONSTANTS.ORDER_STATUS_ACTIVE: OrderState.OPEN,
    CONSTANTS.ORDER_STATUS_PROCESSING: OrderState.OPEN,
    CONSTANTS.ORDER_STATUS_INACTIVE: OrderState.OPEN,
}


class LmexExchange(ExchangePyBase):
    """
    LMEX spot exchange connector for Hummingbot.

    LMEX is a BTSE-family exchange.  The spot API lives at https://api.lmex.io/spot
    and uses HMAC-SHA384 authentication.  Symbol format matches Hummingbot (BTC-USD),
    so no conversion is required.

    WebSocket streaming is not yet implemented (LMEX WS docs pending); the connector
    operates in REST-polling mode for both the order book and user data.
    """

    DEFAULT_DOMAIN = CONSTANTS.DEFAULT_DOMAIN

    # REST polling tick limit: force a poll every 30 s even if the user stream is alive.
    TICK_INTERVAL_LIMIT = 30.0

    web_utils = web_utils

    def __init__(
        self,
        lmex_api_key: str,
        lmex_secret_key: str,
        domain: str = DEFAULT_DOMAIN,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        """
        :param lmex_api_key: LMEX API key (request-api header).
        :param lmex_secret_key: LMEX API secret (used for HMAC-SHA384 signature).
        :param domain: '' for production, 'sandbox' for test environment.
        :param trading_pairs: Market trading pairs to track.
        :param trading_required: Whether real trading is enabled.
        """
        self._lmex_api_key = lmex_api_key
        self._lmex_secret_key = lmex_secret_key
        self._domain = domain
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        super().__init__()

    # ------------------------------------------------------------------
    # ExchangePyBase abstract properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "lmex"

    @property
    def authenticator(self) -> LmexAuth:
        return LmexAuth(
            api_key=self._lmex_api_key,
            secret_key=self._lmex_secret_key,
            time_provider=self._time_synchronizer,
        )

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

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
        return CONSTANTS.SYMBOL_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.SYMBOL_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.NETWORK_CHECK_PATH_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    # ------------------------------------------------------------------
    # Order type support
    # ------------------------------------------------------------------

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    # ------------------------------------------------------------------
    # Exception classification
    # ------------------------------------------------------------------

    def _is_request_exception_related_to_time_synchronizer(
        self, request_exception: Exception
    ) -> bool:
        # LMEX uses a nonce (not a strict timestamp window), so time-sync errors are not expected.
        return False

    def _is_order_not_found_during_status_update_error(
        self, status_update_exception: Exception
    ) -> bool:
        return str(CONSTANTS.ORDER_STATUS_NOT_FOUND) in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(
        self, cancelation_exception: Exception
    ) -> bool:
        return str(CONSTANTS.ORDER_STATUS_NOT_FOUND) in str(cancelation_exception)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LmexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LmexAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    # ------------------------------------------------------------------
    # Trading rules
    # ------------------------------------------------------------------

    async def _format_trading_rules(
        self, raw_trading_pair_info: Any
    ) -> List[TradingRule]:
        """
        Converts the market_summary response into TradingRule objects.

        LMEX market_summary fields used:
          symbol, active, minOrderSize, maxOrderSize, minPriceIncrement, minSizeIncrement
        The response may be a single object or a list depending on whether a symbol
        filter is applied.  We normalise to a list here.
        """
        result: List[TradingRule] = []

        if isinstance(raw_trading_pair_info, dict):
            raw_trading_pair_info = [raw_trading_pair_info]

        for rule in raw_trading_pair_info:
            try:
                if not web_utils.is_exchange_information_valid(rule):
                    continue

                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=rule["symbol"]
                )

                min_order_size = Decimal(str(rule.get("minOrderSize", "0")))
                max_order_size = Decimal(str(rule.get("maxOrderSize", "0")))
                min_price_increment = Decimal(str(rule.get("minPriceIncrement", "0")))
                min_base_amount_increment = Decimal(str(rule.get("minSizeIncrement", "0")))

                result.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_order_size,
                        max_order_size=max_order_size if max_order_size > 0 else None,
                        min_price_increment=min_price_increment,
                        min_base_amount_increment=min_base_amount_increment,
                    )
                )
            except Exception:
                self.logger().error(
                    f"Error parsing trading rule {rule}. Skipping.", exc_info=True
                )

        return result

    # ------------------------------------------------------------------
    # Order placement and cancellation
    # ------------------------------------------------------------------

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
        Places an order on LMEX.

        POST /api/v3.2/order
        Returns: (exchange_order_id, timestamp)
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        side = trade_type.name.upper()  # "BUY" or "SELL"

        if order_type is OrderType.MARKET:
            order_type_str = "MARKET"
            tif = "IOC"
            post_only = False
        elif order_type is OrderType.LIMIT_MAKER:
            order_type_str = "LIMIT"
            tif = "GTC"
            post_only = True
        else:
            # LIMIT
            order_type_str = "LIMIT"
            tif = "GTC"
            post_only = False

        data: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type_str,
            "size": f"{amount:f}",
            "clOrderID": order_id,
            "time_in_force": tif,
            "postOnly": post_only,
        }

        if order_type.is_limit_type():
            data["price"] = f"{price:f}"

        order_result = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_PATH_URL,
        )

        # LMEX returns a list; take the first entry
        if isinstance(order_result, list):
            order_result = order_result[0]

        status_code = order_result.get("status")
        if status_code in CONSTANTS.FAILED_STATUS_CODES:
            raise IOError(
                f"Order rejected by LMEX (status {status_code}): {order_result}"
            )

        exchange_order_id = str(order_result.get("orderID", ""))
        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancels an open order on LMEX.

        DELETE /api/v3.2/order?symbol=<symbol>&orderID=<id>
        Returns True if the cancel was acknowledged.
        """
        exchange_order_id = await tracked_order.get_exchange_order_id()
        symbol = await self.exchange_symbol_associated_to_pair(
            trading_pair=tracked_order.trading_pair
        )

        result = await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params={"symbol": symbol, "orderID": exchange_order_id},
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_PATH_URL,
        )

        if isinstance(result, list):
            result = result[0]

        status_code = result.get("status")
        return status_code in CONSTANTS.CANCELLED_STATUS_CODES

    # ------------------------------------------------------------------
    # Balance updates
    # ------------------------------------------------------------------

    async def _update_balances(self):
        """
        Fetches wallet balances from GET /api/v3.2/user/wallet.
        Response: [{currency, total, available}, ...]
        """
        wallet: List[Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.USER_WALLET_PATH_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.USER_WALLET_PATH_URL,
        )
        self._process_balance_message(wallet)

    def _process_balance_message(self, wallet: List[Dict[str, Any]]):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        for entry in wallet:
            asset = entry["currency"]
            self._account_balances[asset] = Decimal(str(entry["total"]))
            self._account_available_balances[asset] = Decimal(str(entry["available"]))
            remote_asset_names.add(asset)

        # Remove any assets that are no longer reported
        for asset in local_asset_names - remote_asset_names:
            del self._account_balances[asset]
            del self._account_available_balances[asset]

    # ------------------------------------------------------------------
    # Order status
    # ------------------------------------------------------------------

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Queries GET /api/v3.2/order?orderID=<id> for the current order state.
        """
        try:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            order_data = await self._api_get(
                path_url=CONSTANTS.ORDER_PATH_URL,
                params={"orderID": exchange_order_id},
                is_auth_required=True,
                limit_id=CONSTANTS.ORDER_PATH_URL,
            )
            if isinstance(order_data, list):
                order_data = order_data[0]

            return self._create_order_update_from_order_data(order_data, tracked_order)

        except asyncio.TimeoutError:
            raise IOError(
                f"Skipped order status update for {tracked_order.client_order_id} "
                "- waiting for exchange order id."
            )

    def _create_order_update_from_order_data(
        self, order_data: Dict[str, Any], order: InFlightOrder
    ) -> OrderUpdate:
        status_code = order_data.get("status")
        new_state = _LMEX_STATUS_TO_ORDER_STATE.get(status_code, order.current_state)

        # clOrderID is echoed back by LMEX and matches our client order id
        client_order_id = order_data.get("clOrderID", "") or order.client_order_id

        timestamp = order_data.get("timestamp", self.current_timestamp)
        if isinstance(timestamp, int) and timestamp > 1e10:
            # millisecond epoch — convert to seconds
            timestamp = timestamp / 1e3

        return OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=float(timestamp),
            new_state=new_state,
            client_order_id=client_order_id,
            exchange_order_id=str(order_data.get("orderID", order.exchange_order_id or "")),
        )

    # ------------------------------------------------------------------
    # Trade history
    # ------------------------------------------------------------------

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Fetches all fill records for a specific order via
        GET /api/v3.2/user/trade_history?orderID=<id>&symbol=<symbol>
        """
        trade_updates: List[TradeUpdate] = []
        try:
            exchange_order_id = await order.get_exchange_order_id()
            symbol = await self.exchange_symbol_associated_to_pair(
                trading_pair=order.trading_pair
            )
            fills = await self._api_get(
                path_url=CONSTANTS.TRADE_HISTORY_PATH_URL,
                params={"orderID": exchange_order_id, "symbol": symbol},
                is_auth_required=True,
                limit_id=CONSTANTS.TRADE_HISTORY_PATH_URL,
            )
            if not isinstance(fills, list):
                fills = [fills] if fills else []

            for fill in fills:
                trade_updates.append(
                    self._create_trade_update_from_fill(fill, order)
                )

        except asyncio.TimeoutError:
            raise IOError(
                f"Skipped trade updates for {order.client_order_id} "
                "- waiting for exchange order id."
            )

        return trade_updates

    def _create_trade_update_from_fill(
        self, fill: Dict[str, Any], order: InFlightOrder
    ) -> TradeUpdate:
        """
        LMEX trade history entry:
        {tradeId, orderId, side, price, size, filledSize, feeCurrency, feeAmount, timestamp}
        """
        fee_currency = fill.get("feeCurrency", "")
        fee_amount = Decimal(str(fill.get("feeAmount", "0")))

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=fee_currency,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_currency)],
        )

        fill_price = Decimal(str(fill.get("price", "0")))
        fill_size = Decimal(str(fill.get("filledSize", fill.get("size", "0"))))

        timestamp = fill.get("timestamp", self.current_timestamp)
        if isinstance(timestamp, int) and timestamp > 1e10:
            timestamp = timestamp / 1e3

        return TradeUpdate(
            trade_id=str(fill.get("tradeId", "")),
            client_order_id=order.client_order_id,
            exchange_order_id=str(fill.get("orderId", order.exchange_order_id or "")),
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=fill_size,
            fill_quote_amount=fill_size * fill_price,
            fill_price=fill_price,
            fill_timestamp=float(timestamp),
        )

    # ------------------------------------------------------------------
    # Fee estimation
    # ------------------------------------------------------------------

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
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _update_trading_fees(self):
        pass

    # ------------------------------------------------------------------
    # User stream event listener
    # ------------------------------------------------------------------

    async def _user_stream_event_listener(self):
        """
        Processes synthetic events emitted by LmexAPIUserStreamDataSource.
        Each event is a dict: {"type": EVENT_TYPE_*, "data": <payload>}
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("type")
                data = event_message.get("data")

                if event_type == EVENT_TYPE_ORDER_UPDATE:
                    self._process_order_message(data)
                elif event_type == EVENT_TYPE_TRADE_UPDATE:
                    self._process_trade_message(data)
                elif event_type == EVENT_TYPE_BALANCE_UPDATE:
                    self._process_balance_message(data)
                else:
                    self.logger().debug(
                        f"Unrecognised user stream event type: {event_type}"
                    )

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Routes a raw LMEX order dict to the order tracker.
        LMEX open-orders response: {orderID, clOrderID, status, ...}
        """
        client_order_id = str(order_msg.get("clOrderID", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(
                f"Ignoring order update for unknown client id: {client_order_id!r}"
            )
            return

        order_update = self._create_order_update_from_order_data(order_msg, tracked_order)
        self._order_tracker.process_order_update(order_update=order_update)

    def _process_trade_message(self, trade: Dict[str, Any]):
        """
        Routes a raw LMEX trade-history entry to the order tracker.
        LMEX trade entry: {tradeId, orderId, side, price, size, filledSize,
                           feeCurrency, feeAmount, timestamp}
        Matches via the exchange order id.
        """
        exchange_order_id = str(trade.get("orderId", ""))
        tracked_order = None
        for order in self._order_tracker.all_fillable_orders.values():
            if order.exchange_order_id == exchange_order_id:
                tracked_order = order
                break

        if tracked_order is None:
            self.logger().debug(
                f"Ignoring trade for unknown exchange order id: {exchange_order_id!r}"
            )
            return

        trade_update = self._create_trade_update_from_fill(trade, tracked_order)
        self._order_tracker.process_trade_update(trade_update)

    # ------------------------------------------------------------------
    # Trading pair symbol mapping
    # ------------------------------------------------------------------

    def _initialize_trading_pair_symbols_from_exchange_info(
        self, exchange_info: Any
    ):
        """
        Builds the bidict mapping exchange symbol → Hummingbot trading pair.

        LMEX spot uses dash-separated symbols (BTC-USD) that already match
        Hummingbot's format, so the mapping is a direct 1:1 pass-through.
        """
        mapping = bidict()

        if isinstance(exchange_info, dict):
            exchange_info = [exchange_info]

        for market in filter(web_utils.is_exchange_information_valid, exchange_info):
            symbol = market.get("symbol", "")
            if not symbol:
                continue
            # LMEX symbol is already in Hummingbot format (e.g. BTC-USD).
            mapping[symbol] = symbol

        self._set_trading_pair_symbol_map(mapping)

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str) -> str:
        """LMEX spot symbols are identical to Hummingbot trading pairs."""
        symbol_map = await self.trading_pair_symbol_map()
        return symbol_map.get(symbol, symbol)

    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        """LMEX spot trading pairs are identical to exchange symbols."""
        symbol_map = await self.trading_pair_symbol_map()
        inverse = {v: k for k, v in symbol_map.items()}
        return inverse.get(trading_pair, trading_pair)

    # ------------------------------------------------------------------
    # Last traded price
    # ------------------------------------------------------------------

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        resp = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.SYMBOL_PATH_URL,
            params={"symbol": symbol},
        )
        # market_summary returns a single object or list; normalise
        if isinstance(resp, list):
            resp = resp[0]
        return float(resp.get("last", 0))
