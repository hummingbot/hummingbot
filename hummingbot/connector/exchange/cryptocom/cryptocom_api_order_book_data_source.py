import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.cryptocom import cryptocom_constants as CONSTANTS, cryptocom_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.cryptocom.cryptocom_exchange import CryptocomExchange


class CryptocomAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "CryptocomExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        params = {
            "instrument_name": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "depth": 150,
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )
        if data.get("code", 0) != 0:
            raise IOError(f"Error requesting Crypto.com order book snapshot: {data}")

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            channels = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                channels.extend([f"trade.{symbol}", f"book.{symbol}.150"])

            payload = {
                "id": int(time.time() * 1e3),
                "method": "subscribe",
                "params": {"channels": channels},
            }
            await ws.send(WSJSONRequest(payload=payload))

            self.logger().info("Subscribed to Crypto.com public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book and trade streams...",
                exc_info=True,
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_PUBLIC_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response = await self._request_order_book_snapshot(trading_pair)
        data = snapshot_response.get("result", {}).get("data", [])
        snapshot_data = data[0] if len(data) > 0 else {}

        snapshot_msg = self.snapshot_message_from_exchange(
            snapshot_data,
            metadata={"trading_pair": trading_pair},
        )
        return snapshot_msg

    def snapshot_message_from_exchange(
        self,
        msg: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        payload = dict(msg)
        if metadata:
            payload.update(metadata)

        update_id = int(payload.get("t", int(time.time() * 1e3)))
        bids = payload.get("bids") or payload.get("b") or []
        asks = payload.get("asks") or payload.get("a") or []

        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": payload["trading_pair"],
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            },
            timestamp=update_id * 1e-3,
        )

    def trade_message_from_exchange(self, msg: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> OrderBookMessage:
        payload = dict(msg)
        if metadata:
            payload.update(metadata)

        side = str(payload.get("s", "")).upper()
        trade_type = float(TradeType.BUY.value) if side == "BUY" else float(TradeType.SELL.value)
        trade_id = payload.get("d") or payload.get("id") or payload.get("t")
        timestamp_ms = int(payload.get("t", int(time.time() * 1e3)))

        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": payload["trading_pair"],
                "trade_type": trade_type,
                "trade_id": trade_id,
                "update_id": timestamp_ms,
                "price": payload.get("p"),
                "amount": payload.get("q"),
            },
            timestamp=timestamp_ms * 1e-3,
        )

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        result = raw_message.get("result", {})
        channel = str(result.get("channel", ""))
        symbol = channel.split(".", 1)[1] if "." in channel else ""
        if not symbol:
            return
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)

        for trade in result.get("data", []):
            trade_message = self.trade_message_from_exchange(trade, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        result = raw_message.get("result", {})
        channel = str(result.get("channel", ""))
        parts = channel.split(".")
        if len(parts) < 2:
            return
        symbol = parts[1]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)

        data = result.get("data", [])
        if len(data) == 0:
            return

        snapshot_message = self.snapshot_message_from_exchange(data[0], {"trading_pair": trading_pair})
        message_queue.put_nowait(snapshot_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        result = event_message.get("result", {})
        channel = str(result.get("channel", ""))
        if channel.startswith("book."):
            return self._diff_messages_queue_key
        if channel.startswith("trade."):
            return self._trade_messages_queue_key
        return ""

    async def _process_message_for_unknown_channel(self, event_message: Dict[str, Any], websocket_assistant: WSAssistant):
        if event_message.get("method") == "public/heartbeat":
            await websocket_assistant.send(WSJSONRequest(payload={"id": event_message.get("id"), "method": "public/respond-heartbeat"}))
