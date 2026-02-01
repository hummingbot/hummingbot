import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.evedex import evedex_constants as CONSTANTS
from hummingbot.connector.exchange.evedex.evedex_order_book import EvedexOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.logger import HummingbotLogger


class EvedexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        api_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__(trading_pairs)
        self._domain = domain
        self._api_factory = api_factory
        self._message_id = 1
        self._ws_assistant: Optional[WSAssistant] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._get_last_traded_prices(trading_pairs=trading_pairs)

    async def _get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        results = {}
        # Fetch all tickers or iterate
        # Assuming we can fetch all or per instrument.
        # CONSTANTS.INSTRUMENTS_PATH_URL might return all
        try:
            response = await rest_assistant.execute_request(
                url=f"{CONSTANTS.REST_URL}{CONSTANTS.INSTRUMENTS_PATH_URL}",
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.INSTRUMENTS_PATH_URL,
            )
            data = await response.json()
            for instrument in data:
                # instrument['name'] e.g. "ETH-USD"
                # Map back to HB trading pair if possible, or just use if matches
                if instrument["name"] in trading_pairs:
                    results[instrument["name"]] = float(instrument["lastPrice"])
        except Exception:
            self.logger().exception("Failed to fetch last traded prices")
        
        return results

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            # Query: ?instrument=ETH-USD&maxLevel=50
            params = {
                "instrument": trading_pair,
                "maxLevel": 50
            }
            response = await rest_assistant.execute_request(
                url=f"{CONSTANTS.REST_URL}{CONSTANTS.ORDER_BOOK_PATH_URL}",
                params=params,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
            )
            return await response.json()
        except Exception:
            self.logger().exception(f"Failed to fetch order book snapshot for {trading_pair}")
            return {}

    async def listen_for_subscriptions(self):
        while True:
            try:
                self._ws_assistant = await self._api_factory.get_ws_assistant()
                await self._ws_assistant.connect(ws_url=CONSTANTS.WSS_URL, ping_timeout=CONSTANTS.WS_PING_TIMEOUT)
                
                # Centrifuge Connect Handshake
                connect_payload = {
                    "id": self._get_next_message_id(),
                    "method": "connect",
                    "params": {} 
                }
                await self._ws_assistant.send(WSRequest(payload=connect_payload))

                # Wait for connect response? For now, assume optimistic subscription
                # In robust impl, wait for 'result' with client ID.

                # Subscribe to channels
                for trading_pair in self._trading_pairs:
                    # Using trading pair as symbol directly for now
                    subscribe_payload = {
                        "id": self._get_next_message_id(),
                        "method": "subscribe",
                        "params": {
                            "channel": f"order:book:{trading_pair}" 
                        }
                    }
                    await self._ws_assistant.send(WSRequest(payload=subscribe_payload))
                    
                    trades_payload = {
                        "id": self._get_next_message_id(),
                        "method": "subscribe",
                        "params": {
                            "channel": f"trades:{trading_pair}"
                        }
                    }
                    await self._ws_assistant.send(WSRequest(payload=trades_payload))
                
                await self._process_websocket_messages(websocket_assistant=self._ws_assistant)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error occurred when listening to order book streams.")
                await self._sleep(1.0)
            finally:
                if self._ws_assistant and self._ws_assistant.connected:
                    await self._ws_assistant.disconnect()

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            
            # Centrifuge Ping (empty object)
            if data == {}:
                await websocket_assistant.send(WSRequest(payload={}))
                continue

            # Handle Push
            if "push" in data:
                push = data["push"]
                channel = push.get("channel", "")
                pub = push.get("pub", {})
                content = pub.get("data", {})
                
                if channel.startswith("order:book:"):
                    self._process_order_book_update(channel, content)
                elif channel.startswith("trades:"):
                    self._process_trades_update(channel, content)

    def _process_order_book_update(self, channel: str, content: Dict[str, Any]):
        trading_pair = channel.split(":")[-1]
        # Content format: { "bids": [...], "asks": [...], "u": 12345 } 
        # "u" is update ID / sequence
        
        # Check if snapshot or diff. Centrifuge usually pushes diffs after initial state,
        # but here we might treat as snapshots/diffs based on content structure.
        # Assuming content is standard diff format.
        
        timestamp = time.time()
        order_book_message = EvedexOrderBook.diff_message_from_exchange(
            msg=content,
            timestamp=timestamp,
            metadata={"trading_pair": trading_pair, "update_id": content.get("u", int(timestamp*1000))}
        )
        self._message_queue.put_nowait(order_book_message)

    def _process_trades_update(self, channel: str, content: Dict[str, Any]):
        trading_pair = channel.split(":")[-1]
        # content might be a list of trades or single trade
        # { "price": "...", "amount": "...", "side": "...", "id": ... }
        timestamp = time.time()
        
        # Wrap as list if single
        trades = content if isinstance(content, list) else [content]
        
        for trade in trades:
             trade_msg = EvedexOrderBook.trade_message_from_exchange(
                msg=trade,
                timestamp=timestamp,
                metadata={
                    "trading_pair": trading_pair,
                    "trade_type": float(1.0 if trade.get("side") == "buy" else 2.0),
                    "trade_id": trade.get("id"),
                    "update_id": int(timestamp*1000),
                    "price": trade.get("price"),
                    "amount": trade.get("amount")
                }
            )
             self._message_queue.put_nowait(trade_msg)

    def _get_next_message_id(self) -> int:
        mid = self._message_id
        self._message_id += 1
        return mid

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        # Polling for snapshots to ensure consistency
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot = await self._request_order_book_snapshot(trading_pair)
                    timestamp = time.time()
                    if snapshot:
                         order_book_message = EvedexOrderBook.snapshot_message_from_exchange(
                            msg=snapshot,
                            timestamp=timestamp,
                            metadata={"trading_pair": trading_pair, "update_id": snapshot.get("u", int(timestamp*1000))}
                        )
                         output.put_nowait(order_book_message)
                await asyncio.sleep(60.0) # Poll every minute
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error in snapshot polling loop")
                await asyncio.sleep(5.0)
