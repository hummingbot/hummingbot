import asyncio
import functools
import logging
from collections import defaultdict
from decimal import Decimal
from enum import Enum
from typing import Any, AsyncGenerator, Awaitable, Callable, Coroutine, Dict, NamedTuple, Tuple

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger

from .coinbase_advanced_trade_web_utils import get_timestamp_from_exchange_time
from .connecting_functions.exception_log_manager import log_if_possible
from .pipe import SENTINEL
from .single_stream_data_source.single_stream_data_source import SingleStreamDataSource
from .stream_data_source.enums import StreamAction
from .stream_data_source.errors import CoinbaseAdvancedTradeWSSubscriptionError
from .stream_data_source.protocols import WSAssistantPtl, WSResponsePtl


class CoinbaseAdvancedTradeCumulativeUpdate(NamedTuple):
    client_order_id: str
    exchange_order_id: str
    status: str
    trading_pair: str
    fill_timestamp_s: float  # seconds
    average_price: Decimal
    cumulative_base_amount: Decimal
    remainder_base_amount: Decimal
    cumulative_fee: Decimal
    # Needed for tracking existing orders on the exchange
    order_type: OrderType
    trade_type: TradeType
    creation_timestamp_s: float = 0.0  # seconds
    # Coinbase Advanced Trade delivers trade events from the maker's perspective
    is_taker: bool = False


class WebsocketAction(Enum):
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


async def coinbase_advanced_trade_subscription_builder(
        *,
        action: StreamAction,
        channel: str,
        pairs: Tuple[str],
        pair_to_symbol: Callable[[str], Awaitable[str]]
) -> Dict[str, Any]:
    """
    Build the subscription message for Coinbase Advanced Trade API.
    :param action: The action to perform.
    :param channel: The channel to subscribe to.
    :param pairs: The trading pairs to subscribe to.
    :param pair_to_symbol: The function to convert trading pair to symbol.
    :return: The subscription message.
    """
    """
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-overview
    {
        "type": "subscribe",
        "product_ids": [
            "ETH-USD",
            "ETH-EUR"
        ],
        "channel": "level2",
        "api_key": "exampleApiKey123",
        "timestamp": 1660838876,
        "signature": "00000000000000000000000000",
    }
    """

    if action == StreamAction.SUBSCRIBE:
        _type = "subscribe"
    elif action == StreamAction.UNSUBSCRIBE:
        _type = "unsubscribe"
    else:
        raise ValueError(f"Invalid action: {action}")
    return {
        "type": _type,
        "product_ids": [await pair_to_symbol(pair) for pair in pairs],
        "channel": channel,
    }


def on_failed_subscription(
        response: WSResponsePtl,
        *,
        logger: HummingbotLogger | logging.Logger | None = None,
) -> WSResponsePtl:
    """
    Log the failed subscription message.
    :param response: The message received from the exchange.
    :param logger: The logger to use.
    """
    """
    {'type': 'subscriptions', 'channels': [{'name': 'heartbeat', 'product_ids': ['BTC-USD']}, {'name': 'user', 'product_ids': ['BTC-USD']}], 'message': 'Invalid product_ids: BTC-USD'}
    """
    if response.data:
        if response.data.get("type") != "error":
            return response
        else:
            raise CoinbaseAdvancedTradeWSSubscriptionError(f"Failed subscription: {response.data}")


# --- Websocket message parsers ---

def sequence_reader(
        message: Dict[str, Any],
        *,
        logger: HummingbotLogger | logging.Logger | None = None,
) -> int:
    """Extract the sequence number from the message."""
    """
    {'channel': 'subscriptions', 'client_id': '', 'timestamp': '2023-10-14T23:34:47.866340883Z', 'sequence_num': 0, 'events': [{'subscriptions': {'heartbeats': ['heartbeats']}}]}
    {'channel': 'user', 'client_id': '', 'timestamp': '2023-10-14T23:34:48.160207575Z', 'sequence_num': 1, 'events': [{'type': 'snapshot', 'orders': []}]}
    {'channel': 'subscriptions', 'client_id': '', 'timestamp': '2023-10-14T23:34:48.160220355Z', 'sequence_num': 2, 'events': [{'subscriptions': {'heartbeats': ['heartbeats'], 'user': ['df59559b-af66-5c60-9cbc-b497d26c6608']}}]}
    """
    # sequence_num = 0: subscriptions message for heartbeats
    # sequence_num = 1: user snapshot message
    # sequence_num = 2: subscriptions message for user
    if not isinstance(message, dict):
        log_if_possible(logger, "ERROR", f"Invalid message type: {type(message)} {message}")
        raise ValueError(f"Invalid message type: {type(message)} {message}")

    if logger:
        if message["channel"] == "user":
            logger.debug(f"Sequence handler {message['channel']}:{message['sequence_num']}:{message}")
        else:
            logger.debug(f"Sequence handler {message['channel']}:{message['sequence_num']}")
            logger.debug(f"{message}")

    return message["sequence_num"]


def timestamp_and_filter(
        event_message: Dict[str, Any],
        *,
        logger: HummingbotLogger | logging.Logger | None = None,
) -> Dict[str, Any]:
    """
    Reformat the timestamp to seconds.
    Filter out heartbeat and (subscriptions?) messages.
    :param event_message: The message received from the exchange.
    :param logger: The logger to use.
    """
    """
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#user-channel
    {
      "channel": "user",
      "client_id": "",
      "timestamp": "2023-02-09T20:33:57.609931463Z",
      "sequence_num": 0,
      "events": [...]
    }
    """
    if event_message["channel"] == "user":
        if isinstance(event_message["timestamp"], str):
            event_message["timestamp"] = get_timestamp_from_exchange_time(event_message["timestamp"], "s")
        return event_message

    elif event_message["channel"] in ["subscriptions", "heartbeats"]:
        logging.debug(f"Filtering message {event_message} {event_message['channel']} not user")


async def message_to_cumulative_update(
        event_message: Dict[str, Any],
        *,
        symbol_to_pair: Callable[[str], Coroutine[Any, Any, str]],
        logger: HummingbotLogger | logging.Logger | None = None,
) -> AsyncGenerator[CoinbaseAdvancedTradeCumulativeUpdate, None]:
    """
    Streamline the messages for processing by the exchange.
    :param event_message: The message received from the exchange.
    :param symbol_to_pair: The function to convert a symbol to a trading pair.
    :param logger: The logger to use.
    """
    """
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#user-channel
    {
      "channel": "user",
      "client_id": "",
      "timestamp": "2023-02-09T20:33:57.609931463Z",
      "sequence_num": 0,
      "events": [
        {
          "type": "snapshot",
          "orders": [
            {
              "order_id": "XXX",
              "client_order_id": "YYY",
              "cumulative_quantity": "0",
              "leaves_quantity": "0.000994",
              "avg_price": "0",
              "total_fees": "0",
              "status": "OPEN",
              "product_id": "BTC-USD",
              "creation_time": "2022-12-07T19:42:18.719312Z",
              "order_side": "BUY",
              "order_type": "Limit"
            },
          ]
        }
      ]
    }
    """
    # logging.debug(f"Cumulative handler received event {event_message}")
    # The timestamp may have been updated by the sequencer or another pipe
    if not isinstance(event_message["timestamp"], float):
        event_message["timestamp"] = get_timestamp_from_exchange_time(event_message["timestamp"], "s")

    timestamp_s: float = event_message["timestamp"]
    for event in event_message.get("events"):
        for order in event["orders"]:
            try:
                if order["client_order_id"] != '':
                    order_type: OrderType | None = None
                    if order["order_type"] == "Limit":
                        order_type = OrderType.LIMIT
                    elif order["order_type"] == "Market":
                        order_type = OrderType.MARKET
                    # elif order["order_type"] == "Stop Limit":
                    #     order_type = OrderType.STOP_LIMIT

                    cumulative_order: CoinbaseAdvancedTradeCumulativeUpdate = CoinbaseAdvancedTradeCumulativeUpdate(
                        exchange_order_id=order["order_id"],
                        client_order_id=order["client_order_id"],
                        status=order["status"],
                        trading_pair=await symbol_to_pair(order["product_id"]),
                        fill_timestamp_s=timestamp_s,
                        average_price=Decimal(order["avg_price"]),
                        cumulative_base_amount=Decimal(order["cumulative_quantity"]),
                        remainder_base_amount=Decimal(order["leaves_quantity"]),
                        cumulative_fee=Decimal(order["total_fees"]),
                        order_type=order_type,
                        trade_type=TradeType.BUY if order["order_side"] == "BUY" else TradeType.SELL,
                        creation_timestamp_s=get_timestamp_from_exchange_time(order["creation_time"], "s"),
                    )
                    if logger:
                        logger.debug(f"Cumulative handler {cumulative_order}")
                    yield cumulative_order
                elif logger:
                    logger.debug(f"Skipping order {order}")

            except Exception as e:
                if logger:
                    logger.error(f"Failed to create a CumulativeUpdate error {e}"
                                 f"\n\t{order}")
                raise e


def collect_cumulative_update(
        event_message: CoinbaseAdvancedTradeCumulativeUpdate,
        logger: HummingbotLogger | logging.Logger | None = None,
) -> CoinbaseAdvancedTradeCumulativeUpdate:
    """
    Collect the CumulativeUpdate messages from the stream.
    :param event_message: The message received from the exchange.
    :param logger: The logger to use.
    """
    # Filter-out non-CumulativeUpdate messages
    if isinstance(event_message, CoinbaseAdvancedTradeCumulativeUpdate):
        return event_message

    if logger:
        logger.error(f"Invalid message type: {type(event_message)} {event_message}")
    raise ValueError(f"Invalid message type: {type(event_message)} {event_message}")


class CoinbaseAdvancedTradeAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    UserStreamTrackerDataSource implementation for Coinbase Advanced Trade API.
    """
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    __slots__ = (
        "_sequences",
        "_stream_to_queue",
    )

    def __init__(
            self,
            channel: str,
            pairs: Tuple[str, ...],
            ws_factory: Callable[[], Coroutine[Any, Any, WSAssistantPtl]],
            ws_url: str,
            pair_to_symbol: Callable[[str], Coroutine[Any, Any, str]] | None,
            symbol_to_pair: Callable[[str], Coroutine[Any, Any, str]] | None,
            heartbeat_channel: str | None = None,
    ) -> None:
        """
        Initialize the Coinbase Advanced Trade API user stream data source.

        :param channel: The channels to subscribe to.
        :param pairs: The trading pairs to subscribe to.
        :param ws_factory: The factory function to create a websocket connection.
        :param ws_url: The websocket URL.
        :param pair_to_symbol: The function to convert a trading pair to a symbol.
        :param symbol_to_pair: The function to convert a symbol to a trading pair.
        :param heartbeat_channel: The channel to send heartbeat messages to.
        """
        super().__init__()
        self._sequences: defaultdict[str, int] = defaultdict(int)

        self._stream_to_queue: SingleStreamDataSource = SingleStreamDataSource(
            channel=channel,
            pairs=pairs,
            ws_factory=ws_factory,
            ws_url=ws_url,
            pair_to_symbol=pair_to_symbol,
            subscription_builder=coinbase_advanced_trade_subscription_builder,
            on_failed_subscription=on_failed_subscription,
            sequence_reader=functools.partial(
                sequence_reader,  # Validate the sequence number
                logger=self.logger()),
            transformers=[
                functools.partial(
                    timestamp_and_filter,  # Reformat the timestamp to seconds
                    logger=self.logger()),
                functools.partial(
                    message_to_cumulative_update,
                    symbol_to_pair=symbol_to_pair,
                    logger=self.logger()),
                functools.partial(
                    collect_cumulative_update,
                    logger=self.logger()),
            ],
            heartbeat_channel=heartbeat_channel,
        )

    async def _connected_websocket_assistant(self):
        raise NotImplementedError("This method is not implemented.")

    async def _subscribe_channels(self, websocket_assistant):
        raise NotImplementedError("This method is not implemented.")

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message

        :return: the timestamp of the last received message in seconds
        """
        return self._stream_to_queue.last_recv_time

    async def listen_for_user_stream(self, output: asyncio.Queue[CoinbaseAdvancedTradeCumulativeUpdate]):
        self.logger().debug(f"Starting for user streams {self._stream_to_queue}")
        await self._stream_to_queue.start_stream()
        self.logger().debug("Subscribing to the streams")
        await self._stream_to_queue.subscribe()

        while True:
            message: CoinbaseAdvancedTradeCumulativeUpdate = await self._stream_to_queue.queue.get()
            # Filter-out non-CumulativeUpdate messages
            if isinstance(message, CoinbaseAdvancedTradeCumulativeUpdate):
                await output.put(message)
            elif message is SENTINEL:
                self.logger().debug("SENTINEL received")
            else:
                self.logger().error(f"Invalid message type: {type(message)} {message}")
                raise ValueError(f"Invalid message type: {type(message)} {message}")

    def stop_nowait(self):
        self.logger().debug("Stopping the stream")
        self._stream_to_queue.stop_task_nowait()
        self.logger().debug("Stopped")
