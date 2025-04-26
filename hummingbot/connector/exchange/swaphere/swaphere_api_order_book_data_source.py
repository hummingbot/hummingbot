import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.swaphere import swaphere_constants as CONSTANTS
from hummingbot.connector.exchange.swaphere.swaphere_web_utils import api_request
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class SwaphereAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None
    
    def __init__(
        self,
        trading_pairs: List[str] = None,
        web_assistants_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__(trading_pairs)
        self._web_assistants_factory = web_assistants_factory or WebAssistantsFactory()
        self._ws_assistant: Optional[WSAssistant] = None
        
    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger
        
    async def get_snapshot(
        self, 
        trading_pair: str, 
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Get current order book snapshot for a trading pair
        :param trading_pair: the trading pair to get snapshot for
        :param limit: the number of asks/bids to get
        :return: snapshot data in dictionary format
        """
        params = {
            "instId": trading_pair,
            "sz": limit,
        }
        snapshot = await api_request(
            path=CONSTANTS.SWAPHERE_ORDER_BOOK_PATH,
            api_factory=self._web_assistants_factory,
            params=params,
        )
        return snapshot
        
    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """
        Creates a new order book with snapshot data for a trading pair
        :param trading_pair: the trading pair to create order book for
        :return: a new order book
        """
        snapshot = await self.get_snapshot(trading_pair, 1000)
        snapshot_timestamp = int(snapshot.get("ts", time.time() * 1000))
        snapshot_msg = OrderBookMessage(
            OrderBookMessage.MESSAGE_TYPE_SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": snapshot_timestamp,
                "bids": snapshot.get("bids", []),
                "asks": snapshot.get("asks", []),
            },
            timestamp=snapshot_timestamp * 1e-3,
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book
        
    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates a websocket assistant and connects it to the exchange
        :return: a websocket assistant
        """
        if self._ws_assistant is None:
            self._ws_assistant = await self._web_assistants_factory.get_ws_assistant()
            await self._ws_assistant.connect(
                ws_url=CONSTANTS.SWAPHERE_WS_URI_PUBLIC,
                ping_timeout=30,
            )
        return self._ws_assistant
        
    async def listen_for_subscriptions(self):
        """
        Subscribe to order book and trade channels for all trading pairs
        """
        ws = await self._connected_websocket_assistant()
        for trading_pair in self._trading_pairs:
            orderbook_subscription = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": CONSTANTS.SWAPHERE_WS_PUBLIC_BOOKS_CHANNEL,
                        "instId": trading_pair,
                    },
                ],
            }
            trades_subscription = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": CONSTANTS.SWAPHERE_WS_PUBLIC_TRADES_CHANNEL,
                        "instId": trading_pair,
                    },
                ],
            }
            
            orderbook_request = WSJSONRequest(payload=orderbook_subscription)
            trades_request = WSJSONRequest(payload=trades_subscription)
            
            await ws.send(orderbook_request)
            await ws.send(trades_request)
            
            self.logger().info(f"Subscribed to public orderbook and trade channels for {trading_pair}")
            
    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Listen for order book diffs from websocket
        :param ev_loop: the event loop
        :param output: a queue to put the diffs into
        """
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self.listen_for_subscriptions()
                
                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if data.get("arg", {}).get("channel") == CONSTANTS.SWAPHERE_WS_PUBLIC_BOOKS_CHANNEL:
                        trading_pair = data.get("arg", {}).get("instId")
                        timestamp = int(data.get("data", [{}])[0].get("ts", time.time() * 1000))
                        
                        order_book_message = OrderBookMessage(
                            OrderBookMessage.MESSAGE_TYPE_DIFF,
                            {
                                "trading_pair": trading_pair,
                                "update_id": timestamp,
                                "bids": data.get("data", [{}])[0].get("bids", []),
                                "asks": data.get("data", [{}])[0].get("asks", []),
                            },
                            timestamp=timestamp * 1e-3,
                        )
                        
                        output.put_nowait(order_book_message)
                        
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error listening for order book diffs. Retrying after 5 seconds...",
                                  exc_info=True)
                await asyncio.sleep(5)
                
    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Listen for trade updates from websocket
        :param ev_loop: the event loop
        :param output: a queue to put the trade messages into
        """
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self.listen_for_subscriptions()
                
                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if data.get("arg", {}).get("channel") == CONSTANTS.SWAPHERE_WS_PUBLIC_TRADES_CHANNEL:
                        for trade_data in data.get("data", []):
                            trading_pair = data.get("arg", {}).get("instId")
                            timestamp = int(trade_data.get("ts", time.time() * 1000))
                            
                            trade_message = OrderBookMessage(
                                OrderBookMessage.MESSAGE_TYPE_TRADE,
                                {
                                    "trading_pair": trading_pair,
                                    "trade_id": trade_data.get("tradeId"),
                                    "trade_type": float(trade_data.get("side", "buy") == "buy"),
                                    "amount": float(trade_data.get("sz", "0")),
                                    "price": float(trade_data.get("px", "0")),
                                },
                                timestamp=timestamp * 1e-3,
                            )
                            
                            output.put_nowait(trade_message)
                            
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error listening for trades. Retrying after 5 seconds...",
                                  exc_info=True)
                await asyncio.sleep(5) 