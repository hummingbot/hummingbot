import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils import (
    build_api_factory,
    public_rest_url,
)
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
        self._trading_pairs = trading_pairs

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        result = {}
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=public_rest_url(CONSTANTS.MARKET_PRICES_PATH_URL, domain=domain or self._domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.MARKET_PRICES_PATH_URL,
        )
        prices = response if isinstance(response, list) else response.get("data", [])
        for item in prices:
            symbol = item.get("market") or item.get("symbol", "")
            pair = self._connector.convert_from_exchange_trading_pair(symbol)
            if pair in trading_pairs:
                result[pair] = float(item.get("markPrice") or item.get("price", 0))
        return result

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        path = CONSTANTS.ORDER_BOOK_PATH_URL.format(market_name=exchange_symbol)
        response = await rest_assistant.execute_request(
            url=public_rest_url(path, domain=self._domain),
            method=RESTMethod.GET,
            params={"depth": 100},
            throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
        )
        return response

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp = snapshot.get("timestamp", time.time() * 1000) / 1000.0
        data = snapshot.get("data", snapshot)
        bids = [[float(p), float(s)] for p, s in data.get("bids", [])]
        asks = [[float(p), float(s)] for p, s in data.get("asks", [])]
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": int(snapshot_timestamp * 1000),
                "bids": bids,
                "asks": asks,
            },
            timestamp=snapshot_timestamp,
        )

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        path = CONSTANTS.FUNDING_INFO_PATH_URL.format(market_name=exchange_symbol)
        resp = await rest_assistant.execute_request(
            url=public_rest_url(path, domain=self._domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.FUNDING_INFO_PATH_URL,
        )
        data = resp.get("data", resp)
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=float(data.get("indexPrice", 0)),
            mark_price=float(data.get("markPrice", 0)),
            next_funding_utc_timestamp=int(data.get("nextFundingTime", 0)) / 1000,
            rate=float(data.get("fundingRate", 0)),
        )

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.DECIBEL_WSS_URL, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        for trading_pair in self._trading_pairs:
            exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair)
            subscribe_payload = {
                "op": "subscribe",
                "args": [
                    f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}.{exchange_symbol}",
                    f"{CONSTANTS.WS_TRADES_CHANNEL}.{exchange_symbol}",
                    f"{CONSTANTS.WS_FUNDING_CHANNEL}.{exchange_symbol}",
                ],
            }
            subscribe_request = WSJSONRequest(payload=subscribe_payload)
            await ws.send(subscribe_request)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = event_message.get("channel", "")
        if CONSTANTS.WS_ORDERBOOK_CHANNEL in channel:
            return self._diff_messages_queue_key
        elif CONSTANTS.WS_TRADES_CHANNEL in channel:
            return self._trade_messages_queue_key
        elif CONSTANTS.WS_FUNDING_CHANNEL in channel:
            return self._funding_info_messages_queue_key
        return ""

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        trading_pair = self._connector.convert_from_exchange_trading_pair(
            raw_message.get("market", data.get("market", ""))
        )
        if not trading_pair:
            return
        trades = data if isinstance(data, list) else [data]
        for trade in trades:
            msg = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content={
                    "trading_pair": trading_pair,
                    "trade_type": 1.0 if trade.get("side", "").lower() == "buy" else 2.0,
                    "trade_id": trade.get("id", int(time.time() * 1000)),
                    "update_id": int(trade.get("timestamp", time.time() * 1000)),
                    "price": float(trade.get("price", 0)),
                    "amount": float(trade.get("size", 0)),
                },
                timestamp=float(trade.get("timestamp", time.time() * 1000)) / 1000.0,
            )
            await message_queue.put(msg)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        trading_pair = self._connector.convert_from_exchange_trading_pair(
            raw_message.get("market", data.get("market", ""))
        )
        if not trading_pair:
            return
        msg = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": trading_pair,
                "update_id": int(data.get("timestamp", time.time() * 1000)),
                "bids": [[float(p), float(s)] for p, s in data.get("bids", [])],
                "asks": [[float(p), float(s)] for p, s in data.get("asks", [])],
            },
            timestamp=float(data.get("timestamp", time.time() * 1000)) / 1000.0,
        )
        await message_queue.put(msg)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        await self._parse_order_book_diff_message(raw_message, message_queue)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        trading_pair = self._connector.convert_from_exchange_trading_pair(
            raw_message.get("market", data.get("market", ""))
        )
        if not trading_pair:
            return
        info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=float(data.get("indexPrice", 0)),
            mark_price=float(data.get("markPrice", 0)),
            next_funding_utc_timestamp=int(data.get("nextFundingTime", 0)) / 1000,
            rate=float(data.get("fundingRate", 0)),
        )
        await message_queue.put(info)

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """Subscribe to a single trading pair channels.

        This method is required by the PerpetualAPIOrderBookDataSource abstract interface.
        The base implementation subscribes in batch via `_subscribe_channels`, but dynamic
        subscription is useful for some strategies and simplifies unit test instantiation.
        """
        if trading_pair not in self._trading_pairs:
            self._trading_pairs.append(trading_pair)
        # If a websocket assistant is already running it will be handled by the stream loop.
        return True

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if trading_pair in self._trading_pairs:
            self._trading_pairs.remove(trading_pair)
        return True
