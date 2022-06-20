import aiohttp
import asyncio
from async_timeout import timeout
from decimal import Decimal
import ujson
import logging
import math
import pandas as pd
from typing import (
    Any,
    Dict,
    List,
    Optional,
    AsyncIterable,
)
from libc.stdint cimport int64_t
import copy

from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    TradeType,
    TradeFee,
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketTransactionFailureEvent,
    MarketOrderFailureEvent
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.connector.exchange.coinex.coinex_order_book_tracker import CoinexOrderBookTracker
from hummingbot.connector.exchange.coinex.coinex_user_stream_tracker import CoinexUserStreamTracker
from hummingbot.connector.exchange.coinex.coinex_api_order_book_data_source import CoinexAPIOrderBookDataSource
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.event.events import OrderType
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.connector.exchange.coinex.coinex_in_flight_order import CoinexInFlightOrder
from hummingbot.connector.exchange.coinex.coinex_in_flight_order cimport CoinexInFlightOrder
from hummingbot.connector.exchange.coinex import coinex_utils
from hummingbot.connector.exchange.coinex import coinex_constants as Constants
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

s_logger = None
s_decimal_0 = Decimal("0.0")
s_decimal_nan = Decimal("nan")

cdef class CoinexExchangeTransactionTracker(TransactionTracker):
    cdef:
        CoinexExchange _owner

    def __init__(self, owner: CoinexExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class CoinexExchange(ExchangeBase):
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    API_CALL_TIMEOUT = 10.0
    UPDATE_ORDERS_INTERVAL = 10.0
    UPDATE_FEE_PERCENTAGE_INTERVAL = 60.0
    MAKER_FEE_PERCENTAGE_DEFAULT = 0.005
    TAKER_FEE_PERCENTAGE_DEFAULT = 0.005

    COINEX_API_ENDPOINT = f"{Constants.REST_URL}"

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 coinex_api_key: str,
                 coinex_secret_key: str,
                 poll_interval: float = 5.0,    # interval which the class periodically pulls status from the rest API
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._trading_required = trading_required
        self._coinex_auth = CoinexAuth(coinex_api_key, coinex_secret_key)
        self._trading_pairs = trading_pairs
        self._order_book_tracker = CoinexOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = CoinexUserStreamTracker(coinex_auth=self._coinex_auth,
                                                            trading_pairs=trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._last_fee_percentage_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._tx_tracker = CoinexExchangeTransactionTracker(self)
        self._trading_rules = {}
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._shared_client = None
        self._maker_fee_percentage = Decimal(self.MAKER_FEE_PERCENTAGE_DEFAULT)
        self._taker_fee_percentage = Decimal(self.TAKER_FEE_PERCENTAGE_DEFAULT)
        self._real_time_balance_update = False

    @property
    def name(self) -> str:
        """
        *required
        :return: A lowercase name / id for the market. Must stay consistent with market name in global settings.
        """
        return "coinex"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        """
        *required
        Get mapping of all the order books that are being tracked.
        :return: Dict[trading_pair : OrderBook]
        """
        self.logger().info(f"{self._order_book_tracker.order_books}")
        return self._order_book_tracker.order_books

    @property
    def coinex_auth(self) -> CoinexAuth:
        """
        :return: CoinexAuth class (This is unique to coinex pro market).
        Read more here: https://github.com/coinexcom/coinex_exchange_api/wiki/012security_authorization#generate-string-to-sign
        """
        return self._coinex_auth

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        *required
        :return: a dictionary of relevant status checks.
        This is used by `ready` method below to determine if a market is ready for trading.
        """
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True
        }

    @property
    def ready(self) -> bool:
        """
        *required
        :return: a boolean value that indicates if the market is ready for trading
        """
        return all(self.status_dict.values())

    @property
    def limit_orders(self) -> List[LimitOrder]:
        """
        *required
        :return: list of active limit orders
        """
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        *required
        :return: Dict[client_order_id: InFlightOrder]
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    @property
    def in_flight_orders(self) -> Dict[str, CoinexInFlightOrder]:
        return self._in_flight_orders

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        *required
        Updates inflight order statuses from API results
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        self._in_flight_orders.update({
            key: CoinexInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        """
        *required
        Used by the discovery strategy to read order books of all actively trading markets,
        and find opportunities to profit
        """
        return await CoinexAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        """
        *required
        c_start function used by top level Clock to orchestrate components of the bot
        """
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    async def start_network(self):
        """
        *required
        Async function used by NetworkBase class to handle when a single market goes online
        """
        self._stop_network()
        self._order_book_tracker.start()
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    def _stop_network(self):
        """
        Synchronous function that handles when a single market goes offline
        """
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = None

    async def stop_network(self):
        """
        *required
        Async wrapper for `self._stop_network`. Used by NetworkBase class to handle when a single market goes offline.
        """
        self._stop_network()

    # TODO: FIX ME
    async def check_network(self) -> NetworkStatus:
        """
        *required
        Async function used by NetworkBase class to check if the market is online / offline.
        I think we can use https://github.com/coinexcom/coinex_exchange_api/wiki/023deals in place...
        """
        # try:
        #     await self._api_request("get", path_url="/time")
        # except asyncio.CancelledError:
        #     raise
        # except Exception:
        #     return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        """
        *required
        Used by top level Clock to orchestrate components of the bot.
        This function is called frequently with every clock tick
        """
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)

        ExchangeBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns: Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           http_method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False) -> Dict[str, Any]:
        """
        A wrapper for submitting API requests to CoinEx
        :returns: json data from the endpoints
        """
        url = path_url
        client = await self._http_client()
        try:
            _headers = {
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36",
            }
            if is_auth_required:
                _auth_dict = self.coinex_auth.generate_auth_dict(params)
                _headers["Authorization"] = _auth_dict["signature"]
                _params = _auth_dict["params"]
            else:
                _params = params
            post_json = ujson.dumps(_params)
            if http_method == "post":
                response = await client.post(url=url, timeout=self.API_CALL_TIMEOUT, data=post_json, headers=_headers)
            elif http_method == "get":
                response = await client.get(url=url, timeout=self.API_CALL_TIMEOUT, params=_params, headers=_headers)
            elif http_method == "delete":
                response = await client.delete(url=url, timeout=self.API_CALL_TIMEOUT, params=_params, headers=_headers)
            else:
                raise NotImplementedError(f"{http_method} HTTP Method not implemented. ")

            parsed_response = await response.json()
        except ValueError as e:
            self.logger().error(f"{str(e)}")
            raise ValueError(f"Error authenticating request {http_method} {path_url}. Error: {str(e)}")
        except Exception as e:
            raise IOError(f"Error parsing data from {path_url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {path_url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response} "
                          f"Params: {_params} ")

        return parsed_response

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        """
        *required
        function to calculate fees for a particular order
        :returns: TradeFee class that includes fee percentage and flat fees
        TODO: FIX ME this can work instead of the update fee %
        See: https://github.com/coinexcom/coinex_exchange_api/wiki/026market_single_info
        """
        # There is no API for checking user's fee tier
        # Fee info from https://coinex.com/fees
        # TODO: Review me, there's only fees per market as defined in trading rules otherwise we use global config
        """
        cdef:
            object maker_fee = self._maker_fee_percentage
            object taker_fee = self._taker_fee_percentage
        if order_type is OrderType.LIMIT and fee_overrides_config_map["coinex_maker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["coinex_maker_fee"].value / Decimal("100"))
        if order_type is OrderType.MARKET and fee_overrides_config_map["coinex_taker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["coinex_taker_fee"].value / Decimal("100"))
        return TradeFee(percent=maker_fee if order_type is OrderType.LIMIT else taker_fee)
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("coinex", is_maker)

    async def _update_fee_percentage(self):
        """
        Pulls the API for updated balances
        TODO: FIX ME this is returned per pair
        See: https://github.com/coinexcom/coinex_exchange_api/wiki/025marketinfo
        """
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_fee_percentage_update_timestamp <= self.UPDATE_FEE_PERCENTAGE_INTERVAL:
            return

        path_url = "/fees"
        fee_info = await self._api_request("get", path_url=path_url)
        self._maker_fee_percentage = Decimal(fee_info["maker_fee_rate"])
        self._taker_fee_percentage = Decimal(fee_info["taker_fee_rate"])
        self._last_fee_percentage_update_timestamp = current_timestamp

    async def _update_balances(self):
        """
        Pulls the API for updated balances
        """
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        path_url = Constants.BALANCE_URL
        account_balances = await self._api_request("get", path_url=path_url, is_auth_required=True)
        account_balances = account_balances['data']
        for currency, balance_entry in account_balances.iteritems():
            asset_name = currency
            available_balance = Decimal(str(balance_entry["available"]))
            total_balance = Decimal(str(balance_entry["available"])) + Decimal(str(balance_entry["frozen"]))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]
        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self._current_timestamp

    async def _update_trading_rules(self):
        """
        Pulls the API for trading rules (min / max order size, etc)
        TODO: More modern versions of this use polling...
        See: https://github.com/CoinAlpha/hummingbot/blob/ec9ac5d0eeeb4b0523aa2c998bfaf8443af7a157/hummingbot/connector/exchange/probit/probit_exchange.py
        """
        cdef:
            # The poll interval for rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) <= 0:
            path_url = Constants.MARKETS_URL
            market_info = await self._api_request("get", path_url=path_url)
            market_info = market_info['data']
            self._trading_rules.clear()
            self._trading_rules = self._format_trading_rules(market_info)

    def _format_trading_rules(self, market_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Turns json data from API into TradingRule instances
        :param market_info: The json API response
        :return A dictionary of trading rules
        Response Example:
        {
            "code": 0,
            "data": {
                "KAVAUSDT": {
                    "name": "KAVAUSDT",
                    "min_amount": "0.5",
                    "maker_fee_rate": "0.002",
                    "taker_fee_rate": "0.002",
                    "pricing_name": "USDT",
                    "pricing_decimal": 4,
                    "trading_name": "KAVA",
                    "trading_decimal": 8
                }
            }
        }
        """
        cdef:
            dict result = {}
        for pair, rule in market_info.iteritems():
            try:
                trading_pair = coinex_utils.convert_from_exchange_trading_pair(rule["name"], rule["pricing_name"])
                # self.logger().info(f"{trading_pair}")
                price_decimals = Decimal(str(rule["pricing_decimal"]))
                quantity_decimals = Decimal(str(rule["trading_decimal"]))
                min_amount = Decimal(str(rule["min_amount"]))
                # E.g. a price decimal of 2 means 0.01 incremental.
                price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
                quantity_step = Decimal("1") / Decimal(str(math.pow(10, quantity_decimals)))
                result[trading_pair] = TradingRule(trading_pair,
                                          min_price_increment=price_step,
                                          min_order_size=min_amount,
                                          min_base_amount_increment=quantity_step
                                          )
            except Exception:
                self.logger().error(f"Error parsing the trading_pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _update_order_status(self, trading_pair: str):
        """
        Pulls the rest API for for latest order statuses and update local order statuses.
        """
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_order_update_timestamp <= self.UPDATE_ORDERS_INTERVAL:
            return

        tracked_orders = list(self._in_flight_orders.values())
        results = await self.list_orders(trading_pair)
        order_dict = None
        if len(results) > 0:
            self.logger().debug(f"We have located orders: {results}")
            order_dict = dict((str(result["id"]), result) for result in results)
            self.logger().debug(f"Created dict of ids to go through: {order_dict}")
            # TODO: Should this handle executed orders as well?

        for tracked_order in tracked_orders:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            exchange_order_id = str(exchange_order_id)
            client_order_id = tracked_order.client_order_id
            order_update = None
            if order_dict is not None:
                order_update = order_dict.get(exchange_order_id)
            if order_update is None:
                try:
                    # TODO: Does this handle completed orders?
                    # TODO: Should this be in the continue loop? It doesn't seem to do anything with it...
                    # TODO: should this be order_update set vs just order?
                    # TODO: This just seems like a doublecheck but nothing is done except error handling
                    order = await self.get_order(client_order_id, tracked_order.trading_pair)
                except IOError as e:
                    if "order not found" in str(e):
                        # The order does not exist. So we should not be tracking it.
                        self.logger().info(
                            f"The tracked order {client_order_id} does not exist on CoinEx."
                            f"Order removed from tracking."
                        )
                        self.c_stop_tracking_order(client_order_id)
                        self.c_trigger_event(
                            self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                            OrderCancelledEvent(self._current_timestamp, client_order_id)
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: ",
                        exc_info=True,
                        app_warning_msg=f"Could not fetch updates for the order {client_order_id}. "
                                        f"Check API key and network connection.{e}"
                    )
                continue

            status = order_update.get("status")
            # Calculate the newly executed amount for this update.
            # TODO: Review params from https://github.com/coinexcom/coinex_exchange_api/wiki/036finished
            # https://github.com/coinexcom/coinex_exchange_api/wiki/034pending
            new_confirmed_amount = Decimal(order_update["deal_amount"])
            execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
            execute_price = s_decimal_0 if new_confirmed_amount == s_decimal_0 \
                else Decimal(order_update["deal_money"]) / new_confirmed_amount

            order_type_description = tracked_order.order_type_description
            order_type = tracked_order.order_type
            # Emit event if executed amount is greater than 0.
            if execute_amount_diff > s_decimal_0:
                order_filled_event = OrderFilledEvent(
                    self._current_timestamp,
                    tracked_order.client_order_id,
                    tracked_order.trading_pair,
                    tracked_order.trade_type,
                    order_type,
                    execute_price,
                    execute_amount_diff,
                    self.c_get_fee(
                        tracked_order.base_asset,
                        tracked_order.quote_asset,
                        order_type,
                        tracked_order.trade_type,
                        execute_price,
                        execute_amount_diff,
                    ),
                    # CoinEx's websocket stream tags events with order_id rather than trade_id
                    # Using order_id here for easier data validation
                    exchange_trade_id=exchange_order_id,
                )
                self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                   f"{order_type_description} order {client_order_id}.")
                self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            # Update the tracked order
            tracked_order.last_state = status if status in {"done", "cancel"} else order_update["status"]
            tracked_order.executed_amount_base = new_confirmed_amount
            tracked_order.executed_amount_quote = Decimal(order_update["deal_money"])
            tracked_order.fee_paid = Decimal(order_update["deal_fee"])
            if tracked_order.is_done:
                if not tracked_order.is_failure:
                    if tracked_order.trade_type == TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    (tracked_order.fee_asset
                                                                     or tracked_order.base_asset),
                                                                    tracked_order.executed_amount_base,
                                                                    tracked_order.executed_amount_quote,
                                                                    tracked_order.fee_paid,
                                                                    order_type))
                    else:
                        self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_order.client_order_id,
                                                                     tracked_order.base_asset,
                                                                     tracked_order.quote_asset,
                                                                     (tracked_order.fee_asset
                                                                      or tracked_order.quote_asset),
                                                                     tracked_order.executed_amount_base,
                                                                     tracked_order.executed_amount_quote,
                                                                     tracked_order.fee_paid,
                                                                     order_type))
                else:
                    self.logger().info(f"The market order {tracked_order.client_order_id} has failed/been cancelled "
                                       f"according to order status API.")
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                         OrderCancelledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id
                                         ))
                self.c_stop_tracking_order(tracked_order.client_order_id)
        self._last_order_update_timestamp = current_timestamp

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        """
        Iterator for incoming messages from the user stream.
        """
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 1 seconds.", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Update order statuses from incoming messages from the user stream
        TODO: Review and cleanup
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_method = event_message.get("method")
                event_params = event_message.get("params", None)
                # Order update broadcast
                if event_method == "order.update":
                    tracked_order = None  # Setup for our comparison
                    content = event_params[1]  # Indexed response message
                    exchange_order_id = str(content["id"])  # CoinEx uses ints for their IDs

                    for order in self._in_flight_orders.values():
                        order_id = await order.get_exchange_order_id()
                        if order_id == exchange_order_id:
                            tracked_order = order
                            break

                    self.logger().info(f"In Flight: {self._in_flight_orders}")
                    if tracked_order is None:
                        self.logger().info(f"Unrecognized order ID from user stream: {exchange_order_id}.")
                        self.logger().info(f"Event: {event_message}")
                        continue

                    order_type_description = tracked_order.order_type_description

                     # TODO: We should enum these
                    event_type = int(event_params[0]) # 1: PUT, 2: UPDATE, 3: FINISH
                    execute_price = Decimal(content["price"] if content["price"] else 0.0)
                    execute_amount_diff = s_decimal_0

                    # Created order
                    # TODO: It seems like create and finish / cancel are to be included in the same function
                    if event_type == 1:  # PUT
                        self.logger().info(f"We've created an order: {content}")
                        remaining_size = Decimal(content.get("left", tracked_order.amount))
                        new_confirmed_amount = tracked_order.amount - remaining_size
                        execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                        tracked_order.executed_amount_base = new_confirmed_amount
                        tracked_order.executed_amount_quote += execute_amount_diff * execute_price
                        # TODO: We can use this here to check if the order is done.... Not sure it broadcasts finished orders...
                    # Update
                    elif event_type == 2:  # UPDATE
                        # TODO: Key options "left", "deal_money", "deal_amount"
                        self.logger().info(f"We've updated an order: {content}")
                        execute_amount_diff = Decimal(content.get("deal_amount", 0.0))
                        if execute_amount_diff > s_decimal_0:
                            tracked_order.executed_amount_base += execute_amount_diff
                            tracked_order.executed_amount_quote += execute_amount_diff * execute_price
                    elif event_type == 3:  # FINISH
                        # TODO: This seems like a delete too...
                        self.logger().info(f"Something weird, we'll handle it below: {content}")
                        pass
                    else:
                        self.logger().error(f"Invalid change message - '{event_message}'. Aborting.")

                    if execute_amount_diff > s_decimal_0:
                        self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                           f"{order_type_description} order {tracked_order.client_order_id}")
                        exchange_order_id = tracked_order.exchange_order_id
                        self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                         OrderFilledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id,
                                             tracked_order.trading_pair,
                                             tracked_order.trade_type,
                                             tracked_order.order_type,
                                             execute_price,
                                             execute_amount_diff,
                                             self.c_get_fee(
                                                 tracked_order.base_asset,
                                                 tracked_order.quote_asset,
                                                 tracked_order.order_type,
                                                 tracked_order.trade_type,
                                                 execute_price,
                                                 execute_amount_diff,
                                             ),
                                             exchange_trade_id=exchange_order_id
                                         ))
                    if event_type == 3:
                        # TODO: Not sure about this cat: Keys "last_deal_amount" ????
                        execute_amount_diff = s_decimal_0
                        if "deal_amount" in content:
                            self.logger().info(content["deal_amount"])
                            execute_amount_diff = Decimal(content["deal_amount"])
                        if execute_amount_diff == s_decimal_0:
                            self.logger().info(f"We've cancelled an order: {content}")
                            self.logger().info(f"The market order {tracked_order.client_order_id} has been "
                                               f"cancelled according to CoinEx user stream. MAYBE???")
                            tracked_order.last_state = "canceled"
                            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                                 OrderCancelledEvent(self._current_timestamp, tracked_order.client_order_id))
                            execute_amount_diff = 0
                            self.c_stop_tracking_order(tracked_order.client_order_id)
                        else:
                            self.logger().info(f"We've completed an order: {content}")
                            if tracked_order.trade_type == TradeType.BUY:
                                self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                                   f"according to CoinEx user stream.")
                                self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                     BuyOrderCompletedEvent(self._current_timestamp,
                                                                            tracked_order.client_order_id,
                                                                            tracked_order.base_asset,
                                                                            tracked_order.quote_asset,
                                                                            (tracked_order.fee_asset
                                                                             or tracked_order.base_asset),
                                                                            tracked_order.executed_amount_base,
                                                                            tracked_order.executed_amount_quote,
                                                                            tracked_order.fee_paid,
                                                                            tracked_order.order_type))
                            else:
                                self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                                   f"according to CoinEx user stream.")
                                self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                     SellOrderCompletedEvent(self._current_timestamp,
                                                                             tracked_order.client_order_id,
                                                                             tracked_order.base_asset,
                                                                             tracked_order.quote_asset,
                                                                             (tracked_order.fee_asset
                                                                              or tracked_order.quote_asset),
                                                                             tracked_order.executed_amount_base,
                                                                             tracked_order.executed_amount_quote,
                                                                             tracked_order.fee_paid,
                                                                             tracked_order.order_type))
                            self.c_stop_tracking_order(tracked_order.client_order_id)
                    # TODO: Do we need continues?
                # Asset (balance) update broadcast
                elif event_method == "asset.update":
                    self.logger().info(f"Asset: {event_params}")
                    content = event_params[0] # Indexed param result (array / list)
                    for key, value in content.items():
                        currency = key
                        available_balance = Decimal(value["available"])
                        total_balance = Decimal(value["available"]) + Decimal(value["frozen"])
                    self._account_balances.update({currency: total_balance})
                    self._account_available_balances.update({currency: available_balance})
                    continue  # TODO: Do we need continues?
                else:
                    self.logger().error(f"Invalid event message - '{event_message}'.")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    # TODO: Review supported order types on coinex
    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    # TODO: Review, add support for other order types
    async def place_order(self, order_id: str, trading_pair: str, amount: Decimal, is_buy: bool, order_type: OrderType,
                          price: Decimal):
        """
        Async wrapper for placing orders through the rest API.
        :returns: json response from the API
        TODO: Review, what if we want to place a market order?
        """
        path_url = Constants.NEW_LIMIT_ORDER_URL
        params = {
            "market": coinex_utils.convert_to_exchange_trading_pair(trading_pair),
            "amount": f"{amount:f}",
            "type": "buy" if is_buy else "sell",
        }
        # TODO: Reivew why this is like that?
        if order_type is OrderType.LIMIT:
            params["price"] = f"{price:f}"
        elif order_type is OrderType.LIMIT_MAKER:
            # path_url = "order/market"
            params["price"] = f"{price:f}"
            params["option"] = "MAKER_ONLY"
        order_result = await self._api_request("post", path_url=path_url, params=params, is_auth_required=True)
        if order_result["code"] != 0:
            # TODO: Do we handle error here and does it bubble up?
            self.logger().info(f"Error creating order: {order_result}")
            raise ValueError("Failed to create order: {order_result['message']}")
        order_result = order_result["data"]

        self.logger().debug(f"Order Details: {order_result}")
        return order_result

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_0):
        """
        Function that takes strategy inputs, auto corrects itself with trading rule,
        and submit an API request to place a buy order
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, None, trading_pair, order_type, TradeType.BUY, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type, decimal_price)

            exchange_order_id = str(order_result["id"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(self._current_timestamp,
                                                      order_type,
                                                      trading_pair,
                                                      decimal_amount,
                                                      decimal_price,
                                                      order_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting buy {order_type_str} order to CoinEx for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to CoinEx. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_0,
                   dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the buy order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = s_decimal_0):
        """
        Function that takes strategy inputs, auto corrects itself with trading rule,
        and submit an API request to place a sell order
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, None, trading_pair, order_type, TradeType.SELL, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type, decimal_price)

            exchange_order_id = str(order_result["id"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(self._current_timestamp,
                                                       order_type,
                                                       trading_pair,
                                                       decimal_amount,
                                                       decimal_price,
                                                       order_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to CoinEx for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit sell order to CoinEx. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.LIMIT,
                    object price=s_decimal_0,
                    dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the sell order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        """
        Function that makes API request to cancel an active order
        TODO: FIX ME - We need to add a market to each of these
        See: https://github.com/coinexcom/coinex_exchange_api/wiki/035cancel
        """
        try:
            exchange_order_id = await self._in_flight_orders.get(order_id).get_exchange_order_id()
            exchange_order_id = str(exchange_order_id)
            path_url = Constants.CANCEL_ORDER_URL
            params = {
                "id": int(exchange_order_id),
                "market": coinex_utils.convert_to_exchange_trading_pair(trading_pair),
            }
            cancelled_id = await self._api_request("delete", path_url=path_url, params=params, is_auth_required=True)
            self.logger().debug(f"{cancelled_id}")
            if len(cancelled_id['data']) > 0:
                cancelled_id = cancelled_id['data']
                if str(cancelled_id['id']) == exchange_order_id:
                    self.logger().info(f"Successfully cancelled order {order_id}.")
                    self.c_stop_tracking_order(order_id)
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                         OrderCancelledEvent(self._current_timestamp, order_id))
                    return order_id
            # TODO: Review and cleanup, this doesn't need to be everywhere...
            elif "order not found" in cancelled_id['message'].lower():
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on CoinEx. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except IOError as e:
            if "order not found" in str(e).lower():
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on CoinEx. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # TODO: REVIEW FIX
            if "order not found" in str(e).lower():
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on CoinEx. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id

            self.logger().network(
                f"Failed to cancel order {order_id}: ",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on CoinEx. "
                                f"Check API key and network connection.{e}"
            )
        return None

    cdef c_cancel(self, str trading_pair, str order_id):
        """
        *required
        Synchronous wrapper that schedules cancelling an order.
        """
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        *required
        Async function that cancels all active orders.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :returns: List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self.execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                results = await safe_gather(*tasks, return_exceptions=True)
                for client_order_id in results:
                    if type(client_order_id) is str:
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
                    else:
                        # TODO: Fix missing orders in here... Might fix already with completed orders.....
                        self.logger().warning(
                            f"failed to cancel order with error: "
                            f"{repr(client_order_id)}"
                        )
        except Exception as e:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order on CoinEx. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    async def _status_polling_loop(self):
        """
        Background process that periodically pulls for changes from the rest API
        """
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await safe_gather(
                    self._update_balances(),
                    *tuple(self._update_order_status(tp) for tp in self._trading_pairs),
                    # self._update_fee_percentage(),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch account updates on CoinEx. "
                                    f"Check API key and network connection."
                )

    async def _trading_rules_polling_loop(self):
        """
        Separate background process that periodically pulls for trading rule changes
        (Since trading rules don't get updated often, it is pulled less often.)
        """
        while True:
            try:
                await safe_gather(self._update_trading_rules())
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching trading rules.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch trading rule updates on CoinEx. "
                                    f"Check network connection."
                )
                await asyncio.sleep(0.5)

    # TODO: Review and double check how to handle order not found on coinex
    async def get_order(self, client_order_id: str, trading_pair: str, ) -> Dict[str, Any]:
        """
        Gets status update for a particular order via rest API
        :returns: json response
        See: https://github.com/coinexcom/coinex_exchange_api/wiki/037order_status
        """
        order = self._in_flight_orders.get(client_order_id)
        if order is None:
            return None
        exchange_order_id = await order.get_exchange_order_id()
        path_url = Constants.ORDER_URL
        params = {
            "id": int(exchange_order_id),
            "market": coinex_utils.convert_to_exchange_trading_pair(trading_pair),  # TODO: NEED TO ADD THIS FOR API SUPPORT
        }
        result = await self._api_request("get", path_url=path_url, params=params, is_auth_required=True)

        if (not result) or ("data" not in result) or (not result["data"]):
            raise IOError(f"Order not found for client_order_id: {client_order_id}")

        result = result["data"]
        return result

    async def list_orders(self, trading_pair: str) -> List[Any]:
        """
        Gets a list of the user's orders via rest API
        :returns: json response
        TODO: FIX ME, this can include paging.....??
        Also fix the trading_pair
        See: https://github.com/coinexcom/coinex_exchange_api/wiki/034pending
        https://github.com/coinexcom/coinex_exchange_api/wiki/036finished
        """
        incomplete_path_url = Constants.OPEN_ORDER_URL
        complete_path_url = Constants.ORDER_HISTORY_URL
        self.logger().debug(f"LIST ORDER MARKET: {coinex_utils.convert_to_exchange_trading_pair(trading_pair)}")
        params = {
            "page": int(1),
            "limit": int(100),
            "market": coinex_utils.convert_to_exchange_trading_pair(trading_pair)
        }
        incomplete_result = await self._api_request("get", path_url=incomplete_path_url, params=params, is_auth_required=True)
        # TODO: Do something with count / limit = number of paging times.... eg ceil(count/limit) = page we gotta get to.
        complete_result = await self._api_request("get", path_url=complete_path_url, params=params, is_auth_required=True)
        # TODO: Do something with count / limit = number of paging times.... eg ceil(count/limit) = page we gotta get to.
        # self.logger().info(f"{incomplete_result['data']['data']}")
        # TODO: Need to add https://github.com/coinexcom/coinex_exchange_api/wiki/036finished
        if len(incomplete_result['data']['data']) > 0:
            incomplete_result = incomplete_result['data']['data']
        else:
            incomplete_result = []

        if len(complete_result['data']['data']) > 0:
            complete_result = complete_result['data']['data']
        else:
            complete_result = []

        aggregate_result = complete_result + incomplete_result
        result = dict()

        for order in aggregate_result:
            if str(order["id"]) not in result:
                result[str(order["id"])] = order

        return list(result.values())

    cdef OrderBook c_get_order_book(self, str trading_pair):
        """
        :returns: OrderBook for a specific trading pair
        """
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    cdef c_start_tracking_order(self,
                                str order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        """
        Add new order to self._in_flight_orders mapping
        """
        self._in_flight_orders[order_id] = CoinexInFlightOrder(
            order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
        )

    cdef c_stop_tracking_order(self, str order_id):
        """
        Delete an order from self._in_flight_orders mapping
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef c_did_timeout_tx(self, str tracking_id):
        """
        Triggers MarketEvent.TransactionFailure when an Ethereum transaction has timed out
        """
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        """
        *required
        Get the minimum increment interval for price
        :return: Min order price increment in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        """
        *required
        Get the minimum increment interval for order size (e.g. 0.01 USD)
        :return: Min order size increment in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        # CoinEx is using the min_order_size as max_precision
        # Order size must be a multiple of the min_order_size
        return trading_rule.min_order_size

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        """
        *required
        Check current order amount against trading rule, and correct any rule violations
        :return: Valid order amount in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        global s_decimal_0
        quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)

        # Check against min_order_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing either check, return 0.
        if quantized_amount > trading_rule.max_order_size:
            return s_decimal_0

        return quantized_amount

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_nan, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_nan, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_nan) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
