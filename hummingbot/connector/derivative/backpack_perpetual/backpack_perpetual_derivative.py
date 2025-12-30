import asyncio
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.backpack_perpetual import (
    backpack_perpetual_constants as CONSTANTS,
    backpack_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_api_order_book_data_source import (
    BackpackPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_auth import BackpackPerpetualAuth
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_user_stream_data_source import (
    BackpackPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BackpackPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Backpack Perpetual Derivative connector.

    Implements the PerpetualDerivativePyBase interface for perpetual futures trading.
    """

    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
        self,
        backpack_perpetual_api_key: str,
        backpack_perpetual_api_secret: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._backpack_api_key = backpack_perpetual_api_key
        self._backpack_api_secret = backpack_perpetual_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = PositionMode.ONEWAY
        self._last_trade_history_timestamp = None

        super().__init__()

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[BackpackPerpetualAuth]:
        if self._trading_required:
            return BackpackPerpetualAuth(
                api_key=self._backpack_api_key,
                secret_key=self._backpack_api_secret,
            )
        return None

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
        return CONSTANTS.MARKETS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.MARKETS_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.STATUS_URL

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
        return 120

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BackpackPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BackpackPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path)

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path)
        return exchange_info

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_trading_rules(self):
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = await self._api_get(path_url=self.trading_pairs_request_path)
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        """
        Initialize trading pair symbols for perpetual markets.

        Backpack perpetual symbols end with _PERP:
        - BTC_USDC_PERP
        - SOL_USDC_PERP
        """
        mapping = bidict()

        for market in exchange_info:
            symbol = market.get("symbol", "")
            base_symbol = market.get("baseSymbol", "")
            quote_symbol = market.get("quoteSymbol", "")

            # Only include perpetual markets
            if "_PERP" not in symbol:
                continue

            if base_symbol and quote_symbol:
                # Create trading pair without _PERP suffix for internal use
                trading_pair = combine_to_hb_trading_pair(base_symbol, quote_symbol)
                mapping[symbol] = trading_pair

        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, exchange_info: List[Dict[str, Any]]) -> List[TradingRule]:
        trading_rules = []

        for market in exchange_info:
            try:
                symbol = market.get("symbol", "")
                base_symbol = market.get("baseSymbol", "")
                quote_symbol = market.get("quoteSymbol", "")

                # Only include perpetual markets
                if "_PERP" not in symbol:
                    continue

                if not base_symbol or not quote_symbol:
                    continue

                trading_pair = combine_to_hb_trading_pair(base_symbol, quote_symbol)

                min_order_size = Decimal(str(market.get("minOrderSize", "0.00001")))
                tick_size = Decimal(str(market.get("tickSize", "0.01")))
                step_size = Decimal(str(market.get("stepSize", "0.00001")))
                min_notional = Decimal(str(market.get("minNotional", "1")))

                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=tick_size,
                        min_base_amount_increment=step_size,
                        min_notional_size=min_notional,
                        buy_order_collateral_token=quote_symbol,
                        sell_order_collateral_token=quote_symbol,
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
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=quote_currency,
            flat_fees=[TokenAmount(amount=Decimal("0"), token=quote_currency)],
        )
        return fee

    async def _update_trading_fees(self):
        pass

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
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        side = CONSTANTS.ORDER_SIDE_BID if trade_type == TradeType.BUY else CONSTANTS.ORDER_SIDE_ASK

        if order_type == OrderType.LIMIT:
            backpack_order_type = "Limit"
            time_in_force = "GTC"
        elif order_type == OrderType.LIMIT_MAKER:
            backpack_order_type = "Limit"
            time_in_force = "GTC"
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
            "clientId": order_id,
        }

        if order_type != OrderType.MARKET:
            api_params["price"] = str(price)
            api_params["timeInForce"] = time_in_force

        if order_type == OrderType.LIMIT_MAKER:
            api_params["postOnly"] = True

        # Add reduce-only for close positions
        if position_action == PositionAction.CLOSE:
            api_params["reduceOnly"] = True

        order_result = await self._api_post(
            path_url=CONSTANTS.ORDER_URL,
            data=api_params,
            is_auth_required=True,
        )

        if "error" in order_result or order_result.get("status") == "error":
            error_msg = order_result.get("error", order_result.get("message", "Unknown error"))
            raise IOError(f"Error submitting order {order_id}: {error_msg}")

        exchange_order_id = str(order_result.get("id", order_result.get("orderId", "")))
        timestamp = self.current_timestamp

        return exchange_order_id, timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        api_params = {
            "symbol": symbol,
            "clientId": order_id,
        }

        if tracked_order.exchange_order_id:
            api_params["orderId"] = tracked_order.exchange_order_id

        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_URL,
            params=api_params,
            is_auth_required=True,
        )

        if "error" in cancel_result:
            error_msg = cancel_result.get("error", "Unknown error")
            if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                self.logger().debug(f"Order {order_id} does not exist on Backpack. No cancellation needed.")
                await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f"Error cancelling order {order_id}: {error_msg}")

        return True

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.BALANCE_URL,
            is_auth_required=True,
        )

        if isinstance(account_info, dict):
            for asset_name, balance_data in account_info.items():
                if isinstance(balance_data, dict):
                    available = Decimal(str(balance_data.get("available", "0")))
                    locked = Decimal(str(balance_data.get("locked", "0")))
                    total = available + locked

                    self._account_available_balances[asset_name] = available
                    self._account_balances[asset_name] = total
                    remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        """Update perpetual positions from the exchange."""
        try:
            positions_data = await self._api_get(
                path_url=CONSTANTS.POSITIONS_URL,
                is_auth_required=True,
            )

            if isinstance(positions_data, list):
                for position_data in positions_data:
                    await self._process_position_data(position_data)
            elif isinstance(positions_data, dict):
                for symbol, position_data in positions_data.items():
                    position_data["symbol"] = symbol
                    await self._process_position_data(position_data)
        except Exception:
            self.logger().warning("Error updating positions", exc_info=True)

    async def _process_position_data(self, position_data: Dict[str, Any]):
        """Process individual position data."""
        try:
            symbol = position_data.get("symbol", "")
            if not symbol or "_PERP" not in symbol:
                return

            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)

            position_side_str = position_data.get("side", "")
            if position_side_str == CONSTANTS.POSITION_SIDE_LONG:
                position_side = PositionSide.LONG
            elif position_side_str == CONSTANTS.POSITION_SIDE_SHORT:
                position_side = PositionSide.SHORT
            else:
                # Determine from quantity
                quantity = Decimal(str(position_data.get("quantity", "0")))
                position_side = PositionSide.LONG if quantity > 0 else PositionSide.SHORT

            amount = abs(Decimal(str(position_data.get("quantity", "0"))))
            entry_price = Decimal(str(position_data.get("entryPrice", "0")))
            unrealized_pnl = Decimal(str(position_data.get("unrealizedPnl", "0")))
            leverage = Decimal(str(position_data.get("leverage", "1")))

            if amount == Decimal("0"):
                # No position
                pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
                if pos_key in self._perpetual_trading._account_positions:
                    del self._perpetual_trading._account_positions[pos_key]
            else:
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount if position_side == PositionSide.LONG else -amount,
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(trading_pair, position_side, position)

        except Exception:
            self.logger().warning(f"Error processing position data: {position_data}", exc_info=True)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
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
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    continue

                stream = event_message.get("stream", "")
                data = event_message.get("data", {})

                if stream.startswith("account.orderUpdate") or "orderUpdate" in stream:
                    await self._process_order_update(data)
                elif stream.startswith("account.position") or "positionUpdate" in stream:
                    await self._process_position_update(data)
                elif stream.startswith("account.fill") or "fill" in stream:
                    await self._process_trade_message(data)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.",
                    exc_info=True,
                )
                await self._sleep(5.0)

    async def _process_order_update(self, order_data: Dict[str, Any]):
        client_order_id = order_data.get("clientId", order_data.get("clientOrderId", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        status = order_data.get("status", order_data.get("orderStatus", ""))
        new_state = CONSTANTS.ORDER_STATE.get(status)

        if new_state is None:
            self.logger().warning(f"Unknown order status: {status}")
            return

        exchange_order_id = str(order_data.get("id", order_data.get("orderId", "")))
        update_timestamp = float(order_data.get("updatedAt", order_data.get("timestamp", 0)))
        if update_timestamp > 1e12:
            update_timestamp = update_timestamp / 1000.0

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _process_position_update(self, position_data: Dict[str, Any]):
        """Process position update from WebSocket."""
        await self._process_position_data(position_data)

    async def _process_trade_message(self, trade_data: Dict[str, Any]):
        client_order_id = trade_data.get("clientId", trade_data.get("clientOrderId", ""))
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if tracked_order is None:
            return

        fee_asset = trade_data.get("feeSymbol", trade_data.get("feeCurrency", ""))
        fee_amount = Decimal(str(trade_data.get("fee", "0")))

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=tracked_order.position,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
        )

        fill_price = Decimal(str(trade_data.get("price", trade_data.get("px", "0"))))
        fill_amount = Decimal(str(trade_data.get("quantity", trade_data.get("sz", "0"))))

        trade_update = TradeUpdate(
            trade_id=str(trade_data.get("tradeId", trade_data.get("id", ""))),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade_data.get("orderId", "")),
            trading_pair=tracked_order.trading_pair,
            fee=fee,
            fill_base_amount=fill_amount,
            fill_quote_amount=fill_price * fill_amount,
            fill_price=fill_price,
            fill_timestamp=float(trade_data.get("timestamp", 0)) / 1000.0,
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        params = {"symbol": symbol}

        if tracked_order.exchange_order_id:
            params["orderId"] = tracked_order.exchange_order_id
        else:
            params["clientId"] = tracked_order.client_order_id

        order_info = await self._api_get(
            path_url=CONSTANTS.ORDER_URL,
            params=params,
            is_auth_required=True,
        )

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
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        ticker_data = await self._api_get(
            path_url=CONSTANTS.TICKER_URL,
            params={"symbol": symbol},
        )

        price = float(ticker_data.get("lastPrice", ticker_data.get("lastPx", 0)))
        return price

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        # Backpack likely only supports ONEWAY mode
        if mode != PositionMode.ONEWAY:
            return False, "Backpack only supports ONEWAY position mode"
        return True, ""

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """Set leverage for a trading pair."""
        try:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            api_params = {
                "symbol": symbol,
                "leverage": leverage,
            }

            result = await self._api_post(
                path_url=CONSTANTS.LEVERAGE_URL,
                data=api_params,
                is_auth_required=True,
            )

            if "error" in result:
                return False, result.get("error", "Unknown error")

            return True, ""
        except Exception as e:
            return False, str(e)

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        """
        Fetch the last funding fee payment.

        Returns:
            Tuple of (timestamp, funding_rate, payment_amount)
        """
        try:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

            funding_data = await self._api_get(
                path_url=CONSTANTS.FUNDING_RATES_URL,
                params={"symbol": symbol},
            )

            if isinstance(funding_data, list) and len(funding_data) > 0:
                latest = funding_data[-1]
                timestamp = int(latest.get("timestamp", 0))
                rate = Decimal(str(latest.get("rate", "0")))
                payment = Decimal(str(latest.get("payment", "0")))
                return timestamp, rate, payment

            return 0, Decimal("0"), Decimal("0")
        except Exception:
            self.logger().warning(f"Error fetching funding payment for {trading_pair}", exc_info=True)
            return 0, Decimal("0"), Decimal("0")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
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

                fee = TradeFeeBase.new_perpetual_fee(
                    fee_schema=self.trade_fee_schema(),
                    position_action=order.position,
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
