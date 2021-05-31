import logging
from typing import (
    Dict,
    List,
    Optional,
    Any,
    AsyncIterable,
)
from decimal import Decimal
import asyncio
# import json
# import aiohttp
import math
import time

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.core.clock import Clock
from hummingbot.core.utils import estimate_fee
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.digifinex.digifinex_global import DigifinexGlobal
from hummingbot.connector.exchange.digifinex.digifinex_order_book_tracker import DigifinexOrderBookTracker
from hummingbot.connector.exchange.digifinex.digifinex_user_stream_tracker import DigifinexUserStreamTracker
# from hummingbot.connector.exchange.digifinex.digifinex_auth import DigifinexAuth
from hummingbot.connector.exchange.digifinex.digifinex_in_flight_order import DigifinexInFlightOrder
from hummingbot.connector.exchange.digifinex import digifinex_utils
# from hummingbot.connector.exchange.digifinex import digifinex_constants as Constants
from hummingbot.core.data_type.common import OpenOrder
ctce_logger = None
s_decimal_NaN = Decimal("nan")


class DigifinexExchange(ExchangeBase):
    """
    DigifinexExchange connects with digifinex.com exchange and provides order book pricing, user account tracking and
    trading functionality.
    """
    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(self,
                 digifinex_api_key: str,
                 digifinex_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param key: The API key to connect to private digifinex.com APIs.
        :param secret: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._global = DigifinexGlobal(digifinex_api_key, digifinex_secret_key)
        # self._rest_api = DigifinexRestApi(self._digifinex_auth, self._http_client)
        self._order_book_tracker = DigifinexOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = DigifinexUserStreamTracker(self._global, trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders: Dict[str, DigifinexInFlightOrder] = {}  # Dict[client_order_id:str, DigifinexInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0

    @property
    def name(self) -> str:
        return "digifinex"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, DigifinexInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various connector's components.
        """
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "user_stream_initialized":
                self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
        }

    @property
    def ready(self) -> bool:
        """
        :return True when all statuses pass, this might take 5-10 seconds for all the connector's components and
        services to be ready.
        """
        return all(self.status_dict.values())

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        :return active in-flight orders in json format, is used to save in sqlite db.
        """
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
            if not value.is_done
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        self._in_flight_orders.update({
            key: DigifinexInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def start(self, clock: Clock, timestamp: float):
        """
        This function is called automatically by the clock.
        """
        super().start(clock, timestamp)

    def stop(self, clock: Clock):
        """
        This function is called automatically by the clock.
        """
        super().stop(clock)

    async def start_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        It starts tracking order book, polling trading rules,
        updating statuses and tracking user data.
        """
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        """
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def check_network(self) -> NetworkStatus:
        """
        This function is required by NetworkIterator base class and is called periodically to check
        the network connection. Simply ping the network (or call any light weight public API).
        """
        try:
            await self._global.rest_api.request("get", "ping")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _ = e
            self.logger().exception('check_network', stack_info=True)
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _trading_rules_polling_loop(self):
        """
        Periodically update trading rule.
        """
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Unexpected error while fetching trading rules. Error: {str(e)}",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from digifinex.com. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        instruments_info = await self._global.rest_api.request("get", path_url="markets")
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(instruments_info)

    def _format_trading_rules(self, instruments_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param instruments_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        {
            "data": [{
                "volume_precision": 4,
                "price_precision": 2,
                "market": "btc_usdt",
                "min_amount": 2,
                "min_volume": 0.0001
            }],
            "date": 1589873858,
            "code": 0
        }
        """
        result = {}
        for rule in instruments_info["data"]:
            try:
                trading_pair = digifinex_utils.convert_from_exchange_trading_pair(rule["market"])
                price_decimals = Decimal(str(rule["price_precision"]))
                quantity_decimals = Decimal(str(rule["volume_precision"]))
                # E.g. a price decimal of 2 means 0.01 incremental.
                price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
                quantity_step = Decimal("1") / Decimal(str(math.pow(10, quantity_decimals)))
                result[trading_pair] = TradingRule(trading_pair,
                                                   min_price_increment=price_step,
                                                   min_base_amount_increment=quantity_step)
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    def get_order_price_quantum(self, trading_pair: str, price: Decimal):
        """
        Returns a price step, a minimum price increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal):
        """
        Returns an order amount step, a minimum amount increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Buys an amount of base asset (of the given trading pair). This function returns immediately.
        To see an actual order, you'll have to wait for BuyOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-USDT) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns A new internal order id
        """
        order_id: str = digifinex_utils.get_new_client_order_id(True, trading_pair)
        safe_ensure_future(self._create_order(TradeType.BUY, order_id, trading_pair, amount, order_type, price))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Sells an amount of base asset (of the given trading pair). This function returns immediately.
        To see an actual order, you'll have to wait for SellOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-USDT) to sell from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns A new internal order id
        """
        order_id: str = digifinex_utils.get_new_client_order_id(False, trading_pair)
        safe_ensure_future(self._create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price))
        return order_id

    def cancel(self, trading_pair: str, order_id: str):
        """
        Cancel an order. This function returns immediately.
        To get the cancellation result, you'll have to wait for OrderCancelledEvent.
        :param trading_pair: The market (e.g. BTC-USDT) of the order.
        :param order_id: The internal order id (also called client_order_id)
        """
        tracked_order = self._in_flight_orders.get(order_id)
        if tracked_order is None:
            raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
        if tracked_order.exchange_order_id is None:
            self.ev_loop.run_until_complete(tracked_order.get_exchange_order_id())
        safe_ensure_future(self._execute_cancel(tracked_order))
        return order_id

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Decimal):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param order_type: The order type
        :param price: The order price
        """
        if not order_type.is_limit_type():
            raise Exception(f"Unsupported order type: {order_type}")
        trading_rule = self._trading_rules[trading_pair]

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        if amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")
        symbol = digifinex_utils.convert_to_exchange_trading_pair(trading_pair)
        api_params = {"symbol": symbol,
                      "type": trade_type.name.lower(),
                      "price": f"{price:f}",
                      "amount": f"{amount:f}",
                      # "client_oid": order_id
                      }
        if order_type is OrderType.LIMIT_MAKER:
            api_params["post_only"] = 1
        self.start_tracking_order(order_id,
                                  None,
                                  trading_pair,
                                  trade_type,
                                  price,
                                  amount,
                                  order_type
                                  )
        try:
            order_result = await self._global.rest_api.request("post", "spot/order/new", api_params, True)
            exchange_order_id = str(order_result["order_id"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
            event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.trigger_event(event_tag,
                               event_class(
                                   self.current_timestamp,
                                   order_type,
                                   trading_pair,
                                   amount,
                                   price,
                                   order_id
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to Digifinex for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = DigifinexInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def _execute_cancel(self, o: DigifinexInFlightOrder) -> str:
        """
        Executes order cancellation process by first calling cancel-order API. The API result doesn't confirm whether
        the cancellation is successful, it simply states it receives the request.
        :param trading_pair: The market trading pair
        :param order_id: The internal order id
        order.last_state to change to CANCELED
        """
        try:
            await self._global.rest_api.request(
                "post",
                "spot/order/cancel",
                {"order_id": o.exchange_order_id},
                True
            )
            if o.client_order_id in self._in_flight_orders:
                self.trigger_event(MarketEvent.OrderCancelled,
                                   OrderCancelledEvent(self.current_timestamp, o.client_order_id))
                del self._in_flight_orders[o.client_order_id]
            return o.exchange_order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {o.exchange_order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {o.exchange_order_id} on Digifinex. "
                                f"Check API key and network connection."
            )

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for web
        socket API updates.
        """
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Digifinex. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self._global.rest_api.get_balance()
        for account in account_info["list"]:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["free"]))
            self._account_balances[asset_name] = Decimal(str(account["total"]))
            remote_asset_names.add(asset_name)

        try:
            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]
        except Exception as e:
            self.logger().error(e)

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = []
            for tracked_order in tracked_orders:
                order_id = await tracked_order.get_exchange_order_id()
                tasks.append(self._global.rest_api.request("get",
                                                           "spot/order/detail",
                                                           {"order_id": order_id},
                                                           True))
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            update_results = await safe_gather(*tasks, return_exceptions=True)
            for update_result in update_results:
                if isinstance(update_result, Exception):
                    raise update_result
                if "data" not in update_result:
                    self.logger().info(f"_update_order_status result not in resp: {update_result}")
                    continue
                order_data = update_result["data"]
                self._process_rest_trade_details(order_data)
                self._process_order_status(order_data.get('order_id'), order_data.get('status'))

    def _process_order_status(self, exchange_order_id: str, status: int):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        """
        tracked_order = self.find_exchange_order(exchange_order_id)
        if tracked_order is None:
            return
        client_order_id = tracked_order.client_order_id
        # Update order execution status
        tracked_order.last_state = str(status)
        if tracked_order.is_cancelled:
            self.logger().info(f"Successfully cancelled order {client_order_id}.")
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(
                                   self.current_timestamp,
                                   client_order_id))
            tracked_order.cancelled_event.set()
            self.stop_tracking_order(client_order_id)
        # elif tracked_order.is_failure:
        #     self.logger().info(f"The market order {client_order_id} has failed according to order status API. "
        #                        f"Reason: {digifinex_utils.get_api_reason(order_msg['reason'])}")
        #     self.trigger_event(MarketEvent.OrderFailure,
        #                        MarketOrderFailureEvent(
        #                            self.current_timestamp,
        #                            client_order_id,
        #                            tracked_order.order_type
        #                        ))
        #     self.stop_tracking_order(client_order_id)

    def _process_rest_trade_details(self, order_detail_msg: Any):
        for trade_msg in order_detail_msg['detail']:
            """
            Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
            event if the total executed amount equals to the specified order amount.
            """
            # for order in self._in_flight_orders.values():
            #     await order.get_exchange_order_id()
            tracked_order = self.find_exchange_order(trade_msg['order_id'])
            if tracked_order is None:
                return

            updated = tracked_order.update_with_rest_order_detail(trade_msg)
            if not updated:
                return

            self.trigger_event(
                MarketEvent.OrderFilled,
                OrderFilledEvent(
                    self.current_timestamp,
                    tracked_order.client_order_id,
                    tracked_order.trading_pair,
                    tracked_order.trade_type,
                    tracked_order.order_type,
                    Decimal(str(trade_msg["executed_price"])),
                    Decimal(str(trade_msg["executed_amount"])),
                    estimate_fee.estimate_fee(self.name, tracked_order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]),
                    # TradeFee(0.0, [(trade_msg["fee_currency"], Decimal(str(trade_msg["fee"])))]),
                    exchange_trade_id=trade_msg["tid"]
                )
            )
            if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or \
                    tracked_order.executed_amount_base >= tracked_order.amount:
                tracked_order.last_state = "FILLED"
                self.logger().info(f"The {tracked_order.trade_type.name} order "
                                   f"{tracked_order.client_order_id} has completed "
                                   f"according to order status API.")
                event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
                    else MarketEvent.SellOrderCompleted
                event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
                    else SellOrderCompletedEvent
                self.trigger_event(event_tag,
                                   event_class(self.current_timestamp,
                                               tracked_order.client_order_id,
                                               tracked_order.base_asset,
                                               tracked_order.quote_asset,
                                               tracked_order.fee_asset,
                                               tracked_order.executed_amount_base,
                                               tracked_order.executed_amount_quote,
                                               tracked_order.fee_paid,
                                               tracked_order.order_type))
                self.stop_tracking_order(tracked_order.client_order_id)

    def find_exchange_order(self, exchange_order_id: str):
        for o in self._in_flight_orders.values():
            if o.exchange_order_id == exchange_order_id:
                return o

    def _process_order_message_traded(self, order_msg):
        tracked_order: DigifinexInFlightOrder = self.find_exchange_order(order_msg['id'])
        if tracked_order is None:
            return

        (delta_trade_amount, delta_trade_price) = tracked_order.update_with_order_update(order_msg)
        if not delta_trade_amount:
            return

        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                delta_trade_price,
                delta_trade_amount,
                estimate_fee.estimate_fee(self.name, tracked_order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]),
                # TradeFee(0.0, [(trade_msg["fee_currency"], Decimal(str(trade_msg["fee"])))]),
                exchange_trade_id='N/A'
            )
        )
        if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or \
                tracked_order.executed_amount_base >= tracked_order.amount:
            tracked_order.last_state = "2"
            self.logger().info(f"The {tracked_order.trade_type.name} order "
                               f"{tracked_order.client_order_id} has completed "
                               f"according to order status API.")
            event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
                else MarketEvent.SellOrderCompleted
            event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
                else SellOrderCompletedEvent
            self.trigger_event(event_tag,
                               event_class(self.current_timestamp,
                                           tracked_order.client_order_id,
                                           tracked_order.base_asset,
                                           tracked_order.quote_asset,
                                           tracked_order.fee_asset,
                                           tracked_order.executed_amount_base,
                                           tracked_order.executed_amount_quote,
                                           tracked_order.fee_paid,
                                           tracked_order.order_type))
            self.stop_tracking_order(tracked_order.client_order_id)

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        if self._trading_pairs is None:
            raise Exception("cancel_all can only be used when trading_pairs are specified.")
        cancellation_results = []
        try:
            # for trading_pair in self._trading_pairs:
            #     await self._global.rest_api.request(
            #         "post",
            #         "private/cancel-all-orders",
            #         {"instrument_name": digifinex_utils.convert_to_exchange_trading_pair(trading_pair)},
            #         True
            #     )

            open_orders = list(self._in_flight_orders.values())
            for o in open_orders:
                await self._execute_cancel(o)

            for cl_order_id, tracked_order in self._in_flight_orders.items():
                open_order = [o for o in open_orders if o.exchange_order_id == tracked_order.exchange_order_id]
                if not open_order:
                    cancellation_results.append(CancellationResult(cl_order_id, True))
                    # self.trigger_event(MarketEvent.OrderCancelled,
                    #                    OrderCancelledEvent(self.current_timestamp, cl_order_id))
                else:
                    cancellation_results.append(CancellationResult(cl_order_id, False))
        except Exception:
            self.logger().network(
                "Failed to cancel all orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel all orders on Digifinex. Check API key and network connection."
            )
        return cancellation_results

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return TradeFee(percent=self.estimate_fee_pct(is_maker))

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
                    app_warning_msg="Could not fetch user events from Digifinex. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        DigifinexAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if "method" not in event_message:
                    continue
                channel = event_message["method"]
                # if "user.trade" in channel:
                #     for trade_msg in event_message["result"]["data"]:
                #         await self._process_trade_message(trade_msg)
                if "order.update" in channel:
                    for order_msg in event_message["params"]:
                        self._process_order_status(order_msg['id'], order_msg['status'])
                        self._process_order_message_traded(order_msg)
                elif channel == "balance.update":
                    balances = event_message["params"]
                    for balance_entry in balances:
                        asset_name = balance_entry["currency"]
                        self._account_balances[asset_name] = Decimal(str(balance_entry["total"]))
                        self._account_available_balances[asset_name] = Decimal(str(balance_entry["free"]))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def get_open_orders(self) -> List[OpenOrder]:
        result = await self._global.rest_api.request(
            "get",
            "spot/order/current",
            {},
            True
        )
        ret_val = []
        for order in result["data"]:
            # if digifinex_utils.HBOT_BROKER_ID not in order["client_oid"]:
            #     continue
            if order["type"] not in ["buy", "sell"]:
                raise Exception(f"Unsupported order type {order['type']}")
            ret_val.append(
                OpenOrder(
                    client_order_id=None,
                    trading_pair=digifinex_utils.convert_from_exchange_trading_pair(order["symbol"]),
                    price=Decimal(str(order["price"])),
                    amount=Decimal(str(order["amount"])),
                    executed_amount=Decimal(str(order["executed_amount"])),
                    status=order["status"],
                    order_type=OrderType.LIMIT,
                    is_buy=True if order["type"] == "buy" else False,
                    time=int(order["created_date"]),
                    exchange_order_id=order["order_id"]
                )
            )
        return ret_val
