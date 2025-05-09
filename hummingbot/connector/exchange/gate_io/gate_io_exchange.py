import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS, gate_io_web_utils as web_utils
from hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source import GateIoAPIOrderBookDataSource
from hummingbot.connector.exchange.gate_io.gate_io_api_user_stream_data_source import GateIoAPIUserStreamDataSource
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GateIoExchange(ExchangePyBase):
    DEFAULT_DOMAIN = ""

    # Using 120 seconds here as Gate.io websocket is quiet
    TICK_INTERVAL_LIMIT = 120.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 gate_io_api_key: str,
                 gate_io_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = DEFAULT_DOMAIN):
        """
        :param gate_io_api_key: The API key to connect to private Gate.io APIs.
        :param gate_io_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self._gate_io_api_key = gate_io_api_key
        self._gate_io_secret_key = gate_io_secret_key
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs

        super().__init__(client_config_map)

    @property
    def authenticator(self):
        return GateIoAuth(
            api_key=self._gate_io_api_key,
            secret_key=self._gate_io_secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "gate_io"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.SYMBOL_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.SYMBOL_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.NETWORK_CHECK_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return CONSTANTS.ERR_LABEL_TIME_RELATED_ERROR in str(request_exception)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ERR_LABEL_ORDER_NOT_FOUND in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ERR_LABEL_ORDER_NOT_FOUND in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GateIoAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GateIoAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _format_trading_rules(self, raw_trading_pair_info: Dict[str, Any]) -> List[TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.

        :param raw_trading_pair_info: The json API response
        :return A dictionary of trading rules.

        Example raw_trading_pair_info:
        https://www.gate.io/docs/apiv4/en/#list-all-currency-pairs-supported
        """
        result = []
        for rule in raw_trading_pair_info:
            try:
                if not web_utils.is_exchange_information_valid(rule):
                    continue

                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["id"])

                min_amount_inc = Decimal(f"1e-{rule['amount_precision']}")
                min_price_inc = Decimal(f"1e-{rule['precision']}")
                min_amount = Decimal(str(rule.get("min_base_amount", min_amount_inc)))
                min_notional = Decimal(str(rule.get("min_quote_amount", min_price_inc)))
                result.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_amount,
                        min_price_increment=min_price_inc,
                        min_base_amount_increment=min_amount_inc,
                        min_notional_size=min_notional,
                        min_order_value=min_notional,
                    )
                )
            except Exception:
                self.logger().error(
                    f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        order_type_str = order_type.name.lower().split("_")[0]
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        # When type is market, it refers to different currency according to side
        # side : buy means quote currency, BTC_USDT means USDT
        # side : sell means base currency，BTC_USDT means BTC
        data = {
            "text": order_id,
            "currency_pair": symbol,
            "side": trade_type.name.lower(),
            "type": order_type_str,
            "amount": f"{amount:f}",
        }
        if order_type.is_limit_type():
            data.update({
                "price": f"{price:f}",
                "time_in_force": "gtc"
            })
            if order_type is OrderType.LIMIT_MAKER:
                data.update({"time_in_force": "poc"})
        else:
            data.update({
                "time_in_force": "ioc",
            })
            if trade_type.name.lower() == 'buy':
                if price.is_nan():
                    price = self.get_price_for_volume(
                        trading_pair,
                        True,
                        amount
                    ).result_price
                data.update({
                    "amount": f"{price * amount:f}",
                })

        # RESTRequest does not support json, and if we pass a dict
        # the underlying aiohttp will encode it to params
        data = data
        endpoint = CONSTANTS.ORDER_CREATE_PATH_URL
        order_result = await self._api_post(
            path_url=endpoint,
            data=data,
            is_auth_required=True,
            limit_id=endpoint,
        )
        if order_result.get("status") in {"cancelled"}:
            raise IOError({"label": "ORDER_REJECTED", "message": "Order rejected."})
        exchange_order_id = str(order_result["id"])
        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        This implementation-specific method is called by _cancel
        returns True if successful
        """
        canceled = False
        exchange_order_id = await tracked_order.get_exchange_order_id()
        params = {
            'currency_pair': await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        }
        resp = await self._api_delete(
            path_url=CONSTANTS.ORDER_DELETE_PATH_URL.format(order_id=exchange_order_id),
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_DELETE_LIMIT_ID,
        )
        canceled = resp.get("status") == "cancelled"
        return canceled

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        account_info = ""
        try:
            account_info = await self._api_get(
                path_url=CONSTANTS.USER_BALANCES_PATH_URL,
                is_auth_required=True,
                limit_id=CONSTANTS.USER_BALANCES_PATH_URL
            )
            self._process_balance_message(account_info)
        except Exception as e:
            self.logger().network(
                f"Unexpected error while fetching balance update - {str(e)}", exc_info=True,
                app_warning_msg=(f"Could not fetch balance update from {self.name_cap}"))
            raise e
        return account_info

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        try:
            exchange_order_id = await order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "currency_pair": trading_pair,
                    "order_id": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL)

            for trade_fill in all_fills_response:
                trade_update = self._create_trade_update_with_order_fill_data(
                    order_fill=trade_fill,
                    order=order)
                trade_updates.append(trade_update)

        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id} "
                          "- waiting for exchange order id.")

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
            updated_order_data = await self._api_get(
                path_url=CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=exchange_order_id),
                params={
                    "currency_pair": trading_pair
                },
                is_auth_required=True,
                limit_id=CONSTANTS.ORDER_STATUS_LIMIT_ID)

            order_update = self._create_order_update_with_order_status_data(
                order_status=updated_order_data,
                order=tracked_order)
        except asyncio.TimeoutError:
            raise IOError(f"Skipped order status update for {tracked_order.client_order_id}"
                          f" - waiting for exchange order id.")

        return order_update

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = [
            CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USER_BALANCE_ENDPOINT_NAME,
        ]
        async for event_message in self._iter_user_event_queue():
            channel: str = event_message.get("channel", None)
            results: List[Dict[str, Any]] = event_message.get("result", None)
            try:
                if channel not in user_channels:
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue

                if channel == CONSTANTS.USER_TRADES_ENDPOINT_NAME:
                    for trade_msg in results:
                        self._process_trade_message(trade_msg)
                elif channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                    for order_msg in results:
                        self._process_order_message(order_msg)
                elif channel == CONSTANTS.USER_BALANCE_ENDPOINT_NAME:
                    self._process_balance_message_ws(results)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _normalise_order_message_state(self, order_msg: Dict[str, Any], tracked_order):
        state = None
        # we do not handle:
        #   "failed" because it is handled by create order
        #   "put" as the exchange order id is returned in the create order response
        #   "open" for same reason

        # same field for both WS and REST
        amount_left = Decimal(order_msg.get("left"))
        filled_amount = Decimal(order_msg.get("filled_total"))

        # WS
        if "event" in order_msg:
            event_type = order_msg.get("event")
            if event_type == "update":
                state = OrderState.FILLED
                if amount_left > 0:
                    state = OrderState.PARTIALLY_FILLED
            if event_type == "finish":
                finish_as = order_msg.get("finish_as")
                if finish_as == "filled" or finish_as == "ioc":
                    state = OrderState.FILLED
                elif finish_as == "cancelled":
                    state = OrderState.CANCELED
                elif finish_as == "open" and filled_amount > 0:
                    state = OrderState.PARTIALLY_FILLED
        else:
            status = order_msg.get("status")
            if status == "closed":
                finish_as = order_msg.get("finish_as")
                if finish_as == "filled" or finish_as == "ioc":
                    state = OrderState.FILLED
                elif finish_as == "cancelled":
                    state = OrderState.CANCELED
                elif finish_as == "open" and filled_amount > 0:
                    state = OrderState.PARTIALLY_FILLED
            if status == "cancelled":
                state = OrderState.CANCELED
        return state

    def _create_order_update_with_order_status_data(self, order_status: Dict[str, Any], order: InFlightOrder):
        client_order_id = str(order_status.get("text", ""))
        state = self._normalise_order_message_state(order_status, order) or order.current_state

        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=int(order_status["update_time"]),
            new_state=state,
            client_order_id=client_order_id,
            exchange_order_id=str(order_status["id"]),
        )
        return order_update

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancelation or failure event if needed.

        :param order_msg: The order response from either REST or web socket API (they are of the same format)

        Example Order:
        https://www.gate.io/docs/apiv4/en/#list-orders
        """
        client_order_id = str(order_msg.get("text", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        order_update = self._create_order_update_with_order_status_data(order_status=order_msg, order=tracked_order)
        self._order_tracker.process_order_update(order_update=order_update)

    def _create_trade_update_with_order_fill_data(
            self,
            order_fill: Dict[str, Any],
            order: InFlightOrder):

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=order_fill["fee_currency"],
            flat_fees=[TokenAmount(
                amount=Decimal(order_fill["fee"]),
                token=order_fill["fee_currency"]
            )]
        )
        trade_update = TradeUpdate(
            trade_id=str(order_fill["id"]),
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(order_fill["amount"]),
            fill_quote_amount=Decimal(order_fill["amount"]) * Decimal(order_fill["price"]),
            fill_price=Decimal(order_fill["price"]),
            fill_timestamp=order_fill["create_time"],
        )
        return trade_update

    def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        Example Trade:
        https://www.gate.io/docs/apiv4/en/#retrieve-market-trades
        """
        client_order_id = client_order_id or str(trade["text"])
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if tracked_order is None:
            self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
        else:
            trade_update = self._create_trade_update_with_order_fill_data(
                order_fill=trade,
                order=tracked_order)
            self._order_tracker.process_trade_update(trade_update)

    def _process_balance_message(self, balance_update):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        for account in balance_update:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["locked"])) + Decimal(str(account["available"]))
            remote_asset_names.add(asset_name)
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _process_balance_message_ws(self, balance_update):
        for account in balance_update:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["total"]))

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(web_utils.is_exchange_information_valid, exchange_info):
            mapping[symbol_data["id"]] = combine_to_hb_trading_pair(base=symbol_data["base"],
                                                                    quote=symbol_data["quote"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "currency_pair": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PATH_URL,
            params=params
        )

        return float(resp_json[0]["last"])
