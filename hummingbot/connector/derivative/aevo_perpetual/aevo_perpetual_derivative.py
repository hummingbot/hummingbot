import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.aevo_perpetual import (
    aevo_perpetual_constants as CONSTANTS,
    aevo_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_order_book_data_source import (
    AevoPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_user_stream_data_source import (
    AevoPerpetualUserStreamDataSource,
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
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class AevoPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            aevo_perpetual_api_key: str = None,
            aevo_perpetual_api_secret: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.aevo_perpetual_api_key = aevo_perpetual_api_key
        self.aevo_perpetual_api_secret = aevo_perpetual_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = PositionMode.ONEWAY
        self._last_trade_history_timestamp = None
        super().__init__()

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> AevoPerpetualAuth:
        return AevoPerpetualAuth(
            self.aevo_perpetual_api_key,
            self.aevo_perpetual_api_secret,
            self._time_synchronizer
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
        return 600

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return AevoPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return AevoPerpetualUserStreamDataSource(
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
        pass

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_fills_from_trades(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {"order_id": order_id}
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            params=api_params,
            is_auth_required=True)
        if cancel_result.get("error"):
            raise IOError(f"Error canceling order: {cancel_result.get('error')}")
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
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        side = "buy" if trade_type is TradeType.BUY else "sell"

        api_params = {
            "instrument_name": symbol,
            "side": side,
            "amount": str(amount),
            "type": "market" if order_type is OrderType.MARKET else "limit",
            "client_order_id": order_id,
        }

        if order_type.is_limit_type():
            api_params["price"] = str(price)
            api_params["time_in_force"] = CONSTANTS.TIME_IN_FORCE_GTC

        order_result = await self._api_post(
            path_url=CONSTANTS.ORDER_URL,
            data=api_params,
            is_auth_required=True)

        if order_result.get("error"):
            raise IOError(f"Error placing order: {order_result.get('error')}")

        exchange_order_id = str(order_result.get("order_id", order_result.get("id", "")))
        transact_time = float(order_result.get("timestamp", time.time() * 1000)) / 1000

        return exchange_order_id, transact_time

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            exchange_order_id = await order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                params={"instrument_name": trading_pair},
                is_auth_required=True)

            fills = all_fills_response if isinstance(all_fills_response, list) else all_fills_response.get("trades", [])
            for trade in fills:
                trade_order_id = str(trade.get("order_id", ""))
                if trade_order_id == exchange_order_id:
                    fee_amount = Decimal(str(trade.get("fee", "0")))
                    fee_asset = trade.get("fee_currency", "USDC")
                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=PositionAction.OPEN,
                        percent_token=fee_asset,
                        flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)]
                    )
                    trade_update = TradeUpdate(
                        trade_id=str(trade.get("trade_id", "")),
                        client_order_id=order.client_order_id,
                        exchange_order_id=trade_order_id,
                        trading_pair=order.trading_pair,
                        fill_timestamp=float(trade.get("timestamp", time.time() * 1000)) / 1000,
                        fill_price=Decimal(str(trade.get("price", "0"))),
                        fill_base_amount=Decimal(str(trade.get("amount", "0"))),
                        fill_quote_amount=Decimal(str(trade.get("price", "0"))) * Decimal(str(trade.get("amount", "0"))),
                        fee=fee,
                    )
                    trade_updates.append(trade_update)
        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id}")
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        order_update = await self._api_get(
            path_url=f"{CONSTANTS.ORDER_URL}/{tracked_order.exchange_order_id}",
            is_auth_required=True)

        if order_update.get("error"):
            raise IOError(f"Error fetching order status: {order_update.get('error')}")

        new_state = CONSTANTS.ORDER_STATE.get(order_update.get("status", ""), tracked_order.current_state)
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(order_update.get("timestamp", time.time() * 1000)) / 1000,
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_update.get("order_id", "")),
        )

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
                    app_warning_msg="Could not fetch user events from Aevo. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)
                await self._sleep(5.0)

    async def _process_user_stream_event(self, event_message: Dict[str, Any]):
        channel = event_message.get("channel", "")

        if "orders" in channel:
            data = event_message.get("data", {})
            client_order_id = data.get("client_order_id")
            tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
            if tracked_order is not None:
                new_state = CONSTANTS.ORDER_STATE.get(data.get("status", ""), tracked_order.current_state)
                order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=float(data.get("timestamp", time.time() * 1000)) / 1000,
                    new_state=new_state,
                    client_order_id=client_order_id,
                    exchange_order_id=str(data.get("order_id", "")),
                )
                self._order_tracker.process_order_update(order_update)

        elif "fills" in channel:
            data = event_message.get("data", {})
            client_order_id = data.get("client_order_id")
            tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
            if tracked_order is not None:
                fee_amount = Decimal(str(data.get("fee", "0")))
                fee_asset = data.get("fee_currency", "USDC")
                fee = TradeFeeBase.new_perpetual_fee(
                    fee_schema=self.trade_fee_schema(),
                    position_action=PositionAction.OPEN,
                    percent_token=fee_asset,
                    flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
                )
                trade_update = TradeUpdate(
                    trade_id=str(data.get("trade_id", "")),
                    client_order_id=client_order_id,
                    exchange_order_id=str(data.get("order_id", "")),
                    trading_pair=tracked_order.trading_pair,
                    fill_timestamp=float(data.get("timestamp", time.time() * 1000)) / 1000,
                    fill_price=Decimal(str(data.get("price", "0"))),
                    fill_base_amount=Decimal(str(data.get("amount", "0"))),
                    fill_quote_amount=Decimal(str(data.get("price", "0"))) * Decimal(str(data.get("amount", "0"))),
                    fee=fee,
                )
                self._order_tracker.process_trade_update(trade_update)

        elif "positions" in channel:
            data = event_message.get("data", {})
            positions = data if isinstance(data, list) else [data]
            for position_data in positions:
                try:
                    symbol = position_data.get("instrument_name", "")
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
                    amount = Decimal(str(position_data.get("amount", "0")))
                    side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
                    pos_key = self._perpetual_trading.position_key(trading_pair, side)
                    if amount != 0:
                        position = Position(
                            trading_pair=trading_pair,
                            position_side=side,
                            unrealized_pnl=Decimal(str(position_data.get("unrealized_pnl", "0"))),
                            entry_price=Decimal(str(position_data.get("average_price", "0"))),
                            amount=abs(amount),
                            leverage=Decimal(str(position_data.get("leverage", "1"))),
                        )
                        self._perpetual_trading.set_position(pos_key, position)
                    else:
                        self._perpetual_trading.remove_position(pos_key)
                except KeyError:
                    continue

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules = exchange_info_dict if isinstance(exchange_info_dict, list) else exchange_info_dict.get("markets", [])
        return_val = []
        for rule in rules:
            try:
                if web_utils.is_exchange_information_valid(rule):
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["instrument_name"])
                    min_order_size = Decimal(str(rule.get("min_order_size", "0.001")))
                    tick_size = Decimal(str(rule.get("tick_size", "0.01")))
                    step_size = Decimal(str(rule.get("amount_step", "0.001")))
                    min_notional = Decimal(str(rule.get("min_notional", "1")))
                    collateral_token = rule.get("quote_currency", "USDC")
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
                self.logger().error(f"Error parsing trading pair rule {rule}. Error: {e}. Skipping...", exc_info=True)
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        markets = exchange_info if isinstance(exchange_info, list) else exchange_info.get("markets", [])
        for symbol_data in filter(web_utils.is_exchange_information_valid, markets):
            exchange_symbol = symbol_data["instrument_name"]
            base = symbol_data.get("base_currency", exchange_symbol.split("-")[0])
            quote = symbol_data.get("quote_currency", "USDC")
            trading_pair = combine_to_hb_trading_pair(base, quote)
            if trading_pair not in mapping.inverse:
                mapping[exchange_symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"instrument_name": exchange_symbol}
        response = await self._api_get(path_url=CONSTANTS.TICKER_PRICE_URL, params=params)
        price = float(response.get("last_price", response.get("mark_price", 0)))
        return price

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self._api_get(path_url=CONSTANTS.ACCOUNT_INFO_URL, is_auth_required=True)
        balances = account_info.get("balances", [account_info])
        if not isinstance(balances, list):
            balances = [balances]
        for balance in balances:
            asset_name = balance.get("currency", balance.get("asset", "USDC"))
            available_balance = Decimal(str(balance.get("available", balance.get("balance", "0"))))
            total_balance = Decimal(str(balance.get("balance", balance.get("equity", "0"))))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        positions = await self._api_get(path_url=CONSTANTS.POSITION_INFORMATION_URL, is_auth_required=True)
        positions_list = positions if isinstance(positions, list) else positions.get("positions", [])
        for position in positions_list:
            try:
                symbol = position.get("instrument_name", "")
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
                amount = Decimal(str(position.get("amount", "0")))
                position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
                unrealized_pnl = Decimal(str(position.get("unrealized_pnl", "0")))
                entry_price = Decimal(str(position.get("average_price", "0")))
                leverage = Decimal(str(position.get("leverage", "1")))
                pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
                if amount != 0:
                    _position = Position(
                        trading_pair=trading_pair,
                        position_side=position_side,
                        unrealized_pnl=unrealized_pnl,
                        entry_price=entry_price,
                        amount=abs(amount),
                        leverage=leverage
                    )
                    self._perpetual_trading.set_position(pos_key, _position)
                else:
                    self._perpetual_trading.remove_position(pos_key)
            except KeyError:
                continue

    async def _update_order_fills_from_trades(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            trading_pairs_to_order_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {})
            for order in self._order_tracker.active_orders.values():
                trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order
            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [
                self._api_get(
                    path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                    params={"instrument_name": await self.exchange_symbol_associated_to_pair(trading_pair=tp)},
                    is_auth_required=True,
                )
                for tp in trading_pairs
            ]
            results = await safe_gather(*tasks, return_exceptions=True)
            for trades, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map.get(trading_pair)
                if isinstance(trades, Exception):
                    self.logger().network(f"Error fetching trades update for {trading_pair}: {trades}.")
                    continue
                trades_list = trades if isinstance(trades, list) else trades.get("trades", [])
                for trade in trades_list:
                    order_id = str(trade.get("order_id"))
                    if order_id in order_map:
                        tracked_order = order_map.get(order_id)
                        fee_amount = Decimal(str(trade.get("fee", "0")))
                        fee_asset = trade.get("fee_currency", "USDC")
                        fee = TradeFeeBase.new_perpetual_fee(
                            fee_schema=self.trade_fee_schema(),
                            position_action=PositionAction.OPEN,
                            percent_token=fee_asset,
                            flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)]
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade.get("trade_id", "")),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=order_id,
                            trading_pair=tracked_order.trading_pair,
                            fill_timestamp=float(trade.get("timestamp", time.time() * 1000)) / 1000,
                            fill_price=Decimal(str(trade.get("price", "0"))),
                            fill_base_amount=Decimal(str(trade.get("amount", "0"))),
                            fill_quote_amount=Decimal(str(trade.get("price", "0"))) * Decimal(str(trade.get("amount", "0"))),
                            fee=fee,
                        )
                        self._order_tracker.process_trade_update(trade_update)

    async def _update_order_status(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            tracked_orders = list(self._order_tracker.active_orders.values())
            tasks = [
                self._api_get(
                    path_url=f"{CONSTANTS.ORDER_URL}/{order.exchange_order_id}",
                    is_auth_required=True,
                )
                for order in tracked_orders
            ]
            results = await safe_gather(*tasks, return_exceptions=True)
            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._order_tracker.all_orders:
                    continue
                if isinstance(order_update, Exception) or order_update.get("error"):
                    error_msg = str(order_update) if isinstance(order_update, Exception) else order_update.get("error")
                    if CONSTANTS.ORDER_NOT_EXIST_MESSAGE in error_msg:
                        await self._order_tracker.process_order_not_found(client_order_id)
                    else:
                        self.logger().network(f"Error fetching status for order {client_order_id}: {error_msg}")
                    continue
                new_state = CONSTANTS.ORDER_STATE.get(order_update.get("status", ""), tracked_order.current_state)
                new_order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=float(order_update.get("timestamp", time.time() * 1000)) / 1000,
                    new_state=new_state,
                    client_order_id=client_order_id,
                    exchange_order_id=str(order_update.get("order_id", "")),
                )
                self._order_tracker.process_order_update(new_order_update)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return self._position_mode

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode != PositionMode.ONEWAY:
            return False, "Aevo only supports ONEWAY position mode"
        return True, ""

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {"instrument_name": symbol, "leverage": leverage}
        result = await self._api_post(
            path_url=CONSTANTS.SET_LEVERAGE_URL,
            data=params,
            is_auth_required=True,
        )
        if result.get("error"):
            return False, str(result.get("error"))
        return True, ""

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        payment_response = await self._api_get(
            path_url=CONSTANTS.GET_INCOME_HISTORY_URL,
            params={"instrument_name": exchange_symbol},
            is_auth_required=True,
        )
        payments = payment_response if isinstance(payment_response, list) else payment_response.get("funding", [])
        if len(payments) < 1:
            return 0, Decimal("-1"), Decimal("-1")
        sorted_payments = sorted(payments, key=lambda a: a.get("timestamp", 0), reverse=True)
        funding_payment = sorted_payments[0]
        payment = Decimal(str(funding_payment.get("payment", "0")))
        funding_rate = Decimal(str(funding_payment.get("funding_rate", "0")))
        timestamp = int(funding_payment.get("timestamp", 0))
        if payment == Decimal("0"):
            return 0, Decimal("-1"), Decimal("-1")
        return timestamp, funding_rate, payment
