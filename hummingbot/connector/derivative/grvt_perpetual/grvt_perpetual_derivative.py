import asyncio
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple
import json

from hummingbot.connector.derivative_base import DerivativeBase
from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GRVTPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GRVTPerpetualAuth
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_user_stream_data_source import (
    GRVTPerpetualUserStreamDataSource,
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, DeductedFromReturnsTradeFee, AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class GRVTPerpetualDerivative(DerivativeBase):
    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> GRVTPerpetualAuth:
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
        return "HBOT"

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.MARK_PRICE_URL

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return self.quote_asset(trading_pair)

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self.quote_asset(trading_pair)

    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    def is_trading_required(self) -> bool:
        return self._trading_required

    def funding_fee_poll_interval(self) -> int:
        return 120

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        grvt_perpetual_api_key: str = "",
        grvt_perpetual_api_secret: str = "",
        grvt_perpetual_sub_account_id: str = "",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._domain = domain
        self._auth = GRVTPerpetualAuth(
            api_key=grvt_perpetual_api_key,
            api_secret=grvt_perpetual_api_secret,
            sub_account_id=grvt_perpetual_sub_account_id,
            domain=domain,
        )
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        
        self._instrument_hashes = {}  # Store hashes required for order signing
        self._last_server_time_diff = 0

        super().__init__(client_config_map)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self.time_synchronizer,
            domain=self._domain,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GRVTPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GRVTPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector_name=self.name,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL, self._domain, CONSTANTS.GRVT_EDGE_RPC)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        
        cancel_payload = {
            "subAccountID": int(self._auth._sub_account_id),
            "orderID": tracked_order.exchange_order_id or order_id
        }
        
        # In a real implementation we might need to sign cancellation
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=cancel_payload,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.CANCEL_ORDER_URL,
        )
        if response.get("status") == "success":
            return True
        return False

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
        url = web_utils.private_rest_url(CONSTANTS.CREATE_ORDER_URL, self._domain, CONSTANTS.GRVT_EDGE_RPC)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        
        asset_id = int(self._instrument_hashes.get(trading_pair, "0x1"), 16)
        
        message_data = {
            "subAccountID": int(self._auth._sub_account_id),
            "isMarket": order_type == OrderType.MARKET,
            "timeInForce": 1 if order_type == OrderType.LIMIT else 0,
            "postOnly": order_type == OrderType.LIMIT_MAKER,
            "reduceOnly": position_action == PositionAction.CLOSE,
            "legs": [
                {
                    "assetID": asset_id,
                    "contractSize": int(amount * Decimal("1e8")),
                    "limitPrice": int(price * Decimal("1e8")) if price else 0,
                    "isBuyingContract": trade_type == TradeType.BUY
                }
            ],
            "nonce": int(self.current_timestamp * 1e3),
            "expiration": int(self.current_timestamp * 1e3) + 60000000
        }
        
        signature = self._auth.sign_order_payload(message_data)
        
        payload = {
            "order": message_data,
            "signature": signature
        }

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=payload,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.CREATE_ORDER_URL,
        )
        
        exchange_order_id = response.get("orderID", "dummy_exchange_id")
        return exchange_order_id, self.current_timestamp

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = Decimal("0"),
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        fee_percent = Decimal("0.0001") if is_maker else Decimal("0.0005")
        return AddedToCostTradeFee(percent=fee_percent)

    async def _update_trading_fees(self):
        pass

    async def _update_balances(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_SUMMARY_URL, self._domain, CONSTANTS.GRVT_TRADE_DATA_RPC)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        try:
            response = await rest_assistant.execute_request(
                url=url,
                method=RESTMethod.POST,
                data={"subAccountID": self._auth._sub_account_id},
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.ACCOUNT_SUMMARY_URL,
            )
            self._account_available_balances.clear()
            self._account_balances.clear()
            for asset in response.get("assets", []):
                currency = asset["asset"]
                available = Decimal(str(asset["available"]))
                total = Decimal(str(asset["total"]))
                self._account_available_balances[currency] = available
                self._account_balances[currency] = total
        except Exception as e:
            self.logger().error(f"Error updating balances: {e}")

    async def _update_positions(self):
        url = web_utils.private_rest_url(CONSTANTS.POSITIONS_URL, self._domain, CONSTANTS.GRVT_TRADE_DATA_RPC)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        try:
            response = await rest_assistant.execute_request(
                url=url,
                method=RESTMethod.POST,
                data={"subAccountID": self._auth._sub_account_id},
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.POSITIONS_URL,
            )
            
            for pos in response.get("positions", []):
                symbol = pos.get("instrument")
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
                size = Decimal(str(pos.get("size", "0")))
                if size == Decimal("0"):
                    if trading_pair in self._account_positions:
                        del self._account_positions[trading_pair]
                    continue
                
                position_side = PositionSide.LONG if size > 0 else PositionSide.SHORT
                from hummingbot.connector.derivative.position import Position
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=Decimal(str(pos.get("unrealizedPnl", "0"))),
                    entry_price=Decimal(str(pos.get("entryPrice", "0"))),
                    amount=abs(size),
                    leverage=Decimal(str(pos.get("leverage", "1")))
                )
                self._account_positions[trading_pair] = position
        except Exception as e:
            self.logger().error(f"Error updating positions: {e}")

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[Any]:
        rules = []
        instruments = exchange_info_dict.get("result", [])
        for instrument in instruments:
            try:
                symbol = instrument["instrument"]
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
                
                self._instrument_hashes[trading_pair] = instrument.get("instrumentHash", "0x1")
                
                min_order_size = Decimal(str(instrument.get("minOrderSize", "0.01")))
                min_price_increment = Decimal(str(instrument.get("tickSize", "0.01")))
                min_base_amount_increment = Decimal(str(instrument.get("stepSize", "0.01")))
                
                rule = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_order_size,
                    min_price_increment=min_price_increment,
                    min_base_amount_increment=min_base_amount_increment,
                )
                rules.append(rule)
            except Exception as e:
                self.logger().error(f"Error parsing rule: {e}")
        return rules

    async def _update_trading_rules(self):
        exchange_info = await self._make_trading_rules_request()
        rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for rule in rules_list:
            self._trading_rules[rule.trading_pair] = rule

    async def _make_trading_rules_request(self) -> Any:
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL, self._domain, CONSTANTS.GRVT_MARKET_DATA_RPC)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data={},
            throttler_limit_id=CONSTANTS.EXCHANGE_INFO_URL,
        )
        return response

    async def _make_trading_pairs_request(self) -> Any:
        return await self._make_trading_rules_request()

    async def _update_order_status(self):
        url = web_utils.private_rest_url(CONSTANTS.OPEN_ORDERS_URL, self._domain, CONSTANTS.GRVT_TRADE_DATA_RPC)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        try:
            response = await rest_assistant.execute_request(
                url=url,
                method=RESTMethod.POST,
                data={"subAccountID": self._auth._sub_account_id},
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.OPEN_ORDERS_URL,
            )
            orders = response.get("orders", [])
            for order_info in orders:
                client_order_id = order_info.get("clientOrderID")
                if not client_order_id:
                    continue
                tracked_order = self.in_flight_orders.get(client_order_id)
                if not tracked_order:
                    continue
                state = CONSTANTS.ORDER_STATE.get(order_info.get("status"), OrderState.OPEN)
                order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=state,
                    client_order_id=client_order_id,
                    exchange_order_id=order_info.get("orderID")
                )
                self._order_tracker.process_order_update(order_update)
        except Exception as e:
            self.logger().error(f"Error updating order status: {e}")

    async def _update_trade_history(self):
        pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=tracked_order.current_state,
            client_order_id=tracked_order.client_order_id,
        )

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Error getting user event from queue.", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message.get("channel")
                data = event_message.get("data", {})
                if channel == "order":
                    for order_data in data:
                        client_order_id = order_data.get("clientOrderID")
                        tracked_order = self.in_flight_orders.get(client_order_id)
                        if tracked_order:
                            status = CONSTANTS.ORDER_STATE.get(order_data.get("status"), OrderState.OPEN)
                            order_update = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=float(order_data.get("time", 0)) * 1e-9,
                                new_state=status,
                                client_order_id=client_order_id,
                                exchange_order_id=order_data.get("orderID")
                            )
                            self._order_tracker.process_order_update(order_update)
                elif channel == "user_trade":
                    for trade_data in data:
                        client_order_id = trade_data.get("clientOrderID")
                        tracked_order = self.in_flight_orders.get(client_order_id)
                        if tracked_order:
                            fee = AddedToCostTradeFee(
                                percent_token=tracked_order.quote_asset,
                                flat_fees=[TokenAmount(token=tracked_order.quote_asset, amount=Decimal(str(trade_data.get("fee", "0"))))]
                            )
                            trade_update = TradeUpdate(
                                trade_id=trade_data.get("id"),
                                client_order_id=client_order_id,
                                exchange_order_id=trade_data.get("orderID"),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(str(trade_data.get("size"))),
                                fill_quote_amount=Decimal(str(trade_data.get("size"))) * Decimal(str(trade_data.get("price"))),
                                fill_price=Decimal(str(trade_data.get("price"))),
                                fill_timestamp=float(trade_data.get("time", 0)) * 1e-9
                            )
                            self._order_tracker.process_trade_update(trade_update)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error processing user stream event: {e}", exc_info=True)

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        url = web_utils.public_rest_url(CONSTANTS.TICKER_URL, self._domain, CONSTANTS.GRVT_MARKET_DATA_RPC)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        try:
            response = await rest_assistant.execute_request(
                url=url,
                method=RESTMethod.POST,
                data={"instrument": symbol},
                throttler_limit_id=CONSTANTS.TICKER_URL,
            )
            return float(response.get("result", {}).get("lastPrice", 0))
        except Exception:
            return 0.0

    async def _make_network_check_request(self):
        url = web_utils.public_rest_url(CONSTANTS.MARK_PRICE_URL, self._domain, CONSTANTS.GRVT_MARKET_DATA_RPC)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data={"instrument": "BTC-USDT"},
            throttler_limit_id=CONSTANTS.MARK_PRICE_URL,
        )

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return PositionMode.ONEWAY

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        return True, ""

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        return 0, Decimal("0"), Decimal("0")
