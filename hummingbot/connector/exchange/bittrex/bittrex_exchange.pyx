import asyncio
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple
from libc.stdint cimport int64_t
from bidict import bidict

from hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source import BittrexAPIOrderBookDataSource
from hummingbot.connector.exchange.bittrex import bittrex_constants as CONSTANTS, bittrex_web_utils as web_utils, bittrex_utils
from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    MarketTransactionFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

class BittrexExchange(ExchangePyBase):

    UPDATE_ORDERS_INTERVAL = 10.0

    def __init__(self,
                 bittrex_api_key: str,
                 bittrex_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        self.api_key = bittrex_api_key
        self.secret_key = bittrex_secret_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__()

    @property
    def name(self) -> str:
        return "bittrex"

    @property
    def authenticator(self) -> BittrexAuth:
        return BittrexAuth(self.api_key, self. secret_key)

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return None

    @property
    def client_order_id_max_length(self):
        return 40

    @property
    def client_order_id_prefix(self):
        return ""

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.SERVER_TIME_URL

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
        return [OrderType.LIMIT, OrderType.MARKET]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BittrexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal
                           ) -> Tuple[str, float]:

        path_url = CONSTANTS.ORDER_CREATION_URL
        body = {
            "marketSymbol": trading_pair,
            "direction": "BUY" if trade_type is TradeType.BUY else "SELL",
            "type": "LIMIT" if order_type is OrderType.LIMIT else "MARKET",
            "quantity": amount,
            "clientOrderId": order_id
        }
        if order_type is OrderType.LIMIT:
            body.update({
                "limit": price,
                "timeInForce": "GOOD_TIL_CANCELLED"
                # Available options [GOOD_TIL_CANCELLED, IMMEDIATE_OR_CANCEL,
                # FILL_OR_KILL, POST_ONLY_GOOD_TIL_CANCELLED]
            })
        elif order_type is OrderType.MARKET:
            body.update({
                "timeInForce": "IMMEDIATE_OR_CANCEL"
            })
        order_result = await self._api_post(
            path_url=path_url,
            params=body,
            data=body,
            is_auth_required=True)
        o_id = str(order_result["id"])
        transact_time = order_result["createdAt"] * 1e-3
        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {
            "id": order_id,
        }
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_DELETION_URL,
            params=api_params,
            is_auth_required=True)
        if cancel_result.get("status") == "CLOSED":
            return True
        return False

    #TODO refactor fees code
    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price,
                          object is_maker = None):
        # There is no API for checking fee
        # Fee info from https://bittrex.zendesk.com/hc/en-us/articles/115003684371
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("bittrex", is_maker)

    async def _update_balances(self):
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        path_url = "/balances"
        account_balances = await self._api_request("GET", path_url=path_url)

        for balance_entry in account_balances:
            asset_name = balance_entry["currencySymbol"]
            available_balance = Decimal(balance_entry["available"])
            total_balance = Decimal(balance_entry["total"])
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _format_trading_rules(self, markets: List) -> List[TradingRule]:
        retval = []
        for market in markets:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbo(market.get("symbol"))
                min_trade_size = market.get("minTradeSize")
                precision = market.get("precision")
                retval.append(TradingRule(trading_pair,
                                              min_order_size=min_trade_size,
                                              min_price_increment=Decimal(f"1e-{precision}"),
                                              min_base_amount_increment=Decimal(f"1e-{precision}"),
                                              min_notional_size=Decimal(f"1e-{precision}")
                                              ))
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {market}. Skipping.", exc_info=True)
        return retval


    async def list_orders(self) -> List[Any]:
        """
        Only a list of all currently open orders(does not include filled orders)
        :returns json response
        i.e.
        Result = [
              {
                "id": "string (uuid)",
                "marketSymbol": "string",
                "direction": "string",
                "type": "string",
                "quantity": "number (double)",
                "limit": "number (double)",
                "ceiling": "number (double)",
                "timeInForce": "string",
                "expiresAt": "string (date-time)",
                "clientOrderId": "string (uuid)",
                "fillQuantity": "number (double)",
                "commission": "number (double)",
                "proceeds": "number (double)",
                "status": "string",
                "createdAt": "string (date-time)",
                "updatedAt": "string (date-time)",
                "closedAt": "string (date-time)"
              }
              ...
            ]

        """
        path_url = "/orders/open"

        result = await self._api_request("GET", path_url=path_url)
        return result

    async def _update_order_status(self):
        cdef:
            # This is intended to be a backup measure to close straggler orders, in case Bittrex's user stream events
            # are not capturing the updates as intended. Also handles filled events that are not captured by
            # _user_stream_event_listener
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t> (self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t> (self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:

            tracked_orders = list(self._in_flight_orders.values())
            open_orders = await self.list_orders()
            open_orders = dict((entry["id"], entry) for entry in open_orders)

            for tracked_order in tracked_orders:
                try:
                    exchange_order_id = await tracked_order.get_exchange_order_id()
                except asyncio.TimeoutError:
                    if tracked_order.last_state == "FAILURE":
                        self.c_stop_tracking_order(client_order_id)
                        self.logger().warning(
                            f"No exchange ID found for {client_order_id} on order status update."
                            f" Order no longer tracked. This is most likely due to a POST_ONLY_NOT_MET error."
                        )
                        continue
                    else:
                        self.logger().error(f"Exchange order ID never updated for {tracked_order.client_order_id}")
                        raise
                client_order_id = tracked_order.client_order_id
                order = open_orders.get(exchange_order_id)

                # Do nothing, if the order has already been cancelled or has failed
                if client_order_id not in self._in_flight_orders:
                    continue

                if order is None:  # Handles order that are currently tracked but no longer open in exchange
                    self._order_not_found_records[client_order_id] = \
                        self._order_not_found_records.get(client_order_id, 0) + 1

                    if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                        # Wait until the order not found error have repeated for a few times before actually treating
                        # it as a fail. See: https://github.com/CoinAlpha/hummingbot/issues/601
                        continue
                    tracked_order.last_state = "CLOSED"
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(self._current_timestamp,
                                                client_order_id,
                                                tracked_order.order_type)
                    )
                    self.c_stop_tracking_order(client_order_id)
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: "
                        f"{tracked_order}",
                        app_warning_msg=f"Could not fetch updates for the order {client_order_id}. "
                                        f"Check API key and network connection."
                    )
                    continue

                order_state = order["status"]
                order_type = tracked_order.order_type.name.lower()
                trade_type = tracked_order.trade_type.name.lower()
                order_type_description = tracked_order.order_type_description

                executed_price = Decimal(order["limit"])
                executed_amount_diff = s_decimal_0

                remaining_size = Decimal(order["quantity"]) - Decimal(order["fillQuantity"])
                new_confirmed_amount = tracked_order.amount - remaining_size
                executed_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                tracked_order.executed_amount_base = new_confirmed_amount
                tracked_order.executed_amount_quote += executed_amount_diff * executed_price

                if executed_amount_diff > s_decimal_0:
                    self.logger().info(f"Filled {executed_amount_diff} out of {tracked_order.amount} of the "
                                       f"{order_type_description} order {tracked_order.client_order_id}.")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                         OrderFilledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id,
                                             tracked_order.trading_pair,
                                             tracked_order.trade_type,
                                             tracked_order.order_type,
                                             executed_price,
                                             executed_amount_diff,
                                             self.c_get_fee(
                                                 tracked_order.base_asset,
                                                 tracked_order.quote_asset,
                                                 tracked_order.order_type,
                                                 tracked_order.trade_type,
                                                 executed_price,
                                                 executed_amount_diff
                                             ),
                                             exchange_trade_id=str(int(self._time() * 1e6))
                                         ))

                if order_state == "CLOSED":
                    self._process_api_closed(order, tracked_order)

    def _process_api_closed(self, order: Dict, tracked_order: BittrexInFlightOrder):
        order_type = tracked_order.order_type
        trade_type = tracked_order.trade_type
        client_order_id = tracked_order.client_order_id
        if order["quantity"] == order["fillQuantity"]:  # Order COMPLETED
            tracked_order.last_state = "CLOSED"
            self.logger().info(f"The {order_type}-{trade_type} "
                               f"{client_order_id} has completed according to Bittrex order status API.")

            if tracked_order.trade_type is TradeType.BUY:
                self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                     BuyOrderCompletedEvent(
                                         self._current_timestamp,
                                         tracked_order.client_order_id,
                                         tracked_order.base_asset,
                                         tracked_order.quote_asset,
                                         tracked_order.executed_amount_base,
                                         tracked_order.executed_amount_quote,
                                         tracked_order.order_type))
            elif tracked_order.trade_type is TradeType.SELL:
                self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                     SellOrderCompletedEvent(
                                         self._current_timestamp,
                                         tracked_order.client_order_id,
                                         tracked_order.base_asset,
                                         tracked_order.quote_asset,
                                         tracked_order.executed_amount_base,
                                         tracked_order.executed_amount_quote,
                                         tracked_order.order_type))
        else:  # Order PARTIAL-CANCEL or CANCEL
            tracked_order.last_state = "CANCELED"
            self.logger().info(f"The {tracked_order.order_type}-{tracked_order.trade_type} "
                               f"{client_order_id} has been canceled according to Bittrex order status API.")
            self.c_trigger_event(self.MARKET_ORDER_CANCELED_EVENT_TAG,
                                 OrderCancelledEvent(
                                     self._current_timestamp,
                                     client_order_id
                                 ))

        self.c_stop_tracking_order(client_order_id)

    async def _iter_user_stream_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 1 second.", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_stream_queue():
            try:
                content = stream_message.get("content")
                event_type = stream_message.get("event_type")

                if event_type == "balance":  # Updates total balance and available balance of specified currency
                    balance_delta = content["delta"]
                    asset_name = balance_delta["currencySymbol"]
                    total_balance = Decimal(balance_delta["total"])
                    available_balance = Decimal(balance_delta["available"])
                    self._account_available_balances[asset_name] = available_balance
                    self._account_balances[asset_name] = total_balance
                elif event_type == "order":  # Updates track order status
                    safe_ensure_future(self._process_order_update_event(stream_message))
                elif event_type == "execution":
                    safe_ensure_future(self._process_execution_event(stream_message))

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _process_order_update_event(self, stream_message: Dict[str, Any]):
        content = stream_message["content"]
        order = content["delta"]
        order_status = order["status"]
        order_id = order["id"]
        tracked_order: BittrexInFlightOrder = None

        for o in self._in_flight_orders.values():
            exchange_order_id = await o.get_exchange_order_id()
            if exchange_order_id == order_id:
                tracked_order = o
                break

        if tracked_order and order_status == "CLOSED":
            if order["quantity"] == order["fillQuantity"]:
                tracked_order.last_state = "done"
                event = (self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG
                         if tracked_order.trade_type == TradeType.BUY
                         else self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG)
                event_class = (BuyOrderCompletedEvent
                               if tracked_order.trade_type == TradeType.BUY
                               else SellOrderCompletedEvent)

                try:
                    await asyncio.wait_for(tracked_order.wait_until_completely_filled(), timeout=1)
                except asyncio.TimeoutError:
                    self.logger().warning(
                        f"The order fill updates did not arrive on time for {tracked_order.client_order_id}. "
                        f"The complete update will be processed with incorrect information.")

                self.logger().info(f"The {tracked_order.trade_type.name} order {tracked_order.client_order_id} "
                                   f"has completed according to order delta websocket API.")
                self.c_trigger_event(event,
                                     event_class(
                                         self._current_timestamp,
                                         tracked_order.client_order_id,
                                         tracked_order.base_asset,
                                         tracked_order.quote_asset,
                                         tracked_order.executed_amount_base,
                                         tracked_order.executed_amount_quote,
                                         tracked_order.order_type
                                     ))
                self.c_stop_tracking_order(tracked_order.client_order_id)

            else:  # CANCEL
                self.logger().info(f"The order {tracked_order.client_order_id} has been canceled "
                                   f"according to Order Delta WebSocket API.")
                tracked_order.last_state = "cancelled"
                self.c_trigger_event(self.MARKET_ORDER_CANCELED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp,
                                                         tracked_order.client_order_id))
                self.c_stop_tracking_order(tracked_order.client_order_id)

    async def _process_execution_event(self, stream_message: Dict[str, Any]):
        content = stream_message["content"]
        events = content["deltas"]

        for execution_event in events:
            order_id = execution_event["orderId"]

            tracked_order = None
            for order in self._in_flight_orders.values():
                exchange_order_id = await order.get_exchange_order_id()
                if exchange_order_id == order_id:
                    tracked_order = order
                    break

            if tracked_order:
                updated = tracked_order.update_with_trade_update(execution_event)

                if updated:
                    self.logger().info(f"Filled {Decimal(execution_event['quantity'])} out of "
                                       f"{tracked_order.amount} of the "
                                       f"{tracked_order.order_type_description} order "
                                       f"{tracked_order.client_order_id}. - ws")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                         OrderFilledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id,
                                             tracked_order.trading_pair,
                                             tracked_order.trade_type,
                                             tracked_order.order_type,
                                             Decimal(execution_event["rate"]),
                                             Decimal(execution_event["quantity"]),
                                             AddedToCostTradeFee(
                                                 flat_fees=[
                                                     TokenAmount(
                                                         tracked_order.fee_asset, Decimal(execution_event["commission"])
                                                     )
                                                 ]
                                             ),
                                             exchange_trade_id=execution_event["id"]
                                         ))

    '''async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while polling updates.",
                                      exc_info=True,
                                      app_warning_msg=f"Could not fetch updates from Bittrex. "
                                                      f"Check API key and network connection.")
                await asyncio.sleep(5.0)'''

    '''async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60 * 5)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rule updates.",
                                      exc_info=True,
                                      app_warning_msg=f"Could not fetch updates from Bitrrex. "
                                                      f"Check API key and network connection.")
                await asyncio.sleep(0.5)'''


    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price, is_maker)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List):
        mapping = bidict()
        for symbol_data in filter(bittrex_utils.is_exchange_information_valid, exchange_info):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["baseCurrencySymbol"],
                                                                        quote=symbol_data["quoteCurrencySymbol"])
        self._set_trading_pair_symbol_map(mapping)

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        # This method should be removed and instead we should implement _get_last_traded_price
        return await BittrexAPIOrderBookDataSource.get_last_traded_prices(trading_pairs=trading_pairs)
