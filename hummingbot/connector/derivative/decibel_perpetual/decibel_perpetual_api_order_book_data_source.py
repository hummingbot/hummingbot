import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils import rest_url
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class DecibelPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        # Best-effort: Decibel exposes all-market prices via REST.
        domain = domain or self._domain
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=rest_url(CONSTANTS.MARKET_PRICES_PATH_URL, domain=domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.MARKET_PRICES_PATH_URL,
            is_auth_required=True,
        )
        prices = response if isinstance(response, list) else response.get("data", [])
        result: Dict[str, float] = {}
        for item in prices:
            market_name = item.get("market_name") or item.get("market") or item.get("symbol")
            if market_name is None:
                continue
            pair = self._connector.convert_from_exchange_trading_pair(market_name)
            if pair in trading_pairs:
                price = item.get("mark_price") or item.get("markPrice") or item.get("price") or 0
                result[pair] = float(price)
        return result

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        market_addr = await self._connector.market_address_associated_to_pair(trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            url=rest_url(CONSTANTS.DEPTH_PATH_URL, domain=self._domain),
            method=RESTMethod.GET,
            params={"market_addr": market_addr},
            throttler_limit_id=CONSTANTS.DEPTH_PATH_URL,
            is_auth_required=True,
        )

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        data = snapshot.get("data", snapshot)
        ts_ms = data.get("timestamp") or data.get("transaction_unix_ms") or int(time.time() * 1000)
        bids = data.get("bids") or []
        asks = data.get("asks") or []
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": int(data.get("sequence") or ts_ms),
                "bids": [[float(p), float(s)] for p, s in bids],
                "asks": [[float(p), float(s)] for p, s in asks],
            },
            timestamp=float(ts_ms) / 1000.0,
        )

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        # Funding is available via market_price topic; REST equivalent is not currently used.
        # Return a safe default; the FundingInfoUpdate stream will keep it up to date.
        last_price = await self._connector.get_last_traded_price(trading_pair)
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=float(last_price),
            mark_price=float(last_price),
            next_funding_utc_timestamp=0,
            rate=0.0,
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        ws_headers = self._connector.authenticator.ws_headers
        await ws.connect(
            ws_url=CONSTANTS.WS_URLS[self._domain],
            ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL,
            ws_headers=ws_headers,
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        for trading_pair in self._trading_pairs:
            market_addr = await self._connector.market_address_associated_to_pair(trading_pair)
            topics = [
                f"{CONSTANTS.WS_DEPTH_TOPIC_PREFIX}:{market_addr}",
                f"{CONSTANTS.WS_TRADES_TOPIC_PREFIX}:{market_addr}",
                f"{CONSTANTS.WS_MARKET_PRICE_TOPIC_PREFIX}:{market_addr}",
            ]
            for topic in topics:
                await ws.send(WSJSONRequest(payload={"method": "subscribe", "topic": topic}))

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        topic = event_message.get("topic", "")
        if topic.startswith(f"{CONSTANTS.WS_DEPTH_TOPIC_PREFIX}:"):
            return self._diff_messages_queue_key
        if topic.startswith(f"{CONSTANTS.WS_TRADES_TOPIC_PREFIX}:"):
            return self._trade_messages_queue_key
        if topic.startswith(f"{CONSTANTS.WS_MARKET_PRICE_TOPIC_PREFIX}:") or topic == CONSTANTS.WS_ALL_MARKET_PRICES_TOPIC:
            return self._funding_info_messages_queue_key
        return ""

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        topic: str = raw_message.get("topic", "")
        data = raw_message.get("data")
        if not topic.startswith(f"{CONSTANTS.WS_TRADES_TOPIC_PREFIX}:") or data is None:
            return
        market_addr = topic.split(":", 1)[1]
        trading_pair = await self._connector.trading_pair_associated_to_market_address(market_addr)
        if trading_pair is None:
            return
        trades = data if isinstance(data, list) else [data]
        for trade in trades:
            ts_ms = trade.get("transaction_unix_ms") or trade.get("timestamp") or int(time.time() * 1000)
            msg = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content={
                    "trading_pair": trading_pair,
                    "trade_type": 1.0 if str(trade.get("side", "")).lower() == "buy" else 2.0,
                    "trade_id": trade.get("trade_id") or trade.get("id") or int(ts_ms),
                    "update_id": int(ts_ms),
                    "price": float(trade.get("price", 0)),
                    "amount": float(trade.get("size", trade.get("qty", 0))),
                },
                timestamp=float(ts_ms) / 1000.0,
            )
            await message_queue.put(msg)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        topic: str = raw_message.get("topic", "")
        data = raw_message.get("data")
        if not topic.startswith(f"{CONSTANTS.WS_DEPTH_TOPIC_PREFIX}:") or data is None:
            return
        market_addr = topic.split(":", 1)[1].split(":", 1)[0]
        trading_pair = await self._connector.trading_pair_associated_to_market_address(market_addr)
        if trading_pair is None:
            return
        ts_ms = data.get("transaction_unix_ms") or data.get("timestamp") or int(time.time() * 1000)
        update_id = int(data.get("sequence") or ts_ms)
        bids = data.get("bids") or []
        asks = data.get("asks") or []
        msg = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": [[float(p), float(s)] for p, s in bids],
                "asks": [[float(p), float(s)] for p, s in asks],
            },
            timestamp=float(ts_ms) / 1000.0,
        )
        await message_queue.put(msg)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Decibel depth stream may send full snapshots; treat them as diffs.
        await self._parse_order_book_diff_message(raw_message, message_queue)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        topic: str = raw_message.get("topic", "")
        data = raw_message.get("data")
        if data is None:
            return
        market_addr: Optional[str] = None
        if topic.startswith(f"{CONSTANTS.WS_MARKET_PRICE_TOPIC_PREFIX}:"):
            market_addr = topic.split(":", 1)[1]
        if market_addr is None:
            return
        trading_pair = await self._connector.trading_pair_associated_to_market_address(market_addr)
        if trading_pair is None:
            return
        info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=float(data.get("oracle_price", data.get("index_price", 0)) or 0),
            mark_price=float(data.get("mark_price", 0) or 0),
            next_funding_utc_timestamp=int(data.get("next_funding_unix_s", data.get("next_funding_utc_timestamp", 0)) or 0),
            rate=float(data.get("funding_rate", data.get("funding_rate_bps", 0)) or 0),
        )
        await message_queue.put(info)

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if trading_pair not in self._trading_pairs:
            self._trading_pairs.append(trading_pair)
        return True

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if trading_pair in self._trading_pairs:
            self._trading_pairs.remove(trading_pair)
        return True
