import asyncio
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants as constants
import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils as web_utils
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_exchange import CoinbaseAdvancedTradeExchange

from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_order_book import (
    CoinbaseAdvancedTradeOrderBook,
)


class CoinbaseAdvancedTradeAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'CoinbaseAdvancedTradeExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = constants.DEFAULT_DOMAIN):
        """
        Initialize the CoinbaseAdvancedTradeAPIUserStreamDataSource.

        :param trading_pairs: The list of trading pairs to subscribe to.
        :param connector: The CoinbaseAdvancedTradeExchangePairProtocol implementation.
        :param api_factory: The WebAssistantsFactory instance for creating the WSAssistant.
        :param domain: The domain for the WebSocket connection.
        """
        super().__init__(trading_pairs)
        self._domain: str = domain
        self._api_factory: WebAssistantsFactory = api_factory
        self._connector: 'CoinbaseAdvancedTradeExchange' = connector

        self._subscription_lock: Optional[asyncio.Lock] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._last_traded_prices: Dict[str, float] = defaultdict(lambda: 0.0)

        # Override the default base queue keys
        self._diff_messages_queue_key = constants.WS_ORDER_SUBSCRIPTION_KEYS[0]
        self._trade_messages_queue_key = constants.WS_ORDER_SUBSCRIPTION_KEYS[1]
        self._snapshot_messages_queue_key = "unused_snapshot_queue"

    async def _parse_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        order_book_message: OrderBookMessage = await CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            raw_message,
            self._connector.exchange_symbol_associated_to_pair)
        await message_queue.put(order_book_message)

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        await asyncio.sleep(0)
        return {trading_pair: self._last_traded_prices[trading_pair] or 0.0 for trading_pair in trading_pairs}

    # --- Overriding methods from the Base class ---
    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Reads the order diffs events queue. For each event creates a diff message instance and adds it to the
        output queue

        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created diff messages
        """
        while True:
            try:
                event = await self._message_queue[self._diff_messages_queue_key].get()
                await self._parse_message(raw_message=event, message_queue=output)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public order book updates from exchange")

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Coinbase Advanced Trade does not provide snapshots messages.
        The snapshot is retrieved from the first message of the 'level2' channel.

        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created snapshot messages
        """
        pass

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output_queue: asyncio.Queue):
        """
        Reads the trade events queue.
        For each event creates a trade message instance and adds it to the output queue

        :param ev_loop: the event loop the method will run in
        :param output_queue: a queue to add the created trade messages
        """
        while True:
            try:
                trade_event = await self._message_queue[self._trade_messages_queue_key].get()
                await self._parse_message(raw_message=trade_event, message_queue=output_queue)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public trade updates from exchange")

    def _get_messages_queue_keys(self) -> Tuple[str, ...]:
        return tuple(constants.WS_ORDER_SUBSCRIPTION_KEYS)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        if event_message and "channel" in event_message and event_message["channel"]:
            return constants.WS_ORDER_SUBSCRIPTION_CHANNELS.inverse[event_message["channel"]]

    # Implemented methods
    async def _connected_websocket_assistant(self) -> WSAssistant:
        self._ws_assistant: WSAssistant = await self._api_factory.get_ws_assistant()
        await self._ws_assistant.connect(ws_url=constants.WSS_URL.format(domain=self._domain))
        return self._ws_assistant

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the order book events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-best-practices

        Recommended to use several subscriptions
        {
            "type": "subscribe",
            "product_ids": [
                "ETH-USD",
                "BTC-USD"
            ],
            "channel": "level2",

            # Complemented by the WSAssistant
            "signature": "XYZ",
            "api_key": "XXX",
            "timestamp": 1675974199
        }
        """
        try:
            symbols = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                symbols.append(symbol)

            for channel in ["heartbeats", *constants.WS_ORDER_SUBSCRIPTION_CHANNELS]:
                payload = {
                    "type": "subscribe",
                    "product_ids": symbols,
                    "channel": channel,
                }
                await ws.send(WSJSONRequest(payload=payload, is_auth_required=True))

            self.logger().info(f"Subscribed to order book channels for: {', '.join(self._trading_pairs)}")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data

            if data and "type" in data and data["type"] == 'error':
                self.logger().error(f"Error received from websocket: {ws_response}")
                raise ValueError(f"Error received from websocket: {ws_response}")

            if data is not None and "channel" in data:  # data will be None when the websocket is disconnected
                if data["channel"] in constants.WS_ORDER_SUBSCRIPTION_CHANNELS.inverse:
                    queue_key: str = constants.WS_ORDER_SUBSCRIPTION_CHANNELS.inverse[data["channel"]]
                    await self._message_queue[queue_key].put(data)

                elif data["channel"] in ["subscriptions", "heartbeats"]:
                    self.logger().debug(f"Ignoring message from Coinbase Advanced Trade: {data}")
                else:
                    self.logger().debug(
                        f"Unrecognized websocket message received from Coinbase Advanced Trade: {data['channel']}")
            else:
                self.logger().warning(f"Unrecognized websocket message received from Coinbase Advanced Trade: {data}")

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        params = {
            "product_id": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        snapshot: Dict[str, Any] = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=constants.SNAPSHOT_EP, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            is_auth_required=True,
            throttler_limit_id=constants.SNAPSHOT_EP,
        )

        snapshot_timestamp: float = self._connector.time_synchronizer.time()

        snapshot_msg: OrderBookMessage = CoinbaseAdvancedTradeOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    # --- Implementation of abstract methods from the Base class ---
    # Unused methods
    async def _parse_order_book_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError("Coinbase Advanced Trade does not implement this method.")

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError("Coinbase Advanced Trade does not implement this method.")

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError("Coinbase Advanced Trade does not implement this method.")
