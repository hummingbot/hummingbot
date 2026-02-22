import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from types import MethodType
from typing import Any, Dict, List, Optional, Tuple, Union

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.bing_x_perpetual import (
    bing_x_perpetual_constants as CONSTANTS,
    bing_x_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_api_order_book_data_source import (
    BingXPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_auth import BingXPerpetualAuth
from hummingbot.connector.derivative.bing_x_perpetual.bing_x_perpetual_api_user_stream_data_source import (
    BingXPerpetualAPIUserStreamDataSource,
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
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

s_logger = None


class BingXPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            bing_x_perpetual_api_key: str = None,
            bing_x_perpetual_api_secret: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        self._api_key = bing_x_perpetual_api_key
        self._secret_key = bing_x_perpetual_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> BingXPerpetualAuth:
        return BingXPerpetualAuth(self._api_key, self._secret_key)

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
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_TIME_PATH_URL

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
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "Order does not exist" in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "order not found" in str(cancelation_exception).lower()

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BingXPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
            throttler=self._throttler,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BingXPerpetualAPIUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
            throttler=self._throttler,
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
        Update fees information from the exchange.
        BingX does not provide a fee endpoint; using default fees.
        """
        pass

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_fills_from_trades(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "symbol": symbol,
        }
        if tracked_order.exchange_order_id:
            api_params["orderId"] = tracked_order.exchange_order_id
        else:
            api_params["clientOrderId"] = tracked_order.client_order_id

        cancel_result = await self._api_request(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            method=RESTMethod.DELETE,
            params=api_params,
            is_auth_required=True)

        if isinstance(cancel_result, dict) and cancel_result.get("code") == 0:
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
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL

        api_params = {
            "symbol": symbol,
            "side": side_str,
            "quantity": amount_str,
            "type": "MARKET" if order_type is OrderType.MARKET else "LIMIT",
            "newClientOrderId": order_id,
        }
        if order_type.is_limit_type():
            api_params["price"] = price_str
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC

        # Handle position side for hedge mode
        if self.position_mode == PositionMode.HEDGE:
            if position_action == PositionAction.OPEN:
                api_params["positionSide"] = CONSTANTS.POSITION_SIDE_LONG if trade_type is TradeType.BUY else CONSTANTS.POSITION_SIDE_SHORT
            else:
                api_params["positionSide"] = CONSTANTS.POSITION_SIDE_SHORT if trade_type is TradeType.BUY else CONSTANTS.POSITION_SIDE_LONG

        try:
            order_result = await self._api_request(
                path_url=CONSTANTS.ORDER_PATH_URL,
                method=RESTMethod.POST,
                params=api_params,
                is_auth_required=True)
            order_data = order_result.get("data", order_result)
            o_id = str(order_data["orderId"])
            transact_time = int(order_data.get("transactTime", int(time.time() * 1e3))) * 1e-3
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = "status is 503" in error_description
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = time.time()
            else:
                raise
        return o_id, transact_time

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            if order.exchange_order_id is not None:
                exchange_order_id = order.exchange_order_id
                trading_pair = order.trading_pair
                symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                all_fills_response = await self._api_request(
                    path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                    method=RESTMethod.GET,
                    params={
                        "symbol": symbol,
                        "orderId": exchange_order_id,
                    },
                    is_auth_required=True)

                fills_data = all_fills_response.get("data", all_fills_response)
                if isinstance(fills_data, dict):
                    fills_data = [fills_data]
                elif fills_data is None:
                    fills_data = []

                for trade in fills_data:
                    position_side = trade.get("positionSide", "LONG")
                    position_action = (PositionAction.OPEN
                                       if (order.trade_type is TradeType.BUY and position_side == "LONG"
                                           or order.trade_type is TradeType.SELL and position_side == "SHORT")
                                       else PositionAction.CLOSE)
                    fee_asset = trade.get("commissionAsset", trade.get("feeAsset", order.quote_asset))
                    fee_amount = Decimal(str(trade.get("commission", trade.get("fee", "0"))))
                    flat_fees = [] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)]
                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=position_action,
                        percent_token=fee_asset,
                        flat_fees=flat_fees,
                    )
                    fill_price = Decimal(str(trade.get("price", "0")))
                    fill_amount = Decimal(str(trade.get("qty", trade.get("executedQty", "0"))))
                    trade_update = TradeUpdate(
                        trade_id=str(trade.get("id", trade.get("orderId", ""))),
                        client_order_id=order.client_order_id,
                        exchange_order_id=str(trade.get("orderId", exchange_order_id)),
                        trading_pair=trading_pair,
                        fill_timestamp=int(trade.get("time", trade.get("updateTime", time.time() * 1e3))) * 1e-3,
                        fill_price=fill_price,
                        fill_base_amount=fill_amount,
                        fill_quote_amount=fill_price * fill_amount,
                        fee=fee,
                    )
                    trade_updates.append(trade_update)
        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id} "
                          "- waiting for exchange order id.")
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        params = {
            "symbol": symbol,
        }
        if tracked_order.exchange_order_id:
            params["orderId"] = tracked_order.exchange_order_id
        else:
            params["clientOrderId"] = tracked_order.client_order_id

        updated_order_data = await self._api_request(
            path_url=CONSTANTS.ORDER_PATH_URL,
            method=RESTMethod.GET,
            params=params,
            is_auth_required=True)

        order_data = updated_order_data.get("data", updated_order_data)
        new_state = CONSTANTS.ORDER_STATE.get(order_data.get("status", ""), OrderState.OPEN)

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_data.get("orderId", "")),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(order_data.get("updateTime", time.time() * 1e3)) * 1e-3,
            new_state=new_state,
        )
        return order_update

    async def _iter_user_event_queue(self):
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from BingX. Check API key and network connection.",
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
        event_type = event_message.get("e")
        if event_type == "ORDER_TRADE_UPDATE":
            order_message = event_message.get("o", {})
            client_order_id = order_message.get("c", order_message.get("C", None))

            tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
            if tracked_order is not None:
                trade_id = str(order_message.get("t", "0"))
                if trade_id != "0":
                    fee_asset = order_message.get("N", tracked_order.quote_asset)
                    fee_amount = Decimal(str(order_message.get("n", "0")))
                    position_side = order_message.get("ps", "LONG")
                    position_action = (PositionAction.OPEN
                                       if (tracked_order.trade_type is TradeType.BUY and position_side == "LONG"
                                           or tracked_order.trade_type is TradeType.SELL and position_side == "SHORT")
                                       else PositionAction.CLOSE)
                    flat_fees = [] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)]
                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=position_action,
                        percent_token=fee_asset,
                        flat_fees=flat_fees,
                    )
                    fill_price = Decimal(str(order_message.get("L", "0")))
                    fill_amount = Decimal(str(order_message.get("l", "0")))
                    trade_update = TradeUpdate(
                        trade_id=trade_id,
                        client_order_id=client_order_id,
                        exchange_order_id=str(order_message.get("i", "")),
                        trading_pair=tracked_order.trading_pair,
                        fill_timestamp=int(order_message.get("T", time.time() * 1e3)) * 1e-3,
                        fill_price=fill_price,
                        fill_base_amount=fill_amount,
                        fill_quote_amount=fill_price * fill_amount,
                        fee=fee,
                    )
                    self._order_tracker.process_trade_update(trade_update)

            tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
            if tracked_order is not None:
                order_status = order_message.get("X", "NEW")
                new_state = CONSTANTS.ORDER_STATE.get(order_status, OrderState.OPEN)
                order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=int(event_message.get("T", time.time() * 1e3)) * 1e-3,
                    new_state=new_state,
                    client_order_id=client_order_id,
                    exchange_order_id=str(order_message.get("i", "")),
                )
                self._order_tracker.process_order_update(order_update)

        elif event_type == "ACCOUNT_UPDATE":
            update_data = event_message.get("a", {})
            # Update balances
            for asset in update_data.get("B", []):
                asset_name = asset["a"]
                self._account_balances[asset_name] = Decimal(str(asset["wb"]))
                self._account_available_balances[asset_name] = Decimal(str(asset["cw"]))

            # Update positions
            for asset in update_data.get("P", []):
                trading_pair = asset.get("s", "")
                try:
                    hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
                except KeyError:
                    continue

                side = PositionSide[asset.get("ps", "LONG")]
                position = self._perpetual_trading.get_position(hb_trading_pair, side)
                if position is not None:
                    amount = Decimal(str(asset.get("pa", "0")))
                    if amount == Decimal("0"):
                        pos_key = self._perpetual_trading.position_key(hb_trading_pair, side)
                        self._perpetual_trading.remove_position(pos_key)
                    else:
                        position.update_position(
                            position_side=side,
                            unrealized_pnl=Decimal(str(asset.get("up", "0"))),
                            entry_price=Decimal(str(asset.get("ep", "0"))),
                            amount=amount,
                        )
                else:
                    await self._update_positions()

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules = exchange_info_dict.get("data", [])
        if isinstance(rules, dict):
            rules = rules.get("contracts", rules.get("symbols", []))
        return_val = []
        for rule in rules:
            try:
                if web_utils.is_exchange_information_valid(rule):
                    symbol = rule.get("symbol", "")
                    # BingX perpetual: symbol is like BTC-USDT
                    parts = symbol.split("-")
                    if len(parts) == 2:
                        base = parts[0]
                        quote = parts[1]
                        trading_pair = combine_to_hb_trading_pair(base, quote)
                    else:
                        trading_pair = symbol

                    min_order_size = Decimal(str(rule.get("minQty", rule.get("tradeMinQuantity", "0.001"))))
                    step_size = Decimal(str(rule.get("stepSize", rule.get("tradeMinQuantity", "0.001"))))
                    tick_size = Decimal(str(rule.get("tickSize", rule.get("pricePrecision", "0.01"))))
                    min_notional = Decimal(str(rule.get("minNotional", "5")))
                    collateral_token = rule.get("currency", rule.get("marginAsset", quote if len(parts) == 2 else "USDT"))

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
        data = exchange_info.get("data", [])
        if isinstance(data, dict):
            data = data.get("contracts", data.get("symbols", []))
        for symbol_data in filter(web_utils.is_exchange_information_valid, data):
            exchange_symbol = symbol_data.get("symbol", "")
            # BingX perpetual symbols are like BTC-USDT
            parts = exchange_symbol.split("-")
            if len(parts) == 2:
                base = parts[0]
                quote = parts[1]
                trading_pair = combine_to_hb_trading_pair(base, quote)
            else:
                trading_pair = exchange_symbol
            if trading_pair not in mapping.inverse:
                mapping[exchange_symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"symbol": symbol}
        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.LAST_TRADED_PRICE_PATH,
            params=params,
        )
        data = resp_json.get("data", resp_json)
        if isinstance(data, list):
            return float(data[0].get("lastPrice", 0))
        return float(data.get("lastPrice", 0))

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=True)

        data = account_info.get("data", {})
        # BingX perpetual balance response can be a dict of asset balances or a list
        if isinstance(data, dict):
            balance_data = data.get("balance", data)
            if isinstance(balance_data, dict):
                for asset_name, asset_info in balance_data.items():
                    if isinstance(asset_info, dict):
                        available = Decimal(str(asset_info.get("availableMargin", asset_info.get("crossWalletBalance", "0"))))
                        total = Decimal(str(asset_info.get("equity", asset_info.get("balance", "0"))))
                        self._account_available_balances[asset_name] = available
                        self._account_balances[asset_name] = total
                        remote_asset_names.add(asset_name)
            elif isinstance(balance_data, list):
                for asset_entry in balance_data:
                    asset_name = asset_entry.get("asset", "")
                    available = Decimal(str(asset_entry.get("availableBalance", asset_entry.get("availableMargin", "0"))))
                    total = Decimal(str(asset_entry.get("balance", asset_entry.get("equity", "0"))))
                    self._account_available_balances[asset_name] = available
                    self._account_balances[asset_name] = total
                    remote_asset_names.add(asset_name)
        elif isinstance(data, list):
            for asset_entry in data:
                asset_name = asset_entry.get("asset", "")
                available = Decimal(str(asset_entry.get("availableBalance", "0")))
                total = Decimal(str(asset_entry.get("balance", "0")))
                self._account_available_balances[asset_name] = available
                self._account_balances[asset_name] = total
                remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        positions_response = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.POSITIONS_PATH_URL,
            is_auth_required=True)

        positions_data = positions_response.get("data", [])
        if isinstance(positions_data, dict):
            positions_data = [positions_data]
        elif positions_data is None:
            positions_data = []

        for position in positions_data:
            trading_pair = position.get("symbol", "")
            try:
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
            except KeyError:
                continue

            position_side_str = position.get("positionSide", "LONG")
            if position_side_str == "BOTH":
                # One-way mode
                position_side = PositionSide.BOTH
            else:
                position_side = PositionSide[position_side_str]

            unrealized_pnl = Decimal(str(position.get("unrealizedProfit", position.get("unRealizedProfit", "0"))))
            entry_price = Decimal(str(position.get("entryPrice", position.get("avgPrice", "0"))))
            amount = Decimal(str(position.get("positionAmt", position.get("positionSize", "0"))))
            leverage = Decimal(str(position.get("leverage", "1")))
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)

            if amount != Decimal("0"):
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
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            trading_pairs_to_order_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {})
            for order in self._order_tracker.active_orders.values():
                trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order
            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = []
            for tp in trading_pairs:
                symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tp)
                tasks.append(
                    self._api_request(
                        path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                        method=RESTMethod.GET,
                        params={"symbol": symbol},
                        is_auth_required=True,
                    )
                )
            results = await safe_gather(*tasks, return_exceptions=True)
            for trades_response, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map.get(trading_pair)
                if isinstance(trades_response, Exception):
                    self.logger().network(
                        f"Error fetching trades update for {trading_pair}: {trades_response}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                trades = trades_response.get("data", trades_response)
                if not isinstance(trades, list):
                    trades = [trades] if trades else []
                for trade in trades:
                    order_id = str(trade.get("orderId", ""))
                    if order_id in order_map:
                        tracked_order = order_map[order_id]
                        position_side = trade.get("positionSide", "LONG")
                        position_action = (PositionAction.OPEN
                                           if (tracked_order.trade_type is TradeType.BUY and position_side == "LONG"
                                               or tracked_order.trade_type is TradeType.SELL and position_side == "SHORT")
                                           else PositionAction.CLOSE)
                        fee_asset = trade.get("commissionAsset", trade.get("feeAsset", tracked_order.quote_asset))
                        fee_amount = Decimal(str(trade.get("commission", trade.get("fee", "0"))))
                        fee = TradeFeeBase.new_perpetual_fee(
                            fee_schema=self.trade_fee_schema(),
                            position_action=position_action,
                            percent_token=fee_asset,
                            flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)]
                        )
                        fill_price = Decimal(str(trade.get("price", "0")))
                        fill_amount = Decimal(str(trade.get("qty", trade.get("executedQty", "0"))))
                        trade_update = TradeUpdate(
                            trade_id=str(trade.get("id", trade.get("orderId", ""))),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=order_id,
                            trading_pair=tracked_order.trading_pair,
                            fill_timestamp=int(trade.get("time", trade.get("updateTime", time.time() * 1e3))) * 1e-3,
                            fill_price=fill_price,
                            fill_base_amount=fill_amount,
                            fill_quote_amount=fill_price * fill_amount,
                            fee=fee,
                        )
                        self._order_tracker.process_trade_update(trade_update)

    async def _update_order_status(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            tracked_orders = list(self._order_tracker.active_orders.values())
            tasks = []
            for order in tracked_orders:
                symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
                params = {"symbol": symbol}
                if order.exchange_order_id:
                    params["orderId"] = order.exchange_order_id
                else:
                    params["clientOrderId"] = order.client_order_id
                tasks.append(
                    self._api_request(
                        path_url=CONSTANTS.ORDER_PATH_URL,
                        method=RESTMethod.GET,
                        params=params,
                        is_auth_required=True,
                        return_err=True,
                    )
                )
            results = await safe_gather(*tasks, return_exceptions=True)
            for order_update_response, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._order_tracker.all_orders:
                    continue
                if isinstance(order_update_response, Exception):
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: {order_update_response}."
                    )
                    continue
                order_data = order_update_response.get("data", order_update_response)
                if isinstance(order_data, dict) and "code" in order_data:
                    await self._order_tracker.process_order_not_found(client_order_id)
                    continue

                status = order_data.get("status", "NEW") if isinstance(order_data, dict) else "NEW"
                new_state = CONSTANTS.ORDER_STATE.get(status, OrderState.OPEN)

                new_order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=int(order_data.get("updateTime", time.time() * 1e3)) * 1e-3 if isinstance(order_data, dict) else time.time(),
                    new_state=new_state,
                    client_order_id=client_order_id,
                    exchange_order_id=str(order_data.get("orderId", "")) if isinstance(order_data, dict) else "",
                )
                self._order_tracker.process_order_update(new_order_update)

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        # BingX perpetual position mode is set at account level, not per trading pair
        # This is a simplified implementation
        self._position_mode = mode
        return True, ""

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {
            "symbol": symbol,
            "side": "LONG",
            "leverage": leverage,
        }
        try:
            result = await self._api_request(
                path_url=CONSTANTS.SET_LEVERAGE_PATH_URL,
                method=RESTMethod.POST,
                params=params,
                is_auth_required=True)
            # Also set for SHORT side
            params["side"] = "SHORT"
            await self._api_request(
                path_url=CONSTANTS.SET_LEVERAGE_PATH_URL,
                method=RESTMethod.POST,
                params=params,
                is_auth_required=True)
            return True, ""
        except Exception as e:
            return False, str(e)

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        try:
            payment_response = await self._api_request(
                path_url=CONSTANTS.GET_INCOME_HISTORY_URL,
                method=RESTMethod.GET,
                params={
                    "symbol": symbol,
                    "incomeType": "FUNDING_FEE",
                },
                is_auth_required=True)

            funding_info_response = await self._api_request(
                path_url=CONSTANTS.FUNDING_RATE_PATH_URL,
                method=RESTMethod.GET,
                params={"symbol": symbol})

            payment_data = payment_response.get("data", payment_response)
            if isinstance(payment_data, list):
                sorted_payments = sorted(payment_data, key=lambda a: a.get('time', 0), reverse=True)
            else:
                sorted_payments = [payment_data] if payment_data else []

            if len(sorted_payments) < 1:
                return 0, Decimal("-1"), Decimal("-1")

            funding_payment = sorted_payments[0]
            _payment = Decimal(str(funding_payment.get("income", "0")))

            funding_data = funding_info_response.get("data", funding_info_response)
            if isinstance(funding_data, list) and len(funding_data) > 0:
                funding_rate = Decimal(str(funding_data[0].get("lastFundingRate", "0")))
            elif isinstance(funding_data, dict):
                funding_rate = Decimal(str(funding_data.get("lastFundingRate", "0")))
            else:
                funding_rate = Decimal("-1")

            timestamp = funding_payment.get("time", 0)
            if _payment != Decimal("0"):
                return timestamp, funding_rate, _payment
            else:
                return 0, Decimal("-1"), Decimal("-1")
        except Exception:
            return 0, Decimal("-1"), Decimal("-1")

    async def _api_request(self,
                           path_url: str,
                           method: RESTMethod = RESTMethod.GET,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           return_err: bool = False,
                           limit_id: Optional[str] = None,
                           trading_pair: Optional[str] = None,
                           **kwargs) -> Dict[str, Any]:
        last_exception = None
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.rest_url(path_url, domain=self.domain)

        local_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        for _ in range(2):
            try:
                request_result = await rest_assistant.execute_request(
                    url=url,
                    params=params,
                    data=data,
                    method=method,
                    is_auth_required=is_auth_required,
                    return_err=return_err,
                    headers=local_headers,
                    throttler_limit_id=limit_id if limit_id else path_url,
                )
                return request_result
            except IOError as request_exception:
                last_exception = request_exception
                if self._is_request_exception_related_to_time_synchronizer(request_exception=request_exception):
                    self._time_synchronizer.clear_time_offset_ms_samples()
                    await self._update_time_synchronizer()
                else:
                    raise

        raise last_exception
