import asyncio
import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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
        self._diff_messages_queue_key = constants.WS_ORDER_SUBSCRIPTION_CHANNELS.inverse["order_book_diff"]
        self._trade_messages_queue_key = constants.WS_ORDER_SUBSCRIPTION_CHANNELS.inverse["trade"]

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        # await asyncio.sleep(0)
        return {trading_pair: self._last_traded_prices[trading_pair] or 0.0 for trading_pair in trading_pairs}

    # Implemented methods

    async def _request_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
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
        return snapshot

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the order book events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        https://docs.cdp.coinbase.com/advanced-trade/docs/ws-best-practices

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

            for channel in ["heartbeats", *constants.WS_ORDER_SUBSCRIPTION_KEYS]:
                payload = {
                    "type": "subscribe",
                    "product_ids": symbols,
                    "channel": channel,
                }
                await ws.send(WSJSONRequest(payload=payload, is_auth_required=True))

            self.logger().info(f"Subscribed to order book channels for: {', '.join(self._trading_pairs)}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            self.logger().debug(f"Error: {e}")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        """_summary_
        Processes the messages received from the websocket connection.
        {
            'channel': 'l2_data',
            'client_id': '',
            'timestamp': '2024-10-08T09:10:36.120390407Z',
            'sequence_num': 14,
            'events': [
                {
                    'type': 'update',
                    'product_id': 'BTC-USD',
                    'updates': [
                        {
                            'side': 'bid',
                            'event_time': '2024-10-08T09:10:35.171517Z',
                            'price_level': '62317.89',
                            'new_quantity': '0.032355'},
                        {
                            'side': 'offer',
                            'event_time': '2024-10-08T09:10:35.171517Z',
                            'price_level': '62394.77',
                            'new_quantity': '0.0170024'
                        }
                    ]
                }
            ]
        }
        """
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data

            if data and "type" in data and data["type"] == 'error':
                self.logger().error(f"Error received from websocket: {ws_response}")
                raise ValueError(f"Error received from websocket: {ws_response}")

            if data is not None and "channel" in data:  # data will be None when the websocket is disconnected
                if data["channel"] in constants.WS_ORDER_SUBSCRIPTION_CHANNELS.keys():
                    queue_key: str = constants.WS_ORDER_SUBSCRIPTION_CHANNELS[data["channel"]]
                    await self._message_queue[queue_key].put(data)

                elif data["channel"] in ["subscriptions", "heartbeats"]:
                    self.logger().debug(f"Ignoring message from Coinbase Advanced Trade: {data}")
                else:
                    self.logger().debug(
                        f"Unrecognized websocket message received from Coinbase Advanced Trade: {data['channel']}")
            else:
                self.logger().warning(f"Unrecognized websocket message received from Coinbase Advanced Trade: {data}")

    # --- Implementation of abstract methods from the Base class ---
    # Unused methods
    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = CoinbaseAdvancedTradeOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    # --- Implementation of abstract methods from the Base class ---
    # Unused methods
    async def _parse_order_book_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "code" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["product_id"])
            order_book_message: OrderBookMessage = CoinbaseAdvancedTradeOrderBook._market_trades_order_book_message(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "code" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["product_id"])
            order_book_message: OrderBookMessage = CoinbaseAdvancedTradeOrderBook._level2_order_book_message(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]):
        channel = ""
        if event_message and "channel" in event_message:
            if "events" in event_message:
                event_type = event_message.get("channel")
                if event_type in ["level2", "market_trades"]:
                    channel = (self._diff_messages_queue_key if event_type == constants.WS_ORDER_SUBSCRIPTION_CHANNELS.inverse["order_book_diff"]
                               else self._trade_messages_queue_key)
                return channel
