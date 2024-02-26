import asyncio
import logging
import math
import time
import traceback
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional

import aiohttp
from async_timeout import timeout

import hummingbot.connector.exchange.msamex.msamex_http_utils as http_utils
from hummingbot.connector.exchange.msamex.msamex_api_order_book_data_source import (
    mSamexAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.msamex.msamex_auth import mSamexAuth
from hummingbot.connector.exchange.msamex.msamex_constants import Constants
from hummingbot.connector.exchange.msamex.msamex_in_flight_order import mSamexInFlightOrder
from hummingbot.connector.exchange.msamex.msamex_order_book_tracker import mSamexOrderBookTracker
from hummingbot.connector.exchange.msamex.msamex_user_stream_tracker import mSamexUserStreamTracker
from hummingbot.connector.exchange.msamex.msamex_utils import (
    mSamexAPIError,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    get_new_client_order_id,
    str_date_to_ts,
)
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OpenOrder, OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

ctce_logger = None
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class mSamexExchange(ExchangeBase):
    """
    mSamexExchange connects with mSamex.io exchange and provides order book pricing, user account tracking and
    trading functionality.
    """
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3
    ORDER_NOT_EXIST_CANCEL_COUNT = 2
    ORDER_NOT_CREATED_ID_COUNT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 msamex_api_key: str,
                 msamex_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param msamex_api_key: The API key to connect to private mSamex.io APIs.
        :param msamex_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__(client_config_map)
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._throttler = AsyncThrottler(Constants.RATE_LIMITS, self._client_config.rate_limits_share_pct)
        self._msamex_auth = mSamexAuth(msamex_api_key, msamex_secret_key)
        self._set_order_book_tracker(mSamexOrderBookTracker(
            throttler=self._throttler,
            trading_pairs=trading_pairs))
        self._user_stream_tracker = mSamexUserStreamTracker(
            throttler=self._throttler,
            msamex_auth=self._msamex_auth,
            trading_pairs=trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, mSamexInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._order_not_created_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0

    @property
    def name(self) -> str:
        return "msamex"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self.order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, mSamexInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various connector's components.
        """
        return {
            "order_books_initialized": self.order_book_tracker.ready,
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

    def _sleep_time(self, delay: int = 0):
        """
        Function created to enable patching during unit tests execution.
        """
        return delay

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        self._in_flight_orders.update({
            key: mSamexInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT, OrderType.MARKET]

    def start(self, clock: Clock, timestamp: float):
        """
        This function is called automatically by the clock.
        """
        if self._poll_notifier.is_set():
            self._poll_notifier.clear()
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
        self.order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        """
        # Resets timestamps for status_polling_task
        self._last_poll_timestamp = 0
        self._last_timestamp = 0

        self.order_book_tracker.stop()
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
            await self._api_request(method="GET", endpoint=Constants.ENDPOINT['NETWORK_CHECK'])
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _trading_rules_polling_loop(self):
        """
        Periodically update trading rule.
        """
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(Constants.INTERVAL_TRADING_RULES)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Unexpected error while fetching trading rules. Error: {str(e)}",
                                      exc_info=True,
                                      app_warning_msg=("Could not fetch new trading rules from "
                                                       f"{Constants.EXCHANGE_NAME}. Check network connection."))
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        symbols_info = await self._api_request("GET", endpoint=Constants.ENDPOINT['SYMBOL'])
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(symbols_info)

    def _format_trading_rules(self, symbols_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param symbols_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        [
            {
                id: "btcusdt",
                name: "BTC/USDT",
                base_unit: "btc",
                quote_unit: "usdt",
                min_price: "0.01",
                max_price: "200000.0",
                min_amount: "0.00000001",
                amount_precision: 8,
                price_precision: 2,
                state: "enabled"
            }
        ]
        """
        result = {}
        for rule in symbols_info:
            try:
                trading_pair = convert_from_exchange_trading_pair(rule["id"])
                min_amount = Decimal(rule["min_amount"])
                min_notional = min(Decimal(rule["min_price"]) * min_amount, Decimal("0.00000001"))
                result[trading_pair] = TradingRule(trading_pair,
                                                   min_order_size=min_amount,
                                                   min_base_amount_increment=Decimal(f"1e-{rule['amount_precision']}"),
                                                   min_notional_size=min_notional,
                                                   min_price_increment=Decimal(f"1e-{rule['price_precision']}"))
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _api_request(self,
                           method: str,
                           endpoint: str,
                           params: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           try_count: int = 0,
                           limit_id: Optional[str] = None,
                           disable_retries: bool = False):
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param endpoint: The path url or the API end point
        :param params: Additional get/post parameters
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        shared_client = await self._http_client()

        parsed_response = await http_utils.api_call_with_retries(
            method=method,
            endpoint=endpoint,
            auth_headers=self._msamex_auth.get_headers if is_auth_required else None,
            params=params,
            shared_client=shared_client,
            throttler=self._throttler,
            limit_id=limit_id or endpoint,
            try_count=try_count,
            logger=self.logger(),
            disable_retries=disable_retries)

        if "errors" in parsed_response or "error" in parsed_response:
            parsed_response['errors'] = parsed_response.get('errors', parsed_response.get('error'))
            raise mSamexAPIError(parsed_response)
        return parsed_response

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
        if trading_pair not in self.order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self.order_book_tracker.order_books[trading_pair]

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
        order_id: str = get_new_client_order_id(True, trading_pair)
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
        order_id: str = get_new_client_order_id(False, trading_pair)
        safe_ensure_future(self._create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price))
        return order_id

    def cancel(self, trading_pair: str, order_id: str):
        """
        Cancel an order. This function returns immediately.
        To get the cancellation result, you'll have to wait for OrderCancelledEvent.
        :param trading_pair: The market (e.g. BTC-USDT) of the order.
        :param order_id: The internal order id (also called client_order_id)
        """
        safe_ensure_future(self._execute_cancel(trading_pair, order_id))
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
        trading_rule = self._trading_rules[trading_pair]

        try:
            amount = self.quantize_order_amount(trading_pair, amount)
            price = self.quantize_order_price(trading_pair, s_decimal_0 if math.isnan(price) else price)
            if amount < trading_rule.min_order_size:
                raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")
            order_type_str = order_type.name.lower().split("_")[0]
            api_params = {"market": convert_to_exchange_trading_pair(trading_pair),
                          "side": trade_type.name.lower(),
                          "ord_type": order_type_str,
                          # "price": f"{price:f}",
                          "client_id": order_id,
                          "volume": f"{amount:f}",
                          }
            if order_type is not OrderType.MARKET:
                api_params['price'] = f"{price:f}"
            # if order_type is OrderType.LIMIT_MAKER:
            #     api_params["postOnly"] = "true"
            self.start_tracking_order(order_id, None, trading_pair, trade_type, price, amount, order_type)

            order_result = await self._api_request("POST",
                                                   Constants.ENDPOINT["ORDER_CREATE"],
                                                   params=api_params,
                                                   is_auth_required=True,
                                                   limit_id=Constants.RL_ID_ORDER_CREATE,
                                                   disable_retries=True
                                                   )
            exchange_order_id = str(order_result["id"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
            else:
                raise Exception('Order not tracked.')
            if trade_type is TradeType.BUY:
                event_tag = MarketEvent.BuyOrderCreated
                event_cls = BuyOrderCreatedEvent
            else:
                event_tag = MarketEvent.SellOrderCreated
                event_cls = SellOrderCreatedEvent
            self.trigger_event(event_tag,
                               event_cls(self.current_timestamp, order_type, trading_pair, amount, price, order_id,
                                         exchange_order_id))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if isinstance(e, mSamexAPIError):
                error_reason = e.error_payload.get('error', {}).get('message', e.error_payload.get('errors'))
            else:
                error_reason = e
            if error_reason and "upstream connect error" not in str(error_reason):
                self.stop_tracking_order(order_id)
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            else:
                self._order_not_created_records[order_id] = 0
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to {Constants.EXCHANGE_NAME} for "
                f"{amount} {trading_pair} {price} - {error_reason}.",
                exc_info=True,
                app_warning_msg=(f"Error submitting order to {Constants.EXCHANGE_NAME} - {error_reason}.")
            )

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
        self._in_flight_orders[order_id] = mSamexInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            creation_timestamp=self.current_timestamp
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]
        if order_id in self._order_not_found_records:
            del self._order_not_found_records[order_id]
        if order_id in self._order_not_created_records:
            del self._order_not_created_records[order_id]

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> CancellationResult:
        """
        Executes order cancellation process by first calling cancel-order API. The API result doesn't confirm whether
        the cancellation is successful, it simply states it receives the request.
        :param trading_pair: The market trading pair (Unused during cancel on mSamex.io)
        :param order_id: The internal order id
        order.last_state to change to CANCELED
        """
        order_state, errors_found = None, {}
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                self.logger().warning(f"Failed to cancel order {order_id}. Order not found in inflight orders.")
            elif not tracked_order.is_local:
                if tracked_order.exchange_order_id is None:
                    try:
                        async with timeout(6):
                            await tracked_order.get_exchange_order_id()
                    except Exception:
                        order_state = "reject"
                exchange_order_id = tracked_order.exchange_order_id
                response = await self._api_request("POST",
                                                   Constants.ENDPOINT["ORDER_DELETE"].format(id=exchange_order_id),
                                                   is_auth_required=True,
                                                   limit_id=Constants.RL_ID_ORDER_DELETE)
                if isinstance(response, dict):
                    order_state = response.get("state", None)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self.logger().info(f"The order {order_id} could not be canceled due to a timeout."
                               " The action will be retried later.")
            errors_found = {"message": "Timeout during order cancelation"}
        except mSamexAPIError as e:
            errors_found = e.error_payload.get('errors', e.error_payload)
            if isinstance(errors_found, dict):
                order_state = errors_found.get("state", None)
            if order_state is None or 'market.order.invaild_id_or_uuid' in errors_found:
                self._order_not_found_records[order_id] = self._order_not_found_records.get(order_id, 0) + 1

        if order_state in Constants.ORDER_STATES['CANCEL_WAIT'] or \
                self._order_not_found_records.get(order_id, 0) >= self.ORDER_NOT_EXIST_CANCEL_COUNT:
            self.logger().info(f"Successfully canceled order {order_id} on {Constants.EXCHANGE_NAME}.")
            self.stop_tracking_order(order_id)
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(self.current_timestamp, order_id))
            tracked_order.cancelled_event.set()
            return CancellationResult(order_id, True)
        else:
            if not tracked_order or not tracked_order.is_local:
                err_msg = errors_found.get('message', errors_found) if isinstance(errors_found, dict) else errors_found
                self.logger().network(
                    f"Failed to cancel order - {order_id}: {err_msg}",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel the order {order_id} on {Constants.EXCHANGE_NAME}. "
                                    f"Check API key and network connection."
                )
            return CancellationResult(order_id, False)

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for web
        socket API updates.
        """
        while True:
            try:
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
                warn_msg = (f"Could not fetch account updates from {Constants.EXCHANGE_NAME}. "
                            "Check API key and network connection.")
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg=warn_msg)
                await asyncio.sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self._api_request("GET", Constants.ENDPOINT["USER_BALANCES"], is_auth_required=True)
        for account in account_info:
            asset_name = account["currency"].upper()
            self._account_available_balances[asset_name] = Decimal(str(account["balance"]))
            self._account_balances[asset_name] = Decimal(str(account["locked"])) + Decimal(str(account["balance"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def stop_tracking_order_exceed_not_found_limit(self, tracked_order: mSamexInFlightOrder):
        """
        Increments and checks if the tracked order has exceed the ORDER_NOT_EXIST_CONFIRMATION_COUNT limit.
        If true, Triggers a MarketOrderFailureEvent and stops tracking the order.
        """
        client_order_id = tracked_order.client_order_id
        self._order_not_found_records[client_order_id] = self._order_not_found_records.get(client_order_id, 0) + 1
        if self._order_not_found_records[client_order_id] >= self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
            # Wait until the order not found error have repeated a few times before actually treating
            # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp, client_order_id, tracked_order.order_type))
            tracked_order.last_state = "fail"
            self.stop_tracking_order(client_order_id)

    async def _process_stuck_order(self, tracked_order):
        order_id = tracked_order.client_order_id
        open_orders = await self.get_open_orders()
        matched_orders = [order for order in open_orders if str(order.client_order_id) == str(order_id)]

        if len(matched_orders) == 1:
            tracked_order.update_exchange_order_id(str(matched_orders[0].exchange_order_id))
            del self._order_not_created_records[order_id]

            return

        self._order_not_created_records[order_id] = self._order_not_created_records.get(order_id, 0) + 1
        if self._order_not_created_records[order_id] >= self.ORDER_NOT_CREATED_ID_COUNT:
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp, order_id, tracked_order.order_type))
            tracked_order.last_state = "fail"
            self.stop_tracking_order(order_id)

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / Constants.UPDATE_ORDER_STATUS_INTERVAL)
        current_tick = int(self.current_timestamp / Constants.UPDATE_ORDER_STATUS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = []
            for tracked_order in tracked_orders:
                if tracked_order.exchange_order_id is None:
                    # Try waiting for the ID once
                    try:
                        async with timeout(self._sleep_time(5)):
                            await tracked_order.get_exchange_order_id()
                    except Exception:
                        pass
                    # Dispatch future to query open orders for the ID
                    safe_ensure_future(self._process_stuck_order(tracked_order))
                    # Try waiting for ID again, skip it for now if failed.
                    try:
                        async with timeout(self._sleep_time(8)):
                            await tracked_order.get_exchange_order_id()
                    except Exception:
                        continue
                exchange_order_id = tracked_order.exchange_order_id
                tasks.append(self._api_request("GET",
                                               Constants.ENDPOINT["ORDER_STATUS"].format(id=exchange_order_id),
                                               is_auth_required=True,
                                               limit_id=Constants.RL_ID_ORDER_STATUS))
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            responses = await safe_gather(*tasks, return_exceptions=True)
            for response, tracked_order in zip(responses, tracked_orders):
                if isinstance(response, mSamexAPIError):
                    err = response.error_payload.get('errors', response.error_payload)
                    if "record.not_found" in err:
                        self.stop_tracking_order_exceed_not_found_limit(tracked_order=tracked_order)
                    else:
                        continue
                elif "id" not in response:
                    self.logger().info(f"_update_order_status order id not in resp: {response}")
                    continue
                else:
                    self._process_order_message(response)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        Example Order:
        {
            "id": 9401,
            "market": "rogerbtc",
            "kind": "ask",
            "side": "sell",
            "ord_type": "limit",
            "price": "0.00000099",
            "avg_price": "0.00000099",
            "state": "wait",
            "origin_volume": "7000.0",
            "remaining_volume": "2810.1",
            "executed_volume": "4189.9",
            "at": 1596481983,
            "created_at": 1596481983,
            "updated_at": 1596553643,
            "trades_count": 272
        }
        """
        exchange_order_id = str(order_msg["id"])

        tracked_orders = list(self._in_flight_orders.values())
        track_order = [o for o in tracked_orders if exchange_order_id == o.exchange_order_id]
        if not track_order:
            return
        tracked_order = track_order[0]
        # Estimate fee
        order_msg["trade_fee"] = self.estimate_fee_pct(tracked_order.order_type is OrderType.LIMIT_MAKER)
        try:
            updated = tracked_order.update_with_order_update(order_msg)
        except Exception as e:
            self.logger().error(
                f"Error in order update for {tracked_order.exchange_order_id}. Message: {order_msg}\n{e}")
            traceback.print_exc()
            raise e
        if updated:
            safe_ensure_future(self._trigger_order_fill(tracked_order, order_msg))
        if tracked_order.is_cancelled:
            self.logger().info(f"Successfully canceled order {tracked_order.client_order_id}.")
            self.stop_tracking_order(tracked_order.client_order_id)
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(self.current_timestamp, tracked_order.client_order_id))
            tracked_order.cancelled_event.set()
        elif tracked_order.is_failure:
            self.logger().info(
                f"The market order {tracked_order.client_order_id} has failed according to order status API. ")
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp, tracked_order.client_order_id, tracked_order.order_type))
            tracked_order.last_state = "fail"
            self.stop_tracking_order(tracked_order.client_order_id)

    async def _process_trade_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        """
        exchange_order_id = str(trade_msg["order_id"])

        tracked_orders = list(self._in_flight_orders.values())
        for order in tracked_orders:
            if order.exchange_order_id is None:
                try:
                    async with timeout(6):
                        await order.get_exchange_order_id()
                except Exception:
                    pass
        track_order = [o for o in tracked_orders if exchange_order_id == o.exchange_order_id]

        if not track_order:
            return
        tracked_order = track_order[0]

        # Estimate fee
        trade_msg["trade_fee"] = self.estimate_fee_pct(tracked_order.order_type is OrderType.LIMIT_MAKER)
        updated = tracked_order.update_with_trade_update(trade_msg)

        if not updated:
            return

        await self._trigger_order_fill(tracked_order, trade_msg)

    def _process_balance_message(self, balance_message: Dict[str, Any]):
        asset_name = balance_message["currency"].upper()
        self._account_available_balances[asset_name] = Decimal(str(balance_message["balance"]))
        self._account_balances[asset_name] = Decimal(str(balance_message["locked"])) + Decimal(
            str(balance_message["balance"]))

    async def _trigger_order_fill(self,
                                  tracked_order: mSamexInFlightOrder,
                                  update_msg: Dict[str, Any]):
        executed_price = Decimal(str(update_msg.get("price")
                                     if update_msg.get("price") is not None
                                     else update_msg.get("avg_price", "0")))
        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                executed_price,
                tracked_order.executed_amount_base,
                AddedToCostTradeFee(percent=update_msg["trade_fee"]),
                update_msg.get("exchange_trade_id", update_msg.get("id", update_msg.get("order_id")))
            )
        )
        if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or \
                tracked_order.executed_amount_base >= tracked_order.amount or \
                (not tracked_order.is_cancelled and tracked_order.is_done):
            tracked_order.last_state = "done"
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
                                           tracked_order.executed_amount_base,
                                           tracked_order.executed_amount_quote,
                                           tracked_order.order_type))
            self.stop_tracking_order(tracked_order.client_order_id)

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        cancel_all_failed = False
        if self._trading_pairs is None:
            raise Exception("cancel_all can only be used when trading_pairs are specified.")
        open_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        if len(open_orders) == 0:
            return []
        tasks = [self._execute_cancel(o.trading_pair, o.client_order_id) for o in open_orders]
        cancellation_results = []
        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=False)
        except Exception:
            cancel_all_failed = True
        for cancellation_result in cancellation_results:
            if not cancellation_result.success:
                cancel_all_failed = True
                break
        if cancel_all_failed:
            self.logger().network(
                "Failed to cancel all orders, unexpected error.", exc_info=True,
                app_warning_msg=(f"Failed to cancel all orders on {Constants.EXCHANGE_NAME}. "
                                 "Check API key and network connection.")
            )
        return cancellation_results

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (Constants.SHORT_POLL_INTERVAL
                         if (not self._user_stream_tracker.is_connected
                             or now - self._user_stream_tracker.last_recv_time > Constants.USER_TRACKER_MAX_AGE)
                         else Constants.LONG_POLL_INTERVAL)
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
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.", exc_info=True,
                    app_warning_msg=(f"Could not fetch user events from {Constants.EXCHANGE_NAME}. "
                                     "Check API key and network connection."))
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        mSamexAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_methods = [
                    Constants.WS_METHODS["USER_BALANCES"],
                    Constants.WS_METHODS["USER_ORDERS"],
                    Constants.WS_METHODS["USER_TRADES"],
                ]

                for method in list(event_message.keys()):
                    params: dict = event_message.get(method, None)

                    if params is None or method not in event_methods:
                        continue
                    if method == Constants.WS_METHODS["USER_TRADES"]:
                        await self._process_trade_message(params)
                    elif method == Constants.WS_METHODS["USER_ORDERS"]:
                        self._process_order_message(params)
                    elif method == Constants.WS_METHODS["USER_BALANCES"]:
                        self._process_balance_message(params)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def get_open_orders(self) -> List[OpenOrder]:
        result = await self._api_request("GET",
                                         Constants.ENDPOINT["USER_ORDERS"],
                                         is_auth_required=True,
                                         limit_id=Constants.RL_ID_USER_ORDERS)
        ret_val = []
        for order in result:
            if order["state"] in Constants.ORDER_STATES['DONE']:
                # Skip done orders
                continue
            exchange_order_id = str(order["id"])
            client_order_id = order["client_id"]
            if order["ord_type"] != OrderType.LIMIT.name.lower():
                self.logger().info(f"Unsupported order type found: {order['type']}")
                # Skip and report non-limit orders
                continue
            ret_val.append(
                OpenOrder(
                    client_order_id=client_order_id,
                    trading_pair=convert_from_exchange_trading_pair(order["market"]),
                    price=Decimal(str(order["price"])),
                    amount=Decimal(str(order["origin_volume"])),
                    executed_amount=Decimal(str(order["executed_volume"])),
                    status=order["state"],
                    order_type=OrderType.LIMIT,
                    is_buy=True if order["side"].lower() == TradeType.BUY.name.lower() else False,
                    time=str_date_to_ts(order["created_at"]),
                    exchange_order_id=exchange_order_id
                )
            )
        return ret_val

    async def all_trading_pairs(self) -> List[str]:
        # This method should be removed and instead we should implement _initialize_trading_pair_symbol_map
        return await mSamexAPIOrderBookDataSource.fetch_trading_pairs()

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        # This method should be removed and instead we should implement _get_last_traded_price
        return await mSamexAPIOrderBookDataSource.get_last_traded_prices(
            trading_pairs=trading_pairs,
            throttler=self._throttler
        )
