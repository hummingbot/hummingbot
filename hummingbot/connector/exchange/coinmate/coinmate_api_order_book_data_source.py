import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.coinmate import (
    coinmate_constants as CONSTANTS,
    coinmate_web_utils as web_utils
)
from hummingbot.connector.exchange.coinmate.coinmate_order_book import (
    CoinmateOrderBook
)
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import (
    OrderBookTrackerDataSource
)
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    WSJSONRequest
)
from hummingbot.core.web_assistant.web_assistants_factory import (
    WebAssistantsFactory
)
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinmate.coinmate_exchange import (
        CoinmateExchange
    )


class CoinmateAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "CoinmateExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory
    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        coinmate_symbol = web_utils.convert_to_exchange_trading_pair(
            trading_pair
        )
        params = {
            "currencyPair": coinmate_symbol,
            "groupByPriceLimit": "False"
        }
            
        rest_assistant = await self._api_factory.get_rest_assistant()
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.ORDERBOOK_PATH_URL, 
            domain=self._domain
        )
        data = await rest_assistant.execute_request(
                    url=url,
                    params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.GLOBAL_RATE_LIMIT_ID,
            headers={"Content-Type": "application/json"}
        )

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                coinmate_symbol = web_utils.convert_to_exchange_trading_pair(
                    trading_pair
                )
                
                orderbook_payload = {
                    "event": "subscribe",
                    "data": {
                        "channel": f"order_book-{coinmate_symbol}"
                    }
                }
                subscribe_orderbook_request = WSJSONRequest(payload=orderbook_payload)
                
                trades_payload = {
                    "event": "subscribe", 
                    "data": {
                        "channel": f"trades-{coinmate_symbol}"
                    }
                }
                subscribe_trades_request = WSJSONRequest(payload=trades_payload)
                
                await ws.send(subscribe_orderbook_request)
                await ws.send(subscribe_trades_request)
            
            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and "
                "delta streams...",
                exc_info=True
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL,
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        
        if response.get("error") is False and "data" in response:
            snapshot_data = response["data"]
        else:
            raise ValueError(f"Invalid order book response: {response}")
        
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = (
            CoinmateOrderBook.snapshot_message_from_exchange(
                snapshot_data,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], 
                                   message_queue: asyncio.Queue):
        if (raw_message.get("event") == "data" and 
            "trades" in raw_message.get("channel", "")):
            channel = raw_message.get("channel", "")
            if "-" in channel:
                coinmate_symbol = channel.split("-", 1)[1]
                trading_pair = web_utils.convert_from_exchange_trading_pair(
                    coinmate_symbol
                )
                
                data = raw_message.get("payload", raw_message.get("data", []))
                self.logger().debug(
                    f"Processing trade message for {trading_pair}: {data}"
                )
                
                for trade_data in data:
                    trade_message = CoinmateOrderBook.trade_message_from_exchange(
                        trade_data, 
                        timestamp=float(trade_data.get("date", time.time())), 
                        metadata={"trading_pair": trading_pair}
                    )
                    message_queue.put_nowait(trade_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], 
                                                 message_queue: asyncio.Queue):
        if (raw_message.get("event") == "data" and 
            "order_book" in raw_message.get("channel", "")):
            channel = raw_message.get("channel", "")
            if "-" in channel:
                coinmate_symbol = channel.split("-", 1)[1]
                trading_pair = web_utils.convert_from_exchange_trading_pair(
                    coinmate_symbol
                )
                
                data = raw_message.get("payload", raw_message.get("data", {}))
                self.logger().debug(
                    f"Processing order book snapshot for {trading_pair}: {data}"
                )
                order_book_message: OrderBookMessage = (
                    CoinmateOrderBook.snapshot_message_from_exchange(
                        data, 
                        timestamp=time.time(), 
                        metadata={"trading_pair": trading_pair}
                    )
                )
                message_queue.put_nowait(order_book_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], 
                                             message_queue: asyncio.Queue):
        if (raw_message.get("event") == "data" and 
            "order_book" in raw_message.get("channel", "")):
            channel = raw_message.get("channel", "")
            if "-" in channel:
                coinmate_symbol = channel.split("-", 1)[1]
                trading_pair = web_utils.convert_from_exchange_trading_pair(
                    coinmate_symbol
                )
                
                data = raw_message.get("payload", raw_message.get("data", {}))
                self.logger().debug(
                    f"Processing order book diff for {trading_pair}: {data}"
                )
                order_book_message: OrderBookMessage = (
                    CoinmateOrderBook.diff_message_from_exchange(
                        data, 
                        timestamp=time.time(), 
                        metadata={"trading_pair": trading_pair}
                    )
                )
                message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        self.logger().debug(f"Received WebSocket message: {event_message}")
        
        channel = ""
        event = event_message.get("event", "")
        
        if event == "data":
            event_type = event_message.get("channel", "")
            if "order_book" in event_type:
                channel = self._snapshot_messages_queue_key
            elif "trades" in event_type:
                channel = self._trade_messages_queue_key
        elif event == "subscribe_success":
            self.logger().info(
                f"Successfully subscribed to: "
                f"{event_message.get('data', {}).get('channel', 'unknown')}"
            )
        elif event in ["ping", "pong"]:
            self.logger().debug(f"Received {event} from server")
        elif event == "error":
            self.logger().error(
                f"WebSocket error: {event_message.get('message', 'Unknown error')}"
            )
        
        return channel
