import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from async_timeout import timeout

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.phemex_perpetual import (
    phemex_perpetual_constants as CONSTANTS,
    phemex_perpetual_utils,
    phemex_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_api_order_book_data_source import (
    PhemexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_api_user_stream_data_source import (
    PhemexPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_auth import PhemexPerpetualAuth
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange_base import bidict
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class PhemexPerpetualDerivative(PerpetualDerivativePyBase):
    _position_mode: PositionMode
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        phemex_perpetual_api_key: str = None,
        phemex_perpetual_api_secret: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.phemex_perpetual_api_key = phemex_perpetual_api_key
        self.phemex_perpetual_secret_key = phemex_perpetual_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> PhemexPerpetualAuth:
        return PhemexPerpetualAuth(
            self.phemex_perpetual_api_key, self.phemex_perpetual_secret_key, self._time_synchronizer
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
        return ""

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    async def start_network(self):
        """
        Start all required tasks to update the status of the connector.
        """
        await super().start_network()
        if self.is_trading_required:
            await self._get_position_mode()

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

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
        """
        Documentation doesn't make this clear.
        To-do: Confirm manually or from their team.
        """
        return 'Error: {"code": "401","msg": "401 Request Expired at' in request_exception.args[0]

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "Order not found for Client ID" in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_FOUND_ERROR_CODE) in str(
            cancelation_exception
        ) and CONSTANTS.ORDER_NOT_FOUND_ERROR_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler, time_synchronizer=self._time_synchronizer, domain=self._domain, auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return PhemexPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return PhemexPerpetualAPIUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
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
        """
        Update fees information from the exchange
        """
        pass

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        trading_pairs_to_orders_map = {}
        tasks = []
        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
        for order in incomplete_orders:
            if trading_pairs_to_orders_map.get(order.trading_pair, None) is None:
                trading_pairs_to_orders_map[order.trading_pair] = []
            trading_pairs_to_orders_map[order.trading_pair].append(order.client_order_id)

        for pair in trading_pairs_to_orders_map:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=pair)
            tasks.append(
                self._api_delete(path_url=CONSTANTS.CANCEL_ALL_ORDERS, params={"symbol": symbol}, is_auth_required=True)
            )
        successful_cancellations = []
        failed_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for trading_pair, cr in zip(trading_pairs_to_orders_map, cancellation_results):
                    if isinstance(cr, Exception) or cr["code"] != 0:
                        [
                            failed_cancellations.append(CancellationResult(client_order_id, False))
                            for client_order_id in trading_pairs_to_orders_map[trading_pair]
                        ]
                    else:
                        [
                            successful_cancellations.append(CancellationResult(client_order_id, True))
                            for client_order_id in trading_pairs_to_orders_map[trading_pair]
                        ]
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order. Check API key and network connection.",
            )

        return successful_cancellations + failed_cancellations

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        if self._position_mode is PositionMode.ONEWAY:
            pos_side = "Merged"
        else:
            if tracked_order.position is PositionAction.OPEN:
                pos_side = "Long" if tracked_order.trade_type is TradeType.BUY else "Short"
            else:
                pos_side = "Short" if tracked_order.trade_type is TradeType.BUY else "Long"
        api_params = {"clOrdID": order_id, "symbol": symbol, "posSide": pos_side}
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.CANCEL_ORDERS, params=api_params, is_auth_required=True
        )

        if cancel_result["code"] != CONSTANTS.SUCCESSFUL_RETURN_CODE:
            code = cancel_result["code"]
            message = cancel_result["msg"]
            raise IOError(f"{code} - {message}")
        is_order_canceled = CONSTANTS.ORDER_STATE[cancel_result["data"]["ordStatus"]] == OrderState.CANCELED

        return is_order_canceled

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
        api_params = {
            "symbol": symbol,
            "side": "Buy" if trade_type is TradeType.BUY else "Sell",
            "orderQtyRq": amount_str,
            "ordType": "Market" if order_type is OrderType.MARKET else "Limit",
            "clOrdID": order_id,
            "posSide": "Merged",
        }
        if order_type.is_limit_type():
            api_params["priceRp"] = price_str
        if order_type == OrderType.LIMIT_MAKER:
            api_params["timeInForce"] = "PostOnly"
        elif order_type == OrderType.MARKET:
            api_params["timeInForce"] = "ImmediateOrCancel"
        if self._position_mode is PositionMode.HEDGE:
            api_params["posSide"] = "Long" if trade_type is TradeType.BUY else "Short"
            if position_action == PositionAction.CLOSE:
                api_params["posSide"] = "Short" if trade_type is TradeType.BUY else "Long"

        order_result = await self._api_post(path_url=CONSTANTS.PLACE_ORDERS, data=api_params, is_auth_required=True)
        code = order_result.get("code")
        if code == 0 and order_result.get("data", {}).get("orderID", None) is not None:
            o_id = str(order_result["data"]["orderID"])
            transact_time = order_result["data"]["actionTimeNs"] * 1e-9
            return o_id, transact_time
        else:
            raise IOError(f"{code} - {order_result.get('msg')}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # Not required in Phemex because it reimplements _update_orders_fills
        return await self._update_orders_fills(orders=[order])

    async def _all_trades_details(self, trading_pair: str, start_time: float) -> List[Dict[str, Any]]:
        result = {}
        try:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            result = await self._api_get(
                path_url=CONSTANTS.GET_TRADES,
                params={"symbol": symbol, "start": int(start_time * 1e3), "limit": 200},
                is_auth_required=True,
            )
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().warning(f"There was an error requesting trades history for Phemex ({ex})")

        return result

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        # Reimplementing this method because Phemex does not provide an endpoint to request trades for a particular
        # order

        if len(orders) > 0:
            orders_by_id = dict()
            min_order_creation_time = defaultdict(lambda: self.current_timestamp)
            trading_pairs = set()
            for order in orders:
                orders_by_id[order.client_order_id] = order
                trading_pair = order.trading_pair
                trading_pairs.add(trading_pair)
                min_order_creation_time[trading_pair] = min(min_order_creation_time[trading_pair], order.creation_timestamp)
            tasks = [
                safe_ensure_future(
                    self._all_trades_details(trading_pair=trading_pair, start_time=min_order_creation_time[trading_pair])
                )
                for trading_pair in trading_pairs
            ]

            trades_data = []
            results = await safe_gather(*tasks)
            for result in results:
                for trades_for_market in result.get("data", {}).get("rows", []):
                    trades_data.append(trades_for_market)

            for trade_info in trades_data:
                client_order_id = trade_info["clOrdID"]
                tracked_order = orders_by_id.get(client_order_id)

                if tracked_order is not None:
                    position_action = tracked_order.position
                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=position_action,
                        percent_token=CONSTANTS.COLLATERAL_TOKEN,
                        flat_fees=[
                            TokenAmount(amount=Decimal(trade_info["execFeeRv"]), token=CONSTANTS.COLLATERAL_TOKEN)
                        ],
                    )
                    trade_update: TradeUpdate = TradeUpdate(
                        trade_id=trade_info["execID"],
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=trade_info["orderID"],
                        trading_pair=tracked_order.trading_pair,
                        fill_timestamp=trade_info["transactTimeNs"] * 1e-9,
                        fill_price=Decimal(trade_info["execPriceRp"]),
                        fill_base_amount=Decimal(trade_info["execQtyRq"]),
                        fill_quote_amount=Decimal(trade_info["execValueRv"]),
                        fee=fee,
                    )

                    self._order_tracker.process_trade_update(trade_update=trade_update)

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.GET_ORDERS,
            params={"symbol": trading_pair, "clOrdID": tracked_order.client_order_id},
            is_auth_required=True,
        )

        orders_data = response.get("data", {}).get("rows", [])

        if len(orders_data) == 0:
            raise IOError(f"Order not found for Client ID {tracked_order.client_order_id}")

        order_info = orders_data[0]
        order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=CONSTANTS.ORDER_STATE[order_info["ordStatus"]],
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=order_info["orderId"],
        )
        return order_update

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
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _process_user_stream_event(self, event_message: Dict[str, Any]):
        for balance in event_message.get("accounts_p", []):
            total_balance = Decimal(str(balance["accountBalanceRv"]))
            locked_balance = Decimal(str(balance["totalUsedBalanceRv"]))
            asset = balance["currency"]
            self._account_balances[asset] = total_balance
            self._account_available_balances[asset] = total_balance - locked_balance

        for trade_info in event_message.get("orders_p", []):
            client_order_id = trade_info["clOrdID"]
            tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)

            if tracked_order is not None:
                position_action = tracked_order.position
                fee = TradeFeeBase.new_perpetual_fee(
                    fee_schema=self.trade_fee_schema(),
                    position_action=position_action,
                    percent_token=CONSTANTS.COLLATERAL_TOKEN,
                    flat_fees=[TokenAmount(amount=Decimal(trade_info["execFeeRv"]), token=CONSTANTS.COLLATERAL_TOKEN)],
                )
                trade_update: TradeUpdate = TradeUpdate(
                    trade_id=trade_info["execID"],
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=trade_info["orderID"],
                    trading_pair=tracked_order.trading_pair,
                    fill_timestamp=trade_info["transactTimeNs"] * 1e-9,
                    fill_price=Decimal(trade_info["execPriceRp"]),
                    fill_base_amount=Decimal(trade_info["execQty"]),
                    fill_quote_amount=Decimal(trade_info["execValueRv"]),
                    fee=fee,
                )
                self._order_tracker.process_trade_update(trade_update=trade_update)

                order_update: OrderUpdate = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=trade_info["transactTimeNs"] * 1e-9,
                    new_state=CONSTANTS.ORDER_STATE[trade_info["ordStatus"]],
                    client_order_id=client_order_id,
                    exchange_order_id=trade_info["orderID"],
                )

                self._order_tracker.process_order_update(order_update)

        for position in event_message.get("positions_p", []):
            total_maint_margin_required = Decimal("0")
            try:
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(position["symbol"])
            except KeyError:
                # Ignore results for which their symbols is not tracked by the connector
                continue
            if position["posSide"] == "Merged":
                position_side: PositionSide = PositionSide.LONG if position["side"] == "Buy" else PositionSide.SHORT
            else:
                position_side: PositionSide = PositionSide.LONG if position["posSide"] == "Long" else PositionSide.SHORT
            position_mode = PositionMode.HEDGE if position["posMode"] == "Hedged" else PositionMode.ONEWAY
            amount = Decimal(position["size"])
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side, position_mode)
            if amount != Decimal("0"):
                _position = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=Decimal(position["unrealisedPnlRv"]),
                    entry_price=Decimal(position["avgEntryPriceRp"]),
                    amount=amount * Decimal("-1") if position_side is PositionSide.SHORT else amount,
                    leverage=Decimal(position.get("leverageRr")),
                )
                self._perpetual_trading.set_position(pos_key, _position)
            else:
                self._perpetual_trading.remove_position(pos_key)
            total_maint_margin_required += Decimal(position["maintMarginReqRr"])
            if Decimal(position["deleveragePercentileRr"]) > Decimal("0.90"):
                negative_pnls_msg = f"{hb_trading_pair}: {position['deleveragePercentileRr']}, "
                self.logger().warning(
                    "Margin Call: Your position risk is too high, and you are at risk of "
                    "liquidation. Close your positions or add additional margin to your wallet."
                )
                self.logger().info(
                    f"Margin Required: {total_maint_margin_required}. Negative PnL assets: {negative_pnls_msg}."
                )

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        :param exchange_info_dict: Trading rules dictionary response from the exchange
        """
        rules: list = exchange_info_dict.get("data", {}).get("perpProductsV2", [])
        return_val: list = []
        for rule in rules:
            try:
                if web_utils.is_exchange_information_valid(rule):
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["symbol"])

                    min_order_size = Decimal(rule["qtyStepSize"])
                    step_size = Decimal(rule["qtyStepSize"])
                    tick_size = Decimal(rule["tickSize"])
                    min_notional = Decimal(rule["minOrderValueRv"])
                    collateral_token = rule["settleCurrency"]

                    return_val.append(
                        TradingRule(
                            trading_pair,
                            min_order_size=min_order_size,
                            min_price_increment=Decimal(tick_size),
                            min_base_amount_increment=Decimal(step_size),
                            min_notional_size=Decimal(min_notional),
                            buy_order_collateral_token=collateral_token,
                            sell_order_collateral_token=collateral_token,
                        )
                    )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule: {rule}. Skipping.")
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(
            phemex_perpetual_utils.is_exchange_information_valid,
            exchange_info.get("data", {}).get("perpProductsV2", []),
        ):
            exchange_symbol = symbol_data["symbol"]
            base = symbol_data["contractUnderlyingAssets"]
            quote = symbol_data["settleCurrency"]
            trading_pair = combine_to_hb_trading_pair(base, quote)
            mapping[exchange_symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INFO,
            params={"currency": CONSTANTS.COLLATERAL_TOKEN},
            is_auth_required=True,
        )

        if account_info["code"] != CONSTANTS.SUCCESSFUL_RETURN_CODE:
            code = account_info["code"]
            message = account_info["msg"]
            raise IOError(f"{code} - {message}")

        account_data = account_info["data"]["account"]

        self._account_available_balances.clear()
        self._account_balances.clear()
        total_balance = Decimal(str(account_data["accountBalanceRv"]))
        locked_balance = Decimal(str(account_data["totalUsedBalanceRv"]))
        self._account_balances[account_data["currency"]] = total_balance
        self._account_available_balances[account_data["currency"]] = total_balance - locked_balance

    async def _request_positions(self):
        positions = await self._api_get(
            path_url=CONSTANTS.POSITION_INFO,
            params={"currency": CONSTANTS.COLLATERAL_TOKEN},
            is_auth_required=True,
        )
        return positions if positions is not None else {}

    async def _update_positions(self):
        positions = await self._request_positions()
        for position in positions.get("data", {}).get("positions", []):
            trading_pair = position.get("symbol")
            try:
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
                if hb_trading_pair not in self.trading_pairs:
                    continue
            except KeyError:
                # Ignore results for which their symbols is not tracked by the connector
                continue

            mid_price = self.get_mid_price(hb_trading_pair)
            if mid_price != s_decimal_NaN:

                position_mode = PositionMode.HEDGE if position["posMode"] == "Hedged" else PositionMode.ONEWAY
                if position["posSide"] == "Merged":
                    position_side: PositionSide = PositionSide.LONG if position["side"] == "Buy" else PositionSide.SHORT
                else:
                    position_side: PositionSide = PositionSide.LONG if position["posSide"] == "Long" else PositionSide.SHORT

                entry_price = Decimal(position.get("avgEntryPriceRp"))

                price_diff = mid_price - entry_price
                amount = Decimal(position.get("size"))
                unrealized_pnl = (
                    price_diff * amount if position_side == PositionSide.LONG else price_diff * amount * Decimal("-1")
                )
                leverage = Decimal(position.get("leverageRr"))
                pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side, position_mode)
                if amount != Decimal("0"):
                    _position = Position(
                        trading_pair=hb_trading_pair,
                        position_side=position_side,
                        unrealized_pnl=unrealized_pnl,
                        entry_price=entry_price,
                        amount=amount * Decimal("-1") if position_side is PositionSide.SHORT else amount,
                        leverage=leverage,
                    )
                    self._perpetual_trading.set_position(pos_key, _position)
                else:
                    self._perpetual_trading.remove_position(pos_key)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        self._position_mode = PositionMode.ONEWAY
        positions = await self._request_positions()
        for position in positions.get("data", {}).get("positions", []):
            trading_pair = position.get("symbol")
            try:
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
                if hb_trading_pair in self.trading_pairs:
                    self._position_mode = PositionMode.HEDGE if position["posMode"] == "Hedged" else PositionMode.ONEWAY
            except KeyError:
                continue
        return self._position_mode

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        response = await self._api_put(
            path_url=CONSTANTS.POSITION_MODE,
            params={
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                "targetPosMode": "OneWay" if mode == PositionMode.ONEWAY else "Hedged",
            },
            is_auth_required=True,
        )
        success = False
        msg = response["msg"]
        if msg == "" and response["code"] == 0:
            success = True
            self._position_mode = mode
        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }
        if self._position_mode is PositionMode.ONEWAY:
            params["leverageRr"] = str(leverage)
        else:
            params["longLeverageRr"] = str(leverage)
            params["shortLeverageRr"] = str(leverage)
        response = await self._api_put(
            path_url=CONSTANTS.POSITION_LEVERAGE,
            params=params,
            is_auth_required=True,
        )
        success = False
        msg = response["msg"]
        if msg == "" and response["code"] == 0:
            success = True
        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        payment_response = await self._api_get(
            path_url=CONSTANTS.FUNDING_PAYMENT,
            params={
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                "offset": 0,
                "limit": 200,
            },
            is_auth_required=True,
        )
        payments = payment_response.get("data", {}).get("rows", [])
        if len(payments) > 0:
            funding_payment = payments[0]
            payment = Decimal(funding_payment["execFeeRv"])
            funding_rate = Decimal(funding_payment["feeRateRr"])
            timestamp = funding_payment["createTime"]
        return timestamp, funding_rate, payment

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {"symbol": exchange_symbol, "resolution": 60}

        resp_json = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL,
            params=params,
        )

        price = 0
        kline = resp_json.get("data", {}).get("rows", [])
        if len(kline) > 0:
            price = float(kline[0][2])
        return price
