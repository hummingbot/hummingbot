import asyncio
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, NamedTuple

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants as constants
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils import (
    get_timestamp_from_exchange_time,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

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
    _sequence: int = 0
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

        self._ws_assistant: WSAssistant | None = None
        self._reset_recv_time: bool = False

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message

        :return: the timestamp of the last received message in seconds
        """
        if self._ws_assistant and not self._reset_recv_time:
            return self._ws_assistant.last_recv_time
        return 0

    async def _connected_websocket_assistant(self, pair=None) -> WSAssistant:
        """
        Create and connect the WebSocket assistant.

        :return: The connected WSAssistant instance.
        """
        self._ws_assistant = await self._api_factory.get_ws_assistant()

        await self._ws_assistant.connect(
            ws_url=constants.WSS_URL.format(domain=self._domain),
            ping_timeout=constants.WS_HEARTBEAT_TIME_INTERVAL
        )
        return self._ws_assistant

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
        """
        Subscribes to the user events through the provided websocket connection.
        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        await self._subscribe_or_unsubscribe(websocket_assistant, constants.WebsocketAction.SUBSCRIBE)

    async def _unsubscribe_channels(self, websocket_assistant: WSAssistant) -> None:
        """
        Unsubscribes to the user events through the provided websocket connection.
        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        await self._subscribe_or_unsubscribe(websocket_assistant, constants.WebsocketAction.UNSUBSCRIBE)

    async def _subscribe_or_unsubscribe(
            self,
            websocket_assistant: WSAssistant,
            action: constants.WebsocketAction
    ) -> None:
        """
        Applies the WebsocketAction in argument to the list of channels/pairs through the provided websocket connection.
        :param action: WebsocketAction defined in the CoinbaseAdvancedTradeConstants.
        :param websocket_assistant: the websocket assistant used to connect to the exchange
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
            or
            jwt: "JWT",
            "timestamp": 1675974199
        }
        """
        symbols: List[str] = [
            await self._connector.exchange_symbol_associated_to_pair(trading_pair=pair) for pair in self._trading_pairs
        ]

        try:
            for channel in ["heartbeats", constants.WS_USER_SUBSCRIPTION_KEYS]:
                payload = {
                    "type": action.value,
                    "product_ids": symbols,
                    "channel": channel,
                }

                # Change subscription to the channel and pair
                await websocket_assistant.send(WSJSONRequest(payload=payload, is_auth_required=True))
            self.logger().info(
                f"{action.value.capitalize()}-ing to {constants.WS_USER_SUBSCRIPTION_KEYS} for {self._trading_pairs} ...")
        except (asyncio.CancelledError, Exception) as e:
            self.logger().exception(
                f"Unexpected error occurred {action.value.capitalize()}-ing "
                f"to {constants.WS_USER_SUBSCRIPTION_KEYS} for {self._trading_pairs}...\n"
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
            await asyncio.sleep(0)
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

            if 'type' in data and data["type"] == "error":
                if "authentication failure" in data["message"]:
                    self.logger().error(f"authentication error: {data}")
                    await self._subscribe_channels(self._ws_assistant)
                else:
                    self.logger().error(f"Received error message: {data}")
                # Reset last received time
                self._reset_recv_time = True
                return

            self._process_sequence_number(data)

            channel: str = data["channel"]
            if channel == 'user':
                async for order in self._decipher_message(event_message=data):
                    try:
                        # queue.put_nowait(order)
                        await self._try_except_queue_put(item=order, queue=queue)
                    except asyncio.QueueFull:
                        self.logger().exception("Timeout while waiting to put message into raw queue. Message dropped.")
                        raise
            elif channel == 'subscriptions':
                self._process_subscription_message(data)
            elif channel in {"heartbeats"}:
                self._process_heartbeat_message(data)

    def _process_sequence_number(self, data: Dict[str, Any]):
        """
        Processes the sequence number from the websocket message.
        :param data: The message received from the websocket connection.
        """
        if "sequence_num" in data and data["sequence_num"] > self._sequence:
            self.logger().warning(
                f"Received a message with a higher sequence number than the current one. "
                f"Current sequence: {self._sequence}, received sequence: {data['sequence_num']}."
            )

        self._sequence = data["sequence_num"] + 1

    def _process_subscription_message(self, data: Dict[str, Any]):
        """
        Processes the subscription message from the websocket connection.
        :param data: The message received from the websocket connection.
        """
        pass  # self.logger().debug(f"Received subscription message: {data}")

    def _process_heartbeat_message(self, data: Dict[str, Any]):
        """
        Processes the heartbeat message from the websocket connection.
        :param data: The message received from the websocket connection.
        """
        pass  # self.logger().debug(f"Received heartbeat message: {data}")

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
        # self.logger().debug(f" '-> _decipher_message: message: {event_message}")

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
                        self.logger().debug(f"Yielding order: {cumulative_order}")
                        yield cumulative_order

                except Exception as e:
                    self.logger().exception(f"Failed to create a CumulativeUpdate error {e}\n\t{order}")
                    raise e
