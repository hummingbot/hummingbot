import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_constants import WebsocketAction
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_cumulative_trade import (
    CoinbaseAdvancedTradeCumulativeUpdate,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_protocols import (  # CoinbaseAdvancedTradeWebAssistantsFactoryProtocol,; WSAssistant,
    CoinbaseAdvancedTradeAuthProtocol,
    CoinbaseAdvancedTradeExchangePairProtocol,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils import get_timestamp_from_exchange_time
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class CoinbaseAdvancedTradeAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    UserStreamTrackerDataSource implementation for Coinbase Advanced Trade API.
    """
    # Queue keys for the message queue - Should be "user"
    _queue_keys: Tuple[str] = CONSTANTS.WS_USER_SUBSCRIPTION_KEYS
    _sequence: Dict[str, int] = defaultdict(int)

    def __init__(self,
                 auth: CoinbaseAdvancedTradeAuthProtocol,
                 trading_pairs: List[str],
                 connector: CoinbaseAdvancedTradeExchangePairProtocol,
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
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
        self._connector: CoinbaseAdvancedTradeExchangePairProtocol = connector

        self._subscription_lock: Optional[asyncio.Lock] = None
        self._ws_assistant: Optional[WSAssistant] = None

        # Localized message queue for pre-processing
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._message_queue_lock: Optional[asyncio.Lock] = None
        self._message_queue_task: Optional[asyncio.Task] = None

    def _async_init(self):
        """
        Initialize the async context.
        """
        if not self._message_queue_lock:
            self._message_queue_lock = asyncio.Lock()
        if not self._subscription_lock:
            self._subscription_lock = asyncio.Lock()
        if not self._message_queue_task:
            self._message_queue_task = asyncio.create_task(self._preprocess_messages())

    async def close(self):
        """
        Cleans the async context
        """
        # Cancel any remaining tasks
        if self._message_queue_task is not None:
            self._message_queue_task.cancel()
            self._message_queue_task = None

        # Disconnect from the websocket
        if self._ws_assistant is not None:
            await self._ws_assistant.disconnect()
            self._ws_assistant = None

    # Implemented methods
    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and connect the WebSocket assistant.

        :return: The connected WSAssistant instance.
        """
        # Initialize the async context
        self._async_init()

        self._ws_assistant: WSAssistant = await self._api_factory.get_ws_assistant()
        await self._ws_assistant.connect(ws_url=CONSTANTS.WSS_URL.format(domain=self._domain),
                                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return self._ws_assistant

    async def _subscribe_channels(self, ws: WSAssistant) -> None:
        """
        Subscribes to the user events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        """
        https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-best-practices

        Recommended to use several subscriptions
        {
            "type": "subscribe",
            "product_ids": [
                "ETH-USD",
                "BTC-USD"
            ],
            "channel": "user",

            # Complemented by the WSAssistant
            "signature": "XYZ",
            "api_key": "XXX",
            "timestamp": 1675974199
        }
        """
        # Initialize the async context
        self._async_init()

        channels, trading_pairs = self._get_target_channels_and_pairs(None, None)
        await self._subscribe_or_unsubscribe(ws, WebsocketAction.SUBSCRIBE, channels, trading_pairs)

    async def _unsubscribe_channels(self, ws: WSAssistant,
                                    channels: Optional[List[str]] = None,
                                    trading_pairs: Optional[List[str]] = None) -> None:
        """
        Unsubscribes to the user events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        :param channels: The channels to unsubscribe from. If None, unsubscribe from all.
        :param trading_pairs: The trading pairs to unsubscribe from. If None, unsubscribe from all.
        """
        """
        https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-overview#unsubscribe
        {
            "type": "unsubscribe",
            "product_ids": [
                "ETH-USD",
                "ETH-EUR"
            ],
            "channel": "user",
            "api_key": "exampleApiKey123",
            "timestamp": 1660839876,
            "signature": "00000000000000000000000000",
        }
        """
        # Initialize the async context
        self._async_init()

        channels, trading_pairs = self._get_target_channels_and_pairs(channels, trading_pairs)
        await self._subscribe_or_unsubscribe(ws, WebsocketAction.UNSUBSCRIBE, channels, trading_pairs)

    async def _subscribe_or_unsubscribe(self,
                                        ws: WSAssistant,
                                        action: WebsocketAction,
                                        channels: Optional[List[str]] = None,
                                        trading_pairs: Optional[List[str]] = None) -> None:
        """
        Applies the WebsocketAction in argument to the list of channels/pairs through the provided websocket connection.
        :param action: WebsocketAction defined in the CoinbaseAdvancedTradeConstants.
        :param ws: the websocket assistant used to connect to the exchange
        :param channels: The channels to apply action to. If None, applies action to all.
        :param trading_pairs: The trading pairs to apply action to. If None, applies action to all.
        """
        # Initialize the async context
        self._async_init()

        async with self._subscription_lock:
            for channel in channels:
                for trading_pair in trading_pairs:
                    symbol: str = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                    payload = {
                        "type": action.value,
                        "product_ids": [symbol],
                        "channel": channel,
                    }

                    await self._manage_queue(f"{channel}-{symbol}", action)

                    try:
                        # Change subscription to the channel and pair
                        await ws.send(WSJSONRequest(payload=payload))
                        self.logger().info(f"{action.value.capitalize()}d to {channel} for {trading_pair}...")
                    except asyncio.CancelledError:
                        await ws.disconnect()  # Close the connection
                        await self.close()  # Clean the async context
                        raise
                    except Exception:
                        await self.close()  # Clean the async context
                        self.logger().error(
                            f"Unexpected error occurred {action.value.capitalize()}-ing "
                            f"to {channel} for {trading_pair}...",
                            exc_info=True
                        )
                        raise

    async def _manage_queue(self, channel_symbol: str, action: WebsocketAction):
        """
        Manage the queue of messages received from the websocket.
        :param channel_symbol: The channel symbol associated to the queue.
        :param action: The action to apply to the queue.
        """
        # Initialize the async context
        self._async_init()

        if action == WebsocketAction.UNSUBSCRIBE:
            async with self._message_queue_lock:
                # Clear the queue for the channel and pair
                while not self._message_queue[channel_symbol].empty():
                    try:
                        _, _ = self._message_queue[channel_symbol].get_nowait()
                        self._message_queue[channel_symbol].task_done()
                    except asyncio.QueueEmpty:
                        break
                self._message_queue.pop(channel_symbol)

                if len(self._message_queue) == 0 and self._message_queue_task and not self._message_queue_task.done():
                    self._message_queue_task.cancel()
                    self._message_queue_task = None

        if action == WebsocketAction.SUBSCRIBE:
            if self._message_queue_task is None or self._message_queue_task.done():
                self._message_queue_task = asyncio.create_task(self._preprocess_messages())

        raise ValueError(f"Unknown action {action.value}.")  # Should never happen

    def _get_target_channels_and_pairs(self,
                                       channels: Optional[List[str]],
                                       trading_pairs: Optional[List[str]]) -> Tuple[List[str], List[str]]:
        target_channels = channels if channels is not None else self._queue_keys
        target_trading_pairs = trading_pairs if trading_pairs is not None else self._trading_pairs
        return target_channels, target_trading_pairs

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

    async def _process_websocket_messages(self, ws: WSAssistant, queue: asyncio.Queue):
        """
        Processes the messages from the websocket connection and puts them into the intermediary queue.
        :param ws: the websocket assistant used to connect to the exchange
        :param queue: The intermediary queue to put the messages into.
        """
        async for ws_response in ws.iter_messages():  # type: ignore # PyCharm doesn't recognize iter_messages
            data: Dict[str, Any] = ws_response.data
            channel_symbol = f"{data['channel']}-{data['product_id']}"
            try:
                # Dispatch each product to its own queue
                await self._try_except_queue_put(item=(data, queue),
                                                 queue=self._message_queue[channel_symbol])
            except asyncio.QueueFull:
                self.logger().error("Timeout while waiting to put message into raw queue. Message dropped.")
                raise

    async def _preprocess_messages(self):
        """Takes messages from the intermediary queue, preprocesses them, and puts them into the final queue."""
        # Initialize the async context
        self._async_init()

        while True:
            for channel_symbol in self._message_queue:
                async with self._message_queue_lock:
                    message, final_queue = await self._message_queue[channel_symbol].get()
                async for order in self._decipher_message(event_message=message):
                    try:
                        await self._try_except_queue_put(item=order, queue=final_queue)
                    except asyncio.QueueFull:
                        self.logger().error("Timeout while waiting to put order into final queue. Order dropped.")
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

        for event in event_message.get("events"):
            timestamp_s: float = get_timestamp_from_exchange_time(event["timestamp"], "second")
            for order in event["orders"]:
                yield CoinbaseAdvancedTradeCumulativeUpdate(
                    exchange_order_id=order["order_id"],
                    client_order_id=order["client_order_id"],
                    status=order["status"],
                    trading_pair=await self._connector.trading_pair_associated_to_exchange_symbol(
                        symbol=order["product_id"]
                    ),
                    fill_timestamp=timestamp_s,
                    average_price=Decimal(order["avg_price"]),
                    cumulative_base_amount=Decimal(order["cumulative_quantity"]),
                    remainder_base_amount=Decimal(order["leaves_quantity"]),
                    cumulative_fee=Decimal(order["total_fees"]),
                )

        # Update the expected next sequence number
        self._sequence[channel] = sequence + 1
