import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, NamedTuple, Optional, Tuple

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from .coinbase_advanced_trade_v2_exchange import CoinbaseAdvancedTradeV2Exchange

from . import coinbase_advanced_trade_v2_constants as constants
from .coinbase_advanced_trade_v2_auth import CoinbaseAdvancedTradeV2Auth
from .coinbase_advanced_trade_v2_web_utils import get_timestamp_from_exchange_time


class CoinbaseAdvancedTradeV2CumulativeUpdate(NamedTuple):
    client_order_id: str
    exchange_order_id: str
    status: str
    trading_pair: str
    fill_timestamp: float  # seconds
    average_price: Decimal
    cumulative_base_amount: Decimal
    remainder_base_amount: Decimal
    cumulative_fee: Decimal
    is_taker: bool = False  # Coinbase Advanced Trade delivers trade events from the maker's perspective


class CoinbaseAdvancedTradeV2APIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    UserStreamTrackerDataSource implementation for Coinbase Advanced Trade API.
    """
    # Queue keys for the message queue - Should be "user"
    _queue_keys: Tuple[str] = constants.WS_USER_SUBSCRIPTION_KEYS
    _sequence: Dict[str, int] = defaultdict(int)

    def __init__(self,
                 auth: CoinbaseAdvancedTradeV2Auth,
                 trading_pairs: List[str],
                 connector: 'CoinbaseAdvancedTradeV2Exchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = constants.DEFAULT_DOMAIN):
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
        self._connector: 'CoinbaseAdvancedTradeV2Exchange' = connector

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
        from .coinbase_advanced_trade_v2_exchange import DebugToFile
        with DebugToFile.log_with_bullet(
                message="Connecting to Coinbase Advanced Trade user stream...",
                bullet="-"):
            await self._ws_assistant.connect(ws_url=constants.WSS_URL.format(domain=self._domain),
                                             ping_timeout=constants.WS_HEARTBEAT_TIME_INTERVAL)
        return self._ws_assistant

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
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
        from .coinbase_advanced_trade_v2_exchange import DebugToFile
        DebugToFile.log_debug(f"Subscribing to channels: {channels} and trading pairs: {trading_pairs}")
        await self._subscribe_or_unsubscribe(websocket_assistant, "subscribe", channels, trading_pairs)

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
        await self._subscribe_or_unsubscribe(ws, "unsubscribe", channels, trading_pairs)

    async def _subscribe_or_unsubscribe(self,
                                        ws: WSAssistant,
                                        action: str,
                                        channels: Optional[List[str]] = None,
                                        trading_pairs: Optional[List[str]] = None) -> None:
        """
        Applies the WebsocketAction in argument to the list of channels/pairs through the provided websocket connection.
        :param action: WebsocketAction defined in the CoinbaseAdvancedTradeConstants.
        :param ws: the websocket assistant used to connect to the exchange
        :param channels: The channels to apply action to. If None, applies action to all.
        :param trading_pairs: The trading pairs to apply action to. If None, applies action to all.
        """
        if channels is None or len(channels) == 0:
            return

        # Initialize the async context
        self._async_init()

        from .coinbase_advanced_trade_v2_exchange import DebugToFile
        with DebugToFile.log_with_bullet(
                message=f"{action.capitalize()}ing to {channels} for {trading_pairs}...",
                bullet="["):
            async with self._subscription_lock:
                for channel in channels:
                    for trading_pair in trading_pairs:
                        symbol: str = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                        payload = {
                            "type": action,
                            "product_ids": [symbol],
                            "channel": channel,
                        }

                        await self._manage_queue(f"{channel}:{symbol}", action)

                        try:
                            # Change subscription to the channel and pair
                            await ws.send(WSJSONRequest(payload=payload, is_auth_required=True))
                            ws_response: WSResponse = await ws.receive()
                            self.logger().info(f"{action.capitalize()}d to {channel} for {trading_pair}...")
                            DebugToFile.log_debug(f"Subscribing to {channel} channel for {symbol}...")
                            DebugToFile.log_debug(f"User: {ws_response}")
                        except (asyncio.CancelledError, Exception) as e:
                            await self.close()  # Clean the async context
                            self.logger().error(
                                f"Unexpected error occurred {action.capitalize()}-ing "
                                f"to {channel} for {trading_pair}...\n"
                                f"Exception: {e}",
                                exc_info=True
                            )
                            raise

    async def _manage_queue(self, channel_symbol: str, action: str):
        """
        Manage the queue of messages received from the websocket.
        :param channel_symbol: The channel symbol associated to the queue.
        :param action: The action to apply to the queue.
        """
        # Initialize the async context
        if action not in ["subscribe", "unsubscribe"]:
            self.logger().error(
                f"Unsupported action {action.capitalize()} "
                f"to {channel_symbol}...\n",
                exc_info=True
            )
            return

        self._async_init()

        if action == "subscribe":
            if self._message_queue_task is None or self._message_queue_task.done():
                self._message_queue_task = asyncio.create_task(self._preprocess_messages())

        elif action == "unsubscribe":
            async with self._message_queue_lock:
                # Clear the queue for the channel and pair
                while not self._message_queue[channel_symbol].empty():
                    try:
                        _, _ = await self._message_queue[channel_symbol].get()
                        self._message_queue[channel_symbol].task_done()
                    except asyncio.QueueEmpty:
                        break
                self._message_queue.pop(channel_symbol)

                if len(self._message_queue) == 0 and self._message_queue_task and not self._message_queue_task.done():
                    self._message_queue_task.cancel()
                    self._message_queue_task = None

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

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        """
        Processes the messages from the websocket connection and puts them into the intermediary queue.
        :param ws: the websocket assistant used to connect to the exchange
        :param queue: The intermediary queue to put the messages into.
        """
        async for ws_response in websocket_assistant.iter_messages():  # type: ignore # PyCharm doesn't recognize iter_messages

            if "type" in ws_response.data and ws_response.data["type"] == 'error':
                self.logger().error(f"Error received from websocket: {ws_response}")
                raise Exception(f"Error received from websocket: {ws_response}")

            data: Dict[str, Any] = ws_response.data
            from .coinbase_advanced_trade_v2_exchange import DebugToFile
            DebugToFile.log_debug(f"{ws_response}")

            if len(data["events"]) == 0:
                continue

            for event in data["events"]:
                DebugToFile.log_debug(f"{event}")
                if "orders" not in event or len(event["orders"]) == 0:
                    continue

                for order in event["orders"]:
                    channel_symbol = f"{data['channel']}:{order['product_id']}"
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
            # When there are no channels, this for blocks the event loop
            await asyncio.sleep(0)
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
                yield CoinbaseAdvancedTradeV2CumulativeUpdate(
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
