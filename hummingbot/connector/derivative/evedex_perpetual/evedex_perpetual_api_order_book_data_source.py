import asyncio
import logging
from typing import Any, Dict, List, Optional

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.core.utils.async_utils import safe_ensure_future
from . import (
    evedex_perpetual_constants as CONSTANTS,
    evedex_perpetual_utils as utils,
    evedex_perpetual_web_utils as web_utils,
)

logger = logging.getLogger(__name__)


class EvedexPerpetualAPIOrderBookDataSource:
    def __init__(
        self,
        trading_pairs: List[str],
        rest_assistant: RESTAssistant,
        ws_assistant: WSAssistant,
        throttler: AsyncThrottler,
        environment: str = "demo",
    ):
        self._trading_pairs = trading_pairs
        self._rest_assistant = rest_assistant
        self._ws_assistant = ws_assistant
        self._throttler = throttler
        self._environment = environment
        self._rest_base = web_utils.get_rest_url(environment)
        self._ws_base = web_utils.get_ws_url(environment)
        self._env_prefix = CONSTANTS.ENV_PREFIX[environment]
        
        self._instruments_cache: Dict[str, Dict] = {}
        self._last_snapshot_timestamp: Dict[str, float] = {}
        self._order_book_diff_queue: asyncio.Queue = asyncio.Queue()
        self._trade_message_queue: asyncio.Queue = asyncio.Queue()
        self._ws_listener_task: Optional[asyncio.Task] = None
        self._ws_connect_lock = asyncio.Lock()
        self._ws_ready = asyncio.Event()
        
    async def get_trading_pairs(self) -> List[str]:
        instruments = await self.get_instruments()
        pairs = []
        
        for instrument_id, info in instruments.items():
            try:
                trading_pair = utils.to_trading_pair(instrument_id)
                pairs.append(trading_pair)
            except Exception as e:
                logger.warning(f"Failed to convert instrument {instrument_id}: {e}")
        
        return pairs
    
    async def get_instruments(self, force_refresh: bool = False) -> Dict[str, Dict]:
        if self._instruments_cache and not force_refresh:
            return self._instruments_cache
        
        url = f"{self._rest_base}{CONSTANTS.ENDPOINTS['instrument_list']}"
        
        params = {"fields": "all"}
        
        try:
            response = await web_utils.api_request(
                rest_assistant=self._rest_assistant,
                method=RESTMethod.GET,
                url=url,
                params=params,
                throttler_limit_id="instrument_list",
            )
            
            instruments = {}
            for item in response.get("instruments", []):
                instrument_id = item.get("instrumentId")
                if instrument_id:
                    instruments[instrument_id] = item
            
            self._instruments_cache = instruments
            logger.info(
                f"Loaded {len(instruments)} instruments with complete metadata"
            )
            return instruments
            
        except Exception as e:
            logger.error(f"Failed to fetch instruments: {e}")
            return self._instruments_cache
    
    async def get_order_book_snapshot(
        self,
        trading_pair: str,
        market_level: int = 20
    ) -> Dict[str, Any]:
        instrument = utils.to_exchange_symbol(trading_pair)
        url = f"{self._rest_base}{CONSTANTS.ENDPOINTS['orderbook_deep'].format(instrument=instrument)}"
        
        params = {"marketLevel": market_level}
        
        try:
            response = await web_utils.api_request(
                rest_assistant=self._rest_assistant,
                method=RESTMethod.GET,
                url=url,
                params=params,
                throttler_limit_id="public",
            )
            
            snapshot_time = response.get("t", 0)
            self._last_snapshot_timestamp[trading_pair] = snapshot_time
            
            return {
                "trading_pair": trading_pair,
                "update_id": snapshot_time,
                "bids": self._parse_order_book_side(response.get("bids", [])),
                "asks": self._parse_order_book_side(response.get("asks", [])),
                "timestamp": snapshot_time / 1000.0,  # Convert ms to s
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch order book snapshot for {trading_pair}: {e}")
            raise
    
    def _parse_order_book_side(self, side_data: List) -> List[List[float]]:
        result = []
        for entry in side_data:
            try:
                if isinstance(entry, list) and len(entry) >= 2:
                    price = float(entry[0])
                    qty = float(entry[1])
                elif isinstance(entry, dict):
                    price = float(entry.get("p", 0))
                    qty = float(entry.get("q", 0))
                else:
                    continue
                
                if price > 0 and qty > 0:
                    result.append([price, qty])
            except (ValueError, TypeError) as e:
                logger.debug(f"Failed to parse order book entry {entry}: {e}")
        
        return result
    
    async def listen_for_order_book_diffs(
        self,
        output: asyncio.Queue
    ) -> None:
        await self._ensure_ws_listener()
        while True:
            try:
                message: OrderBookMessage = await self._order_book_diff_queue.get()
                await output.put(message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Order book diff stream error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def listen_for_trades(self, output: asyncio.Queue) -> None:
        await self._ensure_ws_listener()
        while True:
            try:
                trade_message: OrderBookMessage = await self._trade_message_queue.get()
                await output.put(trade_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Trade stream error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _ensure_ws_listener(self):
        if self._ws_listener_task and not self._ws_listener_task.done():
            await self._ws_ready.wait()
            return
        
        async with self._ws_connect_lock:
            if self._ws_listener_task and not self._ws_listener_task.done():
                await self._ws_ready.wait()
                return
            
            await self._connect_and_subscribe()
            self._ws_listener_task = safe_ensure_future(self._ws_listen_loop())
            await self._ws_ready.wait()
    
    async def _connect_and_subscribe(self):
        self._ws_ready.clear()
        try:
            await self._ws_assistant.connect(
                ws_url=self._ws_base,
                ping_timeout=CONSTANTS.WS_HEARTBEAT_INTERVAL,
            )
        except RuntimeError:
            # Already connected
            pass
        
        await self._subscribe_public_channels()
        self._ws_ready.set()
    
    async def _subscribe_public_channels(self):
        subscribe_requests = []
        
        for trading_pair in self._trading_pairs:
            instrument = utils.to_exchange_symbol(trading_pair)
            diff_channel = CONSTANTS.WS_CHANNELS["orderbook_diff"].format(
                env=self._env_prefix,
                instrument=instrument
            )
            trades_channel = CONSTANTS.WS_CHANNELS["recent_trades"].format(
                env=self._env_prefix,
                instrument=instrument
            )
            
            subscribe_requests.append(diff_channel)
            subscribe_requests.append(trades_channel)
        
        for channel in subscribe_requests:
            subscribe_msg = {
                "method": 1,
                "params": {
                    "channel": channel,
                }
            }
            try:
                await self._ws_assistant.send(WSJSONRequest(payload=subscribe_msg))
                logger.info(f"Subscribed to channel: {channel}")
            except Exception as e:
                logger.error(f"Failed to subscribe to {channel}: {e}")
    
    async def _ws_listen_loop(self):
        while True:
            try:
                async for ws_response in self._ws_assistant.iter_messages():
                    message = ws_response.data
                    if not isinstance(message, dict):
                        continue
                    await self._handle_ws_message(message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"WebSocket listener error: {e}", exc_info=True)
                await asyncio.sleep(CONSTANTS.WS_RECONNECT_DELAY)
                await self._connect_and_subscribe()
            else:
                # Connection closed, attempt reconnection
                await asyncio.sleep(CONSTANTS.WS_RECONNECT_DELAY)
                await self._connect_and_subscribe()
    
    async def _handle_ws_message(self, message: Dict[str, Any]):
        channel = message.get("channel", "")
        data = message.get("data", {})
        
        if not channel or not data:
            return
        
        try:
            if ":orderBook-" in channel:
                diff_message = self._build_order_book_diff(channel, data)
                if diff_message:
                    self._order_book_diff_queue.put_nowait(diff_message)
            elif ":recent-trade-" in channel:
                trade_message = self._build_trade_message(channel, data)
                if trade_message:
                    self._trade_message_queue.put_nowait(trade_message)
        except Exception as e:
            logger.error(f"Failed to process WebSocket message: {e}", exc_info=True)
    
    def _build_order_book_diff(self, channel: str, data: Dict[str, Any]) -> Optional[OrderBookMessage]:
        instrument = channel.split(":orderBook-")[1].split("-")[0]
        trading_pair = utils.to_trading_pair(instrument)
        update_id = data.get("t", 0)
        
        if update_id == 0:
            return None
        
        return OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": self._parse_order_book_side(data.get("bids", [])),
                "asks": self._parse_order_book_side(data.get("asks", [])),
                "timestamp": update_id / 1000.0,
            },
            timestamp=update_id / 1000.0,
        )
    
    def _build_trade_message(self, channel: str, data: Dict[str, Any]) -> Optional[OrderBookMessage]:
        instrument = channel.split(":recent-trade-")[1]
        trading_pair = utils.to_trading_pair(instrument)
        
        trade_id = data.get("tradeId")
        timestamp = data.get("t", 0)
        if trade_id is None or timestamp == 0:
            return None
        
        price = float(data.get("price", 0))
        quantity = float(data.get("quantity", 0))
        side = data.get("side", "").lower()
        
        return OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": trading_pair,
                "trade_id": trade_id,
                "price": price,
                "amount": quantity,
                "trade_type": side,
                "timestamp": timestamp / 1000.0,
            },
            timestamp=timestamp / 1000.0,
        )
