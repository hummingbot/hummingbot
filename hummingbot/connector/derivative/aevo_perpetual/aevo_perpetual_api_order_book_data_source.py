import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_utils import (
    convert_to_exchange_trading_pair,
)
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class AevoPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "AevoPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs = trading_pairs

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Get last traded prices for the given trading pairs.
        """
        result = {}
        for trading_pair in trading_pairs:
            try:
                exchange_pair = convert_to_exchange_trading_pair(trading_pair)
                url = web_utils.public_rest_url(
                    path_url=f"{CONSTANTS.TICKER_URL}?instrument_name={exchange_pair}",
                    domain=domain or self._domain,
                )
                rest_assistant = await self._api_factory.get_rest_assistant()
                response = await rest_assistant.execute_request(
                    url=url,
                    method=RESTMethod.GET,
                    throttler_limit_id=CONSTANTS.TICKER_URL,
                )
                if response:
                    result[trading_pair] = float(response.get("last_price", 0))
            except Exception:
                pass
        return result

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Request order book snapshot from REST API.
        """
        exchange_pair = convert_to_exchange_trading_pair(trading_pair)
        url = web_utils.public_rest_url(
            path_url=f"{CONSTANTS.ORDERBOOK_URL}?instrument_name={exchange_pair}",
            domain=self._domain,
        )
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDERBOOK_URL,
        )
        return response

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Get order book snapshot and convert to OrderBookMessage.
        """
        snapshot = await self._request_order_book_snapshot(trading_pair)
        timestamp = time.time()

        bids = [[float(bid[0]), float(bid[1])] for bid in snapshot.get("bids", [])]
        asks = [[float(ask[0]), float(ask[1])] for ask in snapshot.get("asks", [])]

        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": int(timestamp * 1000),
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp,
        )

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse trade message from WebSocket.
        """
        data = raw_message.get("data", {})
        if not data:
            return

        trading_pair = self._connector.exchange_symbol_associated_to_pair(
            data.get("instrument_name", "")
        )
        if trading_pair not in self._trading_pairs:
            return

        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": trading_pair,
                "trade_type": "buy" if data.get("side") == "buy" else "sell",
                "trade_id": data.get("trade_id", str(time.time())),
                "update_id": int(time.time() * 1000),
                "price": float(data.get("price", 0)),
                "amount": float(data.get("amount", 0)),
            },
            timestamp=float(data.get("timestamp", time.time() * 1e9)) / 1e9,
        )
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse order book diff message from WebSocket.
        """
        data = raw_message.get("data", {})
        if not data:
            return

        trading_pair = self._connector.exchange_symbol_associated_to_pair(
            data.get("instrument_name", "")
        )
        if trading_pair not in self._trading_pairs:
            return

        timestamp = float(data.get("timestamp", time.time() * 1e9)) / 1e9
        bids = [[float(bid[0]), float(bid[1])] for bid in data.get("bids", [])]
        asks = [[float(ask[0]), float(ask[1])] for ask in data.get("asks", [])]

        order_book_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": trading_pair,
                "update_id": int(timestamp * 1000),
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp,
        )
        message_queue.put_nowait(order_book_message)

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribe to order book and trade channels.
        """
        for trading_pair in self._trading_pairs:
            exchange_pair = convert_to_exchange_trading_pair(trading_pair)

            orderbook_subscribe = {
                "op": "subscribe",
                "data": [f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:{exchange_pair}"],
            }
            await ws.send(WSJSONRequest(payload=orderbook_subscribe))

            trades_subscribe = {
                "op": "subscribe",
                "data": [f"{CONSTANTS.WS_TRADES_CHANNEL}:{exchange_pair}"],
            }
            await ws.send(WSJSONRequest(payload=trades_subscribe))

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and connect WebSocket assistant.
        """
        ws_url = web_utils.wss_url(domain=self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        """
        Process incoming WebSocket messages.
        """
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            channel = data.get("channel", "")

            if CONSTANTS.WS_ORDERBOOK_CHANNEL in channel:
                await self._parse_order_book_diff_message(data, self._message_queue[CONSTANTS.WS_ORDERBOOK_CHANNEL])
            elif CONSTANTS.WS_TRADES_CHANNEL in channel:
                await self._parse_trade_message(data, self._message_queue[CONSTANTS.WS_TRADES_CHANNEL])

    async def listen_for_subscriptions(self):
        """
        Main loop for WebSocket subscription handling.
        """
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in WebSocket subscription loop")
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Get funding info for a trading pair.
        """
        exchange_pair = convert_to_exchange_trading_pair(trading_pair)
        url = web_utils.public_rest_url(
            path_url=f"{CONSTANTS.FUNDING_URL}?instrument_name={exchange_pair}",
            domain=self._domain,
        )
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.FUNDING_URL,
        )

        funding_info = FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(str(response.get("index_price", 0))),
            mark_price=Decimal(str(response.get("mark_price", 0))),
            next_funding_utc_timestamp=int(response.get("next_funding_time", 0)),
            rate=Decimal(str(response.get("funding_rate", 0))),
        )
        return funding_info
