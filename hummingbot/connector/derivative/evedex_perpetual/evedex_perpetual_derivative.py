import asyncio
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
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
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
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = evedex_perpetual_api_key
        self._api_secret = evedex_perpetual_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self.market_to_id: Dict[str, str] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[EvedexPerpetualAuth]:
        if self._trading_required:
            return EvedexPerpetualAuth(self._api_key, self._api_secret)
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

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

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
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

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
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_orders(self):
        tracked_orders = list(self._order_tracker.active_orders.values())
        if not tracked_orders:
            return
        for order in tracked_orders:
            try:
                order_update = await self._request_order_status(order)
                self._order_tracker.process_order_update(order_update)
            except Exception as e:
                self.logger().warning(f"Error fetching order status for {order.client_order_id}: {e}")

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        cancel_data = {
            "orderId": tracked_order.exchange_order_id or order_id,
            "market": symbol,
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=cancel_data,
            is_auth_required=True)
        if cancel_result.get("status") == "error":
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f'{cancel_result.get("message", "Cancel failed")}')
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
        order_type_str = "LIMIT"
        if order_type == OrderType.MARKET:
            order_type_str = "MARKET"
        elif order_type == OrderType.LIMIT_MAKER:
            order_type_str = "LIMIT_MAKER"

        api_params = {
            "market": symbol,
            "side": "BUY" if trade_type == TradeType.BUY else "SELL",
            "type": order_type_str,
            "quantity": str(amount),
            "nonce": str(uuid.uuid4()),
            "reduceOnly": position_action == PositionAction.CLOSE,
        }
        if order_type.is_limit_type():
            api_params["price"] = str(price)
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC

        order_result = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_URL,
            data=api_params,
            is_auth_required=True)

        if order_result.get("status") == "error":
            raise IOError(f"Error submitting order: {order_result.get('message')}")

        data = order_result.get("data", order_result)
        exchange_order_id = str(data.get("orderId", data.get("id", "")))
        return exchange_order_id, self.current_timestamp

    async def _update_trade_history(self):
        orders = list(self._order_tracker.all_fillable_orders.values())
        all_fillable_orders = self._order_tracker.all_fillable_orders_by_exchange_order_id
        if not orders:
            return
        try:
            response = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                is_auth_required=True)
            trades = response.get("data", response) if isinstance(response, dict) else response
            for trade in trades:
                exchange_order_id = str(trade.get("orderId", ""))
                fillable_order = all_fillable_orders.get(exchange_order_id)
                if fillable_order:
                    self._process_trade_event(trade, fillable_order)
        except Exception as e:
            self.logger().warning(f"Failed to fetch trade updates: {e}")

    def _process_trade_event(self, trade: Dict[str, Any], order: InFlightOrder):
        fee_asset = order.quote_asset
        position_action = PositionAction.OPEN if trade.get("side", "").upper() == order.trade_type.name else PositionAction.CLOSE
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=Decimal(str(trade.get("fee", 0))), token=fee_asset)]
        )
        trade_update = TradeUpdate(
            trade_id=str(trade.get("id", trade.get("tradeId", ""))),
            client_order_id=order.client_order_id,
            exchange_order_id=str(trade.get("orderId", "")),
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(str(trade.get("quantity", trade.get("size", 0)))),
            fill_quote_amount=Decimal(str(trade.get("price", 0))) * Decimal(str(trade.get("quantity", trade.get("size", 0)))),
            fill_price=Decimal(str(trade.get("price", 0))),
            fill_timestamp=trade.get("timestamp", time.time() * 1000) / 1000,
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        pass

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = tracked_order.exchange_order_id or await tracked_order.get_exchange_order_id()
        response = await self._api_get(
            path_url=CONSTANTS.ORDER_URL,
            params={"orderId": exchange_order_id},
            is_auth_required=True)
        data = response.get("data", response)
        status = data.get("status", "").upper()
        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=data.get("updatedAt", time.time() * 1000) / 1000,
            new_state=CONSTANTS.ORDER_STATE.get(status, tracked_order.current_state),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(data.get("orderId", data.get("id", exchange_order_id))),
        )
        return order_update

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unknown error. Retrying after 1 seconds.", exc_info=True)
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message.get("channel", "")
                data = event_message.get("data", {})
                if "orders" in channel:
                    self._process_order_message(data)
                elif "positions" in channel:
                    await self._process_position_message(data)
                elif "balance" in channel:
                    self._process_balance_message(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener.", exc_info=True)
                await self._sleep(5.0)

    def _process_order_message(self, order_data: Dict[str, Any]):
        client_order_id = order_data.get("clientOrderId", order_data.get("nonce", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            return
        status = order_data.get("status", "").upper()
        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_data.get("updatedAt", time.time() * 1000) / 1000,
            new_state=CONSTANTS.ORDER_STATE.get(status, tracked_order.current_state),
            client_order_id=client_order_id,
            exchange_order_id=str(order_data.get("orderId", order_data.get("id", ""))),
        )
        self._order_tracker.process_order_update(order_update)

    async def _process_position_message(self, position_data: Dict[str, Any]):
        positions = position_data if isinstance(position_data, list) else [position_data]
        for pos in positions:
            symbol = pos.get("market", pos.get("symbol", ""))
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
            except KeyError:
                continue
            amount = Decimal(str(pos.get("size", pos.get("quantity", 0))))
            position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
            if amount != 0:
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=Decimal(str(pos.get("unrealizedPnl", 0))),
                    entry_price=Decimal(str(pos.get("entryPrice", 0))),
                    amount=amount,
                    leverage=Decimal(str(pos.get("leverage", 1)))
                )
                self._perpetual_trading.set_position(pos_key, position)
            else:
                self._perpetual_trading.remove_position(pos_key)

    def _process_balance_message(self, balance_data: Dict[str, Any]):
        balances = balance_data if isinstance(balance_data, list) else [balance_data]
        for bal in balances:
            asset = bal.get("asset", bal.get("currency", CONSTANTS.CURRENCY))
            self._account_balances[asset] = Decimal(str(bal.get("total", bal.get("balance", 0))))
            self._account_available_balances[asset] = Decimal(str(bal.get("available", bal.get("free", 0))))

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules = exchange_info_dict.get("data", exchange_info_dict)
        if isinstance(rules, dict):
            rules = rules.get("markets", [rules])
        return_val = []
        for rule in rules:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(rule.get("symbol", rule.get("market", "")))
                min_order_size = Decimal(str(rule.get("minOrderSize", rule.get("minQuantity", "0.001"))))
                step_size = Decimal(str(rule.get("quantityStep", rule.get("stepSize", "0.001"))))
                tick_size = Decimal(str(rule.get("priceStep", rule.get("tickSize", "0.01"))))
                min_notional = Decimal(str(rule.get("minNotional", "5")))
                collateral_token = rule.get("quoteCurrency", rule.get("settleCurrency", CONSTANTS.CURRENCY))
                self.market_to_id[rule.get("symbol", rule.get("market", ""))] = rule.get("id", "")
                return_val.append(TradingRule(
                    trading_pair,
                    min_order_size=min_order_size,
                    min_price_increment=tick_size,
                    min_base_amount_increment=step_size,
                    min_notional_size=min_notional,
                    buy_order_collateral_token=collateral_token,
                    sell_order_collateral_token=collateral_token,
                ))
            except Exception as e:
                self.logger().error(f"Error parsing trading pair rule: {e}", exc_info=True)
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        data = exchange_info.get("data", exchange_info)
        markets = data.get("markets", [data]) if isinstance(data, dict) else data
        for market in markets:
            if not web_utils.is_exchange_information_valid(market):
                continue
            symbol = market.get("symbol", market.get("market", ""))
            base = market.get("baseCurrency", market.get("baseAsset", ""))
            quote = market.get("quoteCurrency", market.get("quoteAsset", CONSTANTS.CURRENCY))
            trading_pair = combine_to_hb_trading_pair(base, quote)
            if trading_pair not in mapping.inverse:
                mapping[symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_URL,
            params={"market": symbol})
        data = response.get("data", response)
        return float(data.get("lastPrice", data.get("price", 0)))

    async def _update_balances(self):
        response = await self._api_get(path_url=CONSTANTS.ACCOUNT_INFO_URL, is_auth_required=True)
        data = response.get("data", response)
        balances = data.get("balances", [data])
        for bal in balances:
            asset = bal.get("asset", bal.get("currency", CONSTANTS.CURRENCY))
            self._account_balances[asset] = Decimal(str(bal.get("total", bal.get("balance", 0))))
            self._account_available_balances[asset] = Decimal(str(bal.get("available", bal.get("free", 0))))

    async def _update_positions(self):
        response = await self._api_get(path_url=CONSTANTS.POSITION_INFORMATION_URL, is_auth_required=True)
        data = response.get("data", response)
        positions = data if isinstance(data, list) else data.get("positions", [])
        for pos in positions:
            symbol = pos.get("market", pos.get("symbol", ""))
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
            except KeyError:
                continue
            amount = Decimal(str(pos.get("size", pos.get("quantity", 0))))
            position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
            if amount != 0:
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=Decimal(str(pos.get("unrealizedPnl", 0))),
                    entry_price=Decimal(str(pos.get("entryPrice", 0))),
                    amount=amount,
                    leverage=Decimal(str(pos.get("leverage", 1)))
                )
                self._perpetual_trading.set_position(pos_key, position)
            else:
                self._perpetual_trading.remove_position(pos_key)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return PositionMode.ONEWAY

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode != PositionMode.ONEWAY:
            return False, "EVEDEX only supports ONEWAY position mode"
        return True, ""

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {"market": symbol, "leverage": leverage}
        try:
            response = await self._api_post(
                path_url=CONSTANTS.SET_LEVERAGE_URL,
                data=params,
                is_auth_required=True)
            if response.get("status") == "error":
                return False, response.get("message", "Failed to set leverage")
            return True, ""
        except Exception as e:
            return False, str(e)

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.GET_INCOME_HISTORY_URL,
            params={"market": symbol},
            is_auth_required=True)
        data = response.get("data", response)
        payments = data if isinstance(data, list) else []
        if not payments:
            return 0, Decimal("-1"), Decimal("-1")
        payment = payments[0]
        timestamp = int(payment.get("timestamp", 0))
        funding_rate = Decimal(str(payment.get("fundingRate", 0)))
        amount = Decimal(str(payment.get("payment", payment.get("amount", 0))))
        return timestamp, funding_rate, amount
