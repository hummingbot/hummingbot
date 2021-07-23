import aiohttp
import asyncio
import logging
import time
import ujson

from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Optional,
    AsyncIterable,
    Union,
)

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.connector.exchange.ndax.ndax_message_payload import NdaxMessagePayload, NdaxAccountPositionEventPayload
from hummingbot.connector.exchange.ndax.ndax_user_stream_tracker import NdaxUserStreamTracker
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.connector.exchange_base import ExchangeBase

from hummingbot.core.event.events import (
    OrderType,
)
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

s_decimal_NaN = Decimal("nan")


class NdaxExchange(ExchangeBase):
    """
    Class to onnect with NDAX exchange. Provides order book pricing, user account tracking and
    trading functionality.
    """
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 uid: str,
                 api_key: str,
                 secret_key: str,
                 username: str,
                 account_id: int = None,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param uid: User ID of the account
        :param api_key: The API key to connect to private NDAX APIs.
        :param secret_key: The API secret.
        :param username: The username of the account in use.
        :param account_id: The account ID associated with the trading account in use.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._auth = NdaxAuth(uid=uid, api_key=api_key, secret_key=secret_key, username=username)
        # self._order_book_tracker = ProbitOrderBookTracker(trading_pairs=trading_pairs, domain=domain)
        self._user_stream_tracker = NdaxUserStreamTracker(self._auth)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        # self._in_flight_orders = {}  # Dict[client_order_id:str, ProbitInFlightOrder]
        # self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        # self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._last_poll_timestamp = 0

        self._status_polling_task = None
        # self._user_stream_tracker_task = None
        # self._user_stream_event_listener_task = None
        # self._trading_rules_polling_task = None

        self._account_id = account_id

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def account_id(self) -> int:
        return self._account_id

    def supported_order_types(self) -> List[OrderType]:
        """
        :return: a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _get_account_id(self) -> int:
        """
        Calls REST API to retrieve Account ID
        """
        params = {
            "OMSId": 0,
            "UserId": int(self._auth.uid),
            "UserName": self._auth.username
        }

        resp: List[int] = await self._api_request(
            "GET",
            path_url=CONSTANTS.USER_ACCOUNTS_PATH_URL,
            params=params,
            is_auth_required=True,
        )

        """
        NOTE: Currently there is no way to determine which accountId the user intends to use.
              The GetUserAccountInfos endpoint doesnt seem to provide anything useful either.
              The assumption here is that the FIRST entry in the list is the accountId the user intends to use
        """
        return resp[0]

    async def start_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        It starts tracking order book, polling trading rules,
        updating statuses and tracking user data.
        """
        # self._order_book_tracker.start()
        # self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            if not self._account_id:
                self._account_id = await self._get_account_id()
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            # self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            # self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False) -> Union[Dict[str, Any], List[Any]]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: The query parameters of the API request
        :param params: The body parameters of the API request
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        url = CONSTANTS.REST_URL + path_url
        client = await self._http_client()

        try:
            if is_auth_required:
                headers = self._auth.get_auth_headers()
            else:
                headers = self._auth.get_headers()

            if method == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = await client.post(url, headers=headers, data=ujson.dumps(data))
            else:
                raise NotImplementedError(f"{method} HTTP Method not implemented. ")

            parsed_response = await response.json()
        except ValueError as e:
            self.logger().error(f"{str(e)}")
            raise ValueError(f"Error authenticating request {method} {url}. Error: {str(e)}")
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response} "
                          f"Params: {params} "
                          f"Data: {data}")

        return parsed_response

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        params = {
            "OMSId": 1,
            "AccountId": self.account_id
        }
        account_positions: List[Dict[str, Any]] = await self._api_request(
            method="GET",
            path_url=CONSTANTS.ACCOUNT_POSITION_PATH_URL,
            params=params,
            is_auth_required=True
        )
        for position in account_positions:
            asset_name = position["ProductSymbol"]
            self._account_balances[asset_name] = Decimal(str(position["Amount"]))
            self._account_available_balances[asset_name] = self._account_balances[asset_name] - Decimal(str(position["Hold"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_order_status(self):
        # Waiting on buy and sell functionality.
        pass

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
                                      app_warning_msg="Could not fetch account updates from NDAX. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock tick(1 second by default).
        It checks if a status polling task is due for execution.
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
                    app_warning_msg="Could not fetch user events from NDAX. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_payload = NdaxMessagePayload.new_instance(
                    endpoint=NdaxWebSocketAdaptor.endpoint_from_message(event_message),
                    payload=NdaxWebSocketAdaptor.payload_from_message(event_message))
                event_payload.process_event(connector=self)
                # if "channel" not in event_message and event_message["channel"] not in CONSTANTS.WS_PRIVATE_CHANNELS:
                #     continue
                # channel = event_message["channel"]
                #
                # if channel == "balance":
                #     for asset, balance_details in event_message["data"].items():
                #         self._account_balances[asset] = Decimal(str(balance_details["total"]))
                #         self._account_available_balances[asset] = Decimal(str(balance_details["available"]))
                # elif channel in ["open_order"]:
                #     for order_update in event_message["data"]:
                #         self._process_order_message(order_update)
                # elif channel == "trade_history":
                #     for trade_update in event_message["data"]:
                #         self._process_trade_message(trade_update)

            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unexpected error in user stream listener loop ({ex})", exc_info=True)
                await asyncio.sleep(5.0)

    def process_account_position_event(self, account_position_event: NdaxAccountPositionEventPayload):
        self._account_balances[account_position_event.product_symbol] = account_position_event.amount
        self._account_available_balances[account_position_event.product_symbol] = (account_position_event.amount -
                                                                                   account_position_event.on_hold)
