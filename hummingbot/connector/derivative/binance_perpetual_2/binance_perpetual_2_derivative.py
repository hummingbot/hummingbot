import asyncio
import copy
import logging
import time
import traceback
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING, AsyncIterable

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.binance_perpetual_2 import (
    binance_perpetual_2_constants as CONSTANTS,
    binance_perpetual_2_web_utils as web_utils,
)
from hummingbot.connector.derivative.binance_perpetual_2.binance_perpetual_2_auth import BinancePerpetual2Auth
from hummingbot.connector.derivative.binance_perpetual_2.binance_perpetual_2_api_order_book_data_source import BinancePerpetual2APIOrderBookDataSource
from hummingbot.connector.derivative.binance_perpetual_2.binance_perpetual_2_api_user_stream_data_source import BinancePerpetual2UserStreamDataSource
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
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

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

bpm_logger = None


class BinancePerpetual2Derivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            binance_perpetual_2_api_key: str = None,
            binance_perpetual_2_api_secret: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.binance_perpetual_2_api_key = binance_perpetual_2_api_key
        self.binance_perpetual_2_secret_key = binance_perpetual_2_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self._order_not_found_records = defaultdict(int)
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> BinancePerpetual2Auth:
        return BinancePerpetual2Auth(self.binance_perpetual_2_api_key, self.binance_perpetual_2_secret_key,
                                    self._time_synchronizer)

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
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return hasattr(CONSTANTS, "ORDER_NOT_EXIST_ERROR_CODE") and str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return hasattr(CONSTANTS, "UNKNOWN_ORDER_ERROR_CODE") and str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BinancePerpetual2APIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BinancePerpetual2UserStreamDataSource(
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
            
    async def _status_polling_loop_fetch_updates(self):
        """
        Fetches account updates from the exchange.
        """
        await safe_gather(
            self._update_balances(),
            self._update_positions(),
        )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Sends a request to cancel an order.
        """
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
            "origClientOrderId": tracked_order.client_order_id,
        }
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_URL,
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_URL,
        )
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
            **kwargs) -> Tuple[str, float]:
        """
        Places an order on the exchange.
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        order_side = "BUY" if trade_type is TradeType.BUY else "SELL"
        order_type_str = "LIMIT" if order_type is OrderType.LIMIT else "MARKET"
        if order_type is OrderType.LIMIT_MAKER:
            order_type_str = "LIMIT_MAKER"

        params = {
            "symbol": symbol,
            "side": order_side,
            "type": order_type_str,
            "newClientOrderId": order_id,
        }

        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            params.update({
                "price": f"{price:f}",
                "timeInForce": "GTC",
            })

        if order_type is not OrderType.MARKET and amount > 0:
            params.update({"quantity": f"{amount:f}"})
        else:
            params.update({"quantity": f"{amount:f}"})

        if position_action is not PositionAction.NIL:
            params["positionSide"] = "BOTH"

        exchange_order = await self._api_post(
            path_url=CONSTANTS.ORDER_URL,
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_URL,
        )

        return str(exchange_order["clientOrderId"]), self.current_timestamp
        
    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Gets the latest trade updates for a specific order.
        """
        trade_updates = []
        try:
            exchange_order_id = await order.get_exchange_order_id()
            params = {
                "symbol": await self.exchange_symbol_associated_to_pair(order.trading_pair),
                "orderId": exchange_order_id,
            }

            trade_history = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                params=params,
                is_auth_required=True,
                limit_id=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
            )

            for trade in trade_history:
                trade_updates.append(
                    TradeUpdate(
                        trade_id=str(trade["id"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=order.trading_pair,
                        fee=TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=order.trade_type,
                            percent_token=trade["commissionAsset"],
                            flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])],
                        ),
                        fill_base_amount=Decimal(trade["qty"]),
                        fill_quote_amount=Decimal(trade["qty"]) * Decimal(trade["price"]),
                        fill_price=Decimal(trade["price"]),
                        fill_timestamp=trade["time"] * 1e-3,
                    )
                )

            return trade_updates
        except Exception as e:
            self.logger().network(
                f"Error fetching trade updates for order {order.client_order_id}: {e}",
                app_warning_msg=f"Failed to fetch trade update for order {order.client_order_id}"
            )
            return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Gets the current state of an order on the exchange.
        """
        order_params = {
            "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
            "origClientOrderId": tracked_order.client_order_id,
        }

        exchange_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_URL,
            params=order_params,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_URL,
        )

        status = exchange_order_data["status"]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(exchange_order_data["orderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=exchange_order_data["updateTime"] * 1e-3,
            new_state=CONSTANTS.ORDER_STATE[status] if hasattr(CONSTANTS, "ORDER_STATE") and status in CONSTANTS.ORDER_STATE else status,
        )

        return order_update

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        """
        Iterates through the user event queue.
        """
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Error iterating user event queue.",
                    exc_info=True,
                    app_warning_msg="Could not get user events from Binance. Retrying in 5 seconds.",
                )
                await self._sleep(5.0)

    async def _user_stream_event_listener(self):
        """
        Listens to user stream events and processes them.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error processing user event: {e}", exc_info=True)
                
    async def _process_user_stream_event(self, event_message: Dict[str, Any]):
        """
        Processes the user stream event.
        """
        # 这里只是一个示例，实际实现需要根据币安的WebSocket API文档处理不同类型的事件
        if "e" in event_message:
            event_type = event_message["e"]
            
            if event_type == "ORDER_TRADE_UPDATE":
                # 处理订单交易更新
                order_data = event_message.get("o", {})
                client_order_id = order_data.get("c", "")
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(order_data.get("s", ""))
                
                # 创建订单更新
                if client_order_id and trading_pair:
                    order_status = order_data.get("X", "")
                    order_update = OrderUpdate(
                        client_order_id=client_order_id,
                        exchange_order_id=str(order_data.get("i", "")),
                        trading_pair=trading_pair,
                        update_timestamp=event_message.get("E", 0) * 1e-3,
                        new_state=CONSTANTS.ORDER_STATE[order_status] if hasattr(CONSTANTS, "ORDER_STATE") and order_status in CONSTANTS.ORDER_STATE else order_status,
                    )
                    self._order_tracker.process_order_update(order_update)
                    
            elif event_type == "ACCOUNT_UPDATE":
                # 处理账户余额和仓位更新
                await self._update_balances()
                await self._update_positions()
                
            elif event_type == "MARGIN_CALL":
                # 处理保证金催缴
                pass
                
    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Gets trading rules from the exchange.
        """
        trading_rules = []
        for symbol_data in exchange_info_dict["symbols"]:
            if web_utils.is_exchange_information_valid(symbol_data):
                try:
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol_data["symbol"])

                    min_notional = 0
                    min_base = 0
                    min_price_increment = 0
                    min_base_increment = 0

                    for filter_dict in symbol_data["filters"]:
                        if filter_dict["filterType"] == "PRICE_FILTER":
                            min_price_increment = Decimal(filter_dict["tickSize"])
                        elif filter_dict["filterType"] == "LOT_SIZE":
                            min_base_increment = Decimal(filter_dict["stepSize"])
                            min_base = Decimal(filter_dict["minQty"])
                        elif filter_dict["filterType"] == "MIN_NOTIONAL":
                            min_notional = Decimal(filter_dict["notional"])

                    trading_rules.append(
                        TradingRule(
                            trading_pair=trading_pair,
                            min_order_size=min_base,
                            min_price_increment=min_price_increment,
                            min_base_amount_increment=min_base_increment,
                            min_notional_size=min_notional,
                            buy_order_collateral_token=symbol_data["quoteAsset"],
                            sell_order_collateral_token=symbol_data["quoteAsset"],
                        )
                    )
                except Exception:
                    self.logger().error(f"Error parsing trading rule {symbol_data['symbol']}: {traceback.format_exc()}")

        return trading_rules
                
    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """
        Initializes trading pair symbols from exchange info.
        """
        mapping = bidict()
        for symbol_data in filter(web_utils.is_exchange_information_valid, exchange_info["symbols"]):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(symbol_data["baseAsset"], symbol_data["quoteAsset"])
        self._set_trading_pair_symbol_map(mapping)
                
    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        Gets the last traded price.
        """
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
        }

        resp_json = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_URL,
            params=params,
            limit_id=CONSTANTS.TICKER_PRICE_URL,
        )

        return float(resp_json["price"])
                
    async def _update_balances(self):
        """
        Updates the user balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INFO_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.ACCOUNT_INFO_URL,
        )

        assets = account_info.get("assets", [])
        for asset in assets:
            asset_name = asset.get("asset", "")
            available_balance = Decimal(asset.get("availableBalance", "0"))
            wallet_balance = Decimal(asset.get("walletBalance", "0"))
            if asset_name not in remote_asset_names:
                remote_asset_names.add(asset_name)
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = wallet_balance

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]
                
    async def _update_positions(self):
        """
        Updates the user positions.
        """
        positions = await self._api_get(
            path_url=CONSTANTS.POSITION_INFORMATION_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.POSITION_INFORMATION_URL,
        )

        for position in positions:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(position.get("symbol", ""))
            position_side = PositionSide.LONG if Decimal(position.get("positionAmt", "0")) > 0 else PositionSide.SHORT
            unrealized_pnl = Decimal(position.get("unRealizedProfit", "0"))
            entry_price = Decimal(position.get("entryPrice", "0"))
            amount = Decimal(position.get("positionAmt", "0"))
            leverage = Decimal(position.get("leverage", "0"))

            if not trading_pair or amount == 0:
                continue

            position_key = self._perpetual_trading.position_key(trading_pair, position_side)
            if position_key in self._perpetual_trading._account_positions:
                position = self._perpetual_trading._account_positions[position_key]
                position.update_position(amount=amount,
                                         price=entry_price,
                                         unrealized_pnl=unrealized_pnl,
                                         leverage=leverage)
            else:
                pos = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage,
                )
                self._perpetual_trading._account_positions[position_key] = pos
                
    async def _get_position_mode(self) -> Optional[PositionMode]:
        """
        Gets the position mode of the user.
        """
        params = {}
        position_mode_info = await self._api_get(
            path_url=CONSTANTS.CHANGE_POSITION_MODE_URL,
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.GET_POSITION_MODE_LIMIT_ID,
        )

        if position_mode_info["dualSidePosition"]:
            return PositionMode.HEDGE
        else:
            return PositionMode.ONEWAY
                
    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """
        Sets the position mode of a trading pair.
        """
        params = {"dualSidePosition": mode == PositionMode.HEDGE}
        try:
            response = await self._api_post(
                path_url=CONSTANTS.CHANGE_POSITION_MODE_URL,
                params=params,
                is_auth_required=True,
                limit_id=CONSTANTS.POST_POSITION_MODE_LIMIT_ID,
            )
            if response.get("msg") == "success" or response.get("code") == 200:
                self._position_mode = mode
                return True, ""
            return False, response.get("msg", "Unknown error.")
        except Exception as e:
            return False, str(e)
                
    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """
        Sets the leverage of a trading pair.
        """
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "leverage": leverage,
        }
        try:
            response = await self._api_post(
                path_url=CONSTANTS.SET_LEVERAGE_URL,
                params=params,
                is_auth_required=True,
                limit_id=CONSTANTS.SET_LEVERAGE_URL,
            )
            if response.get("leverage", 0) == leverage:
                return True, ""
            return False, response.get("msg", "Unknown error.")
        except Exception as e:
            return False, str(e)
                
    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        """
        Fetches the last fee payment.
        """
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "incomeType": "FUNDING_FEE",
            "limit": 1,
        }

        income_history = await self._api_get(
            path_url=CONSTANTS.GET_INCOME_HISTORY_URL,
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.GET_INCOME_HISTORY_URL,
        )

        if not income_history:
            return 0, Decimal("0"), Decimal("0")

        payment = income_history[0]
        timestamp = int(payment["time"])
        funding_rate = Decimal(payment["rate"]) if "rate" in payment else Decimal("0")
        payment_amount = Decimal(payment["income"])

        return timestamp, funding_rate, payment_amount
                
    async def _update_order_fills_from_trades(self):
        """
        Updates order fills from trades.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._trading_pairs) > 0:
            try:
                trading_pairs_to_order_map = defaultdict(lambda: {})
                for order in self._order_tracker.all_fillable_orders.values():
                    trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order

                if len(trading_pairs_to_order_map) == 0:
                    return

                for trading_pair in trading_pairs_to_order_map:
                    exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
                    params = {
                        "symbol": exchange_symbol,
                    }

                    if self._last_trade_history_timestamp:
                        params["startTime"] = int(self._last_trade_history_timestamp)

                    trade_history = await self._api_get(
                        path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                        params=params,
                        is_auth_required=True,
                        limit_id=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                    )

                    # Process trade history
                    for trade in trade_history:
                        trade_id = trade["id"]
                        exchange_order_id = str(trade["orderId"])
                        if exchange_order_id in trading_pairs_to_order_map[trading_pair]:
                            tracked_order = trading_pairs_to_order_map[trading_pair][exchange_order_id]
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent_token=trade["commissionAsset"],
                                flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])],
                            )

                            trade_update = TradeUpdate(
                                trade_id=trade_id,
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=exchange_order_id,
                                trading_pair=trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(trade["qty"]),
                                fill_quote_amount=Decimal(trade["qty"]) * Decimal(trade["price"]),
                                fill_price=Decimal(trade["price"]),
                                fill_timestamp=trade["time"] * 1e-3,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                    # Update timestamp of last trade history
                    if trade_history:
                        self._last_trade_history_timestamp = max([int(trade["time"]) for trade in trade_history])
            except Exception as e:
                self.logger().network(
                    f"Error fetching trade history: {e}",
                    app_warning_msg=f"Failed to fetch trade history from {self.name}.",
                    exc_info=True,
                )
                
    async def _update_order_status(self):
        """
        Updates the order status.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._trading_pairs) > 0:
            tracked_orders = list(self._order_tracker.active_orders.values())
            tasks = []
            for tracked_order in tracked_orders:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                tasks.append(self._api_get(
                    path_url=CONSTANTS.ORDER_URL,
                    params={
                        "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
                        "orderId": exchange_order_id,
                    },
                    is_auth_required=True,
                    limit_id=CONSTANTS.ORDER_URL,
                    return_err=True,
                ))

            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for order_update, tracked_order in zip(results, tracked_orders):
                if isinstance(order_update, Exception):
                    if self._is_order_not_found_during_status_update_error(order_update):
                        self._order_not_found_records[tracked_order.client_order_id] += 1
                        if self._order_not_found_records[tracked_order.client_order_id] >= self._order_tracker.lost_order_count_limit:
                            self._order_tracker.process_order_not_found(tracked_order.client_order_id)
                    continue

                # Update the tracked order
                status = order_update["status"]
                new_state = CONSTANTS.ORDER_STATE[status] if hasattr(CONSTANTS, "ORDER_STATE") and status in CONSTANTS.ORDER_STATE else status

                update = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=order_update["orderId"],
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=order_update["updateTime"] * 1e-3,
                    new_state=new_state,
                )
                self._order_tracker.process_order_update(update) 

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass 