import asyncio
import hashlib
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Literal, Optional, Tuple

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
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class EvedexPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            evedex_perpetual_api_key: str = None,
            evedex_perpetual_api_secret: str = None,
            evedex_perpetual_auth_mode: Literal["wallet", "api_key"] = "wallet",
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.evedex_perpetual_api_key = evedex_perpetual_api_key
        self.evedex_perpetual_api_secret = evedex_perpetual_api_secret
        self._auth_mode = evedex_perpetual_auth_mode
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self.symbol_to_instrument: Dict[str, Dict] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[EvedexPerpetualAuth]:
        if self._trading_required:
            return EvedexPerpetualAuth(
                self.evedex_perpetual_api_key,
                self.evedex_perpetual_api_secret,
                use_api_key_auth=(self._auth_mode == "api_key")
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
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_URL

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

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path)

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth)

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

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        d_price = Decimal(round(float(f"{price:.5g}"), 6))
        return d_price

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
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_lost_orders()

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
        pass

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        exchange_symbol = web_utils.convert_to_exchange_trading_pair(symbol)
        
        is_mainnet = self._domain == CONSTANTS.DOMAIN
        
        cancel_params = self._auth.sign_cancel_order(
            order_id=tracked_order.exchange_order_id or order_id,
            instrument=exchange_symbol,
            is_mainnet=is_mainnet
        )
        
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=cancel_params,
            is_auth_required=True)

        if cancel_result.get("error"):
            error_msg = cancel_result.get("error", {}).get("message", str(cancel_result.get("error")))
            self.logger().debug(f"Order {order_id} cancel error: {error_msg}")
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(error_msg)
        
        return True

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode("utf-8"))
        hex_order_id = f"0x{md5.hexdigest()}"
        
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(trading_pair, reference_price * Decimal(1 + CONSTANTS.MARKET_ORDER_SLIPPAGE))

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode("utf-8"))
        hex_order_id = f"0x{md5.hexdigest()}"
        
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(trading_pair, reference_price * Decimal(1 - CONSTANTS.MARKET_ORDER_SLIPPAGE))

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

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
        exchange_symbol = web_utils.convert_to_exchange_trading_pair(symbol)
        
        # Determine order type string
        order_type_str = "limit"
        time_in_force = "GTC"
        if order_type is OrderType.LIMIT_MAKER:
            time_in_force = "GTX"  # Post-only
        elif order_type is OrderType.MARKET:
            time_in_force = "IOC"
        
        is_mainnet = self._domain == CONSTANTS.DOMAIN
        
        # Sign the order using EIP-712
        signed_order = self._auth.sign_order(
            instrument=exchange_symbol,
            side="buy" if trade_type is TradeType.BUY else "sell",
            price=str(price),
            quantity=str(amount),
            order_type=order_type_str,
            time_in_force=time_in_force,
            client_order_id=order_id,
            is_mainnet=is_mainnet
        )
        
        # Add reduce-only flag if closing position
        if position_action == PositionAction.CLOSE:
            signed_order["reduceOnly"] = True
        
        order_result = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_URL,
            data=signed_order,
            is_auth_required=True)
        
        if order_result.get("error"):
            error_msg = order_result.get("error", {}).get("message", str(order_result.get("error")))
            raise IOError(f"Error submitting order {order_id}: {error_msg}")
        
        order_data = order_result.get("data", order_result)
        exchange_order_id = str(order_data.get("orderId", order_data.get("id", "")))
        
        return (exchange_order_id, self.current_timestamp)

    async def _update_trade_history(self):
        orders = list(self._order_tracker.all_fillable_orders.values())
        all_fillable_orders = self._order_tracker.all_fillable_orders_by_exchange_order_id
        
        if len(orders) > 0:
            try:
                all_fills_response = await self._api_get(
                    path_url=CONSTANTS.USER_TRADES_URL,
                    is_auth_required=True)
                
                trades = all_fills_response.get("data", [])
                for trade_fill in trades:
                    self._process_trade_rs_event_message(order_fill=trade_fill, all_fillable_order=all_fillable_orders)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(
                    f"Failed to fetch trade updates. Error: {request_error}",
                    exc_info=request_error,
                )

    def _process_trade_rs_event_message(self, order_fill: Dict[str, Any], all_fillable_order):
        exchange_order_id = str(order_fill.get("orderId", ""))
        fillable_order = all_fillable_order.get(exchange_order_id)
        
        if fillable_order is not None:
            fee_asset = fillable_order.quote_asset
            side = order_fill.get("side", "").lower()
            position_action = PositionAction.OPEN if "open" in side else PositionAction.CLOSE
            
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(str(order_fill.get("fee", 0))), token=fee_asset)]
            )

            trade_update = TradeUpdate(
                trade_id=str(order_fill.get("tradeId", order_fill.get("id", ""))),
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=fillable_order.trading_pair,
                fee=fee,
                fill_base_amount=Decimal(str(order_fill.get("quantity", order_fill.get("size", 0)))),
                fill_quote_amount=Decimal(str(order_fill.get("price", 0))) * Decimal(str(order_fill.get("quantity", order_fill.get("size", 0)))),
                fill_price=Decimal(str(order_fill.get("price", 0))),
                fill_timestamp=order_fill.get("timestamp", time.time() * 1000) / 1000,
            )

            self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        pass

    async def _handle_update_error_for_active_order(self, order: InFlightOrder, error: Exception):
        try:
            raise error
        except (asyncio.TimeoutError, KeyError):
            self.logger().debug(
                f"Tracked order {order.client_order_id} does not have an exchange id. "
                f"Attempting fetch in next polling interval."
            )
            await self._order_tracker.process_order_not_found(order.client_order_id)
        except asyncio.CancelledError:
            raise
        except Exception as request_error:
            self.logger().warning(
                f"Error fetching status update for the active order {order.client_order_id}: {request_error}.",
            )
            await self._order_tracker.process_order_not_found(order.client_order_id)

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        client_order_id = tracked_order.client_order_id
        try:
            if tracked_order.exchange_order_id:
                exchange_order_id = tracked_order.exchange_order_id
            else:
                exchange_order_id = await tracked_order.get_exchange_order_id()
        except asyncio.TimeoutError:
            exchange_order_id = None
        
        order_response = await self._api_get(
            path_url=CONSTANTS.ORDER_STATUS_URL,
            params={"orderId": exchange_order_id or client_order_id},
            is_auth_required=True)
        
        order_data = order_response.get("data", order_response)
        current_state = order_data.get("status", "").lower()
        
        _order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_data.get("updatedAt", order_data.get("timestamp", time.time() * 1000)) / 1000,
            new_state=CONSTANTS.ORDER_STATE.get(current_state, CONSTANTS.ORDER_STATE["open"]),
            client_order_id=order_data.get("clientOrderId", client_order_id),
            exchange_order_id=str(order_data.get("orderId", order_data.get("id", exchange_order_id))),
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
                    app_warning_msg="Could not fetch user events from EVEDEX. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        user_channels = [
            CONSTANTS.WS_USER_ORDERS_CHANNEL,
            CONSTANTS.WS_USER_TRADES_CHANNEL,
            CONSTANTS.WS_USER_POSITIONS_CHANNEL,
            CONSTANTS.WS_USER_BALANCE_CHANNEL,
        ]
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    push_data = event_message.get("push", {})
                    channel = push_data.get("channel", "")
                    data = push_data.get("pub", {}).get("data", {})
                elif event_message is asyncio.CancelledError:
                    raise asyncio.CancelledError
                else:
                    raise Exception(event_message)
                
                if not any(ch in channel for ch in user_channels):
                    continue
                
                if CONSTANTS.WS_USER_ORDERS_CHANNEL in channel:
                    self._process_order_message(data)
                elif CONSTANTS.WS_USER_TRADES_CHANNEL in channel:
                    await self._process_trade_message(data)
                elif CONSTANTS.WS_USER_BALANCE_CHANNEL in channel:
                    self._process_balance_message(data)
                elif CONSTANTS.WS_USER_POSITIONS_CHANNEL in channel:
                    self._process_position_message(data)
                    
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        exchange_order_id = str(trade.get("orderId", ""))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        if tracked_order is None:
            all_orders = self._order_tracker.all_fillable_orders
            for k, v in all_orders.items():
                await v.get_exchange_order_id()
            _cli_tracked_orders = [o for o in all_orders.values() if exchange_order_id == o.exchange_order_id]
            if not _cli_tracked_orders:
                self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
                return
            tracked_order = _cli_tracked_orders[0]
        
        fee_asset = tracked_order.quote_asset
        side = trade.get("side", "").lower()
        position_action = PositionAction.OPEN if "open" in side else PositionAction.CLOSE
        
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=Decimal(str(trade.get("fee", 0))), token=fee_asset)]
        )
        
        trade_update = TradeUpdate(
            trade_id=str(trade.get("tradeId", trade.get("id", ""))),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=trade.get("timestamp", time.time() * 1000) / 1000,
            fill_price=Decimal(str(trade.get("price", 0))),
            fill_base_amount=Decimal(str(trade.get("quantity", trade.get("size", 0)))),
            fill_quote_amount=Decimal(str(trade.get("price", 0))) * Decimal(str(trade.get("quantity", trade.get("size", 0)))),
            fee=fee,
        )
        self._order_tracker.process_trade_update(trade_update)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        client_order_id = str(order_msg.get("clientOrderId", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return
        
        current_state = order_msg.get("status", "").lower()
        tracked_order.update_exchange_order_id(str(order_msg.get("orderId", order_msg.get("id", ""))))
        
        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_msg.get("updatedAt", order_msg.get("timestamp", time.time() * 1000)) / 1000,
            new_state=CONSTANTS.ORDER_STATE.get(current_state, CONSTANTS.ORDER_STATE["open"]),
            client_order_id=client_order_id,
            exchange_order_id=str(order_msg.get("orderId", order_msg.get("id", ""))),
        )
        self._order_tracker.process_order_update(order_update=order_update)

    def _process_balance_message(self, balance_data: Dict[str, Any]):
        # Update account balances from WebSocket message
        pass

    def _process_position_message(self, position_data: Dict[str, Any]):
        # Update positions from WebSocket message
        pass

    async def _format_trading_rules(self, exchange_info_dict: Dict) -> List[TradingRule]:
        instruments = exchange_info_dict.get("data", exchange_info_dict.get("instruments", []))
        return_val = []
        
        for instrument in instruments:
            try:
                symbol = instrument.get("symbol", "")
                trading_pair = web_utils.convert_from_exchange_trading_pair(symbol)
                
                # Store instrument info for later use
                self.symbol_to_instrument[symbol] = instrument
                
                tick_size = Decimal(str(instrument.get("tickSize", instrument.get("priceStep", "0.01"))))
                step_size = Decimal(str(instrument.get("stepSize", instrument.get("quantityStep", "0.001"))))
                min_order_size = Decimal(str(instrument.get("minOrderSize", instrument.get("minQuantity", "0.001"))))
                
                collateral_token = CONSTANTS.CURRENCY
                
                return_val.append(
                    TradingRule(
                        trading_pair,
                        min_base_amount_increment=step_size,
                        min_price_increment=tick_size,
                        min_order_size=min_order_size,
                        buy_order_collateral_token=collateral_token,
                        sell_order_collateral_token=collateral_token,
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing trading pair rule {instrument}. Skipping.", exc_info=True)
        
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict):
        mapping = bidict()
        instruments = exchange_info.get("data", exchange_info.get("instruments", []))
        
        for symbol_data in filter(web_utils.is_exchange_information_valid, instruments):
            exchange_symbol = symbol_data.get("symbol", "")
            trading_pair = web_utils.convert_from_exchange_trading_pair(exchange_symbol)
            
            if trading_pair in mapping.inverse:
                self._resolve_trading_pair_symbols_duplicate(mapping, exchange_symbol, trading_pair.split("-")[0], trading_pair.split("-")[1])
            else:
                mapping[exchange_symbol] = trading_pair
        
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        symbol = web_utils.convert_to_exchange_trading_pair(exchange_symbol)
        
        response = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_URL,
            params={"symbol": symbol})
        
        ticker_data = response.get("data", response)
        return float(ticker_data.get("lastPrice", ticker_data.get("price", 0)))

    async def _update_balances(self):
        try:
            response = await self._api_get(
                path_url=CONSTANTS.BALANCE_URL,
                is_auth_required=True)
            
            balances = response.get("data", response.get("balances", []))
            
            self._account_available_balances.clear()
            self._account_balances.clear()
            
            for balance in balances:
                asset = balance.get("asset", balance.get("currency", ""))
                total = Decimal(str(balance.get("total", balance.get("balance", 0))))
                available = Decimal(str(balance.get("available", balance.get("free", 0))))
                
                self._account_balances[asset] = total
                self._account_available_balances[asset] = available
                
        except Exception as e:
            self.logger().warning(f"Error updating balances: {e}")

    async def _update_positions(self):
        try:
            response = await self._api_get(
                path_url=CONSTANTS.POSITIONS_URL,
                is_auth_required=True)
            
            positions = response.get("data", response.get("positions", []))
            
            for position_data in positions:
                symbol = position_data.get("symbol", "")
                trading_pair = web_utils.convert_from_exchange_trading_pair(symbol)
                
                if trading_pair not in self._trading_pairs:
                    continue
                
                position_side = PositionSide.LONG if float(position_data.get("size", 0)) > 0 else PositionSide.SHORT
                amount = abs(Decimal(str(position_data.get("size", position_data.get("quantity", 0)))))
                entry_price = Decimal(str(position_data.get("entryPrice", position_data.get("avgPrice", 0))))
                unrealized_pnl = Decimal(str(position_data.get("unrealizedPnl", 0)))
                leverage = Decimal(str(position_data.get("leverage", 1)))
                
                if amount > 0:
                    pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
                    position = Position(
                        trading_pair=trading_pair,
                        position_side=position_side,
                        unrealized_pnl=unrealized_pnl,
                        entry_price=entry_price,
                        amount=amount,
                        leverage=leverage,
                    )
                    self._perpetual_trading.set_position(pos_key, position)
                    
        except Exception as e:
            self.logger().warning(f"Error updating positions: {e}")

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        symbol = web_utils.convert_to_exchange_trading_pair(exchange_symbol)
        
        try:
            response = await self._api_post(
                path_url=CONSTANTS.SET_LEVERAGE_URL,
                data={
                    "symbol": symbol,
                    "leverage": leverage
                },
                is_auth_required=True)
            
            if response.get("error"):
                return False, str(response.get("error"))
            
            return True, ""
        except Exception as e:
            return False, str(e)
