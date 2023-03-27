import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.phemex_perpetual import (
    phemex_perpetual_constants as CONSTANTS,
    phemex_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_api_order_book_data_source import (
    PhemexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_api_user_stream_data_source import (
    PhemexPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_auth import PhemexPerpetualAuth
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

bpm_logger = None


class PhemexPerpetualDerivative(PerpetualDerivativePyBase):
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
        domain: str = CONSTANTS.DOMAIN,
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
        """
        Documentation doesn't make this clear.
        To-do: Confirm manually or from their team.
        """
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return status_update_exception["bizError"] == CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return cancelation_exception["bizError"] in CONSTANTS.UNKNOWN_ORDER_ERROR_CODE

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
            connector=self,
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
            """To-Do: Update
            self._update_balances(),
            self._update_positions(),""",
        )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        posSide = ""
        if self._position_mode is PositionMode.ONEWAY:
            posSide = "Merged"
        else:
            posSide = "Long" if tracked_order.trade_type is TradeType.BUY else "Short"
        api_params = {"clOrdID": order_id, "symbol": symbol, "posSide": posSide}
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.CANCEL_ORDERS, params=api_params, is_auth_required=True
        )
        if cancel_result.get("data", {}).get("bizError") == CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE:
            self.logger().debug(f"The order {order_id} does not exist or cannot be cancelled on Phemex Perpetuals. ")
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(cancel_result.get("data", {}).get("bizError"))
        if cancel_result.get("code") == 0 and cancel_result.get("data", {}).get("bizError") == 0:
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
        api_params = {
            "symbol": symbol,
            "side": "Buy" if trade_type is TradeType.BUY else "Sell",
            "orderQtyRq": amount_str,
            "ordType": "Market" if order_type is OrderType.MARKET else "Limit",
            "clOrdID": order_id,
        }
        if order_type.is_limit_type():
            api_params["priceRp"] = price_str
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = "GoodTillCancel"
        if order_type == OrderType.LIMIT_MAKER:
            api_params["timeInForce"] = "PostOnly"
        if self._position_mode is PositionMode.ONEWAY:
            api_params["posSide"] = "Merged"
        else:
            api_params["posSide"] = "Long" if position_action == PositionAction.OPEN else "Short"

        order_result = await self._api_post(path_url=CONSTANTS.PLACE_ORDERS, data=api_params, is_auth_required=True)
        o_id = str(order_result["data"]["orderID"])
        transact_time = order_result["data"]["actionTimeNs"] * 1e-9
        return o_id, transact_time

    async def _all_trade_updates_for_order(self, tracked_order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            # exchange_order_id = await tracked_order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                params={"symbol": trading_pair, "execType": 1, "limit": 200},  # Normal trades
                is_auth_required=True,
            )

            for trade in all_fills_response.get("data", {}).get("rows", []):
                # To-do: Enquire for their team how to know the order trades in trade updates are associated with - https://phemex-docs.github.io/#query-user-trade-2
                continue

        except asyncio.TimeoutError:
            raise IOError(
                f"Skipped order update with order fills for {tracked_order.client_order_id} "
                "- waiting for exchange order id."
            )

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        order_update = await self._api_get(
            path_url=CONSTANTS.GET_ORDERS,
            params={"symbol": trading_pair, "clOrdID": tracked_order.client_order_id},
            is_auth_required=True,
        )
        _order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_update["updateTime"] * 1e-3,
            new_state=CONSTANTS.ORDER_STATE[order_update["status"]],
            client_order_id=order_update["clientOrderId"],
            exchange_order_id=order_update["orderId"],
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
                    app_warning_msg="Could not fetch user events from Phemex. Check API key and network connection.",
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
        event_type = event_message.get("e")
        if event_type == "ORDER_TRADE_UPDATE":

            """trade_update: TradeUpdate = TradeUpdate(

                        )
                        self._order_tracker.process_trade_update(trade_update)
            AND
                        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                        if tracked_order is not None:
                            order_update: OrderUpdate = OrderUpdate(

                            )

                            self._order_tracker.process_order_update(order_update)"""

        elif event_type == "ACCOUNT_UPDATE":
            """

                        position.update_position(position_side=PositionSide[asset["ps"]],
                                                    unrealized_pnl=Decimal(asset["up"]),
                                                    entry_price=Decimal(asset["ep"]),
                                                    amount=Decimal(asset["pa"]))
            OR
                        await self._update_positions()
            """

        elif event_type == "MARGIN_CALL":
            """self.logger().warning("Margin Call: Your position risk is too high, and you are at risk of "
                                  "liquidation. Close your positions or add additional margin to your wallet.")
            self.logger().info(f"Margin Required: {total_maint_margin_required}. "
                               f"Negative PnL assets: {negative_pnls_msg}.")"""

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange
        """
        return  # To-do

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        return  # To-do

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        return  # To-do

    async def _update_positions(self):
        """
        if _position:
            self._perpetual_trading.set_position(pos_key, _position)
        else:
            self._perpetual_trading.remove_position(pos_key)
        """
        return  # To-do

    async def _update_order_status(self):
        """
        Calls the REST API to get order/trade updates for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            tracked_orders = list(self._order_tracker.active_orders.values())
            tasks = [
                self._api_request(
                    path_url=CONSTANTS.GET_ORDERS,
                    params={
                        "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair),
                        "origClientOrderId": order.client_order_id,
                    },
                    method=RESTMethod.GET,
                    is_auth_required=True,
                    return_err=True,
                )
                for order in tracked_orders
            ]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._order_tracker.all_orders:
                    continue
                if order_update["bizError"] != 0:
                    await self._order_tracker.process_order_not_found(client_order_id)

                new_order_update: OrderUpdate = OrderUpdate(
                    trading_pair=await self.trading_pair_associated_to_exchange_symbol(order_update["symbol"]),
                    update_timestamp=order_update["actionTimeNs"] * 1e-9,
                    new_state=CONSTANTS.ORDER_STATE[order_update["ordStatus"]],
                    client_order_id=order_update["clOrdId"],
                    exchange_order_id=order_update["orderId"],
                )

                self._order_tracker.process_order_update(new_order_update)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        # To-do:
        pass

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        pass  # To-do
