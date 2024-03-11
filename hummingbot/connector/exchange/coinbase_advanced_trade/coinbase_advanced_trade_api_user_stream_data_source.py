import asyncio
import logging
from asyncio import Task
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, NamedTuple, Tuple

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants as constants
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

from .coinbase_advanced_trade_web_utils import get_timestamp_from_exchange_time

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_exchange import (  # noqa: F401
        CoinbaseAdvancedTradeExchange,
    )


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


class CoinbaseAdvancedTradeAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    UserStreamTrackerDataSource implementation for Coinbase Advanced Trade API.
    """
    # Queue keys for the message queue - Should be "user"
    _queue_keys: Tuple[str, ...] = ("user",)
    _sequence: Dict[str, int] = defaultdict(int)
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    def __init__(self,
                 auth,
                 trading_pairs: List[str],
                 connector: 'CoinbaseAdvancedTradeExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = "com"):
        """
        Initialize the CoinbaseAdvancedTradeAPIUserStreamDataSource.

        :param auth: The CoinbaseAdvancedTradeAuth instance for authentication.
        :param trading_pairs: The list of trading pairs to subscribe to.
        :param connector: The CoinbaseAdvancedTradeExchangePairProtocol implementation.
        :param api_factory: The WebAssistantsFactory instance for creating the WSAssistant.
        :param domain: The domain for the WebSocket connection.
        """
        super().__init__()
        self._domain: str = domain
        self._api_factory: WebAssistantsFactory = api_factory
        self._trading_pairs: List[str] = trading_pairs
        self._connector = connector

        self._subscription_lock: asyncio.Lock = asyncio.Lock()
        self._ws_assistant: Dict[str, WSAssistant | None] = {}
        self._tasks: Dict[str, Task] = {}

    async def close(self):
        """
        Cleans the async context
        """
        # Disconnect from the websocket
        [await v.disconnect() for v in self._ws_assistant.values() if v is not None]
        self._ws_assistant = {k: None for k in self._ws_assistant.keys()}

    # Implemented methods
    async def _connected_websocket_assistant(self, pair=None) -> Dict[str, WSAssistant | None]:
        """
        Create and connect the WebSocket assistant.

        :return: The connected WSAssistant instance.
        """
        if pair is not None:
            self._ws_assistant[pair] = await self._api_factory.get_ws_assistant()

            await self._ws_assistant[pair].connect(
                ws_url=constants.WSS_URL.format(domain=self._domain),
                ping_timeout=constants.WS_HEARTBEAT_TIME_INTERVAL
            )
            return self._ws_assistant

        self._ws_assistant: Dict[str, WSAssistant] = {
            p: await self._api_factory.get_ws_assistant() for p in self._trading_pairs
        }
        [
            await v.connect(
                ws_url=constants.WSS_URL.format(domain=self._domain),
                ping_timeout=constants.WS_HEARTBEAT_TIME_INTERVAL
            ) for v in self._ws_assistant.values() if v is not None
        ]
        return self._ws_assistant

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message

        :return: the timestamp of the last received message in seconds
        """
        if self._ws_assistant:
            last_recv_time: float = max(v.last_recv_time for v in self._ws_assistant.values() if v is not None)
            return last_recv_time
        return 0

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue

        :param output: the queue to use to store the received messages
        """
        try:
            # Create the listener for each trading pair that does not have one active
            for pair in self._trading_pairs:
                if self._tasks.get(pair) is None:
                    self._tasks[pair] = asyncio.create_task(self._listen_for_user_stream(pair, output=output))
            while True:
                # Await for a task to complete
                done, pending = await asyncio.wait(self._tasks.values(), return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    if task.cancelled():
                        raise asyncio.CancelledError
                    if pair := next(k for k, v in self._tasks.items() if v == task):
                        self._tasks[pair] = asyncio.create_task(self._listen_for_user_stream(pair, output=output))
        except asyncio.CancelledError:
            raise
        finally:
            # Cancel all the sub-listeners
            [task.cancel() for task in self._tasks.values() if task is not None]
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    async def _listen_for_user_stream(self, pair: str, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue

        :param pair: The trading pair to subscribe to.
        :param output: the queue to use to store the received messages
        """
        sleep_ = 0
        while True:
            try:
                await self._connected_websocket_assistant(pair)
                await self._subscribe_channels(websocket_assistant=self._ws_assistant[pair])
                await self._send_ping(websocket_assistant=self._ws_assistant[pair])  # to update last_recv_timestamp
                await self._process_websocket_messages(websocket_assistant=self._ws_assistant[pair], queue=output)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception as e:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
                self.logger().debug(f"Exception: {e}")
                sleep_ = 5
            finally:
                if pair in self._ws_assistant:
                    if self._ws_assistant[pair] is not None:
                        await self._ws_assistant[pair].disconnect()
                    self._ws_assistant[pair] = None
                await self._sleep(sleep_)

    async def _subscribe_channel(self, websocket_assistant: WSAssistant, pair) -> None:
        """
        Subscribes to the user events through the provided websocket connection.
        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        await self._subscribe_or_unsubscribe(
            websocket_assistant,
            constants.WebsocketAction.SUBSCRIBE,
            pair,
        )

    async def _unsubscribe_channel(
            self,
            websocket_assistant: WSAssistant,
            pair: str
    ) -> None:
        """
        Unsubscribes to the user events through the provided websocket connection.
        :param websocket_assistant: the websocket assistant used to connect to the exchange
        :param pair: The trading pairs to unsubscribe from. If None, unsubscribe from all.
        """
        await self._subscribe_or_unsubscribe(
            websocket_assistant,
            constants.WebsocketAction.UNSUBSCRIBE,
            pair
        )

    async def _subscribe_or_unsubscribe(
            self,
            websocket_assistant: WSAssistant,
            action: constants.WebsocketAction,
            pair: str
    ) -> None:
        """
        Applies the WebsocketAction in argument to the list of channels/pairs through the provided websocket connection.
        :param action: WebsocketAction defined in the CoinbaseAdvancedTradeConstants.
        :param websocket_assistant: the websocket assistant used to connect to the exchange
        :param pair: The trading pairs to apply action to. If None, applies action to all.
        """
        """
        https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-best-practices

        Recommended to use one subscription per channel
        {
            "type": "subscribe",  # or "unsubscribe"
            "product_ids": [
                "ETH-USD",
                "BTC-USD"   # Possible but not preferred
            ],
            "channel": "user",

            # Complemented by the WSAssistant
            "signature": "XYZ",
            "api_key": "XXX",
            "timestamp": 1675974199
        }
        """
        async with self._subscription_lock:
            symbol: str = await self._connector.exchange_symbol_associated_to_pair(trading_pair=pair)

            payload = {
                "type": action.value,
                "product_ids": [symbol],
                "channel": constants.WS_USER_SUBSCRIPTION_KEYS,
            }

            try:
                # Change subscription to the channel and pair
                await websocket_assistant.send(WSJSONRequest(payload=payload))
                self.logger().debug(
                    f"{action.value.capitalize()}d to {constants.WS_USER_SUBSCRIPTION_KEYS} for {pair}...")
                self.logger().info(
                    f"{action.value.capitalize()}d to {constants.WS_USER_SUBSCRIPTION_KEYS} for {pair}...")
            except (asyncio.CancelledError, Exception) as e:
                await self.close()  # Clean the async context
                self.logger().exception(
                    f"Unexpected error occurred {action.value.capitalize()}-ing "
                    f"to {constants.WS_USER_SUBSCRIPTION_KEYS} for {pair}...\n"
                    f"Exception: {e}",
                    exc_info=True
                )
                raise

    @staticmethod
    async def _try_except_queue_put(item: Any, queue: asyncio.Queue):
        """
        Try to put the order into the queue, except if the queue is full.
        :param queue: The queue to put the order into.
        """
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                await asyncio.wait_for(queue.put(item), timeout=1.0)
            except asyncio.TimeoutError:
                raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        """
        Processes the messages from the websocket connection and puts them into the intermediary queue.
        :param websocket_assistant: the websocket assistant used to connect to the exchange
        :param queue: The intermediary queue to put the messages into.
        """
        async for ws_response in websocket_assistant.iter_messages():  # type: ignore # PyCharm doesn't recognize iter_messages
            data: Dict[str, Any] = ws_response.data
            async for order in self._decipher_message(event_message=data):
                try:
                    await self._try_except_queue_put(item=order, queue=queue)
                except asyncio.QueueFull:
                    self.logger().exception("Timeout while waiting to put message into raw queue. Message dropped.")
                    raise

    async def _decipher_message(self, event_message: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streamline the messages for processing by the exchange.
        :param event_message: The message received from the exchange.
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
        channel: str = event_message["channel"]
        sequence: int = event_message["sequence_num"]

        if sequence != self._sequence[channel]:
            self.logger().warning(
                f"Sequence number mismatch. Expected {self._sequence[channel]}, received {sequence}."
            )

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
                            trading_pair=await self._connector.trading_pair_associated_to_exchange_symbol(
                                symbol=order["product_id"]
                            ),
                            fill_timestamp_s=timestamp_s,
                            average_price=Decimal(order["avg_price"]),
                            cumulative_base_amount=Decimal(order["cumulative_quantity"]),
                            remainder_base_amount=Decimal(order["leaves_quantity"]),
                            cumulative_fee=Decimal(order["total_fees"]),
                            order_type=order_type,
                            trade_type=TradeType.BUY if order["order_side"] == "BUY" else TradeType.SELL,
                            creation_timestamp_s=get_timestamp_from_exchange_time(order["creation_time"], "s"),
                        )
                        yield cumulative_order

                except Exception as e:
                    self.logger().exception(f"Failed to create a CumulativeUpdate error {e}\n\t{order}")
                    raise e

        # Update the expected next sequence number
        self._sequence[channel] = sequence + 1
