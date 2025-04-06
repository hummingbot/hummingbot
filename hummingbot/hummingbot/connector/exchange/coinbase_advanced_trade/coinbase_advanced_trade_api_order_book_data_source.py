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

    async def _connected_websocket_assistant(self) -> WSAssistant:
        self._ws_assistant: WSAssistant = await self._api_factory.get_ws_assistant()
        await self._ws_assistant.connect(ws_url=constants.WSS_URL.format(domain=self._domain), max_msg_size=constants.WS_MAX_MSG_SIZE)
        return self._ws_assistant

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

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if raw_message is not None or "code" not in raw_message:
            event_type = raw_message["events"][0]["type"]
            if event_type == "update":
                events = raw_message["events"][0]
                trading_pair = events["trades"][0]["product_id"]
                # TODO: This code needs to be removed when Coinbase DIFF channel is fixed for USDC
                pair = await self.filter_pair(trading_pair)
                trade_message: OrderBookMessage = CoinbaseAdvancedTradeOrderBook.trade_message_from_exchange(
                    raw_message, {"trading_pair": pair})
                self.logger().debug(f"Order book message: {trade_message}")
                message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if raw_message is not None or "code" not in raw_message:
            event_type = raw_message["events"][0]["type"]
            if event_type == "update":
                trading_pair = raw_message["events"][0]["product_id"]
                # TODO: This code needs to be removed when Coinbase DIFF channel is fixed for USDC
                pair = await self.filter_pair(trading_pair)
                order_book_message: OrderBookMessage = CoinbaseAdvancedTradeOrderBook.diff_message_from_exchange(
                    raw_message, time.time(), {"trading_pair": pair})
                self.logger().debug(f"Order book message: {order_book_message}")
                message_queue.put_nowait(order_book_message)

    async def filter_pair(self, trading_pair):
        pairs = []
        for trad_pair in self._trading_pairs:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trad_pair)
            pairs.append(symbol)
        new_pair = ""
        base = trading_pair.split("-")[0]
        for symbol in pairs:
            symbol_base, symbol_quote = symbol.split("-")
            # Check if there's an exact match
            if symbol == trading_pair:
                new_pair = symbol
                break

            elif base == symbol_base and "USD" in symbol_quote:
                new_quote = "USDC"
                proposed_pair = f"{base}-{new_quote}"
                # Only update if the proposed pair exists in pairs
                if proposed_pair in pairs:
                    new_pair = proposed_pair
                    break

        return new_pair

    def _channel_originating_message(self, event_message: Dict[str, Any]):
        channel = ""
        if event_message and "channel" in event_message:
            if "events" in event_message:
                event_type = event_message.get("channel")
                if event_type in ["l2_data", "market_trades"]:
                    channel = (self._diff_messages_queue_key if event_type == constants.WS_ORDER_SUBSCRIPTION_CHANNELS.inverse["order_book_diff"]
                               else self._trade_messages_queue_key)
                return channel
