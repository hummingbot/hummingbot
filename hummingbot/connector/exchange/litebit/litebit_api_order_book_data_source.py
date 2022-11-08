#!/usr/bin/env python
import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.exchange.litebit.litebit_constants as constants
from hummingbot.connector.exchange.litebit import litebit_web_utils as web_utils
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

from . import litebit_utils
from .litebit_order_book import LitebitOrderBook

if TYPE_CHECKING:
    from hummingbot.connector.exchange.litebit.litebit_exchange import LitebitExchange


class LitebitAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self, trading_pairs: List[str],
                 connector: 'LitebitExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = constants.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_msg: OrderBookMessage = LitebitOrderBook.trade_message_from_exchange(
            raw_message["data"]
        )
        message_queue.put_nowait(trade_msg)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        order_book_msg: OrderBookMessage = LitebitOrderBook.diff_message_from_exchange(
            raw_message["data"], metadata={"trading_pair": litebit_utils.convert_from_exchange_trading_pair(
                raw_message["data"]["market"]
            )}
        )
        message_queue.put_nowait(order_book_msg)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        snapshot_msg: OrderBookMessage = LitebitOrderBook.snapshot_message_from_exchange(
            raw_message["data"],
            metadata={"trading_pair": litebit_utils.convert_from_exchange_trading_pair(
                raw_message["data"]["market"]
            )}
        )
        message_queue.put_nowait(snapshot_msg)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Get whole orderbook
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        order_book_response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=constants.GET_BOOK_PATH, domain=self._domain),
            params={"market": litebit_utils.convert_to_exchange_trading_pair(trading_pair)},
            method=RESTMethod.GET,
            throttler_limit_id=constants.GET_BOOK_PATH,
        )
        snapshot_msg: OrderBookMessage = LitebitOrderBook.snapshot_message_from_exchange(
            order_book_response,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=constants.WSS_URL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            channels = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                channels.append(f"book:{symbol}")
                channels.append(f"trades:{symbol}")

            payload = {
                "rid": 1,
                "event": "subscribe",
                "data": channels,
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        if event_message["event"] == "book" and event_message["data"]["update_type"] == "delta":
            return self._diff_messages_queue_key
        elif event_message["event"] == "book" and event_message["data"]["update_type"] == "snapshot":
            return self._snapshot_messages_queue_key
        elif event_message["event"] == "trade":
            return self._trade_messages_queue_key
