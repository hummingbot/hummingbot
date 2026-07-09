import asyncio
import datetime
import time
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.evedex_perpetual import (
    evedex_perpetual_constants as CONSTANTS,
    evedex_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_api_order_book_data_source import (
    EvedexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_user_stream_data_source import (
    EvedexPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

epm_logger = None


class EvedexAlreadyClosedPositionError(ValueError):
    def __init__(self, trading_pair: str, reference_price: Decimal):
        super().__init__(f"Position already closed for {trading_pair}.")
        self.trading_pair = trading_pair
        self.reference_price = reference_price


class EvedexPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            evedex_perpetual_api_key: str = None,
            evedex_perpetual_private_key: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.evedex_perpetual_api_key = evedex_perpetual_api_key
        self.evedex_perpetual_private_key = evedex_perpetual_private_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = PositionMode.ONEWAY  # Evedex uses one-way mode
        self._last_trade_history_timestamp = None
        self._auth: Optional[EvedexPerpetualAuth] = None
        self._real_time_balance_update = False  # Remove this once bybit enables available balance again through ws
        self._balance_update_task: Optional[asyncio.Task] = None
        self._position_update_task: Optional[asyncio.Task] = None
        self._position_transition_order_ids: Dict[str, str] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> EvedexPerpetualAuth:
        if self._auth is None:
            self._auth = EvedexPerpetualAuth(
                api_key=self.evedex_perpetual_api_key,
                time_provider=self._time_synchronizer,
                private_key=self.evedex_perpetual_private_key or ""
            )
            self._auth.set_token_fetcher(self._fetch_access_token)
        return self._auth

    async def _fetch_access_token(self) -> dict:
        """
        Fetch the access token for WebSocket authentication from /api/dx-feed/auth.
        Returns the token data including 'token', 'tokenId', and 'expireAt'.
        """
        try:
            token_data = await self._api_get(
                path_url=CONSTANTS.DX_FEED_AUTH_PATH_URL,
                is_auth_required=True
            )
            return token_data
        except Exception as e:
            self.logger().warning(f"Failed to fetch access token: {e}")
            return {}

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
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

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
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self):
        """
        Evedex supports one-way position mode
        """
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    async def _create_order(
            self,
            trade_type: TradeType,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType,
            price: Optional[Decimal] = None,
            position_action: PositionAction = PositionAction.NIL,
            **kwargs,
    ):
        tracks_position_transition = (
            self._position_mode == PositionMode.ONEWAY and position_action == PositionAction.CLOSE
        )
        if tracks_position_transition:
            self._begin_position_transition(trading_pair=trading_pair, order_id=order_id)
        try:
            await super()._create_order(
                trade_type=trade_type,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                position_action=position_action,
                **kwargs,
            )
        except asyncio.CancelledError:
            if tracks_position_transition:
                self._clear_position_transition(
                    trading_pair=trading_pair,
                    reason=f"close order task {order_id} canceled before completion",
                )
            raise
        finally:
            if tracks_position_transition:
                self._schedule_position_update(reason=f"close order workflow for {order_id}")

    def _quantize_market_cash_quantity(self, trading_pair: str, cash_quantity: Decimal) -> Decimal:
        # Evedex validates cashQuantity against the instrument price increment.
        cash_quantity_quantum = self.get_order_price_quantum(trading_pair, cash_quantity)
        return (cash_quantity // cash_quantity_quantum) * cash_quantity_quantum

    def _active_position_for_trading_pair(self, trading_pair: str) -> Optional[Position]:
        position = self._perpetual_trading.get_position(trading_pair)
        if position is not None and position.amount != Decimal("0"):
            return position
        return None

    def _position_size_for_trading_pair(self, trading_pair: str) -> Decimal:
        position = self._active_position_for_trading_pair(trading_pair)
        return abs(position.amount) if position is not None else Decimal("0")

    def _reference_price_for_close(self, trading_pair: str, trade_type: TradeType, price: Decimal) -> Decimal:
        if price is not None and price != s_decimal_NaN and not price.is_nan():
            return price
        try:
            return self.get_price(trading_pair, trade_type is TradeType.BUY)
        except Exception:
            return Decimal("0")

    async def _reconcile_market_close_amount(
        self,
        order_id: str,
        trading_pair: str,
        requested_amount: Decimal,
        trade_type: TradeType,
        price: Decimal,
    ) -> Decimal:
        live_position_amount = self._position_size_for_trading_pair(trading_pair)
        refresh_succeeded = False
        try:
            await self._update_positions()
            refresh_succeeded = True
            live_position_amount = self._position_size_for_trading_pair(trading_pair)
        except Exception:
            self.logger().warning(
                f"Failed to refresh positions before placing Evedex market close order {order_id} for {trading_pair}. "
                f"Falling back to local position amount {live_position_amount}.",
                exc_info=True,
            )

        if live_position_amount <= Decimal("0"):
            if not refresh_succeeded:
                return requested_amount
            raise EvedexAlreadyClosedPositionError(
                trading_pair=trading_pair,
                reference_price=self._reference_price_for_close(
                    trading_pair=trading_pair,
                    trade_type=trade_type,
                    price=price,
                ),
            )

        reconciled_amount = min(requested_amount, live_position_amount)
        if reconciled_amount < requested_amount:
            self.logger().info(
                f"Clamping Evedex market close order {order_id} for {trading_pair} from "
                f"{requested_amount} to live position size {reconciled_amount}."
            )

        return reconciled_amount

    def _mark_close_order_as_filled_without_exchange(
        self,
        order_id: str,
        trading_pair: str,
        reference_price: Decimal,
    ):
        tracked_order = self._order_tracker.fetch_order(client_order_id=order_id)
        if tracked_order is None:
            return

        if reference_price > Decimal("0"):
            tracked_order.price = reference_price
        synthetic_exchange_order_id = tracked_order.exchange_order_id or f"already-closed-{order_id}"
        tracked_order.update_exchange_order_id(synthetic_exchange_order_id)
        tracked_order.executed_amount_base = tracked_order.amount
        if tracked_order.price is not None and tracked_order.price != s_decimal_NaN and not tracked_order.price.is_nan():
            tracked_order.executed_amount_quote = tracked_order.amount * tracked_order.price
        else:
            tracked_order.executed_amount_quote = Decimal("0")
        tracked_order.check_filled_condition()

        self._order_tracker.process_order_update(OrderUpdate(
            trading_pair=trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FILLED,
            client_order_id=order_id,
            exchange_order_id=synthetic_exchange_order_id,
        ))
        self._schedule_balance_update(reason=f"already-flat position close order {order_id}")
        self._schedule_position_update(reason=f"already-flat position close order {order_id}")
        if self._position_transition_order_id(trading_pair) == order_id:
            self._clear_position_transition(
                trading_pair=trading_pair,
                reason="close order was synthesized as filled because the live position was already flat",
            )

    def _begin_position_transition(self, trading_pair: str, order_id: str):
        self._position_transition_order_ids[trading_pair] = order_id
        self.logger().debug(
            f"Marked Evedex position transition in progress for {trading_pair} with close order {order_id}."
        )

    def _clear_position_transition(self, trading_pair: str, reason: str):
        order_id = self._position_transition_order_ids.pop(trading_pair, None)
        if order_id is not None:
            self.logger().debug(
                f"Cleared Evedex position transition for {trading_pair} (close order {order_id}): {reason}."
            )

    def _position_transition_order_id(self, trading_pair: str) -> Optional[str]:
        return self._position_transition_order_ids.get(trading_pair)

    def _position_transition_order(self, trading_pair: str) -> Optional[InFlightOrder]:
        order_id = self._position_transition_order_id(trading_pair)
        if order_id is None:
            return None
        return self._order_tracker.fetch_order(client_order_id=order_id)

    def _is_position_transition_pending(self, trading_pair: str) -> bool:
        transition_order_id = self._position_transition_order_id(trading_pair)
        if transition_order_id is None:
            return False

        tracked_close_order = self._position_transition_order(trading_pair)
        if tracked_close_order is not None and not tracked_close_order.is_done:
            return True

        return self._active_position_for_trading_pair(trading_pair) is not None

    def _position_transition_clear_reason(self, trading_pair: str) -> str:
        tracked_close_order = self._position_transition_order(trading_pair)
        if tracked_close_order is None:
            return "close order is no longer tracked and position refresh confirmed the pair is flat"
        return (
            f"close order {tracked_close_order.client_order_id} reached terminal state "
            f"{tracked_close_order.current_state.name} and position refresh confirmed the pair is flat"
        )

    async def _refresh_position_transition_state(self, trading_pair: str, reason: str):
        if self._position_transition_order_id(trading_pair) is None:
            return
        self.logger().debug(
            f"Refreshing Evedex positions while transition is pending for {trading_pair} ({reason})."
        )
        try:
            await self._update_positions()
        except Exception:
            self.logger().warning(
                f"Failed to refresh positions while transition was pending for {trading_pair}.",
                exc_info=True,
            )

    def _reconcile_position_transitions(self):
        for trading_pair in list(self._position_transition_order_ids.keys()):
            if not self._is_position_transition_pending(trading_pair):
                self._clear_position_transition(
                    trading_pair=trading_pair,
                    reason=self._position_transition_clear_reason(trading_pair),
                )

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        """
        Fetches prices for all trading pairs from EvedEx.
        Used by rate oracle for price discovery.

        :return: List of dicts with 'symbol' and 'price' keys
        """
        results: List[Dict[str, str]] = []
        try:
            response = await self._api_get(
                path_url=CONSTANTS.INSTRUMENTS_PATH_URL,
                params={"fields": "metrics"},
            )
            instruments = response if isinstance(response, list) else [response]
            for instrument in instruments:
                symbol = instrument.get("name")
                price = instrument.get("markPrice")
                if symbol and price:
                    results.append({
                        "symbol": symbol,
                        "price": str(price),
                    })
        except Exception:
            self.logger().exception("Error fetching all pairs prices from EvedEx")
        return results

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # Evedex doesn't use timestamp-based authentication
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return EvedexPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return EvedexPerpetualUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
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
        """
        Update fees information from the exchange
        """
        pass

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_fills_from_trades(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    def _generate_order_id(self) -> str:
        """Generate Evedex-compatible order ID in format: XXXXX:XXXXXXXXXXXXXXXXXXXXXXXXXX

        The first 5 digits represent the number of days since Evedex epoch (July 24, 2025).
        The remaining 26 characters are a random lowercase hex string.
        """
        # Evedex epoch: July 24, 2025 = day 20293 since Unix epoch
        EVEDEX_EPOCH_DAYS = 20293
        days_since_unix_epoch = int(time.time() / 86400)
        days_since_evedex_epoch = days_since_unix_epoch - EVEDEX_EPOCH_DAYS
        prefix = str(days_since_evedex_epoch).zfill(5)
        suffix = uuid.uuid4().hex[:26]  # lowercase hex
        return f"{prefix}:{suffix}"

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()
        path_url = CONSTANTS.CANCEL_ORDER_PATH_URL.format(orderId=exchange_order_id)

        await self._api_delete(
            path_url=path_url,
            is_auth_required=True,
            limit_id=CONSTANTS.CANCEL_ORDER_PATH_URL)

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
        if self._position_mode == PositionMode.ONEWAY and position_action == PositionAction.OPEN:
            transition_order_id = self._position_transition_order_id(trading_pair)
            if transition_order_id is not None:
                await self._refresh_position_transition_state(
                    trading_pair=trading_pair,
                    reason=f"before placing OPEN order {order_id}",
                )
                transition_order_id = self._position_transition_order_id(trading_pair)
                if transition_order_id is not None:
                    raise ValueError(
                        f"Position transition in progress for {trading_pair}. "
                        f"Close order {transition_order_id} is awaiting flat-position confirmation."
                    )

        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        # Generate Evedex-compatible order ID
        evedex_order_id = self._generate_order_id()

        # Get leverage
        leverage = self.get_leverage(trading_pair)
        leverage_int = int(leverage)
        side = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        chain_id = CONSTANTS.CHAIN_ID

        cash_quantity = None
        limit_id = None
        base_params = {
            "id": evedex_order_id,
            "instrument": symbol,
            "leverage": leverage_int,
            "chainId": chain_id,
        }
        if position_action == PositionAction.CLOSE and order_type == OrderType.MARKET:
            amount = await self._reconcile_market_close_amount(
                order_id=order_id,
                trading_pair=trading_pair,
                requested_amount=amount,
                trade_type=trade_type,
                price=price,
            )
            tracked_order = self._order_tracker.fetch_order(client_order_id=order_id)
            if tracked_order is not None:
                tracked_order.amount = amount
            path_url = CONSTANTS.CLOSE_POSITION_PATH_URL.format(instrument=symbol)
            limit_id = CONSTANTS.CLOSE_POSITION_PATH_URL
            api_params = {
                **base_params,
                "quantity": str(amount),
            }
            signer = self.authenticator.sign_position_close
            signer_kwargs = {
                "order_id": evedex_order_id,
                "instrument": symbol,
                "leverage": leverage_int,
                "quantity": amount,
                "chain_id": chain_id,
            }
        elif order_type == OrderType.MARKET:
            path_url = CONSTANTS.MARKET_ORDER_PATH_URL
            reference_price = price
            if reference_price.is_nan():
                reference_price = await self.get_order_price(
                    trading_pair=trading_pair,
                    is_buy=trade_type is TradeType.BUY,
                    amount=amount,
                )
            raw_cash_quantity = amount * reference_price
            cash_quantity = self._quantize_market_cash_quantity(trading_pair, raw_cash_quantity)
            if cash_quantity <= Decimal("0"):
                raise ValueError(
                    f"Calculated market cash quantity {cash_quantity} is invalid for {trading_pair}. "
                    f"Raw value: {raw_cash_quantity}."
                )
            api_params = {
                **base_params,
                "side": side,
                "cashQuantity": f"{cash_quantity:f}",
                "timeInForce": CONSTANTS.TIME_IN_FORCE_IOC,
            }
            signer = self.authenticator.sign_market_order
            signer_kwargs = {
                "order_id": evedex_order_id,
                "instrument": symbol,
                "side": side,
                "time_in_force": CONSTANTS.TIME_IN_FORCE_IOC,
                "leverage": leverage_int,
                "cash_quantity": cash_quantity,
                "chain_id": chain_id,
            }
        else:
            path_url = CONSTANTS.LIMIT_ORDER_PATH_URL
            api_params = {
                **base_params,
                "side": side,
                "quantity": str(amount),
                "limitPrice": str(price),
                "timeInForce": CONSTANTS.TIME_IN_FORCE_GTC,
            }
            signer = self.authenticator.sign_limit_order
            signer_kwargs = {
                "order_id": evedex_order_id,
                "instrument": symbol,
                "side": side,
                "leverage": leverage_int,
                "quantity": amount,
                "limit_price": price,
                "chain_id": chain_id,
            }

        # Add EIP-712 signature (required by EvedEx)
        if self.authenticator.wallet_address is None:
            raise ValueError(
                "EvedEx requires a private key for order signing. "
                "Please configure evedex_perpetual_private_key in your connector settings."
            )

        api_params["signature"] = signer(**signer_kwargs)

        try:
            order_result = await self._api_post(
                path_url=path_url,
                data=api_params,
                is_auth_required=True,
                limit_id=limit_id)

            exchange_order_id = str(order_result.get("id", evedex_order_id))
            transact_time = self._parse_exchange_timestamp(
                order_result.get("createdAt"),
                order_result.get("updatedAt"),
                order_result.get("completedAt"),
            )

        except IOError as e:
            error_description = str(e)

            # Handle insufficient funds - force balance refresh and raise
            if CONSTANTS.INSUFFICIENT_FUNDS_ERROR.lower() in error_description.lower():
                self.logger().error(f"Insufficient funds detected, refreshing balances: {error_description}")
                # Schedule balance refresh
                safe_ensure_future(self._update_balances())
                raise ValueError(f"Insufficient funds to place order for {trading_pair}: {error_description}")

            # Handle position close errors (Too many quantity / Unknown position)
            if (CONSTANTS.TOO_MANY_QUANTITY_ERROR.lower() in error_description.lower() or
                    CONSTANTS.UNKNOWN_POSITION_ERROR.lower() in error_description.lower()):
                self.logger().error(f"Position error detected, refreshing positions: {error_description}")
                refresh_succeeded = False
                try:
                    await self._update_positions()
                    refresh_succeeded = True
                except Exception:
                    self.logger().warning(
                        f"Failed to refresh positions after position error for {trading_pair}.",
                        exc_info=True,
                    )
                if refresh_succeeded and self._position_size_for_trading_pair(trading_pair) <= Decimal("0"):
                    raise EvedexAlreadyClosedPositionError(
                        trading_pair=trading_pair,
                        reference_price=self._reference_price_for_close(
                            trading_pair=trading_pair,
                            trade_type=trade_type,
                            price=price,
                        ),
                    )
                raise ValueError(f"Position error for {trading_pair}: {error_description}")

            if "503" in error_description:
                exchange_order_id = "UNKNOWN"
                transact_time = time.time()
            else:
                raise

        return exchange_order_id, transact_time

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
        position_action = kwargs.get("position_action")
        if position_action == PositionAction.CLOSE and isinstance(exception, EvedexAlreadyClosedPositionError):
            self.logger().info(
                f"Treating Evedex close order {order_id} for {trading_pair} as filled because the live position "
                f"is already flat."
            )
            self._mark_close_order_as_filled_without_exchange(
                order_id=order_id,
                trading_pair=trading_pair,
                reference_price=exception.reference_price,
            )
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

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            exchange_order_id = await order.get_exchange_order_id()
            orders_response = await self._api_get(
                path_url=CONSTANTS.GET_ORDERS_PATH_URL,
                params={
                    "status": "FILLED",
                    "offset": 0,
                    "limit": 500,
                },
                is_auth_required=True,
                limit_id=CONSTANTS.GET_ORDERS_PATH_URL)

            order_list = orders_response.get("list", []) if isinstance(orders_response, dict) else orders_response
            for order_data in order_list:
                if str(order_data.get("id", "")) != exchange_order_id:
                    continue

                fee = self._trade_fee_for_update(order, order_data.get("fee", []))

                total_quantity = Decimal(str(order_data.get("quantity", 0)))
                unfilled_quantity = Decimal(str(order_data.get("unFilledQuantity", 0)))
                filled_quantity = total_quantity - unfilled_quantity
                filled_avg_price = Decimal(str(order_data.get("filledAvgPrice", 0)))
                if filled_quantity <= 0:
                    continue

                trade_id = str(order_data.get("exchangeRequestId", exchange_order_id))
                trade_update: TradeUpdate = TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fill_timestamp=time.time(),
                    fill_price=filled_avg_price,
                    fill_base_amount=filled_quantity,
                    fill_quote_amount=filled_quantity * filled_avg_price,
                    fee=fee,
                )
                trade_updates.append(trade_update)

        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id} "
                          "- waiting for exchange order id.")

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        path_url = CONSTANTS.GET_ORDER_PATH_URL.format(orderId=exchange_order_id)

        order_update = await self._api_get(
            path_url=path_url,
            is_auth_required=True,
            limit_id=CONSTANTS.GET_ORDER_PATH_URL)

        new_state = CONSTANTS.ORDER_STATE.get(order_update.get("status", ""), tracked_order.current_state)

        _order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=time.time(),
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_update.get("id", exchange_order_id)),
        )
        return _order_update

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Evedex. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Wait for new messages from _user_stream_tracker.user_stream queue and processes them according to their
        message channels. The respective UserStreamDataSource queues these messages.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)
                await self._sleep(5.0)

    async def _process_user_stream_event(self, event_message: Dict[str, Any]):
        """
        Process user stream events from Centrifugo.

        Handles both push format:
        - Push: {"push": {"channel": "futures-perp:order:123", "pub": {"data": {...}}}}
        """
        # Handle Centrifugo push message format
        if isinstance(event_message, dict):
            if "push" in event_message:
                push_data = event_message.get("push", {})
                channel = push_data.get("channel", "")
                pub_data = push_data.get("pub", {})
                data = pub_data.get("data", {})

                # Centrifugo channel patterns: futures-perp:{type}:{userExchangeId}
                if "futures-perp:order" in channel and "futures-perp:orderFilled" not in channel:
                    await self._process_order_update(data)
                elif "futures-perp:position" in channel:
                    await self._process_position_update(data)
                elif "futures-perp:orderFilled" in channel:
                    await self._process_order_fill(data)

    def _position_action_for_order(self, tracked_order: InFlightOrder) -> PositionAction:
        if tracked_order.position != PositionAction.NIL:
            return tracked_order.position
        return PositionAction.OPEN if tracked_order.trade_type is TradeType.BUY else PositionAction.CLOSE

    def _trade_fee_for_update(self, tracked_order: InFlightOrder, fee_list: List[Dict[str, Any]]) -> TradeFeeBase:
        flat_fees = []
        for fee_item in fee_list:
            coin = str(fee_item.get("coin", "USDT")).upper()
            if coin == "TOTAL":
                continue
            amount = Decimal(str(fee_item.get("quantity", 0)))
            if amount == 0:
                continue
            flat_fees.append(TokenAmount(amount=amount, token=coin))

        return TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=self._position_action_for_order(tracked_order),
            percent_token="USDT",
            flat_fees=flat_fees,
        )

    @staticmethod
    def _parse_exchange_timestamp(*raw_timestamps: Any) -> float:
        for raw_timestamp in raw_timestamps:
            if raw_timestamp is None:
                continue
            try:
                if isinstance(raw_timestamp, (int, float, Decimal)):
                    return float(raw_timestamp)
                return datetime.datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00")).timestamp()
            except Exception:
                continue
        return time.time()

    @staticmethod
    def _trade_id_from_fill_data(fill_data: Dict[str, Any], exchange_order_id: str) -> str:
        filled_quantity = EvedexPerpetualDerivative._filled_amount_from_order_event(fill_data)

        price = fill_data.get("fillPrice", fill_data.get("filledAvgPrice", 0))
        # Evedex does not expose one stable fill identifier across WS order updates, WS fill events,
        # and REST /fill payloads. Prefer the most execution-specific field available, then fall back
        # to shared timestamps so the same economic fill hashes to the same trade_id across sources.
        trade_identifier = (
            fill_data.get("executionId")
            or fill_data.get("createdAt")
            or fill_data.get("updatedAt")
            or fill_data.get("completedAt")
            or fill_data.get("exchangeRequestId")
            or "trade"
        )
        return f"{exchange_order_id}_{trade_identifier}_{filled_quantity}_{price}"

    @staticmethod
    def _filled_amount_from_order_event(order_data: Dict[str, Any]) -> Decimal:
        fill_quantity = order_data.get("fillQuantity")
        if fill_quantity is not None:
            try:
                return Decimal(str(fill_quantity))
            except Exception:
                return Decimal("0")

        if "quantity" in order_data and "unFilledQuantity" in order_data:
            try:
                return Decimal(str(order_data.get("quantity", 0))) - Decimal(str(order_data.get("unFilledQuantity", 0)))
            except Exception:
                return Decimal("0")

        return Decimal("0")

    @staticmethod
    def _is_terminal_order_status(status: Any) -> bool:
        return str(status).upper() in {"FILLED", "CANCELLED", "REJECTED", "EXPIRED", "ERROR"}

    @staticmethod
    def _is_ioc_or_market_order_event(order_data: Dict[str, Any], tracked_order: Optional[InFlightOrder] = None) -> bool:
        raw_type = str(order_data.get("type", "")).upper()
        time_in_force = str(order_data.get("timeInForce", "")).upper()
        tracked_order_is_market = tracked_order is not None and tracked_order.order_type == OrderType.MARKET
        return raw_type == "MARKET" or time_in_force == CONSTANTS.TIME_IN_FORCE_IOC or tracked_order_is_market

    def _terminal_reported_executed_quantity(
        self,
        order_data: Dict[str, Any],
        tracked_order: Optional[InFlightOrder] = None,
    ) -> Optional[Decimal]:
        if tracked_order is None or not self._is_ioc_or_market_order_event(order_data, tracked_order):
            return None

        status = str(order_data.get("status", "")).upper()
        if status not in {"FILLED", "CANCELLED", "EXPIRED"}:
            return None

        filled_quantity = self._filled_amount_from_order_event(order_data)
        order_quantity = Decimal(str(order_data.get("quantity", tracked_order.amount)))
        quantity_candidates = [quantity for quantity in (filled_quantity, order_quantity) if quantity > Decimal("0")]
        reference_quantity = max(tracked_order.amount, order_quantity)

        if not quantity_candidates:
            return None

        normalized_quantity = min(quantity_candidates)
        if normalized_quantity >= reference_quantity:
            return None

        if status == "FILLED" or filled_quantity > Decimal("0"):
            return normalized_quantity

        return None

    def _normalize_tracked_order_for_terminal_partial_fill(
        self,
        tracked_order: Optional[InFlightOrder],
        order_data: Dict[str, Any],
    ):
        if tracked_order is None:
            return

        executed_quantity = self._terminal_reported_executed_quantity(order_data, tracked_order)
        if executed_quantity is not None:
            tracked_order.amount = executed_quantity
            tracked_order.check_filled_condition()

    def _get_order_state_from_order_data(
        self,
        order_data: Dict[str, Any],
        tracked_order: Optional[InFlightOrder] = None,
    ) -> Optional[OrderState]:
        status = str(order_data.get("status", "")).upper()
        if (
            status in {"CANCELLED", "EXPIRED"}
            and self._terminal_reported_executed_quantity(order_data, tracked_order) is not None
        ):
            return OrderState.FILLED
        return CONSTANTS.ORDER_STATE.get(status)

    def _log_fill_processed(
        self,
        tracked_order: InFlightOrder,
        exchange_order_id: str,
        fill_amount: Decimal,
        fill_price: Decimal,
        source: str,
    ):
        self.logger().debug(
            f"Processed Evedex {source} fill for {tracked_order.client_order_id} ({exchange_order_id}): "
            f"+{fill_amount} {tracked_order.base_asset} at {fill_price}. "
            f"Executed {tracked_order.executed_amount_base}/{tracked_order.amount}."
        )

    def _log_order_state_change(
        self,
        tracked_order: InFlightOrder,
        exchange_order_id: str,
        previous_state: OrderState,
        new_state: OrderState,
        source: str,
    ):
        self.logger().debug(
            f"Processed Evedex {source} order update for {tracked_order.client_order_id} ({exchange_order_id}): "
            f"{previous_state.name} -> {new_state.name}."
        )

    async def _process_order_fill(self, fill_data: Dict[str, Any]):
        # Process OrderFill from orderFills-{userExchangeId} channel.
        """
       {'id': '00239:8f0aa829617c4eca834a367cac', 'instrument': 'XRPUSD', 'user': '42520', 'side': 'SELL', 'quantity': 20, 'limitPrice': 0, 'status': 'FILLED', 'unFilledQuantity': 0, 'realizedPnL': 0.0013588, 'createdAt': '2026-03-20T02:42:54.804Z', 'updatedAt': '2026-03-20T02:42:54.804Z', 'filledAvgPrice': 1.4486, 'type': 'MARKET', 'timeInForce': 'IOC', 'cashQuantity': '0.00000000', 'rejectedReason': '', 'fee': [{'coin': 'usdt', 'quantity': 0.0130374}, {'coin': 'total', 'quantity': 0}], 'group': 'manually', 'stopPrice': None, 'triggeredAt': None, 'check': False, 'completedAt': '2026-03-20T02:42:54.964Z', 'exchangeRequestId': '72057614201194187', 'userSession': None, 'fillQuantity': 20}
        """
        order_id = str(fill_data.get("id", ""))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(order_id)
        fill_amount = self._filled_amount_from_order_event(fill_data)

        if tracked_order is not None:
            fill_price = Decimal(str(fill_data.get("fillPrice", fill_data.get("filledAvgPrice", 0))))
            fill_timestamp = self._parse_exchange_timestamp(fill_data.get("updatedAt"))
            trade_id = self._trade_id_from_fill_data(fill_data, order_id)
            new_fill_amount = max(Decimal("0"), fill_amount - tracked_order.executed_amount_base)

            if new_fill_amount > Decimal("0"):
                trade_update: TradeUpdate = TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=order_id,
                    trading_pair=tracked_order.trading_pair,
                    fill_timestamp=fill_timestamp,
                    fill_price=fill_price,
                    fill_base_amount=new_fill_amount,
                    fill_quote_amount=new_fill_amount * fill_price,
                    fee=self._trade_fee_for_update(tracked_order, fill_data.get("fee", [])),
                )
                self._order_tracker.process_trade_update(trade_update)
                self._log_fill_processed(
                    tracked_order=tracked_order,
                    exchange_order_id=order_id,
                    fill_amount=new_fill_amount,
                    fill_price=fill_price,
                    source="user stream",
                )
                self._schedule_position_update(
                    reason=f"user stream fill for {tracked_order.client_order_id} ({order_id})"
                )

            updatable_order = self._order_tracker.all_updatable_orders_by_exchange_order_id.get(order_id)
            if updatable_order is not None:
                self._normalize_tracked_order_for_terminal_partial_fill(updatable_order, fill_data)
                previous_state = updatable_order.current_state
                new_state = self._get_order_state_from_order_data(fill_data, updatable_order) or previous_state
                if new_state != previous_state:
                    order_update = OrderUpdate(
                        trading_pair=updatable_order.trading_pair,
                        update_timestamp=fill_timestamp,
                        new_state=new_state,
                        client_order_id=updatable_order.client_order_id,
                        exchange_order_id=order_id,
                    )
                    self._order_tracker.process_order_update(order_update)
                    self._log_order_state_change(
                        tracked_order=updatable_order,
                        exchange_order_id=order_id,
                        previous_state=previous_state,
                        new_state=new_state,
                        source="user stream fill",
                    )

            self._schedule_balance_update(reason=f"user stream fill for {tracked_order.client_order_id} ({order_id})")
        elif fill_amount > Decimal("0"):
            self.logger().debug(
                f"Processed untracked Evedex user stream fill for exchange order {order_id}: "
                f"fill amount {fill_amount}. Scheduling balance and position refresh."
            )
            self._schedule_balance_update(reason=f"untracked user stream fill for {order_id}")
            self._schedule_position_update(reason=f"untracked user stream fill for {order_id}")

    def _schedule_balance_update(self, reason: str = "connector event"):
        if self._balance_update_task is None or self._balance_update_task.done():
            self.logger().debug(f"Scheduling Evedex balance refresh ({reason}).")
            self._balance_update_task = safe_ensure_future(self._update_balances())
        else:
            self.logger().debug(f"Evedex balance refresh already pending ({reason}).")

    def _schedule_position_update(self, reason: str = "connector event"):
        if self._position_update_task is None or self._position_update_task.done():
            self.logger().debug(f"Scheduling Evedex position refresh ({reason}).")
            self._position_update_task = safe_ensure_future(self._update_positions())
        else:
            self.logger().debug(f"Evedex position refresh already pending ({reason}).")

    async def _process_order_update(self, order_data: Dict[str, Any]):
        # Order.id is the EXCHANGE order ID, not the client order ID
        """Process order update from the exchange.

        Args:
            order_data (Dict[str, Any]): The order data received from the exchange.
            {'id': '00239:9d6ea491b48b471e82a66d6e4c', 'instrument': 'XRPUSD', 'user': '42520', 'side': 'BUY', 'quantity': 20, 'limitPrice': 1.44853206, 'status': 'FILLED', 'unFilledQuantity': 0, 'realizedPnL': 0, 'createdAt': '2026-03-20T02:41:24.587Z', 'updatedAt': '2026-03-20T02:41:33.799Z', 'filledAvgPrice': 1.44853206, 'type': 'LIMIT', 'timeInForce': 'GTC', 'cashQuantity': '0.00000000', 'rejectedReason': '', 'fee': [{'coin': 'usdt', 'quantity': 0.0043456}, {'coin': 'total', 'quantity': 0.01303678854}], 'group': 'manually', 'stopPrice': None, 'triggeredAt': None, 'check': False, 'completedAt': '2026-03-20T02:41:34.067Z', 'exchangeRequestId': '72057614201035602', 'userSession': None, 'fillQuantity': 20}
        """

        exchange_order_id = str(order_data.get("id", ""))
        should_refresh_balance = False
        should_refresh_position = False
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
        fill_quantity = self._filled_amount_from_order_event(order_data)

        if tracked_order is not None:
            # Calculate filled quantity from Order type fields: quantity - unFilledQuantity
            total_quantity = Decimal(str(order_data.get("quantity", 0)))
            unfilled_quantity = Decimal(str(order_data.get("unFilledQuantity", 0)))
            filled_quantity = total_quantity - unfilled_quantity

            # Only process if there's a new fill (compare with tracked order's executed amount)
            if filled_quantity > tracked_order.executed_amount_base:
                new_fill_amount = filled_quantity - tracked_order.executed_amount_base
                fill_price = Decimal(str(order_data.get("filledAvgPrice", order_data.get("fillPrice", 0))))
                fill_timestamp = self._parse_exchange_timestamp(order_data.get("updatedAt"))
                trade_id = self._trade_id_from_fill_data(order_data, exchange_order_id)

                trade_update: TradeUpdate = TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=tracked_order.trading_pair,
                    fill_timestamp=fill_timestamp,
                    fill_price=fill_price,
                    fill_base_amount=new_fill_amount,
                    fill_quote_amount=new_fill_amount * fill_price,
                    fee=self._trade_fee_for_update(tracked_order, order_data.get("fee", [])),
                )

                self._order_tracker.process_trade_update(trade_update)
                self._log_fill_processed(
                    tracked_order=tracked_order,
                    exchange_order_id=exchange_order_id,
                    fill_amount=new_fill_amount,
                    fill_price=fill_price,
                    source="order update",
                )
                should_refresh_balance = True
                should_refresh_position = True

        # Process order status update - find by exchange_order_id
        tracked_order = self._order_tracker.all_updatable_orders_by_exchange_order_id.get(exchange_order_id)
        is_updatable_order_tracked = tracked_order is not None

        if tracked_order is not None:
            self._normalize_tracked_order_for_terminal_partial_fill(tracked_order, order_data)
            previous_state = tracked_order.current_state
            new_state = self._get_order_state_from_order_data(order_data, tracked_order) or previous_state
            order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self._parse_exchange_timestamp(order_data.get("updatedAt")),
                new_state=new_state,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=exchange_order_id,
            )
            self._order_tracker.process_order_update(order_update)
            if new_state != previous_state:
                self._log_order_state_change(
                    tracked_order=tracked_order,
                    exchange_order_id=exchange_order_id,
                    previous_state=previous_state,
                    new_state=new_state,
                    source="user stream order",
                )
            should_refresh_balance = True
            should_refresh_position = should_refresh_position or fill_quantity > Decimal("0")

        if not is_updatable_order_tracked and self._is_terminal_order_status(order_data.get("status")):
            self.logger().debug(
                f"Processed untracked terminal Evedex order update for exchange order {exchange_order_id}: "
                f"status={order_data.get('status')}, fill_quantity={fill_quantity}."
            )
            should_refresh_balance = True
            should_refresh_position = fill_quantity > Decimal("0") or str(order_data.get("status", "")).upper() == "FILLED"

        if should_refresh_balance:
            self._schedule_balance_update(
                reason=f"order update for {exchange_order_id} status={order_data.get('status')}"
            )
        if should_refresh_position:
            self._schedule_position_update(
                reason=f"order update for {exchange_order_id} status={order_data.get('status')}"
            )

    async def _process_position_update(self, position_data: Dict[str, Any]):
        positions = position_data if isinstance(position_data, list) else [position_data]
        await self._apply_position_updates(positions=positions, remove_stale=False)

    async def _apply_position_updates(self, positions: List[Dict[str, Any]], remove_stale: bool):
        active_position_keys = set()

        for position in positions:
            instrument = position.get("instrument", "")
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(instrument)
            except KeyError:
                continue

            raw_side = str(position.get("side", "")).upper()
            if raw_side in {"BUY", "LONG"}:
                position_side = PositionSide.LONG
            elif raw_side in {"SELL", "SHORT"}:
                position_side = PositionSide.SHORT
            else:
                self.logger().debug(f"Skipping position update with unsupported side '{raw_side}': {position}")
                continue

            amount = Decimal(str(position.get("quantity", 0)))
            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)

            if amount != Decimal("0"):
                active_position_keys.add(pos_key)
                signed_amount = -amount if position_side == PositionSide.SHORT else amount
                unrealized_pnl = Decimal(str(position.get("unRealizedPnL", position.get("unrealizedPnL", 0))))
                entry_price = Decimal(str(position.get("avgPrice", position.get("entryPrice", 0))))
                leverage = Decimal(str(position.get("leverage", 1)))

                self._perpetual_trading.set_position(
                    pos_key,
                    Position(
                        trading_pair=trading_pair,
                        position_side=position_side,
                        unrealized_pnl=unrealized_pnl,
                        entry_price=entry_price,
                        amount=signed_amount,
                        leverage=leverage,
                    ),
                )
                self.logger().debug(
                    f"Updated Evedex position {trading_pair} {position_side.name}: "
                    f"amount={signed_amount}, entry_price={entry_price}, leverage={leverage}."
                )
            else:
                self._perpetual_trading.remove_position(pos_key)
                self.logger().debug(f"Removed Evedex position {trading_pair} {position_side.name}.")

        if remove_stale:
            # REST returns a snapshot of all positions, so stale local positions can be safely removed here.
            current_position_keys = set(self._perpetual_trading.account_positions.keys())
            stale_position_keys = current_position_keys - active_position_keys
            for pos_key in stale_position_keys:
                self.logger().debug(f"Removing stale position: {pos_key}")
                self._perpetual_trading.remove_position(pos_key)

        self._reconcile_position_transitions()

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.
        """
        rules = exchange_info_dict if isinstance(exchange_info_dict, list) else exchange_info_dict.get("list", [])
        return_val: list = []

        for rule in rules:
            try:
                if web_utils.is_exchange_information_valid(rule):
                    instrument_name = rule.get("name", "")
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=instrument_name)

                    min_order_size = Decimal(str(rule.get("minQuantity", "0.001")))
                    tick_size = Decimal(str(rule.get("priceIncrement", "0.01")))
                    step_size = Decimal(str(rule.get("quantityIncrement", "0.001")))
                    # Use minVolume if available, otherwise fallback to calculation
                    min_volume = rule.get("minVolume")
                    if min_volume is not None and min_volume > 0:
                        min_notional = Decimal(str(min_volume))
                    else:
                        min_price = Decimal(str(rule.get("minPrice", "0.01")))
                        min_notional = min_order_size * min_price if min_price > 0 else Decimal("10")

                    # Get quote asset from the instrument
                    to_coin = rule.get("to", {})
                    collateral_token = to_coin.get("symbol", "USD").upper()
                    # Evedex uses USD but Hummingbot expects USDT
                    if collateral_token == "USD":
                        collateral_token = "USDT"

                    return_val.append(
                        TradingRule(
                            trading_pair,
                            min_order_size=min_order_size,
                            min_price_increment=tick_size,
                            min_base_amount_increment=step_size,
                            min_notional_size=min_notional,
                            buy_order_collateral_token=collateral_token,
                            sell_order_collateral_token=collateral_token,
                        )
                    )
            except Exception as e:
                self.logger().error(
                    f"Error parsing the trading pair rule {rule}. Error: {e}. Skipping...", exc_info=True
                )
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        rules = exchange_info if isinstance(exchange_info, list) else exchange_info.get("list", [])

        for symbol_data in filter(web_utils.is_exchange_information_valid, rules):
            instrument_name = symbol_data.get("name", "")
            from_coin = symbol_data.get("from", {})
            to_coin = symbol_data.get("to", {})

            base = from_coin.get("symbol", "")
            quote = to_coin.get("symbol", "")

            if base and quote:
                trading_pair = combine_to_hb_trading_pair(base, quote)
                # Only convert USD to USDT if not already USDT
                if quote == "USD":
                    trading_pair = trading_pair.replace("-USD", "-USDT")
                mapping[instrument_name] = trading_pair

        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        try:
            response = await self._api_get(
                path_url=CONSTANTS.INSTRUMENTS_PATH_URL,
                params={"fields": "metrics"},
            )
            instruments = response if isinstance(response, list) else [response]
            for instrument in instruments:
                symbol = instrument.get("name")
                price = instrument.get("lastPrice")
                if symbol == exchange_symbol and price:
                    return float(price)
        except Exception:
            self.logger().exception(f"Error fetching last traded price for {trading_pair} from EvedEx")
            raise

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """

        # Get available balance info
        available_balance_info = await self._api_get(
            path_url=CONSTANTS.AVAILABLE_BALANCE_PATH_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.AVAILABLE_BALANCE_PATH_URL)

        # Process funding balance
        # API returns: {"currency": "usdt", "funding": {"currency": "usdt", "balance": <num>}, "availableBalance": <num>, ...}
        funding = available_balance_info.get("funding", {})
        # Convert currency to uppercase as Hummingbot expects "USDT" not "usdt"
        currency = str(funding.get("currency", available_balance_info.get("currency", "usdt"))).upper()
        # Total balance is in funding.balance
        balance = Decimal(str(funding.get("balance", 0)))
        available = Decimal(str(available_balance_info.get("availableBalance", 0)))

        self._account_balances[currency] = balance
        self._account_available_balances[currency] = available

    async def _update_positions(self):
        positions_response = await self._api_get(
            path_url=CONSTANTS.POSITIONS_PATH_URL,
            is_auth_required=True)

        positions = positions_response.get("list", []) if isinstance(positions_response, dict) else positions_response
        await self._apply_position_updates(positions=positions, remove_stale=True)

    async def _update_order_fills_from_trades(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            trading_pairs_to_order_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {})
            for order in self._order_tracker.active_orders.values():
                trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order

            trading_pairs = list(trading_pairs_to_order_map.keys())

            # Use the fill endpoint to get recent fills
            for trading_pair in trading_pairs:
                try:
                    order_map = trading_pairs_to_order_map.get(trading_pair, {})
                    if not order_map:
                        continue

                    earliest_creation_ts = min(
                        (o.creation_timestamp for o in order_map.values() if o.creation_timestamp),
                        default=self.current_timestamp
                    )
                    after_ts = self._last_poll_timestamp if self._last_poll_timestamp > 0 else earliest_creation_ts
                    after_ts = max(0, after_ts - 1)
                    before_ts = self.current_timestamp + 1
                    if after_ts >= before_ts:
                        after_ts = max(0, before_ts - 1)

                    after_iso = datetime.datetime.fromtimestamp(
                        after_ts, tz=datetime.timezone.utc
                    ).isoformat(timespec="seconds").replace("+00:00", "Z")
                    before_iso = datetime.datetime.fromtimestamp(
                        before_ts, tz=datetime.timezone.utc
                    ).isoformat(timespec="seconds").replace("+00:00", "Z")

                    exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                    fills = await self._api_get(
                        path_url=CONSTANTS.ORDER_FILLS_PATH_URL,
                        params={
                            "instrument": exchange_symbol,
                            "after": after_iso,
                            "before": before_iso
                        },
                        is_auth_required=True)

                    fill_list = fills.get("list", []) if isinstance(fills, dict) else fills

                    for fill in fill_list:
                        order_id = str(fill.get("order"))
                        if order_id in order_map:
                            tracked_order: InFlightOrder = order_map.get(order_id)
                            fill_timestamp = self._parse_exchange_timestamp(fill.get("createdAt"))
                            fee = self._trade_fee_for_update(tracked_order, fill.get("fee", []))
                            fill_quantity = Decimal(str(fill.get("fillQuantity", 0)))
                            fill_price = Decimal(str(fill.get("fillPrice", 0)))
                            trade_id = self._trade_id_from_fill_data(fill, order_id)

                            if fill_quantity <= Decimal("0"):
                                continue

                            trade_update: TradeUpdate = TradeUpdate(
                                trade_id=trade_id,
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=order_id,
                                trading_pair=trading_pair,
                                fill_timestamp=fill_timestamp,
                                fill_price=fill_price,
                                fill_base_amount=fill_quantity,
                                fill_quote_amount=fill_quantity * fill_price,
                                fee=fee,
                            )
                            self._order_tracker.process_trade_update(trade_update)
                except Exception as e:
                    self.logger().network(
                        f"Error fetching trades update for {trading_pair}: {e}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )

    async def _update_order_status(self):
        """
        Calls the REST API to get order/trade updates for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            tracked_orders = list(self._order_tracker.active_orders.values())

            for tracked_order in tracked_orders:
                try:
                    exchange_order_id = await tracked_order.get_exchange_order_id()
                    path_url = CONSTANTS.GET_ORDER_PATH_URL.format(orderId=exchange_order_id)
                    order_update = await self._api_get(
                        path_url=path_url,
                        is_auth_required=True,
                        limit_id=CONSTANTS.GET_ORDER_PATH_URL)

                    new_state = CONSTANTS.ORDER_STATE.get(order_update.get("status", ""), tracked_order.current_state)

                    new_order_update: OrderUpdate = OrderUpdate(
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=time.time(),
                        new_state=new_state,
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=str(order_update.get("id", exchange_order_id)),
                    )
                    self._order_tracker.process_order_update(new_order_update)

                except Exception as e:
                    self.logger().network(
                        f"Error fetching status update for order {tracked_order.client_order_id}: {e}."
                    )

    async def _get_position_mode(self) -> Optional[PositionMode]:
        # Evedex uses one-way position mode
        return PositionMode.ONEWAY

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        # Evedex only supports one-way mode
        if mode == PositionMode.ONEWAY:
            return True, ""
        return False, "Evedex only supports one-way position mode"

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        path_url = CONSTANTS.SET_LEVERAGE_PATH_URL.format(instrument=symbol)

        try:
            set_leverage_result = await self._api_put(
                path_url=path_url,
                data={"leverage": leverage},
                is_auth_required=True,
                limit_id=CONSTANTS.SET_LEVERAGE_PATH_URL,
            )

            if set_leverage_result.get("leverage") == leverage:
                return True, ""
            return True, ""  # Leverage set successfully
        except Exception as e:
            return False, f"Unable to set leverage: {str(e)}"

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        """
        Fetches the last funding fee payment for a trading pair.
        """
        try:
            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

            # Get funding info from user endpoint
            funding_response = await self._api_get(
                path_url=CONSTANTS.POSITIONS_PATH_URL,
                is_auth_required=True,
                limit_id=CONSTANTS.POSITIONS_PATH_URL)

            # Initialize default values
            timestamp = 0
            funding_rate = Decimal("-1")
            payment = Decimal("-1")

            for funding in funding_response.get("list", []):
                if funding.get("coin") == exchange_symbol.split("-")[0]:
                    payment = Decimal(str(funding.get("quantity", 0)))
                    funding_rate = Decimal(str(funding.get("fundingRate", 0)))
                    timestamp = funding.get("updatedAt", 0)
                    break

            return timestamp, funding_rate, payment

        except Exception as e:
            self.logger().error(f"Error fetching funding fee: {e}")
            return 0, Decimal("-1"), Decimal("-1")
