import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.architect_perpetual.architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_api_order_book_data_source import ArchitectPerpetualAPIOrderBookDataSource
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_user_stream_data_source import ArchitectPerpetualUserStreamDataSource
from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class ArchitectPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    def __init__(
        self,
        architect_perpetual_api_key: str,
        architect_perpetual_api_secret: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = architect_perpetual_api_key
        self._api_secret = architect_perpetual_api_secret
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._domain = domain
        self._auth = ArchitectPerpetualAuth(api_key=self._api_key, api_secret=self._api_secret, time_provider=self._time_synchronizer)
        super().__init__()

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> AuthBase:
        return self._auth

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
        return CONSTANTS.MARKETS_ENDPOINT

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.MARKETS_ENDPOINT

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.MARKETS_ENDPOINT

    @property
    def trading_pairs(self) -> List[str]:
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

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules.get(trading_pair)
        if trading_rule:
            return trading_rule.buy_order_collateral_token
        return CONSTANTS.DEFAULT_QUOTE_ASSET

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules.get(trading_pair)
        if trading_rule:
            return trading_rule.sell_order_collateral_token
        return CONSTANTS.DEFAULT_QUOTE_ASSET

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        error_description = str(request_exception)
        return "timestamp" in error_description.lower() and "invalid" in error_description.lower()

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, time_synchronizer=self._time_synchronizer, domain=self._domain, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ArchitectPerpetualAPIOrderBookDataSource(trading_pairs=self._trading_pairs, connector=self, api_factory=self._web_assistants_factory, domain=self.domain)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ArchitectPerpetualUserStreamDataSource(auth=self._auth, trading_pairs=self._trading_pairs, connector=self, api_factory=self._web_assistants_factory, domain=self.domain)

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType, position_action: PositionAction, amount: Decimal, price: Decimal = s_decimal_NaN, is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or False
        return build_perpetual_trade_fee(self.name, is_maker, base_currency=base_currency, quote_currency=quote_currency, order_type=order_type, order_side=order_side, position_action=position_action, amount=amount, price=price)

    async def _update_trading_fees(self) -> None:
        pass

    async def _status_polling_loop_fetch_updates(self) -> None:
        await safe_gather(self._update_order_fills_from_trades(), self._update_order_status(), self._update_balances(), self._update_positions())

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {"order_id": order_id, "symbol": symbol}
        try:
            cancel_result = await self._api_delete(path_url=CONSTANTS.ORDERS_ENDPOINT, params=api_params, is_auth_required=True)
            if cancel_result.get("status") in ["CANCELED", "CANCELLED"]:
                return True
            if cancel_result.get("error") == CONSTANTS.ORDER_NOT_FOUND_ERROR:
                await self._order_tracker.process_order_not_found(order_id)
                return False
        except Exception as e:
            if CONSTANTS.ORDER_NOT_FOUND_ERROR in str(e):
                await self._order_tracker.process_order_not_found(order_id)
            raise
        return False

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType, order_type: OrderType, price: Decimal, position_action: PositionAction = PositionAction.NIL, **kwargs) -> Tuple[str, float]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {"symbol": symbol, "dir": "BUY" if trade_type is TradeType.BUY else "SELL", "quantity": str(amount), "client_order_id": order_id}
        if order_type == OrderType.LIMIT:
            api_params["limit_price"] = str(price)
            api_params["time_in_force"] = CONSTANTS.TIME_IN_FORCE_GTC
        elif order_type == OrderType.MARKET:
            api_params["type"] = "MARKET"
        try:
            order_result = await self._api_post(path_url=CONSTANTS.ORDERS_ENDPOINT, data=api_params, is_auth_required=True)
            exchange_order_id = str(order_result.get("order_id", order_result.get("id", "")))
            transact_time = order_result.get("timestamp", time.time())
            if isinstance(transact_time, int) and transact_time > 1e12:
                transact_time = transact_time / 1000.0
            return exchange_order_id, transact_time
        except Exception as e:
            if "server overloaded" in str(e).lower():
                return "UNKNOWN", time.time()
            raise

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            exchange_order_id = await order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(path_url=CONSTANTS.TRADES_ENDPOINT, params={"symbol": trading_pair}, is_auth_required=True)
            for trade in all_fills_response:
                if str(trade.get("order_id")) == exchange_order_id:
                    fee_asset = trade.get("fee_asset", CONSTANTS.DEFAULT_QUOTE_ASSET)
                    fee_amount = Decimal(str(trade.get("fee", 0)))
                    trade_update = TradeUpdate(
                        trade_id=str(trade.get("id", trade.get("trade_id"))),
                        client_order_id=order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=order.trading_pair,
                        fee=TokenAmount(token=fee_asset, amount=fee_amount),
                        fill_base_amount=Decimal(str(trade.get("quantity", 0))),
                        fill_quote_amount=Decimal(str(trade.get("price", 0))) * Decimal(str(trade.get("quantity", 0))),
                        fill_price=Decimal(str(trade.get("price", 0))),
                        fill_timestamp=trade.get("timestamp", time.time()),
                    )
                    trade_updates.append(trade_update)
        except Exception as e:
            self.logger().error(f"Error fetching trades for order {order.client_order_id}: {e}")
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        order_response = await self._api_get(path_url=f"{CONSTANTS.ORDERS_ENDPOINT}/{exchange_order_id}", params={"symbol": symbol}, is_auth_required=True)
        order_status = order_response.get("status", "UNKNOWN")
        new_state = CONSTANTS.ORDER_STATE.get(order_status, OrderState.OPEN)
        return OrderUpdate(client_order_id=tracked_order.client_order_id, exchange_order_id=exchange_order_id, trading_pair=tracked_order.trading_pair, update_timestamp=order_response.get("timestamp", time.time()), new_state=new_state)

    async def _update_balances(self) -> None:
        try:
            account_info = await self._api_get(path_url=CONSTANTS.BALANCES_ENDPOINT, is_auth_required=True)
            self._account_available_balances.clear()
            self._account_balances.clear()
            for asset_info in account_info.get("balances", []):
                asset = asset_info.get("asset", asset_info.get("currency", ""))
                free = Decimal(str(asset_info.get("available", asset_info.get("free", 0))))
                total = Decimal(str(asset_info.get("total", asset_info.get("balance", 0))))
                self._account_available_balances[asset] = free
                self._account_balances[asset] = total
        except Exception as e:
            self.logger().error(f"Error updating balances: {e}")

    async def _update_positions(self) -> None:
        try:
            positions_response = await self._api_get(path_url=CONSTANTS.POSITIONS_ENDPOINT, is_auth_required=True)
            for position_data in positions_response.get("positions", positions_response):
                trading_pair = position_data.get("symbol", "")
                if "/" in trading_pair:
                    trading_pair = web_utils.convert_from_exchange_trading_pair(trading_pair)
                if trading_pair not in self._trading_pairs:
                    continue
                amount = Decimal(str(position_data.get("quantity", position_data.get("size", 0))))
                if amount == s_decimal_0:
                    continue
                entry_price = Decimal(str(position_data.get("entry_price", position_data.get("avg_price", 0))))
                unrealized_pnl = Decimal(str(position_data.get("unrealized_pnl", 0)))
                leverage = Decimal(str(position_data.get("leverage", 1)))
                position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
                position = Position(trading_pair=trading_pair, position_side=position_side, unrealized_pnl=unrealized_pnl, entry_price=entry_price, amount=abs(amount), leverage=leverage)
                self._perpetual_trading.set_position(trading_pair, position_side, position)
        except Exception as e:
            self.logger().error(f"Error updating positions: {e}")

    async def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        trading_rules = []
        for info in raw_trading_pair_info:
            try:
                symbol = info.get("symbol", "")
                trading_pair = web_utils.convert_from_exchange_trading_pair(symbol) if "/" in symbol else symbol
                min_order_size = Decimal(str(info.get("min_order_size", info.get("minQty", "0.001"))))
                min_price_increment = Decimal(str(info.get("tick_size", info.get("tickSize", "0.01"))))
                min_base_amount_increment = Decimal(str(info.get("step_size", info.get("stepSize", "0.001"))))
                min_notional_size = Decimal(str(info.get("min_notional", info.get("minNotional", "10"))))
                collateral_token = info.get("quote_asset", info.get("quoteAsset", CONSTANTS.DEFAULT_QUOTE_ASSET))
                trading_rules.append(TradingRule(trading_pair=trading_pair, min_order_size=min_order_size, min_price_increment=min_price_increment, min_base_amount_increment=min_base_amount_increment, min_notional_size=min_notional_size, buy_order_collateral_token=collateral_token, sell_order_collateral_token=collateral_token))
            except Exception as e:
                self.logger().error(f"Error parsing trading rule for {info}: {e}")
        return trading_rules

    async def _user_stream_event_listener(self) -> None:
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("type", event_message.get("channel", ""))
                if event_type in ["order", "orderflow"]:
                    await self._process_order_event(event_message)
                elif event_type == "fill":
                    await self._process_fill_event(event_message)
                elif event_type == "position":
                    await self._process_position_event(event_message)
                elif event_type in ["account", "balance"]:
                    await self._process_balance_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error processing user stream event: {e}")

    async def _process_order_event(self, event: Dict[str, Any]) -> None:
        data = event.get("data", event)
        client_order_id = data.get("client_order_id", data.get("clientOrderId", ""))
        exchange_order_id = str(data.get("order_id", data.get("orderId", "")))
        status = data.get("status", "")
        tracked_order = self._order_tracker.fetch_order(client_order_id=client_order_id)
        if tracked_order is None:
            return
        new_state = CONSTANTS.ORDER_STATE.get(status, OrderState.OPEN)
        order_update = OrderUpdate(client_order_id=client_order_id, exchange_order_id=exchange_order_id, trading_pair=tracked_order.trading_pair, update_timestamp=data.get("timestamp", time.time()), new_state=new_state)
        self._order_tracker.process_order_update(order_update)

    async def _process_fill_event(self, event: Dict[str, Any]) -> None:
        data = event.get("data", event)
        client_order_id = data.get("client_order_id", data.get("clientOrderId", ""))
        exchange_order_id = str(data.get("order_id", data.get("orderId", "")))
        tracked_order = self._order_tracker.fetch_order(client_order_id=client_order_id)
        if tracked_order is None:
            return
        fee_asset = data.get("fee_asset", CONSTANTS.DEFAULT_QUOTE_ASSET)
        fee_amount = Decimal(str(data.get("fee", 0)))
        trade_update = TradeUpdate(
            trade_id=str(data.get("trade_id", data.get("id", ""))),
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fee=TokenAmount(token=fee_asset, amount=fee_amount),
            fill_base_amount=Decimal(str(data.get("quantity", 0))),
            fill_quote_amount=Decimal(str(data.get("price", 0))) * Decimal(str(data.get("quantity", 0))),
            fill_price=Decimal(str(data.get("price", 0))),
            fill_timestamp=data.get("timestamp", time.time()),
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _process_position_event(self, event: Dict[str, Any]) -> None:
        await self._update_positions()

    async def _process_balance_event(self, event: Dict[str, Any]) -> None:
        await self._update_balances()

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        result = {}
        try:
            for trading_pair in trading_pairs:
                symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                ticker_response = await self._api_get(path_url=f"{CONSTANTS.MARKETS_ENDPOINT}/{symbol}/ticker", is_auth_required=False)
                last_price = float(ticker_response.get("last_price", ticker_response.get("price", 0)))
                result[trading_pair] = last_price
        except Exception as e:
            self.logger().error(f"Error getting last traded prices: {e}")
        return result

    async def get_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        return await self._api_get(path_url=CONSTANTS.ORDERBOOK_ENDPOINT, params={"symbol": symbol, "depth": 100}, is_auth_required=False)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        try:
            funding_response = await self._api_get(path_url=f"{CONSTANTS.MARKETS_ENDPOINT}/{symbol}/funding", is_auth_required=False)
            return FundingInfo(trading_pair=trading_pair, index_price=Decimal(str(funding_response.get("index_price", 0))), mark_price=Decimal(str(funding_response.get("mark_price", 0))), next_funding_utc_timestamp=int(funding_response.get("next_funding_time", 0)), rate=Decimal(str(funding_response.get("funding_rate", 0))))
        except Exception as e:
            self.logger().error(f"Error getting funding info for {trading_pair}: {e}")
            return FundingInfo(trading_pair=trading_pair, index_price=s_decimal_0, mark_price=s_decimal_0, next_funding_utc_timestamp=0, rate=s_decimal_0)

    def exchange_symbol_for_tokens(self, trading_pair: str) -> str:
        return web_utils.convert_to_exchange_trading_pair(trading_pair)
