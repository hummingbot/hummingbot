import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.bittrex import bittrex_constants as CONSTANTS, bittrex_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class BittrexAPIOrderBookDataSource(OrderBookTrackerDataSource):

    def __init__(self, trading_pairs: List[str], connector, api_factory: WebAssistantsFactory, ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_KEY
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_KEY
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.BITTREX_WS_URL,
                         ping_timeout=CONSTANTS.PING_TIMEOUT)
        return ws

    # TODO TO BE REFACTORED INTO EXCHANGE CLASS
    '''
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"{BITTREX_REST_URL}{BITTREX_TICKER_PATH}")
            resp_json = await resp.json()
            for trading_pair in trading_pairs:
                resp_record = [o for o in resp_json if o["symbol"] == trading_pair][0]
                results[trading_pair] = float(resp_record["lastTradeRate"])
        return results'''

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            "marketSymbol": exchange_symbol,
        }
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.ORDERBOOK_SNAPSHOT_URL.format(exchange_symbol)),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDERBOOK_SNAPSHOT_LIMIT_ID,
        )
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = self.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            trade_params = []
            market_params = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                trade_params.append(f"trade_{symbol}")
                market_params.append(f"orderBook_{symbol}_25")
            payload = {
                "channels": trade_params
            }
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

            payload = {
                "channels": market_params,
            }
            subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_trade_request)
            await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = self._trade_messages_queue_key
        if "depth" in event_message:
            channel = self._diff_messages_queue_key
        return channel

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["marketSymbol"])
        trade_message = self.trade_message_from_exchange(raw_message, {"trading_pair": trading_pair})
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["marketSymbol"])
        order_book_message: OrderBookMessage = self.diff_message_from_exchange(raw_message, time.time(), {"trading_pair": trading_pair})
        message_queue.put_nowait(order_book_message)

    def snapshot_message_from_exchange(self, msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": int(timestamp),
            "bids": msg["bid"],
            "asks": msg["ask"]
        }, timestamp=timestamp)

    def trade_message_from_exchange(msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.TRADE, {
                "trading_pair": msg["trading_pair"],
                "trade_type": float(TradeType.BUY.value) if msg["deltas"]["takerSide"] == "BUY" else float(TradeType.SELL.value),
                "trade_id": msg["deltas"]["id"],
                "update_id": msg["sequence"],
                "price": msg["deltas"]["rate"],
                "amount": msg["deltas"]["quantity"]
            }, timestamp=timestamp)

    def diff_message_from_exchange(msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.DIFF, {
                "trading_pair": msg["trading_pair"],
                "update_id": int(msg["sequence"]),
                "bids": msg["bidDeltas"],
                "asks": msg["askDeltas"]
            }, timestamp=timestamp)
