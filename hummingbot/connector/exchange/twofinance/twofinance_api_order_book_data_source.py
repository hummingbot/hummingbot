import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.twofinance import (
    twofinance_constants as CONSTANTS,
    twofinance_web_utils as web_utils,
)
from hummingbot.connector.exchange.twofinance.twofinance_matchengine_schemas import MatchEngineEvent
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class TwoFinanceAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        ws_url: Optional[str] = None,
        rest_url: Optional[str] = None,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws_url = ws_url
        self._rest_url = rest_url.rstrip("/") if rest_url is not None else None

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        prices: Dict[str, float] = {}
        for trading_pair in trading_pairs:
            snapshot = await self._request_snapshot(trading_pair)
            bids = snapshot.get("bids") or []
            asks = snapshot.get("asks") or []
            bid = float(bids[0][0] if isinstance(bids[0], list) else bids[0]["price"]) if bids else None
            ask = float(asks[0][0] if isinstance(asks[0], list) else asks[0]["price"]) if asks else None
            if bid is not None and ask is not None:
                prices[trading_pair] = (bid + ask) / 2
            elif bid is not None:
                prices[trading_pair] = bid
            elif ask is not None:
                prices[trading_pair] = ask
        return prices

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event = MatchEngineEvent.from_payload(raw_message)
        message_queue.put_nowait(
            OrderBookMessage(
                OrderBookMessageType.TRADE,
                {
                    "trading_pair": web_utils.normalize_trading_pair(event.market or raw_message.get("trading_pair")),
                    "trade_type": 1.0 if str(event.payload.get("side", "BUY")).upper() == "BUY" else 2.0,
                    "trade_id": int(event.payload.get("trade_id") or event.sequence),
                    "update_id": event.sequence,
                    "price": str(event.payload.get("price") or "0"),
                    "amount": str(event.payload.get("quantity") or event.payload.get("amount") or "0"),
                },
                self._timestamp(event),
            )
        )

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event = MatchEngineEvent.from_payload(raw_message)
        message_queue.put_nowait(
            OrderBookMessage(
                OrderBookMessageType.DIFF,
                {
                    "trading_pair": web_utils.normalize_trading_pair(event.market or raw_message.get("trading_pair")),
                    "update_id": event.sequence,
                    "bids": self._levels(event.payload.get("bids") or []),
                    "asks": self._levels(event.payload.get("asks") or []),
                },
                self._timestamp(event),
            )
        )

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        event = MatchEngineEvent.from_payload(raw_message)
        payload = {
            **event.payload,
            "sequence": event.sequence,
            "market": web_utils.normalize_trading_pair(event.market),
        }
        message_queue.put_nowait(self._snapshot_message(payload))

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        payload = await self._request_snapshot(trading_pair)
        payload.setdefault("trading_pair", trading_pair)
        return self._snapshot_message(payload)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.wss_url(self._domain, self._ws_url), ping_timeout=30)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        await ws.send(
            WSJSONRequest(
                payload=self._subscription_payload("subscribe", self._trading_pairs)
            )
        )

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning("Cannot subscribe: WebSocket connection not established")
            return False
        try:
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload=self._subscription_payload("subscribe", [trading_pair])
                )
            )
            self.add_trading_pair(trading_pair)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error subscribing to 2Finance market data for {trading_pair}.")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning("Cannot unsubscribe: WebSocket connection not established")
            return False
        try:
            await self._ws_assistant.send(
                WSJSONRequest(
                    payload=self._subscription_payload("unsubscribe", [trading_pair])
                )
            )
            self.remove_trading_pair(trading_pair)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error unsubscribing from 2Finance market data for {trading_pair}.")
            return False

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        event_type = str(event_message.get("event_type") or event_message.get("type") or "")
        if event_type in {"TRADE", "TRADE_EXECUTED", "ORDER_TRADE"}:
            return self._trade_messages_queue_key
        if event_type in {"ORDER_BOOK_SNAPSHOT", "BOOK_SNAPSHOT"}:
            return self._snapshot_messages_queue_key
        if event_type in {"ORDER_BOOK_DIFF", "BOOK_DIFF", "LEVEL_UPDATED"}:
            return self._diff_messages_queue_key
        return ""

    async def _request_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        rest = await self._api_factory.get_rest_assistant()
        path = CONSTANTS.ORDER_BOOK_PATH_URL.format(trading_pair=web_utils.exchange_trading_pair(trading_pair))
        url = f"{self._rest_url}{path}" if self._rest_url is not None else web_utils.public_rest_url(path, self._domain)
        payload = await rest.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
        )
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        return payload if isinstance(payload, dict) else {}

    def _snapshot_message(self, payload: Dict[str, Any]) -> OrderBookMessage:
        update_id = int(payload.get("sequence") or payload.get("update_id") or 0)
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": web_utils.normalize_trading_pair(payload.get("trading_pair") or payload.get("market")),
                "update_id": update_id,
                "bids": self._levels(payload.get("bids") or []),
                "asks": self._levels(payload.get("asks") or []),
            },
            float(payload.get("timestamp") or time.time()),
        )

    @staticmethod
    def _levels(levels: List[Any]) -> List[List[str]]:
        normalized = []
        for level in levels:
            if isinstance(level, dict):
                normalized.append([str(level.get("price")), str(level.get("quantity") or level.get("amount"))])
            elif isinstance(level, (list, tuple)) and len(level) >= 2:
                normalized.append([str(level[0]), str(level[1])])
        return normalized

    @staticmethod
    def _timestamp(event: MatchEngineEvent) -> float:
        if event.timestamp_ns is not None:
            return event.timestamp_ns / 1_000_000_000
        return float(event.payload.get("timestamp") or time.time())

    def _subscription_payload(self, method: str, trading_pairs: List[str]) -> Dict[str, Any]:
        params: List[str] = []
        for trading_pair in trading_pairs:
            symbol_id = self._symbol_id_for_pair(trading_pair)
            params.extend([f"{symbol_id}@BOOK", f"{symbol_id}@TRADE", f"{symbol_id}@LEVEL"])
        return {"method": method, "params": params}

    def _symbol_id_for_pair(self, trading_pair: str) -> int:
        metadata = getattr(self._connector, "_symbol_metadata", {}).get(trading_pair, {})
        symbol_id = metadata.get("symbol_id")
        if symbol_id is None:
            raise KeyError(f"missing 2Finance symbol_id for {trading_pair}")
        return int(symbol_id)
