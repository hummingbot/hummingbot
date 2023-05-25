import asyncio
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_protocols import (
    CoinbaseAdvancedTradeExchangePairProtocol,
    CoinbaseAdvancedTradeWSAssistantProtocol,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_order_book import CoinbaseAdvancedTradeOrderBook
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    pass


class CoinbaseAdvancedTradeAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: CoinbaseAdvancedTradeExchangePairProtocol,
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
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
        self._connector: CoinbaseAdvancedTradeExchangePairProtocol = connector

        self._subscription_lock: Optional[asyncio.Lock] = None
        self._ws_assistant: Optional[CoinbaseAdvancedTradeWSAssistantProtocol] = None
        self._last_traded_prices: Dict[str, float] = defaultdict(lambda: 0.0)

        # Override the default base queue keys
        self._diff_messages_queue_key = CONSTANTS.WS_ORDER_SUBSCRIPTION_KEYS[0]
        self._trade_messages_queue_key = CONSTANTS.WS_ORDER_SUBSCRIPTION_KEYS[1]
        self._snapshot_messages_queue_key = "unused_snapshot_queue"

    async def _parse_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        order_book_message: OrderBookMessage = await CoinbaseAdvancedTradeOrderBook.level2_or_trade_message_from_exchange(
            raw_message, time.time(), self._connector.trading_pair_associated_to_exchange_symbol)
        message_queue.put_nowait(order_book_message)

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

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        raise NotImplementedError("Coinbase Advanced Trade does not implement this method.")

    def _get_messages_queue_keys(self) -> Tuple[str]:
        return tuple(CONSTANTS.WS_ORDER_SUBSCRIPTION_KEYS)

    # --- Implementation of abstract methods from the Base class ---
    # Unused methods
    async def _parse_order_book_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError("Coinbase Advanced Trade does not implement this method.")

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError("Coinbase Advanced Trade does not implement this method.")

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError("Coinbase Advanced Trade does not implement this method.")

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        raise NotImplementedError("Coinbase Advanced Trade does not implement this method.")

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        if event_message and "channel" in event_message and event_message["channel"]:
            return CONSTANTS.WS_ORDER_SUBSCRIPTION_CHANNELS.inverse[event_message["channel"]]

    # Implemented methods
    async def _connected_websocket_assistant(self) -> WSAssistant:
        self._ws_assistant: WSAssistant = await self._api_factory.get_ws_assistant()
        await self._ws_assistant.connect(ws_url=CONSTANTS.WSS_URL.format(domain=self._domain),
                                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return self._ws_assistant

    async def _subscribe_channels(self, ws: CoinbaseAdvancedTradeWSAssistantProtocol):
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
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                for channel in CONSTANTS.WS_ORDER_SUBSCRIPTION_CHANNELS:
                    payload = {
                        "type": "subscribe",
                        "product_ids": [symbol],
                        "channel": channel,
                    }
                    await ws.send(WSJSONRequest(payload=payload))

            self.logger().info("Subscribed to public order book and trade channels...")
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
            if data is not None and "channel" in data:  # data will be None when the websocket is disconnected
                if data["channel"] in CONSTANTS.WS_ORDER_SUBSCRIPTION_CHANNELS:
                    self._message_queue[data["channel"]].put_nowait(data)
                else:
                    self.logger().warning(
                        f"Unrecognized websocket message received from Coinbase Advanced Trade: {data['channel']}")
            else:
                self.logger().warning(f"Unrecognized websocket message received from Coinbase Advanced Trade: {data}")
