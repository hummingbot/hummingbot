import asyncio
import logging

from decimal import Decimal
from typing import (
    Dict,
    List,
    Optional,
    AsyncIterable,
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
from hummingbot.logger import HummingbotLogger

s_decimal_NaN = Decimal("nan")


class NdaxExchange(ExchangeBase):
    """
    Class to onnect with NDAX exchange. Provides order book pricing, user account tracking and
    trading functionality.
    """

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
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param uid: User ID of the account
        :param api_key: The API key to connect to private NDAX APIs.
        :param secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._auth = NdaxAuth(uid=uid, api_key=api_key, secret_key=secret_key)
        # self._order_book_tracker = ProbitOrderBookTracker(trading_pairs=trading_pairs, domain=domain)
        self._user_stream_tracker = NdaxUserStreamTracker(self._auth)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        # self._in_flight_orders = {}  # Dict[client_order_id:str, ProbitInFlightOrder]
        # self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        # self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        # self._last_poll_timestamp = 0

        # self._status_polling_task = None
        # self._user_stream_tracker_task = None
        # self._user_stream_event_listener_task = None
        # self._trading_rules_polling_task = None

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    def supported_order_types(self) -> List[OrderType]:
        """
        :return: a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

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
