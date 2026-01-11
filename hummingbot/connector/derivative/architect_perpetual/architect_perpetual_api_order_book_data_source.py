import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class ArchitectPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "ArchitectPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = {}
        self._ws_assistant: Optional[WSAssistant] = None

    @property
    def funding_info_stream_name(self) -> str:
        return "funding_info"

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_data = await self._connector.get_order_book_snapshot(trading_pair)
        timestamp = snapshot_data.get("timestamp", 0)
        update_id = snapshot_data.get("sequence", int(timestamp * 1000))
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": snapshot_data.get("bids", []),
                "asks": snapshot_data.get("asks", []),
            },
            timestamp=timestamp,
        )

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue) -> None:
        trade_data = raw_message.get("data", raw_message)
        trading_pair = trade_data.get("symbol", "")
        if "/" in trading_pair:
            trading_pair = web_utils.convert_from_exchange_trading_pair(trading_pair)
        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": trading_pair,
                "trade_id": trade_data.get("id", str(trade_data.get("timestamp", 0))),
                "update_id": trade_data.get("sequence", 0),
                "price": str(trade_data.get("price", 0)),
                "amount": str(trade_data.get("size", trade_data.get("quantity", 0))),
                "trade_type": float(TradeType.BUY.value) if trade_data.get("side", "").upper() == "BUY" else float(TradeType.SELL.value),
            },
            timestamp=trade_data.get("timestamp", 0),
        )
        await message_queue.put(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue) -> None:
        data = raw_message.get("data", raw_message)
        trading_pair = data.get("symbol", "")
        if "/" in trading_pair:
            trading_pair = web_utils.convert_from_exchange_trading_pair(trading_pair)
        is_snapshot = data.get("type") == "snapshot" or "full" in str(raw_message.get("type", "")).lower()
        message_type = OrderBookMessageType.SNAPSHOT if is_snapshot else OrderBookMessageType.DIFF
        order_book_message = OrderBookMessage(
            message_type=message_type,
            content={
                "trading_pair": trading_pair,
                "update_id": data.get("sequence", int(data.get("timestamp", 0) * 1000)),
                "bids": data.get("bids", []),
                "asks": data.get("asks", []),
            },
            timestamp=data.get("timestamp", 0),
        )
        await message_queue.put(order_book_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue) -> None:
        data = raw_message.get("data", raw_message)
        trading_pair = data.get("symbol", "")
        if "/" in trading_pair:
            trading_pair = web_utils.convert_from_exchange_trading_pair(trading_pair)
        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=Decimal(str(data.get("index_price", 0))),
            mark_price=Decimal(str(data.get("mark_price", 0))),
            next_funding_utc_timestamp=int(data.get("next_funding_time", 0)),
            rate=Decimal(str(data.get("funding_rate", 0))),
        )
        await message_queue.put(funding_info)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        if self._ws_assistant is None or not self._ws_assistant.is_connected:
            ws_url = web_utils.wss_url(self._domain)
            self._ws_assistant = await self._api_factory.get_ws_assistant()
            await self._ws_assistant.connect(ws_url=ws_url)
        return self._ws_assistant

    async def _subscribe_channels(self, ws: WSAssistant) -> None:
        try:
            for trading_pair in self._trading_pairs:
                exchange_symbol = self._connector.exchange_symbol_for_tokens(trading_pair)
                await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": "orderbook", "symbol": exchange_symbol}))
                await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": "trades", "symbol": exchange_symbol}))
                self.logger().info(f"Subscribed to orderbook and trades for {trading_pair}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error subscribing to channels: {e}")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue) -> None:
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if isinstance(data, dict):
                channel = data.get("channel", data.get("type", ""))
                if channel == "orderbook" or "book" in channel.lower():
                    await self._parse_order_book_diff_message(data, queue)
                elif channel == "trades" or "trade" in channel.lower():
                    await self._parse_trade_message(data, queue)
                elif channel == "funding" or "funding" in channel.lower():
                    await self._parse_funding_info_message(data, queue)

    async def listen_for_subscriptions(self) -> None:
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws, self._message_queue.get("order_book", asyncio.Queue()))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"WebSocket subscription error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            finally:
                if ws:
                    await ws.disconnect()
                    ws = None
                    self._ws_assistant = None

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        return await self._connector.get_funding_info(trading_pair)
