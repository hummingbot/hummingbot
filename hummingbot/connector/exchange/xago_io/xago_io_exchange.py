import asyncio
import collections.abc
from enum import Enum, auto
import json
import logging
import math
import random
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

import aiohttp
from bidict import bidict
from dateutil import parser

from hummingbot.connector.exchange.xago_io import (
    xago_io_constants as CONSTANTS,
    xago_io_utils,
    xago_io_web_utils as web_utils,
)
from hummingbot.connector.exchange.xago_io.xago_io_api_order_book_data_source import XagoIoAPIOrderBookDataSource
from hummingbot.connector.exchange.xago_io.xago_io_api_user_stream_data_source import XagoIoAPIUserStreamDataSource
from hummingbot.connector.exchange.xago_io.xago_io_auth import XagoIoAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OpenOrder, OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

ctce_logger = None
s_decimal_NaN = Decimal("nan")

class LogLevel(Enum):
    INFO = auto()
    DEBUG = auto()

class XagoIoExchange(ExchangePyBase):
    """
    XagoIoExchange connects with xago.io exchange and provides order book pricing, user account tracking and
    trading functionality.
    """
    web_utils = web_utils

    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 5.0
    REFRESH_ACCESS_TOKEN = 60.0 * 60.0  # every hour
    LONG_POLL_INTERVAL = 5.0
    DEBUG_HIDDEN_URLS = [xago_io_utils.get_rest_url(CONSTANTS.IDENTITY_REST_URL, CONSTANTS.GET_ACCOUNT_TOKEN),
                         xago_io_utils.get_rest_url(CONSTANTS.EXCHANGE_REST_URL, CONSTANTS.GET_ACCOUNT_SUMMARY_PATH_URL),
                         ]

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 xago_io_api_key: str,
                 xago_io_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DOMAIN,
                 ):
        """
        :param xago_io_api_key: The API key to connect to private xago.io APIs.
        :param xago_io_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self._client_config_map = client_config_map
        self.api_key = xago_io_api_key
        self.secret_key = xago_io_secret_key
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._shared_client = aiohttp.ClientSession()
        self._auth = None
        self._last_poll_timestamp = 0
        self._log_level = LogLevel.INFO
        self.set_log_level()
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return "xago_io"
    
    @property
    def authenticator(self) -> AuthBase:
        if self._auth is None:
            self._auth = XagoIoAuth(
                api_key=self.api_key,
                secret_key=self.secret_key)
        return self._auth

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return CONSTANTS.DOMAIN

    @property
    def client_order_id_max_length(self) -> int:
        return 40

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.GET_TRADING_RULES_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.GET_TRADING_RULES_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.GET_TRADING_RULES_PATH_URL

    @property
    def trading_pairs(self):
        return list(self._trading_pairs)

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
        throttler=self._throttler,
        time_synchronizer=self._time_synchronizer,
        domain=self._domain,
        auth=self._auth)

    async def _place_order(self, 
                        order_id: str, 
                        trading_pair: str, 
                        amount: Decimal, 
                        trade_type: TradeType,
                        order_type: OrderType, 
                        price: Decimal,
                        **kwargs) -> Tuple[str, float]:
       
        if order_type == order_type.LIMIT_MAKER:
            order_type = order_type.LIMIT
        trading_rule = self._trading_rules[trading_pair]
        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        if amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")
        exchange_order_type = "Instant" if order_type == order_type.MARKET else order_type.name

        api_params = {
            "currencyPair": xago_io_utils.convert_to_exchange_trading_pair(trading_pair),
            "direction": trade_type.name,
            "type": exchange_order_type,
            "price": float(price),
            "amount": xago_io_utils.get_execute_amount(amount, price, trade_type.name),
        }

        try:
            url = CONSTANTS.EXCHANGE_REST_URL + CONSTANTS.CREATE_ORDER_PATH_URL
            order_result = await self._api_request(
                path_url="",
                overwrite_url=url,
                method=RESTMethod.POST,
                params=api_params,
                is_auth_required=True
            )
            exchange_order_id = str(order_result)
            self.logger().info(f"Order placed: {exchange_order_id} ({order_id})")
            return exchange_order_id, time.time()
        except Exception as e:
            self.logger().error(f"Error placing order: {e}")
            raise

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # Implement this method to get all trade updates for an order
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = order.exchange_order_id
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            url = CONSTANTS.EXCHANGE_REST_URL + CONSTANTS.GET_ORDER_FILLS_PATH_URL + "?orderId=" + exchange_order_id
            exchange_order = await self._api_request(
                path_url="",
                overwrite_url=url,
                method=RESTMethod.GET,
                is_auth_required=True)

            for trade in exchange_order["fills"]:
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["currencyCode"],
                    flat_fees=[TokenAmount(amount=Decimal(str(trade["fee"])), token=trade["currencyCode"])]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(str(trade["amount"])),
                    fill_quote_amount=Decimal(str(trade["total"])),
                    fill_price=Decimal(str(trade["price"])),
                    fill_timestamp=trade["timestamp"],
                )
                trade_updates.append(trade_update)

        return trade_updates
        

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        order_id = await tracked_order.get_exchange_order_id()
        try:
            url = CONSTANTS.EXCHANGE_REST_URL + CONSTANTS.GET_ORDER_DETAIL_PATH_URL + order_id
            updated_order_data = await self._api_get(
                path_url="",
                overwrite_url=url,
                method=RESTMethod.GET,
                is_auth_required=True
                )

            new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=xago_io_utils.get_ms_timestamp(),
                new_state=new_state,
            )

            return order_update
        except Exception as e:
            self.logger().info(
                f"Failed to fetch order status {e}")

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                 amount: Decimal, price: Decimal, is_maker: bool = True) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))
       
    async def _update_trading_fees(self):
        # Implement this method to update trading fees
        pass

    def _create_order_book_data_source(self):
        return XagoIoAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            auth=self._auth,
            shared_client=self._shared_client)

    def _create_user_stream_data_source(self):
        return XagoIoAPIUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # Implement this method to check if an exception is related to time synchronizer
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(
            cancelation_exception
        ) and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def set_log_level(self):
        client_config = getattr(self, "_client_config_map")
        hb_config = getattr(client_config, "hb_config")
        log_level = getattr(hb_config, "log_level")
        self._log_level = LogLevel.INFO if log_level == LogLevel.INFO.name else LogLevel.DEBUG
        self.logger().info(f"log_level set: {self._log_level}")

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

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

    async def check_network(self) -> NetworkStatus:
        """
        This function is required by NetworkIterator base class and is called periodically to check
        the network connection. Simply ping the network (or call any light weight public API).
        """
        try:
            # since there is no ping endpoint, the lowest rate call is to fetch the currencypairs
            await self.all_trading_pairs()
        except asyncio.CancelledError:
            raise
        except Exception as e:
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
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Unexpected error while fetching trading rules. Error: {str(e)}",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from xago.io. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        """
        :sets The trading rules for each market
        :first we fetch the currency_pairs, then we build up the manually build up the rules for each currency
        :as the rules are not yet returned from the api.
        """
        # Get currency_pairs
        currency_pairs = await self.all_trading_pairs()
        instruments_info = {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "symbols": []
            }
        }
        symbols = []
        for pair in currency_pairs:
            currencies = xago_io_utils.get_base_quote_currencies(pair)
            symbol = {
                "symbol": pair,
                "base_currency": currencies["base"],
                "quote_currency": currencies["quote"],
                "quote_increment": "5.000000",
                "base_min_size": "1.000000",
                "base_max_size": "100000.000000",
                "price_min_precision": 6,
                "price_max_precision": 6,
                "expiration": "NA",
                "min_buy_amount": "1.000000",
                "min_sell_amount": "1.000000"
            }
            symbols.append(symbol)

        instruments_info["data"]["symbols"] = symbols
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(instruments_info)

    def _format_trading_rules(self, instruments_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param instruments_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        {
            "id": 11,
            "method": "public/get-instruments",
            "code": 0,
            "result": {
                "instruments": [
                      {
                        "instrument_name": "ETH_CRO",
                        "quote_currency": "CRO",
                        "base_currency": "ETH",
                        "price_decimals": 2,
                        "quantity_decimals": 2
                      },
                      {
                        "instrument_name": "CRO_BTC",
                        "quote_currency": "BTC",
                        "base_currency": "CRO",
                        "price_decimals": 8,
                        "quantity_decimals": 2
                      }
                    ]
              }
        }
        """
        result = {}
        for rule in instruments_info["data"]["symbols"]:
            try:
                trading_pair = xago_io_utils.convert_from_exchange_trading_pair(rule["symbol"])
                price_decimals = Decimal(str(rule["price_max_precision"]))
                # E.g. a price decimal of 2 means 0.01 incremental.
                price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
                result[trading_pair] = TradingRule(trading_pair=trading_pair,
                                                   min_order_size=Decimal(str(rule["base_min_size"])),
                                                   max_order_size=Decimal(str(rule["base_max_size"])),
                                                   min_order_value=Decimal(str(rule["min_buy_amount"])),
                                                   min_base_amount_increment=Decimal(str(rule["quote_increment"])),
                                                   min_price_increment=price_step)
            except Exception as e:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _api_request(self,
                           path_url: str,
                           overwrite_url: Optional[str] = None,
                           method: RESTMethod = RESTMethod.GET,
                           params: Dict[str, Any] = {},
                           is_auth_required: bool = False) -> Dict[str, Any]:
        """
        Sends an aiohttp request to the Exchange endpoint and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url
        :param overwrite_url: The endpoint and path url
        :param use_access_token_auth: When True the function will add the current
        :ACCESS_TOKEN to the Authorization header as a Bearer token.
        :returns A response in json format.
        """
        # async with self._throttler.execute_task(url):
        client = await self._http_client()
        if not is_auth_required:
            auth_dict = self._auth.generate_auth_dict()
            params.update(auth_dict)
        
        url = overwrite_url or await self._api_request_url(path_url=path_url, is_auth_required=is_auth_required)

        headers = self._auth.get_headers(is_auth_required)
        try:
            response = await client.get(url, data=json.dumps(params), headers=headers) if method == RESTMethod.GET \
                else await client.post(url, data=json.dumps(params), headers=headers)
        
            if response.status != 200:
                raise Exception({"status": response.status, "reason": response.reason})

            resp_json = await response.json()

            if self._log_level == LogLevel.DEBUG:
                self.logger_debug(response, resp_json, url, params)

            return resp_json
        except Exception as e:
            resp_json = await response.json()
            if isinstance(e, str):
                self.logger().info(f"({rand}) REQUEST {response.real_url}")
                self.logger().info(f"({rand}) RESPONSE ({response.status}) {response.reason} {response.reason}")
                raise IOError(f"Error fetching data from {url}. Error: {str(e)}. Response status: {response.status} Response reason: {response.reason}")
            else:
                (error_dict,) = e.args
                rand = random.randint(10000, 99999)
                if isinstance(error_dict, collections.abc.Mapping):
                    self.logger().info(f"({rand}) REQUEST {response.real_url} {params}")
                    self.logger().info(f"({rand}) RESPONSE ({response.status}) {response.reason} {resp_json if self.debug_show_data(url) else '***HIDDEN' }")
                    raise IOError(f"Error fetching data from {url}. Error: {json.dumps(error_dict)} {response.status} {response.reason} ")

    def logger_debug(self, response, resp_json, url, params):
        """
        Log the data as info to console / logs.
        """
        if url == "https://exchange-api.xago.io/v1/prices/current":
            return
        rand = random.randint(10000, 99999)
        self.logger().info(f"({rand}) REQUEST {response.real_url} {params}")
        self.logger().info(f"({rand}) RESPONSE ({response.status}) {response.reason} {resp_json if self.debug_show_data(url) else '***HIDDEN' }")

    def debug_show_data(self, url):
        """
        Returns if the data should be shown or not.
        """

        return False if url in self.DEBUG_HIDDEN_URLS else True

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()
        if exchange_order_id is None:
            self.logger().error(f"While cancelling order {order_id}, exchange order id not found in order tracker. Removing")
            return True

        url = CONSTANTS.EXCHANGE_REST_URL + CONSTANTS.CANCEL_ORDER_PATH_URL + exchange_order_id
        cancel_result = await self._api_request(
                path_url="",
                overwrite_url=url,
                method=RESTMethod.POST,
                params={},
                is_auth_required=True
            )
        if cancel_result == exchange_order_id:
            self.logger().info(f"Order cancelled: {exchange_order_id} ({tracked_order.client_order_id})")
            return True

        self.logger().error(f"Error cancelling order {exchange_order_id} ({tracked_order.client_order_id}): {cancel_result}")
        return False

    async def _status_polling_loop(self):
        """
        Performs all required operation to keep the connector updated and synchronized with the exchange.
        It contains the backup logic to update status using API requests in case the main update source
        (the user stream data source websocket) fails.
        It also updates the time synchronizer. This is necessary because the exchange requires
        the time of the client to be the same as the time in the exchange.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await self._status_polling_loop_fetch_updates()
                await self._refresh_token(),
                self._last_poll_timestamp = self.current_timestamp
                self._poll_notifier = asyncio.Event()
            except asyncio.CancelledError:
                raise
            except NotImplementedError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch account updates from {self.name_cap}. "
                                    "Check API key and network connection.")
                await self._sleep(0.5)

    async def _refresh_token(self):
        """
        Calls IDENTITY REST API to refresh the ACCESS_TOKEN.
        """
        last_tick = int(self._last_poll_timestamp / self.REFRESH_ACCESS_TOKEN)
        current_tick = int(time.time() / self.REFRESH_ACCESS_TOKEN)
        if current_tick > last_tick:
            url = xago_io_utils.get_rest_url(CONSTANTS.IDENTITY_REST_URL, CONSTANTS.GET_ACCOUNT_TOKEN)
            result = await self._api_request(
                path_url="",
                overwrite_url=url,
                method=RESTMethod.POST,
                params={},
                is_auth_required=False
            )
            CONSTANTS.ACCESS_TOKEN = result["tokenValue"]

    async def _update_balances(self):
        """
        Calls EXCHANGE REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        if CONSTANTS.ACCESS_TOKEN == '':
            await self._refresh_token()

        url = CONSTANTS.EXCHANGE_REST_URL + CONSTANTS.GET_ACCOUNT_SUMMARY_PATH_URL
        account_info = await self._api_request(
            path_url="",
            overwrite_url=url,
            method=RESTMethod.GET,
            params={},
            is_auth_required=True
        )

        for account in account_info["balances"]:
            asset_name = account["currencyCode"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["balance"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

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
        function are ignore except order_type. Use OrderType.LIMIT to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    
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
                    app_warning_msg="Could not fetch user events from XagoIo. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    
    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        XagoIoAPIUserStreamDataSource.
        """

        async for event_message in self._iter_user_event_queue():
            try:
                if "type" not in event_message or "data" not in event_message:
                    continue
                channel = event_message["type"]
                if channel == CONSTANTS.INFO_STREAM:
                    continue
                if channel == CONSTANTS.TRADE_STREAM:
                    data = event_message["data"]
                    tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(data["orderId"])
                    if tracked_order is not None:
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=data["fee"],
                            flat_fees=[TokenAmount(amount=Decimal(data["fee"]), token=data["feeCurrency"])]
                        )
                        trade_update = TradeUpdate(
                            trade_id=data["id"],
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=data["orderId"],
                            trading_pair=tracked_order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(str(data["amountBase"])),
                            fill_quote_amount=Decimal(str(data["amountQuote"])),
                            fill_price=Decimal(str(data["price"])),
                            fill_timestamp=data["timestamp"],
                        )
                        self._order_tracker.process_trade_update(trade_update)
                elif channel == CONSTANTS.ORDER_STREAM:
                    data = event_message['data']
                    exchange_order_id = data['orderId']
                    tracked_order = None
                    for order in self._order_tracker.all_updatable_orders.values():
                        if order.exchange_order_id == exchange_order_id:
                            tracked_order = order
                            break
                    if tracked_order is not None:
                        if CONSTANTS.ORDER_STATE[data["status"]] == OrderState.FAILED:
                            self.logger().error(f"Order status is Failed")
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=data["updatedAt"],
                            new_state=CONSTANTS.ORDER_STATE[data["status"]],
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=data["orderId"],
                        )
                        self._order_tracker.process_order_update(order_update=order_update)
                elif channel == CONSTANTS.BALANCE_STREAM:
                    balance = event_message["data"]["balance"]
                    asset_name = next(iter(balance))
                    self._account_balances[asset_name] = Decimal(str(balance[asset_name]["available"])) + Decimal(str(balance[asset_name]["locked"]))
                    self._account_available_balances[asset_name] = Decimal(str(balance[asset_name]["available"]))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def get_open_orders(self) -> List[OpenOrder]:
        currency_pair = xago_io_utils.convert_to_exchange_trading_pair(self._trading_pairs[0])
        url = CONSTANTS.EXCHANGE_REST_URL + CONSTANTS.GET_OPEN_ORDERS_PATH_URL + f"&currencyPair={currency_pair}"
        result = await self._api_request(
            path_url="",
            overwrite_url=url,
            method=RESTMethod.GET,
            params={},
            is_auth_required=True
        )

        ret_val = []
        for order in result["orders"]:
            order = xago_io_utils.format_exchange_order_type(order)
            if order["type"] != "limit":
                continue
            time_formatted = parser.parse(order["createdAt"])
            time = int(time_formatted.timestamp())
            ret_val.append(
                OpenOrder(
                    client_order_id='',
                    trading_pair=currency_pair,
                    price=Decimal(str(order["price"])),
                    amount=Decimal(str(order["amount"])),
                    executed_amount=Decimal(0.0),
                    status=order["status"],
                    order_type=OrderType.LIMIT,
                    is_buy=True if order["side"] == "bid" else False,
                    time=time,
                    exchange_order_id=order["id"]
                )
            )
        return ret_val

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        # This method should be removed and instead we should implement _get_last_traded_price
        return await XagoIoAPIOrderBookDataSource.get_last_traded_prices(
            trading_pairs=trading_pairs)

    # async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
    #     url = CONSTANTS.EXCHANGE_REST_URL + CONSTANTS.GET_TICKER_PATH_URL
    #     pairs_prices = await self._api_request(
    #         path_url="",
    #         overwrite_url=url,
    #         method=RESTMethod.GET,
    #         params={},
    #         is_auth_required=False
    #     )
    #     return pairs_prices

    # Original v1.10
    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        url = CONSTANTS.EXCHANGE_REST_URL + CONSTANTS.GET_FX_RATES
        pairs_prices = await self._api_request(
            path_url="",
            overwrite_url=url,
            method=RESTMethod.GET,
            params={},
            is_auth_required=False
        )
        return pairs_prices

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(xago_io_utils.is_exchange_information_valid, exchange_info["currencyPairs"]):
            mapping[symbol_data["pair"]] = xago_io_utils.convert_from_exchange_trading_pair(symbol_data["pair"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        
        url = f"{CONSTANTS.EXCHANGE_REST_URL}/prices/ticker" + "?currencyPair=" + xago_io_utils.convert_to_exchange_trading_pair(trading_pair)
        
        resp = await self._api_request(
            method=RESTMethod.GET,
            overwrite_url=url
        )
        return resp['lastFillPrice']
