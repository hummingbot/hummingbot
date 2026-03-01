import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Set, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GrvtPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_order_sign_utils import build_order_signature
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_user_stream_data_source import (
    GrvtPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class GrvtPerpetualDerivative(PerpetualDerivativePyBase):
    """
    GRVT Perpetual connector implementing the Hummingbot v2.1+ PerpetualDerivativePyBase interface.

    Authentication: API key session cookie (lazily obtained via GrvtPerpetualAuth).
    Order signing: EIP-712 typed-data with Ethereum private key via grvt_perpetual_order_sign_utils.
    All amounts are denominated in USDC / USDT (settle currency).
    GRVT only supports ONEWAY position mode.
    """

    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            grvt_perpetual_api_key: Optional[str] = None,
            grvt_perpetual_sub_account_id: Optional[str] = None,
            grvt_perpetual_private_key: Optional[str] = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.grvt_perpetual_api_key = grvt_perpetual_api_key
        self.grvt_perpetual_sub_account_id = grvt_perpetual_sub_account_id
        self.grvt_perpetual_private_key = grvt_perpetual_private_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self._symbol_map_fallback_warned: Set[str] = set()
        self._instrument_info_by_symbol: Dict[str, Dict[str, Any]] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> GrvtPerpetualAuth:
        if self.grvt_perpetual_api_key is None or self.grvt_perpetual_sub_account_id is None:
            raise ValueError("API key and sub-account ID are required for authentication")
        return GrvtPerpetualAuth(
            self.grvt_perpetual_api_key,
            self.grvt_perpetual_sub_account_id,
            self._time_synchronizer,
            self._domain,
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.ALL_INSTRUMENTS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.ALL_INSTRUMENTS_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.ALL_INSTRUMENTS_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs or []

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 600

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self):
        # GRVT only supports one-way mode for perpetuals
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    # ------------------------------------------------------------------
    # Error classification helpers
    # ------------------------------------------------------------------

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return (
            str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(status_update_exception)
            and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)
        )

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return (
            str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(cancelation_exception)
            and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)
        )

    # ------------------------------------------------------------------
    # Exchange info helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_result_list(response: Any) -> List[Dict[str, Any]]:
        """Robustly extract a list of instrument dicts from various GRVT response shapes."""
        if isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]

        if not isinstance(response, dict):
            return []

        for key in ("result", "results", "data", "instruments", "items"):
            value = response.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                if "instrument" in value:
                    return [value]
                for nested_key in ("result", "results", "data", "instruments", "items"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        return [item for item in nested_value if isinstance(item, dict)]
                    if isinstance(nested_value, dict) and "instrument" in nested_value:
                        return [nested_value]

        if "instrument" in response:
            return [response]

        return []

    async def exchange_symbol_for_trading_pair(self, trading_pair: str) -> str:
        """Return the GRVT instrument string for a hummingbot trading pair."""
        try:
            return await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        except KeyError:
            fallback_symbol = web_utils.convert_to_exchange_trading_pair(trading_pair)
            if trading_pair not in self._symbol_map_fallback_warned:
                self.logger().warning(
                    f"Trading pair {trading_pair} not found in symbol map. "
                    f"Using fallback symbol {fallback_symbol}."
                )
                self._symbol_map_fallback_warned.add(trading_pair)
            return fallback_symbol

    async def _instrument_info_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch and cache instrument metadata required for EIP-712 order signing."""
        instrument_info = self._instrument_info_by_symbol.get(symbol)
        if instrument_info is not None:
            return instrument_info

        response = await self._api_post(
            path_url=CONSTANTS.GET_INSTRUMENT_URL,
            data={"instrument": symbol},
            is_auth_required=False,
        )
        instruments = self._extract_result_list(response)
        if len(instruments) == 0:
            return None

        for instrument_data in instruments:
            if instrument_data.get("instrument") == symbol:
                self._instrument_info_by_symbol[symbol] = instrument_data
                return instrument_data

        # Fall back to first result if exact match not found
        instrument_data = instruments[0]
        self._instrument_info_by_symbol[symbol] = instrument_data
        return instrument_data

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            domain=self._domain,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> GrvtPerpetualAPIOrderBookDataSource:
        return GrvtPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs or [],
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GrvtPerpetualUserStreamDataSource(
            auth=self._auth,  # type: ignore[arg-type]
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    # ------------------------------------------------------------------
    # Fee calculation
    # ------------------------------------------------------------------

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or False
        fee = build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )
        return fee

    async def _update_trading_fees(self):
        """Update fees from exchange. GRVT fees are static; nothing to fetch."""

    # ------------------------------------------------------------------
    # Trading rules / pairs
    # ------------------------------------------------------------------

    async def _make_trading_rules_request(self) -> Any:
        """GRVT uses POST for all endpoints."""
        exchange_info = await self._api_post(
            path_url=self.trading_rules_request_path,
            data={},
            is_auth_required=False,
        )
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        """GRVT uses POST for all endpoints."""
        exchange_info = await self._api_post(
            path_url=self.trading_pairs_request_path,
            data={},
            is_auth_required=False,
        )
        return exchange_info

    async def _make_network_check_request(self):
        """GRVT uses POST for all endpoints."""
        await self._api_post(
            path_url=self.check_network_request_path,
            data={},
            is_auth_required=False,
        )

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_fills_from_trades(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {
            "sub_account_id": self.grvt_perpetual_sub_account_id,
            "client_order_id": order_id,
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=api_params,
            is_auth_required=True,
        )

        if cancel_result.get("code"):
            error_code = cancel_result.get("code")
            error_msg = cancel_result.get("message", "")
            if error_code == CONSTANTS.UNKNOWN_ORDER_ERROR_CODE:
                self.logger().debug(
                    f"The order {order_id} does not exist on GRVT. No cancellation needed."
                )
                await self._order_tracker.process_order_not_found(order_id)
                raise IOError(f"{error_code} - {error_msg}")

        return True

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
        amount_str = f"{amount:f}"
        price_str = f"{price:f}" if price.is_finite() else "0"
        symbol = await self.exchange_symbol_for_trading_pair(trading_pair=trading_pair)

        is_buying_asset = trade_type is TradeType.BUY
        is_market = order_type is OrderType.MARKET
        time_in_force = CONSTANTS.TIME_IN_FORCE_IOC if is_market else CONSTANTS.TIME_IN_FORCE_GTC

        # Build GRVT order legs
        leg: Dict[str, Any] = {
            "instrument": symbol,
            "size": amount_str,
            "is_buying_asset": is_buying_asset,
        }

        if order_type.is_limit_type():
            leg["limit_price"] = price_str

        if self.grvt_perpetual_private_key is None:
            raise ValueError("GRVT private key is required to sign order payloads.")

        instrument_info = await self._instrument_info_for_symbol(symbol=symbol)
        if instrument_info is None:
            raise ValueError(
                f"Could not fetch instrument details required for signing: {symbol}"
            )

        limit_price_for_signing = Decimal("0") if is_market else price
        if limit_price_for_signing.is_nan():
            limit_price_for_signing = Decimal("0")

        if self.grvt_perpetual_sub_account_id is None:
            raise ValueError("GRVT sub-account ID is required to sign order payloads.")

        signature = build_order_signature(
            private_key=self.grvt_perpetual_private_key,
            domain=self._domain,
            sub_account_id=self.grvt_perpetual_sub_account_id,
            instrument_hash=instrument_info.get("instrument_hash"),
            base_decimals=instrument_info.get("base_decimals"),
            is_market=is_market,
            time_in_force=time_in_force,
            post_only=order_type == OrderType.LIMIT_MAKER,
            reduce_only=position_action == PositionAction.CLOSE,
            is_buying_contract=is_buying_asset,
            size=amount,
            limit_price=limit_price_for_signing,
        )

        order_data = {
            "order": {
                "sub_account_id": self.grvt_perpetual_sub_account_id,
                "is_market": is_market,
                "time_in_force": time_in_force,
                "post_only": order_type == OrderType.LIMIT_MAKER,
                "reduce_only": position_action == PositionAction.CLOSE,
                "legs": [leg],
                "signature": signature,
                "metadata": {
                    "client_order_id": order_id,
                },
            }
        }

        try:
            order_result = await self._api_post(
                path_url=CONSTANTS.CREATE_ORDER_URL,
                data=order_data,
                is_auth_required=True,
            )

            result_order = order_result.get("result", order_result)
            o_id = str(result_order.get("order_id", ""))
            create_time = result_order.get("metadata", {}).get(
                "create_time", str(int(time.time() * 1e9))
            )
            transact_time = int(create_time) / 1e9
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = "503" in error_description
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = time.time()
            else:
                raise
        return o_id, transact_time

    # ------------------------------------------------------------------
    # Order / trade status
    # ------------------------------------------------------------------

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            exchange_order_id = await order.get_exchange_order_id()

            all_fills_response = await self._api_post(
                path_url=CONSTANTS.FILL_HISTORY_URL,
                data={
                    "sub_account_id": self.grvt_perpetual_sub_account_id,
                    "kind": ["PERPETUAL"],
                },
                is_auth_required=True,
            )

            fills = self._extract_result_list(all_fills_response)
            for fill in fills:
                fill_order_id = str(fill.get("order_id", ""))
                if fill_order_id == exchange_order_id:
                    fee_amount = Decimal(str(fill.get("fee", "0")))
                    quote_asset = order.quote_asset
                    position_action = (
                        PositionAction.CLOSE
                        if order.position == PositionAction.CLOSE
                        else PositionAction.OPEN
                    )

                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=position_action,
                        percent_token=quote_asset,
                        flat_fees=[TokenAmount(amount=fee_amount, token=quote_asset)],
                    )

                    fill_price = Decimal(str(fill.get("price", "0")))
                    fill_size = Decimal(str(fill.get("size", "0")))

                    trade_update: TradeUpdate = TradeUpdate(
                        trade_id=str(fill.get("trade_id", "")),
                        client_order_id=order.client_order_id,
                        exchange_order_id=fill_order_id,
                        trading_pair=order.trading_pair,
                        fill_timestamp=int(fill.get("event_time", str(int(time.time() * 1e9)))) / 1e9,
                        fill_price=fill_price,
                        fill_base_amount=fill_size,
                        fill_quote_amount=fill_price * fill_size,
                        fee=fee,
                    )
                    trade_updates.append(trade_update)

        except asyncio.TimeoutError as exc:
            raise IOError(
                f"Skipped order update with order fills for {order.client_order_id} "
                "- waiting for exchange order id."
            ) from exc

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        order_update_response = await self._api_post(
            path_url=CONSTANTS.GET_ORDER_URL,
            data={
                "sub_account_id": self.grvt_perpetual_sub_account_id,
                "client_order_id": tracked_order.client_order_id,
            },
            is_auth_required=True,
        )

        if "code" in order_update_response:
            _order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=tracked_order.current_state,
                client_order_id=tracked_order.client_order_id,
            )
            return _order_update

        result_order = order_update_response.get("result", order_update_response)
        order_state_obj = result_order.get("state", {})
        if isinstance(order_state_obj, dict):
            order_status = order_state_obj.get("status", "OPEN")
            update_time = order_state_obj.get("update_time", str(int(time.time() * 1e9)))
        else:
            order_status = str(order_state_obj)
            update_time = str(int(time.time() * 1e9))

        _order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(update_time) / 1e9,
            new_state=CONSTANTS.ORDER_STATE.get(order_status, tracked_order.current_state),
            client_order_id=result_order.get("metadata", {}).get(
                "client_order_id", tracked_order.client_order_id
            ),
            exchange_order_id=str(result_order.get("order_id", "")),
        )
        return _order_update

    # ------------------------------------------------------------------
    # User stream processing
    # ------------------------------------------------------------------

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 second.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from GRVT. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """Process messages from _user_stream_tracker.user_stream queue."""
        async for event_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error in user stream listener loop: {e}", exc_info=True
                )
                await self._sleep(5.0)

    async def _process_user_stream_event(self, event_message: Dict[str, Any]):
        stream = event_message.get("stream", "")
        feed = event_message.get("feed", {})

        if stream == CONSTANTS.WS_ORDER_STREAM:
            await self._process_order_event(feed)
        elif stream == CONSTANTS.WS_FILL_STREAM:
            await self._process_fill_event(feed)
        elif stream == CONSTANTS.WS_POSITION_STREAM:
            await self._process_position_event(feed)

    async def _process_order_event(self, order_data: Dict[str, Any]):
        """Process an order state-change message from the user WebSocket stream."""
        client_order_id = order_data.get("metadata", {}).get("client_order_id")
        if not client_order_id:
            return

        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if tracked_order is None:
            return

        order_state_obj = order_data.get("state", {})
        if isinstance(order_state_obj, dict):
            order_status = order_state_obj.get("status", "OPEN")
            update_time = order_state_obj.get("update_time", str(int(time.time() * 1e9)))
        else:
            order_status = str(order_state_obj)
            update_time = str(int(time.time() * 1e9))

        order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(update_time) / 1e9,
            new_state=CONSTANTS.ORDER_STATE.get(order_status, tracked_order.current_state),
            client_order_id=client_order_id,
            exchange_order_id=str(order_data.get("order_id", "")),
        )
        self._order_tracker.process_order_update(order_update)

    async def _process_fill_event(self, fill_data: Dict[str, Any]):
        """Process a fill/trade event from the user WebSocket stream."""
        order_id = str(fill_data.get("order_id", ""))
        client_order_id = str(fill_data.get("client_order_id", ""))

        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if tracked_order is None:
            # Try to find by exchange order id
            for o in self._order_tracker.all_fillable_orders.values():
                if o.exchange_order_id == order_id:
                    tracked_order = o
                    client_order_id = o.client_order_id
                    break

        if tracked_order is None:
            return

        fill_price = Decimal(str(fill_data.get("price", "0")))
        fill_size = Decimal(str(fill_data.get("size", "0")))
        fee_amount = Decimal(str(fill_data.get("fee", "0")))
        quote_asset = tracked_order.quote_asset

        flat_fees = (
            [] if fee_amount == Decimal("0")
            else [TokenAmount(amount=fee_amount, token=quote_asset)]
        )

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=PositionAction.OPEN,
            percent_token=quote_asset,
            flat_fees=flat_fees,
        )

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=str(fill_data.get("trade_id", "")),
            client_order_id=client_order_id,
            exchange_order_id=order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=int(fill_data.get("event_time", str(int(time.time() * 1e9)))) / 1e9,
            fill_price=fill_price,
            fill_base_amount=fill_size,
            fill_quote_amount=fill_price * fill_size,
            fee=fee,
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _process_position_event(self, position_data: Dict[str, Any]):
        """Process a position update from the user WebSocket stream."""
        instrument = position_data.get("instrument", "")
        try:
            hb_trading_pair = web_utils.convert_from_exchange_trading_pair(instrument)
        except Exception:
            return

        side = PositionSide.BOTH
        amount = Decimal(str(position_data.get("size", "0")))
        entry_price = Decimal(str(position_data.get("entry_price", "0")))
        unrealized_pnl = Decimal(str(position_data.get("unrealized_pnl", "0")))
        leverage = Decimal(str(position_data.get("leverage", "1")))

        pos_key = self._perpetual_trading.position_key(hb_trading_pair, side)

        if amount != Decimal("0"):
            position = Position(
                trading_pair=hb_trading_pair,
                position_side=side,
                unrealized_pnl=unrealized_pnl,
                entry_price=entry_price,
                amount=amount,
                leverage=leverage,
            )
            self._perpetual_trading.set_position(pos_key, position)
        else:
            self._perpetual_trading.remove_position(pos_key)

    # ------------------------------------------------------------------
    # Trading rules formatting
    # ------------------------------------------------------------------

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """Build TradingRule objects from GRVT instrument data."""
        instruments = self._extract_result_list(exchange_info_dict)
        return_val: List[TradingRule] = []
        for rule in instruments:
            try:
                if web_utils.is_exchange_information_valid(rule):
                    instrument = rule.get("instrument", "")
                    trading_pair = web_utils.convert_from_exchange_trading_pair(instrument)

                    tick_size = Decimal(str(rule.get("tick_size", "0.01")))
                    min_size = Decimal(str(rule.get("min_size", "0.001")))
                    size_increment = Decimal(str(rule.get("size_increment", str(min_size))))
                    min_notional = Decimal(str(rule.get("min_notional", "10")))
                    quote_currency = rule.get("quote", "USDT")

                    return_val.append(
                        TradingRule(
                            trading_pair,
                            min_order_size=min_size,
                            min_price_increment=tick_size,
                            min_base_amount_increment=size_increment,
                            min_notional_size=min_notional,
                            buy_order_collateral_token=quote_currency,
                            sell_order_collateral_token=quote_currency,
                        )
                    )
            except Exception as e:
                self.logger().error(
                    f"Error parsing the trading pair rule {rule}. Error: {e}. Skipping...",
                    exc_info=True,
                )
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """Build the hummingbot symbol -> exchange symbol bidirectional map."""
        mapping = bidict()
        instruments = self._extract_result_list(exchange_info)
        for instrument_data in instruments:
            if web_utils.is_exchange_information_valid(instrument_data):
                instrument = instrument_data.get("instrument", "")
                if not instrument:
                    continue
                self._instrument_info_by_symbol[instrument] = instrument_data
                trading_pair = web_utils.convert_from_exchange_trading_pair(instrument)
                if "-" not in trading_pair:
                    base = instrument_data.get("base", "")
                    quote = instrument_data.get("quote", "")
                    if base and quote:
                        trading_pair = combine_to_hb_trading_pair(base, quote)
                if trading_pair not in mapping.inverse:
                    mapping[instrument] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    # ------------------------------------------------------------------
    # Price / balance / position queries
    # ------------------------------------------------------------------

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_for_trading_pair(trading_pair=trading_pair)
        params = {"instrument": exchange_symbol}
        response = await self._api_post(
            path_url=CONSTANTS.MINI_TICKER_URL,
            data=params,
            is_auth_required=False,
        )
        result = response.get("result", response)
        price = float(result.get("last_price", result.get("mark_price", "0")))
        return price

    async def _update_balances(self):
        """Calls the REST API to update total and available balances."""
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_post(
            path_url=CONSTANTS.ACCOUNT_SUMMARY_URL,
            data={"sub_account_id": self.grvt_perpetual_sub_account_id},
            is_auth_required=True,
        )

        result = account_info.get("result", account_info)
        total_available = Decimal(str(result.get("available_balance", "0")))
        settle_currency = result.get("settle_currency", "USDT")

        spot_balances = result.get("spot_balances", [])
        for spot_balance in spot_balances:
            asset_name = spot_balance.get("currency", "")
            total_balance = Decimal(str(spot_balance.get("balance", "0")))
            self._account_balances[asset_name] = total_balance
            self._account_available_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        # Override settle currency available balance with the account-level figure
        if settle_currency in remote_asset_names:
            self._account_available_balances[settle_currency] = total_available

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        """Calls the REST API to update open perpetual positions."""
        positions_response = await self._api_post(
            path_url=CONSTANTS.POSITIONS_URL,
            data={
                "sub_account_id": self.grvt_perpetual_sub_account_id,
                "kind": ["PERPETUAL"],
            },
            is_auth_required=True,
        )

        positions = self._extract_result_list(positions_response)
        for position in positions:
            instrument = position.get("instrument", "")
            try:
                hb_trading_pair = web_utils.convert_from_exchange_trading_pair(instrument)
            except Exception:
                continue

            position_side = PositionSide.BOTH
            unrealized_pnl = Decimal(str(position.get("unrealized_pnl", "0")))
            entry_price = Decimal(str(position.get("entry_price", "0")))
            amount = Decimal(str(position.get("size", "0")))
            leverage = Decimal(str(position.get("leverage", "1")))
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)

            if amount != 0:
                _position = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(pos_key, _position)
            else:
                self._perpetual_trading.remove_position(pos_key)

    async def _update_order_fills_from_trades(self):
        """Poll fill history and push TradeUpdate events for tracked orders."""
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            trading_pairs_to_order_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {})
            for order in self._order_tracker.active_orders.values():
                if order.exchange_order_id is not None:
                    trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order

            try:
                fills_response = await self._api_post(
                    path_url=CONSTANTS.FILL_HISTORY_URL,
                    data={
                        "sub_account_id": self.grvt_perpetual_sub_account_id,
                        "kind": ["PERPETUAL"],
                    },
                    is_auth_required=True,
                )

                fills = self._extract_result_list(fills_response)
                for fill in fills:
                    fill_order_id = str(fill.get("order_id", ""))
                    for _, order_map in trading_pairs_to_order_map.items():
                        if fill_order_id in order_map:
                            tracked_order = order_map[fill_order_id]
                            fill_price = Decimal(str(fill.get("price", "0")))
                            fill_size = Decimal(str(fill.get("size", "0")))
                            fee_amount = Decimal(str(fill.get("fee", "0")))
                            quote_asset = tracked_order.quote_asset

                            fee = TradeFeeBase.new_perpetual_fee(
                                fee_schema=self.trade_fee_schema(),
                                position_action=PositionAction.OPEN,
                                percent_token=quote_asset,
                                flat_fees=[TokenAmount(amount=fee_amount, token=quote_asset)],
                            )
                            trade_update: TradeUpdate = TradeUpdate(
                                trade_id=str(fill.get("trade_id", "")),
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=fill_order_id,
                                trading_pair=tracked_order.trading_pair,
                                fill_timestamp=int(
                                    fill.get("event_time", str(int(time.time() * 1e9)))
                                ) / 1e9,
                                fill_price=fill_price,
                                fill_base_amount=fill_size,
                                fill_quote_amount=fill_price * fill_size,
                                fee=fee,
                            )
                            self._order_tracker.process_trade_update(trade_update)
            except Exception as e:
                self.logger().network(
                    f"Error fetching trades update: {e}.",
                    app_warning_msg="Failed to fetch trade updates.",
                )

    async def _update_order_status(self):
        """Poll order status for all active tracked orders."""
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            tracked_orders = list(self._order_tracker.active_orders.values())
            tasks = [
                self._api_post(
                    path_url=CONSTANTS.GET_ORDER_URL,
                    data={
                        "sub_account_id": self.grvt_perpetual_sub_account_id,
                        "client_order_id": order.client_order_id,
                    },
                    is_auth_required=True,
                )
                for order in tracked_orders
            ]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for order_update_result, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._order_tracker.all_orders:
                    continue
                if isinstance(order_update_result, Exception) or "code" in order_update_result:
                    if (
                        not isinstance(order_update_result, Exception)
                        and order_update_result.get("code") == CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE
                    ):
                        await self._order_tracker.process_order_not_found(client_order_id)
                    else:
                        self.logger().network(
                            f"Error fetching status update for order {client_order_id}: "
                            f"{order_update_result}."
                        )
                    continue

                result_order = order_update_result.get("result", order_update_result)
                order_state_obj = result_order.get("state", {})
                if isinstance(order_state_obj, dict):
                    order_status = order_state_obj.get("status", "OPEN")
                    update_time = order_state_obj.get("update_time", str(int(time.time() * 1e9)))
                else:
                    order_status = str(order_state_obj)
                    update_time = str(int(time.time() * 1e9))

                new_order_update: OrderUpdate = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=int(update_time) / 1e9,
                    new_state=CONSTANTS.ORDER_STATE.get(
                        order_status, tracked_order.current_state
                    ),
                    client_order_id=result_order.get("metadata", {}).get(
                        "client_order_id", client_order_id
                    ),
                    exchange_order_id=str(result_order.get("order_id", "")),
                )
                self._order_tracker.process_order_update(new_order_update)

    # ------------------------------------------------------------------
    # Position mode / leverage
    # ------------------------------------------------------------------

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return PositionMode.ONEWAY

    async def _trading_pair_position_mode_set(
        self, mode: PositionMode, trading_pair: str
    ) -> Tuple[bool, str]:
        if mode != PositionMode.ONEWAY:
            return False, "GRVT only supports one-way position mode"
        return True, ""

    async def _set_trading_pair_leverage(
        self, trading_pair: str, leverage: int
    ) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_for_trading_pair(trading_pair)
        params = {
            "sub_account_id": self.grvt_perpetual_sub_account_id,
            "instrument": symbol,
            "leverage": str(leverage),
        }
        try:
            set_leverage_result = await self._api_post(
                path_url=CONSTANTS.SET_INITIAL_LEVERAGE_URL,
                data=params,
                is_auth_required=True,
            )
            if set_leverage_result.get("code"):
                return False, f"Unable to set leverage: {set_leverage_result.get('message', '')}"
            return True, ""
        except Exception as e:
            return False, f"Error setting leverage: {e}"

    # ------------------------------------------------------------------
    # Funding payments
    # ------------------------------------------------------------------

    async def _fetch_last_fee_payment(
        self, trading_pair: str
    ) -> Tuple[int, Decimal, Decimal]:
        exchange_symbol = await self.exchange_symbol_for_trading_pair(trading_pair)

        payment_response = await self._api_post(
            path_url=CONSTANTS.FUNDING_PAYMENT_HISTORY_URL,
            data={
                "sub_account_id": self.grvt_perpetual_sub_account_id,
                "instrument": exchange_symbol,
                "limit": 1,
            },
            is_auth_required=True,
        )

        funding_rate_response = await self._api_post(
            path_url=CONSTANTS.FUNDING_RATE_URL,
            data={
                "instrument": exchange_symbol,
                "limit": 1,
            },
            is_auth_required=False,
        )

        payments = self._extract_result_list(payment_response)
        funding_rates = self._extract_result_list(funding_rate_response)

        if len(payments) < 1:
            return 0, Decimal("-1"), Decimal("-1")

        funding_payment = payments[0]
        _payment = Decimal(str(funding_payment.get("payment", "0")))
        timestamp = int(funding_payment.get("event_time", "0"))

        if len(funding_rates) > 0:
            funding_rate = Decimal(str(funding_rates[0].get("funding_rate", "0")))
        else:
            funding_rate = Decimal("-1")

        if timestamp > 0:
            # Convert from nanoseconds to seconds
            timestamp = int(timestamp / 1e9)

        if _payment != Decimal("0"):
            return timestamp, funding_rate, _payment
        else:
            return 0, Decimal("-1"), Decimal("-1")
