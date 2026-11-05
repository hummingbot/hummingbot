import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.reya_perpetual import (
    reya_perpetual_constants as CONSTANTS,
    reya_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_derivative import ReyaPerpetualDerivative


class ReyaPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    def __init__(self, trading_pairs: List[str], connector: "ReyaPerpetualDerivative",
                 api_factory: WebAssistantsFactory, domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._last_update_id = 0

    def _next_update_id(self) -> int:
        # Depth frames carry no sequence number. Ids are assigned in arrival order, so the
        # order book tracker applies each diff after the snapshot that preceded it.
        self._last_update_id = max(self._last_update_id + 1, time.time_ns())
        return self._last_update_id

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        summary = await self._connector._api_get(path_url=CONSTANTS.MARKET_SUMMARY_PATH.format(symbol=symbol))
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(summary["oraclePrice"]),
            mark_price=Decimal(summary["markPrice"]),
            next_funding_utc_timestamp=0,  # Funding accrues continuously, with no scheduled settlement.
            rate=Decimal(summary["fundingRate"]) / 100,  # The API reports hourly percentage points.
        )

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        update_id = self._next_update_id()
        snapshot = await self._connector._api_get(path_url=CONSTANTS.DEPTH_PATH.format(symbol=symbol),
                                                  params={"limit": CONSTANTS.DEPTH_LEVELS})
        return self._book_message(OrderBookMessageType.SNAPSHOT, trading_pair, snapshot, update_id)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.wss_url(self._domain))
        return ws

    def _channels(self, symbol: str) -> List[str]:
        return [f"/v2/market/{symbol}/depth", f"/v2/market/{symbol}/perpExecutions",
                f"/v2/perpMarket/{symbol}/summary"]

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
                for channel in self._channels(symbol):
                    await ws.send(WSJSONRequest(payload={"type": "subscribe", "channel": channel}))
            self.logger().info("Subscribed to public order book, trade and funding channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams.")
            raise

    async def _subscribe_or_unsubscribe(self, trading_pair: str, operation: str) -> bool:
        if self._ws_assistant is None:
            return False
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        for channel in self._channels(symbol):
            await self._ws_assistant.send(WSJSONRequest(payload={"type": operation, "channel": channel}))
        return True

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        subscribed = await self._subscribe_or_unsubscribe(trading_pair, "subscribe")
        if subscribed:
            self.add_trading_pair(trading_pair)
        return subscribed

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        unsubscribed = await self._subscribe_or_unsubscribe(trading_pair, "unsubscribe")
        if unsubscribed:
            self.remove_trading_pair(trading_pair)
        return unsubscribed

    @staticmethod
    def _payload(message: Dict[str, Any]) -> Any:
        return message.get("contents") if message.get("type") == "subscribed" else message.get("data")

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        message_type = event_message.get("type")
        channel = event_message.get("channel", "")
        if message_type == "error":
            self.logger().warning(f"Reya rejected subscription {channel}: {event_message.get('message')}")
            return ""
        if message_type not in ("subscribed", "channel_data"):
            return ""
        if channel.endswith("/depth"):
            payload = self._payload(event_message) or {}
            event_message["update_id"] = self._next_update_id()
            if payload.get("type") == "SNAPSHOT":
                return self._snapshot_messages_queue_key
            return self._diff_messages_queue_key
        if channel.endswith("/perpExecutions") and message_type == "channel_data":
            # The subscription acknowledgement replays recent trades; only new ones are emitted.
            return self._trade_messages_queue_key
        if channel.endswith("/summary"):
            return self._funding_info_messages_queue_key
        return ""

    async def _book_message_from_event(self, message_type: OrderBookMessageType, raw_message: Dict[str, Any],
                                       message_queue: asyncio.Queue):
        depth = self._payload(raw_message)
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(depth["symbol"])
        message_queue.put_nowait(self._book_message(message_type, trading_pair, depth, raw_message["update_id"]))

    @staticmethod
    def _book_message(message_type: OrderBookMessageType, trading_pair: str, depth: Dict[str, Any],
                      update_id: int) -> OrderBookMessage:
        content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [[level["px"], level["qty"]] for level in depth["bids"]],
            "asks": [[level["px"], level["qty"]] for level in depth["asks"]],
        }
        if message_type == OrderBookMessageType.DIFF:
            content["first_update_id"] = update_id
        return OrderBookMessage(message_type, content, depth["updatedAt"] / 1000)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        await self._book_message_from_event(OrderBookMessageType.SNAPSHOT, raw_message, message_queue)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        await self._book_message_from_event(OrderBookMessageType.DIFF, raw_message, message_queue)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        for trade in self._payload(raw_message) or []:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(trade["symbol"])
            message_queue.put_nowait(OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_id": str(trade["sequenceNumber"]),
                "trade_type": float(TradeType.BUY.value if trade["side"] == "B" else TradeType.SELL.value),
                "price": trade["price"],
                "amount": trade["qty"],
            }, trade["timestamp"] / 1000))

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        summary = self._payload(raw_message)
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(summary["symbol"])
        message_queue.put_nowait(FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=Decimal(summary["oraclePrice"]) if summary.get("oraclePrice") is not None else None,
            mark_price=Decimal(summary["markPrice"]),
            next_funding_utc_timestamp=0,
            rate=Decimal(summary["fundingRate"]) / 100,
        ))
